"""Fresh price/member window alongside, never over, frozen historical research."""
from collections import Counter
from decimal import Decimal,ROUND_HALF_UP
import json
from hashlib import sha256
from datetime import datetime
from zoneinfo import ZoneInfo
from canonical_json import digest
EXPECTED_IDS={'1225669757','1225663598','1225661533','1225666030','1225666031','1225675857','1225669888','1225663603','1225667855','1225662351','1225662350'}
WATCHED=('603398.SH','600363.SH','002667.SZ','688053.SH','002514.SZ')
def current_extension(inputs,daily):
 p=inputs.get('current_extension')
 if p is None:return None
 if p['version']!=1 or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('current extension packet changed')
 if p['baseline_through']!=inputs['through']or p['baseline_market_digest']!=digest({k:inputs[k]for k in ('calendar','through','members','activities','benchmarks','fixed_prices')})or p['baseline_daily_digest']!=digest(daily):raise ValueError('extension historical market binding changed')
 fresh=p['market_inputs']
 if fresh.get('current_extension')or fresh.get('announcement_study')or fresh['through']!='2026-11-19'or p['baseline_through']!='2026-11-06':raise ValueError('new window cannot recursively rewrite old study')
 if p['method_promotions']!=0 or p['historical_facts_rewritten']is not False:raise ValueError('new market observations cannot promote methods or rewrite historical facts')
 from st_regime_comparison import build,period_metrics,fixed_observation,main_board
 view=build(fresh);days=[d for d in view['daily']if d['date']>inputs['through']]
 if len(days)!=9 or days[0]['anchor']!=inputs['through']:raise ValueError('extension window missing sessions')
 fixed=fixed_observation(fresh,days);latest=period_metrics(days);full=next(c for c in view['comparisons']if c['key']=='all')
 old_fixed={r['symbol']for r in inputs['members']if r['trade_date']=='2026-07-03'and main_board(r['symbol'])};new_fixed={r['symbol']for r in fresh['members']if r['trade_date']=='2026-07-03'and main_board(r['symbol'])}
 if old_fixed!=new_fixed or len(old_fixed)!=150:raise ValueError('extension fixed cohort changed')
 sources={s['announcement_id']:s for s in p['sources']}
 if set(sources)!=EXPECTED_IDS or len(p['sources'])!=11 or len(p['events'])!=11 or {e['source_id']for e in p['events']}!=EXPECTED_IDS:raise ValueError('extension source/event set changed')
 for aid,s in sources.items():
  meta=s['raw_item'];day=datetime.fromtimestamp(meta['announcementTime']/1000,ZoneInfo('Asia/Shanghai')).date().isoformat()
  if str(meta['announcementId'])!=aid or meta['secCode']!=s['symbol']or day!=s['announcement_date']or not '2026-11-06'<day<=fresh['through']or s['url']!='https://static.cninfo.com.cn/'+meta['adjunctUrl']or s['protected_gate_passed']is not True or len(s['page_hashes'])!=s['pages']or set(s['selected_pages'])!={str(n)for n in range(1,s['pages']+1)}:raise ValueError('extension official source binding changed')
  for n,t in s['selected_pages'].items():
   if sha256(t.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('extension source page changed')
  if s['symbol']not in ''.join(s['selected_pages'].values()):raise ValueError('extension source company changed')
 def text(aid):return ''.join(sources[aid]['selected_pages'].values())
 clauses={'1225669757':('审议结果:通过','2026年11月12日'),'1225663598':('2026年11月11日','仍为20%','2026年11月9日'),'1225669888':('2026年11月13日','2026年11月12日'),'1225662351':('35,000','资本公积','不计入公司收入总额','30日内'),'1225662350':('5亿元','尚需提交股东会审议'),'1225666030':('20,458,800','105,640,000','14.67%'),'1225667855':('2026年10月13日','事先告知书')}
 for aid,tokens in clauses.items():
  if any(t not in text(aid)for t in tokens):raise ValueError('extension stage clause missing')
 events=[]
 for e in p['events']:
  s=sources[e['source_id']]
  from st_initial_warning_origin import origin_document_date
  try:printed=origin_document_date(s)
  except ValueError:
   if s['announcement_id']!='1225667855':raise
   printed=None
  if e['document_dated_on']!=printed or e['id']!='current_'+s['announcement_id'] or e['symbol']!=s['symbol']or e['published_on']!=s['announcement_date']or not e['pages']or any(str(n)not in s['selected_pages']for n in e['pages']):raise ValueError('extension event binding changed')
  events.append({**{k:v for k,v in e.items()if k!='source_id'},'source':{k:v for k,v in s.items()if k not in ('selected_pages','page_hashes','raw_item')}})
 members={(r['trade_date'],r['symbol']):r for r in fresh['members']};rows=[]
 if set(p['tracked_quotes'])!=set(WATCHED):raise ValueError('extension tracked scope changed')
 for c,quotes in p['tracked_quotes'].items():
  if [r['date']for r in quotes]!=[inputs['through'],*[d['date']for d in days]]:raise ValueError('tracked dates not common')
  a,z=quotes[0],quotes[-1];usable=all(r['raw_close']is not None and r['adj_factor']is not None and r['volume']and r['volume']>0 for r in (a,z));ret=float((Decimal(str(z['raw_close']))*Decimal(str(z['adj_factor']))/(Decimal(str(a['raw_close']))*Decimal(str(a['adj_factor'])))-1)*100)if usable else None
  oldname=members.get((inputs['through'],c[:6]),{}).get('name',c[:6]);name=members.get((fresh['through'],c[:6]),{}).get('name','思科瑞'if c=='688053.SH'else oldname);rows.append({'symbol':c,'name':name,'old_name':oldname,'still_st':(fresh['through'],c[:6])in members,'in_main_board_reference':main_board(c[:6]),'anchor':inputs['through'],'through':fresh['through'],'close':z['raw_close'],'change_pct':ret,'prices':quotes,'events':[e for e in events if e['symbol']==c[:6]]})
 # Source-corrobated removal; historical table must not erase this company.
 sk=[r['trade_date']for r in fresh['members']if r['symbol']=='688053'and r['trade_date']>inputs['through']]
 if sk!=['2026-11-09','2026-11-10']:raise ValueError('Sikerui official removal/provider boundary conflict')
 for s in p['cross_sources']:
  if sha256(s['text'].encode()).hexdigest()!=s['sha256']:raise ValueError('extension independent source bytes changed')
 cross={s['key']:s for s in p['cross_sources']};expected_keys={('sh'if c.endswith('.SH')else'sz')+c[:6]+'-'+k for c in WATCHED for k in ('raw','qfq')}|{'000985','932000'}
 if set(cross)!=expected_keys or len(p['cross_sources'])!=12:raise ValueError('extension crossquote scope changed')
 checked={}
 for c,quotes in p['tracked_quotes'].items():
  ticker=('sh'if c.endswith('.SH')else'sz')+c[:6];checked[c]={};latest_factor=Decimal(str(quotes[-1]['adj_factor']))
  for kind in ('raw','qfq'):
   item=cross[ticker+'-'+kind];block=json.loads(item['text'])['data'][ticker]
   if block['qt'][ticker][2]!=c[:6]or not item['url'].startswith('https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?'):raise ValueError('crossquote code/channel changed')
   parsed={r[0]:r for r in (block.get('qfqday')or block.get('day'))};count=0
   for q in quotes:
    if q['raw_close']is None or not q['volume']:continue
    expected=Decimal(str(q['raw_close']))*(Decimal(str(q['adj_factor']))/latest_factor if kind=='qfq'else Decimal(1))
    if q['date']not in parsed or abs(Decimal(parsed[q['date']][2])-expected)>Decimal('.000001'):raise ValueError('crossquote stock value conflict')
    count+=1
   checked[c][kind]={'matching_points':count,'differences':[]}
 for code,label in [('000985','csi_all_share'),('932000','csi_2000')]:
  src=cross[code];official=json.loads(src['text'])['data'];off={r['tradeDate']:r for r in official};provider={r['trade_date'].replace('-',''):r for r in fresh['benchmarks']if r['benchmark_id']==label and r['trade_date']>=inputs['through']}
  if set(off)!=set(provider)or any(r['indexCode']!=code for r in official)or not src['url'].startswith('https://www.csindex.com.cn/csindex-home/perf/index-perf?'):raise ValueError('official index scope changed')
  diff=[];maximum=Decimal(0)
  for d,r in provider.items():
   a,b=Decimal(str(r['close'])),Decimal(str(off[d]['close']));maximum=max(maximum,abs(a-b))
   if a.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)!=b:raise ValueError('official index rounded value conflict')
   if a!=b:diff.append({'date':d,'provider':str(r['close']),'official':str(off[d]['close'])})
  checked[code]={'matching_points_at_official_two_decimals':len(official),'unrounded_differences':diff,'max_absolute_point_difference':float(maximum)}
 if checked!=p['crosscheck']:raise ValueError('extension crosscheck summary changed')

 return {'baseline_through':inputs['through'],'through':fresh['through'],'latest':latest,'fixed':fixed,'full_comparison':full,'path':view['path'],'days':days,'tracked':rows,'events':events,'crosscheck':p['crosscheck'],'source_refs':[{k:v for k,v in s.items()if k!='text'}for s in p['cross_sources']],'source_counts':{'new_pdf_files':11,'new_pdf_pages':sum(s['pages']for s in sources.values()),'catalog_companies':7,'catalog_rows':sum(x['rows']for x in p['catalog_coverage'])},'old_history_unchanged':True,'boundary':'11月新窗口与历史冻结复盘分开；新行情和名单不回填成旧时点已知。动态ST日等权复合、固定150只与大盘不是同一组合；主板ST参考不含科创思科瑞。公告为有目的选样，不认证七家公司全部事项或完整官方ST全表，价格变化不证明公告净影响。'}
