"""Offline reconciliation of issuer unit NAVs with exact archived source decimals."""
from collections import Counter
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from etf_issuer_nav import NAV_VERSION, nav_definitions
from etf_asset_identity import parse_asset_disclosure
from etf_nav_parsers import parse_chinaamc, parse_efunds, parse_huatai, parse_jsfund, parse_nffund

VERSION='issuer_nav_raw_reconciliation_v1'
HUATAI_API='https://www.huatai-pb.com/common-web/chart/fundnettable/getFundNetTableJson'
HUATAI_SITE='9496d23c648f4a72a79150c3f2ac669b'
NF_API='https://www.nffund.com/nfwebApi/fund/newValueList'
CHINAAMC_API='https://www.chinaamc.com/product/fundLishijingzhi.do'
EFUNDS_SCHEMA='https://www.efunds.com.cn/js/fund_details/product-detail-overview.js?7905e4a6'


def response(directory,ref,now):
    key=ref['response_sha256']
    if not re.fullmatch('[a-f0-9]{64}',key):raise ValueError('invalid source hash')
    raw=(directory/'responses'/(key+'.raw')).read_bytes()
    observed=datetime.fromisoformat(ref['observed_at'])
    if (type(ref['bytes']) is not int or len(raw)!=ref['bytes'] or not 0<len(raw)<=4_000_000
        or hashlib.sha256(raw).hexdigest()!=key or observed.tzinfo is None or observed>now):
        raise ValueError('changed NAV original or invalid observation')
    return raw


def request(ref,code,url,params=None,method='GET'):
    if (ref['code']!=code or ref['url']!=url or ref['method']!=method or ref['params']!=(params or {})
        or any(type(ref['params'][k]) is not type(v) for k,v in (params or {}).items())):
        raise ValueError('NAV source query identity changed')


