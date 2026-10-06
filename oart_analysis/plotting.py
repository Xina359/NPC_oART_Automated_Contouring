"""Canonical figure names, exact-size multi-format output and full trace exports."""
from pathlib import Path
from .constants import FIGURES,ALIASES
from .io import write_csv,write_json


def save_figure(fig,stem):
    import matplotlib.pyplot as plt
    stem=Path(stem);stem.parent.mkdir(parents=True,exist_ok=True)
    for ext in ('svg','pdf','png','tiff'):
        kw={'dpi':600 if ext=='tiff' else 300,'bbox_inches':None}
        if ext=='tiff':kw['pil_kwargs']={'compression':'tiff_lzw'}
        fig.savefig(stem.with_suffix('.'+ext),**kw)
    plt.close(fig)


def render(data,figure,output):
    figure=ALIASES.get(figure,figure)
    if figure not in FIGURES: raise ValueError(f'Unknown figure: {figure}')
    directory='ExtendedDataFigure'+figure[2:] if figure.startswith('ED') else 'Figure'+figure
    folder=Path(output)/directory;folder.mkdir(parents=True,exist_ok=True)
    if figure in ('5','ED6'):
        from .figures.comparisons import compose
        fig,records,layout=compose(data['summary_s4'],figure)
        stem='Figure5_bc' if figure=='5' else 'ExtendedDataFigure6_abcd'
        write_csv(records,folder/'plotted_values.csv');write_json(layout,folder/'axis_limits.json')
    elif figure=='6':
        from .figures.prospective import compose
        fig,summaries,ranked,stats=compose(data);stem='Figure6_ab'
        write_csv(data['performance'],folder/'plotted_patient_values.csv');write_csv(summaries,folder/'distribution_summaries.csv')
        write_csv(ranked,folder/'ranked_timing.csv');write_json(stats,folder/'timing_summary.json')
    elif figure=='ED4':
        from .figures.gtvn_strategies import compose
        fig,summary=compose(data['gtvn']);stem='ExtendedDataFigure4_b'
        write_csv(data['gtvn'],folder/'plotted_patient_values.csv');write_csv(summary,folder/'descriptive_summary.csv')
    elif figure=='ED5':
        from .figures.representative_case import compose
        fig,header=compose(data['case']);stem='ExtendedDataFigure5'
        write_csv(data['case'],folder/'plotted_patient_values.csv');write_csv(header,folder/'header_means.csv')
    else:
        from .figures.organ_effects import compose
        fig,records,layout=compose(data['summary_s5']);stem='ExtendedDataFigure7_abc'
        write_csv(records,folder/'plotted_values.csv');write_json(layout,folder/'axis_limits.json')
    save_figure(fig,folder/stem)
    write_json({'figure':figure,'panels':{'5':'b,c','6':'a,b','ED4':'b only (three internal metric plots)','ED5':'whole quantitative figure','ED6':'a-d','ED7':'a-c'}[figure],
        'clinical_images_or_proprietary_models_reproduced':False,'layout':'numerical panel layout, not a pixel-identical copy of manuscript artwork',
        'source_policy':'archived plotting summaries/available patient endpoints; all plotted data exported'},folder/'figure_scope.json')
    return folder
