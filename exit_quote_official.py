"""Classify available source responses without manufacturing missing endpoints."""
import json
from hashlib import sha256
from decimal import Decimal as D

def verify(e):
 if {s['symbol']for s in e['sources']}!={'000016','002717','002731','600491'}:raise ValueError('four-subject identities changed')
 result=[]
 for s in e['sources']:
  code=s['symbol'];ref=s['source'];raw=s['raw_text']
  if sha256(raw.encode()).hexdigest()!=ref['sha256']or len(raw.encode())!=ref['bytes']:raise ValueError('original source changed')
  p=json.loads(raw)
  if code.startswith('0'):
   if str(p.get('code'))!='0':
    result.append({'symbol':code,'status':'official_request_failed','usable_endpoint':False});continue
   if p['data']['code']!=code:raise ValueError('source identity changed')
   rows=p['data']['picupdata'];dates=[r[0]for r in rows]
   if dates!=sorted(set(dates)):raise ValueError('quote dates changed')
   prices={}
   for r in rows:
    op,cl,lo,hi=map(D,r[1:5])
    if not all(v.is_finite()for v in [op,cl,lo,hi])or not 0<lo<=min(op,cl)<=max(op,cl)<=hi or D(str(r[7]))<=0:raise ValueError('invalid candle')
    prices[r[0]]=cl
   if code!='002717':raise ValueError('unexpected successful subject')
   if '2026-11-19'in prices:raise ValueError('missing endpoint status changed; new review required')
   base=e['primary_historical_raw'][code]
   if any(d not in prices or prices[d]!=D(v)for d,v in base.items()):raise ValueError('historical raw mismatch')
   result.append({'symbol':code,'status':'prior_quotes_corroborated_missing_endpoint','raw_matched_days':len(base),'last_returned_record':max(prices),'usable_endpoint':False})
  else:
   if p['code']!=code or p['end']!=p['total']or len(p['kline'])!=p['end']-p['begin']:raise ValueError('SSE source scope changed')
   rows={str(r[0]):r for r in p['kline']}
   if min(rows)>='20260703'or'20260703'in rows or'20261119'not in rows:raise ValueError('anchor coverage changed; new review required')
   if e['primary_anchor']['has_trade']is not False:raise ValueError('primary anchor status changed')
   if D(str(rows['20261119'][4]))<=0:raise ValueError('endpoint activity not observed')
   result.append({'symbol':code,'status':'anchor_not_returned_matches_primary_nontrading','usable_endpoint':False})
 if len({r['symbol']for r in result})!=4:raise ValueError('four-subject scope changed')
 return result
