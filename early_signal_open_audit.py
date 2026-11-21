"""Reconcile earlier signal next-opens across saved raw daily and public OHLC."""
from pathlib import Path
from hashlib import sha256
from decimal import Decimal as D
import gzip,json
from canonical_json import digest
from long_breadth_st_alignment import INPUT,INPUT_SHA
from long_signal_next_close import analyze as signal_replay
from st_stock_price_crosscheck import SUBJECTS,quotes_from_source,price_scope_digest


def analyze():
    raw=INPUT.read_bytes()
    if sha256(raw).hexdigest()!=INPUT_SHA:raise ValueError('frozen source differs')
    inputs=json.loads(gzip.decompress(raw));packet=inputs['stock_price_crosscheck']
    if packet['content_digest']!=digest({k:v for k,v in packet.items() if k!='content_digest'}) or packet['price_scope_digest']!=price_scope_digest(inputs):raise ValueError('quote scope differs')
    source=Path('LONG_SIGNAL_NEXT_CLOSE_EVIDENCE_2026_11_21.json');signals=json.loads(source.read_text())
    if signal_replay()!=signals:raise ValueError('signal chronology differs')
    signals=[r for r in signals['rows'] if r['next_close']<=inputs['through']]
    if len(signals)!=5:raise ValueError('earlier-signal scope differs')
    public={};refs=[]
    for ref in packet['sources']:
        if ref['key']!='tencent_raw':continue
        quotes_from_source(ref)
        if ref['symbol'] in public or json.loads(ref['raw_text']).get('code')!=0:raise ValueError('duplicate or failed public quote')
        ticker=('sh' if ref['symbol'].startswith('6') else 'sz')+ref['symbol']
        items=json.loads(ref['raw_text'])['data'][ticker]['day']
        public[ref['symbol']]={r[0]:dict(open=r[1],close=r[2],high=r[3],low=r[4]) for r in items}
        refs.append({k:ref[k] for k in ('symbol','key','url','sha256','observed_at')})
    if set(public)!=set(SUBJECTS):raise ValueError('five raw quote identities differ')
    original={c['symbol']:{r['date']:r for r in c['rows']} for c in packet['original_prices']['companies']};rows=[];primary_refs=[]
    for signal in signals:
        day=signal['next_close'];ref=next(r for r in packet['original_prices']['source_refs'] if r['api']=='daily' and r['trade_date']==day)
        raw=gzip.decompress(Path(ref['response_asset']).read_bytes())
        if sha256(raw).hexdigest()!=ref['response_sha256']:raise ValueError('primary raw daily differs')
        response=json.loads(raw)
        if response['code']!=0:raise ValueError('daily source failed')
        fields=response['data']['fields'];items=response['data']['items'];daily={}
        for item in items:
            q=dict(zip(fields,item,strict=True))
            if q['trade_date']!=day.replace('-','') or q['ts_code'] in daily:raise ValueError('daily identity/date differs')
            daily[q['ts_code']]=q
        primary_refs.append(ref)
        for symbol,label in SUBJECTS.items():
            code=symbol+('.SH' if symbol.startswith('6') else '.SZ');q=daily.get(code);other=public[symbol].get(day);base=original[symbol][day]
            if not base['has_trade']:
                if other or (q and D(str(q['vol']))>0):raise ValueError('nontrade conflicts with quote')
                rows.append(dict(signal_date=signal['signal_date'],next_session=day,symbol=code,label=label,status='no_trade_in_original',suspension_records=base['suspension_records']));continue
            if not q or not other or D(str(q['vol']))<=0:raise ValueError('required traded quote missing')
            p={k:D(str(q[k])) for k in ('open','high','low','close','pre_close')}
            if any(not v.is_finite() or v<=0 for v in p.values()) or not p['low']<=min(p['open'],p['close'])<=max(p['open'],p['close'])<=p['high']:raise ValueError('invalid OHLC')
            if any(p[k]!=D(other[k]) for k in ('open','high','low','close')):raise ValueError('raw OHLC channels conflict')
            if p['close']!=D(str(base['raw_close'])):raise ValueError('original raw close conflict')
            rows.append(dict(signal_date=signal['signal_date'],next_session=day,symbol=code,label=label,status='two_channel_ohlc_match',**{k:str(q[k]) for k in p},open_vs_reference_pct=float((p['open']/p['pre_close']-1)*100),one_price_day=len({p[k] for k in ('open','high','low','close')})==1,actual_limits_status='not_replayed_here'))
    return dict(version='early_signal_open_audit_v1',input_asset_sha256=INPUT_SHA,signal_evidence_sha256=sha256(source.read_bytes()).hexdigest(),raw_public_sources=refs,primary_daily_sources=primary_refs,rows=rows,summary=dict(signal_count=len(signals),positions=len(rows),matched=sum(r['status']=='two_channel_ohlc_match' for r in rows),nontrading=sum(r['status']=='no_trade_in_original' for r in rows)),limits=['Five pre-existing comparison identities, not then-ST membership or a representative portfolio', 'Raw OHLC equality across two quote channels does not establish independent underlying feeds', 'This pass does not replay actual daily upper/lower limits, queues or individual order fills', 'Open change uses the primary same-day pre-close reference, not necessarily unadjusted prior actual close', 'All sources retrieved retrospectively; no proof of realtime availability or strategy efficacy'])


if __name__=='__main__':
    e=analyze();Path('EARLY_SIGNAL_OPEN_AUDIT_EVIDENCE_2026_11_21.json').write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(summary=e['summary'],rows=e['rows']),ensure_ascii=False,indent=2))
