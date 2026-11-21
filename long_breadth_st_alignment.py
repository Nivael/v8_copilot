"""Full-window first hits, with same following ST/market days and dated source controls."""
from pathlib import Path
from hashlib import sha256
from datetime import date
from decimal import Decimal as D,ROUND_HALF_UP
import gzip,json
from canonical_json import digest
from market_calendar import sessions_2026
from st_regime_comparison import build
INPUT=Path('/Volumes/Leibniz/dev/st_research/local_data/v8_copilot/market_risk/st_regime_comparison/inputs-93929179971e89fd4787986afd0d891bfde54971c7a31faa33aa3cc2b22c57f9.json.gz')
INPUT_SHA='77ece10df1b70da14007a415b6564bc70c4628d413c8be116771b8c41b5ca292'


def analyze():
    raw=INPUT.read_bytes()
    if sha256(raw).hexdigest()!=INPUT_SHA:raise ValueError('ST input changed')
    inputs=json.loads(gzip.decompress(raw));m=inputs['current_extension']['market_inputs'];daily=build(m)['daily'];byday={r['date']:r for r in daily}
    source=next(s for s in inputs['initial_twentyseventh_four']['cross_sources']if s['key']=='000985')
    if sha256(source['text'].encode()).hexdigest()!=source['sha256']:raise ValueError('official index bytes changed')
    official={r['tradeDate']:D(str(r['close']))for r in json.loads(source['text'])['data']};market={r['trade_date'].replace('-',''):D(str(r['close']))for r in m['benchmarks']if r['benchmark_id']=='csi_all_share'}
    dates=sessions_2026(date(2026,7,3),date(2026,11,19))
    if sorted(official)!=[d.replace('-','')for d in dates]:raise ValueError('index control calendar differs')
    if any(market[d].quantize(D('.01'),rounding=ROUND_HALF_UP)!=v for d,v in official.items()):raise ValueError('index price conflict')
    for day in dates:
        r=byday[day]
        if r['missing']or r['observed_count']<=0:raise ValueError('ST coverage unresolved')
    bp=Path('LONG_MARKET_BREADTH_EVIDENCE_2026_11_21.json');breadth=json.loads(bp.read_text());claimed=breadth.pop('content_digest')
    if digest(breadth)!=claimed:raise ValueError('breadth content changed')
    if [p['date']for p in breadth['points']]!=sessions_2026(date(2026,7,1),date(2026,11,20)):raise ValueError('breadth dates differ')
    for file,key in breadth['source_sha256'].items():
        if sha256(Path(file).read_bytes()).hexdigest()!=key:raise ValueError('breadth source binding changed')
    streak=0;signals=[];days=[]
    for point in breadth['points']:
        a=point['all'];n=a['observed_trading_stocks'];up=a['advancing'];streak=streak+1 if up*2<n else 0
        days.append(dict(date=point['date'],trading=n,advancing=up,streak=streak))
        if streak!=3:continue
        day=point['date'];i=dates.index(day);after=dates[i+1:i+6]
        def compound(key):
            value=D(1)
            for d in after:value*=1+D(str(byday[d][key]))/100
            return float((value-1)*100)if after else None
        st=compound('return_pct');mk=compound('market_pct');full=len(after)==5;end=after[-1]if after else day
        official_change=float((official[end.replace('-','')]/official[day.replace('-','')]-1)*100)if after else None
        if mk is not None and abs(mk-official_change)>.002:raise ValueError('market window conflicts with official endpoints')
        signals.append(dict(date=day,three_closes=[d['date']for d in days[-3:]],following_dates=after,through=end,complete_five=full,observed_following_sessions=len(after),st_pct=st,market_pct=mk,official_rounded_market_pct=official_change,st_minus_market_pp=st-mk if st is not None else None))
    return dict(version='long_breadth_st_alignment_v1',breadth_sha256=sha256(bp.read_bytes()).hexdigest(),input_asset=str(INPUT),input_asset_sha256=INPUT_SHA,index_source={k:source[k]for k in ['url','sha256']if k in source},reading=dict(breadth_start='2026-07-01',breadth_through='2026-11-20',breadth_days=97,common_start=dates[0],common_through=dates[-1],common_days=len(dates),official_index_dates=len(official),signal_count=len(signals),complete_signal_count=sum(s['complete_five']for s in signals),partial_signal_count=sum(not s['complete_five']for s in signals),signals=signals,days=days),limits=['First hit only on third weak close, no parameter optimization','Complete 5-day and partial 3-day outcomes stay separate','More historical intervals are not independent policy experiments or strategy validation','Dynamic ST reference compounds daily changing groups; no account or executable portfolio claim','Official index controls have two-decimal precision; source return calculation retained separately'])


if __name__=='__main__':
    e=analyze();Path('LONG_BREADTH_ST_ALIGNMENT_EVIDENCE_2026_11_21.json').write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n');print(json.dumps(e['reading']['signals'],ensure_ascii=False,indent=2))
