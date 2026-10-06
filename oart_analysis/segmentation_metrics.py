"""DSC and pooled bidirectional voxel-surface distances in physical millimetres.

The selected numerical convention is explicit: six-neighbour voxel-boundary
centres, equal weight per surface voxel, linear interpolation for the pooled
95th percentile. This is not a mesh-area-weighted surface implementation.
"""
import numpy as np
from scipy.ndimage import binary_erosion, generate_binary_structure, distance_transform_edt


def binary_mask(mask):
    arr=np.asarray(mask)
    if arr.ndim != 3 or not np.isfinite(arr).all() or not np.isin(arr, (0,1)).all():
        raise ValueError('Expected a finite binary 3-D mask. Select label IDs or threshold probabilities explicitly before evaluation.')
    return arr.astype(bool)


def union_masks(masks):
    """Union bilateral components BEFORE metric calculation."""
    masks=[binary_mask(m) for m in masks]
    if not masks or any(m.shape != masks[0].shape for m in masks):
        raise ValueError('Union requires at least one mask and identical shapes')
    return np.logical_or.reduce(masks)


def segmentation_metrics(reference, prediction, spacing_mm):
    ref, pred=binary_mask(reference), binary_mask(prediction)
    spacing=np.asarray(spacing_mm,dtype=float)
    if ref.shape != pred.shape:
        raise ValueError('Masks must occupy exactly the same voxel grid')
    if spacing.shape != (3,) or not np.isfinite(spacing).all() or (spacing<=0).any():
        raise ValueError('Provide three positive spacings in ARRAY AXIS ORDER, in mm')
    if not ref.any() or not pred.any():
        raise ValueError('Empty mask: distance metrics are undefined. Resolve the case explicitly; no silent filling or exclusion.')
    footprint=generate_binary_structure(3,1)
    ref_surface=ref & ~binary_erosion(ref, structure=footprint, border_value=0)
    pred_surface=pred & ~binary_erosion(pred, structure=footprint, border_value=0)
    p_to_r=distance_transform_edt(~ref_surface,sampling=spacing)[pred_surface]
    r_to_p=distance_transform_edt(~pred_surface,sampling=spacing)[ref_surface]
    distances=np.concatenate((p_to_r,r_to_p))
    voxel_volume=float(np.prod(spacing))
    return {
        'DSC': float(2*np.count_nonzero(ref & pred)/(np.count_nonzero(ref)+np.count_nonzero(pred))),
        'HD95_mm': float(np.quantile(distances,.95,method='linear')),
        'ASD_mm': float(np.mean(distances)),
        'reference_volume_cm3': float(np.count_nonzero(ref)*voxel_volume/1000),
        'prediction_volume_cm3': float(np.count_nonzero(pred)*voxel_volume/1000),
        'reference_surface_points': int(ref_surface.sum()),
        'prediction_surface_points': int(pred_surface.sum()),
    }

