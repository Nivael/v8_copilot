"""Read-only, source-bound observations for a 1–4 week rebound research queue."""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import parse_qs,urlsplit
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from settings import DATA_ROOT

ROOT=DATA_ROOT/'local_data/v8_copilot/market_risk'
OUTPUT=ROOT/'trader_observations/swing_watch'
VERSION='trader_swing_reading_v1'
DATED_VERSION='trader_swing_reading_v2'
RULES={'twenty_day_change_lte_pct':-15,'from_window_high_lte_pct':-20,'five_day_change_gt_pct':0,
       'five_day_change_lte_pct':15,'from_twenty_day_low_lte_pct':20,'latest_amount_gte_yuan':10_000_000,'latest_close_gte_yuan':1}


def processor_digest():
    return digest({name:sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                   for name in (Path(__file__).name,'workbench_views.py','market_breadth_refresh.py','market_breadth_export.py','market_breadth_history.py','market_periods.py','market_calendar.py','exchange_risk_membership.py','market_close_membership.py','canonical_json.py')})


def packet(path):
    value=json.loads(path.read_text())
    if digest({k:v for k,v in value.items() if k!='content_digest'})!=value['content_digest']:raise ValueError('observation packet changed')
    return value


def source_bytes(directory,ref,extension):
    raw=(directory/'responses'/(ref['response_sha256']+'.'+extension)).read_bytes()
    if sha256(raw).hexdigest()!=ref['response_sha256'] or ref.get('bytes',len(raw))!=len(raw):raise ValueError('closing source changed')
    return raw


