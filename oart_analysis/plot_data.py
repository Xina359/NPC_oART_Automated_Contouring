"""The same six public plotting data categories in bundled and workbook modes.

Numeric records retain their source precision, actual worksheet names and
cell references; missing patient-level data are never fabricated."""
from __future__ import annotations
from collections import defaultdict
from importlib.resources import files
from pathlib import Path
import csv
import hashlib
import io
import itertools
import json
import math
import numpy as np
from .constants import *
from .analysis import case_values,probability,significant
from .io import unique_index,require_numeric,finite_number,write_csv,write_json
from . import __version__

DATASETS={'summary_s4':'table_s4_plot.csv','summary_s5':'table_s5_plot.csv',
          'performance':'prospective_endpoints.csv','timing':'prospective_timing.csv',
          'gtvn':'gtvn_strategies.csv','case':'representative_oar_case.csv'}
COUNTS={'summary_s4':90,'summary_s5':315,'performance':2430,'timing':135,'gtvn':108,'case':21}
SUMMARY_MAP={'centre':'Centre','roi':'ROI','metric':'Metric','n':'Paired n','unit':'Unit',
    'before_model':'Before model','after_model':'After model','before_mean':'Before mean',
    'after_mean':'After mean','before_sd':'Before SD','after_sd':'After SD',
    'mean_difference':'Mean difference (after-before)','ci_lower':'95% CI lower',
    'ci_upper':'95% CI upper','p_value':'Two-sided paired t-test P','q_value':'BH-adjusted q'}


def from_workbook(source,full_analysis_performed=False):
    result={}
    for key,sheet in (('summary_s4','Table S4'),('summary_s5','Table S5')):
        out=[]
        for raw in source[sheet]:
            row={k:raw[v] for k,v in SUMMARY_MAP.items()};n=int(raw['source_row'])
            row['n']=int(row['n']);row['p_value']=str(row['p_value']);row['q_value']=str(row['q_value'])
            row.update(roi_group=raw['ROI group'],source_sheet=sheet,source_row=n,
                before_cell=f'H{n}',after_cell=f'P{n}',difference_cell=f'W{n}',q_cell=f'AB{n}')
            out.append(row)
        result[key]=out
    lookup=defaultdict(list)
    for row in source['Prospective patient metrics']: lookup[(row['Study ID'],row['Metric'])].append(row)
    performance=[]
    for study_id in sorted({k[0] for k in lookup}):
        for metric in METRICS:
            rows=lookup[(study_id,metric)]
            for category in (*TARGETS,'Large OARs','Small OARs'):
                grouped=category in GROUPS;matches=[r for r in rows if r['ROI group' if grouped else 'ROI']==category]
                count=len(GROUPS[category]) if grouped else 1
                if len(matches)!=count or (grouped and {r['ROI'] for r in matches}!=set(GROUPS[category])): raise ValueError('Incomplete prospective endpoint')
                performance.append({'study_id':study_id,'category':category,'category_type':'Grouped OARs' if grouped else 'Target',
                    'metric':metric,'value':float(np.mean([r['Value'] for r in matches])),'unit':unit(metric),'n_components':count,
                    'source_sheet':'Prospective patient metrics','source_rows':';'.join(str(r['source_row']) for r in matches),
                    'source_cells':';'.join(f"H{r['source_row']}" for r in matches),
                    'derivation':f'within-patient mean across {count} OARs' if grouped else 'direct ROI value'})
    result['performance']=performance
    result['timing']=[{'study_id':r['Study ID'],'algorithm_s':r[TIMES[0]],'review_s':r[TIMES[1]],'combined_s':r[TIMES[2]],
        'source_sheet':'Prospective timing','source_row':int(r['source_row']),
        'algorithm_cell':f"B{r['source_row']}",'review_cell':f"C{r['source_row']}",'combined_cell':f"D{r['source_row']}"} for r in source['Prospective timing']]
    result['gtvn']=source['Fig S4 GTVn comparison']
    result['case']=case_values(source['Retrospective patient metrics'])
    validate(result)
    return result,{'input_mode':'workbook',**source['metadata'],
                   'full_patient_level_analysis':bool(full_analysis_performed),'complete_S6_available':bool(full_analysis_performed)}


