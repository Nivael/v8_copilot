"""Complete the eight frozen quote explanations without equating reconstruction to clean source arithmetic."""
from decimal import Decimal as D,ROUND_HALF_UP,ROUND_DOWN,localcontext
from hashlib import sha256
from math import isclose
import re,unicodedata
from canonical_json import digest
from st_stock_price_crosscheck import quotes_from_source
SUBJECTS={'000793','000821','002538','002689','600079','603189','603822','603869'}
KEYS=('calendar','through','fixed_prices','activities','members','fixed_quote_audit','dividend_basis','label_changes')
def scope_digest(i):return digest({k:i[k]for k in KEYS})
def norm(s):return re.sub(r'\s+','',unicodedata.normalize('NFKC',s)).replace(',','')
def remaining_basis_view(i):
 p=i.get('remaining_basis')
 if p is None:return None
 if p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'})or p['scope_digest']!=scope_digest(i)or p['through']!=i['through']:raise ValueError('remaining basis binding changed')
 if len(p['rows'])!=8 or {r['symbol']for r in p['rows']}!=SUBJECTS:raise ValueError('remaining issuer scope changed')
 sources={s['announcement_id']:s for s in p['sources']}
 if len(sources)!=len(p['sources'])or len(sources)!=11:raise ValueError('remaining primary source set changed')
 for s in sources.values():
  if not s['protected_gate_passed']or len(s['selected_pages'])!=s['pages']or s['published_on']>i['through']:raise ValueError('remaining source scope changed')
  for page,t in s['selected_pages'].items():
   if sha256(re.sub(r'\s+','',unicodedata.normalize('NFKC',t)).encode()).hexdigest()!=s['page_text_hashes'][int(page)-1]:raise ValueError('remaining page text changed')
 def text(src):
  s=sources[src['announcement_id']]
  if any(src[k]!=s[k]for k in ('sha256','url','symbol')):raise ValueError('remaining source ref changed')
  return norm(s['selected_pages'][str(src['page'])])
 cal=i['calendar'];frozen={(r['symbol'],r['trade_date']):r for r in i['fixed_prices']};activity={(r['symbol'],r['trade_date']):r for r in i['activities']};audit=i['fixed_quote_audit'];out=[]
 if audit['content_digest']!=digest({k:v for k,v in audit.items()if k!='content_digest'}):raise ValueError('quote packet changed')
 for item in p['rows']:
  r=dict(item);symbol=r['symbol'];ex=r['effective_on'];body=text(r['cash_source']);datebody=text(r['date_source'])
  if r['published_on']!=sources[r['cash_source']['announcement_id']]['published_on']:raise ValueError('remaining publication date mismatch')
  if (symbol=='000821')!=(r['source_conflict']is not None):raise ValueError('known formula conflict was hidden')
  if not r['published_on']<=r['record_on']<ex<=i['through']or r['cash_source']['symbol']!=symbol or r['date_source']['symbol']!=symbol:raise ValueError('remaining action known date or identity changed')
  for d in (r['record_on'],ex):
   y,m,day=d.split('-');tokens=[f'{y}年{int(m)}月{int(day)}日',f'{y}/{int(m)}/{int(day)}']
   if not any(t in datebody for t in tokens):raise ValueError('action date absent from selected page')
  company=next(c for c in audit['original_prices']['companies']if c['symbol']==symbol);base={x['date']:x for x in company['rows']};traded={d for d,x in base.items()if x['has_trade']};raw=quotes_from_source(next(s for s in audit['sources']if s['symbol']==symbol and s['key']=='tencent_raw'));qfq=quotes_from_source(next(s for s in audit['sources']if s['symbol']==symbol and s['key']=='tencent_qfq'))
  if set(raw)!=traded or set(qfq)!=traded or any(raw[d]!=D(str(base[d]['raw_close']))for d in traded):raise ValueError('remaining independent raw prices changed')
  prev=max(d for d in traded if d<ex);pre=raw[prev];kind=r['kind'];cash=None;virtual=None;conflict=None
  if kind=='cash_dividend':
   cash=D(r['per_eligible_share_cash']);total=D(r['total_shares']);excluded=D(r['excluded_shares']);eligible=total-excluded;amount=D(r['declared_total']);reported=D(r['reference_cash'])
   if not(cash.is_finite()and 0<cash<pre and 0<=excluded<total)or(eligible*cash).quantize(D('.01'),rounding=ROUND_HALF_UP)!=amount:raise ValueError('remaining dividend units or total changed')
   amounts={D(n)/10 for n in re.findall(r'每10股派(?:发现金红利|发现金股利)?([0-9.]+)元',body)}|{D(n)for n in re.findall(r'每股(?:现金红利|派发现金红利)([0-9.]+)元',body)}
   if cash not in amounts:raise ValueError('per-share unit not in original page')
   if excluded and str(int(excluded))not in body:raise ValueError('repurchase exclusion absent from source')
   if r['reference_rounding']not in ('truncate','round')or type(r['reference_digits'])is not int or not 0<=r['reference_digits']<=8:raise ValueError('unknown cash precision rule')
   if any(str(v).lstrip('0')not in body for v in (r['total_shares'],r['declared_total'])):raise ValueError('remaining share/amount absent from source')
   virtual=amount/total;rounding=ROUND_DOWN if r['reference_rounding']=='truncate'else ROUND_HALF_UP;declared=virtual.quantize(D(1).scaleb(-r['reference_digits']),rounding=rounding)
   if declared!=reported:raise ValueError('virtual cash rounding changed')
   reference=(pre-reported).quantize(D('.01'),rounding=ROUND_HALF_UP)
   if r['source_conflict']:
    c=r['source_conflict'];b=text(c['source']);printed=D(c['printed_denominator']);right=D(c['consistent_total_denominator']);report=D(c['reported_per_ten']);literal=amount/printed*10;consistent=(amount/right*10).quantize(D('.000001'),rounding=ROUND_DOWN)
    if c['issuer_correction_verified']is not False or printed!=eligible or right!=total or consistent!=report or abs(literal-report)<D('.000001')or any(c[k]not in b for k in ('printed_denominator','consistent_total_denominator','reported_per_ten')):raise ValueError('source formula conflict not preserved')
    conflict={**c,'literal_per_ten':str(literal),'consistent_per_ten':str(consistent),'status':'unresolved_issuer_formula_denominator'}
   r['eligible_shares']=str(eligible);r['virtual_cash_exact']=str(virtual)
  elif kind=='reorg_reference':
   if symbol!='000793':raise ValueError('unexpected noncash reorg')
   old=D(r['pre_shares']);added=D(r['added_shares']);after=D(r['after_shares']);debt=D(r['debt_shares']);investment=D(r['industrial_shares'])+D(r['financial_shares']);debtvalue=debt*D(r['debt_price']);investcash=D(r['industrial_cash'])+D(r['financial_cash']);holder=D(r['old_holder_distribution'])
   if old+added!=after or debt+investment!=added or holder!=0 or(old*D('1.2')).quantize(D('1'),rounding=ROUND_DOWN)!=added:raise ValueError('reorg share arithmetic changed')
   if any(r[k]not in body for k in ('debt_shares','industrial_cash','financial_cash')):raise ValueError('reorg amount absent from source')
   average=(debtvalue+investcash)/added;unrounded=(pre*old+debtvalue+investcash)/(old+debt+investment+holder);reference=unrounded.quantize(D('.01'),rounding=ROUND_HALF_UP)if pre>average else pre
   if reference!=D(r['declared_reference'])or average.quantize(D('.01'),rounding=ROUND_HALF_UP)!=D(r['declared_new_share_average']):raise ValueError('reorg reference formula changed')
   if r['declared_reference']not in text(r['reference_source']) or r['document_dated_on']!='2026-06-17':raise ValueError('reorg declared price/date changed')
   r.update(reference_unrounded=str(unrounded),new_share_average_unrounded=str(average),debt_value=str(debtvalue),investor_cash_terms=str(investcash),last_actual_date=prev,actual_halt_dates=[d for d in cal if prev<d<ex and not base[d]['has_trade']])
  else:raise ValueError('unknown remaining action kind')
  cache=next(x['row']for x in p['ex_cache_rows']if x['symbol']==symbol and x['date']==ex);act=activity[(symbol,ex)]
  if cache['ts_code'][:6]!=symbol or D(str(cache['pre_close']))!=reference or D(str(cache['close']))!=raw[ex]or cache['vol']<=0 or D(str(act['pre_close']))!=reference or D(str(act['close']))!=raw[ex]:raise ValueError('remaining reference/cache conflict')
  if not any(x['symbol']==symbol and x['trade_date']==ex for x in i['members']):raise ValueError('remaining ST membership missing')
  before=D(str(base[prev]['adj_factor']));factor=(before*pre/reference).quantize(D('.0001'),rounding=ROUND_HALF_UP)
  if any(D(str(x['adj_factor']))!=(before if d<ex else factor)for d,x in base.items())or D(str(company['normalization_factor']))!=factor:raise ValueError('remaining factor rounding changed')
  product_bad=[];normalized_bad=[];direct=[];cent=[];cash_alt_bad=[];exact_alt_bad=[];normalized={}
  for day in sorted(traded):
   constructed=raw[day]if day>=ex else raw[day]*reference/pre if kind=='reorg_reference'else raw[day]-D(r['reference_cash']);constructed=constructed.quantize(D('.001'),rounding=ROUND_HALF_UP)
   if constructed!=qfq[day]:product_bad.append(day)
   value=float(raw[day]*(before if day<ex else factor)/factor);normalized[day]=value
   if not isclose(value,frozen[(symbol,day)]['close'],rel_tol=0,abs_tol=1e-12):normalized_bad.append(day)
   primary=D(str(base[day]['qfq_close'])).quantize(D('.01'),rounding=ROUND_HALF_UP)
   if primary!=qfq[day]:direct.append(day)
   if primary!=qfq[day].quantize(D('.01'),rounding=ROUND_HALF_UP):cent.append(day)
   if cash is not None and(raw[day]if day>=ex else raw[day]-cash).quantize(D('.001'),rounding=ROUND_HALF_UP)!=qfq[day]:cash_alt_bad.append(day)
   if virtual is not None and(raw[day]if day>=ex else raw[day]-virtual).quantize(D('.001'),rounding=ROUND_HALF_UP)!=qfq[day]:exact_alt_bad.append(day)
  upper=max((reference*D('1.05')).quantize(D('.01'),rounding=ROUND_HALF_UP),reference+D('.01'))
  r.update(previous_session=prev,previous_raw=str(pre),reference=str(reference),ex_raw=str(raw[ex]),factor_before=str(before),factor_on=str(factor),traded_days=len(traded),direct_difference_days=len(direct),same_cent_difference_days=len(cent),same_cent_difference_dates=cent,product_mismatch_dates=product_bad,normalized_mismatch_dates=normalized_bad,supported=not product_bad and not normalized_bad,source_conflict=conflict,eligible_cash_also_matches=cash is not None and not cash_alt_bad,exact_virtual_also_matches=virtual is not None and not exact_alt_bad,normalized_prices=normalized,raw_day_pct=float((raw[ex]/pre-1)*100),reference_day_pct=float((raw[ex]/reference-1)*100),direct_day_pct=float((qfq[ex]/qfq[prev]-1)*100),old_up_boundary=str(upper),above_old_up_boundary=raw[ex]>upper)
  r['windows']={k:{'anchor':a,'through':b,'primary_pct':(frozen[(symbol,b)]['close']/frozen[(symbol,a)]['close']-1)*100,'direct_pct':float((qfq[b]/qfq[a]-1)*100),'rebuilt_pct':(normalized[b]/normalized[a]-1)*100}for k,a,b in [('all','2026-07-03',i['through']),('20',cal[-21],i['through']),('5',cal[-6],i['through'])]};out.append(r)
 count=sum(r['supported']for r in out)
 return {'through':i['through'],'rows':out,'supported_count':count,'remaining_unreconstructed':8-count,'source_conflict_companies':sum(bool(r['source_conflict'])for r in out),'new_files':sum(not s['reused']for s in sources.values()),'reused_files':sum(s['reused']for s in sources.values()),'source_pages':sum(s['pages']for s in sources.values()),'new_pages':sum(s['pages']for s in sources.values()if not s['reused']),'price_dates':sum(r['traded_days']for r in out),'quote_points':sum(r['traded_days']for r in out)*2,'new_quote_queries':0,'prior_snapshot_digest':p['prior_snapshot_digest'],'answer':f'剩余8只中，{count}只的冻结价格构造可重建。华闻是重整转增除权，其余7只是现金分派及精度差异；京机原件的公式分母冲突仍单列，价格能复现不等于原件全部算式无问题。','what_would_change':'若原件更正、登记股本、复权产品精度或公司行动发生变化，重核对应参考价、因子和窗口；不能复现时撤回该项重建支持。原件冲突须等明确原件澄清，不能用价格吻合替发行人改写公式。','boundary':p['boundary']}

