import sqlite3,json,hashlib,math
from pathlib import Path
from collections import Counter
import argparse
parser=argparse.ArgumentParser(description='Read-only audit of saved ST activity price-bound coverage; not a full-market exit indicator.')
parser.add_argument('--database',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
p=args.database
def valid(v): return isinstance(v,(int,float)) and math.isfinite(v) and v>0
def same(a,b): return a is not None and b is not None and abs(a-b)<=max(.0001,abs(b)*1e-6)
def digest(rows): return hashlib.sha256(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
c=sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True)
c.execute('begin')
snapshots=c.execute('select * from activity_snapshots order by snapshot_id').fetchall()
q='''with ranked as (select s.*,row_number() over(partition by trade_date order by fetched_at desc,snapshot_id desc) r from activity_snapshots s where daily_row_count>0 and daily_basic_row_count>0 and limit_row_count>0) select d.snapshot_id,d.symbol,d.trade_date,d.payload_json from ranked s join market_activity_daily d on d.snapshot_id=s.snapshot_id where s.r=1 order by d.trade_date,d.symbol'''
rows=c.execute(q).fetchall();counts=Counter(); affected=[];days={}; counts_by_day={}
for sid,sym,day,raw in rows:
 x=json.loads(raw); k=counts_by_day.setdefault(day,Counter()); k['rows']+=1
 complete=valid(x['up_limit']) and valid(x['down_limit'])
 k['both_positive_bounds' if complete else 'incomplete_bounds']+=1
 flat=all(valid(x[v]) for v in ('open','high','low','close')) and same(x['open'],x['high']) and same(x['high'],x['low']) and same(x['low'],x['close'])
 hit=same(x['close'],x['up_limit']) or same(x['close'],x['down_limit'])
 if flat and not complete and not hit:
  k['flat_unresolved_by_raw_bounds']+=1
  if x['limit_status'] is None and x['one_price_limit'] is False:
   k['stored_false_without_vendor_or_complete_bounds']+=1
   affected.append({'snapshot_id':sid,'symbol':sym,'trade_date':day,'was_eligible':x['eligible_for_anomaly']})
 for name in ('limit_state_conflict','eligible_for_anomaly'):
  if x[name]: k[name]+=1
for k in counts_by_day.values(): counts.update(k)
result={'scope':'latest qualifying snapshot per saved day, exactly repository latest_facts selection; ST activity only, not full market','database_name':p.name,'snapshots_count':len(snapshots),'snapshot_metadata_digest':digest(snapshots),'selected_payload_digest':digest(rows),'counts':dict(counts),'date_start':min(counts_by_day) if rows else None,'date_end':max(counts_by_day) if rows else None,'dates_count':len(counts_by_day),'target_recent_start':'2026-11-09','target_recent_end':'2026-11-20','target_recent_saved_rows':sum(v['rows'] for d,v in counts_by_day.items() if '2026-11-09'<=d<='2026-11-20'),'affected':affected,'daily':{d:dict(v) for d,v in sorted(counts_by_day.items())},'limits':['Normalized stored bounds do not certify independently replayable exchange originals.','No writes, no restatement of saved snapshots.','No claim of complete-market coverage, limitdown counts, queue availability or executable exit.']}
assert sum(v['rows'] for v in counts_by_day.values())==len(rows)
assert len({(r[1],r[2]) for r in rows})==len(rows)
args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ('daily','affected','limits')},ensure_ascii=False,indent=2))
c.rollback();c.close()
