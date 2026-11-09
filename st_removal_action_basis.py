"""Issuer-bound dividend reconstruction for pre-rule removal event windows."""
from decimal import Decimal as D,ROUND_HALF_UP
from hashlib import sha256
from math import isclose
from urllib.parse import urlparse
import re,unicodedata
from canonical_json import digest
from st_stock_price_crosscheck import quotes_from_source
KEYS=('calendar','through','dynamic_reference_audit','pre_rule_membership','removal_era_comparison')
TARGETS={'600360':{'2026-06-08','2026-10-27'},'000668':{'2026-07-08'},'603580':{'2026-08-14'}}
def scope_digest(i):return digest({k:i[k]for k in KEYS})
def norm(t):return re.sub(r'\s+','',unicodedata.normalize('NFKC',t)).replace(',','')
def action_basis_view(i):
 p=i.get('removal_action_basis')
 if p is None:return None
 if p['version']!=1 or p['through']!=i['through']or p['scope_digest']!=scope_digest(i)or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('removal action source binding changed')
 if len(p['actions'])!=4 or {(r['symbol'],r['ex_on'])for r in p['actions']}!={(s,d)for s,dates in TARGETS.items()for d in dates}:raise ValueError('removal action event scope changed')
 sources={s['announcement_id']:s for s in p['sources']}
 if len(sources)!=4 or len(p['sources'])!=4:raise ValueError('removal action source set changed')
 for s in sources.values():
  host=urlparse(s['url']).hostname;official=host in ('disc.static.szse.cn','static.cninfo.com.cn')
  if not official and host!='file.finance.sina.com.cn':raise ValueError('unrecognized issuer mirror host')
  if s['host_is_official']!=official or s['source_format']!=('pdf_official'if official else'pdf_mirror')or not s['protected_gate_passed']or len(s['selected_pages'])!=s['pages']:raise ValueError('removal action provenance changed')
  if not official and not all(s.get(k)for k in ('catalog_url','catalog_announcement_id','html_url')):raise ValueError('mirror lost official catalog chain')
  for page,text in s['selected_pages'].items():
   # Source text identity uses the shared whitespace-only gate, not amount normalization.
   if sha256(re.sub(r'\s+','',unicodedata.normalize('NFKC',text)).encode()).hexdigest()!=s['page_text_hashes'][int(page)-1]:raise ValueError('removal action page changed')
 cal=i['calendar'];companies={c['symbol']:c for c in i['dynamic_reference_audit']['original_prices']['companies']};out=[]
 for symbol,dates in TARGETS.items():
  company=companies[symbol];base={r['date']:r for r in company['rows']};raw=quotes_from_source(next(s for s in i['dynamic_reference_audit']['sources']if s['symbol']==symbol and s['key']=='tencent_raw'));q=quotes_from_source(next(s for s in i['dynamic_reference_audit']['sources']if s['symbol']==symbol and s['key']=='tencent_qfq'));traded={d for d,r in base.items()if r['has_trade']}
  if list(base)!=cal or set(raw)!=traded or set(q)!=traded or any(raw[d]!=D(str(base[d]['raw_close']))for d in traded):raise ValueError('removal action raw quotes differ')
  actions=[];current=D(str(base[cal[0]]['adj_factor']));initial=current
  for item in sorted((r for r in p['actions']if r['symbol']==symbol),key=lambda r:r['ex_on']):
   r=dict(item);s=sources[r['source_id']];body=norm(s['selected_pages'][str(r['cash_page'])]);dated=norm(s['selected_pages'][str(r['date_page'])]);cash=D(r['cash_per_share']);total=D(r['total_shares']);ex=r['ex_on'];record=r['record_on']
   if s['symbol']!=symbol or symbol not in norm(s['selected_pages']['1'])or r['published_on']!=s['published_on']or not r['published_on']<=record<ex<=i['through']or r['personal_receipt_verified']is not False:raise ValueError('removal action identity or known-time changed')
   amounts={D(x)for x in re.findall(r'每股(?:派发现金红利|现金红利)([0-9.]+)元',body)}|{D(x)/10 for x in re.findall(r'每10股派(?:发现金红利)?([0-9.]+)元',body)}
   if cash not in amounts or str(int(total))not in body or not(0<cash<1 and total>0):raise ValueError('cash/share units absent from original page')
   amount=(cash*total).quantize(D('.01'),rounding=ROUND_HALF_UP)
   if r['declared_total']is not None and(D(r['declared_total'])!=amount or r['declared_total']not in body):raise ValueError('dividend total conflicts with original')
   for day in (record,ex):
    y,m,d=day.split('-')
    if not any(token in dated for token in (f'{y}年{int(m)}月{int(d)}日',f'{y}/{int(m)}/{int(d)}')):raise ValueError('action schedule absent from cited page')
   prev=max(d for d in traded if d<ex)
   if record!=prev or ex not in traded:raise ValueError('dividend record/ex actual sessions differ')
   reference=(raw[prev]-cash).quantize(D('.01'),rounding=ROUND_HALF_UP);factor=(current*raw[prev]/reference).quantize(D('.0001'),rounding=ROUND_HALF_UP)
   if D(str(base[ex]['pre_close']))!=reference or D(str(base[prev]['adj_factor']))!=current or D(str(base[ex]['adj_factor']))!=factor:raise ValueError('cash/reference/factor reconstruction failed')
   actions.append({**r,'derived_total':str(amount),'previous_raw':str(raw[prev]),'reference':str(reference),'factor_before':str(current),'factor_on':str(factor),'factor_formula':str(current*raw[prev]/reference),'host_is_official':s['host_is_official'],'source':{k:v for k,v in s.items()if k not in ('selected_pages','page_text_hashes','rank')}});current=factor
  byex={a['ex_on']:a for a in actions};factor=initial;expected={}
  for day in cal:
   if day in byex:factor=D(byex[day]['factor_on'])
   if D(str(base[day]['adj_factor']))!=factor:raise ValueError('unexplained factor change outside notices')
   expected[day]=factor
  additive_bad=[];direct_difference=[];same_cent=[];normalized={}
  for day in sorted(traded):
   adjusted=(raw[day]-sum(D(a['cash_per_share'])for a in actions if day<a['ex_on'])).quantize(D('.001'),rounding=ROUND_HALF_UP)
   if adjusted!=q[day]:additive_bad.append(day)
   value=raw[day]*expected[day]/factor;normalized[day]=float(value)
   if value.quantize(D('.01'),rounding=ROUND_HALF_UP)!=q[day]:direct_difference.append(day)
   if value.quantize(D('.01'),rounding=ROUND_HALF_UP)!=q[day].quantize(D('.01'),rounding=ROUND_HALF_UP):same_cent.append(day)
  if additive_bad:raise ValueError('issuer cash actions do not reproduce frozen qfq')
  out.append({'symbol':symbol,'name':company['name'],'actions':actions,'traded_days':len(traded),'raw_agrees':True,'additive_mismatch_dates':additive_bad,'direct_difference_dates':direct_difference,'same_cent_difference_dates':same_cent,'normalized_prices':normalized,'supported':True,'source_level':'official_and_issuer_pdf_mirror'if any(not a['host_is_official']for a in actions)else'official_body','future_actions_do_not_describe_then_known_information':True})
 return {'through':i['through'],'issuers':3,'actions_count':4,'files':4,'pages':sum(s['pages']for s in sources.values()),'official_files':sum(s['host_is_official']for s in sources.values()),'mirror_files':sum(not s['host_is_official']for s in sources.values()),'traded_security_days':sum(r['traded_days']for r in out),'quote_points':sum(r['traded_days']for r in out)*2,'new_market_queries':0,'rows':out,'sources':[{k:v for k,v in s.items()if k not in ('selected_pages','page_text_hashes','rank')}for s in sources.values()],'prior_snapshot_digest':p['prior_snapshot_digest'],'boundary':p['boundary']}
def window_support(symbol,w,basis):
 if not basis or w['stock_pct']is None or not w['anchor']or not w['through']:return None
 r=next((r for r in basis['rows']if r['symbol']==symbol),None)
 if not r or not r['supported']:return None
 a,b=w['anchor'],w['through'];prices=r['normalized_prices']
 if a not in prices or b not in prices or not isclose((prices[b]/prices[a]-1)*100,w['stock_pct'],abs_tol=1e-10,rel_tol=0):return None
 used=[x for x in r['actions']if a<x['ex_on']<=b]
 if not used:return None
 return {'supported':True,'source_ids':[x['source_id']for x in used],'has_mirror':any(not x['host_is_official']for x in used),'scope':'only_issuer_actions_inside_window'}
