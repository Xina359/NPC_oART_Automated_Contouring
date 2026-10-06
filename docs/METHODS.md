# Numerical analysis specification

This document specifies numerical analysis, not a clinical model.

## Input and pairing

The primary key is centre, model state, study ID, ROI and metric. Pairing uses
study IDs within centre/ROI/metric, never row order or metric rank. Duplicate
keys, nonnumeric values, undefined units, absent paired states and unexpected
counts are rejected. Main-centre tests contain 12 GTV and 29 distinct CTV/OAR
patients. External test counts are 14, 21, 14 and 25. Prospective records cover
135 patients × 25 target/organ categories × 3 metrics. ROI names/codes must be
one-to-one across cohorts.

## Composite precision

For every patient and metric, the small and large composites are arithmetic
means over all 10 or all 11 fixed organ categories, respectively. Every required
constituent must be present. Bilateral union is an upstream mask operation,
reported in the paper; the numerical workbook cannot independently verify it.
Large organs in a small-organ inference pathway stay in the large statistical
composite. No new per-patient volume threshold is applied.

Primary S4 reanalysis uses the four-decimal values stored in
`Patient-level OAR averages`, verified within half a last decimal unit against
constituent means. The primary result is not replaced by higher precision.
`Table_S4_unrounded_composites_sensitivity.csv` and
`Composite_precision_sensitivity.csv` explicitly show the alternative.
The auxiliary external summary and prospective composites use constituent means
without additional intermediate rounding. S4/S5 plots use the validated
archived summary values so both input modes show the same archived data.

## Descriptive statistics, CI, t test and BH

Sample SD divides by n-1; SEM=SD/sqrt(n). Quantiles are linear interpolations.
All observations are retained. For d=after-before, the two-sided test uses
`t=mean(d)/(SD(d)/sqrt(n))`, n-1 degrees of freedom. Pointwise 95% CIs are
`mean(d) ± t(0.975,n-1)*SD(d)/sqrt(n)`. All-zero differences yield P=1; constant
nonzero differences yield the limiting P=0 with an undefined t statistic.

BH adjustment is performed independently inside each centre and table: 18
comparisons for S4 and 63 for S5. It uses the reverse cumulative minimum of
m*p(rank)/rank and restores the original endpoint order. Significance is q<0.05.
CIs are not multiplicity-adjusted; a zero-crossing CI and BH significance need
not give the same decision. The original study methods specify these families.

Archived strings such as `<0.0001` are strict bounds, not exact probabilities.
Complete-workbook recalculations export actual computed P/q. Bundled plots use
stored results and make no claim to reconstruct their missing patient pairs.
Numeric archive comparisons use 0.00005 plus a small floating-point allowance;
counts are checked exactly and bounded P/q are tested as strict inequalities.

## Display-only rounding

Final labels use decimal half-up rounding. Intermediate means, differences, CI
limits or P/q are not pre-rounded before another display rounding. Percentile
display uses Decimal linear interpolation on the supplied values to avoid a
binary64 representation deciding an exact decimal midpoint. Unrounded numeric
CSV outputs retain binary64 precision. For example, 0.744625 displays as 0.74
at two decimals and 0.745 at three, without producing 0.75 by double rounding.

## Expanded S6

S6a-c each contain 27 rows in this order: GTVp, GTVn, CTV1, CTV2, small- and
large-OAR composites, 10 small organs and 11 large organs. Each row has n=135,
mean, sample SD, pointwise 95% mean CI, median, Q1, Q3, P5 and P95. This is 81
rows and 729 core summary numbers (excluding the repeated sample counts).

The six DSC target/composite endpoints are primary; individual-organ DSC is
supportive and distance metrics are secondary. This code adds no new prospective
hypothesis tests. S6 CI limits are t-based; distribution quantiles are not CIs.
The complete table requires the local workbook; the default bundled subset
contains only the six patient-level endpoints used in Fig.6a.

## Plot signs, case and timing

All table differences are after-before. DSC gain keeps the sign. For surface
reductions, negate the effect and map CI to [-upper,-lower]. Full confidence
intervals remain on the axes, including deterioration.

ED5 uses MC_R023 with 21 OARs. Header means are equal-weight averages within this
one patient and are not cohort results. ED4 includes 12 patients under the same
three strategies. Both are descriptive; no extra P/q testing is introduced.

The timing arithmetic sum is computed per patient before its SD/percentiles.
Ranking is 1-135 by that sum, not temporal order.
Sample-size calculation uses SD=.0653, half-width=.012,
normal 95% confidence, then 15% non-evaluable allowance: 114 and 135.
