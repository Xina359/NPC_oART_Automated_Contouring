"""Extended Data Fig. 4b: three metric plots within ONE manuscript panel.

There are no formal ED4c/d panels; the separate clinical image panel ED4a is
not created by this quantitative plotting module.
"""
import numpy as np
import matplotlib.pyplot as plt
from .common import setup
from ..constants import STRATEGIES,METRICS
from ..statistics import describe
from ..display import rounded

def compose(rows):
    setup();patients=sorted({r['Study ID'] for r in rows});values={(r['Study ID'],r['Strategy'],r['Metric']):r['Value'] for r in rows}
    fig,axes=plt.subplots(1,3,figsize=(8.3,3.2));fig.subplots_adjust(left=.075,right=.98,bottom=.27,top=.77,wspace=.36)
    offsets=np.linspace(-.11,.11,len(patients));summaries=[];colours=('#627185','#B7935A','#377CA8')
    for ax,metric in zip(axes,METRICS):
        data=[np.array([values[(p,s,metric)] for p in patients]) for s in STRATEGIES]
        for i,p in enumerate(patients):
            ax.plot(np.arange(1,4)+offsets[i],[values[(p,s,metric)] for s in STRATEGIES],color='.65',lw=.5,alpha=.4)
        boxes=ax.boxplot(data,positions=(1,2,3),widths=.50,whis=1.5,showfliers=False,patch_artist=True)
        for patch,c in zip(boxes['boxes'],colours):patch.set_facecolor(c);patch.set_alpha(.25)
        low=min(v.min() for v in data);high=max(v.max() for v in data);span=max(high-low,.01)
        ax.set_ylim(low-span*.10,high+span*.28)
        for j,(v,c,strategy) in enumerate(zip(data,colours,STRATEGIES),1):
            ax.scatter(j+offsets,v,s=14,color=c,edgecolors='white',linewidths=.3,zorder=3)
            s=describe(v);summaries.append({'Strategy':strategy,'Metric':metric,**s})
            ax.text(j,high+span*.12,f"{rounded(s['mean'],2)} ± {rounded(s['sd'],2)}",ha='center',color=c,fontsize=7)
        ax.set_title(metric+(' (mm)' if metric!='DSC' else ''),pad=9)
        ax.set_xticks((1,2,3),('Baseline','DIR','PCG-UNet'),rotation=23,ha='right');ax.grid(axis='y',alpha=.15)
    fig.text(.018,.92,'b',weight='bold',fontsize=11)
    fig.text(.075,.92,'GTVn strategies: 12 paired patients',fontsize=9)
    fig.text(.075,.055,'All three plots belong to Extended Data Fig. 4b. Labels: mean ± sample s.d.\nNo new hypothesis tests are added; all observations are shown.',fontsize=7)
    return fig,summaries
