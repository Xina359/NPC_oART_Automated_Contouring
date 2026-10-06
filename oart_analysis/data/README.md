# Packaged numerical subset - version 2.1.0

The six CSVs in this directory contain real study plotting records regenerated
from the current `Source_data.xlsx`. The package loader uses installed resources, so these files remain
available outside a source checkout.

`manifest.json` records filenames, row counts, field types, CSV SHA-256 hashes,
source-workbook identity and the actual GTVn worksheet name.
`source_profile.json` records only source identity, schema and stored-data hashes;
it contains no complete workbook or patient image.

See `data/README.md` in the source distribution for the field dictionary and
`docs/PUBLIC_SCOPE.md` for access boundaries. The software licence does not
assign a new data licence. The six CSVs support reproduction of the included
figures; additional reuse follows the manuscript's data terms and applicable
permissions. Original clinical images, model weights and proprietary contouring
software are not packaged.