def _metric(v,m,u):
    if m not in METRICS or not finite_number(v) or v<0 or (m=='DSC' and v>1) or u!=unit(m):
        raise ValueError('Invalid metric, value or unit')


def validate(data):
    if set(data)!=set(DATASETS): raise ValueError('Exactly six public plotting datasets are required')
    for name in DATASETS:
        if len(data[name])!=COUNTS[name]: raise ValueError(f'Incorrect record count: {name}')
    for name,rois in (('summary_s4',ENDPOINTS),('summary_s5',(*SMALL,*LARGE))):
        rows=data[name];index=unique_index(rows,('centre','roi','metric'),name)
        if set(index)!=set(itertools.product(CENTRES,rois,METRICS)): raise ValueError(f'Incomplete endpoint coverage: {name}')
        for r in rows:
            if r['n']!=expected_n(r['centre'],r['roi']) or (r['before_model'],r['after_model'])!=models(r['centre']): raise ValueError('Invalid comparison')
            for state in ('before','after'):
                _metric(r[state+'_mean'],r['metric'],r['unit'])
                if not finite_number(r[state+'_sd']) or r[state+'_sd']<0: raise ValueError('Invalid standard deviation')
            require_numeric([r],('mean_difference','ci_lower','ci_upper'),name)
            if not r['ci_lower']<=r['mean_difference']<=r['ci_upper']: raise ValueError('Invalid confidence interval')
            if abs(r['after_mean']-r['before_mean']-r['mean_difference'])>.000150001: raise ValueError('Inconsistent rounded means')
            probability(r['p_value']);probability(r['q_value']);significant(r['q_value'])
    pro=data['performance'];ids={r['study_id'] for r in pro}
    index=unique_index(pro,('study_id','category','metric'),'prospective endpoints')
    if len(ids)!=135 or set(index)!=set(itertools.product(ids,(*TARGETS,*GROUPS),METRICS)): raise ValueError('Incomplete prospective patients')
    for r in pro:
        _metric(r['value'],r['metric'],r['unit'])
        if r['n_components']!=(len(GROUPS[r['category']]) if r['category'] in GROUPS else 1): raise ValueError('Wrong constituent count')
        if r['category_type']!=('Grouped OARs' if r['category'] in GROUPS else 'Target'): raise ValueError('Wrong category type')
    index=unique_index(data['timing'],('study_id',),'timing')
    if set(index)!={(p,) for p in ids}: raise ValueError('Timing and prospective IDs differ')
    for r in data['timing']:
        require_numeric([r],('algorithm_s','review_s','combined_s'),'timing')
        if min(r[k] for k in ('algorithm_s','review_s','combined_s'))<0 or abs(r['algorithm_s']+r['review_s']-r['combined_s'])>1e-9: raise ValueError('Invalid timing sum')
    ids={r['Study ID'] for r in data['gtvn']};idx=unique_index(data['gtvn'],('Study ID','Strategy','Metric'),'GTVn')
    if len(ids)!=12 or set(idx)!=set(itertools.product(ids,STRATEGIES,METRICS)): raise ValueError('Incomplete GTVn strategies')
    for r in data['gtvn']:
        _metric(r['Value'],r['Metric'],r['Unit'])
        if r['Centre']!='Main centre' or r['ROI']!='GTVn': raise ValueError('Unexpected GTVn labels')
    if set(unique_index(data['case'],('study_id','roi'),'case'))!={('MC_R023',r) for r in (*SMALL,*LARGE)}: raise ValueError('Wrong representative case')
    for r in data['case']:
        if (r['group'],r['roi']) not in CASE_ORDER: raise ValueError('Incorrect case anatomical group')
        for m in METRICS:
            k=m.lower()
            for state in ('baseline','vag'): _metric(r[state+'_'+k],m,unit(m))
            change=(r['vag_'+k]-r['baseline_'+k])*(1 if m=='DSC' else -1)
            if not finite_number(r['beneficial_change_'+k]) or abs(change-r['beneficial_change_'+k])>1e-12: raise ValueError('Case effect mismatch')
    return {'checks':'passed','dataset_rows':{k:len(v) for k,v in data.items()},
        'scope':'six plotting datasets only; not complete patient-level retrospective or all-organ prospective reanalysis'}


