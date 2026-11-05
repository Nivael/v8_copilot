"""Source-reconciled SZSE daily observed-sample price reference; no model or trading claims."""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import closing
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from canonical_json import digest
from data_refresh import atomic_write_json
import exchange_risk_membership as risk_lists
import market_breadth_history as history
from market_breadth import st_name
from settings import DATA_ROOT, MARKET_CONTEXT_DB

VERSION='szse_st_observed_price_reference_v1'
PLAN_PATH=Path(__file__).with_name('szse_st_reference_plan_v1.json')
PROFILE_PATH=Path(__file__).with_name('szse_st_transitions_v1.json')
PLAN=json.loads(PLAN_PATH.read_text());EVENTS=json.loads(PROFILE_PATH.read_text())['events']
PLAN_DIGEST=digest(PLAN)
ROOT=DATA_ROOT/'local_data/v8_copilot/market_risk'
OUTPUT=ROOT/'szse_st_reference'


def processor_digest():
    return digest({'files':{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                           for name in (Path(__file__).name,PLAN_PATH.name,PROFILE_PATH.name,'canonical_json.py')},
                   'history':history.processor_digest(),'risk_lists':risk_lists.processor_digest()})


PROCESSOR=processor_digest()


def compact(value):return re.sub(r'\s+','',value)


def notice_proofs(directory,now):
    results=[]
    for item in EVENTS:
        raw=(directory/(item['raw_sha256']+'.pdf')).read_bytes();text=(directory/(item['text_sha256']+'.json')).read_bytes()
        pages=json.loads(text)['pages'];observed=datetime.fromisoformat(item['observed_at'])
        first=compact(pages[0]);page=compact(pages[item['proof_page']-1])
        codes={code for group in re.findall(r'证券代码[:：]([0-9、，,]+)',first) for code in re.findall(r'\d{6}',group)}
        if (not raw.startswith(b'%PDF-') or hashlib.sha256(raw).hexdigest()!=item['raw_sha256']
            or hashlib.sha256(text).hexdigest()!=item['text_sha256'] or len(pages)!=item['page_count']
            or item['symbol'] not in codes or item['company'] not in first
            or observed.tzinfo is None or observed>now or item['old_name'] not in first):
            raise ValueError('notice source/identity changed')
        stamp=r'(20\d{2})年(\d{1,2})月(\d{1,2})日'
        if item['date_label']:
            pattern=re.escape(item['date_label'])+r'[:：](?:自)?'+stamp
        else:pattern=r'股票于'+stamp+r'复牌并进入退市整理期'
        dates={date(*map(int,parts)).isoformat() for parts in re.findall(pattern,page)}
        if dates!={item['effective_on']}:raise ValueError('notice effective-date role not matched')
        if item['kind'] in ('warning_added','warning_removed'):
            direction=r'(?:股票|证券)简称[:：]?由[“"]?'+re.escape(item['old_name'])+r'[”"]?(?:变更|变)为[“"]?'+re.escape(item['new_name'])+r'[”"]?'
            if not re.search(direction,page):raise ValueError('notice name direction not matched')
        elif item['kind']=='delisting_period':
            if '进入退市整理期' not in page or '证券简称：'+item['new_name'] not in page:raise ValueError('delisting-period scope not matched')
        elif item['kind']!='listing_end' or item['new_name'] is not None:raise ValueError('undeclared transition kind')
        results.append(dict(item))
    return results


