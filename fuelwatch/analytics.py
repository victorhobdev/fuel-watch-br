"""Contrato analitico: calculo decimal, elegibilidade e fingerprints tipados."""
from decimal import Decimal, ROUND_HALF_UP
import hashlib,json
from statistics import median

SIX=Decimal('0.000001')

def decimal_median(values):
    values=[Decimal(str(x)) for x in values]
    if not values: return None
    return median(values).quantize(SIX,rounding=ROUND_HALF_UP)

def relative_difference(value,reference,eligible):
    if not eligible or reference is None or Decimal(str(reference))<=0:return None
    return ((Decimal(str(value))-Decimal(str(reference)))/Decimal(str(reference))*100).quantize(SIX,rounding=ROUND_HALF_UP)

def row_hash(values,kinds):
    normalized=[]
    for value,kind in zip(values,kinds):
        if value is None or (kind!='str' and str(value) in {'nan','NaT','<NA>'}):normalized.append(None)
        elif kind=='decimal':normalized.append(str(Decimal(str(value)).quantize(SIX,rounding=ROUND_HALF_UP)))
        elif kind=='date':normalized.append(str(value)[:10])
        elif kind in {'int','bool'}:normalized.append(str(int(value)))
        else:normalized.append(str(value))
    return hashlib.sha256(json.dumps(normalized,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
