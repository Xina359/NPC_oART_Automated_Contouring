"""Patient-level statistics, with no automatic record deletion or imputation."""
import math
import numpy as np
from scipy import stats


def numeric_vector(values):
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or len(x) < 2 or not np.isfinite(x).all():
        raise ValueError("Expected at least two finite observations in a one-dimensional vector")
    return x


def describe(values, confidence=0.95):
    x = numeric_vector(values)
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")
    n, mean, sd = len(x), float(x.mean()), float(x.std(ddof=1))
    sem = sd / math.sqrt(n)
    halfwidth = float(stats.t.ppf((1 + confidence) / 2, n - 1)) * sem
    q = np.quantile(x, [0, .05, .25, .5, .75, .95, 1], method="linear")
    return dict(n=n, mean=mean, sd=sd, sem=sem, cv=(sd / mean if mean != 0 else None),
                ci_lower=mean-halfwidth, ci_upper=mean+halfwidth,
                **dict(zip(("minimum", "p5", "q1", "median", "q3", "p95", "maximum"), map(float, q))))


def paired_test(before, after):
    x, y = numeric_vector(before), numeric_vector(after)
    if len(x) != len(y):
        raise ValueError("Paired vectors must have identical lengths")
    d = y - x
    summary = describe(d)
    # Degenerate difference distributions are explicit; no silent NaN P values.
    if summary["sd"] == 0:
        t, p = (0.0, 1.0) if summary["mean"] == 0 else (None, 0.0)
    else:
        t = summary["mean"] / summary["sem"]
        p = float(2 * stats.t.sf(abs(t), len(d) - 1))
    return dict(before=describe(x), after=describe(y), difference=summary, t=t, p=p)


def benjamini_hochberg(p_values):
    p = np.asarray(p_values, dtype=float)
    if p.ndim != 1 or not len(p) or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError("P values must be a nonempty finite vector in [0, 1]")
    order = np.argsort(p, kind="stable")
    q_sorted = np.minimum.accumulate((p[order] * len(p) / np.arange(1, len(p)+1))[::-1])[::-1]
    q = np.empty_like(p)
    q[order] = np.minimum(q_sorted, 1)
    return q


def orient_effect(mean, lower, upper, metric):
    if metric not in ("DSC", "HD95", "ASD") or not lower <= mean <= upper:
        raise ValueError("Invalid metric or confidence interval")
    return (mean, lower, upper) if metric == "DSC" else (-mean, -upper, -lower)


def precision_sample_size(sd=0.0653, half_width=0.012, non_evaluable=0.15, confidence=0.95):
    if sd <= 0 or half_width <= 0 or not 0 <= non_evaluable < 1 or not 0 < confidence < 1:
        raise ValueError("Invalid sample-size assumptions")
    z = float(stats.norm.ppf((1+confidence)/2))
    continuous_n = (z*sd/half_width)**2
    evaluable = math.ceil(continuous_n)
    return dict(sd=sd, half_width=half_width, confidence=confidence, non_evaluable=non_evaluable,
                z=z, continuous_n=continuous_n, evaluable_n=evaluable,
                recruitment_n=math.ceil(evaluable/(1-non_evaluable)))

