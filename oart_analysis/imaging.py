"""Local image adapters for matched labelmaps and classic CT/RTSTRUCT inputs.

RTSTRUCTs use the native validated voxel-centre polygon rasterizer.
No registration, resampling, segmentation inference, or clinical QA is performed.
Optional dependencies are imported only when an image format requires them.
"""
from pathlib import Path
import json
import os
import shutil
import tempfile
import numpy as np
from .segmentation_metrics import segmentation_metrics
from .io import write_csv,write_json
from .rtstruct_raster import load_ct_series,rasterize_rtstruct,validate_ct_series


def require_same_grid(reference,prediction):
    for image in (reference,prediction):
        if image.GetDimension()!=3 or image.GetNumberOfComponentsPerPixel()!=1:
            raise ValueError('Only scalar three-dimensional labelmaps are supported')
        spacing=np.asarray(image.GetSpacing(),float)
        if not np.isfinite(spacing).all() or (spacing<=0).any(): raise ValueError('Invalid voxel spacing')
        direction=np.array(image.GetDirection(),float).reshape(3,3)
        if not np.isfinite(direction).all() or not np.allclose(direction.T@direction,np.eye(3),rtol=0,atol=1e-6):
            raise ValueError('Nonorthogonal image axes are unsupported')
    if reference.GetSize()!=prediction.GetSize():raise ValueError('Mask dimensions differ')
    for attr in ('GetSpacing','GetOrigin','GetDirection'):
        a=np.array(getattr(reference,attr)(),float);b=np.array(getattr(prediction,attr)(),float)
        if not np.isfinite(a).all() or not np.isfinite(b).all() or not np.allclose(a,b,rtol=0,atol=1e-6):
            raise ValueError(f'Mask geometry differs: {attr}; no automatic registration or resampling')


def _ascii_temporary_root(ascii_temp_root=None):
    """Find an existing ASCII temporary parent without changing system TMP."""
    root = str(Path(ascii_temp_root if ascii_temp_root is not None else tempfile.gettempdir()).absolute())
    if not Path(root).is_dir():
        raise ValueError('ascii_temp_root must be an existing directory')
    if root.isascii():
        return root
    # An existing Windows short-path alias may make a Unicode user TEMP usable.
    # Do not resolve this alias back to the long path before calling SimpleITK.
    if ascii_temp_root is None and os.name == 'nt':
        import ctypes
        get_short_path = ctypes.windll.kernel32.GetShortPathNameW
        get_short_path.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint)
        get_short_path.restype = ctypes.c_uint
        size = get_short_path(root, None, 0)
        if size:
            buffer = ctypes.create_unicode_buffer(size)
            written = get_short_path(root, buffer, size)
            if 0 < written < size and buffer.value.isascii() and Path(buffer.value).is_dir():
                return buffer.value
    raise ValueError('NIfTI staging needs an existing ASCII directory; set ascii_temp_root explicitly')


def _read_labelmap(path, sitk, ascii_temp_root=None):
    """Read Unicode-path NIfTI through a private byte-for-byte ASCII copy."""
    path = Path(path).absolute()
    if str(path).isascii():
        return sitk.ReadImage(str(path))
    lower = path.name.lower()
    suffix = '.nii.gz' if lower.endswith('.nii.gz') else '.nii' if lower.endswith('.nii') else None
    if suffix is None:
        raise ValueError('Unicode-path staging supports single-file .nii and .nii.gz labelmaps only')
    root = _ascii_temporary_root(ascii_temp_root)
    with tempfile.TemporaryDirectory(prefix='npc_oart_nifti_', dir=root) as private:
        staged = Path(private) / ('labelmap' + suffix)
        shutil.copyfile(path, staged)
        return sitk.ReadImage(str(staged))


