"""Complete-data checks are opt-in; no private workbook or synthetic clinical data is bundled."""
import copy
import csv
import json
import os
import random
from pathlib import Path
import math
import numpy as np
import pytest
from scipy import stats
from oart_analysis.io import read_source, sha256
from oart_analysis.analysis import analyse, validate_metrics, compute_composites, calculate_table
from oart_analysis.constants import ENDPOINTS, TARGETS, METRICS, GROUP_LABELS, SMALL, LARGE
from oart_analysis.plot_data import from_workbook, load_bundled, DATASETS

pytestmark=pytest.mark.workbook

@pytest.fixture(scope='module')
def source():
    value=os.getenv('NPC_OART_SOURCE_DATA')
    if not value: pytest.skip('Set NPC_OART_SOURCE_DATA to an approved local full Source_data.xlsx')
    path=Path(value)
    if not path.is_file(): pytest.fail('NPC_OART_SOURCE_DATA points to a missing workbook; no fallback')
    return read_source(path),path

@pytest.fixture(scope='module')
def run(source,tmp_path_factory):
    data,path=source;before=sha256(path)
    output=tmp_path_factory.mktemp('full-reanalysis')
    report=analyse(data,output)
    assert sha256(path)==before
    return report,output


def test_full_recalculation_report(run):
    report,_=run
    expected={'paired_comparisons':405,'significance_classifications_matched':405,'table_cells_verified':8505,
              'composite_values_verified':1236,'external_summary_values_verified':1008,
              'GTVn_reused_values_verified':72,'patients_prospective':135,'S6_rows':81,'S6_summary_numbers':729}
    for key,value in expected.items(): assert report[key]==value
    assert report['raw_imaging_verified'] is False
    assert report['clinical_model_execution'] is False


def test_s6_all_roi_rows_and_role(run):
    with (run[1]/'Table_S6.csv').open() as f: rows=list(csv.DictReader(f))
    assert len(rows)==81 and {r['n'] for r in rows}=={'135'}
    assert {r['Metric'] for r in rows}==set(METRICS)
    assert sum(r['endpoint_role']=='primary' for r in rows)==6
    assert sum(r['endpoint_role']=='supportive' for r in rows)==21
    assert sum(r['endpoint_role']=='secondary' for r in rows)==54
    assert len({r['ROI'] for r in rows})==27


@pytest.mark.parametrize('roi,expected',[('GTVp',(.940,.936,.944)),('GTVn',(.790,.783,.797)),
                                       ('CTV1',(.910,.906,.914)),('CTV2',(.900,.896,.904)),
                                       (GROUP_LABELS['Small OARs'],(.904,.902,.906)),(GROUP_LABELS['Large OARs'],(.905,.904,.906))])
def test_main_dsc_mean_ci(run,roi,expected):
    with (run[1]/'Table_S6.csv').open() as f:
        r=next(r for r in csv.DictReader(f) if r['Metric']=='DSC' and r['ROI']==roi)
    assert [float(f"{float(r[k]):.3f}") for k in ('mean','ci_lower','ci_upper')]==list(expected)


def test_timing_against_patientwise_oracle(source,run):
    rows=source[0]['Prospective timing'];x=np.array([[r[k] for k in ['Algorithm-processing time (s)','Review-and-modification interval (s)']] for r in rows])
    summed=x.sum(axis=1)
    assert np.mean(summed)==pytest.approx(318.9985185185185)
    assert np.std(summed,ddof=1)==pytest.approx(30.673669653332)
    np.testing.assert_allclose(np.percentile(summed,[5,50,95]),[267.18,318.3,372.3])


def test_pairing_independent_of_row_order(source):
    rows=source[0]['Retrospective patient metrics'];targets=[r for r in rows if r['ROI'] in TARGETS]
    complete=targets+compute_composites(rows)
    a=calculate_table(complete,ENDPOINTS)
    random.Random(592).shuffle(complete)
    assert a==calculate_table(complete,ENDPOINTS)


@pytest.mark.parametrize('defect',['duplicate','missing','range','code','group','unit'])
def test_patient_data_validation_rejects_defects(source,defect):
    rows=copy.deepcopy(source[0]['Prospective patient metrics'])
    if defect=='duplicate': rows.append(dict(rows[0]))
    elif defect=='missing': rows.pop()
    elif defect=='range': next(r for r in rows if r['Metric']=='DSC')['Value']=1.5
    elif defect=='code': rows[0]['ROI code']='not_the_same_code'
    elif defect=='group': rows[0]['ROI group']='not_the_same_group'
    else: rows[0]['Unit']='cm'
    with pytest.raises(ValueError): validate_metrics(rows,True)


def test_missing_constituent_not_averaged(source):
    rows=source[0]['Prospective patient metrics']
    removed=False;broken=[]
    for r in rows:
        if r['ROI'] in SMALL and not removed: removed=True
        else: broken.append(r)
    with pytest.raises(ValueError,match='Incomplete OAR composite'):compute_composites(broken)


def test_paired_missing_patient_is_not_silently_dropped(source):
    rows=source[0]['Retrospective patient metrics'];complete=[r for r in rows if r['ROI'] in TARGETS]+compute_composites(rows)
    complete.pop(0)
    with pytest.raises(ValueError,match='Unmatched pairs'):calculate_table(complete,ENDPOINTS)


def test_bundled_and_workbook_plot_data_match(source):
    from_workbook_data,_=from_workbook(source[0]);bundled_data,_=load_bundled()
    for key in DATASETS:
        assert from_workbook_data[key]==bundled_data[key]


def test_roi_composite_sd_not_mean_of_organ_sds(source,run):
    pro=source[0]['Prospective patient metrics']
    organ_sds=[np.std([r['Value'] for r in pro if r['ROI']==roi and r['Metric']=='DSC'],ddof=1) for roi in SMALL]
    composite=compute_composites(pro)
    values=[r['Value'] for r in composite if r['ROI']==GROUP_LABELS['Small OARs'] and r['Metric']=='DSC']
    assert abs(np.std(values,ddof=1)-np.mean(organ_sds))>0.001
    assert len(values)==135
