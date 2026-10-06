"""ED5: one OAR case, with the manuscript's baseline and change annotations.

Uses anatomical grouping and a baseline-centred comparison. Grey
labels are absolute baseline values; black labels are beneficial changes.
Header deltas use after-minus-before for every metric, including distances.
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from .common import setup, SHORT
from ..constants import METRICS, CASE_ORDER
from ..display import rounded

BASELINE_COLOUR = '#71808A'
MODEL_COLOUR = '#377B97'


def _signed(value, digits):
    return ('+' if value >= 0 else '') + rounded(float(value), digits)


def _row_layout():
    positions, groups = [], []
    previous = None
    y = 0.0
    for group, roi in CASE_ORDER:
        if group != previous:
            if previous is not None:
                y += 1.05
            groups.append((group, y - .72, len(positions)))
            previous = group
        positions.append(y)
        y += 1.0
    return positions, groups


def compose(rows):
    setup()
    lookup = {r['roi']: r for r in rows}
    rows = [lookup[roi] for _, roi in CASE_ORDER]
    ypos, groups = _row_layout()
    fig = plt.figure(figsize=(183 / 25.4, 226 / 25.4))
    grid = fig.add_gridspec(1, 4, left=.02, right=.98, top=.85, bottom=.115,
                           width_ratios=(1.40, 1, 1, 1), wspace=.25)
    labels = fig.add_subplot(grid[0, 0])
    axes = [fig.add_subplot(grid[0, i]) for i in (1, 2, 3)]
    for ax in (labels, *axes):
        ax.set_ylim(ypos[-1] + .6, -1.15)
        for g, (_, _, first) in enumerate(groups):
            last = groups[g + 1][2] - 1 if g + 1 < len(groups) else len(rows) - 1
            ax.axhspan(ypos[first] - .45, ypos[last] + .45,
                       color='#F3F6F7' if g % 2 == 0 else '#FCFDFD', zorder=0)
    labels.set_xlim(0, 1)
    labels.set_axis_off()
    for r, y in zip(rows, ypos):
        labels.text(.02, y, SHORT.get(r['roi'], r['roi']), va='center', fontsize=6)
    for group, y, _ in groups:
        labels.text(0, y, group, va='center', fontsize=6.4,
                    weight='bold', color=MODEL_COLOUR)

    header = []
    for ax, metric in zip(axes, METRICS):
        m = metric.lower()
        digits = 3 if metric == 'DSC' else 2
        changes = np.array([r['beneficial_change_' + m] for r in rows])
        minimum = min(0, float(changes.min()))
        maximum = max(0, float(changes.max()))
        span = max(maximum - minimum, .001)
        for r, y, change in zip(rows, ypos, changes):
            ax.plot([0, change], [y, y], color='#D1E4EC', lw=3.5,
                    solid_capstyle='round', zorder=2)
            ax.plot([0, change], [y, y], color=MODEL_COLOUR, lw=1, zorder=3)
            ax.plot(0, y, 'o', mfc='white', mec=BASELINE_COLOUR, ms=3.5, zorder=4)
            ax.plot(change, y, 'D', color=MODEL_COLOUR, ms=3.6, zorder=4)
            baseline = ax.annotate(rounded(r['baseline_' + m], digits), (0, y),
                                   xytext=(0, 4), textcoords='offset points',
                                   ha='center', va='bottom', fontsize=6,
                                   color=BASELINE_COLOUR)
            baseline.set_gid(f'baseline-{metric}-{r["roi"]}')
            label = ax.annotate(_signed(change, digits), (change, y),
                                xytext=(4, 0), textcoords='offset points',
                                ha='left', va='center', fontsize=6, color='black')
            label.set_gid(f'beneficial-change-{metric}-{r["roi"]}')
        ax.set_xlim(minimum - .15 * span, maximum + .48 * span)
        ax.set_yticks([])
        ax.xaxis.set_major_locator(MaxNLocator(nbins=3, min_n_ticks=2))
        ax.tick_params(labelsize=6, length=2)
        ax.grid(axis='x', alpha=.12)
        ax.set_xlabel('DSC gain' if metric == 'DSC' else metric + ' reduction (mm)', fontsize=6.5)
        before = float(np.mean([r['baseline_' + m] for r in rows]))
        after = float(np.mean([r['vag_' + m] for r in rows]))
        difference = after - before
        header.append({'metric': metric, 'baseline_mean': before,
                       'VAG_UNet_mean': after, 'after_minus_before': difference,
                       'n_organs': 21, 'study_id': 'MC_R023'})
        unit = '' if metric == 'DSC' else ' mm'
        title = ax.set_title(
            f'{metric}\n{rounded(before, digits)} → {rounded(after, digits)}\n'
            f'Δ {_signed(difference, digits)}{unit}', fontsize=7, pad=10)
        title.set_gid(f'header-after-minus-before-{metric}')
    fig.suptitle('Representative OAR case: MC_R023', fontsize=9, y=.985)
    fig.text(.02, .954, '21 OAR categories; descriptive within-patient changes', fontsize=7)
    footer = fig.text(.02, .022,
             'Grey labels: absolute baseline values. Black labels: DSC gain or distance reduction.\n'
             'Open circles: zero change. Diamonds: VAG-UNet; positive plotted values favour VAG-UNet.\n'
             'Headers: equal-weight organ means and Δ = VAG-UNet − baseline for every metric.\n'
             'No case-level P values or population confidence intervals are inferred.',
             fontsize=6.5, linespacing=1.35)
    footer.set_gid('ED5-explanatory-footer')
    return fig, header
