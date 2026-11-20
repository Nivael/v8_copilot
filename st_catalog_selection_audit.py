"""Audit saved catalog selection. Title matches are leads, never body facts."""
from __future__ import annotations
import html
import re
from collections import defaultdict

RULES=(
 ('cash_receipt',r'收到.*(款|资金|偿还|回款|支付)|款.*到账|支付完毕|资金占用.*(归还|偿还|清偿)|(赠与|捐赠).*进展'),
 ('judicial_change',r'法院.*(受理|裁定)|裁定.*(重整|清算|破产)|判决.*生效|终结.*(诉讼|执行)|决定.*(终止上市|摘牌)'),
 ('transaction_termination',r'终止.*(投资|重组|重整|交易)|解除.*(投资|重组|重整|交易)'),
)
AUXILIARY=re.compile(r'核查意见|说明会|自查报告|法律意见|独立财务顾问')

def _title(value):
 return re.sub(r'\s+','',html.unescape(re.sub('<[^>]*>','',str(value or ''))))

def selected_ids(value):
 """File identity in a source descriptor is not certification it was fully read."""
 found=set()
 def walk(o):
  if isinstance(o,dict):
   if re.fullmatch(r'\d+',str(o.get('announcement_id',''))) and re.fullmatch(r'[0-9a-fA-F]{64}',str(o.get('sha256',''))):found.add(str(o['announcement_id']))
   for v in o.values():walk(v)
  elif isinstance(o,list):
   for v in o:walk(v)
 walk(value)
 return found

def audit_catalog_selection(captures,selected,*,fixed_symbols,protected_ids=()):
 groups=defaultdict(list)
 for c in captures:groups[(c['query_id'],c['symbol'])].append(c)
 queries=[];all_rows={};conflicts=[]
 for (query,symbol),pages in sorted(groups.items()):
  errors=[];pages=sorted(pages,key=lambda p:p['page_number']);numbers=[p['page_number'] for p in pages]
  if numbers!=list(range(1,len(pages)+1)):errors.append('missing_or_duplicate_page')
  declared_totals=[p['payload'].get('totalAnnouncement') for p in pages]
  totals={n for n in declared_totals if isinstance(n,int) and not isinstance(n,bool) and n>=0}
  if len(totals)!=1 or len(declared_totals)!=sum(isinstance(n,int) and not isinstance(n,bool) and n>=0 for n in declared_totals):errors.append('inconsistent_total')
  rows=[]
  for index,c in enumerate(pages):
   d=c['payload'];r=d.get('announcements')
   if not isinstance(r,list):errors.append('unreadable_announcements');continue
   if d.get('hasMore') is not (index<len(pages)-1):errors.append('has_more_not_settled')
   if any(str(a.get('secCode',''))!=symbol for a in r):errors.append('subject_mismatch')
   rows.extend((a,c) for a in r)
  ids=[str(a.get('announcementId','')) for a,_ in rows]
  if any(not re.fullmatch(r'\d+',i) for i in ids):errors.append('invalid_announcement_id')
  if len(set(ids))!=len(ids):errors.append('duplicate_announcement')
  if len(totals)==1 and len(rows)!=next(iter(totals)):errors.append('row_count_mismatch')
  if symbol not in fixed_symbols:errors.append('outside_fixed_scope')
  queries.append({'query_id':query,'symbol':symbol,'status':'unverified' if errors else 'saved_pagination_complete','errors':sorted(set(errors)),'rows':len(rows),'pages':len(pages),'provider_totalpages_values':[p['payload'].get('totalpages') for p in pages],'captures':[{'page_number':p['page_number'],'sha256':p['sha256'],'locator':p['locator']} for p in pages]})
  if errors:continue
  for a,c in rows:
   aid=str(a['announcementId']);title=_title(a['announcementTitle']);path=str(a.get('adjunctUrl',''))
   date=re.search(r'finalpage/(\d{4}-\d{2}-\d{2})/',path)
   entry={'announcement_id':aid,'symbol':symbol,'name':a.get('secName',''),'title':title,'url':path if path.startswith('https://') else 'https://static.cninfo.com.cn/'+path,'published_on':date[1] if date else None,'catalog_query':query,'catalog_page':c['page_number'],'catalog_sha256':c['sha256']}
   if aid in all_rows and any(entry[k]!=all_rows[aid][k] for k in ['symbol','title','url','published_on']):conflicts.append(aid)
   else:all_rows[aid]=entry
 protected=set(map(str,protected_ids));selected=set(map(str,selected));candidates=[];matched=0
 for aid,row in sorted(all_rows.items()):
  if aid in conflicts:continue
  rules=[name for name,pattern in RULES if re.search(pattern,row['title'])]
  if not rules:continue
  matched+=1
  if aid in selected:continue
  candidates.append({**row,'rules':rules,'supporting_document_title':bool(AUXILIARY.search(row['title'])),'selected_source_identity_present':False,'body_status':'not_evaluated_by_this_audit','protected_id':aid in protected,'classification':'title_lead_not_confirmed_omission'})
 complete={q['symbol'] for q in queries if q['status']=='saved_pagination_complete'}
 return {'version':'saved_catalog_selection_audit_v1','queries':queries,'identity_conflicts':sorted(set(conflicts)),'candidates':candidates,'counts':{'capture_pages':len(captures),'saved_queries':len(queries),'pagination_complete_queries':sum(q['status']=='saved_pagination_complete' for q in queries),'symbols_with_complete_saved_queries':len(complete),'fixed_symbols':len(fixed_symbols),'fixed_symbols_without_complete_saved_query':len(set(fixed_symbols)-complete),'unique_catalog_announcements':len(all_rows),'matched_titles':matched,'unselected_title_leads':len(candidates),'unselected_primary_title_leads':sum(not c['supporting_document_title'] for c in candidates),'unselected_supporting_title_leads':sum(c['supporting_document_title'] for c in candidates)},'uncovered_fixed_symbols':sorted(set(fixed_symbols)-complete),'boundary':'Complete pagination applies only to these saved queries. Title leads are not established body facts, proven omissions, a complete event census, or independent cases.'}

def main(argv=None):
 """Rerun a saved audit without networking or changing research state."""
 import argparse
 import json
 from pathlib import Path
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--captures',required=True,help='JSON list of saved page payloads with identity and SHA provenance')
 parser.add_argument('--selected-ids',required=True,help='JSON list of selected source IDs at the declared audit baseline')
 parser.add_argument('--fixed-symbols',required=True,help='JSON list of fixed-cohort symbols')
 parser.add_argument('--protected-ids',help='Optional JSON list used only to flag protected title leads')
 parser.add_argument('--output',required=True)
 args=parser.parse_args(argv)
 read=lambda p:json.loads(Path(p).read_text())
 result=audit_catalog_selection(read(args.captures),set(read(args.selected_ids)),fixed_symbols=set(read(args.fixed_symbols)),protected_ids=read(args.protected_ids) if args.protected_ids else ())
 Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 return 2 if result['identity_conflicts'] or any(q['status']=='unverified' for q in result['queries']) else 0

if __name__=='__main__':
 raise SystemExit(main())
