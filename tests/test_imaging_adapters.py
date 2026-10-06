"""Geometry validation and optional synthetic image I/O; never uses clinical images."""
from copy import deepcopy
from types import SimpleNamespace
import numpy as np
import pytest
from oart_analysis.imaging import require_same_grid,_validate_dicom_series,labelmap_pair,evaluate_config,_ascii_temporary_root

class Grid:
    def __init__(self):
        self.size=(7,8,9);self.spacing=(.95,.95,3.0);self.origin=(0.,0.,0.);self.direction=(1.,0.,0.,0.,1.,0.,0.,0.,1.)
    def GetDimension(self):return 3
    def GetNumberOfComponentsPerPixel(self):return 1
    def GetSize(self):return self.size
    def GetSpacing(self):return self.spacing
    def GetOrigin(self):return self.origin
    def GetDirection(self):return self.direction

def test_grid_geometry_accepts_equal():
    require_same_grid(Grid(),Grid())

@pytest.mark.parametrize('attribute,value',[('size',(7,8,10)),('spacing',(1,1,3)),('origin',(0,0,1)),
('direction',(-1,0,0,0,1,0,0,0,1)),('direction',(1,.1,0,0,1,0,0,0,1)),('spacing',(0,1,1)),('origin',(float('nan'),0,0))])
def test_geometry_mismatch_rejected(attribute,value):
    a,b=Grid(),Grid();setattr(b,attribute,value)
    with pytest.raises(ValueError):require_same_grid(a,b)


def synthetic_series():
    return [SimpleNamespace(ImageOrientationPatient=[1,0,0,0,1,0],PixelSpacing=[.95,.95],
        ImagePositionPatient=[0,0,z],Modality='CT',SeriesInstanceUID='synthetic-series',FrameOfReferenceUID='synthetic-frame',
        Rows=10,Columns=12,SOPInstanceUID=f'synthetic-slice-{i}') for i,z in enumerate([0,3,6])]

def test_dicom_geometry_convention():
    assert _validate_dicom_series(synthetic_series())==(.95,.95,3.0)
    assert _validate_dicom_series(list(reversed(synthetic_series())))==(.95,.95,3.0)

@pytest.mark.parametrize('defect',['irregular','duplicate','sheared','different_frame','different_series','different_spacing','different_orientation','single'])
def test_dicom_geometry_rejects_inconsistent_series(defect):
    series=synthetic_series()
    if defect=='irregular':series[2].ImagePositionPatient=[0,0,8]
    elif defect=='duplicate':series[1].ImagePositionPatient=[0,0,0]
    elif defect=='sheared':series[1].ImagePositionPatient=[1,0,3]
    elif defect=='different_frame':series[1].FrameOfReferenceUID='other'
    elif defect=='different_series':series[1].SeriesInstanceUID='other'
    elif defect=='different_spacing':series[1].PixelSpacing=[1,1]
    elif defect=='different_orientation':series[1].ImageOrientationPatient=[-1,0,0,0,-1,0]
    elif defect=='single':series=series[:1]
    with pytest.raises(ValueError):_validate_dicom_series(series)

@pytest.mark.imaging
def test_optional_nifti_roundtrip(tmp_path):
    sitk=pytest.importorskip('SimpleITK',reason='Optional SimpleITK not installed; actual NIfTI I/O is not verified')
    a=np.zeros((6,8,10),np.uint8);a[2:4,2:4,2:4]=1;a[2:4,5:7,6:8]=2
    image=sitk.GetImageFromArray(a);image.SetSpacing((.95,.95,3))
    ref=tmp_path/'ref.nii.gz';pred=tmp_path/'pred.nii.gz'
    sitk.WriteImage(image,str(ref));sitk.WriteImage(image,str(pred))
    x,y,spacing=labelmap_pair(ref,pred,[1,2],[1,2])
    np.testing.assert_allclose(spacing,(3,.95,.95),rtol=0,atol=1e-6)
    assert x.sum()==16 and np.array_equal(x,y)
    with pytest.raises(ValueError,match='Absent'):labelmap_pair(ref,pred,[3],[1])