def export_bundle(data,provenance,directory):
    """Explicit export of the same six public data categories; never the workbook."""
    validate(data);directory=Path(directory)
    if directory.exists() and any(directory.iterdir()): raise ValueError('Bundle export requires an empty output directory')
    directory.mkdir(parents=True,exist_ok=True)
    manifest={'schema_version':2,'dataset_version':__version__,
        'source_workbook_sha256':provenance.get('source_sha256',provenance.get('source_workbook_sha256')),
        'source_filename':provenance.get('source_filename'),
        'source_strategy_worksheet':provenance.get('strategy_worksheet',provenance.get('source_strategy_worksheet')),
        'source_data_values_sha256':provenance.get('stored_data_fingerprint',{}).get('data_values_sha256',provenance.get('source_data_values_sha256')),
        'numeric_storage':'binary64 values serialized with 17 significant digits; no new intermediate rounding',
        'scope':'six public numerical data categories; no full workbook or raw images','datasets':{}}
    for name,filename in DATASETS.items():
        rows=data[name];write_csv(rows,directory/filename)
        types={k:'int' if k in ('n','n_components','source_row') else 'float' if finite_number(v) else 'str' for k,v in rows[0].items()}
        manifest['datasets'][name]={'file':filename,'rows':len(rows),'types':types,
            'sha256':hashlib.sha256((directory/filename).read_bytes()).hexdigest()}
    write_json(manifest,directory/'manifest.json')
    return manifest


def load_bundled():
    directory=files('oart_analysis').joinpath('data');raw_manifest=directory.joinpath('manifest.json').read_bytes();manifest=json.loads(raw_manifest)
    if manifest['schema_version']!=2 or set(manifest['datasets'])!=set(DATASETS): raise ValueError('Unsupported bundled manifest')
    data={}
    for name,filename in DATASETS.items():
        spec=manifest['datasets'][name]
        if spec['file']!=filename: raise ValueError('Unexpected dataset filename')
        raw=directory.joinpath(filename).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=spec['sha256']: raise ValueError(f'Checksum mismatch: {filename}')
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        if reader.fieldnames!=list(spec['types']): raise ValueError('CSV column schema mismatch')
        rows=[]
        for r in reader:
            if None in r or any(v is None for v in r.values()): raise ValueError('Malformed CSV row')
            converted={}
            for k,kind in spec['types'].items():
                v=r[k]
                if kind=='float': v=float(v)
                elif kind=='int':
                    x=float(v)
                    if not math.isfinite(x) or not x.is_integer(): raise ValueError('Noninteger count/row')
                    v=int(x)
                elif kind!='str': raise ValueError('Unsupported data type')
                converted[k]=v
            rows.append(converted)
        if len(rows)!=spec['rows']: raise ValueError('CSV row count mismatch')
        data[name]=rows
    report=validate(data)
    return data,{'input_mode':'bundled','dataset_version':manifest['dataset_version'],
        'manifest_sha256':hashlib.sha256(raw_manifest).hexdigest(),
        'source_workbook_sha256':manifest['source_workbook_sha256'],
        'source_filename':manifest.get('source_filename'),
        'source_strategy_worksheet':manifest.get('source_strategy_worksheet'),
        'source_data_values_sha256':manifest.get('source_data_values_sha256'),
        'full_patient_level_analysis':False,'complete_S6_available':False,'validation':report}
