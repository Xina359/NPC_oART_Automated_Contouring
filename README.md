# NPC oART Automated Contouring

**Version 2.1.0**

Data extraction, statistical analysis, quantitative figure reproduction and
metrics from locally exported masks for *Clinical integration of automated
contouring for online adaptive radiotherapy in nasopharyngeal carcinoma*.

[Methods](docs/METHODS.md) · [Figure mapping](docs/FIGURE_MAPPING.md) ·
[Data dictionary](data/README.md) · [Local imaging](docs/IMAGING.md)

## Quick start

Python 3.11 or later is required. From the unpacked project directory:

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -c requirements-tested.txt -e ".[test]"
python run_all.py --output outputs/bundled
```

This generates six quantitative figure sets from the six bundled study CSVs.
They contain actual measurements and derived summaries, not simulated examples.
The complete `Source_data.xlsx`, original medical images and proprietary models
are not included. Plotting requires neither a GPU nor uTPS. Once dependencies
are installed, the analysis uses local files and does not download or upload data.
Choose a new or empty output directory for every run.

`requirements-tested.txt` records the core/test dependency constraints used for
this release's local environment.
These requirements describe the analysis package, not the clinical model runtime.

## Select an input mode

| Mode | Selection | Available analysis |
|---|---|---|
| Bundled numerical subset | Omit `--source-data` | Six figure sets and descriptions of their supplied values; archived S4/S5 P and q values remain stored results |
| Complete local workbook | Supply `--source-data PATH` | Patient-level reanalysis, 405 paired comparisons, constituent/composite checks, external summaries, complete S6a-c and all six figure sets |

```bash
# Complete numerical reanalysis and figures from your local workbook
python run_all.py --source-data "D:/paper/Source_data.xlsx" --output outputs/workbook

# Statistical analysis only
python -m oart_analysis.cli analyse --source-data "D:/paper/Source_data.xlsx" --output outputs/analysis_only

# One quantitative figure set from the bundled data
python scripts/plot_extended_data4.py --output outputs/ed4
python -m oart_analysis.cli plot --figure ED7 --output outputs/ed7

# Inspect workbook identity and schema without statistical reanalysis
python scripts/inspect_source_data.py --source-data "D:/paper/Source_data.xlsx" --output outputs/inspection

