"""Analytic geometry oracles; contours are authored directly, never via a rasterizer.

Index-space rectangles have known voxel-centre membership. The fixture writes
their physical coordinates using an independent forward DICOM equation, then
the production adapter must recover those memberships and physical distances.
No original study imaging or external RTSTRUCT library is used.
"""
from copy import deepcopy
import numpy as np
import pytest

pydicom=pytest.importorskip('pydicom')
from pydicom.dataset import Dataset,FileDataset,FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import CTImageStorage,RTStructureSetStorage,ExplicitVRLittleEndian,generate_uid
from oart_analysis.imaging import rtstruct_pair
from oart_analysis.rtstruct_raster import rasterize_rtstruct,load_ct_series
from oart_analysis.segmentation_metrics import segmentation_metrics

pytestmark=pytest.mark.imaging


def image_reference(image):
    item=Dataset();item.ReferencedSOPClassUID=image.SOPClassUID
    item.ReferencedSOPInstanceUID=image.SOPInstanceUID
    return item


def file_dataset(path,sop_class):
    meta=FileMetaDataset();meta.MediaStorageSOPClassUID=sop_class
    meta.MediaStorageSOPInstanceUID=generate_uid();meta.TransferSyntaxUID=ExplicitVRLittleEndian
    meta.ImplementationClassUID=generate_uid()
    ds=FileDataset(str(path),{},file_meta=meta,preamble=b'\0'*128)
    ds.SOPClassUID=sop_class;ds.SOPInstanceUID=meta.MediaStorageSOPInstanceUID
    return ds


def rectangle(r0,r1,c0,c1):
    # Vertices are (column, row); closed boundary is implicitly the last edge.
    return [(c0,r0),(c1,r0),(c1,r1),(c0,r1)]


def fixture(tmp_path,shape=(12,20),spacing=(2.,.75,2.5),orientation=(1.,0.,0.,0.,1.,0.)):
    """Three classic CT files with filenames deliberately opposite slice order."""
    directory=tmp_path/'ct';directory.mkdir()
    series_uid,frame_uid,study_uid=generate_uid(),generate_uid(),generate_uid()
    first_axis=np.array(orientation[:3]);second_axis=np.array(orientation[3:])
    normal=np.cross(first_axis,second_axis);base=np.array((10.,20.,30.))
    images=[]
    for index in range(3):
        path=directory/f'{2-index}.dcm';ds=file_dataset(path,CTImageStorage)
        ds.Modality='CT';ds.SeriesInstanceUID=series_uid;ds.StudyInstanceUID=study_uid
        ds.FrameOfReferenceUID=frame_uid;ds.Rows,ds.Columns=shape
        ds.ImageOrientationPatient=list(orientation)
        ds.ImagePositionPatient=list(base+normal*index*spacing[2]);ds.PixelSpacing=list(spacing[:2])
        ds.SliceThickness=spacing[2];ds.InstanceNumber=index+1
        ds.SamplesPerPixel=1;ds.PhotometricInterpretation='MONOCHROME2'
        ds.BitsAllocated=16;ds.BitsStored=16;ds.HighBit=15;ds.PixelRepresentation=1
        ds.PixelData=np.zeros(shape,dtype='<i2').tobytes()
        ds.save_as(path,enforce_file_format=True);images.append(ds)
    rt=file_dataset(tmp_path/'rt.dcm',RTStructureSetStorage);rt.Modality='RTSTRUCT'
    frame=Dataset();frame.FrameOfReferenceUID=frame_uid
    study=Dataset();study.ReferencedSOPClassUID='1.2.840.10008.3.1.2.3.1'
    study.ReferencedSOPInstanceUID=study_uid
    refseries=Dataset();refseries.SeriesInstanceUID=series_uid
    refseries.ContourImageSequence=Sequence([image_reference(ds) for ds in images])
    study.RTReferencedSeriesSequence=Sequence([refseries])
    frame.RTReferencedStudySequence=Sequence([study]);rt.ReferencedFrameOfReferenceSequence=Sequence([frame])
    rt.StructureSetROISequence=Sequence();rt.ROIContourSequence=Sequence()

    def add_roi(name,polygons,kind='CLOSED_PLANAR',slice_index=1):
        number=len(rt.StructureSetROISequence)+1
        definition=Dataset();definition.ROINumber=number;definition.ROIName=name
        definition.ReferencedFrameOfReferenceUID=frame_uid
        rt.StructureSetROISequence.append(definition)
        roi=Dataset();roi.ReferencedROINumber=number;roi.ContourSequence=Sequence()
        for vertices in polygons:
            contour=Dataset();contour.ContourGeometricType=kind
            contour.NumberOfContourPoints=len(vertices)
            # Forward equation follows DICOM. No production inverse or mask
            # helper participates in construction of physical contour points.
            origin=np.asarray(images[slice_index].ImagePositionPatient)
            points=[origin+column*spacing[1]*first_axis+row*spacing[0]*second_axis
                    for column,row in vertices]
            contour.ContourData=np.asarray(points).ravel().tolist()
            contour.ContourImageSequence=Sequence([image_reference(images[slice_index])])
            roi.ContourSequence.append(contour)
        rt.ROIContourSequence.append(roi)
        return roi
    return directory,images,rt,add_roi


