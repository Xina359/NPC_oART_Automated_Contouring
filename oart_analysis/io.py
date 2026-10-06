"""Read-only OOXML and CSV I/O using the standard library.

Workbook cells are never changed. Explicit worksheet aliases and stored-cell
fingerprints distinguish schema compatibility from numerical validation."""
from __future__ import annotations
import csv
import hashlib
import json
import math
import numbers
import posixpath
import re
import zipfile
from importlib.resources import files
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET
import numpy as np

S = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REQUIRED = ('Table S4', 'Table S5', 'Retrospective patient metrics', 'Patient-level OAR averages',
            'Prospective patient metrics', 'Prospective timing', 'External-centre summary')
# Keep exact aliases: an arbitrary prefix/fuzzy match must never select clinical data.
# The fourth name is the actual tab in the author's 2026-10-06 supplied workbook.
STRATEGY_ALIASES = ('Fig S4 GTVn comparison', 'ED4 GTVn comparison',
                    'Extended Data Fig 4 GTVn', 'Extended Data Fig. 4 GTVn compa')
STRATEGY_INTERNAL_KEY = 'Fig S4 GTVn comparison'  # retained Python API compatibility
STRATEGY_HEADERS = ('Centre', 'Study ID', 'ROI', 'Strategy', 'Metric', 'Value', 'Unit')
STRATEGY_SUMMARY_HEADERS = ('Strategy', 'Metric', 'n', 'Mean', 'Sample SD', 'Unit')

def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def col_index(address):
    match=re.fullmatch(r'([A-Z]+)([1-9][0-9]*)', address)
    if not match: raise ValueError(f'Invalid cell address: {address}')
    n=0
    for c in match[1]: n=n*26+ord(c)-64
    return n-1, int(match[2])

def col_name(index):
    name=''; n=index+1
    while n:
        n, rem=divmod(n-1,26); name=chr(65+rem)+name
    return name

def _parse_xml(data):
    # Reject document types instead of accepting entity expansion in user input.
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('Document types and entities are not accepted in workbook XML')
    return ET.fromstring(data)

def read_workbook_cells(path):
    path=Path(path)
    if not path.is_file(): raise FileNotFoundError(f'Source Data not found: {path}')
    output={}; formula_cells=[]
    with zipfile.ZipFile(path) as z:
        if sum(i.file_size for i in z.infolist())>300*1024*1024:
            raise ValueError('Uncompressed workbook exceeds the 300 MiB safety limit')
        if len(z.namelist())!=len(set(z.namelist())): raise ValueError('Duplicate ZIP members')
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            for si in _parse_xml(z.read('xl/sharedStrings.xml')):
                strings.append(''.join(t.text or '' for t in si.iter(f'{{{S}}}t')))
        relationships={e.get('Id'):e for e in _parse_xml(z.read('xl/_rels/workbook.xml.rels'))}
        for sh in _parse_xml(z.read('xl/workbook.xml')).findall(f'{{{S}}}sheets/{{{S}}}sheet'):
            name=sh.get('name'); rel=relationships[sh.get(f'{{{R}}}id')]
            if rel.get('TargetMode')=='External': raise ValueError('External worksheet target is unsupported')
            target=rel.get('Target')
            target=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            if not target.startswith('xl/') or '..' in target.split('/'): raise ValueError('Unsafe worksheet target')
            cells={}
            for cell in _parse_xml(z.read(target)).iter(f'{{{S}}}c'):
                address=cell.get('r'); col_index(address)
                v=cell.find(f'{{{S}}}v'); f=cell.find(f'{{{S}}}f'); typ=cell.get('t')
                raw=None if v is None else v.text
                if f is not None:
                    formula_cells.append(f'{name}!{address}')
                    if raw is None: raise ValueError(f'Formula has no cached value: {name}!{address}')
                if typ=='inlineStr': value=''.join(t.text or '' for t in cell.iter(f'{{{S}}}t'))
                elif raw is None: continue
                elif typ=='s': value=strings[int(raw)]
                elif typ in ('str','d','e'): value=raw
                elif typ=='b': value=bool(int(raw))
                else:
                    try: value=float(raw)
                    except (TypeError,ValueError): raise ValueError(f'Invalid numeric cell: {name}!{address}')
                if address in cells: raise ValueError(f'Duplicate cell: {name}!{address}')
                cells[address]=value
            if name in output: raise ValueError(f'Duplicate sheet name: {name}')
            output[name]=cells
    return output, formula_cells

