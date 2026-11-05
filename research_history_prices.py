"""Source-bound daily paths for reviewing actual past questions, not simulated trades."""
from collections import defaultdict
from datetime import date,datetime,timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlencode,urlsplit,parse_qs
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from market_calendar import sessions_2026
from settings import DATA_ROOT

ROOT=DATA_ROOT/'local_data/v8_copilot/research_history'
MARKET_ROOT=DATA_ROOT/'local_data/v8_copilot/market_risk'


def bound(path):
    value=json.loads(path.read_text())
    if digest({k:v for k,v in value.items() if k!='content_digest'})!=value['content_digest']:raise ValueError('history input changed')
    return value


def csi_path(root,calendar):
    folder=root/'inputs/csi';ref=json.loads((folder/'current.json').read_text())
    url='https://www.csindex.com.cn/csindex-home/perf/index-perf?'+urlencode({'indexCode':'000985','startDate':'20260501','endDate':calendar[-1].replace('-','')})
    raw=(folder/(ref['sha256']+'.json')).read_bytes()
    if ref['url']!=url or ref['response_url']!=url or sha256(raw).hexdigest()!=ref['sha256'] or len(raw)!=ref['bytes']:raise ValueError('market original changed')
    value=json.loads(raw);points={}
    for row in value['data']:
        day=datetime.strptime(row['tradeDate'],'%Y%m%d').date().isoformat()
        if row['indexCode']!='000985' or day in points or not Decimal(str(row['close'])).is_finite() or float(row['close'])<=0:raise ValueError('market identity or quote changed')
        points[day]=float(row['close'])
    if any(day not in points for day in calendar):raise ValueError('market calendar incomplete')
    return [{'date':day,'value':points[day],'level':points[day]/points[calendar[0]]*100} for day in calendar],ref['sha256']


def vendor_st_path(root,calendar):
    """Keep this published vendor series separate from the internal equal-weight index."""
    folder=root/'inputs/vendor_st';ref=json.loads((folder/'current.json').read_text());url=urlsplit(ref['url'])
    expected={'secid':['90.BK0511'],'klt':['101'],'fqt':['0'],'beg':['20260501'],'end':[calendar[-1].replace('-','')],
              'fields1':['f1,f2,f3,f4,f5,f6'],'fields2':['f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61']}
    raw=(folder/(ref['sha256']+'.json')).read_bytes()
    if (url.scheme!='https' or url.netloc!='push2his.eastmoney.com' or url.path!='/api/qt/stock/kline/get' or parse_qs(url.query)!=expected
        or ref['response_url']!=ref['url'] or sha256(raw).hexdigest()!=ref['sha256'] or len(raw)!=ref['bytes']):raise ValueError('ST vendor source changed')
    stamp=datetime.fromisoformat(ref['observed_at'])
    if stamp.tzinfo is None or stamp>datetime.now(timezone.utc):raise ValueError('ST vendor observation time changed')
    value=json.loads(raw)
    if value['rc']!=0 or value['data']['code']!='BK0511' or value['data']['name']!='ST股':raise ValueError('ST vendor index identity changed')
    points=[];previous=None
    for raw_row in value['data']['klines']:
        row=raw_row.split(',')
        if len(row)!=11:raise ValueError('ST vendor fields changed')
        values=[Decimal(v) for v in row[1:]];close=values[1]
        if any(not v.is_finite() for v in values) or close<=0:raise ValueError('invalid ST vendor price')
        if previous and abs(float((close/previous-1)*100)-float(values[7]))>.015:raise ValueError('ST vendor change mismatch')
        points.append({'date':row[0],'value':float(close),'level':float(close)})
        previous=close
    if [p['date'] for p in points]!=calendar:raise ValueError('ST vendor calendar incomplete')
    base=points[0]['level']
    for point in points:point['level']=point['level']/base*100
    return points,ref['sha256']


