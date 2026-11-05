"""Reconcile published ETF decimal values to archived responses on every offline read.

Matching a projection to its source is not evidence of whole-fund scope, a rounding
rule, final revisions, corporate-action clearance, or investor cash flow.
"""
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from etf_szse_history import API_URL, HTTP_API_URL, SZSE_CODES, history_url, plain

VERSION = 'etf_daily_raw_reconciliation_v1'
SSE_CODES = ('510300.SH','510310.SH','510330.SH','510500.SH','512100.SH')
SSE_API = 'https://query.sse.com.cn/commonQuery.do'
SSE_SQL = 'COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L'
NUMBER = r'(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)(?:\.\d+)?'


def decimal_value(value):
    if isinstance(value, bool) or value is None: raise ValueError('missing or boolean source value')
    text = plain(value)
    if not re.fullmatch(NUMBER, text): raise ValueError('invalid source decimal text')
    number = Decimal(text.replace(',',''))
    if not number.is_finite() or number <= 0: raise ValueError('nonpositive source value')
    return text, number


def timestamp(value, now):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result > now: raise ValueError('invalid source observation time')
    return result


def integer(value):
    if isinstance(value,bool) or not re.fullmatch(r'0|[1-9]\d*',str(value)):raise ValueError('invalid source integer')
    return int(value)


def response(directory, ref, now):
    if not re.fullmatch(r'[a-f0-9]{64}',ref['response_sha256']): raise ValueError('invalid source hash')
    raw = (directory/'responses'/(ref['response_sha256']+'.json')).read_bytes()
    if len(raw)>4_000_000 or hashlib.sha256(raw).hexdigest()!=ref['response_sha256']:
        raise ValueError('ETF archived source bytes changed')
    timestamp(ref['observed_at'],now)
    return json.loads(raw, parse_float=Decimal)


def point(code, day, value, ref, now, *, nav=False):
    day = date.fromisoformat(day).isoformat()
    if day > timestamp(ref['observed_at'],now).astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat():
        raise ValueError('source date postdates its observation')
    text, value = decimal_value(value)
    return {'code':code, 'date':day, 'raw_text':text, 'source_value':format(value,'f'),
            **({} if nav else {'ten_thousand_shares':format(value,'f'),'shares':format(value*10000,'f')}),
            'fractional_digits':len(text.split('.')[1]) if '.' in text else 0,
            'source_url':ref['url'], 'response_sha256':ref['response_sha256'], 'observed_at':ref['observed_at']}


def check_projection(rows, source, code, day_key, value_key):
    actual={}
    for row in rows:
        day=row[day_key]
        if day in actual or row['ts_code']!=code: raise ValueError('duplicate or foreign normalized ETF row')
        actual[day]=decimal_value(row[value_key])[1]
    expected={p['date']:Decimal(p['source_value']) for p in source}
    if len(expected)!=len(source) or actual!=expected:
        raise ValueError('ETF projection differs from exact source decimals or dates')


def summary(raw, funds, *, responses, nav_observations=0):
    return {'version':VERSION, 'availability':'source_reconciled', 'source_response_count':responses,
            'snapshot_digest':raw['content_digest'], 'start':raw['calendar'][0], 'through':raw['requested_through'],
            'share_observations':sum(len(f['records']) for f in funds), 'nav_observations':nav_observations, 'funds':funds,
            'exact_source_projection_verified':True, 'whole_fund_daily_scope_verified':False,
            'source_rounding_rule_verified':False, 'share_precision_verified':False, 'final_revision_verified':False,
            'corporate_actions_checked':False, 'estimated_net_subscription_yuan':None,
            'note':'逐条核对原响应与日表日期、代码和十进制数值一致；原始文本小数位只描述本次返回，尾零省略不证明字段精度、舍入方式或误差上界。原数值保留，不据此证明全基金范围、最终修订、份额事件或净申赎金额。'}