def _records(cells, name, first=0, width=None, allow_blank=False):
    headers={i:cells.get(f'{col_name(i)}1') for i in range(first, first+(width or 0))} if width else {
        col_index(k)[0]:v for k,v in cells.items() if col_index(k)[1]==1}
    if not headers: raise ValueError(f'Missing header: {name}')
    indexes=sorted(headers)
    if any(not isinstance(headers[i],str) or not headers[i].strip() for i in indexes):
        raise ValueError(f'Blank/nontext column heading: {name}')
    if len(set(headers.values()))!=len(headers): raise ValueError(f'Duplicate headings: {name}')
    last=max((col_index(k)[1] for k in cells),default=1)
    rows=[]
    for j in range(2,last+1):
        row={headers[i]:cells.get(f'{col_name(i)}{j}') for i in indexes}
        if all(v is None for v in row.values()):
            if allow_blank: continue
            raise ValueError(f'Empty data row: {name}!{j}')
        row['source_row']=j; rows.append(row)
    return rows

def resolve_strategy_sheet(cells: dict, strategy_sheet: str | None = None) -> tuple[str, str]:
    """Resolve one exact sheet, then validate both data blocks without modifying it.

    Unknown names require an explicit override. Multiple aliases are an error,
    even if their contents are identical; an override records the user's choice.
    """
    if strategy_sheet is not None:
        if strategy_sheet not in cells:
            raise ValueError(f"Requested GTVn strategy worksheet {strategy_sheet!r} not found; "
                             f"available worksheets: {list(cells)}")
        selected, method = strategy_sheet, 'explicit'
    else:
        matches = [name for name in STRATEGY_ALIASES if name in cells]
        if len(matches) != 1:
            raise ValueError('Expected one unambiguous GTVn strategy worksheet; '
                             f'found {matches}. Known aliases: {list(STRATEGY_ALIASES)}. '
                             f'Available worksheets: {list(cells)}. For an intentional rename, '
                             'pass --strategy-sheet with the exact tab name; headers will be validated.')
        selected, method = matches[0], 'known_alias'
    selected_cells = cells[selected]
    for first, expected, label in ((0, STRATEGY_HEADERS, 'A:G'),
                                    (8, STRATEGY_SUMMARY_HEADERS, 'I:N')):
        actual = tuple(selected_cells.get(f'{col_name(i)}1')
                       for i in range(first, first + len(expected)))
        if actual != expected:
            raise ValueError(f'GTVn worksheet {selected!r} has an invalid {label} header schema: '
                             f'expected {expected}, got {actual}')
    return selected, method