def labelmap_pair(reference_path,prediction_path,reference_labels,prediction_labels,*,ascii_temp_root=None):
    try: import SimpleITK as sitk
    except ImportError as exc: raise ImportError('Labelmaps require the optional [imaging] dependencies') from exc
    reference=_read_labelmap(reference_path,sitk,ascii_temp_root)
    prediction=_read_labelmap(prediction_path,sitk,ascii_temp_root)
    require_same_grid(reference,prediction);arrays=[]
    for image,labels in ((reference,reference_labels),(prediction,prediction_labels)):
        if not labels or len(set(labels))!=len(labels) or any(not isinstance(i,int) or isinstance(i,bool) or i<=0 for i in labels):
            raise ValueError('Select unique positive label IDs; list both sides for bilateral structures')
        array=sitk.GetArrayFromImage(image)
        if not np.isfinite(array).all() or not np.equal(array,np.round(array)).all() or (array<0).any():
            raise ValueError('Integer labelmap required; threshold probabilities explicitly')
        missing=set(labels)-set(np.unique(array))
        if missing: raise ValueError(f'Absent label IDs: {sorted(missing)}')
        arrays.append(np.isin(array,labels))
    return arrays[0],arrays[1],tuple(reversed(reference.GetSpacing()))


def _validate_dicom_series(series):
    return validate_ct_series(series)


def rtstruct_pair(ct_directory,reference_path,prediction_path,reference_rois,prediction_rois):
    try:
        import pydicom
    except ImportError as exc: raise ImportError('RTSTRUCTs require the optional [imaging] dependencies') from exc
    series=load_ct_series(ct_directory)
    reference=pydicom.dcmread(str(reference_path),stop_before_pixels=True)
    prediction=pydicom.dcmread(str(prediction_path),stop_before_pixels=True)
    # Both masks use precisely the same sorted CT stack and physical grid.
    return (rasterize_rtstruct(reference,series,reference_rois),
            rasterize_rtstruct(prediction,series,prediction_rois),validate_ct_series(series))


def evaluate_config(config_path,output,*,ascii_temp_root=None):
    config_path=Path(config_path);config=json.loads(config_path.read_text(encoding='utf-8'));cases=config.get('cases',[])
    if not cases:raise ValueError('No imaging cases configured')
    def local_path(value):
        if not value or 'REPLACE_' in str(value):raise ValueError('Replace local imaging paths in the example configuration')
        p=Path(value);p=p if p.is_absolute() else config_path.parent/p
        if not p.exists():raise FileNotFoundError(p)
        return p
    if ascii_temp_root is None and config.get('ascii_temp_root') is not None:
        ascii_temp_root=local_path(config['ascii_temp_root'])
    results=[];keys=set()
    for case in cases:
        identifier=case.get('study_id')
        if not isinstance(identifier,str) or not identifier.strip():raise ValueError('Provide a non-identifying study_id')
        if not case.get('rois'):raise ValueError('No ROI configured for case')
        for roi in case['rois']:
            key=(identifier,case.get('model_state',''),roi['name'])
            if key in keys:raise ValueError(f'Duplicate imaging evaluation key: {key}')
            keys.add(key)
            if case['format']=='labelmap':
                ref,pred,spacing=labelmap_pair(local_path(case['reference_path']),local_path(case['prediction_path']),roi['reference_labels'],roi['prediction_labels'],ascii_temp_root=ascii_temp_root)
            elif case['format']=='rtstruct':
                ref,pred,spacing=rtstruct_pair(local_path(case['ct_directory']),local_path(case['reference_path']),local_path(case['prediction_path']),roi['reference_rois'],roi['prediction_rois'])
            else:raise ValueError('format must be labelmap or rtstruct')
            results.append({'study_id':identifier,'model_state':case.get('model_state',''),'roi':roi['name'],**segmentation_metrics(ref,pred,spacing)})
    output=Path(output);write_csv(results,output/'segmentation_metrics.csv')
    write_json({'cases':len(cases),'evaluated_rois':len(results),'convention':'6-neighbour voxel-boundary centres; pooled bidirectional distances; linear HD95 percentile; point-count-weighted ASD',
        'rtstruct_rasterizer':'native numpy voxel-centre polygon rasterizer; unchanged classic CT grid; array axes row,column,slice',
        'rtstruct_polygon_convention':'inside or on boundary; disjoint simple CLOSED_PLANAR islands; simple CLOSEDPLANAR_XOR polygons combined by XOR; no interpolation between slices',
        'rtstruct_unsupported_geometry':'nested/touching/overlapping CLOSED_PLANAR, keyholes, self-intersections, slabs, offsets, attached contours, source pixel planes, multiframe CT, irregular/sheared grids, out-of-grid contours',
        'automatic_registration_or_resampling':False,'clinical_model_execution':False,'original_study_masks_verified':False},output/'metric_convention.json')
    return len(results)
