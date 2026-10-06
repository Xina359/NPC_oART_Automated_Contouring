# Metrics from locally exported masks

Version 2.1.0 evaluates exported masks using an explicit numerical convention.
It does not execute the clinical contouring networks, register images, resample
misaligned grids or perform treatment-plan QA. Original study images are not
bundled, and metric tables alone cannot establish their original rasterization
or surface-sampling implementation.

## Installation and configuration

```bash
python -m pip install -c requirements-tested.txt -c requirements-imaging-tested.txt -e ".[imaging,test]"
python -m oart_analysis.cli metrics --config config/imaging.local.json --output outputs/local_masks
```

The imaging extra uses SimpleITK for labelmaps and pydicom for DICOM metadata and
RTSTRUCT input. RTSTRUCT rasterization is implemented in this package; rt-utils
is no longer required.

Before running metrics, copy `config/imaging.example.json` for labelmaps or
`config/imaging.rtstruct.example.json` for RTSTRUCTs to `config/imaging.local.json`.
Enter your local reference/prediction paths, non-identifying study IDs and exact
ROI labels or names. Relative paths resolve against the configuration directory.
Use `format: "labelmap"` or `format: "rtstruct"` for each case. Each case can have
multiple ROIs; the combination of study ID, model state and ROI name must be
unique. Multiple label IDs or ROI names define components to union before metric
calculation, for example the two sides of a bilateral organ.

The output directory must be empty. Results are written to
`segmentation_metrics.csv`, with the convention and interpretation recorded in
`metric_convention.json`. The CLI also records the code, Python and installed
dependency versions in `runtime_versions.json`. These outputs remain local;
no upload is performed.

## Labelmap inputs

Provide scalar 3D integer labelmaps on an identical physical grid. Dimensions,
spacing, origin and direction must agree, with finite positive spacing and
orthonormal direction axes. Requested label IDs must be unique positive integers
and present in the input. Labels must be nonnegative integers; probability maps
must be explicitly thresholded before evaluation. Missing labels, empty masks
and geometry mismatches are errors.

For ASCII paths, file formats accepted by SimpleITK can be read, subject to those
scalar/grid restrictions. For paths containing Unicode characters, including
Chinese characters, this adapter supports single-file `.nii` and `.nii.gz` inputs.
It makes a byte-for-byte copy in a private temporary directory with an ASCII path,
reads that copy with SimpleITK and removes the temporary directory afterward.
It does not rename or modify the original file. Detached/multifile formats and
other extensions on Unicode paths are rejected rather than incompletely staged.

An existing ASCII temporary parent is required for staging. The default is the
system temporary directory; on Windows an existing ASCII short-path alias can
be used if available. If neither is suitable, set a top-level `ascii_temp_root`
configuration value to an existing ASCII-named directory. For example,
`"ascii_temp_root": "C:/Temp"` is usable only if that directory exists. The
adapter does not change the system temporary-directory settings. The selected
location must be appropriate for temporary copies of your local imaging data.

SimpleITK arrays are ordered z,y,x, so the image's x,y,z spacing is reversed
before calling the metric kernel. No automatic resampling or interpolation is
performed.

## CT and RTSTRUCT inputs

Supply a directory containing one classic single-frame CT series and separate
reference/prediction RTSTRUCT files. The loader scans CT metadata, sorts slices
by physical position and uses that same stack for both masks. Unrelated non-CT
objects and ordinary non-DICOM files are ignored; malformed files with `.dcm` or
`.dicom` extensions raise an error. At least two regularly spaced CT slices are
required. The accepted grid can be non-square, have unequal row/column spacing
or have oblique orthonormal directions.

Checks require consistent Rows/Columns, orientation, PixelSpacing, series and
frame of reference; unique CT SOP instance identifiers; regular nonduplicate
slice positions; and no in-plane drift between slices. Multiple CT series,
multiframe/enhanced CT, irregular stacks and tilted/sheared grids are rejected.
The loader reads geometry rather than CT pixel values. DICOM SEG is not supported.

RTSTRUCTs must use the same frame of reference and, when present, matching series
and CT SOP references. Requested ROI names must be unique, unambiguous and present.
Each component must contain nonempty supported contours. A contour with an image
reference must identify exactly one CT slice; a contour without that optional
reference must geometrically identify exactly one existing slice plane. All
points must lie on that plane within a small numerical tolerance. Contours are
not rounded to a neighbouring slice, and no contours are interpolated between
slices.

The coordinate convention follows the supplied CT metadata:

- The first ImageOrientationPatient vector advances columns using
  `PixelSpacing[1]`; the second advances rows using `PixelSpacing[0]`.
- Masks have shape `(Rows, Columns, number of slices)` and spacing
  `(row spacing, column spacing, slice spacing)`.
- A voxel centre inside or on the boundary of a supported polygon is included.
  Contours outside the CT field of view are rejected rather than silently clipped.

## Supported contour topology

Within each selected ROI, all contours must use one supported geometric type:

| Type | Combination on a slice | Deliberate restrictions |
|---|---|---|
| `CLOSED_PLANAR` | Union of disjoint simple polygons | Nested, touching, overlapping or intersecting polygons are rejected; holes must not be inferred from ambiguous nesting |
| `CLOSEDPLANAR_XOR` | Exclusive-or of simple polygon masks | Supports explicitly encoded holes; every constituent polygon must still be simple and nondegenerate |

A redundant final vertex matching the first is accepted. Self-intersections,
backtracking/keyhole paths, degenerate polygons and repeated internal vertices
are rejected. Mixed geometric types within one ROI, open/point contours,
slab/offset/attached-contour semantics, and separate source-pixel-plane
characteristics are not supported. Unsupported inputs require explicitly reviewed
preprocessing or a geometrically verified labelmap; this adapter does not silently
repair them. ROI components are unioned only after their individual contours have
been rasterized and checked. Inspect the resulting geometry locally when applying
these conventions to a new export system, especially for small structures and
holes.

## Metric convention

DSC is `2 * intersection / (reference voxel count + prediction voxel count)`.
The surface consists of foreground voxel centres removed by one six-neighbour
binary erosion, with the region outside the array treated as background.
Euclidean nearest-surface distances are measured in millimetres in both directions.
If the directed arrays are A and B:

- HD95 is the linear 95th percentile of the concatenated array `[A, B]`.
- ASD is `(sum(A) + sum(B)) / (len(A) + len(B))`.

ASD is weighted by the number of sampled surface points. It is not the unweighted
average of two directional means and does not use mesh/surfel area weights.
HD95 is not the maximum of two separately calculated directional percentiles.
Volumes are voxel count times voxel volume, reported in cubic centimetres.
Empty reference or prediction masks raise errors; no arbitrary distance or
implicit patient exclusion is substituted.
