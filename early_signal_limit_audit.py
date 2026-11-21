"""Pair the earlier five-stock opening observations with retained actual limits."""
from pathlib import Path
from hashlib import sha256
from decimal import Decimal as D
import gzip,json
from long_breadth_st_alignment import INPUT,INPUT_SHA
from early_signal_open_audit import analyze as replay_ohlc
STORE=Path('/Volumes/Leibniz/dev/st_research/local_data/v8_copilot/market_risk/st_regime_acquisition/20261109')


def analyze():
    source=Path('EARLY_SIGNAL_OPEN_AUDIT_EVIDENCE_2026_11_21.json');old=json.loads(source.read_text())
    if replay_ohlc()!=old:raise ValueError('earlier OHLC replay differs')
    raw=INPUT.read_bytes()
    if sha256(raw).hexdigest()!=INPUT_SHA:raise ValueError('input differs')
    inputs=json.loads(gzip.decompress(raw));dates=sorted({r['next_session'] for r in old['rows']});tables={};refs=[]
    fields='trade_date,ts_code,pre_close,up_limit,down_limit'
    for day in dates:
        selected=[r for r in inputs['refresh_provenance']['original_source_refs'] if r['query']['api_name']=='stk_limit' and r['query']['params']=={'trade_date':day.replace('-','')}]
        if len(selected)!=1:raise ValueError('limit capture absent or ambiguous')
        ref=selected[0]
        receipt=STORE/'queries'/(ref['query_id']+'.json')
        if json.loads(receipt.read_text())!=ref or ref['query']['fields']!=fields:raise ValueError('limit receipt differs')
        original=gzip.decompress((STORE/'responses'/(ref['response_sha256']+'.json.gz')).read_bytes())
        if len(original)!=ref['bytes'] or sha256(original).hexdigest()!=ref['response_sha256']:raise ValueError('limit original differs')
        response=json.loads(original)
        if response['code']!=0 or response['data']['fields']!=fields.split(','):raise ValueError('limit response failed or changed')
        rows={}
        for item in response['data']['items']:
            row=dict(zip(fields.split(','),item,strict=True));code=row['ts_code']
            if code in rows or row['trade_date']!=day.replace('-',''):raise ValueError('limit identity/date differs')
            rows[code]=row
        tables[day]=rows;refs.append(dict(ref,receipt_sha256=sha256(receipt.read_bytes()).hexdigest()))
    rows=[]
    for previous in old['rows']:
        row=dict(previous);limit=tables[row['next_session']].get(row['symbol'])
        if previous['status']!='two_channel_ohlc_match':row['limit_status']='nontraded_not_paired'
        elif not limit:row['limit_status']='limit_row_missing'
        else:
            p={k:D(row[k]) for k in ('open','high','low','close','pre_close')};l={k:D(str(limit[k])) for k in ('up_limit','down_limit','pre_close')}
            if any(not v.is_finite() or v<=0 for v in l.values()) or p['pre_close']!=l['pre_close'] or not l['down_limit']<=p['low']<=min(p['open'],p['close'])<=max(p['open'],p['close'])<=p['high']<=l['up_limit']:raise ValueError('OHLC and limits conflict')
            row.update(limit_status='paired',down_limit=str(limit['down_limit']),up_limit=str(limit['up_limit']),open_at_lower=p['open']==l['down_limit'],touched_lower=p['low']==l['down_limit'],close_at_lower=p['close']==l['down_limit'],one_price_lower=all(p[k]==l['down_limit'] for k in ('open','high','low','close')))
        row['actual_limits_status']=row['limit_status']
        rows.append(row)
    paired=[r for r in rows if r['limit_status']=='paired']
    return dict(version='early_signal_limit_audit_v1',input_asset_sha256=INPUT_SHA,early_ohlc_evidence_sha256=sha256(source.read_bytes()).hexdigest(),signal_evidence_sha256=old['signal_evidence_sha256'],sources=refs,rows=rows,summary=dict(positions=len(rows),paired=len(paired),unresolved=len(rows)-len(paired),open_at_lower=sum(r['open_at_lower'] for r in paired),touched_lower=sum(r['touched_lower'] for r in paired),close_at_lower=sum(r['close_at_lower'] for r in paired),one_price_lower=sum(r['one_price_lower'] for r in paired)),limits=['Actual provider limits are replayed, not inferred from a uniform price percentage','Only five comparison identities on five selected dates, not ST or market-wide counts','Raw OHLC matched two quote channels; lower/upper limits remain a single provider source','All sources retrieved retrospectively, no then-available or order-execution certification','Five dates and 25 positions are not 25 independent strategy validations'])


if __name__=='__main__':
    e=analyze();Path('EARLY_SIGNAL_LIMIT_AUDIT_EVIDENCE_2026_11_21.json').write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(summary=e['summary'],hits=[r for r in e['rows'] if r.get('touched_lower')]),ensure_ascii=False,indent=2))
