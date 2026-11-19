from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import gzip,json
import pytest
from canonical_json import digest
from st_xilv_liability import xilv_liability

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-xilv-liability.json.gz').read_bytes()))
def seal(i):
 p=i['xilv_liability'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_financing_and_litigation_are_six_chains_not_ten_independent_cases():
 i=fixture();old=deepcopy(i);v=xilv_liability(i,i['test_timeline']);assert i==old
 assert v['counts']=={'new_files':10,'new_pages':29,'chains':6,'source_disclosures':10,'complete_windows':29,'incomplete_windows':1}
 assert len(v['chains'][1]['steps'])==3
 assert '不是新增到账'in v['chains'][0]['status']
 assert v['arithmetic']['claim_requested_sum_excluding_other_costs_yuan']=='45147673.22'
 assert v['arithmetic']['cumulative_total_wanyuan']=='1134.00'
 assert v['arithmetic']['not_recognized_losses']and v['method_promotions']==0
 assert v['chains'][-1]['steps'][0]['source']['document_dated_on']=='2026-11-04'
 assert v['chains'][-1]['steps'][0]['windows'][-1]['stock_pct']is None
 assert v['chains'][3]['steps'][0]['windows'][0]['anchor']=='2026-10-09'

@pytest.mark.parametrize('bad',['binding','identity','date','printed','pages','duplicate','cash','rollover','guarantee','execution','party','claim','scope','direction'])
def test_resealed_changes_cannot_turn_quotas_into_cash_or_requests_into_losses(bad):
 i=fixture();p=i['xilv_liability'];s=p['sources'][0]
 if bad=='binding':p['timeline_digest']='bad'
 elif bad=='identity':s['raw_item']['secCode']='000609'
 elif bad=='date':s['published_on']='2026-11-20'
 elif bad=='printed':s['document_dated_on']='2026-01-01'
 elif bad=='pages':s['selected_pages'].pop('1')
 elif bad=='duplicate':p['sources'].append(deepcopy(s))
 else:
  aid,n,token={'cash':('1225435983','1','5月22日'),'rollover':('1225588596','1','2026年6月25日'),'guarantee':('1225435982','2','尚未与银行签订担保协议'),'execution':('1225599714','1','尚未收到'),'party':('1225603727','1','甘肃第六建设集团股份有限公司'),'claim':('1225603727','2','3,368,363.78'),'scope':('1225658225','1','除前期已披露'),'direction':('1225658225','3','原告/申请人')}[bad];s=next(x for x in p['sources']if x['announcement_id']==aid);s['selected_pages'][n]=s['selected_pages'][n].replace(token,'changed');s['page_hashes'][int(n)-1]=sha256(s['selected_pages'][n].encode()).hexdigest()
 seal(i)
 with pytest.raises(ValueError):xilv_liability(i,i['test_timeline'])

def test_absence_keeps_legacy_view():assert xilv_liability({},None)is None
