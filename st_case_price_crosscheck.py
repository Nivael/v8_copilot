"""Company case quotes: explicit partial coverage, no source-count inflation."""
from st_halt_price_crosscheck import _scoped_price_check_view, scope_digest
SUBJECTS={'600730':'高科','603021':'华鹏'}

def case_price_check_view(i,daily):
 v=_scoped_price_check_view(i,daily,packet_key='case_price_crosscheck',subjects=SUBJECTS,allow_partial=True,include_alternate_dates=True,boundary='只核高科、华鹏所列日期的实际成交收盘；两渠道的原始/前复权是四种报价口径，不是四个独立来源，也不证明底层供数独立。失败不当一致，不补造缺失渠道。当前前复权回看不当历史当时可成交价；原行情、财报、公告日期与因果结论不由此改写。')
 if v is None:return None
 for r in v['rows']:
  keys={c['key'] for c in r['channels']};r['missing_channels']=sorted({'tencent_raw','tencent_qfq','eastmoney_raw','eastmoney_qfq'}-keys)
  r['available_prices_agree']=not r['frozen_price_conflicts'] and all(not c['price_differences'] and not c['missing_trade_dates'] and not c['extra_nontrade_dates'] for c in r['channels'])
  r['distinct_quote_channels']=len({k.split('_')[0] for k in keys})
  r['coverage_status']='two_channels_complete' if not r['missing_channels'] else 'partial'
 parts=[]
 for r in v['rows']:
  status='所获收盘和日期一致' if r['available_prices_agree'] else '存在价格或日期差异'
  parts.append(f"{r['name']}取得{r['distinct_quote_channels']}个渠道、{len(r['channels'])}种口径，{status}"+('，缺失渠道尚未认证' if r['missing_channels'] else ''))
 v['answer']='；'.join(parts)+'。'
 v['date_sensitivity']=[]
 for r in v['rows']:
  events={e['event_id']:e for e in r['events']}
  for key,e in events.items():
   if not key.endswith('_alternate'):continue
   primary=events[key[:-10]];a=primary['windows']['20'];b=e['windows']['20']
   if a and b:
    v['date_sensitivity'].append({'symbol':r['symbol'],'name':r['name'],'primary_published_on':primary['published_on'],'alternate_published_on':e['published_on'],'primary':a,'alternate':b,'difference_pp':a['stock_pct']-b['stock_pct'],'window_days':20})
 v['missing_channel_count']=sum(len(r['missing_channels']) for r in v['rows'])
 return v
