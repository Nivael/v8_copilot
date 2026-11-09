"""Two issuers, three source-bound cash actions; retain both observed price constructions."""
from decimal import Decimal as D,ROUND_HALF_UP
from hashlib import sha256
from math import isclose
import re,unicodedata
from canonical_json import digest
from st_stock_price_crosscheck import quotes_from_source

KEYS=('calendar','through','fixed_prices','activities','members','fixed_quote_audit')
def scope_digest(i):return digest({k:i[k] for k in KEYS})
def norm(s):return re.sub(r'\s+','',unicodedata.normalize('NFKC',s))
def date_token(day):
 y,m,d=day.split('-');return f'{y}年{int(m)}月{int(d)}日'
def dividend_basis_view(i):
 p=i.get('dividend_basis')
 if p is None:return None
 if p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'})or p['scope_digest']!=scope_digest(i)or p['through']!=i['through']:raise ValueError('dividend basis scope changed')
 actions=p['actions'];sources={s['announcement_id']:s for s in p['sources']}
 if len(sources)!=3 or len(p['sources'])!=3 or set(sources)!={a['announcement_id']for a in actions}:raise ValueError('primary source set changed')
 if len(actions)!=3 or {(a['symbol'],a['ex_on'])for a in actions}!={('002598','2026-07-10'),('002592','2026-05-19'),('002592','2026-09-18')}:raise ValueError('three-action scope changed')
 for s in sources.values():
  if date_token(s['published_on'])not in norm(''.join(s['selected_pages'].values())):raise ValueError('publication date absent from original body')
  if not s['protected_gate_passed'] or len(s['selected_pages'])!=s['pages']:raise ValueError('unverified primary body')
  for page,text in s['selected_pages'].items():
   if sha256(norm(text).encode()).hexdigest()!=s['page_text_hashes'][int(page)-1]:raise ValueError('dividend page text changed')
 def text(source):
  s=sources[source['announcement_id']]
  if source['sha256']!=s['sha256']or source['url']!=s['url']or source['symbol']!=s['symbol']:raise ValueError('dividend fact source changed')
  return norm(s['selected_pages'][str(source['page'])]).replace(',','')
 for a in actions:
  cash=D(a['cash_per_share']);ten=D(a['cash_per_ten']);shares=D(a['shares'])
  if not cash.is_finite()or cash<=0 or ten/10!=cash or shares<=0 or shares*cash!=D(a['indicative_total']):raise ValueError('dividend unit/share arithmetic changed')
  if not a['published_on']<=a['record_on']<a['ex_on']<=i['through']or a['shares_as_of']>a['record_on']:raise ValueError('dividend known date changed')
  body=text(a['cash_source']);dates=text(a['date_source'])
  if ten not in {D(n)for n in re.findall(r'每10股派(?:发现金红利)?([0-9.]+)元',body)}or a['shares']not in body:raise ValueError('cash/share fact not in original page')
  if not all(date_token(a[k])in dates for k in ('record_on','ex_on'))or a['symbol']!=a['cash_source']['symbol']or a['symbol']!=a['date_source']['symbol']:raise ValueError('source date/issuer mismatch')
  if a['published_on']!=sources[a['announcement_id']]['published_on']or a['shares_final_verified']is not False:raise ValueError('scheduled distribution became certified paid amount')
  if 'prior_shares'in a:
   if D(a['prior_shares'])+D(a['added_shares'])!=shares or D(a['prior_shares'])*cash!=D(a['prior_indicative_total'])or D(a['added_shares'])*cash!=D(a['total_increase'])or D(a['indicative_total'])-D(a['prior_indicative_total'])!=D(a['total_increase']):raise ValueError('share-change total arithmetic changed')
   if not all(a[k]in body for k in ('prior_shares','added_shares')):raise ValueError('share increase absent from source')
 rows=[];audit=i['fixed_quote_audit']
 if audit['content_digest']!=digest({k:v for k,v in audit.items()if k!='content_digest'}):raise ValueError('quote audit packet changed')
 cal=i['calendar'];frozen={(r['symbol'],r['trade_date']):r for r in i['fixed_prices']};activity={(r['symbol'],r['trade_date']):r for r in i['activities']}
 for symbol in ('002598','002592'):
  company=next(c for c in audit['original_prices']['companies']if c['symbol']==symbol);base={r['date']:r for r in company['rows']};selected=sorted([a for a in actions if a['symbol']==symbol],key=lambda a:a['ex_on']);raw=quotes_from_source(next(s for s in audit['sources']if s['symbol']==symbol and s['key']=='tencent_raw'));qfq=quotes_from_source(next(s for s in audit['sources']if s['symbol']==symbol and s['key']=='tencent_qfq'));traded={d for d,r in base.items()if r['has_trade']}
  if set(raw)!=traded or set(qfq)!=traded or any(raw[d]!=D(str(base[d]['raw_close']))for d in traded):raise ValueError('independent raw quotes changed')
  initial=D(str(company['rows'][0]['adj_factor']));current=initial;factors={};events=[]
  for day in cal:
   for a in [a for a in selected if a['ex_on']==day]:
    if not any(r['symbol']==symbol and r['trade_date']==day for r in i['members']):raise ValueError('distribution-day ST membership unsupported')
    prev=max(d for d in traded if d<day);pre=D(str(base[prev]['raw_close']));close=raw[day];cash=D(a['cash_per_share']);reference=(pre-cash).quantize(D('.01'),rounding=ROUND_HALF_UP);formula=current*pre/reference;rounded=formula.quantize(D('.0001'),rounding=ROUND_HALF_UP)
    cache=next(x['row']for x in p['ex_date_cache_rows']if x['symbol']==symbol and x['trade_date']==day);act=activity[(symbol,day)]
    if cache['ts_code'][:6]!=symbol or D(str(cache['pre_close']))!=reference or D(str(cache['close']))!=close or cache['vol']<=0 or D(str(act['pre_close']))!=reference or D(str(act['close']))!=close:raise ValueError('ex-date actual reference/cache conflict')
    upper=(reference*D('1.05')).quantize(D('.01'),rounding=ROUND_HALF_UP);upper=max(upper,reference+D('.01'))
    events.append({**a,'previous_session':prev,'previous_raw':str(pre),'ex_raw':str(close),'reference':str(reference),'factor_before':str(current),'formula_factor':str(formula),'factor_on':str(rounded),'raw_day_pct':float((close/pre-1)*100),'reference_day_pct':float((close/reference-1)*100),'direct_qfq_day_pct':float((qfq[day]/qfq[prev]-1)*100),'old_up_boundary':str(upper),'above_old_up_boundary':close>upper,'at_old_up_boundary':close==upper,'remaining_future_cash':str(sum(D(x['cash_per_share'])for x in selected if x['ex_on']>day))})
    current=rounded
   factors[day]=current
   if D(str(base[day]['adj_factor']))!=current:raise ValueError('sequential four-decimal factor does not match cache')
  if D(str(company['normalization_factor']))!=current:raise ValueError('last normalization factor changed')
  additive_bad=[];normal_bad=[];direct=[];normalized={}
  for day in sorted(traded):
   additive=raw[day]-sum(D(a['cash_per_share'])for a in selected if day<a['ex_on'])
   if qfq[day]!=additive:additive_bad.append(day)
   value=float(raw[day]*factors[day]/current);normalized[day]=value
   if not isclose(value,frozen[(symbol,day)]['close'],rel_tol=0,abs_tol=1e-12):normal_bad.append(day)
   if D(str(base[day]['qfq_close'])).quantize(D('.01'),rounding=ROUND_HALF_UP)!=qfq[day]:direct.append(day)
  supported=not additive_bad and not normal_bad
  windows={}
  for key,start,stop in [('all','2026-07-03',i['through']),('recent20',cal[-21],i['through']),('recent5',cal[-6],i['through'])]:
   old=(frozen[(symbol,stop)]['close']/frozen[(symbol,start)]['close']-1)*100;rebuilt=(normalized[stop]/normalized[start]-1)*100
   if not isclose(old,rebuilt,rel_tol=0,abs_tol=1e-10):raise ValueError('normalized window differs')
   windows[key]={'anchor':start,'through':stop,'primary_pct':old,'direct_pct':float((qfq[stop]/qfq[start]-1)*100),'rebuilt_pct':rebuilt}
  rows.append({'symbol':symbol,'name':company['name'],'actions':events,'traded_days':len(traded),'supported':supported,'status':'basis_reconstructed'if supported else'unresolved','raw_agrees':True,'direct_difference_days':len(direct),'direct_difference_dates':direct,'additive_mismatch_dates':additive_bad,'normalized_mismatch_dates':normal_bad,'normalized_prices':normalized,'windows':windows})
 supported_all=all(r['supported']for r in rows);supported_count=sum(r['supported']for r in rows)
 return {'through':i['through'],'rows':rows,'actions_count':3,'issuers':2,'primary_documents':3,'primary_pages':sum(s['pages']for s in sources.values()),'price_dates':sum(r['traded_days']for r in rows),'direct_quote_points':sum(r['traded_days']for r in rows)*2,'new_quote_queries':0,'new_provider_queries':0,'supported':supported_all,'sources':[{k:v for k,v in s.items()if k!='selected_pages'}for s in sources.values()],'prior_snapshot_digest':p['prior_snapshot_digest'],'prior_audit_status':p['prior_audit_status'],'answer':('章鼓、八菱的原始收盘没有冲突，直接前复权差异可由已核分红及两种价格构造重建。章鼓一次、八菱两次分红分开计算；原读数继续保留，不把重建后的同口径一致说成两个原始产品本来相同。'if supported_all else'本轮仍有重建条件未通过，不能整体认证章鼓与八菱的价格构造；各公司支持状态、原始差异和失败日期分别保留。'),'what_changed':f'本轮{supported_count}家公司从“直接前复权差异待核”更新为“构造可重建”，未通过者不作认证；137只直接一致与11只直接差异的历史数字不改。11只中连同此前绝味，共{supported_count+1}只构造已有解释，另{10-supported_count}只仍待核。','boundary':p['boundary'],'what_would_change':'若分派更正、登记股本或后续公司行动与已核材料冲突，重新核现金、参考价和因子；若新增报价不能按本轮构造复现，撤回对应重建认证。缺个人税务、持有人权利和收款凭据时，不推个人实际回报。'}

def update_quote_audit(audit,basis):
 if not audit or not basis:return
 for r in audit['rows']:
  evidence=next((x for x in basis['rows']if x['symbol']==r['symbol']),None)
  if evidence and evidence['supported']:r['basis_reconciled']=True;r['basis_detail_anchor']='st-dividend-basis'
 explained=sum(bool(r['qfq_difference_days'])and r['basis_reconciled']for r in audit['rows']);audit['qfq_basis_explained_companies']=explained;audit['qfq_unexplained_companies']=audit['qfq_difference_companies']-explained;audit['previous_answer']=audit['answer'];audit['answer']+=f' 直接差异中，{explained}只构造已有解释，另{audit["qfq_unexplained_companies"]}只仍待核；差异原数没有覆盖。'