def apply_remaining_status(audit,basis,original):
 if not audit or not basis:return
 for r in audit['rows']:
  b=next((b for b in basis['rows']if b['symbol']==r['symbol']),None)
  if b and b['supported']:r.update(basis_reconciled=True,basis_detail_anchor='st-dividend-basis',source_arithmetic_conflict=bool(b['source_conflict']))
 count=sum(bool(r['qfq_difference_days'])and r['basis_reconciled']for r in audit['rows']);audit['qfq_basis_explained_companies']=count;audit['qfq_unexplained_companies']=audit['qfq_difference_companies']-count;audit['source_arithmetic_conflict_companies']=basis['source_conflict_companies'];audit['before_remaining_answer']=audit['answer'];audit['answer']=audit['previous_answer']+f' 直接差异中{count}只已有冻结构造解释，另{audit["qfq_unexplained_companies"]}只未重建；京机原件公式分母冲突保留，不作为无冲突认证。'
 if original:
  original['before_remaining_what_changed']=original['what_changed'];original['what_changed']=f'章鼓、八菱的旧解释保留。本轮再核其余8只，累计{count}只直接差异已有构造解释，另{audit["qfq_unexplained_companies"]}只未重建；137只直接一致、11只直接差异仍按旧定义，京机公式分母冲突另列。'
