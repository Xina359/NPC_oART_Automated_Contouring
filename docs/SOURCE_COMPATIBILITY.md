# Source Data compatibility - version 2.1.0

## Reference input

- Filename: `Source_data.xlsx`; selection uses an explicit path and is independent
  of the basename.
- File SHA-256:
  `f8fb9417ee299f19d72df7da49c4aed29fb8b74797d0122bfe262aff33c6af3b`.
- Stored-data SHA-256:
  `065df1d9c89b0016810457a7c4cb47880ea91b98227099cb88dcb1a61240a644`.
- Source profile ID: `source-data-2026-10-06-v2.1.0`.
- Actual GTVn tab: `Extended Data Fig. 4 GTVn compa`.
- No formula cells are recorded in this reference workbook's source profile.

The original workbook is read-only. The package does not rename worksheets,
rewrite metadata, recalculate formulas or change measurements. The general
OOXML reader uses stored cached formula values when available and rejects a
formula cell lacking such a value.

## Worksheets and schema

Seven exact data tabs are `Table S4`, `Table S5`,
`Retrospective patient metrics`, `Patient-level OAR averages`,
`Prospective patient metrics`, `Prospective timing` and `External-centre summary`.
The GTVn strategy tab is resolved from these exact names:

1. `Extended Data Fig. 4 GTVn compa` - current source.
2. `ED4 GTVn comparison` - compatible short name.
3. `Fig S4 GTVn comparison` - supported worksheet alias.
4. `Extended Data Fig 4 GTVn` - supported alternate name.

More than one recognized tab produces an ambiguity error. A deliberate custom
name can be selected with `--strategy-sheet NAME`. Both automatic and explicit
selection must satisfy the two header schemas:

| Block | Headers in order |
|---|---|
| A:G | Centre; Study ID; ROI; Strategy; Metric; Value; Unit |
| I:N | Strategy; Metric; n; Mean; Sample SD; Unit |

There is no fuzzy or prefix matching. A valid header alone does not validate the
research data: complete analysis additionally checks identities, units, counts,
metrics, pairs, constituents and archived numerical relationships.

The internal dictionary key is `Fig S4 GTVn comparison` for compatibility.
The actual selected worksheet name is separately recorded in runtime metadata
and the bundled-data manifest. The API key does not change a manuscript
figure label or the source file's real worksheet name.

## Fingerprints and inspection

`oart_analysis/data/source_profile.json` stores the reference file hash and
ordered cell-address/value hashes of the eight logical data sheets. The
stored-data fingerprint excludes README and formatting and normalizes only the
strategy-sheet identifier. It does not round values or discard patient records.
Runtime metadata distinguishes:

- `exact_file`: byte-identical to the reference workbook.
- `same_stored_data`: file bytes differ but the profiled data cells match.
- `different_stored_data`: at least one profiled data sheet differs.

The result also identifies changed sheet IDs. These describe input identity;
they do not replace full numerical validation or raw-image verification.

```bash
python scripts/inspect_source_data.py --source-data "D:/paper/Source_data.xlsx" --output outputs/inspection
```

This command inspects schema/identity only. Use `analyse` or `run_all.py` with
the same explicit workbook for complete patient-level analysis. The source file
need not retain its original filename to be recognized by its content.
