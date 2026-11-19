from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import json,gzip
import pytest
from canonical_json import digest
from st_xilv_timeline import xilv_timeline

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-xilv-timeline.json.gz').read_bytes()))
def seal(i):
 p=i['xilv_timeline'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_dated_progress_keeps_counterexamples_shared_windows_and_unknowns():
 i=fixture();old=deepcopy(i);v=xilv_timeline(i,i['test_current']);assert i==old
 assert [r['days']for r in v['monthly']]==[20,21,21,17,14]
 assert v['counts']=={'catalog_rows':32,'pdf_files':9,'pdf_pages':95,'event_groups':7,'complete_windows':17,'incomplete_windows':4}
 assert v['first_recovery_after_july']['date']=='2026-08-11'
 assert v['hindsight_extrema']['highest_close']['date']=='2026-09-14'
 pre=next(e for e in v['events']if e['key']=='pre');assert len(pre['sources'])==3
 agree=next(e for e in v['events']if e['key']=='agreement');assert agree['windows'][0]['stock_pct']<0
 loan=next(e for e in v['events']if e['key']=='loan');assert loan['windows'][0]['anchor']=='2026-10-30'and loan['windows'][0]['through']=='2026-11-02'
 assert loan['windows'][-1]['stock_pct']is None and not loan['windows'][-1]['complete']
 assert v['crosscheck']['stock_daily_points']==94 and v['crosscheck']['official_index_daily_points']==188
 assert len(v['crosscheck']['unrounded_index_differences'])==185
 assert not v['method_promotions']and not v['tracked_list_changed']
 assert pre['sources'][-1]['document_dated_on']=='2026-08-31'

@pytest.mark.parametrize('bad',['digest','current','market','future','identity','pages','printed','duplicate','catalog','cash','court','liability','quarter','lockup','stock','index','cross_url','trade'])
def test_resealed_corruption_cannot_turn_stages_or_prices_into_false_certainty(bad):
 i=fixture();p=i['xilv_timeline'];s=p['sources'][0]
 if bad=='digest':p['content_digest']='bad'
 elif bad=='current':p['current_digest']='bad'
 elif bad=='market':p['market_digest']='bad'
 elif bad=='future':s['published_on']='2026-11-20'
 elif bad=='identity':s['raw_item']['secCode']='000609'
 elif bad=='pages':s['selected_pages'].pop('1')
 elif bad=='printed':s['document_dated_on']='2026-01-01'
 elif bad=='duplicate':p['sources'].append(deepcopy(s))
 elif bad=='catalog':p['catalog']['rows'].pop()
 elif bad in ['cash','court','liability','quarter','lockup']:
  aid,n,word={'cash':('1225650665','2','首期借款1,000万元'),'court':('1225538581','1','不代表法院正式受理'),'liability':('1225658226','4','删除条款'),'quarter':('1225621541','2','-133,706,602.68'),'lockup':('1225658226','4','60个月')}[bad];s=next(s for s in p['sources']if s['announcement_id']==aid);s['selected_pages'][n]=s['selected_pages'][n].replace(word,'changed');s['page_hashes'][int(n)-1]=sha256(s['selected_pages'][n].encode()).hexdigest()
 elif bad in ['stock','index']:
  key='sz000610'if bad=='stock'else'000985';s=next(s for s in p['cross_sources']if s['key']==key);raw=json.loads(s['text'])
  if bad=='stock':raw['data'][key]['qfqday'][17][2]='99.9'
  else:raw['data'][17]['close']=9999
  s['text']=json.dumps(raw);s['sha256']=sha256(s['text'].encode()).hexdigest()
 elif bad=='cross_url':p['cross_sources'][0]['url']='https://example.com/'
 elif bad=='trade':
  r=next(r for r in i['current_extension']['market_inputs']['fixed_prices']if r['symbol']=='000610'and r['trade_date']=='2026-07-21');r['has_trade']=False;p['market_digest']=digest(i['current_extension']['market_inputs'])
 if bad!='digest':seal(i)
 with pytest.raises(ValueError):xilv_timeline(i,i['test_current'])

def test_absent_packet_keeps_legacy_view():assert xilv_timeline({},None)is None
