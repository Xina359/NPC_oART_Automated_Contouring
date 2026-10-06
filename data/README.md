# Data dictionary and access boundary

Version 2.1.0 includes six real numerical CSVs under `oart_analysis/data/`,
regenerated from the current `Source_data.xlsx`.
The full workbook, original images,
full constituent patient tables and model weights are not bundled.

| Key / file | Rows | Observation unit and content | Figure use |
|---|---:|---|---|
| `summary_s4` / `table_s4_plot.csv` | 90 | 5 centres x 6 endpoints x 3 metrics; archived paired summaries | Fig. 5b,c; ED6a-d |
| `summary_s5` / `table_s5_plot.csv` | 315 | 5 centres x 21 organ categories x 3 metrics; archived paired summaries | ED7a-c |
| `performance` / `prospective_endpoints.csv` | 2430 | 135 patients x 6 target/composite endpoints x 3 metrics | Fig. 6a |
| `timing` / `prospective_timing.csv` | 135 | One patient's two recorded intervals and arithmetic sum | Fig. 6b |
| `gtvn` / `gtvn_strategies.csv` | 108 | 12 patients x 3 strategies x 3 metrics | Three internal plots of ED4b |
| `case` / `representative_oar_case.csv` | 21 | One OAR in MC_R023, two states and three metrics | ED5 |

These records contain coded study identifiers and measurements/derived values,
not simulated demonstration data. They do not include patient names, dates of
birth or medical images. Their scope should not be confused with the complete
Source Data supplied separately with the study.

## Fields and units

- `centre`, `roi`, `metric`, `before_model`, `after_model` identify a comparison.
  DSC is dimensionless; HD95 and ASD are in millimetres. `n` is the number of
  paired patients, not organs, slices or treatment fractions.
- `before_mean`, `after_mean`, `before_sd`, `after_sd` summarize patients using
  arithmetic means and sample SDs. `mean_difference` is after minus before;
  `ci_lower` and `ci_upper` are its pointwise 95% CI. Distance-improvement plots
  negate the effect and exchange/negate the endpoints during rendering.
- `p_value` and `q_value` retain archived paired-test and within-centre BH
  results. Values such as `<0.0001` are strings expressing strict bounds;
  they are not exact probabilities or newly calculated tests in bundled mode.
- Prospective `study_id`, `category` and `metric` form the record key. `value`
  holds the patient endpoint. `n_components` is 1 for a target, 10 for a small-OAR
  composite or 11 for a large-OAR composite. All required constituents contribute
  equally to the composite without additional intermediate rounding.
- `algorithm_s`, `review_s` and `combined_s` are seconds. `combined_s` is the
  `algorithm_s + review_s` arithmetic sum for each patient.
- GTVn records retain the source's English field names, including `Study ID`,
  `Strategy`, `Metric`, `Value` and `Unit`. The same 12 patients occur under all
  three strategies.
- Case `baseline_*` and `vag_*` fields contain absolute values.
  `beneficial_change_*` is after minus before for DSC and before minus after for
  distances. Anatomical display groups are separate from the fixed small/large
  OAR statistical composites. The 21-organ average is a single-case description.
- `source_sheet`, `source_row`, `source_rows`, `source_cells` and `*_cell` fields
  preserve source worksheet locations where available. Excel rows are 1-based;
  cell lists identify the constituents of a derived value. GTVn sheet identity
  is also stored in the manifest because its title may change across versions.

CSV fields and their serialized types are listed in `oart_analysis/data/manifest.json`.
Missing required measurements are errors, not zero or implicit exclusions.

## Precision and integrity

Stored summary means, effects and CIs retain their archived precision. CSV
floating-point values use 17 significant digits to preserve binary64 round trips;
a long representation does not imply higher source measurement accuracy. Final
plot/table display applies the documented rounding separately.

The manifest records dataset version 2.1.0, row counts, CSV hashes and source
identity. The loader checks hashes, coverage, unique keys, units, counts,
interval ordering, timing sums and case changes. The subset still cannot rebuild
missing retrospective patient pairs or all prospective constituent organ values.
Full reanalysis requires an explicit local workbook.

## Local workbook

Seven data tabs have exact names: `Table S4`, `Table S5`,
`Retrospective patient metrics`, `Patient-level OAR averages`,
`Prospective patient metrics`, `Prospective timing` and `External-centre summary`.
The current eighth data tab is `Extended Data Fig. 4 GTVn compa`. Its A:G block
holds 108 measurements; I:N holds nine archived summaries.

S6 has no independent input worksheet. Complete-workbook analysis derives all
81 rows from the prospective measurements and their complete patient composites.
The source profile contains identity/schema metadata only, not a hidden copy of
the workbook.

```bash
python run_all.py --source-data "D:/paper/Source_data.xlsx" --output outputs/workbook
python scripts/export_public_data.py --source-data "D:/paper/Source_data.xlsx" --output local_data/public_subset
```

Use the actual path to your workbook and an empty output directory. The explicit
public-subset export validates the complete workbook and writes the same six CSV
categories and their manifest. `extract_source_data.py` instead exports fuller
worksheet records locally. It is not a publication or an authorization to release
additional patient records.

## Rights and citation

The six CSVs support reproduction of the included figures. No separate new data
licence is assigned in this package. Apache-2.0 is retained for the software and
does not grant rights in nonpublic medical data, proprietary models or images.
Further reuse follows the associated manuscript's data terms and applicable
permissions. Cite the study and software version as described in
[CITATION.md](../CITATION.md). Requests concerning additional de-identified study
data or models follow the manuscript's corresponding-author route; no download
or remote access service is supplied by this archive.
