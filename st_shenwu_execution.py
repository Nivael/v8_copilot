"""Separate shareholder settlement, issuer cash and a newly signed consortium contract."""
from decimal import Decimal as D,ROUND_HALF_UP
from canonical_json import digest

def scope_digest(i):
 return digest({k:i[k]for k in ('calendar','through','fixed_prices','benchmarks','strong_removal_cases')})

def shenwu_execution_view(i):
 p=i.get('shenwu_execution')
 if p is None:return None
 if p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}) or p['scope_digest']!=scope_digest(i):raise ValueError('shenwu execution source/scope changed')
 if p['symbol']!='000820' or p['through']!=i['through']:raise ValueError('execution subject/cutoff changed')
 sources={r['sha256']:r for r in p['sources']}
 def check(s,published):
  r=sources.get(s['sha256'])
  if not r or r['symbol']!=p['symbol'] or r['published_on']!=published or r['url']!=s['url'] or not 1<=s['page']<=r['pages'] or s['page_text_hash']!=r['page_text_hashes'][s['page']-1] or published>p['through']:raise ValueError('execution timely physical page/source changed')
 for f in p['facts']:check(f['source'],f['published_on'])
 t=p['transfer'];c=p['contract'];r=p['receivable'];a=p['auctions']
 if len(a)!=2 or [x['status']for x in a]!=['failed','failed'] or not(a[0]['start']<a[0]['end']<a[0]['published_on']<a[1]['start']<a[1]['end']<a[1]['published_on']<t['reported_change_on']<t['published_on']):raise ValueError('auction/transfer stage or known order changed')
 if not(t['reported_change_on']<=t['issuer_signed_on']<t['published_on']):raise ValueError('issuer signed date cannot replace public date')
 if t['status']!='registration_complete_per_disclosures' or t['mode']!='court_debt_settlement' or t['issuer_cash_received_yuan']is not None or t['exact_registry_receipt_on']is not None or t['control_changed']is not False or t['compensation_fulfilled']is not None or t['reported_change_on']!='2026-10-08':raise ValueError('unproven transfer cash/control/receipt/compensation claim')
 check(t['source'],t['published_on'])
 if len(t['report_date_sources'])!=2:raise ValueError('counterparty dates not corroborated')
 for s in t['report_date_sources']:check(s,t['published_on'])
 for x in a:check(x['source'],x['published_on'])
 if any(D(x['shares'])!=D(t['shares'])for x in a) or D(t['before_shares'])-D(t['shares'])!=D(t['after_shares']) or D(t['receiver_before'])+D(t['shares'])!=D(t['receiver_after']) or D(t['historical_already_transferred'])+D(t['before_shares'])!=D(t['original_reorganization_shares']):raise ValueError('share chain does not reconcile')
 ratios={k:str((D(num)/D(den)*100).quantize(D('.01'),rounding=ROUND_HALF_UP))for k,num,den in [('transfer_pct',t['shares'],t['total_shares']),('old_holder_before_pct',t['before_shares'],t['total_shares']),('old_holder_after_pct',t['after_shares'],t['total_shares']),('auction_pct_of_then_holdings',t['shares'],t['before_shares']),('historical_pct_of_original',t['historical_already_transferred'],t['original_reorganization_shares'])]}
 if any(ratios[k]!=v for k,v in t['reported_ratios'].items()):raise ValueError('share denominator or rounded ratio changed')
 if not(c['signed_on']<c['issuer_signed_on']<c['published_on']<=p['through']) or c['status']!='signed_not_revenue_or_receipt_certified' or any(c[k]is not None for k in ('recognized_revenue_yuan','actual_receipts_yuan','parent_profit_yuan','allocated_to_subsidiary_yuan','actual_start_on','exact_effective_on')) or c['scope']!='consortium_total_including_tax':raise ValueError('contract date/scope/execution claim changed')
 if sum(D(v)for v in c['components_yuan'].values())!=D(c['total_yuan']) or D(c['energy_kwh'])*1000*D(c['unit_yuan_per_wh'])!=D(c['total_yuan']) or c['calendar_days']!=365 or c['planned_finish_on']!='2027-10-31':raise ValueError('contract total/unit/term does not reconcile')
 check(c['source'],c['published_on']);check(r['source'],r['as_of'])
 if r['status']!='not_received_as_of_report' or r['received_yuan']is not None or r['latest_after_report_status']!='not_verified' or not(r['due_on']<r['as_of']<=p['through']):raise ValueError('receivable as-of missing/zero confused')
 old=next(x for x in i['strong_removal_cases']['rows']if x['symbol']=='000820')
 if r['source']['sha256']!=old['third']['metric_sources']['operating_cash']['sha256'] or not any(str(r['due_yuan'])in f['text']for f in old['facts']):raise ValueError('receivable differs from prior quarterly reading')
 return {**{k:v for k,v in p.items()if k not in ('content_digest','scope_digest')},'ratios':ratios,'contract_components_total_yuan':str(sum(D(v)for v in c['components_yuan'].values())),'observations':[],'independent_company_count':1,'boundary':'六份新原件归四个公告阅读事项；两次流拍到过户是一条股东股份链，三份权益文件不是三次独立验证。双方报告与发行人公告只旁证同一披露事实，不代替登记机构回执或法院原裁定。现金、补偿和收入确认各自需要后续凭证。'}
