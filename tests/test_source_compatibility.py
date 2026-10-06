"""Schema and revision tests use synthetic OOXML fixtures, not patient records."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZipFile

import pytest
from oart_analysis.cli import main
from oart_analysis.io import (
    REQUIRED, STRATEGY_ALIASES, STRATEGY_HEADERS, STRATEGY_SUMMARY_HEADERS,
    STRATEGY_INTERNAL_KEY, col_name, read_source, resolve_strategy_sheet,
    workbook_fingerprints, sha256,
)
from oart_analysis.plot_data import load_bundled, export_bundle

S='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def strategy_cells():
    values={f'{col_name(i)}1':h for i,h in enumerate(STRATEGY_HEADERS)}
    values.update({f'{col_name(i+8)}1':h for i,h in enumerate(STRATEGY_SUMMARY_HEADERS)})
    return values


def fixture_cells(name=STRATEGY_ALIASES[-1]):
    cells={key:{'A1':'synthetic header'} for key in REQUIRED}
    cells[name]=strategy_cells()
    cells['README']={'A15':name,'B35':name+'; Retrospective patient metrics'}
    return cells


def write_fixture(path, cells):
    names=[];relationships=[]
    with ZipFile(path, 'w') as z:
        for i,(name,values) in enumerate(cells.items(),start=1):
            names.append(f'<sheet name={quoteattr(name)} sheetId="{i}" r:id="rId{i}"/>')
            relationships.append(f'<Relationship Id="rId{i}" Target="worksheets/sheet{i}.xml"/>')
            records=''.join(f'<c r="{address}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>' for address,value in values.items())
            z.writestr(f'xl/worksheets/sheet{i}.xml',f'<worksheet xmlns="{S}"><sheetData><row r="1">{records}</row></sheetData></worksheet>')
        z.writestr('xl/workbook.xml',f'<workbook xmlns="{S}" xmlns:r="{R}"><sheets>{"".join(names)}</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels',f'<Relationships>{"".join(relationships)}</Relationships>')
    return path


@pytest.mark.parametrize('name',STRATEGY_ALIASES)
def test_supported_alias_with_both_schema_blocks(name):
    assert resolve_strategy_sheet(fixture_cells(name))==(name,'known_alias')


def test_current_tab_is_31_characters_and_not_readme_display_name():
    assert len(STRATEGY_ALIASES[-1])==31
    assert STRATEGY_ALIASES[-1]!='Extended Data Fig. 4 GTVn comparison'


@pytest.mark.parametrize('name',['Arbitrary GTVn tab','ED4 results','GTVn comparison table'])
def test_custom_exact_override(name):
    cells=fixture_cells(name)
    with pytest.raises(ValueError,match='--strategy-sheet'): resolve_strategy_sheet(cells)
    assert resolve_strategy_sheet(cells,name)==(name,'explicit')


@pytest.mark.parametrize('bad_address',['A1','D1','F1','I1','L1','N1'])
def test_wrong_schema_rejected_even_for_known_alias(bad_address):
    cells=fixture_cells();cells[STRATEGY_ALIASES[-1]][bad_address]='incorrect header'
    with pytest.raises(ValueError,match='header schema'): resolve_strategy_sheet(cells)


def test_explicit_override_does_not_bypass_schema():
    with pytest.raises(ValueError,match='header schema'):
        resolve_strategy_sheet(fixture_cells(),'Prospective patient metrics')


def test_ambiguity_is_not_silently_resolved():
    cells=fixture_cells();cells[STRATEGY_ALIASES[0]]=strategy_cells()
    with pytest.raises(ValueError,match='unambiguous'): resolve_strategy_sheet(cells)
    assert resolve_strategy_sheet(cells,STRATEGY_ALIASES[-1])[1]=='explicit'


def test_missing_explicit_tab_lists_names():
    with pytest.raises(ValueError,match='available worksheets'):
        resolve_strategy_sheet(fixture_cells(),'not a sheet')


def test_fingerprint_ignores_readme_and_strategy_rename():
    a=fixture_cells();first=STRATEGY_ALIASES[-1]
    b=deepcopy(a);b['README']['A15']='different display text'
    b['ED4 GTVn comparison']=b.pop(first)
    assert workbook_fingerprints(a,first)==workbook_fingerprints(b,'ED4 GTVn comparison')


def test_fingerprint_detects_data_change():
    a=fixture_cells();b=deepcopy(a);b['Table S4']['A2']=.9123
    assert workbook_fingerprints(a,STRATEGY_ALIASES[-1])!=workbook_fingerprints(b,STRATEGY_ALIASES[-1])


def test_reader_warns_but_does_not_rewrite_readme(tmp_path):
    cells=fixture_cells();cells['README'].update(A15='Extended Data Fig. 4 GTVn comparison',
        B35='Extended Data Fig. 4 GTVn comparison; Retrospective patient metrics',
        E39='Use linear-interpolated quantiles and state the final display-rounding convention.')
    path=write_fixture(tmp_path/'synthetic.xlsx',cells); before=sha256(path)
    result=read_source(path)
    assert sha256(path)==before
    assert len(result['metadata']['readme_warnings'])==3
    assert result['metadata']['strategy_worksheet']==STRATEGY_ALIASES[-1]
    assert result['metadata']['source_profile_match']['status']=='different_stored_data'


def test_inspection_does_not_claim_statistical_validation(tmp_path):
    path=write_fixture(tmp_path/'R\u00e9sum\u00e9 Source.xlsx',fixture_cells())
    output=tmp_path/'inspection'
    assert main(['inspect-source','--source-data',str(path),'--output',str(output)])==0
    report=json.loads((output/'source_inspection.json').read_text())
    assert report['full_patient_level_analysis'] is False
    assert report['complete_S6_available'] is False
    assert report['source_sha256']==sha256(path)
    assert len(list(output.iterdir()))==1


def test_explicit_override_is_passed_by_cli(tmp_path):
    path=write_fixture(tmp_path/'renamed.xlsx',fixture_cells('My GTVn Data'))
    output=tmp_path/'inspect'
    assert main(['inspect-source','--source-data',str(path),'--strategy-sheet','My GTVn Data','--output',str(output)])==0
    report=json.loads((output/'source_inspection.json').read_text())
    assert report['strategy_worksheet']=='My GTVn Data' and report['strategy_selection']=='explicit'


@pytest.mark.parametrize('command',['all','sample-size','metrics'])
def test_override_requires_workbook(command,tmp_path):
    with pytest.raises(SystemExit) as error:
        main([command,'--strategy-sheet','some tab','--output',str(tmp_path/'new')])
    assert error.value.code==2
    assert not (tmp_path/'new').exists()


def test_unknown_name_cli_does_not_fallback(tmp_path,capsys):
    path=write_fixture(tmp_path/'unknown.xlsx',fixture_cells('Unknown'))
    output=tmp_path/'new'
    assert main(['all','--source-data',str(path),'--output',str(output)])==1
    assert '--strategy-sheet' in capsys.readouterr().err
    assert not output.exists()


def test_bundle_preserves_actual_workbook_provenance(tmp_path):
    data,meta=load_bundled()
    assert meta['source_strategy_worksheet']==STRATEGY_ALIASES[-1]
    manifest=export_bundle(data,meta,tmp_path/'bundle')
    assert manifest['source_strategy_worksheet']==meta['source_strategy_worksheet']
    assert manifest['source_workbook_sha256']==meta['source_workbook_sha256']
    assert manifest['source_data_values_sha256']==meta['source_data_values_sha256']
