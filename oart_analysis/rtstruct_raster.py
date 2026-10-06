"""Conservative RTSTRUCT rasterization on one unchanged classic CT grid.

Coordinates follow DICOM PS3.3 C.7.6.2.1.1: the first IOP vector advances
columns with PixelSpacing[1]; the second advances rows with PixelSpacing[0].
Output axes and spacing are (row, column, slice). A voxel centre is included
when inside or on the boundary of a simple polygon. CLOSED_PLANAR islands
must be disjoint; nested/touching/intersecting contours and keyholes are
rejected. CLOSEDPLANAR_XOR explicitly combines simple polygons using XOR.
There is no interpolation between slices, registration or resampling.
"""
from pathlib import Path
import numpy as np

CT_STORAGE = '1.2.840.10008.5.1.4.1.1.2'
RTSTRUCT_STORAGE = '1.2.840.10008.5.1.4.1.1.481.3'
POLYGON_EPS = 1e-7  # voxel-index units, only for floating-point boundary noise


def _uid(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'Missing or empty {label}')
    return value


def _vector(value, size, label):
    try:
        result = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'Invalid {label}') from exc
    if result.shape != (size,) or not np.isfinite(result).all():
        raise ValueError(f'Invalid {label}')
    return result


def validate_ct_series(series):
    """Validate a sorted, regular CT stack; return row/column/slice spacing."""
    if len(series) < 2:
        raise ValueError('At least two regularly spaced CT slices are required')
    try:
        first = series[0]
        orientation = _vector(first.ImageOrientationPatient, 6, 'DICOM orientation')
        col_dir, row_dir = orientation[:3], orientation[3:]
        normal = np.cross(col_dir, row_dir)
        axes = np.stack((col_dir, row_dir, normal))
        if not np.allclose(axes @ axes.T, np.eye(3), rtol=0, atol=1e-6):
            raise ValueError('Invalid DICOM direction cosines')
        spacing = _vector(first.PixelSpacing, 2, 'PixelSpacing')
        if (spacing <= 0).any():
            raise ValueError('Invalid PixelSpacing')
        origin = _vector(first.ImagePositionPatient, 3, 'ImagePositionPatient')
        shape = (int(first.Rows), int(first.Columns))
        if min(shape) <= 0:
            raise ValueError('Invalid CT Rows/Columns')
        series_uid = _uid(first.SeriesInstanceUID, 'CT SeriesInstanceUID')
        frame_uid = _uid(first.FrameOfReferenceUID, 'CT FrameOfReferenceUID')
        positions, uids = [], set()
        for ds in series:
            if (ds.Modality != 'CT'
                    or _uid(ds.SeriesInstanceUID, 'CT SeriesInstanceUID') != series_uid
                    or _uid(ds.FrameOfReferenceUID, 'CT FrameOfReferenceUID') != frame_uid):
                raise ValueError('One CT series and one frame of reference are required')
            uid = _uid(ds.SOPInstanceUID, 'CT SOPInstanceUID')
            if uid in uids:
                raise ValueError('Missing or duplicate CT SOPInstanceUID')
            uids.add(uid)
            if int(getattr(ds, 'NumberOfFrames', 1)) != 1:
                raise ValueError('Multiframe CT is unsupported')
            if (int(ds.Rows), int(ds.Columns)) != shape:
                raise ValueError('Inconsistent CT grid shape')
            if not np.allclose(_vector(ds.PixelSpacing, 2, 'PixelSpacing'), spacing, rtol=0, atol=1e-6):
                raise ValueError('Inconsistent CT grid spacing')
            if not np.allclose(_vector(ds.ImageOrientationPatient, 6, 'DICOM orientation'), orientation, rtol=0, atol=1e-6):
                raise ValueError('Inconsistent orientations')
            displacement = _vector(ds.ImagePositionPatient, 3, 'ImagePositionPatient') - origin
            distance = float(displacement @ normal)
            if not np.allclose(displacement - distance * normal, 0, rtol=0, atol=1e-3):
                raise ValueError('Tilted/sheared grid requires explicit preprocessing')
            positions.append(distance)
        steps = np.diff(positions)
        if (not (np.all(steps > 0) or np.all(steps < 0))
                or not np.allclose(steps, steps[0], rtol=1e-4, atol=1e-3)):
            raise ValueError('Duplicate, irregular or unsorted CT positions')
        return float(spacing[0]), float(spacing[1]), float(abs(steps[0]))
    except (AttributeError, TypeError, OverflowError) as exc:
        raise ValueError('Missing or invalid CT geometry metadata') from exc


