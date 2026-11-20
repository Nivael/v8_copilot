"""Describe confirmation lag for all six first hits; never assume executable signal close."""
from pathlib import Path
from hashlib import sha256
from decimal import Decimal as D
import json,gzip
from long_breadth_st_alignment import analyze,INPUT,INPUT_SHA
from st_regime_comparison import build


def analyze_cost():
    path=Path('LONG_BREADTH_ST_ALIGNMENT_EVIDENCE_2026_11_21.json');source=json.loads(path.read_text())
    if analyze()!=source:raise ValueError('alignment replay differs')
    raw=INPUT.read_bytes()
    if sha256(raw).hexdigest()!=INPUT_SHA:raise ValueError('ST input changed')
    m=json.loads(gzip.decompress(raw))['current_extension']['market_inputs'];daily=build(m)['daily'];byday={r['date']:r for r in daily};rows=[]
    for signal in source['reading']['signals']:
        before=signal['three_closes'];anchor=byday[before[0]]['anchor']
        if any(byday[d]['anchor']!=prev for d,prev in zip(before,[anchor]+before[:-1])):raise ValueError('confirmation chain differs')
        def compound(days,key):
            v=D(1)
            for day in days:
                r=byday[day]
                if r['missing']or r['observed_count']<=0:raise ValueError('ST coverage unresolved')
                v*=1+D(str(r[key]))/100
            return (v-1)*100
        st=compound(before,'return_pct');mk=compound(before,'market_pct');after=signal['following_dates']
        for key,old in [('return_pct',signal['st_pct']),('market_pct',signal['market_pct'])]:
            if abs(float(compound(after,key))-old)>1e-10:raise ValueError('following window differs')
            a=compound(before,key);b=compound(after,key);whole=compound(before+after,key)
            if abs((1+a/100)*(1+b/100)*100-100-whole)>D('1e-20'):raise ValueError('compound bridge differs')
        rows.append(dict(signal_date=signal['date'],anchor=anchor,confirmation_dates=before,already_st_pct=float(st),already_market_pct=float(mk),following_through=signal['through'],following_sessions=len(after),complete_five=signal['complete_five'],following_st_pct=signal['st_pct'],following_market_pct=signal['market_pct']))
    return dict(version='long_confirmation_cost_v1',alignment_sha256=sha256(path.read_bytes()).hexdigest(),input_asset_sha256=INPUT_SHA,reading=dict(rows=rows,signal_count=len(rows)),limits=['Confirmation-window returns are already realized by third close, not advance warning','Not account loss, opportunity cost or executed strategy return','Earlier warning may avoid loss or miss rebounds; no optimal waiting rule inferred','Before/after percentages compound, never simply add'])


if __name__=='__main__':
    e=analyze_cost();Path('LONG_CONFIRMATION_COST_EVIDENCE_2026_11_21.json').write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n');print(json.dumps(e['reading'],ensure_ascii=False,indent=2))
