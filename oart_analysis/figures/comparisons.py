"""Numerical panels: Fig. 5b,c and Extended Data Fig. 6a-d."""
import numpy as np
import matplotlib.pyplot as plt
from .common import setup,COLOURS,SHORT,effect,limits,panel_label
from ..constants import CENTRES,ENDPOINTS

def compose(rows,figure):
    setup();specs=[('b','DSC','means'),('c','DSC','effects')] if figure=='5' else [
        ('a','HD95','means'),('b','HD95','effects'),('c','ASD','means'),('d','ASD','effects')]
    fig,axes=plt.subplots(len(specs),5,figsize=(9.5,2.55*len(specs)),squeeze=False)
    fig.subplots_adjust(left=.23,right=.985,bottom=.18 if figure=='5' else .08,top=.90 if figure=='5' else .95,hspace=.65,wspace=.24)
    plotted=[];axis_meta=[]
    for i,(letter,metric,kind) in enumerate(specs):
        for j,centre in enumerate(CENTRES):
            ax=axes[i,j];subset={r['roi']:r for r in rows if r['centre']==centre and r['metric']==metric}
            xs=[];colour=COLOURS[j]
            for y,roi in enumerate(ENDPOINTS):
                r=subset[roi];marker='s' if j==0 else 'o'
                if kind=='means':
                    x0,x1=r['before_mean'],r['after_mean'];xs.extend((x0,x1))
                    ax.plot([x0,x1],[y,y],color=colour,alpha=.5,lw=.8)
                    ax.plot(x0,y,marker=marker,ms=4,mfc='white',mec=colour)
                    ax.plot(x1,y,marker=marker,ms=4,mfc=colour,mec=colour)
                    plotted.append({'panel':letter,'centre':centre,'ROI':roi,'metric':metric,'kind':kind,
                        'before_mean':x0,'after_mean':x1,'effect':None,'lower':None,'upper':None})
                else:
                    x,lo,hi=effect(r);xs.extend((0,lo,hi))
                    ax.plot([lo,hi],[y,y],color=colour,lw=1)
                    ax.plot(x,y,marker=marker,ms=4,color=colour)
                    plotted.append({'panel':letter,'centre':centre,'ROI':roi,'metric':metric,'kind':kind,
                        'before_mean':None,'after_mean':None,'effect':x,'lower':lo,'upper':hi})
            ax.set_ylim(len(ENDPOINTS)-.5,-.5);ax.set_yticks(range(len(ENDPOINTS)))
            ax.set_yticklabels([SHORT.get(r,r) for r in ENDPOINTS] if j==0 else [])
            if j==0: panel_label(ax,letter)
            ax.set_title(centre,fontsize=7,color=colour)
            label=metric if kind=='means' else ('DSC gain' if metric=='DSC' else metric+' reduction')
            ax.set_xlabel(label+(' (mm)' if metric!='DSC' else ''))
            lo,hi=limits(xs);ax.set_xlim(lo,hi);ax.tick_params(length=2);ax.grid(axis='y',alpha=.13)
            if kind=='effects':ax.axvline(0,color='.55',lw=.7,zorder=0)
            axis_meta.append({'panel':letter,'centre':centre,'x_min':lo,'x_max':hi,'all_values_and_CIs_retained':True})
    fig.suptitle('Five-centre offline DSC evaluation' if figure=='5' else 'Five-centre surface-distance agreement and changes',fontsize=10,y=.985)
    fig.text(.23,.025 if figure=='5' else .012,
        'Open: comparator / pre-adaptation     Filled: locked / adapted\n'
        'Effects: positive favours locked/adapted; bars are pointwise 95% CIs.\n'
        'Main: GTVs n = 12; CTVs/OARs n = 29. Centres I/II/III/IV: n = 14/21/14/25.',fontsize=6.5)
    return fig,plotted,axis_meta