def capture_sse(symbol,root=ROOT):
    code=symbol[:6];params={'select':'date,close,prevClose,chg_rate,volume,amount','begin':-126,'end':-1,'period':'day'}
    url='https://yunhq.sse.com.cn:32042/v1/sh1/dayk/'+code
    with urlopen(Request(url+'?'+urlencode(params),headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'}),timeout=20) as response:
        raw=response.read(2_000_001)
        if response.url!=url+'?'+urlencode(params) or len(raw)>2_000_000:raise ValueError('unexpected history response')
    key=sha256(raw).hexdigest();folder=root/'inputs/sse';folder.mkdir(parents=True,exist_ok=True);(folder/(key+'.json')).write_bytes(raw)
    ref={'url':url,'params':params,'sha256':key,'bytes':len(raw),'observed_at':datetime.now(timezone.utc).isoformat()}
    # Validate before publishing the reference.
    parse_sse_history(raw,ref,symbol,datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat())
    atomic_write_json(folder/(code+'.json'),ref)
    return ref


def parse_sse_history(raw,ref,symbol,through):
    payload=json.loads(raw);code=symbol[:6]
    if (ref['url']!='https://yunhq.sse.com.cn:32042/v1/sh1/dayk/'+code or payload['code']!=code
        or ref['params']!={'select':'date,close,prevClose,chg_rate,volume,amount','begin':-126,'end':-1,'period':'day'}
        or sha256(raw).hexdigest()!=ref['sha256'] or len(raw)!=ref['bytes']):raise ValueError('stock original identity changed')
    total,begin,end=payload['total'],payload['begin'],payload['end']
    if any(type(v)is not int for v in [total,begin,end]) or end!=total or begin!=max(0,total-125) or len(payload['kline'])!=end-begin:raise ValueError('stock history pages incomplete')
    observed=datetime.fromisoformat(ref['observed_at']).astimezone(ZoneInfo('Asia/Shanghai'));points={};previous_day=''
    for row in payload['kline']:
        if len(row)!=6:raise ValueError('stock quote columns changed')
        day=datetime.strptime(str(row[0]),'%Y%m%d').date().isoformat()
        if day<=previous_day or day>observed.date().isoformat():raise ValueError('stock dates changed')
        previous_day=day
        if day>through or day==observed.date().isoformat() and observed.hour<15:continue
        values=[Decimal(str(v)) for v in row[1:]]
        if any(not v.is_finite() for v in values) or min(values[3:])<0:raise ValueError('invalid stock quote')
        active=values[3]>0
        if active and (min(values[:2])<=0 or abs(float((values[0]/values[1]-1)*100)-float(values[2]))>.015):raise ValueError('stock previous-close return mismatch')
        points[day]={'date':day,'close':float(values[0]) if active else None,'previous_close':float(values[1]) if active else None,'is_trading':active}
    return points


def supplemental_history(root,symbol,calendar,historical,official):
    """A complete, separately bound qfq window for stocks missing from the old DB."""
    refpath=root/'inputs/tencent_qfq'/(symbol[:6]+'.json')
    if not refpath.exists():return historical,None
    ref=json.loads(refpath.read_text());folder=refpath.parent
    raw=(folder/(ref['sha256']+'.json')).read_bytes();code=symbol[:6];key=('sh' if symbol.endswith('.SH') else 'sz')+code
    end=date.fromisoformat(ref['through']).isoformat()
    expected='https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?'+urlencode({'param':f'{key},day,{calendar[0]},{end},640,qfq'})
    observed=datetime.fromisoformat(ref['observed_at'])
    if (ref['url']!=expected or ref.get('response_url')!=expected or sha256(raw).hexdigest()!=ref['sha256']
            or len(raw)!=ref['bytes'] or observed.tzinfo is None or observed>datetime.now(timezone.utc)
            or end>calendar[-1] or end<'2026-09-03' or end>observed.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()):
        raise ValueError('supplemental stock original changed')
    payload=json.loads(raw);data=payload.get('data',{}).get(key,{});quote=data.get('qt',{}).get(key,[])
    if payload.get('code')!=0 or len(quote)<3 or quote[2]!=code or not quote[1]:raise ValueError('supplemental stock identity changed')
    rows=data.get('qfqday',[]);result={};previous='';valid_days=set(calendar)
    for row in rows:
        if len(row)!=6:raise ValueError('supplemental stock columns changed')
        day=date.fromisoformat(row[0]).isoformat();values=[Decimal(v) for v in row[1:]];op,close,high,low,volume=values
        if (day<=previous or day not in valid_days or day>end or any(not v.is_finite() for v in values)
                or min(op,close,low)<=0 or high<max(op,close,low) or low>min(op,close) or volume<=0):
            raise ValueError('supplemental stock dates or prices changed')
        previous=day;result[day]={'close':float(close),'volume':float(volume)}
    endpoint=official.get(end)
    if (not result or next(iter(result))!=calendar[0] or previous!=end or not endpoint or not endpoint['is_trading']
            or abs(result[end]['close']-endpoint['close'])>.011 or '2026-09-03' not in result):
        raise ValueError('supplemental stock endpoint or hand-off is unverified')
    overlap=[day for day in result if day<'2026-09-04' and day in historical and historical[day]['close'] and historical[day]['volume']>0]
    differs=not overlap or any(abs(result[day]['close']-historical[day]['close'])>.011 for day in overlap)
    checked=0;previous_close=None
    for day,row in result.items():
        point=official.get(day)
        if day>='2026-09-04' and previous_close and point and point['is_trading']:
            if min(point['close'],point['previous_close'])<=0 or abs(row['close']/previous_close-point['close']/point['previous_close'])>.0008:
                raise ValueError('supplemental stock official return differs')
            checked+=1
        previous_close=row['close']
    if differs and (ref.get('historical_basis_replaced') is not True or not ref.get('basis_review_note') or checked<20):
        raise ValueError('supplemental stock adjustment basis differs; reviewed replacement and twenty official sessions required')
    # Replace the entire early window, not isolated prices from different adjustments.
    return {**{day:row for day,row in historical.items() if day>='2026-09-04'},
            **{day:row for day,row in result.items() if day<'2026-09-04'}},ref


def stock_path(calendar,historical,official):
    """Historical qfq ratios, then exact official close/previous-close chaining.

    The chart is a price comparison. An unknown gap across the hand-off withdraws
    the chain; a confirmed suspension is a visible gap, never a zero-return dot.
    """
    first=next((Decimal(str(historical[d]['close'])) for d in calendar if d<'2026-09-04' and d in historical and historical[d]['close'] is not None and historical[d]['close']>0),None)
    level=None;unknown=False;result=[]
    for day in calendar:
        old=historical.get(day);point=official.get(day)
        if day<'2026-09-04':
            active=old and old['close'] is not None and old['close']>0 and old['volume']>0
            if active:
                level=Decimal(str(old['close']))/first*100;unknown=False;result.append({'date':day,'value':old['close'],'level':float(level),'basis':'historical_qfq'})
            else:
                if not old or old.get('volume')!=0:unknown=True
                result.append({'date':day,'value':None,'level':None,'basis':'historical_gap'})
            continue
        if point is None:
            unknown=True;result.append({'date':day,'value':None,'level':None,'basis':'missing'});continue
        if not point['is_trading']:
            result.append({'date':day,'value':None,'level':None,'basis':'not_trading'});continue
        if unknown and old and first and old['close'] and old['volume']>0:
            level=Decimal(str(old['close']))/first*100;unknown=False
        elif not unknown:
            if min(point['close'],point['previous_close'])<=0:raise ValueError('invalid active price')
            level=level*Decimal(str(point['close']))/Decimal(str(point['previous_close'])) if level is not None else Decimal(100)
        result.append({'date':day,'value':point['close'],'level':None if unknown else float(level),'basis':'official_previous_close'})
    return result


def build_paths(symbols,market,*,start='2026-05-06',through='2026-11-05',root=ROOT,market_root=MARKET_ROOT,capture_missing=False):
    from market_breadth_history import _read_day
    from trader_swing_reading import closing_day
    from workbench_views import watch_basis
    from exchange_risk_membership import list_status
    calendar=sessions_2026(date.fromisoformat(start),date.fromisoformat(through));history=bound(root/'inputs/historical_prices.json')
    by_symbol=defaultdict(dict)
    for row in history['rows']:by_symbol[row['symbol']][row['trade_date']]=row
    fresh={};source_keys={'historical_prices':history['content_digest']}
    for venue in ['SSE','SZSE']:
        rows,key=closing_day(market_root,through,venue);fresh.update(rows);source_keys['close_'+venue]=key
    hroot=market_root/'public_breadth_history';meta=bound(hroot/'current.json');daily={}
    if meta['content_digest']!=market['breadth_history']['content_digest']:raise ValueError('historical exchange source changed')
    for day in meta['calendar']:
        item=_read_day(hroot,meta['daily_snapshots'][day],day,datetime.now(timezone.utc),check_raw=True)
        daily[day]={r['ts_code']:r for r in item['block']['rows']}
    source_keys['official_szse']=meta['content_digest'];stocks={};warnings={}
    for symbol in symbols:
        official={}
        if symbol.endswith('.SH'):
            try:official={r['date']:r for r in watch_basis(market,symbol,root=market_root)['prices']}
            except (OSError,ValueError,KeyError):
                folder=root/'inputs/sse';refpath=folder/(symbol[:6]+'.json')
                if not refpath.exists() and capture_missing:capture_sse(symbol,root)
                if refpath.exists():
                    ref=json.loads(refpath.read_text());official=parse_sse_history((folder/(ref['sha256']+'.json')).read_bytes(),ref,symbol,through);source_keys[symbol]=ref['sha256']
        else:
            for day,rows in daily.items():
                if symbol in rows:
                    row=rows[symbol];official[day]={'close':row['last'],'previous_close':row['prev_close'],'is_trading':row['is_trading']}
        if symbol in fresh:
            row=fresh[symbol];official[through]={'close':row['last'],'previous_close':row['prev_close'],'is_trading':row['is_trading']}
        historical,override=supplemental_history(root,symbol,calendar,by_symbol[symbol[:6]],official)
        if override:source_keys['supplemental_'+symbol]=digest(override)
        path=stock_path(calendar,historical,official)
        stocks[symbol]={'name':fresh.get(symbol,{}).get('security_name',symbol),'points':path,'as_of':through}
        if override:stocks[symbol].update(history_source_url=override['url'],history_note='早期库存在缺档或复权差异，本标的历史段改用腾讯完整前复权窗口，并核对已有重叠价格、交易所后续日收益及末日收盘；旧库无可比重叠或复权不一致时，单独核查整段替换，不混拼不同复权口径。之后按交易所收盘/前收盘比值衔接，停牌留空。')
        if not path[-1]['level']:warnings[symbol]='latest_path_incomplete'
    broad,broad_digest=csi_path(root,calendar);source_keys['market']=broad_digest
    members=bound(root/'inputs/historical_members.json');source_keys['historical_members']=members['content_digest'];by_day=defaultdict(list)
    for row in members['rows']:
        if row['ts_code'].endswith(('.SH','.SZ')):by_day[row['trade_date']].append(row['symbol'])
    new_st={p['date']:p['all'] for p in market['st_reconstruction']['points']}
    risk=list_status(market_root/'exchange_risk_membership',now=datetime.now(timezone.utc))
    if risk['observed_on']!=through:raise ValueError('ST endpoint membership is not dated')
    new_members=[r['ts_code'] for r in risk['rows'] if r['kind']=='risk_warning' and r['share_class']=='A']
    active=[fresh[s] for s in new_members if s in fresh and fresh[s]['is_trading']]
    new_st[through]={'daily_return_pct':sum(r['pct_chg'] for r in active)/len(active),'coverage_ratio':len(active)/len(new_members)}
    source_keys['new_st']=market['st_reconstruction']['content_digest'];source_keys['new_st_membership']=risk['content_digest']
    level=Decimal(100);st=[];broken=False
    for day in calendar:
        if day<'2026-09-04':
            names=by_day[day];valid=[by_symbol[s][day] for s in names if day in by_symbol[s] and by_symbol[s][day]['volume']>0 and by_symbol[s][day]['pct_change'] is not None]
            coverage=len(valid)/len(names) if names else 0;daily_return=sum(r['pct_change'] for r in valid)/len(valid) if valid else None
        else:
            point=new_st.get(day,{});coverage=point.get('coverage_ratio',0);daily_return=point.get('daily_return_pct')
        if coverage<.95 or daily_return is None:broken=True
        if not broken:level*=1+Decimal(str(daily_return))/100
        st.append({'date':day,'value':None if broken else float(level),'level':None if broken else float(level),'coverage_ratio':coverage,
                   'daily_return_pct':daily_return if coverage>=.95 else None})
    vendor,vendor_digest=vendor_st_path(root,calendar);source_keys['vendor_st']=vendor_digest
    result={'calendar':calendar,'stocks':stocks,'market':broad,'st':vendor,'st_name':'ST板块（东财）',
            'st_source_url':'https://quote.eastmoney.com/bk/90.BK0511.html','source_digests':source_keys,'warnings':warnings,
            'st_note':'本页历史复盘采用东方财富ST股板块行情作价格参照，成分和编制口径由供应商决定；与市场判断页的自建ST等权参考分别保存，不拼接、不视为可交易组合或因果归因。',
            'independent_st':st,'independent_st_note':'沪深ST有成交成员等权对照，早期部分日期覆盖不足95%，保留缺口。'}
    value={'version':'research_history_paths_v1','processor_digest':sha256(Path(__file__).read_bytes()).hexdigest(),'checked_at':datetime.now(timezone.utc).isoformat(),'data':result};value['content_digest']=digest(value)
    atomic_write_json(root/'price_paths/history'/(value['content_digest']+'.json'),value);atomic_write_json(root/'price_paths/current.json',value)
    return value


def prepare_inputs(through,*,root=ROOT):
    """Explicit offline job: copy read-only SQL selections and capture two indices.

    No request handler calls this. Exchange daily-close/membership inputs must
    already cover `through`; build_paths separately verifies their dates.
    """
    import sqlite3
    from settings import BASE_DB,MARKET_CONTEXT_DB
    selections=[('historical_prices',BASE_DB,"select symbol,trade_date,close,volume,pct_change,source from daily_prices where adjust='qfq' and trade_date between '2026-05-01' and '2026-09-07' order by symbol,trade_date"),
                ('historical_members',MARKET_CONTEXT_DB,"select trade_date,symbol,ts_code,name,source from st_membership_daily where trade_date between '2026-05-01' and '2026-09-03' order by trade_date,symbol")]
    for name,path,query in selections:
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
            db.row_factory=sqlite3.Row;db.execute('begin');rows=[dict(row) for row in db.execute(query)]
        value={'version':'research_history_sql_selection_v1','source_file':path.name,'query':query,'observed_at':datetime.now(timezone.utc).isoformat(),'rows':rows};value['content_digest']=digest(value)
        atomic_write_json(root/'inputs'/(name+'.json'),value)
    sources={'csi':'https://www.csindex.com.cn/csindex-home/perf/index-perf?'+urlencode({'indexCode':'000985','startDate':'20260501','endDate':through.replace('-','')}),
             'vendor_st':'https://push2his.eastmoney.com/api/qt/stock/kline/get?'+urlencode({'secid':'90.BK0511','klt':'101','fqt':'0','beg':'20260501','end':through.replace('-',''),'fields1':'f1,f2,f3,f4,f5,f6','fields2':'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61'})}
    for name,url in sources.items():
        with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20) as response:
            raw=response.read(3_000_001)
            if response.url!=url or len(raw)>3_000_000:raise ValueError('unexpected index source')
        json.loads(raw);key=sha256(raw).hexdigest();folder=root/'inputs'/name;folder.mkdir(parents=True,exist_ok=True);(folder/(key+'.json')).write_bytes(raw)
        atomic_write_json(folder/'current.json',{'url':url,'response_url':url,'sha256':key,'bytes':len(raw),'observed_at':datetime.now(timezone.utc).isoformat()})


def main():
    import argparse
    from market_risk import build_market_risk_status
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--through',required=True);parser.add_argument('--import-file',required=True,type=Path);parser.add_argument('--prepare-inputs',action='store_true');parser.add_argument('--capture-missing',action='store_true');args=parser.parse_args()
    date.fromisoformat(args.through)
    if args.prepare_inputs:prepare_inputs(args.through)
    imported=json.loads(args.import_file.read_text());symbols=sorted({s for r in imported['records'] for s in r['symbols']})
    value=build_paths(symbols,build_market_risk_status(),through=args.through,capture_missing=args.capture_missing)
    print(json.dumps({'digest':value['content_digest'],'stocks':len(value['data']['stocks']),'warnings':value['data']['warnings']}))


if __name__=='__main__':main()
