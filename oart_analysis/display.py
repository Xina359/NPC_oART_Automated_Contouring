"""Exact decimal quantiles and final display rounding.

Display rounding is applied once and never used for hypothesis testing."""
from decimal import Decimal, ROUND_HALF_UP, localcontext
from .statistics import numeric_vector

def rounded(value, digits=3):
    if not isinstance(digits,int) or not 0<=digits<=12: raise ValueError('digits must be an integer in [0,12]')
    with localcontext() as ctx:
        ctx.prec=40
        d=Decimal(str(value)).quantize(Decimal(1).scaleb(-digits),rounding=ROUND_HALF_UP)
        if not d: d=abs(d)
        return format(d,f'.{digits}f')

def decimal_quantile(values,q):
    numeric_vector(values)
    q=Decimal(str(q))
    if not 0<=q<=1: raise ValueError('Quantile must be in [0,1]')
    x=sorted(Decimal(str(v)) for v in values)
    h=(len(x)-1)*q;i=int(h);r=h-i
    return x[i] if i==len(x)-1 else x[i]*(1-r)+x[i+1]*r

def quantile_display(values,q,digits=3):
    return rounded(decimal_quantile(values,q),digits)
