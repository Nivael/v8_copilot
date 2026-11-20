import sqlite3,json,hashlib
from pathlib import Path
from collections import Counter
import argparse
parser=argparse.ArgumentParser(description='Read-only source replication metadata audit; does not assess empirical case independence.')
parser.add_argument('--data-dir',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
base=args.data_dir
def load(name,table):
 c=sqlite3.connect('file:'+str(base/name)+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
 rows=[dict(r) for r in c.execute('select * from '+table+' order by 1')];c.close();return rows
experiences=load('experience_repository.sqlite3','experiences');runs=load('research_run_ledger.sqlite3','research_runs');byid={r['run_id']:r for r in runs}
def sha(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
rows=[]
for r in experiences:
 x=json.loads(r['payload_json']);refs=sorted(set(x['source_run_refs']));found=[byid[t] for t in refs if t in byid];packs=[tuple(sorted(json.loads(t['evidence_pack_ids_json']))) for t in found]
 rows.append({'experience_id':r['experience_id'],'status':r['status'],'not_evidence':bool(r['not_evidence']),'source_refs':len(refs),'found_runs':len(found),'valid_runs':sum(json.loads(t['validation_report_json']).get('valid')is True for t in found),'distinct_evidence_pack_sets':len(set(packs)),'repeated_evidence_pack_sets':len(packs)-len(set(packs)),'distinct_question_texts':len({t['question_text'] for t in found}),'distinct_object_ref_sets':len({tuple(sorted(json.loads(t['object_refs_json']))) for t in found})})
result={'scope':'read-only operational experience inventory; repeated pack identifiers do not prove identical empirical cases, different identifiers do not prove independent cases','experience_count':len(experiences),'run_count':len(runs),'status_counts':dict(Counter(r['status'] for r in experiences)),'all_records_marked_not_evidence':all(r['not_evidence'] for r in experiences),'experience_rows_digest':sha(experiences),'research_rows_digest':sha(runs),'records':rows,'policy_source_sha256':hashlib.sha256(Path('experience_auto_accept.py').read_bytes()).hexdigest(),'contract_source_sha256':hashlib.sha256(Path('experience_contract.py').read_bytes()).hexdigest(),'method_promotions_this_audit':0}
args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='records'},ensure_ascii=False,indent=2))
print('accepted_with_repeated_pack_sets',sum(r['status']=='accepted' and r['repeated_evidence_pack_sets']>0 for r in rows))
