"""Fig. 6: prospective contour agreement and recorded timing."""
import math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from .common import setup,panel_label
from ..statistics import describe
from ..display import rounded
from ..constants import METRICS

ORDER=('GTVp','CTV1','CTV2','GTVn','Large OARs','Small OARs')
def compose(data):
    setup();fig=plt.figure(figsize=(8.2,7.3));grid=fig.add_gridspec(2,3,left=.20,right=.97,top=.89,bottom=.15,hspace=.67,height_ratios=(1,1.12),wspace=.35)
    fig.legend(handles=[
        Line2D([],[],marker='o',mfc='white',mec='.25',ls='none',ms=4,label='Median'),
        Line2D([],[],color='.25',lw=4,label='IQR'),
        Line2D([],[],color='.55',lw=1.2,label='P5–P95')],
        loc='center',bbox_to_anchor=(.62,.923),ncol=3,fontsize=6.5,frameon=False)
    summaries=[]
    for k,metric in enumerate(METRICS):
        ax=fig.add_subplot(grid[0,k])
        for y,category in enumerate(ORDER):
            v=[r['value'] for r in data['performance'] if r['category']==category and r['metric']==metric];s=describe(v)
            summaries.append({'category':category,'metric':metric,**s});colour='#3878A3' if category.startswith(('GTV','CTV')) else '#4E9264'
            ax.plot([s['p5'],s['p95']],[y,y],color=colour,alpha=.4,lw=1.2)
            ax.plot([s['q1'],s['q3']],[y,y],color=colour,lw=4)
            ax.plot(s['median'],y,'o',ms=4,mfc='white',mec=colour,lw=.5)
        ax.set_ylim(5.5,-.5);ax.set_yticks(range(6));ax.set_yticklabels([c.replace('OARs','OAR composite') for c in ORDER] if k==0 else [])
        ax.set_xlabel(metric+(' (mm)' if metric!='DSC' else ''));ax.grid(axis='x',alpha=.15)
        if k==0:panel_label(ax,'a')
    ax=fig.add_subplot(grid[1,:]);ranked=[]
    for rank,r in enumerate(sorted(data['timing'],key=lambda r:(r['algorithm_s']+r['review_s'],r['study_id'])),1):
        ranked.append({**r,'rank':rank,'derived_arithmetic_sum_s':r['algorithm_s']+r['review_s']})
    rank=[r['rank'] for r in ranked];a=np.array([r['algorithm_s'] for r in ranked]);b=np.array([r['review_s'] for r in ranked]);combined=a+b
    ax.stackplot(rank,a,b,colors=('#67A8AE','#DEB67D'),labels=('Algorithm interval','Review/modification interval'),alpha=.85)
    ax.plot(rank,combined,color='.25',lw=1.0,label='Arithmetic sum')
    ax.set_xlabel('Patient rank by arithmetic sum (not chronological order)');ax.set_ylabel('Recorded interval (s)')
    ax.set_xlim(1,135);ax.set_ylim(0,float(max(combined))*1.13);ax.set_xticks((1,34,68,101,135));panel_label(ax,'b')
    ax.set_title('Recorded intervals and their arithmetic sum',loc='left',pad=22,fontweight='bold')
    ts={name:describe(v) for name,v in (('algorithm',a),('review',b),('arithmetic_sum',combined))}
    for x,(name,label) in zip((.00,.34,.75),(('algorithm','Algorithm'),('review','Review/modification'),('arithmetic_sum','Sum'))):
        s=ts[name];ax.text(x,1.025,f"{label}: {rounded(s['mean'],0)} ± {rounded(s['sd'],0)} s",transform=ax.transAxes,fontsize=7)
    ax.legend(loc='upper left',fontsize=6.5,ncol=1)
    for q,label in ((.05,'P5'),(.5,'P50'),(.95,'P95')):
        value=float(np.quantile(combined,q,method='linear'))
        pos=1+(len(combined)-1)*q
        point,=ax.plot(pos,value,'o',ms=3,mfc='white',mec='.25',mew=.7,zorder=5)
        point.set_gid('timing-quantile-'+label)
        ax.annotate(f'{label} {rounded(value,0)} s',(pos,value),xytext=(0,-13),textcoords='offset points',ha='center',fontsize=6)
    fig.suptitle('Prospective contour agreement and recorded timing (n = 135)',fontsize=10,y=.96)
    fig.text(.20,.04,'a: Median, IQR and P5–P95 describe patient distributions, not confidence intervals.\n'
        'b: Arithmetic sum = algorithm interval + review/modification interval.',fontsize=7,linespacing=1.4)
    return fig,summaries,ranked,ts
