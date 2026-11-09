from pathlib import Path
import json,gzip
from copy import deepcopy
import pytest
from canonical_json import digest
from st_official_pdf_audit import official_pdf_audit

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/official-pdf-audit.json.gz').read_bytes()))
def view(i):return official_pdf_audit(i,i['test_ann'])
def seal(i):
 p=i['official_pdf_audit'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_official_bytes_are_same_documents_not_new_facts_or_sse_direct_verification():
 i=fixture();old=deepcopy(i);v=view(i);assert i==old
 assert(v['official_copies'],v['affected_companies'],v['pages'],v['byte_identical'])==(8,7,24,8)
 assert(v['remaining_official_copy_gaps'],v['remaining_sse_direct_gaps'])==(0,8)
 assert v['new_facts']==v['new_unique_documents']==v['method_promotions']==0
 assert all(r['official_sha256']==r['mirror_sha256']and not r['sse_direct_verified']for r in v['rows'])
 assert len([r for r in v['rows']if r['sse_attempt']['status']==200])==7
@pytest.mark.parametrize('bad',['digest','scope','inventory','bytes','symbol','metadata_symbol','metadata_id','title','url','date','old_url','sse','http200','promotion','newfacts','gate'])
def test_false_corroboration_is_rejected(bad):
 i=fixture();p=i['official_pdf_audit'];r=p['rows'][0]
 if bad=='digest':p['content_digest']='bad'
 elif bad=='scope':i['through']='2026-11-05'
 elif bad=='inventory':p['rows'].pop()
 elif bad=='bytes':r['official_sha256']='different'
 elif bad=='symbol':r['symbol']='600360'
 elif bad=='metadata_symbol':r['metadata']['secCode']='600360'
 elif bad=='metadata_id':r['metadata']['announcementId']='wrong'
 elif bad=='title':r['official_title']='wrong'
 elif bad=='url':r['official_url']='https://example.invalid/'+r['metadata']['adjunctUrl']
 elif bad=='date':r['published_on']='2026-05-20'
 elif bad=='old_url':r['mirror_url']='changed'
 elif bad=='sse':r['sse_direct_verified']=True
 elif bad=='http200':r['sse_attempt']['pdf']=True
 elif bad=='promotion':p['method_promotions']=1
 elif bad=='newfacts':p['new_facts']=8
 elif bad=='gate':r['protected_gate_passed']=False
 if bad!='digest':seal(i)
 with pytest.raises(ValueError):view(i)
def test_missing_packet_is_compatible():assert official_pdf_audit({}, {})is None