@pytest.mark.parametrize('shape',[(20,20),(12,20)])
@pytest.mark.parametrize('spacing',[(1.,1.,2.5),(2.,.75,2.5)])
@pytest.mark.parametrize('bounds',[(3,6,3,7),(3,6,10,17),(3,6,15,18),(0,2,0,2),(9,11,17,19)])
def test_rectangles_are_not_transposed_scaled_or_clipped(tmp_path,shape,spacing,bounds):
    directory,images,rt,add_roi=fixture(tmp_path,shape,spacing)
    add_roi('Target',[rectangle(*bounds)])
    path=tmp_path/'structure.dcm';rt.save_as(path,enforce_file_format=True)
    ref,pred,actual_spacing=rtstruct_pair(directory,path,path,['Target'],['Target'])
    expected=np.zeros((*shape,3),bool);r0,r1,c0,c1=bounds
    expected[r0:r1+1,c0:c1+1,1]=True
    assert ref.shape==(*shape,3) and actual_spacing==spacing
    np.testing.assert_array_equal(ref,expected);np.testing.assert_array_equal(pred,expected)
    assert segmentation_metrics(ref,pred,actual_spacing)['reference_volume_cm3']==pytest.approx(
        (r1-r0+1)*(c1-c0+1)*np.prod(spacing)/1000)


def test_two_by_two_grid_includes_all_four_voxel_centres(tmp_path):
    _,images,rt,add_roi=fixture(tmp_path,shape=(2,2))
    add_roi('Tiny',[rectangle(0,1,0,1)])
    expected=np.zeros((2,2,3),bool);expected[:,:,1]=True
    np.testing.assert_array_equal(rasterize_rtstruct(rt,images,['Tiny']),expected)


@pytest.mark.parametrize('orientation',[(0.,1.,0.,-1.,0.,0.),(-1.,0.,0.,0.,1.,0.),
    (1.,0.,0.,0.,.6,.8),(.6,.8,0.,-.8,.6,0.)])
def test_rotated_oblique_and_reversed_patient_directions(tmp_path,orientation):
    _,images,rt,add_roi=fixture(tmp_path,orientation=orientation)
    add_roi('Target',[rectangle(3,6,15,18)])
    expected=np.zeros((12,20,3),bool);expected[3:7,15:19,1]=True
    np.testing.assert_array_equal(rasterize_rtstruct(rt,images,['Target']),expected)


@pytest.mark.parametrize('row_shift,column_shift,expected_distance',[(1,0,2.),(0,1,.75)])
def test_physical_distances_use_array_axis_spacing(tmp_path,row_shift,column_shift,expected_distance):
    _,images,rt,add_roi=fixture(tmp_path)
    add_roi('Reference',[rectangle(3.75,4.25,4.75,5.25)])
    add_roi('Prediction',[rectangle(3.75+row_shift,4.25+row_shift,4.75+column_shift,5.25+column_shift)])
    ref=rasterize_rtstruct(rt,images,['Reference']);pred=rasterize_rtstruct(rt,images,['Prediction'])
    assert ref.sum()==pred.sum()==1
    result=segmentation_metrics(ref,pred,(2.,.75,2.5))
    assert result['DSC']==0 and result['HD95_mm']==pytest.approx(expected_distance)
    assert result['ASD_mm']==pytest.approx(expected_distance)


def test_disjoint_islands_and_bilateral_union(tmp_path):
    _,images,rt,add_roi=fixture(tmp_path)
    add_roi('Left',[rectangle(2,3,2,3),rectangle(6,7,2,3)])
    add_roi('Right',[rectangle(2,3,15,16)])
    expected=np.zeros((12,20,3),bool)
    expected[2:4,2:4,1]=True;expected[6:8,2:4,1]=True;expected[2:4,15:17,1]=True
    np.testing.assert_array_equal(rasterize_rtstruct(rt,images,['Left','Right']),expected)