def load_ct_series(directory):
    """Load metadata only, ignoring unrelated non-DICOM files and non-CT objects."""
    import pydicom
    from pydicom.errors import InvalidDicomError
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError('ct_directory must be a directory containing one CT series')
    series = []
    for path in sorted(p for p in directory.rglob('*') if p.is_file()):
        try:
            ds = pydicom.dcmread(str(path), stop_before_pixels=True)
        except InvalidDicomError as exc:
            if path.suffix.lower() in ('.dcm', '.dicom'):
                raise ValueError(f'Invalid DICOM file: {path.name}') from exc
            continue
        if getattr(ds, 'Modality', None) != 'CT':
            continue
        if str(getattr(ds, 'SOPClassUID', '')) != CT_STORAGE:
            raise ValueError('Only classic single-frame CT Image Storage is supported')
        series.append(ds)
    if len(series) < 2:
        raise ValueError('At least two regularly spaced CT slices are required')
    try:
        orientation = _vector(series[0].ImageOrientationPatient, 6, 'DICOM orientation')
        normal = np.cross(orientation[:3], orientation[3:])
        series.sort(key=lambda ds: float(_vector(ds.ImagePositionPatient, 3, 'ImagePositionPatient') @ normal))
    except AttributeError as exc:
        raise ValueError('Missing CT orientation or position') from exc
    validate_ct_series(series)
    return series


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _segments_intersect(a, b, c, d):
    eps = POLYGON_EPS
    if (np.maximum(np.minimum(a, b), np.minimum(c, d))
            > np.minimum(np.maximum(a, b), np.maximum(c, d)) + eps).any():
        return False
    o1, o2 = _cross(b-a, c-a), _cross(b-a, d-a)
    o3, o4 = _cross(d-c, a-c), _cross(d-c, b-c)
    return ((min(o1, o2) <= eps and max(o1, o2) >= -eps)
            and (min(o3, o4) <= eps and max(o3, o4) >= -eps))


def _simple_polygon(points):
    # A redundant final copy of the first point is harmless; internal repeats
    # and backtracking paths (including keyhole encodings) are not supported.
    if len(points) > 3 and np.allclose(points[0], points[-1], rtol=0, atol=POLYGON_EPS):
        points = points[:-1]
    if len(points) < 3:
        raise ValueError('A closed contour needs at least three distinct vertices')
    end = np.roll(points, -1, axis=0)
    edges = end-points
    if (np.linalg.norm(edges, axis=1) <= POLYGON_EPS).any():
        raise ValueError('Duplicate contour vertices are unsupported')
    for i in range(len(points)):
        previous, following = edges[i-1], edges[i]
        if abs(_cross(previous, following)) <= POLYGON_EPS and previous @ following < 0:
            raise ValueError('Backtracking/keyhole contour is unsupported; use CLOSEDPLANAR_XOR')
        # Bounding boxes prune most comparisons without allocating N x N arrays.
        candidates = np.arange(i+2, len(points))
        if i == 0:
            candidates = candidates[candidates != len(points)-1]
        for j in candidates:
            if _segments_intersect(points[i], end[i], points[j], end[j]):
                raise ValueError('Self-intersecting/keyhole contour is unsupported')
    area = np.sum(points[:, 0]*end[:, 1] - end[:, 0]*points[:, 1]) / 2
    if abs(area) <= POLYGON_EPS:
        raise ValueError('Degenerate contour has no polygon area')
    return points


def _contains(poly, x, y):
    """Even-odd inclusion at supplied points, including polygon boundaries."""
    inside = np.zeros(np.broadcast_shapes(np.shape(x), np.shape(y)), dtype=bool)
    boundary = np.zeros_like(inside)
    for a, b in zip(poly, np.roll(poly, -1, axis=0)):
        dx, dy = b-a
        cross = dx*(y-a[1]) - dy*(x-a[0])
        boundary |= ((np.abs(cross) <= POLYGON_EPS*max(1.0, float(np.hypot(dx, dy))))
                     & (x >= min(a[0], b[0])-POLYGON_EPS) & (x <= max(a[0], b[0])+POLYGON_EPS)
                     & (y >= min(a[1], b[1])-POLYGON_EPS) & (y <= max(a[1], b[1])+POLYGON_EPS))
        if abs(dy) > POLYGON_EPS:
            crossing = ((a[1] > y) != (b[1] > y)) & (x < a[0] + (y-a[1])*dx/dy)
            inside ^= crossing
    return inside | boundary


