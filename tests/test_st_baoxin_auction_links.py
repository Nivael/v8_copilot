from pathlib import Path
from copy import deepcopy
import json,gzip
import pytest
from canonical_json import digest
from st_baoxin_auction_links import auction_links_view,scope_digest,ann_digest

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/baoxin-auction-links.json.gz').read_bytes()))
def view(i):return auction_links_view(i,i['test_ann'])
def seal(i):
 p=i['baoxin_auction_links'];p['scope_digest']=scope_digest(i);p['announcement_digest']=ann_digest(i['test_ann']);p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_registered_lots_join_by_buyer_court_bid_type_not_just_sum():
 i=fixture();old=deepcopy(i);v=view(i);assert i==old
 assert(v['registered_groups'],v['registered_shares'],v['registration_notice_days'],v['source_files'],v['source_pages'])==(3,13420000,2,10,40)
 r={r['lot_id']:r for r in v['lots']}
 assert(r['jm-400']['auction_end'],r['jm-400']['registered_as_of'],r['jm-400']['registration_notice'])==('2026-08-29','2026-09-18','2026-09-23')
 assert(r['st-612']['steps'][0]['bid_id'],r['bj-330']['steps'][0]['bid_id'])==('L4934','K8156')
 assert r['bj-330']['registered_as_of']=='2026-11-02'and r['bj-330']['steps'][-1]['date_kind']=='as_of'
 assert len(r['jm-400']['steps'][-1]['source_refs'])==2
 assert len(v['observations'])==10 and len({e['id']for e in v['observations']})==10

def test_reauction_same_underlying_shares_and_pending_not_failure():
 v=view(fixture());r={r['lot_id']:r for r in v['lots']};assert v['reauction_underlying_shares']==11000000 and v['reauction_groups']==2
 assert(r['hz-restricted']['steps'][0]['bid_id'],r['hz-restricted']['steps'][-1]['bid_id'])==('E4057','P9195')
 assert(r['hz-unrestricted']['steps'][0]['bid_id'],r['hz-unrestricted']['steps'][-1]['bid_id'])==('B9887','S2290')
 assert all(r[k]['status']=='reauction_no_registration_proof'for k in ('hz-restricted','hz-unrestricted'))
 assert sum(a['shares']for a in r['jj-942-group']['allocations'])==9420000 and len(r['jj-942-group']['allocations'])==11
 assert '未核'in r['jj-942-group']['note']and '不合计'in v['boundary']
 assert v['holding_gap']['unmatched_intermediate_change']==27660000
 assert(v['conflicts']['bid_total'],v['conflicts']['printed_delta'],v['conflicts']['unexplained_difference'])==(11000000,9000000,2000000)
 first=next(e for e in v['observations']if e['id']=='second_fail_july');assert first['published_on']=='2026-07-04'and first['alternate_published_on']=='2026-07-06'

@pytest.mark.parametrize('bad',['scope','digest','quantity','buyer','bid','asof','noticeday','court','allocation','reauction_type','reauction_buyer','receipt_invention','conflict_repair','source','page','promotion'])
def test_wrong_lot_or_unearned_receipt_is_rejected(bad):
 i=fixture();p=i['baoxin_auction_links'];r=next(r for r in p['lots']if r['lot_id']=='jm-400');q=next(r for r in p['lots']if r['lot_id']=='hz-restricted')
 if bad=='scope':i['through']='2026-11-05'
 elif bad=='digest':r['buyer']='changed'
 elif bad=='quantity':r['shares']=6120000
 elif bad=='buyer':r['buyer']='吴栩涵'
 elif bad=='bid':r['steps'][0]['bid_id']='L4934'
 elif bad=='asof':r['registered_as_of']='2026-09-23'
 elif bad=='noticeday':r['registration_notice']='2026-09-18'
 elif bad=='court':r['court']='汕头市金平区人民法院'
 elif bad=='allocation':next(x for x in p['lots']if x.get('allocations'))['allocations'][0]['shares']+=1
 elif bad=='reauction_type':q['share_type']='无限售流通股'
 elif bad=='reauction_buyer':q['steps'][-1]['buyer']='余芳琴'
 elif bad=='receipt_invention':q['status']='registered'
 elif bad=='conflict_repair':p['known_conflicts']['share_after_as_printed']=174101714
 elif bad=='source':r['steps'][-1]['source']['sha256']='0'*64
 elif bad=='page':p['evidence_pages'][0]['text']+='changed'
 elif bad=='promotion':p['method_promotions']=1
 if bad not in ('scope','digest'):seal(i)
 with pytest.raises((ValueError,KeyError)):view(i)

def test_legacy_no_unearned_match():assert auction_links_view({},None)is None
