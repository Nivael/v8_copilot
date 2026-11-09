"""A source-bound bridge of disclosed holdings, not a reconstructed daily registry."""
from canonical_json import digest
from hashlib import sha256

EXPECTED = [
 ('1225586236',174981714,166141714,8840000,'2026-09-23','2026-09-29'),
 ('1225610808',166141714,160641714,5500000,'2026-10-16','2026-10-20'),
 ('1225612083',160641714,151321714,9320000,'2026-10-19','2026-10-21'),
 ('1225626235',151321714,147321714,4000000,'2026-10-23','2026-10-27'),
]

def holding_bridge_view(inputs):
 p=inputs.get('baoxin_holding_bridge')
 if p is None:return None
 if p['through']!=inputs['through'] or p['content_digest']!=digest({k:v for k,v in p.items() if k!='content_digest'}):raise ValueError('holding bridge binding changed')
 if p['scope_digest']!=digest({k:inputs[k] for k in ('calendar','through','fixed_prices')}):raise ValueError('holding bridge price scope changed')
 sources={s['announcement_id']:s for s in p['sources']}
 if len(sources)!=7 or sum(s['pages']for s in sources.values())!=43:raise ValueError('selected disclosure scope changed')
 pages={}
 for q in p['evidence_pages']:
  s=sources[q['announcement_id']]
  if not s['protected_gate_passed'] or q['digest']!=sha256(q['text'].encode()).hexdigest():raise ValueError('holding evidence page changed')
  pages[q['announcement_id'],q['page']]=q['text']
 for r in p['rows']:
  t=''.join(pages[r['announcement_id'],n] for n in r['pages']).replace(',','')
  if not all(str(x)in t for x in (r['before'],r['after'])) or r['before']-r['after']!=r['registered_shares']:raise ValueError('holding bridge arithmetic lacks source')
  year,month,day=r['as_of'].split('-')
  if f'{year}年{int(month)}月{int(day)}日' not in t or sources[r['announcement_id']]['announcement_date']!=r['published_on']:raise ValueError('as-of and disclosure date lack source')
  if any(token not in t for token in r['identity_tokens']):raise ValueError('registration identity missing')
 actual=[tuple(r[k]for k in ('announcement_id','before','after','registered_shares','as_of','published_on'))for r in p['rows']]
 if actual!=EXPECTED:raise ValueError('holding sequence or as-of dates changed')
 if any(a['after']!=b['before'] for a,b in zip(p['rows'],p['rows'][1:])):raise ValueError('holding bridge discontinuity')
 partial=p['partial'];t=pages['1225612083',1]+pages['1225612083',2]
 if (partial['auction_shares'],partial['registered_shares'],partial['defaulted_shares'],partial['defaulted_buyer'],partial['defaulted_bid'])!=(9420000,9320000,100000,'叶铭康','H7302') or partial['registered_shares']+partial['defaulted_shares']!=partial['auction_shares']:raise ValueError('partial registration cannot become full completion')
 if not all(x in t for x in ('叶铭康','逾期未能缴清拍卖余款','悔拍','H7302','932')):raise ValueError('default evidence absent')
 debt=p['debt'];t=pages['1225649857',1]+pages['1225649857',2]+pages['1225660311',1]
 if (debt['liqing_shares'],debt['yuhong_shares'],debt['registered'])!=(16840000,2618800,False) or not all(x in t for x in ('尚未收到','尚未过户','南京宇宏','南京新华')):raise ValueError('debt ruling is not registration')
 result={k:v for k,v in p.items()if k not in ('evidence_pages','scope_digest','content_digest')}
 result['explained_shares']=sum(r['registered_shares']for r in p['rows'])
 result['unexplained_shares']=p['rows'][0]['before']-p['rows'][-1]['after']-result['explained_shares']
 return result
