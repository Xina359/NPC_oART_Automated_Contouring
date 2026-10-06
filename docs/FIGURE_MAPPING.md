# Manuscript-to-code mapping

Each `plot` command below is a subcommand of `python -m oart_analysis.cli` and
accepts a new/empty `--output` directory. Omit `--source-data` to use bundled
records or explicitly supply the complete workbook.

| Manuscript item | Included part | Input | Command | Stem under output `figures/` |
|---|---|---|---|---|
| Fig. 5 | b,c | Archived S4 summaries | `plot --figure 5` | `Figure5/Figure5_bc` |
| Fig. 6 | a,b | Six prospective endpoints and timing | `plot --figure 6` | `Figure6/Figure6_ab` |
| ED4 | b only, three metric plots | 108 GTVn strategy records | `plot --figure ED4` | `ExtendedDataFigure4/ExtendedDataFigure4_b` |
| ED5 | Quantitative case figure | MC_R023, 21 OAR pairs | `plot --figure ED5` | `ExtendedDataFigure5/ExtendedDataFigure5` |
| ED6 | a-d | Archived S4 summaries | `plot --figure ED6` | `ExtendedDataFigure6/ExtendedDataFigure6_abcd` |
| ED7 | a-c | Archived S5 summaries | `plot --figure ED7` | `ExtendedDataFigure7/ExtendedDataFigure7_abc` |

The formal ED4 panels are a and b. DSC, HD95 and ASD are three internal plots
within b; they are not formal ED4b/c/d. ED4a's clinical image is not generated.
Fig. 5b,c must be assembled separately from the authors' Fig. 5a artwork.

Complete S6 generation uses `analyse --source-data PATH` and writes to
`analysis/Table_S6.csv`, `Table_S6a.csv`, `Table_S6b.csv`, `Table_S6c.csv`,
`Table_S6_display.csv` and `Supplementary_Table_S6.md`. It has 27 rows for each
metric, 81 total. Its full constituent data are not in bundled mode.

## Source compatibility and outputs

The current source is read directly without
renaming any tab; see [SOURCE_COMPATIBILITY.md](SOURCE_COMPATIBILITY.md).

All generated sets export SVG, PDF, PNG and TIFF plus plotted values. Numerical
layouts may differ from manuscript artwork. Full displayed confidence intervals
and observations are retained rather than clipped to force visual agreement.
