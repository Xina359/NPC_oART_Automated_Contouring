"""Shared figure styling, complete interval limits and beneficial effect signs."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from ..constants import GROUP_LABELS
from ..statistics import orient_effect

COLOURS=('#30343B','#377CA8','#4E8A66','#89618D','#BE8A51')
SHORT={GROUP_LABELS['Small OARs']:'Small-OAR composite',GROUP_LABELS['Large OARs']:'Large-OAR composite',
       'Eustachian tube bone':'Eustachian tube bone','Internal auditory canal':'Internal auditory canal',
       'Temporomandibular joint':'Temporomandibular joint','Vestibule/semicircular canals':'Vestibule/semicircular canals'}

def setup():
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Helvetica','DejaVu Sans'],
        'font.size':7,'axes.labelsize':7,
        'axes.titlesize':8,'xtick.labelsize':6,'ytick.labelsize':6,'axes.linewidth':.6,
        'axes.spines.top':False,'axes.spines.right':False,'legend.frameon':False,
        'svg.fonttype':'none','pdf.fonttype':42,'savefig.facecolor':'white','savefig.bbox':None})

def effect(row):
    return orient_effect(row['mean_difference'],row['ci_lower'],row['ci_upper'],row['metric'])

def limits(values,positive=False):
    arr=np.asarray(values,float)
    if not len(arr) or not np.isfinite(arr).all(): raise ValueError('Invalid plotting limits')
    lo=min(0,float(arr.min())) if positive else float(arr.min());hi=float(arr.max())
    margin=max((hi-lo)*.10,.001)
    return (0 if positive and lo==0 else lo-margin,hi+margin)

def panel_label(ax,letter):
    ax.text(-.06,1.08,letter,transform=ax.transAxes,fontweight='bold',fontsize=10,va='bottom')
