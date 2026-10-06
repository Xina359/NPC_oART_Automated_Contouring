# Availability and reproduction scope

Version 2.1.0 provides local numerical extraction/analysis, metrics from exported
masks and quantitative panel plotting. These are research analysis functions;
the package does not implement clinical contour generation or treatment delivery.

| Material or function | Access through this package | Interpretation |
|---|---|---|
| Six plotting CSV datasets | Included in `oart_analysis/data/` | Six numerical data categories extracted from the current Source Data |
| Complete `Source_data.xlsx` | Separate study material supplied locally with `--source-data` | Required for full patient-level reanalysis; not in the software archive |
| S4/S5 paired reanalysis | Code included | Full retrospective pairs are not in the bundled subset |
| S6a-c, 81 rows | Code included | Requires full prospective constituent measurements from the workbook |
| Labelmap and RTSTRUCT metric evaluation | Optional local-file adapter | Requires separate local images and accepted geometry; see IMAGING.md |
| Raw study CT images and contour sets | Not included | Refer to the manuscript's Data Availability statement and restrictions |
| PCG-UNet, PAC-UNet, VAG-UNet implementations, training and weights | Not included | Integrated in licensed uTPS; model requests follow the manuscript's corresponding-author route and applicable rights |
| Image registration, clinician review and contour-QA workflow | Not included | Cannot be reconstructed from a workflow diagram or metric table |
| Fig. 5a and ED1-3 artwork | Not reproduced | Workflow/network artwork is outside quantitative plotting scope |
| ED4a clinical image panel | Not reproduced | Only the three metric plots within ED4b are generated |
| Dose optimization and treatment delivery | Not included | Geometric metrics do not establish dosimetric or clinical benefit |

The six CSVs are supplied for reproduction of the included figures. The software's
Apache-2.0 licence does not independently license study data, restricted images,
proprietary software or model weights. No new data licence is assigned by this
release. Consult the manuscript's access terms and responsible authors for
additional permissions.

The `extract` command writes fuller worksheet records to a local output folder.
That action is separate from public distribution. The `export-bundled` command
writes exactly the six existing CSV categories and their manifest after complete
workbook validation. Neither command uploads any data.
