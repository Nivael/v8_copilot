"""Validate source-bound SZSE daily chart closes; not limit-price or adjustment certification."""
from decimal import Decimal as D
from hashlib import sha256
from urllib.parse import urlparse,parse_qs
import json
from datetime import date
from market_calendar import sessions_2026

def replay(e):
 out=[]
 expected=sessions_2026(date(2026,7,3),date(2026,11,19))
 for item in e['inputs']:
  code=item['symbol'];ref=item['source'];raw=item['official_raw_text'];u=urlparse(ref['url'])
  if u.scheme!='https'or u.netloc!='www.szse.cn'or u.path!='/api/market/ssjjhq/getHistoryData'or parse_qs(u.query)!={'cycleType':['32'],'marketId':['1'],'code':[code]}:raise ValueError('source endpoint changed')
  if sha256(raw.encode()).hexdigest()!=ref['sha256']or len(raw.encode())!=ref['bytes']:raise ValueError('source bytes changed')
  p=json.loads(raw)
  if p.get('code')!='0'or p['data']['code']!=code:raise ValueError('response identity/status changed')
  rows=p['data']['picupdata'];dates=[r[0]for r in rows]
  if dates!=sorted(set(dates)):raise ValueError('source dates not unique/ordered')
  prices={}
  for r in rows:
   if r[0]not in expected:continue
   if len(r)!=9:raise ValueError('daily columns changed')
   op,cl,lo,hi,chg,pct,vol,amt=map(lambda v:D(str(v)),r[1:])
   if not all(v.is_finite()for v in (op,cl,lo,hi,chg,pct,vol,amt))or not 0<lo<=min(op,cl)<=max(op,cl)<=hi or vol<=0 or amt<=0:raise ValueError('invalid candle or activity')
   prices[r[0]]=cl
  if list(prices)!=expected:raise ValueError('target window incomplete')
  historical=item['historical_primary_raw'];recent=item['later_primary_paired']
  if set(prices)!=set(historical)|set(recent)or set(historical)&set(recent):raise ValueError('comparison scope changed')
  for d,v in historical.items():
   if prices[d]!=D(v)or prices[d]!=D(item['historical_tencent_raw'][d]):raise ValueError('historical raw mismatch')
  for d,v in recent.items():
   if prices[d]!=D(item['later_tencent_paired'][d])or abs(prices[d]-D(v))>D('1e-12'):raise ValueError('later paired mismatch')
  out.append({'symbol':code,'historical':len(historical),'later':len(recent),'total':len(prices)})
 if len({r['symbol']for r in out})!=len(out):raise ValueError('duplicate security')
 return out