@pytest.mark.parametrize('reverse_winding',[False,True])
def test_explicit_xor_hole_preserves_hole_independent_of_winding(tmp_path,reverse_winding):
    _,images,rt,add_roi=fixture(tmp_path)
    inner=rectangle(4,6,5,7)
    add_roi('Ring',[rectangle(2,8,3,9),inner[::-1] if reverse_winding else inner],kind='CLOSEDPLANAR_XOR')
    expected=np.zeros((12,20,3),bool);expected[2:9,3:10,1]=True;expected[4:7,5:8,1]=False
    np.testing.assert_array_equal(rasterize_rtstruct(rt,images,['Ring']),expected)


def test_xor_overlapping_polygons_exclude_overlap(tmp_path):
    _,images,rt,add_roi=fixture(tmp_path)
    add_roi('Xor',[rectangle(2,5,2,5),rectangle(4,7,4,7)],kind='CLOSEDPLANAR_XOR')
    expected=np.zeros((12,20,3),bool);expected[2:6,2:6,1]^=True;expected[4:8,4:8,1]^=True
    np.testing.assert_array_equal(rasterize_rtstruct(rt,images,['Xor']),expected)


@pytest.mark.parametrize('second',[(3,4,3,4),(4,7,4,7),(5,7,5,7)])
def test_ambiguous_nested_overlapping_or_touching_closed_planar_rejected(tmp_path,second):
    _,images,rt,add_roi=fixture(tmp_path)
    add_roi('Ambiguous',[rectangle(2,5,2,5),rectangle(*second)])
    with pytest.raises(ValueError,match='ambiguous'):
        rasterize_rtstruct(rt,images,['Ambiguous'])


@pytest.mark.parametrize('vertices',[
    [(2,2),(6,6),(2,6),(6,2)],
    [(2,2),(8,2),(8,8),(2,8),(2,2),(4,4),(4,6),(6,6),(6,4),(4,4),(2,2)],
    [(2,2),(4,2),(3,2),(4,4),(2,4)],
    [(2,2),(2,2),(4,4),(2,4)],
    [(2,2),(3,3),(4,4)]])
def test_self_intersections_keyholes_backtracking_and_degeneracy_rejected(tmp_path,vertices):
    _,images,rt,add_roi=fixture(tmp_path);add_roi('Bad',[vertices])
    with pytest.raises(ValueError):rasterize_rtstruct(rt,images,['Bad'])


def test_optional_image_reference_uses_exact_existing_plane(tmp_path):
    _,images,rt,add_roi=fixture(tmp_path);roi=add_roi('Target',[rectangle(2,3,2,3)])
    del roi.ContourSequence[0].ContourImageSequence
    expected=np.zeros((12,20,3),bool);expected[2:4,2:4,1]=True
    np.testing.assert_array_equal(rasterize_rtstruct(rt,images,['Target']),expected)
    coords=np.asarray(roi.ContourSequence[0].ContourData).reshape(-1,3);coords[:,2]+=.5
    roi.ContourSequence[0].ContourData=coords.ravel().tolist()
    with pytest.raises(ValueError,match='exactly one CT slice'):
        rasterize_rtstruct(rt,images,['Target'])


@pytest.mark.parametrize('defect,pattern',[
    ('global_frame','frame mismatch'),('roi_frame','frame mismatch'),('series','different CT series'),
    ('missing_sop','absent from the CT grid'),('wrong_sop_class','SOP class'),('wrong_slice','referenced CT slice'),
    ('nonplanar','Nonplanar'),('multiframe_ref','Multiframe'),('point_count','point count'),
    ('nonfinite','coordinates'),('open','Only uniform'),('mixed_xor','Only uniform'),
    ('slab','Slab'),('source_planes','Source pixel planes'),('outside','outside'),
    ('duplicate_roi','duplicate ROI'),('duplicate_contour_roi','duplicate contour ROI'),
    ('empty','Empty RTSTRUCT'),('subvoxel_empty','Empty RTSTRUCT')])
