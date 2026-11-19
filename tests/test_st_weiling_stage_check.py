from pathlib import Path
import gzip,json
from copy import deepcopy
import pytest
from canonical_json import digest
from st_weiling_stage_check import weiling_stage_check

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-weiling-stage-check.json.gz').read_bytes()))
def seal(i):
 p=i['weiling_stage_check'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})

def test_control_and_meeting_stages_are_not_repeated_or_backdated():
 i=fixture();before=deepcopy(i);v=weiling_stage_check(i,i['test_current']);assert i==before
 assert len(v['rows'])==4 and v['counts']['pdf_files']==6 and v['counts']['pdf_pages']==41
 assert '控制权未变'in v['rows'][0]['title']
 assert v['rows'][2]['published_on']=='2026-11-06'and v['rows'][2]['document_dated_on']=='2026-11-05'
 assert v['rows'][2]['effective_or_scheduled_on']=='2026-11-04'
 assert v['meeting']['state_at_cutoff']=='scheduled_not_passed'and v['meeting']['scheduled_on']=='2026-11-23'
 assert v['adviser']['document_dated_on']is None and v['adviser']['report_end']=='2026-09-30'
 assert sum(w['stock_pct']is not None for r in v['rows']for w in r['observation']['windows'].values())==9
 assert v['rows'][2]['observation']==v['rows'][3]['observation']

@pytest.mark.parametrize('bad',['checksum','market_binding','identity','title','publication','pages','stage_clause','actual_control','meeting_date','signature','market_inputs'])
def test_resealed_packets_cannot_hide_identity_dates_or_stage_corruption(bad):
 i=fixture();p=i['weiling_stage_check'];s=p['sources'][0]
 if bad=='checksum':p['content_digest']='bad'
 elif bad=='market_binding':p['current_extension_digest']='bad'
 elif bad=='identity':s['raw_item']['secCode']='002207'
 elif bad=='title':s['title']='已收到赠款'
 elif bad=='publication':s['published_on']='2026-11-23'
 elif bad=='pages':s['selected_pages'].pop('2')
 elif bad in ['stage_clause','actual_control','meeting_date','signature']:
  aid,page,token,replacement={'stage_clause':('1225599834','1','未导致公司控制权发生变更','已经变更'),'actual_control':('1225660313','3','2026年11月4日','2026年10月12日'),'meeting_date':('1225675068','1','2026年11月23日14:00','2026年11月18日14:00'),'signature':('1225666404','14','年月日','2026年11月12日')}[bad]
  s=next(s for s in p['sources']if s['announcement_id']==aid);s['selected_pages'][page]=s['selected_pages'][page].replace(token,replacement)
  from hashlib import sha256
  s['page_hashes'][int(page)-1]=sha256(s['selected_pages'][page].encode()).hexdigest()
 elif bad=='market_inputs':i['current_extension']['market_inputs']['through']='2026-11-20'
 if bad!='checksum':seal(i)
 with pytest.raises(ValueError):weiling_stage_check(i,i['test_current'])

def test_legacy_absence_does_not_require_current_data():assert weiling_stage_check({},None)is None