def workbook_fingerprints(cells: dict, strategy_sheet: str) -> dict:
    """Hash stored values in the eight data sheets, separately from README/layout.

    Logical sheet IDs make legitimate strategy-tab renames data-equivalent.
    Neither this fingerprint nor a matching hash validates raw clinical images.
    """
    per_sheet = {}
    for logical in (*REQUIRED, STRATEGY_INTERNAL_KEY):
        actual = strategy_sheet if logical == STRATEGY_INTERNAL_KEY else logical
        ordered = sorted(cells[actual].items(), key=lambda item: (col_index(item[0])[1],
                                                               col_index(item[0])[0]))
        payload = json.dumps(ordered, ensure_ascii=False, allow_nan=False,
                             separators=(',', ':')).encode('utf-8')
        per_sheet[logical] = hashlib.sha256(payload).hexdigest()
    payload = json.dumps(per_sheet, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return {'scheme': 'ooxml-stored-cells-v1', 'data_sheets_sha256': per_sheet,
            'data_values_sha256': hashlib.sha256(payload).hexdigest()}


def read_source(path, *, strategy_sheet: str | None = None):
    cells, formula_cells = read_workbook_cells(path)
    missing = set(REQUIRED) - set(cells)
    if missing:
        raise ValueError(f'Missing worksheets: {sorted(missing)}')
    strategy, selection = resolve_strategy_sheet(cells, strategy_sheet)
    result = {name: _records(cells[name], name) for name in REQUIRED}
    result[STRATEGY_INTERNAL_KEY] = _records(cells[strategy], strategy, 0, 7)
    result['GTVn stored summary'] = _records(cells[strategy], strategy, 8, 6, allow_blank=True)
    warnings = []
    readme = cells.get('README', {})
    if readme.get('A15') not in (None, strategy):
        warnings.append(f"README!A15 lists {readme['A15']!r}, but the actual GTVn tab is "
                        f"{strategy!r}; the actual tab was used without renaming the input")
    if readme.get('B35') is not None:
        declared = [name.strip() for name in str(readme['B35']).split(';')]
        absent = [name for name in declared if name not in cells]
        if absent:
            warnings.append(f'README!B35 names non-existent worksheet labels: {absent}; '
                            'these descriptive labels are not used as lookup keys')
    if 'Fig. S5' in str(readme.get('E32', '')):
        warnings.append('README!E32 retains the old Fig. S5 label; current figure is Extended Data Fig. 5')
    if 'state the final display-rounding convention' in str(readme.get('E39', '')).lower():
        warnings.append('README!E39 retains a review instruction about display rounding. '
                        'Code uses linear quantiles and a single final decimal round-half-up step; '
                        'README wording is left unchanged')
    if formula_cells:
        warnings.append('Formula cells are read from cached values; formula calculation is not performed')
    fingerprint = workbook_fingerprints(cells, strategy)
    actual_sha = sha256(path)
    profile_path = files('oart_analysis').joinpath('data', 'source_profile.json')
    if profile_path.is_file():
        profile = json.loads(profile_path.read_text(encoding='utf-8'))
        if profile.get('fingerprint_scheme') != fingerprint['scheme']:
            raise ValueError('Unsupported packaged source fingerprint scheme')
        changed = [name for name, value in fingerprint['data_sheets_sha256'].items()
                   if value != profile['data_sheets_sha256'].get(name)]
        revision = ('exact_file' if actual_sha == profile['source_workbook_sha256'] else
                    'same_stored_data' if not changed else 'different_stored_data')
        match = {'profile_id': profile['profile_id'], 'status': revision,
                 'validated_source_sha256': profile['source_workbook_sha256'],
                 'changed_data_sheets': changed,
                 'meaning': 'version identity only; full numerical validation is a separate step'}
    else:
        match = {'status': 'unavailable', 'meaning': 'no packaged reference profile'}
    result['metadata'] = {
        'source_filename': Path(path).name, 'source_sha256': actual_sha,
        'strategy_worksheet': strategy, 'strategy_selection': selection,
        'strategy_internal_key': STRATEGY_INTERNAL_KEY,
        'strategy_worksheet_declared_in_readme': readme.get('A15'),
        'sheet_names': list(cells), 'formula_cells': formula_cells,
        'readme_warnings': warnings, 'source_profile_match': match,
        'stored_data_fingerprint': fingerprint,
        'reader': 'standard-library OOXML; read-only cached-cell reader',
    }
    return result


def unique_index(rows, keys, context):
    out={}
    for row in rows:
        key=tuple(row.get(k) for k in keys)
        if any(v is None or str(v).strip()=='' for v in key): raise ValueError(f'Missing identifier in {context}')
        if key in out: raise ValueError(f'Duplicate key in {context}: {key}')
        out[key]=row
    return out

def finite_number(value):
    return isinstance(value,numbers.Real) and not isinstance(value,(bool,np.bool_)) and math.isfinite(value)

def require_numeric(rows, columns, context):
    for row in rows:
        for col in columns:
            if not finite_number(row.get(col)): raise ValueError(f'Invalid numeric value in {context}/{col} at row {row.get("source_row")}')

def group_records(rows,keys):
    out=defaultdict(list)
    for row in rows: out[tuple(row[k] for k in keys)].append(row)
    return out

def write_csv(rows,path,fields=None):
    rows=list(rows); path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    fields=fields or (list(rows[0]) if rows else [])
    if any(set(r)-set(fields) for r in rows): raise ValueError('CSV rows contain inconsistent fields')
    with path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');writer.writeheader()
        for r in rows:
            writer.writerow({k:format(v,'.17g') if isinstance(v,(float,np.floating)) else v for k,v in r.items()})

def write_json(value,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