def _overlap_or_nested(a, b):
    if (np.maximum(a.min(axis=0), b.min(axis=0))
            > np.minimum(a.max(axis=0), b.max(axis=0)) + POLYGON_EPS).any():
        return False
    for a0, a1 in zip(a, np.roll(a, -1, axis=0)):
        for b0, b1 in zip(b, np.roll(b, -1, axis=0)):
            if _segments_intersect(a0, a1, b0, b1):
                return True
    return bool(_contains(a, b[0, 0], b[0, 1]) or _contains(b, a[0, 0], a[0, 1]))


def _polygon_mask(poly, shape):
    rows, columns = shape
    if ((poly < -.5-POLYGON_EPS).any()
            or (poly[:, 0] > columns-.5+POLYGON_EPS).any()
            or (poly[:, 1] > rows-.5+POLYGON_EPS).any()):
        raise ValueError('Contour extends outside the CT field of view; clipping is not allowed')
    lower = np.maximum(np.ceil(poly.min(axis=0)-POLYGON_EPS).astype(int), 0)
    upper = np.minimum(np.floor(poly.max(axis=0)+POLYGON_EPS).astype(int), [columns-1, rows-1])
    result = np.zeros(shape, dtype=bool)
    if (upper < lower).any():
        return result
    x, y = np.meshgrid(np.arange(lower[0], upper[0]+1), np.arange(lower[1], upper[1]+1))
    result[lower[1]:upper[1]+1, lower[0]:upper[0]+1] = _contains(poly, x, y)
    return result


def _check_image_reference(ref, lookup):
    uid = _uid(getattr(ref, 'ReferencedSOPInstanceUID', None), 'ReferencedSOPInstanceUID')
    if uid not in lookup:
        raise ValueError('RTSTRUCT references a SOP instance absent from the CT grid')
    if str(getattr(ref, 'ReferencedSOPClassUID', '')) != CT_STORAGE:
        raise ValueError('RTSTRUCT referenced SOP class is not classic CT Image Storage')
    if hasattr(ref, 'ReferencedFrameNumber'):
        raise ValueError('Multiframe contour references are unsupported')
    return lookup[uid]