def reconcile_fund(directory:Path,code,calendar,rows,refs,now,*,version=NAV_VERSION):
    definition=nav_definitions(version)[code];provider=definition['provider'];points=[];asset=None
    if not refs or len(refs)>10:raise ValueError('missing or excessive NAV source references')
    originals=[response(directory,ref,now) for ref in refs]
    if provider=='jsfund':
        if len(refs)!=1:raise ValueError('unexpected JSFund responses')
        request(refs[0],code,definition['url'])
        points=[(p,refs[0]) for p in parse_jsfund(originals[0].decode('utf-8'),code,calendar,exact=True)]
    elif provider=='efunds':
        if len(refs)!=3:raise ValueError('missing EFunds page/schema/literal')
        literal=f'https://cdn.efunds.com.cn/market/2.0/{code[:6]}_1y.js'
        for ref,url in zip(refs,[definition['url'],EFUNDS_SCHEMA,literal]):request(ref,code,url)
        page,schema,text=[b.decode('utf-8') for b in originals]
        if (literal not in page or not re.search(r'var\s+fundCode\s*=\s*"'+code[:6]+'"',page)
            or '单位净值(元)' not in page or not re.search(r'2\s+EnumSourceTypeNetValue\s+单位净值',schema)):
            raise ValueError('EFunds identity, unit or field mapping changed')
        points=[(p,refs[2]) for p in parse_efunds(text,code,calendar,exact=True)]
        # The separate whole-fund asset review is scoped to 510310, not other EFunds products.
        if code=='510310.SH':asset=parse_asset_disclosure(page,refs[0],now)
    else:
        expected_pages=None;prior_oldest=None
        for page,(ref,raw) in enumerate(zip(refs,originals),1):
            if provider=='chinaamc':
                params={'fundcode':code[:6],'beginDate':calendar[0],'endDate':calendar[-1],'isQuery':'true' if page==1 else '', 'pageIndex':page}
                request(ref,code,CHINAAMC_API,params,'POST')
                parsed,pages=parse_chinaamc(raw.decode('utf-8'),code,calendar,page,exact=True)
            elif provider=='huatai_pb':
                params={'fundcode':code[:6],'from':calendar[0],'to':calendar[-1],'pages':f'{page}-10','siteId':HUATAI_SITE}
                request(ref,code,HUATAI_API,params)
                payload=json.loads(raw,parse_float=Decimal)
                if any(type(payload[k]) is not int for k in ('currentPage','totalPage','totalCount')):
                    raise ValueError('noninteger Huatai pagination')
                parsed,pages=parse_huatai(payload,code,calendar,page,exact=True)
                count=payload['totalCount']
                if (type(count) is not int or count!=len(calendar) or pages!=(count+9)//10
                    or len(payload['dataList'])!=min(10,count-(page-1)*10)):
                    raise ValueError('Huatai source total or page length changed')
            else:
                request(ref,code,NF_API,{'fundCode':code[:6],'curPage':page,'pageSize':10},'POST')
                payload=json.loads(raw,parse_float=Decimal)
                if any(type(payload['data']['jjjzList'][k]) is not int for k in ('pageNum','pageSize','size','total','pages')):
                    raise ValueError('noninteger NFFund pagination')
                parsed,count,oldest=parse_nffund(payload,code,calendar,page,exact=True)
                if (type(ref['reported_history_total']) is not int or ref['reported_history_total']!=count
                    or ref['pagination_basis']!='exact_requested_trading_calendar'
                    or prior_oldest is not None and payload['data']['jjjzList']['list'][0]['fdate_ex']>=prior_oldest
                    or page<len(refs) and oldest<=calendar[0]
                    or page==len(refs) and oldest>calendar[0]):
                    raise ValueError('NFFund history boundary, query total or ordering changed')
                prior_oldest=oldest;pages=len(refs)
            if provider!='nffund':
                if not 1<=pages<=10 or expected_pages is not None and pages!=expected_pages:raise ValueError('changing NAV page count')
                expected_pages=pages
                if len(refs)!=pages:raise ValueError('incomplete NAV page chain')
            points.extend((p,ref) for p in parsed)
    points.sort(key=lambda pair:pair[0]['nav_date'])
    if [p['nav_date'] for p,_ in points]!=calendar or [r['nav_date'] for r in rows]!=calendar:
        raise ValueError('NAV source or projection calendar incomplete')
    result=[]
    for (p,ref),row in zip(points,rows):
        if (row['ts_code']!=code or isinstance(row['unit_nav'],bool) or Decimal(str(row['unit_nav']))!=Decimal(p['source_value'])
            or p['nav_date']>datetime.fromisoformat(ref['observed_at']).astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()):
            raise ValueError('NAV projection differs from exact source decimal or observation date')
        result.append({'date':p['nav_date'],'raw_text':p['raw_text'],'source_value':p['source_value'],'fractional_digits':p['fractional_digits'],
                       'source_url':ref['url']+('?' + urlencode(ref['params']) if ref['method']=='GET' and ref['params'] else ''),
                       'request_method':ref['method'],'request_params':ref['params'],'response_sha256':ref['response_sha256'],'observed_at':ref['observed_at']})
    source_refs=[{'role':('product_identity','unit_NAV_schema','unit_NAV_data')[i] if provider=='efunds' else 'unit_NAV_data',
                  'url':ref['url'],'method':ref['method'],'params':ref['params'],'response_sha256':ref['response_sha256'],
                  'observed_at':ref['observed_at'],'bytes':ref['bytes']} for i,ref in enumerate(refs)]
    return {'code':code,'provider':provider,'source_field':definition['field'],'source_url':definition['url'],'unit':'CNY_per_share',
            **({'asset_disclosure':asset} if asset is not None else {}),
            'source_responses':source_refs,
            'source_response_count':len(refs),'records':result,'fractional_digit_counts':dict(Counter(p['fractional_digits'] for p in result))}


def reconcile_issuer_navs(directory,raw,now):
    version=raw['contract_version'];definitions=nav_definitions(version)
    if raw['definitions']!=definitions or set(raw['etf_navs'])!=set(definitions):raise ValueError('NAV profile or scope changed')
    refs=raw['responses'];codes=set(definitions)
    if any(ref['code'] not in codes for ref in refs):raise ValueError('foreign NAV source reference')
    funds=[reconcile_fund(directory,code,raw['calendar'],raw['etf_navs'][code],[r for r in refs if r['code']==code],now,version=version) for code in definitions]
    return {'version':VERSION,'availability':'source_reconciled','snapshot_digest':raw['content_digest'],'start':raw['calendar'][0],
            'through':raw['requested_through'],'source_response_count':len(refs),'nav_observations':sum(len(f['records']) for f in funds),
            'funds':funds,'exact_source_projection_verified':True,'historical_PIT':False,'corporate_actions_checked':False,
            'whole_fund_daily_scope_verified':False,'share_precision_verified':False,'final_revision_verified':False,'estimated_net_subscription_yuan':None,
            'note':'逐条核对基金公司原响应的单位净值字段与日表；不混用累计净值、参考净值或资产净值。原始小数文本仅描述本次返回，不据此确认全基金份额范围、份额精度、全窗事件、最终修订或历史当时可见性。净值齐全不解除净申赎估算的其他条件。'}
