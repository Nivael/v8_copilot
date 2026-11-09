"""Replay eight original exit quote responses; missing actual endpoints stay missing."""
from copy import deepcopy
from decimal import Decimal,ROUND_HALF_UP
from canonical_json import digest
from st_stock_price_crosscheck import quotes_from_source
from st_fixed_quote_audit import fixed_quote_audit_view
SUBJECTS={'000016','002731'}
KEYS=('calendar','through','fixed_prices','members','benchmarks','fixed_quote_audit','sample_integrity')
def scope_digest(i):return digest({k:i[k]for k in KEYS})
def exit_quote_replay(i,daily,prior_view):
 p=i.get('exit_quote_replay')
 if p is None:return None
 if p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'})or p['scope_digest']!=scope_digest(i)or p['through']!=i['through']:raise ValueError('exit replay binding changed')
 original=i['fixed_quote_audit'];expected=i['sample_integrity']['price_verification']['results'];sources=p['sources'];seen=set();maps={};results=[]
 if len(sources)!=8:raise ValueError('eight old exit responses required')
 for s in sources:
  pair=(s['symbol'],s['key'])
  if pair in seen or pair[0]not in SUBJECTS or pair[1]not in ('tencent_raw','tencent_qfq','eastmoney_raw','eastmoney_qfq')or s['reused']is not True:raise ValueError('exit source scope changed')
  old=next(x for x in expected[s['symbol']]['source_refs']if x['key']==s['key'])
  if any(s[k]!=old[k]for k in ('url','sha256','observed_at','symbol','key')):raise ValueError('old receipt changed')
  q=quotes_from_source(s)
  if len(q)!=old['rows']or not set(q)<=set(i['calendar']):raise ValueError('old response dates changed')
  if not s['observed_at'] or s['observed_at']>p['replayed_at']:raise ValueError('exit replay chronology changed')
  seen.add(pair);maps[pair]=q
 for sym in sorted(SUBJECTS):
  c=next(c for c in original['original_prices']['companies']if c['symbol']==sym);base={r['date']:r for r in c['rows']};traded={d for d,r in base.items()if r['has_trade']};channels=[]
  for key in ('tencent_raw','tencent_qfq','eastmoney_raw','eastmoney_qfq'):
   q=maps[(sym,key)];field='qfq_close'if key.endswith('qfq')else'raw_close'
   if set(q)!=traded or any(q[d]!=Decimal(str(base[d][field])).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)for d in traded):raise ValueError('exit traded dates or prices conflict')
   channels.append({'key':key,'points':len(q),'source':{k:next(s for s in sources if(s['symbol'],s['key'])==(sym,key))[k]for k in ('url','sha256','observed_at','reused')}})
  if maps[(sym,'tencent_raw')]!=maps[(sym,'eastmoney_raw')]or maps[(sym,'tencent_qfq')]!=maps[(sym,'eastmoney_qfq')]:raise ValueError('exit channels conflict')
  q=maps[(sym,'tencent_qfq')];receipt=expected[sym]
  if len(q)!=receipt['same_daily_close_dates']or min(q)!=receipt['first_actual_quote']or max(q)!=receipt['last_actual_quote']or float(q[max(q)])!=receipt['last_actual_close']:raise ValueError('exit old proof changed')
  for key,day in [('anchor','2026-07-03'),('endpoint',i['through'])]:
   actual=float(q[day])if day in q else None
   if actual!=receipt[key+'_actual_close']:raise ValueError('exit actual endpoint changed')
  case=next(c for c in i['sample_integrity']['cases']if c['symbol']==sym)
  results.append({'symbol':sym,'name':c['name'],'traded_days':len(traded),'first_trade':min(q),'last_trade':max(q),'last_actual_close':float(q[max(q)]),'anchor_actual_close':receipt['anchor_actual_close'],'endpoint_actual_close':receipt['endpoint_actual_close'],'classification':case['classification'],'explanation':case['explanation'],'channels':channels,'reference_only_dates':sorted(d for d,r in base.items()if not r['has_trade']and r['raw_close']is not None and r['raw_close']>0),'zero_price_placeholder_dates':sorted(d for d,r in base.items()if not r['has_trade']and r['raw_close']==0)})
 # Recompute only the derived audit with four recovered Tencent responses.
 packet=deepcopy(original)
 if any(s['symbol']in SUBJECTS for s in packet['sources']):raise ValueError('exit original audit already has responses')
 packet['sources']+=[deepcopy(s)for s in sources if s['key'].startswith('tencent_')];packet['content_digest']=digest({k:v for k,v in packet.items()if k!='content_digest'})
 updated=fixed_quote_audit_view({**i,'fixed_quote_audit':packet},daily)
 for row,old in zip(updated['rows'],prior_view['rows'],strict=True):
  if row['symbol']!=old['symbol']:raise ValueError('exit audit order changed')
  for k in ('basis_reconciled','basis_detail_anchor','source_arithmetic_conflict'):
   if k in old:row[k]=old[k]
  if row['symbol']in SUBJECTS:
   row['exit_replayed']=True
   for w in row['windows'].values():
    if w['checked_pct']is None:w['gap']='所选共同日期缺实际成交端点；旧响应已重放，不补零'
 for k in ('qfq_basis_explained_companies','qfq_unexplained_companies','source_arithmetic_conflict_companies','previous_answer','before_remaining_answer'):
  if k in prior_view:updated[k]=deepcopy(prior_view[k])
 updated['before_exit_replay_answer']=prior_view['answer'];updated['before_exit_replay_summaries']=deepcopy(prior_view['summaries']);updated['exit_replayed_companies']=2
 updated['additional_eastmoney_responses']=4;updated['additional_eastmoney_quote_points']=sum(len(q)for(sym,key),q in maps.items()if key.startswith('eastmoney_'));updated['all_channels_quote_points']=updated['quote_points']+updated['additional_eastmoney_quote_points']
 updated['boundary']='固定150只的冻结腾讯原价均已逐日重放，139只直接前复权一致、11只直接差异保留；11只差异已有构造解释，京机原件公式冲突另列。两退出样本另核东方财富原字节，但不证明底层独立；缺共同成交端点仍为空，不认证动态ST全线或制度净因果。'
 updated['answer']+=' 十一只差异已有冻结构造解释，京机原件公式冲突仍待澄清；康佳与萃华原字节本轮已重放，缺共同成交端点仍留空。'
 changes=[]
 for key,s in updated['summaries'].items():
  old=prior_view['summaries'][key];added=sorted(set(s['paired_symbols'])-set(old['paired_symbols']))
  if added:changes.append({'window':key,'added_symbols':added,'before':deepcopy(old),'after':deepcopy(s)})
 for row in results:row['windows']=next(r['windows']for r in updated['rows']if r['symbol']==row['symbol'])
 view={'through':i['through'],'replayed_at':p['replayed_at'],'prior_snapshot_digest':p['prior_snapshot_digest'],'responses':8,'quote_points':sum(len(q)for q in maps.values()),'traded_security_days':sum(r['traded_days']for r in results),'new_queries':0,'full_window_summary':deepcopy(updated['summaries']['all']),'rows':results,'changed_windows':changes,'old_raw_agree_companies':prior_view['raw_agree_companies'],'new_raw_agree_companies':updated['raw_agree_companies'],'old_qfq_agree_companies':prior_view['qfq_agree_companies'],'new_qfq_agree_companies':updated['qfq_agree_companies'],'answer':'康佳、萃华的八份原始报价已找回并与旧收据摘要吻合，133个成交股票日期四个报价口径均与原行情一致。固定150只的原始收盘核验现在覆盖150只；完整区间仍只有146只具备共同成交端点，缺价不补零。','boundary':updated['boundary']}
 return {'audit':updated,'view':view}
