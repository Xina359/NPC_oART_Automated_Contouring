"""ED7a-c at 183 mm: all 315 effects, full CIs and text of at least 6 pt.

Uses OAR-size groups, sample-size headings and comparable external
scales. Limits are calculated from complete CIs rather than fixed old ranges.
"""
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, FuncFormatter
from .common import setup, COLOURS, SHORT, effect, limits
from ..constants import CENTRES, METRICS, SMALL, LARGE
from ..analysis import significant

WIDTH_MM, HEIGHT_MM = 183.0, 247.0


def compose(rows):
    setup()
    fig = plt.figure(figsize=(WIDTH_MM / 25.4, HEIGHT_MM / 25.4))
    lookup = {(r['centre'], r['roi'], r['metric']): r for r in rows}
    plotted, axes_info = [], []
    lefts = (46.0, 73.0, 100.0, 127.0, 154.0)
    axis_width = 24.0
    for k, metric in enumerate(METRICS):
        bottom = (166.0, 92.0, 18.0)[k]
        metric_label = 'DSC gain' if metric == 'DSC' else metric + ' reduction (mm)'
        fig.text(4 / WIDTH_MM, (bottom + 67) / HEIGHT_MM,
                 'abc'[k] + '  ' + metric_label, fontsize=8, weight='bold', va='center')
        fig.text(178 / WIDTH_MM, (bottom + 67) / HEIGHT_MM,
                 'Positive favours locked/adapted →', fontsize=6, ha='right', va='center')
        main_values = [0]
        for roi in (*SMALL, *LARGE):
            _, lo, hi = effect(lookup[(CENTRES[0], roi, metric)])
            main_values.extend((lo, hi))
        main_limits = limits(main_values)
        for part, rois in enumerate((SMALL, LARGE)):
            group = 'small' if part == 0 else 'large'
            block_bottom = bottom + (35 if part == 0 else 2)
            block_height = 23 if part == 0 else 27
            group_label = 'Small OARs (≤4 cm³)' if part == 0 else 'Large OARs (>4 cm³)'
            fig.text(3 / WIDTH_MM, (block_bottom + block_height / 2) / HEIGHT_MM,
                     group_label, rotation=90, fontsize=6, weight='bold',
                     ha='center', va='center', color='.35')
            external_values = [0]
            for centre in CENTRES[1:]:
                for roi in rois:
                    _, lo, hi = effect(lookup[(centre, roi, metric)])
                    external_values.extend((lo, hi))
            external_limits = limits(external_values)
            for j, (centre, left) in enumerate(zip(CENTRES, lefts)):
                ax = fig.add_axes([left / WIDTH_MM, block_bottom / HEIGHT_MM,
                                   axis_width / WIDTH_MM, block_height / HEIGHT_MM])
                ax.set_gid(f'ED7-{metric}-{group}-{centre}')
                for y, roi in enumerate(rois):
                    row = lookup[(centre, roi, metric)]
                    x, lower, upper = effect(row)
                    sig = significant(row['q_value'])
                    ax.plot([lower, upper], [y, y], color='.65', lw=.6)
                    point, = ax.plot(x, y, marker='s' if j == 0 else 'o', ms=3,
                                     mec=COLOURS[j], mfc=COLOURS[j] if sig else 'white', mew=.6)
                    point.set_gid(f'effect-{metric}-{centre}-{roi}')
                    plotted.append({'panel': 'abc'[k], 'centre': centre, 'ROI': roi,
                                    'metric': metric, 'effect': x, 'lower': lower, 'upper': upper,
                                    'stored_q': row['q_value'], 'q_below_0_05': sig,
                                    'P_q_recomputed_from_patient_pairs': False})
                lo, hi = main_limits if j == 0 else external_limits
                ax.set_xlim(lo, hi)
                ax.set_ylim(len(rois) - .5, -.5)
                ax.set_yticks(range(len(rois)))
                ax.set_yticklabels([SHORT.get(roi, roi) for roi in rois] if j == 0 else [], fontsize=6)
                ax.tick_params(axis='y', length=0, pad=2)
                ax.tick_params(axis='x', labelsize=6, length=2, pad=2)
                ax.xaxis.set_major_locator(MaxNLocator(nbins=2, min_n_ticks=2))
                ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f'{value:g}'))
                ax.axvline(0, color='.65', lw=.5, zorder=0)
                ax.grid(axis='y', alpha=.10)
                axes_info.append({'panel': 'abc'[k], 'category': group, 'centre': centre,
                                  'x_min': lo, 'x_max': hi, 'all_CIs_retained': True,
                                  'scale_group': 'main, both OAR sizes' if j == 0 else 'external, ' + group,
                                  'figure_width_mm': WIDTH_MM, 'minimum_font_pt': 6})
                if part == 0:
                    n = lookup[(centre, rois[0], metric)]['n']
                    fig.text((left + axis_width / 2) / WIDTH_MM, (bottom + 62) / HEIGHT_MM,
                             centre, fontsize=6.5, weight='bold', color=COLOURS[j], ha='center')
                    fig.text((left + axis_width / 2) / WIDTH_MM, (bottom + 59) / HEIGHT_MM,
                             f'n = {n}', fontsize=6, color='.35', ha='center')
    fig.text(.5, 242 / HEIGHT_MM, 'Organ-specific changes across five centres',
             fontsize=9, ha='center', va='center')
    fig.text(4 / WIDTH_MM, 3 / HEIGHT_MM,
             'Filled: stored BH-adjusted q < 0.05; open: q ≥ 0.05. Bars: pointwise 95% CIs.\n'
             'Main: squares; external: circles. External centres share a scale within each OAR-size block.\n'
             'All 315 archived effects are shown; patient-level P/q reanalysis requires the local workbook.',
             fontsize=6, linespacing=1.4)
    return fig, plotted, axes_info
