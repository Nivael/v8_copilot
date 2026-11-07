"""Separate, source-bound BSE vendor prices; preserve existing exchange profiles."""
from copy import deepcopy
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal,InvalidOperation
from hashlib import sha256
import json,re
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json,TUSHARE_ROW_SOURCE
from market_calendar import sessions_2026

SOURCE_VERSION='history_bse_vendor_inputs_v1'
VERSION='history_bse_subject_extension_v1'
EXTENSION_KEY='bse_subject_extension'
SHA=re.compile(r'[a-f0-9]{64}')
SYMBOL=re.compile(r'\d{6}\.BJ')
MAX_BYTES=3_000_000


def processor_digest():
    return sha256(Path(__file__).read_bytes()).hexdigest()


def price_url(symbol,start,through):
    return 'https://push2his.eastmoney.com/api/qt/stock/kline/get?'+urlencode({
        'secid':'0.'+symbol[:6],'klt':'101','fqt':'1','beg':start.replace('-',''),'end':through.replace('-',''),
        'fields1':'f1,f2,f3,f4,f5,f6','fields2':'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61'})


def quote_url(symbol,start,through):
    return 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?'+urlencode({'param':f'bj{symbol[:6]},day,{start},{through},640,qfq'})


def _clock(value):
    if not isinstance(value,str):raise ValueError('BSE observation time must be an ISO string')
    stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
    if stamp.tzinfo is None or stamp>datetime.now(timezone.utc):raise ValueError('invalid BSE observation time')
    return stamp


def _raw(ref,folder,expected_url):
    if (not isinstance(ref,dict) or not isinstance(ref.get('sha256'),str) or not SHA.fullmatch(ref['sha256']) or ref['url']!=expected_url or ref['response_url']!=expected_url
            or type(ref['bytes']) is not int or not 0<ref['bytes']<=MAX_BYTES):raise ValueError('BSE source identity changed')
    _clock(ref['observed_at']);path=folder/(ref['sha256']+'.json')
    if path.is_symlink():raise ValueError('BSE source cannot be a mutable link')
    with path.open('rb') as f:raw=f.read(MAX_BYTES+1)
    if len(raw)!=ref['bytes'] or sha256(raw).hexdigest()!=ref['sha256']:raise ValueError('BSE source bytes changed')
    value=json.loads(raw)
    if not isinstance(value,dict):raise ValueError('BSE source is not an object')
    return value


def source_stock(root,source_digest,calendar):
    """Rebuild from both provider byte records and the retained Tushare archive."""
    from research_history_prices import bound
    if not isinstance(source_digest,str) or not SHA.fullmatch(source_digest):raise ValueError('invalid BSE input digest')
    folder=root/'inputs/bse_vendor_v1';source=bound(folder/(source_digest+'.json'))
    if source['version']!=SOURCE_VERSION or source['content_digest']!=source_digest or not SYMBOL.fullmatch(source['symbol']):raise ValueError('unregistered BSE input version or symbol')
    symbol=source['symbol'];code=symbol[:6];start=date.fromisoformat(source['start']).isoformat();through=date.fromisoformat(source['through']).isoformat()
    if (calendar!=sorted(set(calendar)) or start not in calendar or through!=calendar[-1] or start>through
            or source['comparison_basis']!='vendor_qfq_with_archived_tushare_and_next_session_quote'
            or source.get('official_daily_crosscheck') is not False):raise ValueError('BSE coverage or source class changed')
    price=_raw(source['prices'],folder,price_url(symbol,start,through));data=price.get('data') or {}
    if _clock(source['prices']['observed_at']).astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()<through:raise ValueError('BSE prices observed before their period ended')
    if not isinstance(data,dict) or price.get('rc')!=0 or data.get('market')!=0 or data.get('code')!=code or not isinstance(data.get('name'),str) or not data['name'].strip():raise ValueError('BSE price issuer mismatch')
    name=data['name'];days=[d for d in calendar if start<=d<=through];parsed={};previous=''
    lines=data.get('klines')
    if not isinstance(lines,list):raise ValueError('BSE price rows missing')
    for line in lines:
        if not isinstance(line,str):raise ValueError('BSE price strings must remain exact')
        row=line.split(',')
        if len(row)!=11:raise ValueError('BSE price columns changed')
        day=date.fromisoformat(row[0]).isoformat()
        try:values=[Decimal(v) for v in row[1:]]
        except InvalidOperation:raise ValueError('invalid BSE decimal') from None
        op,close,high,low,volume,amount=values[:6]
        if (day<=previous or day not in days or any(not v.is_finite() for v in values)
                or min(op,close,low)<=0 or high<max(op,close,low) or low>min(op,close)
                or volume<=0 or amount<0):raise ValueError('BSE dates or prices changed')
        parsed[day]={'close':close,'volume':volume};previous=day
    # This profile requires a full active vendor window; no implicit flat fills.
    if list(parsed)!=days:raise ValueError('BSE provider window has a gap or changed endpoint')
    quote_source=_raw(source['quote'],folder,quote_url(symbol,start,through))
    try:quote=quote_source['data']['bj'+code]['qt']['bj'+code]
    except (KeyError,TypeError):raise ValueError('BSE quote missing') from None
    if (quote_source.get('code')!=0 or not isinstance(quote,list) or len(quote)<=30 or quote[0]!='62'
            or quote[1]!=name or quote[2]!=code or not isinstance(quote[4],str) or not isinstance(quote[30],str)):raise ValueError('BSE quote instrument mismatch')
    quoted=datetime.strptime(quote[30],'%Y%m%d%H%M%S').replace(tzinfo=ZoneInfo('Asia/Shanghai'))
    following=sessions_2026(date.fromisoformat(through)+timedelta(days=1),date.fromisoformat(through)+timedelta(days=15))
    if (not following or quoted.date().isoformat()!=following[0] or quoted>_clock(source['quote']['observed_at'])
            or not Decimal(quote[4]).is_finite() or abs(Decimal(quote[4])-parsed[through]['close'])>Decimal('.011')):raise ValueError('BSE endpoint has no adjacent-session independent quote')
    archive=bound(root/'inputs/historical_prices.json')
    if archive['content_digest']!=source['archive_digest']:raise ValueError('BSE retained archive changed')
    archive_clock=_clock(archive['observed_at']).astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
    selected=[r for r in archive['rows'] if r['symbol']==code and start<=r['trade_date']<=through and r['volume']>0]
    if len(selected)<20 or len({r['trade_date'] for r in selected})!=len(selected):raise ValueError('BSE archive needs twenty distinct observed comparisons')
    for row in selected:
        old=Decimal(str(row['close']))
        if (row['source']!=TUSHARE_ROW_SOURCE or row['trade_date']>archive_clock or row['trade_date'] not in parsed or not old.is_finite()
                or old<=0 or abs(old-parsed[row['trade_date']]['close'])>Decimal('.011')):raise ValueError('BSE archived-provider comparison failed')
    first=parsed[start]['close'];points=[]
    for day in calendar:
        item=parsed.get(day)
        points.append({'date':day,'value':float(item['close']) if item else None,
                       'level':float(item['close']/first*100) if item else None,
                       'basis':'historical_qfq' if item else 'missing'})
    stock={'name':name,'points':points,'as_of':through,'history_source_url':source['prices']['url'],
           'history_source_kind':'eastmoney_bse_qfq_v1',
           'price_basis_note':'本股整段使用东方财富前复权日线，先前档案采用Tushare；本段未拼接沪深交易所逐日表。价格路径不是你的实际交易盈亏。',
           'history_note':f'北交所标的：本窗{len(days)}个供应商日线点，与较早保存的Tushare逐日收盘核对{len(selected)}个点，末日另与下一交易日腾讯前收盘核对；未取得北交所官方逐日全窗交叉核验，不能当作已验证策略或可成交回报。'}
    return stock,source,{'vendor_points':len(days),'archive_close_checks':len(selected),'independent_endpoint_quote_date':quoted.date().isoformat(),'official_daily_crosscheck':False}