# Export worksheet records for local use
python scripts/extract_source_data.py --source-data "D:/paper/Source_data.xlsx" --output local_data/extracted
```

Replace the example workbook path with its location on your computer. The default
mode never searches for a workbook. An explicitly selected missing or invalid
workbook causes an error, with no fallback. The input is read-only. Formula cells
use their stored cached values; the reader does not calculate formulas and rejects
formula cells without cached values.

The current workbook's GTVn tab is `Extended Data Fig. 4 GTVn compa`; no rename is
needed. Recognized worksheet aliases and an explicit `--strategy-sheet` override are
supported with schema checks. Ambiguous automatic matches cause an error. See
[SOURCE_COMPATIBILITY.md](docs/SOURCE_COMPATIBILITY.md) for the reference input
hash and exact aliases.

Runs record their mode, source identity and validation scope in `data_source.json`.
Analysis/plot runs also write `runtime_versions.json`; each figure directory has
its own input-provenance record. Nonempty output directories are rejected to
prevent mixing results from different inputs. Local extraction is separate from
the six-file public subset and does not itself authorize redistribution.

## Figures and tables

Figure directories appear under the selected output directory's `figures/` folder.
Each figure is exported as editable-text SVG, PDF, 300-dpi PNG and 600-dpi TIFF,
with the plotted values alongside it.

| Directory | Manuscript coverage |
|---|---|
| `Figure5` | Fig. 5b,c: five-centre DSC means and paired effects |
| `Figure6` | Fig. 6a,b: six patient-level endpoints and 135 timing records |
| `ExtendedDataFigure4` | ED4b only: three internal plots for DSC, HD95 and ASD |
| `ExtendedDataFigure5` | ED5: the 21-OAR case MC_R023 |
| `ExtendedDataFigure6` | ED6a-d: HD95/ASD means and paired reductions |
| `ExtendedDataFigure7` | ED7a-c: organ-specific paired effects across five centres |

These are numerical reproductions, not pixel-identical copies of submitted
artwork.

Complete-workbook analysis writes `analysis/Table_S6.csv`, the separate
`Table_S6a.csv`, `Table_S6b.csv` and `Table_S6c.csv`, and display-ready
`Table_S6_display.csv` and `Supplementary_Table_S6.md`. S6 contains 27
ROIs/composites for each of three metrics: **81 rows and 729 core summary
numbers**, excluding repeated sample counts. Each row describes 135 patients.
The bundled six prospective endpoints do not contain all constituent organ
measurements and cannot regenerate this full table or all retrospective P/q tests.

## Numerical conventions

- Patients are the analysis unit. Pairing uses study identifiers within each
  centre, ROI and metric. Missing pairs, duplicate keys and incomplete required
  OAR constituents cause errors; no imputation or automatic exclusion is applied.
- Small/large OAR composites use fixed sets of 10/11 organs. Primary S4 reanalysis
  uses the archived four-decimal patient composites; an unrounded alternative is
  exported separately as sensitivity analysis. Prospective composites and the
  auxiliary external summary use unrounded constituent means.
- Tests are two-sided paired t-tests. Mean confidence intervals are pointwise
  t intervals. BH families contain 18 S4 comparisons or 63 S5 comparisons within
  each centre. Stored probability bounds such as `<0.0001` are not exact P values.
- Final display uses decimal round-half-up once; S6 values use three decimal places. S6 distribution
  percentiles use linear interpolation. Quantile ranges in Fig. 6a are not CIs.
- Distance reductions reverse the after-minus-before sign and negate/exchange
  the CI endpoints. Descriptive GTVn-strategy and single-case plots add no new
  hypothesis tests.
- Fig. 6b ranks patients by the arithmetic sum of two recorded intervals.

Full definitions are in [METHODS.md](docs/METHODS.md).

## Metrics from local masks

The optional adapter calculates DSC, HD95 and ASD from exported labelmaps or
RTSTRUCTs on a supported CT grid. It does not generate model predictions,
register images or resample mismatched masks.

```bash
python -m pip install -c requirements-tested.txt -c requirements-imaging-tested.txt -e ".[imaging,test]"
python -m oart_analysis.cli metrics --config config/imaging.local.json --output outputs/local_masks
```

Before running the second command, copy `config/imaging.example.json` for
labelmaps or `config/imaging.rtstruct.example.json` for RTSTRUCTs to
`config/imaging.local.json`, and enter your local paths and exact ROI labels or
names. Relative input paths are resolved against the configuration file.
Bilateral components are unioned before evaluation. See [IMAGING.md](docs/IMAGING.md)
for accepted geometry, contour conventions and output interpretation. The metric
workbook cannot establish the original study's raw-mask rasterization or surface
implementation, so this adapter does not certify raw-image reproduction of the
archived measurements.

## Availability, rights and citation

The public scope is numerical extraction/analysis, quantitative plotting and
metrics from locally exported masks. PCG-UNet, PAC-UNet and VAG-UNet are integrated
in the licensed automated contouring module of uTPS (United Imaging Healthcare,
Shanghai, China). Their implementations, training pipelines and model weights,
and the registration and clinical workflow systems, are not distributed here.
For model access, refer to the associated manuscript's Data Availability
statement and corresponding author, Y.S. (sunying@sysucc.org.cn), together with
applicable institutional approvals, agreements and rights-holder conditions.
This package does not alter that statement's commitments or conditions.

The software retains the original [Apache License 2.0](LICENSE). It does not
confer rights in proprietary software, model weights or nonpublic medical data.
The six study CSVs support reproduction of the included figures; no separate new
data licence is assigned here. Refer to the manuscript's data-access terms and
the responsible authors for uses requiring additional permission. The full Source
Data is a separate study material, not bundled in this software archive. Keep
local workbooks and medical images outside the public repository.

See [CITATION.md](CITATION.md) for the software identity and study title, and
[PUBLIC_SCOPE.md](docs/PUBLIC_SCOPE.md) for the complete availability mapping.
