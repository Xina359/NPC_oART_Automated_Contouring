"""Caption contracts and complete, legible quantitative figure output."""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.text import Text
import pytest

from oart_analysis.plot_data import load_bundled
from oart_analysis.display import rounded
from oart_analysis.constants import CENTRES, METRICS, SMALL, LARGE
from oart_analysis.figures import representative_case, organ_effects, prospective, gtvn_strategies


@pytest.fixture(scope='module')
def data():
    return load_bundled()[0]


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close('all')


def tagged(fig, prefix):
    return {artist.get_gid(): artist for artist in fig.findobj()
            if artist.get_gid() and artist.get_gid().startswith(prefix)}


def test_ed5_retains_all_absolute_baselines_and_beneficial_changes(data):
    fig, headers = representative_case.compose(data['case'])
    baseline = tagged(fig, 'baseline-')
    changes = tagged(fig, 'beneficial-change-')
    assert len(baseline) == len(changes) == 21 * 3
    for row in data['case']:
        for metric in METRICS:
            digits = 3 if metric == 'DSC' else 2
            base = baseline[f'baseline-{metric}-{row["roi"]}']
            gain = changes[f'beneficial-change-{metric}-{row["roi"]}']
            value = row['beneficial_change_' + metric.lower()]
            assert base.get_text() == rounded(row['baseline_' + metric.lower()], digits)
            assert base.get_color() == representative_case.BASELINE_COLOUR
            assert base.xy[0] == 0
            assert gain.get_color() == 'black'
            assert float(gain.get_text()) == pytest.approx(float(rounded(value, digits)))
            assert gain.xy[0] == pytest.approx(value)
    assert len(headers) == 3


def test_ed5_header_uses_after_minus_before_for_distances(data):
    fig, headers = representative_case.compose(data['case'])
    titles = tagged(fig, 'header-after-minus-before-')
    assert len(titles) == 3
    for header in headers:
        metric = header['metric']
        delta = header['after_minus_before']
        assert delta == pytest.approx(header['VAG_UNet_mean'] - header['baseline_mean'])
        assert delta > 0 if metric == 'DSC' else delta < 0
        signed_text = titles['header-after-minus-before-' + metric].get_text().split('Δ ')[1]
        assert signed_text.startswith('+' if metric == 'DSC' else '-')
        assert ('mm' in signed_text) == (metric != 'DSC')
    fig.canvas.draw()
    for artist in [*titles.values(), *tagged(fig, 'baseline-').values(),
                   *tagged(fig, 'beneficial-change-').values()]:
        bounds = artist.get_window_extent(fig.canvas.get_renderer())
        assert bounds.x0 >= 0 and bounds.y0 >= 0
        assert bounds.x1 <= fig.bbox.width and bounds.y1 <= fig.bbox.height
    renderer = fig.canvas.get_renderer()
    footer = tagged(fig, 'ED5-explanatory-footer')['ED5-explanatory-footer']
    axis_labels = [ax.xaxis.label for ax in fig.axes if ax.get_xlabel()]
    assert footer.get_window_extent(renderer).y1 < min(
        label.get_window_extent(renderer).y0 for label in axis_labels)


def test_ed7_keeps_315_values_and_complete_oriented_intervals(data):
    fig, records, axes_info = organ_effects.compose(data['summary_s5'])
    assert len(records) == len(tagged(fig, 'effect-')) == 315
    expected = {(centre, roi, metric) for centre in CENTRES
                for roi in (*SMALL, *LARGE) for metric in METRICS}
    assert {(r['centre'], r['ROI'], r['metric']) for r in records} == expected
    source = {(r['centre'], r['roi'], r['metric']): r for r in data['summary_s5']}
    axes = {(r['panel'], r['category'], r['centre']): r for r in axes_info}
    for record in records:
        original = source[(record['centre'], record['ROI'], record['metric'])]
        sign = 1 if record['metric'] == 'DSC' else -1
        assert record['effect'] == pytest.approx(sign * original['mean_difference'])
        endpoints = sorted((sign * original['ci_lower'], sign * original['ci_upper']))
        assert [record['lower'], record['upper']] == pytest.approx(endpoints)
        axis = axes[(record['panel'], 'small' if record['ROI'] in SMALL else 'large', record['centre'])]
        assert axis['x_min'] < record['lower'] <= record['upper'] < axis['x_max']
    for panel in 'abc':
        for group in ('small', 'large'):
            external_limits = {(r['x_min'], r['x_max']) for r in axes_info
                               if r['panel'] == panel and r['category'] == group
                               and r['centre'] != CENTRES[0]}
            assert len(external_limits) == 1


def test_ed7_uses_final_width_and_no_sub_six_point_text(data):
    fig, _, _ = organ_effects.compose(data['summary_s5'])
    assert fig.get_figwidth() * 25.4 == pytest.approx(183)
    fig.canvas.draw()
    texts = [artist for artist in fig.findobj(Text)
             if artist.get_visible() and artist.get_text().strip()]
    assert texts and min(artist.get_fontsize() for artist in texts) >= 6
    assert any('Small OARs' in artist.get_text() for artist in texts)
    assert any('Large OARs' in artist.get_text() for artist in texts)
    assert sum(artist.get_text().startswith('n = ') for artist in texts) == 15


def test_fig6_quantile_markers_use_interpolated_rank_and_distribution_key(data):
    fig, _, ranked, _ = prospective.compose(data)
    markers = tagged(fig, 'timing-quantile-')
    assert len(markers) == 3
    values = [r['derived_arithmetic_sum_s'] for r in ranked]
    for percentile in (5, 50, 95):
        point = markers[f'timing-quantile-P{percentile}']
        quantile = percentile / 100
        assert point.get_xdata()[0] == pytest.approx(1 + (len(values) - 1) * quantile)
        assert point.get_ydata()[0] == pytest.approx(np.quantile(values, quantile, method='linear'))
    labels = {text.get_text() for legend in fig.legends for text in legend.get_texts()}
    assert {'Median', 'IQR', 'P5–P95'} <= labels


def test_ed4_has_one_panel_b_and_all_paired_observations(data):
    fig, summaries = gtvn_strategies.compose(data['gtvn'])
    panel_letters = [text.get_text() for text in fig.texts if text.get_text() in ('a', 'b', 'c', 'd')]
    assert panel_letters == ['b']
    assert len(fig.axes) == 3 and len(summaries) == 9
    assert sum(len(collection.get_offsets()) for ax in fig.axes for collection in ax.collections) == 12 * 3 * 3