def test_invalid_rtstruct_is_rejected_without_silent_repair(tmp_path,defect,pattern):
    _,images,rt,add_roi=fixture(tmp_path);roi=add_roi('Target',[rectangle(2,3,2,3)])
    contour=roi.ContourSequence[0]
    if defect=='global_frame':rt.ReferencedFrameOfReferenceSequence[0].FrameOfReferenceUID=generate_uid()
    elif defect=='roi_frame':rt.StructureSetROISequence[0].ReferencedFrameOfReferenceUID=generate_uid()
    elif defect=='series':rt.ReferencedFrameOfReferenceSequence[0].RTReferencedStudySequence[0].RTReferencedSeriesSequence[0].SeriesInstanceUID=generate_uid()
    elif defect=='missing_sop':contour.ContourImageSequence[0].ReferencedSOPInstanceUID=generate_uid()
    elif defect=='wrong_sop_class':contour.ContourImageSequence[0].ReferencedSOPClassUID=RTStructureSetStorage
    elif defect=='wrong_slice':contour.ContourImageSequence[0]=image_reference(images[2])
    elif defect=='nonplanar':contour.ContourData[2]+=.1
    elif defect=='multiframe_ref':contour.ContourImageSequence[0].ReferencedFrameNumber=1
    elif defect=='point_count':contour.NumberOfContourPoints=3
    elif defect=='nonfinite':contour.ContourData[0]=float('nan')
    elif defect=='open':contour.ContourGeometricType='OPEN_PLANAR'
    elif defect=='mixed_xor':
        other=deepcopy(contour);other.ContourGeometricType='CLOSEDPLANAR_XOR';roi.ContourSequence.append(other)
    elif defect=='slab':contour.ContourSlabThickness=1
    elif defect=='source_planes':roi.SourcePixelPlanesCharacteristicsSequence=Sequence([Dataset()])
    elif defect=='outside':contour.ContourData[0]=-100
    elif defect=='duplicate_roi':rt.StructureSetROISequence.append(deepcopy(rt.StructureSetROISequence[0]))
    elif defect=='duplicate_contour_roi':rt.ROIContourSequence.append(deepcopy(roi))
    elif defect=='empty':roi.ContourSequence=Sequence()
    elif defect=='subvoxel_empty':
        rt.ROIContourSequence=Sequence();rt.StructureSetROISequence=Sequence()
        add_roi('Target',[rectangle(2.1,2.2,2.1,2.2)])
    with pytest.raises(ValueError,match=pattern):rasterize_rtstruct(rt,images,['Target'])


def test_empty_bilateral_component_and_missing_roi_are_rejected(tmp_path):
    _,images,rt,add_roi=fixture(tmp_path);add_roi('Left',[rectangle(2,3,2,3)]);add_roi('Right',[])
    with pytest.raises(ValueError,match='Empty RTSTRUCT'):rasterize_rtstruct(rt,images,['Left','Right'])
    with pytest.raises(ValueError,match='ROI absent'):rasterize_rtstruct(rt,images,['Absent'])


@pytest.mark.parametrize('selection',['AB',b'AB'])
def test_roi_selection_must_be_an_explicit_sequence(tmp_path,selection):
    _,images,rt,add_roi=fixture(tmp_path)
    add_roi('A',[rectangle(2,3,2,3)]);add_roi('B',[rectangle(2,3,5,6)])
    add_roi('AB',[rectangle(7,8,10,11)])
    assert rasterize_rtstruct(rt,images,['AB']).sum()==4
    with pytest.raises(ValueError,match='ROI names'):rasterize_rtstruct(rt,images,selection)


@pytest.mark.parametrize('field',['SeriesInstanceUID','FrameOfReferenceUID','SOPInstanceUID'])
@pytest.mark.parametrize('missing',[None,''])
def test_missing_ct_uids_are_not_coerced_to_strings(tmp_path,field,missing):
    _,images,rt,add_roi=fixture(tmp_path);add_roi('Target',[rectangle(2,3,2,3)])
    for image in images:setattr(image,field,missing)
    if field=='FrameOfReferenceUID':
        rt.ReferencedFrameOfReferenceSequence[0].FrameOfReferenceUID=missing
        rt.StructureSetROISequence[0].ReferencedFrameOfReferenceUID=missing
    with pytest.raises(ValueError,match='Missing or empty'):rasterize_rtstruct(rt,images,['Target'])


@pytest.mark.parametrize('defect,pattern',[
    ('duplicate_sop','duplicate CT SOP'),('shape','grid shape'),('enhanced','classic single-frame'),
    ('frame','one frame'),('shift','Tilted/sheared'),('irregular','irregular')])
def test_ct_files_validate_geometry_and_identity(tmp_path,defect,pattern):
    directory,images,_,_=fixture(tmp_path)
    image=images[1]
    if defect=='duplicate_sop':image.SOPInstanceUID=images[0].SOPInstanceUID
    elif defect=='shape':image.Columns=21
    elif defect=='enhanced':image.SOPClassUID='1.2.840.10008.5.1.4.1.1.2.1'
    elif defect=='frame':image.FrameOfReferenceUID=generate_uid()
    elif defect=='shift':image.ImagePositionPatient[0]+=.1
    elif defect=='irregular':image.ImagePositionPatient[2]+=.1
    image.save_as(directory/'1.dcm',enforce_file_format=True)
    with pytest.raises(ValueError,match=pattern):load_ct_series(directory)