@pytest.mark.imaging
@pytest.mark.parametrize('suffix',['.nii','.nii.gz'])
def test_nifti_unicode_path_stages_bytes_and_cleans_only_private_directory(tmp_path,monkeypatch,suffix):
    import hashlib
    import shutil
    from pathlib import Path
    sitk=pytest.importorskip('SimpleITK')
    # Write with an ASCII path first: some Windows ITK builds cannot write to
    # Unicode paths either. Python alone copies the original to that path.
    assert str(tmp_path).isascii(), 'Run imaging tests with an ASCII pytest --basetemp'
    original=tmp_path/('original'+suffix)
    values=np.zeros((3,4,7),np.uint8);values[1,1:3,3:6]=1
    image=sitk.GetImageFromArray(values);image.SetSpacing((.75,2,3))
    sitk.WriteImage(image,str(original))
    unicode_dir=tmp_path/(chr(0x4E2D)+chr(0x6587));unicode_dir.mkdir()
    source=unicode_dir/('mask'+suffix);shutil.copyfile(original,source)
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    staging=tmp_path/'staging';staging.mkdir()
    sentinel=staging/'keep.txt';sentinel.write_text('keep',encoding='ascii')
    real_reader=sitk.ReadImage;seen=[]
    def reader(path):
        assert str(path).isascii()
        seen.append(Path(path))
        assert Path(path).read_bytes()==source.read_bytes()
        return real_reader(path)
    monkeypatch.setattr(sitk,'ReadImage',reader)
    x,y,spacing=labelmap_pair(source,source,[1],[1],ascii_temp_root=staging)
    np.testing.assert_array_equal(x,values==1);np.testing.assert_array_equal(x,y)
    np.testing.assert_allclose(spacing,(3,2,.75),atol=1e-6)
    assert len(seen)==2 and all(p.parent.parent==staging for p in seen)
    assert not any(p.exists() for p in seen)
    assert list(staging.iterdir())==[sentinel]
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before


@pytest.mark.imaging
def test_nifti_staging_cleanup_on_reader_failure(tmp_path,monkeypatch):
    sitk=pytest.importorskip('SimpleITK')
    from oart_analysis.imaging import _read_labelmap
    assert str(tmp_path).isascii(), 'Run imaging tests with an ASCII pytest --basetemp'
    source=tmp_path/(chr(0x4E2D)+'.nii');source.write_bytes(b'invalid synthetic image')
    staging=tmp_path/'staging';staging.mkdir()
    def fail(path):
        raise RuntimeError('synthetic read failure')
    monkeypatch.setattr(sitk,'ReadImage',fail)
    with pytest.raises(RuntimeError,match='synthetic read failure'):
        _read_labelmap(source,sitk,staging)
    assert not list(staging.iterdir()) and source.read_bytes()==b'invalid synthetic image'


def test_ascii_staging_root_validation(tmp_path):
    assert _ascii_temporary_root(tmp_path)==str(tmp_path.absolute())
    unicode_dir=tmp_path/chr(0x4E2D);unicode_dir.mkdir()
    with pytest.raises(ValueError,match='ASCII'):_ascii_temporary_root(unicode_dir)
    with pytest.raises(ValueError,match='existing'):_ascii_temporary_root(tmp_path/'missing')


@pytest.mark.imaging
def test_optional_author_rtstruct_integration(tmp_path):
    pytest.importorskip('pydicom',reason='Optional pydicom not installed; RTSTRUCT I/O is not verified')
    import os
    config=os.getenv('NPC_OART_RTSTRUCT_CONFIG')
    if not config:
        pytest.skip('Set NPC_OART_RTSTRUCT_CONFIG to an approved local RTSTRUCT config; no clinical fixture is bundled')
    assert evaluate_config(config,tmp_path/'local-rtstruct-check')>0