def reconcile_sse(directory:Path, raw, now):
    groups=defaultdict(dict);refs=raw['responses'];calendar=raw['calendar'];observed=defaultdict(list)
    for ref in refs:
        day,page=ref['query_date'],ref['page'];url=urlsplit(ref['url']);query=parse_qs(url.query,keep_blank_values=True)
        expected={'sqlId':[SSE_SQL],'isPagination':['true'],'STAT_DATE':[day],'pageHelp.pageSize':['1000'],
                  'pageHelp.pageNo':[str(page)],'pageHelp.beginPage':[str(page)],'pageHelp.endPage':[str(page)],'pageHelp.cacheSize':['1']}
        if (day not in calendar or type(page) is not int or not 1<=page<=10 or day in groups and page in groups[day]
            or url._replace(query='').geturl()!=SSE_API or query!=expected): raise ValueError('invalid SSE source query or page identity')
        groups[day][page]=(response(directory,ref,now),ref)
    for day,pages in groups.items():
        if sorted(pages)!=list(range(1,len(pages)+1)): raise ValueError('incomplete SSE source pages')
        records=[];totals=set()
        for page,(payload,ref) in sorted(pages.items()):
            meta=payload['pageHelp'];total=integer(meta['total']);totals.add(total)
            if (payload['sqlId']!=SSE_SQL or payload.get('actionErrors') or payload.get('fieldErrors')
                or integer(meta['pageNo'])!=page or integer(meta['pageCount'])!=len(pages)
                or len(pages)!=(total+999)//1000 or type(ref['complete_daily_rows']) is not int or ref['complete_daily_rows']!=total
                or 'data' in meta and meta['data']!=payload['result']): raise ValueError('SSE source scope or pagination changed')
            records.extend((row,ref) for row in payload['result'])
        if len(totals)!=1 or not records or len(records)!=next(iter(totals)): raise ValueError('SSE source total differs from rows')
        seen=set()
        for row,ref in records:
            code=row['SEC_CODE']
            if code in seen or row['STAT_DATE']!=day: raise ValueError('duplicate code or foreign date in SSE source')
            seen.add(code);full=code+'.SH'
            if full in SSE_CODES:observed[full].append(point(full,day,row['TOT_VOL'],ref,now))
    funds=[]
    for code in SSE_CODES:
        points=sorted(observed[code],key=lambda p:p['date']);check_projection(raw['etf_shares'][code],points,code,'trade_date','fd_share')
        funds.append({'code':code,'share_field':'TOT_VOL','share_unit':'ten_thousand_shares','records':points,
                      'fractional_digit_counts':dict(Counter(p['fractional_digits'] for p in points))})
    return summary(raw,funds,responses=len(refs))


def reconcile_szse(directory:Path, raw, now):
    groups=defaultdict(dict);refs=raw['responses'];calendar=raw['calendar'];api=raw['api_url'];observed=defaultdict(list);nav_count=0
    if api not in (API_URL,HTTP_API_URL):raise ValueError('unknown SZSE source endpoint')
    for ref in refs:
        code,kind,page=ref['code'],ref['kind'],ref['page']
        if (code not in SZSE_CODES or kind not in ('shares','NAV') or type(page) is not int or not 1<=page<=10
            or ref['url']!=history_url(api,code,calendar,nav=kind=='NAV',page=page) or page in groups[(code,kind)]):
            raise ValueError('invalid SZSE source identity or query')
        groups[(code,kind)][page]=(response(directory,ref,now),ref)
    for (code,kind),pages in groups.items():
        if sorted(pages)!=list(range(1,len(pages)+1)):raise ValueError('incomplete SZSE source pages')
        records=[];totals=set();nav=kind=='NAV';day_key,value_key=('nav_date','nav_per_share') if nav else ('size_date','current_size')
        for page,(payload,ref) in sorted(pages.items()):
            if not isinstance(payload,list) or len(payload)!=1:raise ValueError('unexpected SZSE source blocks')
            block=payload[0];meta=block['metadata']
            if (any(type(meta[k]) is not int for k in ('pagesize','pageno','pagecount','recordcount'))
                or meta['catalogid']!=('fund_jjjz' if nav else 'fund_jjgm')
                or not re.search(r'[（(]'+('元' if nav else '万份')+r'[）)]$',plain(meta['cols'][value_key]))):
                raise ValueError('SZSE source catalog, unit or pagination type changed')
            unpaged=nav and (meta['pagesize'],meta['pageno'],meta['pagecount'])==(-1,0,0)
            if unpaged:
                if len(pages)!=1 or meta['recordcount']!=0:raise ValueError('invalid unpaginated NAV block')
            elif (meta['pagesize']<=0 or meta['pageno']!=page or meta['pagecount']!=len(pages)
                  or meta['recordcount']<=0 or len(pages)!=(meta['recordcount']+meta['pagesize']-1)//meta['pagesize']):
                raise ValueError('truncated SZSE source pagination')
            if not unpaged:totals.add(meta['recordcount'])
            records.extend((row,ref) for row in block['data'])
        if totals and (len(totals)!=1 or len(records)!=next(iter(totals))):raise ValueError('inconsistent SZSE source total')
        seen=set()
        for row,ref in records:
            day=row[day_key]
            if day in seen or plain(row['fund_code'])!=code[:6]:raise ValueError('duplicate date or wrong fund in SZSE source')
            seen.add(day);p=point(code,day,row[value_key],ref,now,nav=nav)
            if day not in calendar:
                if nav:continue
                raise ValueError('SZSE share source outside requested calendar')
            observed[(code,kind)].append(p)
    funds=[]
    for code in SZSE_CODES:
        for kind,key,day_key,value_key in [('shares','etf_shares','trade_date','fd_share'),('NAV','etf_navs','nav_date','unit_nav')]:
            points=sorted(observed[(code,kind)],key=lambda p:p['date'])
            check_projection(raw[key][code],points,code,day_key,value_key)
            if kind=='NAV':nav_count+=len(points)
        points=sorted(observed[(code,'shares')],key=lambda p:p['date'])
        funds.append({'code':code,'share_field':'current_size','share_unit':'ten_thousand_shares','records':points,
                      'fractional_digit_counts':dict(Counter(p['fractional_digits'] for p in points))})
    return summary(raw,funds,responses=len(refs),nav_observations=nav_count)
