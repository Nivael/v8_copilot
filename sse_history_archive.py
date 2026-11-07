"""Verify a complete primary SSE historical-price archive without certifying missing-day semantics."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from market_breadth import SOURCES, SSE_SELECT, VERSION as ENDPOINT_VERSION
from market_breadth_refresh import parse_sse
from market_periods import recent_calendar_window
from settings import DATA_ROOT

VERSION = 'sse_historical_price_source_archive_v1'
PARAMS = {'select':'date,close,prevClose,chg_rate,volume,amount','begin':-126,'end':-1,'period':'day'}
REGISTRY_PARAMS = {'sqlId':'COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L','COMPANY_STATUS':'2,3,4,5,7,8','type':'inParams',
                   'isPagination':'true','pageHelp.pageSize':500,'pageHelp.cacheSize':1}
OVERVIEW_PARAMS = {'sqlId':'COMMON_SSE_SJ_GPSJ_CJGK_MRGK_C','PRODUCT_CODE':'01,02,03,11,17','type':'inParams','isPagination':'false'}
QUERY_URL = 'https://query.sse.com.cn/commonQuery.do'
REGISTRY_URL = 'https://query.sse.com.cn/sseQuery/commonQuery.do'
PRICE_URL = 'https://yunhq.sse.com.cn:32042/v1/sh1/dayk/'
ROOT = DATA_ROOT/'local_data/v8_copilot/market_risk'
OUTPUT = ROOT/'sse_history_archive'


def processor_digest():
    return digest({name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in
                   (Path(__file__).name,'market_breadth.py','market_breadth_refresh.py','market_periods.py','market_calendar.py','canonical_json.py')})


PROCESSOR = processor_digest()


def stamp(value, now):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed>now: raise ValueError('unavailable observation timestamp')
    return parsed


def body(folder, ref, now):
    if not re.fullmatch('[a-f0-9]{64}',ref['sha256']): raise ValueError('invalid source key')
    stamp(ref['observed_at'],now)
    data=(folder/(ref['sha256']+'.raw')).read_bytes()
    if len(data)!=ref['bytes'] or hashlib.sha256(data).hexdigest()!=ref['sha256']: raise ValueError('changed source bytes')
    return json.loads(data,parse_float=Decimal)


def ordinary_date(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{8}',value): raise ValueError('undated listing')
    return date.fromisoformat(value[:4]+'-'+value[4:6]+'-'+value[6:]).isoformat()


def read_basis(capture, now):
    raw=json.loads((capture/'universe/complete.json').read_text())
    window=recent_calendar_window(raw['window']['end'])
    if raw['window']!=window or window['availability']!='defined' or window['end']>=now.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat():
        raise ValueError('incomplete or unclosed window')
    registry=defaultdict(list);overviews={};observed=[]
    for ref in raw['source_refs']:
        x=body(capture/'universe',ref,now);params=ref['params'];sql=params['sqlId']
        observed_on=stamp(ref['observed_at'],now).astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
        if x.get('actionErrors')!=[] or x.get('fieldErrors')!={} or x['sqlId']!=sql: raise ValueError('upstream source error')
        if sql==REGISTRY_PARAMS['sqlId']:
            if x['pageHelp']['data']!=x['result']: raise ValueError('source result/page mismatch')
            board=params['STOCK_TYPE'];page=params['pageHelp.pageNo']
            if observed_on<window['end']: raise ValueError('registry observation predates the represented window end')
            expected={**REGISTRY_PARAMS,'STOCK_TYPE':board,'pageHelp.pageNo':page,'pageHelp.beginPage':page,'pageHelp.endPage':page}
            if ref['url']!=REGISTRY_URL or params!=expected or board not in ('1','8') or type(page) is not int or page<1:
                raise ValueError('filtered/foreign registry query')
            h=x['pageHelp'];total=h['total']
            if (x['isPagination']!='true' or type(total) is not int or not 0<total<10000 or h['pageNo']!=page or h['pageSize']!=500
                or h['pageCount']!=(total+499)//500 or len(x['result'])!=min(500,total-(page-1)*500)):
                raise ValueError('incomplete registry page')
            registry[board].append((page,total,x['result']))
        elif sql==OVERVIEW_PARAMS['sqlId']:
            day=params['SEARCH_DATE']
            if observed_on<day: raise ValueError('daily-total observation predates its market date')
            if ref['url']!=QUERY_URL or params!={**OVERVIEW_PARAMS,'SEARCH_DATE':day} or day not in window['calendar'] or day in overviews:
                raise ValueError('foreign/repeated daily total')
            groups={r['PRODUCT_CODE']:r for r in x['result']}
            if (x['isPagination']!='false' or len(groups)!=len(x['result'])
                or not {'01','02','03','17'}<=set(groups) or not set(groups)<={'01','02','03','11','17'}):
                raise ValueError('daily board coverage changed')
            if any(r['TRADE_DATE']!=day.replace('-','') or not re.fullmatch(r'\d+',r['LIST_NUM']) for r in groups.values()):
                raise ValueError('undated daily total')
            counts={code:int(r['LIST_NUM']) for code,r in groups.items()}
            if counts['17']!=counts['01']+counts['02']+counts['03']: raise ValueError('daily listing total disagrees')
            overviews[day]=counts
        else: raise ValueError('undeclared basis source')
        observed.append(ref['observed_at'])
    if set(registry)!={'1','8'} or set(overviews)!=set(window['calendar']): raise ValueError('partial historical scope')
    all_rows={}
    for board,pages in registry.items():
        pages.sort();total=pages[0][1]
        if [p[0] for p in pages]!=list(range(1,(total+499)//500+1)) or any(p[1]!=total for p in pages): raise ValueError('registry paging gap')
        for _,_,rows in pages:
            for r in rows:
                code=r['A_STOCK_CODE']
                if not re.fullmatch(r'60\d{4}' if board=='1' else r'68\d{4}',code) or code in all_rows or r['STOCK_TYPE']!=board:
                    raise ValueError('registry is not unique ordinary A shares')
                listed=ordinary_date(r['LIST_DATE']);ended=ordinary_date(r['DELIST_DATE']) if r['DELIST_DATE']!='-' else None
                if ended and ended<=listed: raise ValueError('listing chronology changed')
                all_rows[code]={'code':code,'listed_on':listed,'ended_on':ended,'observed_name':r['COMPANY_ABBR'],'board':board}
    pool={code:r for code,r in all_rows.items() if r['listed_on']<=window['end'] and (r['ended_on'] is None or r['ended_on']>window['start'])}
    populations={}
    for day in window['calendar']:
        active=sorted(code for code,r in pool.items() if r['listed_on']<=day and (r['ended_on'] is None or r['ended_on']>day))
        main=sum(code.startswith('60') for code in active);star=len(active)-main
        if (main,star)!=(overviews[day]['01'],overviews[day]['03']): raise ValueError('historical population does not reconcile')
        populations[day]=active
    return {'window':window,'pool':pool,'populations':populations,'all_registry_rows':len(all_rows),
            'source_refs':raw['source_refs'],'basis_capture_digest':digest(raw),'endpoint_digest':raw['endpoint_snapshot'],
            'basis_fetched_at':max(observed,key=lambda value:stamp(value,now))}


def read_endpoint(directory, key, through, now):
    if not re.fullmatch('[a-f0-9]{64}',key): raise ValueError('invalid endpoint key')
    raw=json.loads((directory/'snapshots'/(key+'.json')).read_text())
    if (digest({k:v for k,v in raw.items() if k!='content_digest'})!=key or raw['content_digest']!=key
        or raw['contract_version']!=ENDPOINT_VERSION or raw['sources']!=SOURCES or raw['requested_through']!=through):
        raise ValueError('endpoint binding changed')
    fetched=stamp(raw['fetched_at'],now);pages=[]
    if fetched.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()<through: raise ValueError('endpoint observation predates quote date')
    refs=[r for r in raw['responses'] if r['venue']=='SSE']
    for i,ref in enumerate(refs):
        if ref['url']!=SOURCES['SSE']['api_url'] or ref['params']!={'select':SSE_SELECT,'begin':i*500,'end':(i+1)*500}:
            raise ValueError('endpoint source scope changed')
        observed=stamp(ref['observed_at'],now)
        # The owning legacy snapshot's fetched_at is collection start; cached
        # pages can precede it and freshly collected pages can follow it.
        if observed.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()<through:
            raise ValueError('endpoint source observation chronology differs')
        data=(directory/'responses'/(ref['response_sha256']+'.json')).read_bytes()
        if hashlib.sha256(data).hexdigest()!=ref['response_sha256'] or len(data)!=ref['bytes']: raise ValueError('endpoint original changed')
        pages.append(json.loads(data))
    if parse_sse(pages,through)!=raw['venues']['SSE']: raise ValueError('endpoint normalization changed')
    return {r['ts_code'][:6]:r for r in raw['venues']['SSE']['rows']}


def parse_prices(payload, ref, basis, now):
    code=ref['code'];params=ref['params'];seen=[];records={};observed=stamp(ref['observed_at'],now)
    if params!=PARAMS or ref['url']!=PRICE_URL+code or payload['code']!=code or code not in basis['pool']: raise ValueError('price source identity changed')
    total,begin,end=payload['total'],payload['begin'],payload['end'];lines=payload['kline']
    if (any(type(v) is not int for v in (total,begin,end)) or total<=0 or end!=total or begin!=max(0,total+PARAMS['begin']+1)
        or len(lines)!=end-begin): raise ValueError('price source pagination incomplete')
    for values in lines:
        if not isinstance(values,list) or len(values)!=6 or type(values[0]) is not int: raise ValueError('price columns/date changed')
        day=ordinary_date(str(values[0]));seen.append(day)
        if day>observed.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat(): raise ValueError('future market date')
        if not basis['window']['start']<=day<=basis['window']['end']: continue  # Includes an explicitly excluded unclosed current day.
        if day not in basis['populations'] or code not in basis['populations'][day]: raise ValueError('quote outside historical listing population')
        last,previous,change,volume,amount=values[1:]
        def number(v): return not isinstance(v,bool) and isinstance(v,(int,Decimal)) and Decimal(v).is_finite()
        if any(not number(v) or v<0 for v in (volume,amount)) or (volume==0)!=(amount==0): raise ValueError('invalid historical activity')
        active=volume>0
        if active and (any(not number(v) for v in (last,previous,change)) or min(last,previous)<=0
                       or abs((Decimal(last)/Decimal(previous)-1)*100-Decimal(change))>Decimal('.015')): raise ValueError('invalid close/reference/rounded change')
        records[day]={'last':str(last) if number(last) else None,'prev_close':str(previous) if number(previous) else None,
                      'volume':str(volume),'amount':str(amount),'is_trading':active}
    if seen!=sorted(set(seen)): raise ValueError('duplicate/unsorted historical dates')
    return records


def project(capture, endpoint_dir, now):
    basis=read_basis(capture,now);plan=json.loads((capture/'full_prices/plan.json').read_text())
    expected_plan={'version':'sse_full_price_capture_plan_v1','through':basis['window']['end'],'start':basis['window']['start'],
                   'basis_digest':basis['basis_capture_digest'],'codes':sorted(basis['pool']),'params':PARAMS}
    raw=json.loads((capture/'full_prices/complete.json').read_text())
    if (plan!=expected_plan or raw['version']!='sse_full_price_capture_v1' or raw['plan_digest']!=digest(plan) or raw['status']!='captured'):
        raise ValueError('incomplete/changed capture plan')
    started=stamp(raw['started_at'],now);completed=stamp(raw['completed_at'],now)
    if started>completed: raise ValueError('invalid capture interval')
    refs=raw['source_refs']
    if [r['code'] for r in refs]!=sorted(basis['pool']) or any(r['status']!='captured' for r in refs): raise ValueError('missing or duplicate security archive')
    endpoint=read_endpoint(endpoint_dir,basis['endpoint_digest'],basis['window']['end'],now)
    if set(endpoint)!=set(basis['populations'][basis['window']['end']]): raise ValueError('endpoint population differs')
    by_day=defaultdict(dict);source_times=[]
    for ref in refs:
        if stamp(ref['observed_at'],now)>completed: raise ValueError('price captured after completion')
        records=parse_prices(body(capture/'full_prices',ref,now),ref,basis,now);source_times.append(ref['observed_at'])
        for day,row in records.items(): by_day[day][ref['code']]=row
        old=endpoint.get(ref['code']);actual=records.get(basis['window']['end'])
        if old and old['is_trading']:
            if not actual or not actual['is_trading'] or any(Decimal(actual[k])!=Decimal(str(old[k])) for k in ('last','prev_close','volume','amount')):
                raise ValueError('last closed-day quote conflicts with independent cross-section')
        elif old and actual and actual['is_trading']: raise ValueError('inactive endpoint has a trade')
    days=[]
    for day,codes in basis['populations'].items():
        rows=by_day[day];missing=[code+'.SH' for code in codes if code not in rows];inactive=[code+'.SH' for code,r in rows.items() if not r['is_trading']]
        days.append({'date':day,'listed_members':len(codes),'observed_trading':sum(r['is_trading'] for r in rows.values()),
                     'explicit_nontrading':inactive,'not_returned':missing,'unclosed_observations_included':False})
    return {'version':VERSION,'availability':'observed','start':basis['window']['start'],'through':basis['window']['end'],
            'historical_breadth_ready':False,'historical_ST_ready':False,'historical_PIT':False,'effect_measured':False,
            'distinct_securities':len(basis['pool']),'expected_security_days':sum(len(c) for c in basis['populations'].values()),
            'price_responses':len(refs),'observed_trading_days':sum(d['observed_trading'] for d in days),
            'not_returned_days':sum(len(d['not_returned']) for d in days),'explicit_nontrading_days':sum(len(d['explicit_nontrading']) for d in days),
            'new_listings':[r for r in basis['pool'].values() if r['listed_on']>=basis['window']['start']],
            'ended_listings':[r for r in basis['pool'].values() if r['ended_on'] is not None and r['ended_on']<=basis['window']['end']],
            'registry_source_rows':basis['all_registry_rows'],'basis_responses':len(basis['source_refs']),
            'source_fetched_at':max(source_times,key=lambda value:stamp(value,now)),
            'first_price_observed_at':min(source_times,key=lambda value:stamp(value,now)),'basis_fetched_at':basis['basis_fetched_at'],
            'endpoint_compared_trading':sum(r['is_trading'] for r in endpoint.values()),'days':days,
            'note':'沪市历史挂牌范围及逐证券价格原件已核对；缺日未自动认作停牌或填零，尚未形成完整历史涨跌分布或历史ST成员/走势。每日名称不由本次简称回填，当前未闭合的历史停复牌依据需另行核实。'}


def input_key(capture):
    return digest({name:json.loads((capture/name).read_text()) for name in ('universe/complete.json','full_prices/plan.json','full_prices/complete.json')})


def archive_status(directory=OUTPUT, *, endpoint_dir=ROOT/'public_breadth', now=None):
    now=now or datetime.now(timezone.utc);base={'version':VERSION,'availability':'missing','historical_breadth_ready':False,'historical_ST_ready':False,'effect_measured':False}
    if processor_digest()!=PROCESSOR: return {**base,'availability':'reload_required'}
    try:
        raw=json.loads((directory/'current.json').read_text());stamp(raw['materialized_at'],now)
        if (raw['version']!=VERSION or raw['processor_digest']!=PROCESSOR or digest({k:v for k,v in raw.items() if k!='content_digest'})!=raw['content_digest']
            or not re.fullmatch('[a-f0-9]{64}',raw['input_digest'])): raise ValueError('archive binding changed')
        capture=directory/'sources'/raw['input_digest']
        if input_key(capture)!=raw['input_digest']: raise ValueError('capture index changed')
        result=project(capture,endpoint_dir,datetime.fromisoformat(raw['materialized_at']))
        if processor_digest()!=PROCESSOR: return {**base,'availability':'reload_required'}
        return {**result,'content_digest':raw['content_digest'],
                'processor_digest':PROCESSOR,'materialized_at':raw['materialized_at']}
    except (OSError,ValueError,KeyError,TypeError,AttributeError,IndexError,ArithmeticError):
        return {**base,'availability':'invalid' if (directory/'current.json').exists() else 'missing'}


def materialize(capture, *, output=OUTPUT, endpoint_dir=ROOT/'public_breadth', now=None):
    now=now or datetime.now(timezone.utc)
    if processor_digest()!=PROCESSOR: raise ValueError('reload changed code')
    if (output/'current.json').exists() and json.loads((output/'current.json').read_text()).get('version')!=VERSION: raise ValueError('foreign output')
    result=project(capture,endpoint_dir,now);key=input_key(capture);target=output/'sources'/key
    def preserve_copy(src,dst,expected=None):
        data=src.read_bytes()
        if expected is not None and hashlib.sha256(data).hexdigest()!=expected: raise ValueError('source changed during copy')
        if dst.exists():
            if dst.read_bytes()!=data: raise ValueError('immutable archive differs')
            return
        dst.parent.mkdir(parents=True,exist_ok=True);tmp=dst.with_suffix(dst.suffix+'.tmp');tmp.write_bytes(data);tmp.replace(dst)
    for name in ('universe/complete.json','full_prices/plan.json','full_prices/complete.json'):
        preserve_copy(capture/name,target/name)
    for group,index in (('universe','universe/complete.json'),('full_prices','full_prices/complete.json')):
        refs=json.loads((capture/index).read_text())['source_refs']
        for ref in refs:
            src=capture/group/(ref['sha256']+'.raw');dst=target/group/src.name
            preserve_copy(src,dst,ref['sha256'])
    if project(target,endpoint_dir,now)!=result or processor_digest()!=PROCESSOR or input_key(capture)!=key: raise ValueError('sources/code changed during materialization')
    raw={'version':VERSION,'processor_digest':PROCESSOR,'input_digest':key,'materialized_at':now.isoformat()};raw['content_digest']=digest(raw)
    atomic_write_json(output/'snapshots'/(raw['content_digest']+'.json'),raw);atomic_write_json(output/'current.json',raw)
    return {k:result[k] for k in ('availability','distinct_securities','expected_security_days','observed_trading_days','not_returned_days')}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--capture',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(materialize(args.capture),ensure_ascii=False));return 0


if __name__=='__main__': raise SystemExit(main())