def closing_day(root,through,venue):
    from market_breadth import validate_venue,SSE_SELECT
    from market_breadth_refresh import parse_sse
    from market_breadth_export import parse_export
    directory=root/'trader_observations'/through/'closing_breadth';value=packet(directory/(venue.lower()+'_close.json'))
    stamp=datetime.fromisoformat(value['observed_at']);now=datetime.now(timezone.utc)
    if (value['version']!='trader_single_venue_close_v1' or value['venue']!=venue or value['through']!=through
        or stamp.tzinfo is None or stamp>now or through>=now.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()):
        raise ValueError('closing observation is not a completed dated session')
    refs=value['responses']
    if venue=='SSE':
        pages=[]
        for index,ref in enumerate(refs):
            if (ref['url']!='https://yunhq.sse.com.cn:32042/v1/sh1/list/exchange/equity'
                or ref['params']!={'select':SSE_SELECT,'begin':index*500,'end':(index+1)*500}):raise ValueError('closing source scope changed')
            pages.append(json.loads(source_bytes(directory,ref,'json')))
        block=parse_sse(pages,through)
    else:
        if len(refs)!=3 or value.get('source_control')!='complete_xlsx_with_independent_first_and_last_json_pages':raise ValueError('incomplete closing controls')
        originals=[]
        for index,ref in enumerate(refs):
            url=urlsplit(ref['url']);params=parse_qs(url.query)
            expected={'SHOWTYPE':['xlsx' if index==2 else 'JSON'],'CATALOGID':['1815_stock_snapshot'],'txtBeginDate':[through],'txtEndDate':[through]}
            if index<2:expected.update(TABKEY=['tab1'],PAGENO=['1' if index==0 else str((value['block']['reported_total']+9)//10)])
            if (url.scheme not in ('http','https') or url.netloc not in ('www.szse.cn','fund.szse.cn')
                or url.path!=('/api/report/ShowReport' if index==2 else '/api/report/ShowReport/data') or params!=expected):
                raise ValueError('closing export query changed')
            body=source_bytes(directory,ref,'xlsx' if index==2 else 'json');originals.append(body if index==2 else json.loads(body))
        block=parse_export(originals[2],originals[0],originals[1],through)
    for ref in refs:
        observed=datetime.fromisoformat(ref['observed_at'])
        if observed.tzinfo is None or observed>stamp:raise ValueError('invalid source observation time')
    validate_venue(venue,block,through)
    if block!=value['block']:raise ValueError('closing projection does not match original')
    return {r['ts_code']:r for r in block['rows']},value['content_digest']


def star_members(root,through,*,directory=None):
    import pandas as pd
    directory=directory if directory is not None else root/'trader_observations/star50_members'
    ref=json.loads((directory/'current.json').read_text())
    if not re.fullmatch(r'[a-f0-9]{64}',ref['sha256']):raise ValueError('invalid member source identity')
    expected='https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/cons/000688cons.xls'
    raw=(directory/(ref['sha256']+'.xls')).read_bytes()
    if ref['url']!=expected or ref['response_url']!=expected or sha256(raw).hexdigest()!=ref['sha256'] or len(raw)!=ref['bytes']:raise ValueError('member original changed')
    stamp=datetime.fromisoformat(ref['observed_at'])
    if stamp.tzinfo is None or stamp>datetime.now(timezone.utc):raise ValueError('invalid member observation time')
    rows=pd.read_excel(directory/(ref['sha256']+'.xls'),dtype=str).to_dict('records')
    if (len(rows)!=50 or len({r['成份券代码Constituent Code'] for r in rows})!=50
        or any(not re.fullmatch(r'\d{6}',r['成份券代码Constituent Code']) or not r['成份券名称Constituent Name'].strip() for r in rows)):
        raise ValueError('not a complete STAR50 list')
    if any(r['日期Date']!=through.replace('-','') or r['指数代码 Index Code']!='000688' or r['交易所Exchange']!='上海证券交易所' for r in rows):raise ValueError('member date, index or venue changed')
    return [{'ts_code':r['成份券代码Constituent Code']+'.SH','name':r['成份券名称Constituent Name']} for r in rows],ref['sha256']


def membership_files(directory):
    """Bind only the exact original inputs; never copy a mutable parent tree."""
    risk=json.loads((directory/'risk/current.json').read_text())
    star=json.loads((directory/'star50/current.json').read_text())
    keys=[ref['response_sha256'] for ref in risk['responses']]+[star['sha256']]
    if any(not re.fullmatch(r'[a-f0-9]{64}',key) for key in keys):raise ValueError('invalid membership input identity')
    names=['risk/current.json','star50/current.json',*[f'risk/responses/{key}.raw' for key in keys[:-1]],f'star50/{keys[-1]}.xls']
    result={}
    for name in names:
        path=directory/name
        if directory.is_symlink() or path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent!=directory.parent) or not path.is_file():
            raise ValueError('invalid membership input file')
        result[name]=sha256(path.read_bytes()).hexdigest()
    return result


def closing_members(root,through,fresh,*,inputs=None):
    if inputs is None:
        from exchange_risk_membership import list_status
        risk=list_status(root/'exchange_risk_membership',now=datetime.now(timezone.utc))
        if risk['availability']!='observed' or risk['observed_on']!=through:raise ValueError('current ST list not independently observed for this date')
        stars,member_digest=star_members(root,through)
        confirmation=None
    else:
        from market_close_membership import load,confirm_close
        membership_files(inputs)
        risk=load(inputs/'risk');confirmation=confirm_close(risk,fresh,through)
        stars,member_digest=star_members(root,through,directory=inputs/'star50')
        if any(r['ts_code'] not in fresh or re.sub(r'\s+','',r['name'])!=re.sub(r'\s+','',fresh[r['ts_code']]['security_name']) for r in stars):
            raise ValueError('STAR50 membership and complete closing names differ')
    st=[{'ts_code':r['ts_code'],'name':r['name']} for r in risk['rows'] if r['kind']=='risk_warning' and r['share_class']=='A']
    return st,stars,risk['content_digest'],member_digest,confirmation


def price_observation(symbol,name,calendar,by_day,latest):
    base={'symbol':symbol,'name':name,'as_of':calendar[-1]}
    if latest is None or not latest['is_trading']:return {**base,'availability':'not_trading'}
    selected=[by_day.get(day) for day in calendar]
    if any(point is None for point in selected) or not selected[0]['is_trading']:
        return {**base,'availability':'history_incomplete'}
    level=Decimal(100);levels=[level];path=[{'date':calendar[0],'close':selected[0]['close'],'level':float(level)}]
    for day,point in zip(calendar[1:],selected[1:],strict=True):
        if not point['is_trading']:
            levels.append(None);path.append({'date':day,'close':None,'level':None});continue
        if min(point['close'],point['previous_close'])<=0:raise ValueError('invalid trading price')
        level*=Decimal(str(point['close']))/Decimal(str(point['previous_close']));levels.append(level);path.append({'date':day,'close':point['close'],'level':float(level)})
    def change(count):return float((level/levels[-count-1]-1)*100) if len(levels)>count and levels[-count-1] is not None else None
    five=[p for p in selected[-5:] if p['is_trading']];recent=[p for p in levels[-21:] if p is not None]
    five_levels=[p for p in levels[-5:] if p is not None];above=len(five_levels)==5 and level>sum(five_levels)/5
    five_change,twenty_change=change(5),change(20);drawdown=float((level/max(p for p in levels if p is not None)-1)*100)
    from_low=float((level/min(recent)-1)*100)
    oversold=twenty_change is not None and twenty_change<=RULES['twenty_day_change_lte_pct'] and drawdown<=RULES['from_window_high_lte_pct']
    repairing=five_change is not None and five_change>RULES['five_day_change_gt_pct'] and above
    extended=repairing and (five_change>RULES['five_day_change_lte_pct'] or from_low>RULES['from_twenty_day_low_lte_pct'])
    liquid=latest['amount']>=RULES['latest_amount_gte_yuan'] and latest['last']>=RULES['latest_close_gte_yuan']
    stage='rebounded_far' if extended else 'early_repair' if oversold and repairing and liquid else 'liquidity_insufficient' if oversold and repairing else 'still_weak' if oversold else 'not_in_screen'
    return {**base,'availability':'available','close':latest['last'],'day_change_pct':latest['pct_chg'],
            'previous_close':latest['prev_close'],'five_day_change_pct':five_change,'twenty_day_change_pct':twenty_change,'from_window_high_pct':drawdown,
            'from_twenty_day_low_pct':from_low,'above_five_day_mean':above,'latest_amount_yuan':latest['amount'],
            'five_day_mean_close':sum(p['close'] for p in five)/5 if len(five)==5 else None,
            'twenty_day_low_close':min(p['close'] for p in selected[-21:] if p['is_trading']),
            'nontrading_days':sum(not p['is_trading'] for p in selected),'oversold':oversold,'stage':stage,'path':path}


def watched_members(fresh):
    from workbench_views import WATCHED,WATCH_LABELS
    return [{'ts_code':symbol,'name':fresh.get(symbol,{}).get('security_name') or WATCH_LABELS[symbol]} for symbol in WATCHED]


def build(data,*,through,root=ROOT,membership_inputs=None):
    from workbench_views import WATCHED,watch_basis
    from market_periods import recent_calendar_window
    from market_calendar import sessions_2026
    from market_breadth_history import _read_day
    period=recent_calendar_window(through);calendar=period['calendar']
    if period['availability']!='defined' or len(calendar)<21:raise ValueError('completed common price calendar required')
    sources={};fresh={};observed_days={}
    required=sessions_2026(datetime.fromisoformat(data['requested_through']).date(),datetime.fromisoformat(through).date())[1:]
    if not required or required[-1]!=through:raise ValueError('new close date required')
    for day in required:
        merged={}
        for venue in ('SSE','SZSE'):
            rows,key=closing_day(root,day,venue)
            if set(rows)&set(merged):raise ValueError('duplicate cross-venue closing security')
            merged.update(rows);sources[venue+':'+day]=key
        observed_days[day]=merged
    fresh=observed_days[through]
    st,stars,risk_digest,member_digest,confirmation=closing_members(root,through,fresh,inputs=membership_inputs)
    hdir=root/'public_breadth_history';history=packet(hdir/'current.json')
    if history['content_digest']!=data['breadth_history']['content_digest']:raise ValueError('base history changed')
    daily={}
    for day in calendar:
        if day in observed_days:continue
        value=_read_day(hdir,history['daily_snapshots'][day],day,datetime.now(timezone.utc),check_raw=True)
        daily[day]={r['ts_code']:r for r in value['block']['rows']}
    results={}
    watched=watched_members(fresh)
    for member in {r['ts_code']:r for r in [*st,*stars,*watched]}.values():
        symbol=member['ts_code']
        if not fresh.get(symbol,{}).get('is_trading'):
            results[symbol]=price_observation(symbol,member['name'],calendar,{},fresh.get(symbol))
            continue
        if symbol.endswith('.SH'):
            try:basis=watch_basis(data,symbol,root=root)
            except (OSError,ValueError,KeyError):
                results[symbol]={'symbol':symbol,'name':member['name'],'as_of':through,'availability':'history_incomplete'}
                continue
            by_day={p['date']:p for p in basis['prices']}
        else:
            by_day={}
            for day,rows in daily.items():
                row=rows.get(symbol)
                if row:by_day[day]={'close':row['last'] if row['is_trading'] else None,'previous_close':row['prev_close'] if row['is_trading'] else None,'is_trading':row['is_trading']}
        for day,rows in observed_days.items():
            row=rows.get(symbol)
            if row:by_day[day]={'close':row['last'] if row['is_trading'] else None,'previous_close':row['prev_close'] if row['is_trading'] else None,'is_trading':row['is_trading']}
        results[symbol]=price_observation(symbol,member['name'],calendar,by_day,fresh.get(symbol))
    groups=[]
    for key,label,members in [('star50','科创50',stars),('st','ST池',st)]:
        all_rows=[results[r['ts_code']] for r in members];valid=[r for r in all_rows if r['availability']=='available']
        eligible=sorted([r for r in valid if r['oversold']],key=lambda r:(r['stage']!='early_repair',r['twenty_day_change_pct']))
        groups.append({'key':key,'name':label,'pool_count':len(members),'observed_count':len(valid),
                       'oversold_count':len(eligible),'early_repair_count':sum(r['stage']=='early_repair' for r in eligible),
                       'rows':eligible,'excluded':[r for r in all_rows if r['availability']!='available']})
    result={'availability':'available','as_of':through,'start':calendar[0],'horizon':'1–4周反弹观察',
            'groups':groups,'rules':RULES,'watchlist':[results[s] for s in WATCHED if s in results],
            'source_digests':{'membership':risk_digest,'star50_members':member_digest,'base_sse':data['sse_history_archive']['content_digest'],'base_szse':history['content_digest'],**sources},
            'reading_note':'这是按当前成员、历史收盘与已公开资料建立的反弹观察。初步修复表示价格条件，不表示公司风险已解决。'}
    if membership_inputs is not None:
        result['source_digests']['membership_inputs']=digest(membership_files(membership_inputs))
        result['membership_confirmation']=confirmation
    return result


def materialize(data,through,*,membership_inputs=None,root=ROOT,output=OUTPUT):
    processor=processor_digest();frozen=None;key=None
    if membership_inputs is not None:
        files=membership_files(membership_inputs);key=digest(files);frozen=output/'sources'/key
        for name,expected in files.items():
            raw=(membership_inputs/name).read_bytes()
            if sha256(raw).hexdigest()!=expected:raise ValueError('membership input changed during copy')
            target=frozen/name
            if target.exists() and target.read_bytes()!=raw:raise ValueError('immutable membership source differs')
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():target.write_bytes(raw)
        if membership_files(frozen)!=files:raise ValueError('frozen membership source changed')
    result=build(data,through=through,root=root,membership_inputs=frozen)
    if processor_digest()!=processor:raise ValueError('reload changed observation processor')
    value={'version':DATED_VERSION if frozen is not None else VERSION,'processor_digest':processor,
           'checked_at':datetime.now(timezone.utc).isoformat(),'data':result}
    if frozen is not None:
        if digest(membership_files(frozen))!=key or result['source_digests']['membership_inputs']!=key:raise ValueError('membership input changed during publication')
        value['membership_input_digest']=key
    value['content_digest']=digest(value)
    atomic_write_json(output/'snapshots'/(value['content_digest']+'.json'),value);atomic_write_json(output/'current.json',value)
    return value


def load(directory=OUTPUT):
    try:
        value=packet(directory/'current.json')
        if value['version'] not in (VERSION,DATED_VERSION) or value['processor_digest']!=processor_digest():return {'availability':'updating'}
        if value['version']==DATED_VERSION:
            key=value.get('membership_input_digest')
            if not isinstance(key,str) or not re.fullmatch(r'[a-f0-9]{64}',key) or value['data']['source_digests'].get('membership_inputs')!=key or not value['data'].get('membership_confirmation'):
                return {'availability':'updating'}
        elif 'membership_inputs' in value['data'].get('source_digests',{}) or value['data'].get('membership_confirmation'):
            return {'availability':'updating'}
        from trader_research_notes import attach_swing_notes
        return attach_swing_notes(value['data'],value['content_digest'],directory.parent)
    except (OSError,ValueError,KeyError,TypeError):return {'availability':'updating'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--through',required=True)
    parser.add_argument('--membership-inputs',type=Path);args=parser.parse_args()
    from market_risk import build_market_risk_status
    value=materialize(build_market_risk_status(),args.through,membership_inputs=args.membership_inputs);data=value['data']
    print(json.dumps({'as_of':data['as_of'],'groups':[{k:g[k] for k in ('name','pool_count','observed_count','oversold_count','early_repair_count')} for g in data['groups']]},ensure_ascii=False))


if __name__=='__main__':main()
