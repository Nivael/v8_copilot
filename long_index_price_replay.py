"""Merge retained official CSI closes without replacing higher-precision studies."""
from pathlib import Path
from hashlib import sha256
from decimal import Decimal as D
import gzip,json,statistics,math
from canonical_json import digest

ROOT=Path('/Volumes/Leibniz/dev/st_research/local_data/v8_copilot/market_risk')


def derive(rows):
    result=[]
    for i,row in enumerate(rows):
        closes=[D(str(r['close']))for r in rows[:i+1]]
        if any(not c.is_finite() or c<=0 for c in closes):raise ValueError('invalid close')
        change=lambda n:float((closes[-1]/closes[-1-n]-1)*100)if len(closes)>n else None
        peak=max(closes[-20:]) if len(closes)>=20 else None
        returns=[float(closes[j]/closes[j-1]-1)for j in range(len(closes)-20,len(closes))]if len(closes)>=21 else None
        result.append(dict(date=row['date'],close=float(closes[-1]),day_pct=change(1),five_day_pct=change(5),twenty_day_pct=change(20),from_twenty_close_high_pct=float((closes[-1]/peak-1)*100)if peak else None,twenty_day_realized_annualized_pct=statistics.stdev(returns)*math.sqrt(252)*100 if returns else None))
    return result


def build():
    alignment=json.loads(Path('LONG_BREADTH_ST_ALIGNMENT_EVIDENCE_2026_11_21.json').read_text());raw=Path(alignment['input_asset']).read_bytes()
    if sha256(raw).hexdigest()!=alignment['input_asset_sha256']:raise ValueError('frozen input changed')
    source=next(s for s in json.loads(gzip.decompress(raw))['initial_twentyseventh_four']['cross_sources']if s['key']=='000985')
    if sha256(source['text'].encode()).hexdigest()!=alignment['index_source']['sha256']:raise ValueError('frozen official source changed')
    july=json.loads(Path('JULY_INDEX_CONTROL_SOURCE_2026_11_21.json').read_text());jr=(Path(july['source_store'])/(july['response_sha256']+'.json')).read_bytes()
    if sha256(jr).hexdigest()!=july['response_sha256'] or len(jr)!=july['bytes']:raise ValueError('July source changed')
    latest=json.loads(Path('MARKET_PRICE_CONTEXT_EVIDENCE_2026_11_21.json').read_text());ref=next(s for s in latest['sources']if s['code']=='000985.CSI');lr=(ROOT/'trader_observations/latest_index/responses'/(ref['response_sha256']+'.json')).read_bytes()
    if sha256(lr).hexdigest()!=ref['response_sha256']:raise ValueError('latest source changed')
    sources=[dict(url=source['url'],sha256=alignment['index_source']['sha256']),dict(url=july['url'],sha256=july['response_sha256']),dict(url=ref['url'],sha256=ref['response_sha256'])]
    prices={};overlaps=0
    for body in [json.loads(source['text']),json.loads(jr),json.loads(lr)]:
        if body['code']!='200' or body['success'] is not True:raise ValueError('official response failed')
        seen=set()
        for r in body['data']:
            if r['indexCode']!='000985' or r['tradeDate'] in seen:raise ValueError('official identity/date conflict')
            seen.add(r['tradeDate']);day=r['tradeDate'];value=D(str(r['close']))
            if day in prices:
                if prices[day]!=value:raise ValueError('overlap price conflict')
                overlaps+=1
            prices[day]=value
    breadth=json.loads(Path('web/src/longBreadthReplay.json').read_text());dates=[r['date']for r in breadth['rows']]
    if sorted(prices)!=[d.replace('-','')for d in dates]:raise ValueError('97-session price coverage differs')
    rows=[dict(date=d,close=float(prices[d.replace('-','')]))for d in dates]
    e=dict(version='official_csi_daily_price_replay_v1',breadth_sha256=breadth['evidence_sha256'],sources=sources,overlapping_closes_matched=overlaps,rows=derive(rows),limits=['Official closes have two-decimal precision; existing higher precision studies unchanged','Returns require n+1 closes; unavailable early windows remain null','20-close high is a rolling closing reference, not intraday high or maximum drawdown','20 daily simple returns sample standard deviation annualized with sqrt(252), descriptive not forecast','Sources observed retrospectively; no historical real-time availability or executable-price claim'])
    e['content_digest']=digest(e);return e


if __name__=='__main__':
    e=build();Path('LONG_INDEX_PRICE_REPLAY_EVIDENCE_2026_11_21.json').write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n');print(dict(days=len(e['rows']),overlaps=e['overlapping_closes_matched'],latest=e['rows'][-1]))