def extension_packet(base,source_digest,*,root):
    from research_history_price_chain import validate_price_packet
    validate_price_packet(base,root=root)
    stock,source,checks=source_stock(root,source_digest,base['data']['calendar']);symbol=source['symbol'];data=deepcopy(base['data'])
    operation='replace' if symbol in data['stocks'] else 'add'
    if operation=='replace':
        before=data['stocks'][symbol];by={r['date']:r for r in stock['points']}
        if stock['as_of']<before['as_of'] or any(r['level'] is not None and by[r['date']]['level'] is None for r in before['points']):raise ValueError('BSE replacement would shrink existing coverage')
    source_key='bse_vendor_'+symbol+'_'+source_digest
    if operation=='replace' and data['stocks'][symbol]==stock and data['source_digests'].get(source_key)==source_digest:return deepcopy(base)
    data['stocks'][symbol]=stock;data['source_digests'][source_key]=source_digest
    stamp=datetime.now(timezone.utc).isoformat();extension={'version':VERSION,'processor_digest':processor_digest(),'base_price_digest':base['content_digest'],'source_digest':source_digest,'symbol':symbol,'operation':operation,'checks':checks,'created_at':stamp};extension['content_digest']=digest(extension)
    packet={'version':base['version'],'processor_digest':base['processor_digest'],'checked_at':stamp,'data':data,EXTENSION_KEY:extension};packet['content_digest']=digest(packet)
    validate_extension(packet,base=base,root=root)
    return packet


def validate_extension(packet,*,base,root):
    extension=packet[EXTENSION_KEY];symbol=extension['symbol'];before=base['data'];data=packet['data']
    if (extension['version']!=VERSION or extension['processor_digest']!=processor_digest()
            or extension['base_price_digest']!=base['content_digest'] or not SYMBOL.fullmatch(symbol)
            or digest({k:v for k,v in extension.items() if k!='content_digest'})!=extension['content_digest']
            or packet['version']!=base['version'] or packet['processor_digest']!=base['processor_digest']
            or packet['checked_at']!=extension['created_at']):raise ValueError('BSE extension binding changed')
    _clock(extension['created_at']);stock,source,checks=source_stock(root,extension['source_digest'],data['calendar'])
    operation='replace' if symbol in before['stocks'] else 'add'
    if source['symbol']!=symbol or extension['operation']!=operation or extension['checks']!=checks or data['stocks'].get(symbol)!=stock:raise ValueError('BSE path differs from source reconstruction')
    expected=deepcopy(before);expected['stocks'][symbol]=stock;expected['source_digests']['bse_vendor_'+symbol+'_'+source['content_digest']]=source['content_digest']
    if data!=expected:raise ValueError('BSE extension changed another subject or shared basis')
    if operation=='replace':
        by={r['date']:r for r in stock['points']};old=before['stocks'][symbol]
        if stock['as_of']<old['as_of'] or any(r['level'] is not None and by[r['date']]['level'] is None for r in old['points']):raise ValueError('BSE replacement coverage regressed')
