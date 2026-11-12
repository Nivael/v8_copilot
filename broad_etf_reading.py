"""Dated, six-group ETF observations. Share changes never identify the buyer."""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from statistics import median
from urllib.parse import parse_qs, urlsplit

from canonical_json import digest
from market_calendar import sessions_2026
from market_risk import ETF_SHARE_SQL, ETF_SHARE_SOURCE
from settings import DATA_ROOT

ROOT=DATA_ROOT/'local_data/v8_copilot/market_risk'
GROUPS={
    '沪深300':('000300',('510300.SH','510310.SH','510330.SH','159919.SZ')),
    '上证50':('000016',('510050.SH',)),
    '中证500':('000905',('510500.SH','159922.SZ')),
    '中证1000':('000852',('512100.SH','159845.SZ')),
    '中证A500':('000510',('563360.SH',)),
    '科创50':('000688',('588000.SH','588080.SH')),
}
NAMES={
    '510300.SH':'华泰柏瑞沪深300ETF','510310.SH':'易方达沪深300ETF','510330.SH':'华夏沪深300ETF','159919.SZ':'嘉实沪深300ETF',
    '510500.SH':'南方中证500ETF','159922.SZ':'嘉实中证500ETF','512100.SH':'南方中证1000ETF','159845.SZ':'华夏中证1000ETF',
    '510050.SH':'华夏上证50ETF','563360.SH':'华泰柏瑞中证A500ETF','588000.SH':'华夏科创50ETF','588080.SH':'易方达科创50ETF',
}
EXTRAS={'510050.SH','563360.SH','588000.SH','588080.SH'}


def positive(value):
    if isinstance(value,bool):raise ValueError('boolean observation')
    result=Decimal(str(value))
    if not result.is_finite() or result<=0:raise ValueError('invalid positive observation')
    return result


def bound_packet(path):
    packet=json.loads(path.read_text())
    if digest({k:v for k,v in packet.items() if k!='content_digest'})!=packet['content_digest']:
        raise ValueError('source packet changed')
    return packet


def read_indices(root,calendar):
    directory=root/'trader_observations/broad_indices';meta=bound_packet(directory/'current.json')
    if meta['version']!='broad_index_sources_v1' or meta['start']!=calendar[0] or meta['through']!=calendar[-1]:
        raise ValueError('index calendar does not match ETF observations')
    refs={ref['code']:ref for ref in meta['responses']}
    if len(refs)!=len(meta['responses']) or set(refs)!={value[0] for value in GROUPS.values()}:
        raise ValueError('incomplete or duplicate broad index identities')
    result={}
    for code,ref in refs.items():
        url=urlsplit(ref['url']);params=parse_qs(url.query)
        if url.scheme!='https' or url.netloc!='www.csindex.com.cn' or url.path!='/csindex-home/perf/index-perf' or params!={'indexCode':[code],'startDate':[calendar[0].replace('-','')],'endDate':[calendar[-1].replace('-','')]}:
            raise ValueError('index query changed')
        raw=(directory/'responses'/(ref['response_sha256']+'.json')).read_bytes()
        if sha256(raw).hexdigest()!=ref['response_sha256'] or len(raw)!=ref['bytes']:raise ValueError('index original changed')
        observed=datetime.fromisoformat(ref['observed_at'])
        if observed.tzinfo is None or observed>datetime.now(timezone.utc):raise ValueError('invalid source observation time')
        payload=json.loads(raw,parse_float=Decimal)
        if str(payload['code'])!='200':raise ValueError('index source unsuccessful')
        by_day={}
        for row in payload['data']:
            day=datetime.strptime(row['tradeDate'],'%Y%m%d').date().isoformat() if '-' not in row['tradeDate'] else row['tradeDate']
            if row['indexCode']!=code or day not in calendar or day in by_day:raise ValueError('index identity or dates changed')
            by_day[day]=positive(row['close'])
        if set(by_day)!=set(calendar):raise ValueError('incomplete index calendar')
        result[code]=[by_day[day] for day in calendar]
    return result,meta['content_digest']


