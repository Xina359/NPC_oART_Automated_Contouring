# Interpretation and limits

1. Full-workbook checks begin with the supplied numerical measurements. They do
   not validate original CT/masks, enrolment records, registration quality,
   clinical system logs or measurement provenance upstream of the workbook.
2. The bundled CSV subset cannot independently recompute every retrospective
   P/q value, verify all constituent OAR means or regenerate complete S6.
3. Primary S4 results preserve archived four-decimal composites. The separately
   exported unrounded sensitivity calculation can differ in its final digits.
4. Display values use one-step decimal half-up rounding. Numeric CSVs retain
   calculation precision.
5. Original surface sampling and contour rasterization cannot be inferred from
   metric results. Optional imaging evaluation uses the explicit conventions in
   IMAGING.md. Synthetic geometry tests do not establish clinical validity.
6. Source README A15/B35 use a longer descriptive GTVn tab name than the actual
   tab; E39 asks for a rounding convention. These nonfatal metadata observations
   are reported without changing the workbook. Input identity and full numerical
   validation are separate checks.
7. Plots reproduce the supplied numbers with documented layouts; they are not
   pixel-identical manuscript artwork or clinical-system screenshots.

8. Public code does not contain the licensed contouring networks or weights.
   Model access and restricted study materials follow the manuscript and
   applicable rights. This release assigns no new data licence.