def collect_inputs(*, root=ROOT, market_db=MARKET_CONTEXT_DB, now=None, full=False):
    now=now or datetime.now(timezone.utc)
    hdir=root/'public_breadth_history'
    meta=history.load_breadth_history(hdir,now,snapshot_digest=PLAN['history_digest'])
    if meta['availability']!='observed' or (meta['start'],meta['through'])!=(PLAN['start'],PLAN['through']):raise ValueError('frozen history unavailable')
    frozen=json.loads((hdir/'snapshots'/(PLAN['history_digest']+'.json')).read_text())
    with closing(sqlite3.connect(market_db.resolve().as_uri()+'?mode=ro',uri=True)) as conn:
        conn.row_factory=sqlite3.Row
        anchor=[dict(row) for row in conn.execute('select trade_date,symbol,ts_code,name,risk_type,risk_type_name,source,fetched_at '
                    'from st_membership_daily where trade_date=? and ts_code like ? order by ts_code',(PLAN['anchor_on'],'%.SZ'))]
    if len(anchor)!=PLAN['anchor_members'] or digest(anchor)!=PLAN['anchor_digest']:raise ValueError('dated membership anchor changed')
    for row in anchor:
        fetched=datetime.fromisoformat(row['fetched_at'])
        if (not re.fullmatch(r'[03]\d{5}\.SZ',row['ts_code']) or row['source']!='tushare:stock_st' or not st_name(row['name'])
            or fetched.tzinfo is None or fetched>now):raise ValueError('invalid anchor identity/availability')
    proofs=notice_proofs(root/'szse_st_reference/documents',now)
    codes={row['ts_code'] for row in anchor}|{row['symbol']+'.SZ' for row in proofs}
    days=[]
    for day in frozen['calendar']:
        daily=history._read_day(hdir,frozen['daily_snapshots'][day],day,now,check_raw=full)
        rows=daily['block']['rows']
        # Keep every source-marked code so an unreviewed new entrant cannot disappear.
        days.append({'date':day,'source_marked':sorted(row['ts_code'] for row in rows if st_name(row['security_name'])),
                     'rows':[row for row in rows if row['ts_code'] in codes]})
    rdir=root/'exchange_risk_membership';rraw=json.loads((rdir/'snapshots'/(PLAN['risk_list_digest']+'.json')).read_text())
    if (rraw['version']!=risk_lists.VERSION or rraw['processor_digest']!=risk_lists.PROCESSOR
        or digest({k:v for k,v in rraw.items() if k!='content_digest'})!=PLAN['risk_list_digest']):raise ValueError('frozen exchange-list binding changed')
    listed=risk_lists.project(rraw,rdir,now)
    return {'anchor':anchor,'proofs':proofs,'days':days,'history_digest':meta['content_digest'],
            'history_fetched_at':meta['fetched_at'],'history_materialized_at':meta['materialized_at'],
            'endpoint_list_observed_on':listed['observed_on'],
            'endpoint_members':sorted(row['ts_code'] for row in listed['rows'] if row['venue']=='SZSE' and row['kind']=='risk_warning' and row['share_class']=='A')}


def project(inputs):
    events=inputs['proofs'];days=inputs['days'];anchor=inputs['anchor']
    if not days or days[0]['date']!=PLAN['start'] or days[-1]['date']!=PLAN['through'] or [d['date'] for d in days]!=sorted({d['date'] for d in days}):
        raise ValueError('reference calendar changed')
    keyed={(row['effective_on'],row['symbol']+'.SZ'):row for row in events}
    if len(keyed)!=len(events) or any(row['effective_on'] not in {d['date'] for d in days} for row in events):raise ValueError('duplicate/outside transition')
    previous={row['ts_code']:row['name'] for row in anchor};members=set(previous);seen=set();points=[];all_members=set(members)
    for daily in days:
        day=daily['date'];rows={row['ts_code']:row for row in daily['rows']}
        if len(rows)!=len(daily['rows']):raise ValueError('duplicate source security')
        actual=set(daily['source_marked'])
        for code in sorted(members^actual):
            event=keyed.get((day,code));before=previous.get(code);after=rows.get(code,{}).get('security_name')
            if not event or (before,after)!=(event['old_name'],event['new_name']):raise ValueError('unreviewed or mismatched historical transition')
            adding=code in actual
            if adding!=(event['kind']=='warning_added'):raise ValueError('transition direction/type differs')
            if event['kind']=='listing_end' and after is not None or event['kind']=='delisting_period' and not after.endswith('退'):
                raise ValueError('wrong exit category')
            if adding:members.add(code);all_members.add(code)
            else:members.remove(code)
            seen.add((day,code))
        if members!=actual:raise ValueError('historical members do not reconcile')
        values=[];missing=[]
        for code in sorted(members):
            row=rows.get(code)
            if not row or not row['is_trading']:missing.append(code);continue
            values.append((Decimal(str(row['last']))/Decimal(str(row['prev_close']))-1)*100)
        coverage=len(values)/len(members) if members else 0
        points.append({'date':day,'member_count':len(members),'observed_members':len(values),'coverage_ratio':coverage,'missing_symbols':missing,
                       'daily_return_pct':float(sum(values)/len(values)) if values else None})
        previous={code:row['security_name'] for code,row in rows.items()}
    if seen!=set(keyed) or members!=set(inputs['endpoint_members']):raise ValueError('transition coverage or endpoint set changed')
    ready=all(point['coverage_ratio']>=PLAN['minimum_daily_coverage'] and point['daily_return_pct'] is not None for point in points)
    level=1000.0;peak=0.0;drawdown=0.0
    for point in points:
        if ready:
            level*=1+point['daily_return_pct']/100;point['close']=round(level,8)
            peak=max(peak,level);drawdown=min(drawdown,(level/peak-1)*100)
        else:point['close']=None
    return {'availability':'observed' if ready else 'insufficient_coverage','scope':'SZSE_risk_warning_A_shares_only',
            'start':PLAN['start'],'through':PLAN['through'],'source_venues':['SZSE'],'missing_venues':['SSE'],
            'combined_ST_ready':False,'historical_PIT':False,'portfolio_wealth':False,'effect_measured':False,
            'anchor_on':PLAN['anchor_on'],'anchor_members':len(anchor),'reviewed_transitions':len(events),'distinct_members':len(all_members),
            'member_day_observations':sum(p['member_count'] for p in points),'endpoint_members':len(members),
            'endpoint_list_observed_on':inputs['endpoint_list_observed_on'],'minimum_coverage':min(p['coverage_ratio'] for p in points),
            'coverage_threshold':PLAN['minimum_daily_coverage'],'return_pct':(points[-1]['close']/points[0]['close']-1)*100 if ready else None,
            'max_drawdown_pct':drawdown if ready else None,'points':points,'events':events,
            'source_fetched_at':inputs['history_fetched_at'],'source_materialized_at':inputs['history_materialized_at'],
            'note':'深市风险警示A股的回溯有成交样本价格参考；每日成员按起始名单及生效事项核对，有成交者等权，停牌及缺失不填零。成员和有成交样本会变化，路径不是组合财富或全收益，退出风险警示不代表原股东损益归零。仅深市，尚非沪深整体ST走势，也不证明市场因素优于节点。'}