def rasterize_rtstruct(dataset, series, names):
    """Rasterize explicitly selected ROIs and union them on the supplied CT grid."""
    spacing = validate_ct_series(series)
    if (getattr(dataset, 'Modality', None) != 'RTSTRUCT'
            or str(getattr(dataset, 'SOPClassUID', '')) != RTSTRUCT_STORAGE):
        raise ValueError('Expected an RT Structure Set Storage object')
    if (not isinstance(names, (list, tuple)) or not names
            or any(not isinstance(n, str) or not n.strip() for n in names)
            or len(names) != len(set(names))):
        raise ValueError('Provide unique nonempty ROI names')
    frame = _uid(series[0].FrameOfReferenceUID, 'CT FrameOfReferenceUID')
    lookup = {_uid(ds.SOPInstanceUID, 'CT SOPInstanceUID'): i for i, ds in enumerate(series)}
    frame_refs = list(getattr(dataset, 'ReferencedFrameOfReferenceSequence', []))
    if (len(frame_refs) != 1
            or _uid(getattr(frame_refs[0], 'FrameOfReferenceUID', None), 'RTSTRUCT FrameOfReferenceUID') != frame):
        raise ValueError('RTSTRUCT/CT frame mismatch')
    for study in getattr(frame_refs[0], 'RTReferencedStudySequence', []):
        for refseries in getattr(study, 'RTReferencedSeriesSequence', []):
            if _uid(getattr(refseries, 'SeriesInstanceUID', None), 'Referenced SeriesInstanceUID') != series[0].SeriesInstanceUID:
                raise ValueError('RTSTRUCT references a different CT series')
            for ref in getattr(refseries, 'ContourImageSequence', []):
                _check_image_reference(ref, lookup)
    definitions, numbers = {}, set()
    for roi in getattr(dataset, 'StructureSetROISequence', []):
        name, number = getattr(roi, 'ROIName', None), getattr(roi, 'ROINumber', None)
        if not name or number is None or name in definitions or number in numbers:
            raise ValueError('Missing or ambiguous duplicate ROI name/number')
        definitions[name] = roi
        numbers.add(number)
    contour_sets = {}
    for item in getattr(dataset, 'ROIContourSequence', []):
        number = getattr(item, 'ReferencedROINumber', None)
        if number not in numbers or number in contour_sets:
            raise ValueError('Unknown or duplicate contour ROI number')
        contour_sets[number] = item
    origins = np.asarray([ds.ImagePositionPatient for ds in series], dtype=float)
    orientation = np.asarray(series[0].ImageOrientationPatient, dtype=float)
    col_dir, row_dir = orientation[:3], orientation[3:]
    normal = np.cross(col_dir, row_dir)
    plane_tolerance = min(1e-3, spacing[2]*1e-3)  # millimetres, much less than a slice
    shape = (int(series[0].Rows), int(series[0].Columns))
    result = np.zeros((*shape, len(series)), dtype=bool)
    for name in names:
        if name not in definitions:
            raise ValueError(f'ROI absent: {name}')
        definition = definitions[name]
        if _uid(getattr(definition, 'ReferencedFrameOfReferenceUID', None), 'ROI ReferencedFrameOfReferenceUID') != frame:
            raise ValueError(f'ROI/CT frame mismatch: {name}')
        item = contour_sets.get(definition.ROINumber)
        if item is None or not getattr(item, 'ContourSequence', None):
            raise ValueError(f'Empty RTSTRUCT component: {name}')
        if hasattr(item, 'SourcePixelPlanesCharacteristicsSequence'):
            raise ValueError('Source pixel planes require explicit preprocessing; only the CT grid is supported')
        contours = item.ContourSequence
        types = {getattr(c, 'ContourGeometricType', '') for c in contours}
        if types not in ({'CLOSED_PLANAR'}, {'CLOSEDPLANAR_XOR'}):
            raise ValueError('Only uniform CLOSED_PLANAR or CLOSEDPLANAR_XOR contours are supported per ROI')
        xor = types == {'CLOSEDPLANAR_XOR'}
        polygons = {}
        for contour in contours:
            if any(hasattr(contour, key) for key in ('ContourSlabThickness', 'ContourOffsetVector', 'AttachedContours')):
                raise ValueError('Slab/offset/attached contour semantics are unsupported')
            try:
                count = int(contour.NumberOfContourPoints)
                values = np.asarray(contour.ContourData, dtype=float)
            except (AttributeError, TypeError, ValueError) as exc:
                raise ValueError('Missing or invalid contour coordinates') from exc
            if count < 3 or values.shape != (3*count,) or not np.isfinite(values).all():
                raise ValueError('Contour point count or coordinates are invalid')
            points = values.reshape(-1, 3)
            image_refs = list(getattr(contour, 'ContourImageSequence', []))
            if image_refs:
                if len(image_refs) != 1:
                    raise ValueError('Each contour must reference exactly one CT slice')
                index = _check_image_reference(image_refs[0], lookup)
            else:
                # ContourImageSequence is optional in DICOM. Geometry must still
                # select an existing plane unambiguously; never round a slice.
                distance = np.abs((origins-points[0]) @ normal)
                matches = np.flatnonzero(distance <= plane_tolerance)
                if len(matches) != 1:
                    raise ValueError('Contour does not identify exactly one CT slice plane')
                index = int(matches[0])
            displacement = points-origins[index]
            if np.max(np.abs(displacement @ normal)) > plane_tolerance:
                raise ValueError('Nonplanar contour or contour does not lie on its referenced CT slice')
            polygon = np.column_stack((displacement @ col_dir / spacing[1], displacement @ row_dir / spacing[0]))
            polygon = _simple_polygon(polygon)
            polygons.setdefault(index, []).append(polygon)
        nonempty = False
        for index, plane_polys in polygons.items():
            if not xor:
                for i, a in enumerate(plane_polys):
                    if any(_overlap_or_nested(a, b) for b in plane_polys[i+1:]):
                        raise ValueError('Nested/touching/overlapping CLOSED_PLANAR contours are ambiguous; use CLOSEDPLANAR_XOR')
            plane = np.zeros(shape, dtype=bool)
            for poly in plane_polys:
                mask = _polygon_mask(poly, shape)
                if xor:
                    plane ^= mask
                else:
                    plane |= mask
            nonempty |= bool(plane.any())
            result[:, :, index] |= plane
        if not nonempty:
            raise ValueError(f'Empty RTSTRUCT component on the CT voxel-centre grid: {name}')
    return result
