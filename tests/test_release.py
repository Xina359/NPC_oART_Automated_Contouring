"""Packaged resources, scope boundaries, numbering, display and output guards."""
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from oart_analysis import __version__
from oart_analysis.cli import main
from oart_analysis.display import rounded, quantile_display, decimal_quantile
from oart_analysis.io import col_index, col_name, read_workbook_cells, read_source
from oart_analysis.plot_data import load_bundled, validate, export_bundle, DATASETS, COUNTS
from oart_analysis.analysis import probability, significant
from oart_analysis.constants import ALIASES, FIGURES

@pytest.fixture(scope='module')
def bundled():
    return load_bundled()


def test_six_datasets_and_scope(bundled):
    data, meta = bundled
    assert len(data) == 6
    assert sum(len(rows) for rows in data.values()) == 3099
    assert {k: len(rows) for k, rows in data.items()} == COUNTS
    assert meta['input_mode'] == 'bundled'
    assert meta['full_patient_level_analysis'] is False
    assert meta['complete_S6_available'] is False


def test_data_files_survive_export(bundled, tmp_path):
    data, meta = bundled
    manifest = export_bundle(data, meta, tmp_path/'bundle')
    assert len(list((tmp_path/'bundle').glob('*.csv'))) == 6
    for key, filename in DATASETS.items():
        assert manifest['datasets'][key]['rows'] == len(data[key])
        assert hashlib.sha256((tmp_path/'bundle'/filename).read_bytes()).hexdigest() == manifest['datasets'][key]['sha256']
    assert not list((tmp_path/'bundle').rglob('*.xlsx'))
    with pytest.raises(ValueError, match='empty'): export_bundle(data, meta, tmp_path/'bundle')


@pytest.mark.parametrize('mutation', ['duplicate_pair','invalid_dsc','negative_time','wrong_composite_size','wrong_unit','wrong_case','missing_record','invalid_q'])
def test_bundle_rejects_corrupt_data(bundled, mutation):
    data = copy.deepcopy(bundled[0])
    if mutation == 'duplicate_pair': data['summary_s4'][1] = dict(data['summary_s4'][0])
    elif mutation == 'invalid_dsc':
        r=next(r for r in data['performance'] if r['metric']=='DSC');r['value']=1.1
    elif mutation == 'negative_time': data['timing'][0]['review_s']=-1
    elif mutation == 'wrong_composite_size': data['performance'][0]['n_components']=500
    elif mutation == 'wrong_unit': data['summary_s4'][0]['unit']='cm'
    elif mutation == 'wrong_case': data['case'][0]['study_id']='OTHER_CASE'
    elif mutation == 'missing_record': data['gtvn'].pop()
    elif mutation == 'invalid_q': data['summary_s5'][0]['q_value']='unavailable'
    with pytest.raises(ValueError): validate(data)


@pytest.mark.parametrize('value, digits, expected', [(0.744625,2,'0.74'),(0.9095,3,'0.910'),(-0.292491509,3,'-0.292'),(0.154770701,2,'0.15'),(-0.0004,3,'0.000'),(0.1245,3,'0.125')])
def test_single_half_up_display(value,digits,expected):
    assert rounded(value,digits)==expected


def test_linear_quantiles_do_not_double_round():
    assert str(decimal_quantile([0.9094,0.9096], .5))=='0.90950'
    assert quantile_display([0.9094,0.9096], .5)=='0.910'
    assert quantile_display([1,2,3,4], .25)=='1.750'
    with pytest.raises(ValueError): decimal_quantile([1,2], 1.1)


@pytest.mark.parametrize('value, expected',[('<0.0001',True),('<0.05',True),('0.050',False),('0.0499',True),('0.50',False)])
def test_probability_bounds_not_display_significance(value,expected):
    assert significant(value) is expected