def reference_status(directory=OUTPUT, *, root=ROOT, market_db=MARKET_CONTEXT_DB, now=None):
    now=now or datetime.now(timezone.utc);base={'version':VERSION,'availability':'missing','combined_ST_ready':False,'effect_measured':False}
    if processor_digest()!=PROCESSOR:return {**base,'availability':'reload_required'}
    try:
        raw=json.loads((directory/'current.json').read_text());observed=datetime.fromisoformat(raw['materialized_at'])
        if (raw['version']!=VERSION or raw['processor_digest']!=PROCESSOR or raw['plan_digest']!=PLAN_DIGEST
            or digest({k:v for k,v in raw.items() if k!='content_digest'})!=raw['content_digest'] or observed.tzinfo is None or observed>now):raise ValueError('invalid reference binding')
        inputs=collect_inputs(root=root,market_db=market_db,now=observed)
        if digest(inputs)!=raw['input_digest']:return {**base,'availability':'source_changed'}
        return {**base,'content_digest':raw['content_digest'],'processor_digest':PROCESSOR,'materialized_at':raw['materialized_at'],**project(inputs)}
    except (OSError,ValueError,KeyError,TypeError,AttributeError,IndexError,sqlite3.Error,ArithmeticError):
        return {**base,'availability':'invalid' if (directory/'current.json').exists() else 'missing'}


def materialize(*,output=OUTPUT,root=ROOT,market_db=MARKET_CONTEXT_DB,now=None):
    now=now or datetime.now(timezone.utc)
    if processor_digest()!=PROCESSOR:raise ValueError('reload before reference materialization')
    if (output/'current.json').exists() and json.loads((output/'current.json').read_text()).get('version')!=VERSION:raise ValueError('foreign output')
    inputs=collect_inputs(root=root,market_db=market_db,now=now,full=True);result=project(inputs)
    raw={'version':VERSION,'processor_digest':PROCESSOR,'plan_digest':PLAN_DIGEST,'input_digest':digest(inputs),'materialized_at':now.isoformat()}
    if processor_digest()!=PROCESSOR or digest(collect_inputs(root=root,market_db=market_db,now=now))!=raw['input_digest']:
        raise ValueError('processor/source changed during reference materialization')
    raw['content_digest']=digest(raw);atomic_write_json(output/'snapshots'/(raw['content_digest']+'.json'),raw);atomic_write_json(output/'current.json',raw)
    return {key:result[key] for key in ('availability','start','through','reviewed_transitions','distinct_members','minimum_coverage','return_pct','max_drawdown_pct')}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args();print(json.dumps(materialize(output=args.output),ensure_ascii=False));return 0


if __name__=='__main__':raise SystemExit(main())