def read_extra_shares(data,root,calendar):
    directory=root/'public_etf';meta=bound_packet(directory/'current.json')
    if (meta['content_digest']!=data['public_etf_snapshot']['content_digest'] or meta['calendar']!=calendar
        or meta['share_unit']!='ten_thousand_shares' or meta['source_sql']!=ETF_SHARE_SQL):
        raise ValueError('extra ETF source not bound to the verified daily source')
    grouped=defaultdict(list)
    for ref in meta['responses']:grouped[ref['query_date']].append(ref)
    if set(grouped)!=set(calendar):raise ValueError('daily source references incomplete')
    paths={code:[] for code in EXTRAS}
    for day in calendar:
        refs=sorted(grouped[day],key=lambda r:r['page']);rows=[];count=None
        for page,ref in enumerate(refs,1):
            url=urlsplit(ref['url']);params=parse_qs(url.query)
            if (url.scheme!='https' or url.netloc!='query.sse.com.cn' or url.path!='/commonQuery.do'
                or params!={'sqlId':[ETF_SHARE_SQL],'isPagination':['true'],'STAT_DATE':[day],'pageHelp.pageSize':['1000'],
                            'pageHelp.pageNo':[str(page)],'pageHelp.beginPage':[str(page)],'pageHelp.endPage':[str(page)],'pageHelp.cacheSize':['1']}):
                raise ValueError('ETF daily source query changed')
            raw=(directory/'responses'/(ref['response_sha256']+'.json')).read_bytes()
            if sha256(raw).hexdigest()!=ref['response_sha256']:raise ValueError('ETF daily source original changed')
            payload=json.loads(raw);help=payload['pageHelp'];total=int(help['total'])
            if int(help['pageNo'])!=page or int(help['pageCount'])!=len(refs) or count is not None and count!=total:
                raise ValueError('ETF daily pages incomplete')
            count=total;rows.extend(payload['result'])
        if count!=len(rows) or len({row['SEC_CODE'] for row in rows})!=count or any(row['STAT_DATE']!=day for row in rows):
            raise ValueError('ETF daily rows incomplete, duplicated or misdated')
        for code in EXTRAS:
            row,=[row for row in rows if row['SEC_CODE']==code[:6]]
            paths[code].append(positive(row['TOT_VOL']))
    return paths,meta['content_digest']


def summarize(paths,indices,calendar,start):
    if len(calendar)<21 or start not in calendar or any(len(path)!=len(calendar) for path in [*paths.values(),*indices.values()]):
        raise ValueError('matching complete calendars required')
    def change(path,n):return float((path[-1]/path[-n-1]-1)*100)
    start_at=calendar.index(start);groups=[]
    for name,(index,codes) in GROUPS.items():
        funds=[{'code':code,'name':NAMES[code],
                'five_day_share_change_pct':change(paths[code],5),'twenty_day_share_change_pct':change(paths[code],20),
                'period_share_change_pct':float((paths[code][-1]/paths[code][start_at]-1)*100)} for code in codes]
        up=sum(f['five_day_share_change_pct']>0 for f in funds);down=sum(f['five_day_share_change_pct']<0 for f in funds)
        price5=change(indices[index],5);price20=change(indices[index],20)
        direction='样本份额都增加' if up==len(funds) else '样本份额都减少' if down==len(funds) else '样本份额分化' if up or down else '样本份额未变'
        reading=direction+('，价格尚未同步回升' if price5<0 and up==len(funds) else '，与短线价格回升同向' if price5>0 and up==len(funds) else '')
        groups.append({'name':name,'index_code':index,'sample_count':len(funds),'increasing_5d':up,'decreasing_5d':down,
                       'five_day_price_change_pct':price5,'twenty_day_price_change_pct':price20,
                       'median_five_day_share_change_pct':median(f['five_day_share_change_pct'] for f in funds),
                       'reading':reading,'funds':funds,'source_url':f'https://www.csindex.com.cn/#/indices/family/detail?indexCode={index}'})
    increasing=sum(g['increasing_5d']==g['sample_count'] for g in groups)
    rising='、'.join(g['name'] for g in groups if g['five_day_price_change_pct']>0)
    falling='、'.join(g['name'] for g in groups if g['five_day_price_change_pct']<0)
    return {'availability':'available','as_of':calendar[-1],'start':start,'groups':groups,'sample_funds':len(paths),
            'headline':f'{increasing}组宽基样本的份额同步增加' if increasing else '宽基样本的份额方向出现分化',
            'interpretation':(('六组宽基样本份额同步增加。' if increasing==6 else '宽基样本份额方向有分化。')
                              +(f'{rising}近5日回升。' if rising else '')+(f'{falling}近5日仍下跌。' if falling else '')
                              +'接下来观察反弹能否扩散。'),
            'institution_reading':'机构判断依据实名持仓与公开动作，ETF总份额用于观察全部投资者的份数变化。',
            'source_url':ETF_SHARE_SOURCE,'estimated_cash_flow_yuan':None}


def build_broad_etf_reading(data,*,root=ROOT):
    if data.get('public_etf_snapshot',{}).get('availability')!='observed':return {'availability':'unavailable'}
    calendar=bound_packet(root/'public_etf/current.json')['calendar']
    if calendar!=sessions_2026(datetime.fromisoformat(calendar[0]).date(),datetime.fromisoformat(calendar[-1]).date()):
        raise ValueError('nonmatching exchange calendar')
    indices,index_digest=read_indices(root,calendar)
    paths,share_digest=read_extra_shares(data,root,calendar)
    for fund in data['etfs']:
        if fund['code'] not in NAMES or fund['code'] in EXTRAS:continue
        points=fund['path']
        if [point['date'] for point in points]!=calendar:raise ValueError('ETF sample calendar incomplete')
        paths[fund['code']]=[positive(point['shares']) for point in points]
    result=summarize(paths,indices,calendar,data['recent_window']['start'])
    from trader_research_notes import capital_actions
    return {**result,'index_sources_digest':index_digest,'share_sources_digest':share_digest,
            'capital_actions':capital_actions(root/'trader_observations')}