@pytest.mark.parametrize('idx',[0,25,26,27,51,52,701,702,16383])
def test_ooxml_column_addresses(idx):
    assert col_index(col_name(idx)+'123')==(idx,123)


def test_ed_numbering_and_legacy_aliases():
    assert tuple(FIGURES)==('5','6','ED4','ED5','ED6','ED7')
    assert ALIASES=={'S4':'ED4','S5':'ED5','S6':'ED6','S7':'ED7'}


def test_cli_sample_size(capsys):
    assert main(['sample-size'])==0
    report=json.loads(capsys.readouterr().out)
    assert (report['evaluable_n'],report['recruitment_n'])==(114,135)


@pytest.mark.parametrize('command',['analyse','extract','export-bundled'])
def test_full_analysis_requires_explicit_workbook(command,capsys,tmp_path):
    with pytest.raises(SystemExit) as e: main([command,'--output',str(tmp_path/'new')])
    assert e.value.code==2
    assert '--source-data' in capsys.readouterr().err
    assert not (tmp_path/'new').exists()


def test_invalid_workbook_does_not_fallback(capsys,tmp_path):
    with pytest.raises(SystemExit): main(['all','--source-data',str(tmp_path/'missing.xlsx'),'--output',str(tmp_path/'out')])
    assert 'no fallback' in capsys.readouterr().err
    assert not (tmp_path/'out').exists()


def test_nonempty_output_rejected(capsys,tmp_path):
    (tmp_path/'keep.txt').write_text('preserve')
    with pytest.raises(SystemExit): main(['all','--output',str(tmp_path)])
    assert 'empty' in capsys.readouterr().err
    assert (tmp_path/'keep.txt').read_text()=='preserve'


def test_input_under_output_rejected(capsys,tmp_path):
    (tmp_path/'Source_data.xlsx').write_text('not a workbook')
    with pytest.raises(SystemExit): main(['all','--source-data',str(tmp_path/'Source_data.xlsx'),'--output',str(tmp_path)])
    assert 'outside' in capsys.readouterr().err


def test_default_does_not_discover_workbook(bundled, tmp_path, monkeypatch, capsys):
    import oart_analysis.plotting
    (tmp_path/'Source_data.xlsx').write_text('invalid workbook that must not be opened')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(oart_analysis.plotting,'render',lambda data,figure,output: output/'dummy')
    assert main(['plot','--figure','S4','--output','new'])==0
    meta=json.loads((tmp_path/'new/data_source.json').read_text())
    assert meta['input_mode']=='bundled' and meta['figure']=='ED4'
    assert meta['full_patient_level_analysis'] is False
    assert 'Legacy selector S4 maps to ED4' in capsys.readouterr().out


def test_fig4_three_internal_axes_only_b(bundled):
    import matplotlib.pyplot as plt
    from oart_analysis.figures.gtvn_strategies import compose
    fig,summary=compose(bundled[0]['gtvn'])
    try:
        assert len(fig.axes)==3 and len(summary)==9
        texts=[text.get_text() for ax in fig.axes for text in ax.texts]+[t.get_text() for t in fig.texts]
        assert 'b' in texts and 'c' not in texts and 'd' not in texts
        assert any('0.74' in t for t in texts)
    finally: plt.close(fig)


@pytest.mark.parametrize('figure',['5','ED6'])
def test_comparison_ci_limits_include_every_record(bundled,figure):
    import matplotlib.pyplot as plt
    from oart_analysis.figures.comparisons import compose
    fig,records,axes=compose(bundled[0]['summary_s4'],figure)
    try:
        for limit in axes:
            sub=[r for r in records if r['panel']==limit['panel'] and r['centre']==limit['centre']]
            for r in sub:
                for key in ['before_mean','after_mean','effect','lower','upper']:
                    if r[key] is not None: assert limit['x_min']<=r[key]<=limit['x_max']
        assert len(records)==(60 if figure=='5' else 120)
    finally: plt.close(fig)
