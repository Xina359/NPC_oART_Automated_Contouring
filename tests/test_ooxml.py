"""Minimal self-contained OOXML reader fixtures; no clinical workbook is embedded."""
from zipfile import ZipFile
from pathlib import Path
import pytest
from oart_analysis.io import read_workbook_cells,read_source,_parse_xml
from oart_analysis.cli import main

S='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'

def workbook(tmp_path,cells,shared='',relationship=None):
    p=tmp_path/'fixture.xlsx'
    with ZipFile(p,'w') as z:
        z.writestr('xl/workbook.xml',f'<workbook xmlns="{S}" xmlns:r="{R}"><sheets><sheet name="Data" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships>'+ (relationship or '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/>')+'</Relationships>')
        z.writestr('xl/worksheets/sheet1.xml',f'<worksheet xmlns="{S}"><sheetData><row r="1">{cells}</row></sheetData></worksheet>')
        if shared:z.writestr('xl/sharedStrings.xml',f'<sst xmlns="{S}">{shared}</sst>')
    return p


def test_reader_inline_shared_numeric_boolean(tmp_path):
    p=workbook(tmp_path,'<c r="A1" t="inlineStr"><is><t>label</t></is></c><c r="B1" t="s"><v>0</v></c><c r="C1"><v>0.9401</v></c><c r="D1" t="b"><v>1</v></c>', '<si><r><t>Shared</t></r><r><t> value</t></r></si>')
    data,formulas=read_workbook_cells(p)
    assert data=={'Data':{'A1':'label','B1':'Shared value','C1':.9401,'D1':True}}
    assert formulas==[]


def test_reader_uses_cache_without_recalculating(tmp_path):
    p=workbook(tmp_path,'<c r="A1"><f>1+1</f><v>7</v></c>')
    data,formulas=read_workbook_cells(p)
    assert data['Data']['A1']==7 and formulas==['Data!A1']


def test_reader_rejects_formula_missing_cache(tmp_path):
    with pytest.raises(ValueError,match='no cached'):
        read_workbook_cells(workbook(tmp_path,'<c r="A1"><f>1+1</f></c>'))


def test_reader_rejects_duplicate_cells(tmp_path):
    with pytest.raises(ValueError,match='Duplicate cell'):
        read_workbook_cells(workbook(tmp_path,'<c r="A1"><v>1</v></c><c r="A1"><v>2</v></c>'))


def test_reader_rejects_external_target(tmp_path):
    p=workbook(tmp_path,'',relationship='<Relationship Id="rId1" Target="https://example.invalid/sheet.xml" TargetMode="External"/>')
    with pytest.raises(ValueError,match='External'):read_workbook_cells(p)


def test_reader_rejects_out_of_archive_target(tmp_path):
    p=workbook(tmp_path,'',relationship='<Relationship Id="rId1" Target="../../../outside.xml"/>')
    with pytest.raises(ValueError,match='Unsafe'):read_workbook_cells(p)


@pytest.mark.parametrize('xml',[b'<!DOCTYPE workbook><workbook/>',b'<!ENTITY a "text"><workbook/>'])
def test_reader_rejects_entity_declarations(xml):
    with pytest.raises(ValueError):_parse_xml(xml)


def test_missing_required_sheets_are_reported(tmp_path):
    with pytest.raises(ValueError,match='Missing worksheets'):read_source(workbook(tmp_path,'<c r="A1"><v>1</v></c>'))


def test_bad_zip_cli_fails_without_fallback(tmp_path,capsys):
    p=tmp_path/'bad.xlsx';p.write_text('not zip')
    assert main(['all','--source-data',str(p),'--output',str(tmp_path/'new')])==1
    assert 'ERROR:' in capsys.readouterr().err
    assert not (tmp_path/'new').exists()
