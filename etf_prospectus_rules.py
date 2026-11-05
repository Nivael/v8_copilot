"""Reviewed publication versions describe rules, examples and historical restatements, not current events."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
import hashlib
from pathlib import Path
import re

from canonical_json import digest
from etf_quarterly import compact, decimal_text, load_report_capture, read_bound_report

VERSION = 'etf_prospectus_rule_review_v1'
FUND_NAMES = {'510300.SH':'华泰柏瑞沪深300交易型开放式指数证券投资基金',
              '159922.SZ':'嘉实中证500交易型开放式指数证券投资基金'}
ROUTES = {'510300.SH':{'ordinary_create_redeem','collection_create'},
          '159922.SZ':{'physical_create_redeem','sz_physical_sh_cash_substitute','collection_create'}}


def proof(page, text): return {'page':page,'text':text}


# Each proof is a deliberately read clause in a fixed raw/text version. These
# are positive rule facts; they neither classify the whole document nor prove
# that no event occurred after its content cutoff.
CASES = [
    {'code':'510300.SH', 'document_id':'076dbe1af397e2695650f35a96f5cf68e92ef7f23349b576c863cb0a5b20e7a6',
     'published_on':'2026-08-13', 'raw_sha256':'e5c1d3bf755f595766c5f4ff4c64b5555e332bd8d466d8d2603cd0c8466f7432',
     'text_sha256':'4adb493232e184c6c313f6c10d063d166c351244727755f011763e59b68de989',
     'cutoffs':proof(3,'本更新招募说明书所载内容截止日为2026年07月31日,有关财务和业绩表现数据截止日为2026年06月30日,财务和业绩表现数据未经审计。'),
     'minimum_units':[
         {'route':'ordinary_create_redeem','label':'申购 / 赎回',
          'heading':proof(35,'十、基金份额的申购赎回'),
          'clause':proof(35,'本基金最小申购、赎回单位为90万份,基金管理人有权对其进行更改,并在更改前至少3个工作日在中国证监会指定媒介公告。')},
         {'route':'collection_create','label':'集合申购',
          'heading':proof(43,'6、集合申购的数额限制'),
          'clause':proof(43,'目前,本基金最小申购单位为90万份。')},
     ],
     'consideration':proof(35,'基金的申购对价、赎回对价包括组合证券、现金替代、现金差额及其他对价。'),
     'cash_distribution':proof(65,'基金收益分配采用现金方式;'),
     'frequency':proof(65,'基金收益分配每年至多4次;'),
     'distribution_condition':proof(65,'基金收益评价日核定的基金累计报酬率超过标的指数同期累计报酬率达到1%以上,方可对超额收益进行分配;'),
     'history':{
         'date':proof(32,'本基金的基金份额折算日为2012年5月11日。'),
         'ratio':proof(32,'根据基金份额折算公式,基金份额折算比例为0.37094933,'),
         'registration':proof(32,'并由中国证券登记结算有限责任公司上海分公司于2012年5月14日进行了变更登记。'),
         'rounding':proof(32,'折算后的基金份额采取四舍五入的方法计算保留到整数位。'),
     },
     'illustration':{
         'premise':proof(31,'2、基金份额折算的举例假设某投资者在基金募集期内认购了5,000份,'),
         'calculation':proof(32,'该投资者折算后的基金份额=5,000×0.26671819=1,334'),
     }},
    {'code':'159922.SZ', 'document_id':'6c2fdf0400bed6d5fd69d7a7e18a7c42e976aa70de9d738430b2c25291513081',
     'published_on':'2026-08-29', 'raw_sha256':'a1f1756d9ecd57256dc9c43a568f73bff0dab2c823d4381092f4e7951cc0a8a4',
     'text_sha256':'b1fa1d2d6da67e0678ba89bd8ce93358d30f9b236a1f0d25571b82704ee4b1d1',
     'cutoffs':proof(3,'本招募说明书所载内容截止日为2026年7月29日,有关财务数据和净值表现截止日为2026年6月30日(未经审计),特别事项注明除外。'),
     'minimum_units':[
         {'route':'physical_create_redeem','label':'实物申购 / 赎回',
          'heading':proof(53,'一、实物申购赎回'),
          'clause':proof(53,'目前,本基金最小申购、赎回单位为100万份,基金管理人可根据市场情况,在法律法规允许的情况下,调整申购与赎回的数额限制,基金管理人必须在调整生效前依照《信息披露办法》的有关规定指定媒介公告。')},
         {'route':'sz_physical_sh_cash_substitute','label':'深市股票实物、沪市股票现金替代申赎',
          'heading':proof(61,'二、场内“深市股票实物申赎,沪市股票现金替代”申购赎回'),
          'clause':proof(64,'目前,本基金最小申购赎回单位为100万份。')},
         {'route':'collection_create','label':'集合申购',
          'heading':proof(75,'6、集合申购的数额限制'),
          'clause':proof(75,'目前,本基金最小申购单位为100万份。')},
     ],
     'consideration':proof(53,'本基金的申购对价、赎回对价包括组合证券、现金替代、现金差额及其他对价。'),
     'cash_distribution':proof(103,'本基金收益分配采取现金分红;'),
     'frequency':proof(103,'本基金收益每年至多分配12次,'),
     'distribution_condition':proof(103,'基金收益评价日核定的基金净值增长率超过标的指数同期增长率达到1%以上时,基金管理人可以进行收益分配;'),
     'history':{
         'date':proof(50,'(一)基金份额折算的时间2013年3月5日。'),
         'ratio':proof(50,'中国证券登记结算有限责任公司按折算比例0.28038605对2013年3月5日(权益登记日)登记在册的本基金的基金份额实施折算,'),
         'registration':proof(50,'并于2013年3月6日进行了变更登记,'),
         'rounding':proof(50,'折算后的基金份额保留到整数位,小数部分舍去,由此产生的误差计入基金财产。'),
     },
     'illustration':None},
]


def parser_digest():
    return digest({name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
                   for name in (Path(__file__).name,'etf_quarterly.py')})


PARSER_DIGEST = parser_digest()
CHINESE_DATE = r'(\d{4})年(\d{1,2})月(\d{1,2})日'


def one(pattern, text):
    found = list(re.finditer(pattern,text))
    if len(found)!=1: raise ValueError('missing or ambiguous reviewed rule field')
    return found[0]


def as_date(match): return date(*map(int,match.groups())).isoformat()


def version_dates(case):
    dates=list(re.finditer(CHINESE_DATE,case['cutoffs']['text']))
    if len(dates)!=2 or '未经审计' not in case['cutoffs']['text']: raise ValueError('unverified content/financial cutoff')
    content_asof,financial_asof=map(as_date,dates)
    if not financial_asof<=content_asof<case['published_on']: raise ValueError('inconsistent version cutoff dates')
    return content_asof,financial_asof


def all_proofs(case):
    proofs = [case[key] for key in ('cutoffs','consideration','cash_distribution','frequency','distribution_condition')]
    for route in case['minimum_units']: proofs += [route['heading'],route['clause']]
    proofs += list(case['history'].values())
    if case['illustration']: proofs += list(case['illustration'].values())
    return proofs


def parse_prospectus_rules(pages, case):
    code = case['code']
    if code not in FUND_NAMES or not pages or any(not isinstance(page,str) for page in pages): raise ValueError('unknown prospectus identity')
    normalized = [compact(page) for page in pages]
    if FUND_NAMES[code] not in normalized[0] or '招募说明书' not in normalized[0]: raise ValueError('wrong prospectus fund')
    for item in all_proofs(case):
        if (type(item['page']) is not int or not 1<=item['page']<=len(pages) or not item['text']
            or normalized[item['page']-1].count(item['text'])!=1): raise ValueError('changed reviewed rule clause')
    content_asof,financial_asof=version_dates(case)
    minima=[]
    for unit in case['minimum_units']:
        if unit['heading']['page']>unit['clause']['page']:raise ValueError('business context follows the quoted unit')
        found = one(r'最小申购(?:、?赎回)?单位为([1-9]\d*)万份',unit['clause']['text'])
        minima.append({'route':unit['route'],'label':unit['label'],'stated_unit_shares':str(int(found[1])*10000),
                       'table_page':unit['clause']['page'],'quantity_scope':'fund_shares_per_business_unit',
                       'effective_at_market_target':'not_verified'})
    if len(minima)!=len(ROUTES[code]) or {row['route'] for row in minima}!=ROUTES[code]: raise ValueError('missing or duplicate business route')
    if '组合证券、现金替代、现金差额及其他对价' not in case['consideration']['text']: raise ValueError('unverified consideration scope')
    if case['cash_distribution']['text'] not in ('基金收益分配采用现金方式;','本基金收益分配采取现金分红;'): raise ValueError('different distribution mode')
    frequency = one(r'每年至多(?:分配)?([1-9]\d*)次',case['frequency']['text'])
    history=case['history']
    event_on=as_date(one(CHINESE_DATE,history['date']['text']))
    registered_on=as_date(one(CHINESE_DATE,history['registration']['text']))
    factor=one(r'折算比例(?:为)?(\d+\.\d{8})(?!\d)',history['ratio']['text'])[1]
    if not event_on<=registered_on<=content_asof or Decimal(factor)<=0: raise ValueError('invalid historical restatement')
    rounding = ('nearest_whole_share' if '四舍五入' in history['rounding']['text'] else
                'floor_to_whole_share' if '小数部分舍去' in history['rounding']['text'] else None)
    if rounding is None: raise ValueError('unknown historical rounding clause')
    example=None
    if case['illustration']:
        item=case['illustration']
        if '举例假设' not in item['premise']['text']: raise ValueError('illustration has no hypothetical premise')
        calc=one(r'折算后的基金份额=([\d,]+)×(\d+\.\d{8})=([\d,]+)',item['calculation']['text'])
        before,ratio,after=Decimal(calc[1].replace(',','')),Decimal(calc[2]),Decimal(calc[3].replace(',',''))
        premise=Decimal(one(r'认购了([\d,]+)份',item['premise']['text'])[1].replace(',',''))
        if premise!=before or (before*ratio).quantize(Decimal(1),rounding=ROUND_HALF_UP)!=after: raise ValueError('illustration premise or rounding does not balance')
        example={'classification':'hypothetical_illustration','before_shares':decimal_text(before),
                 'stated_ratio':calc[2],'after_shares':decimal_text(after),'pages':sorted({v['page'] for v in item.values()}),
                 'not_a_verified_event':True}
    return {'code':code,'content_asof':content_asof,'financial_data_asof':financial_asof,
            'cutoff_exception': '特别事项注明除外' if '特别事项注明除外' in case['cutoffs']['text'] else None,
            'financial_audit_status':'report_states_unaudited','minimum_units':minima,
            'consideration_components':['组合证券','现金替代','现金差额','其他对价'],'cash_is_only_consideration':False,
            'distribution_mode_as_stated':'cash','max_annual_distributions_as_stated':int(frequency[1]),
            'distribution_condition_as_stated':case['distribution_condition']['text'],
            'actual_distributions_in_market_window':None,'current_cash_flow_yuan':None,
            'historical_restatement':{'classification':'later_prospectus_restatement','event_on':event_on,'registered_on':registered_on,
                'stated_ratio':factor,'rounding_in_this_version':rounding,'pages':sorted({v['page'] for v in history.values()}),
                'not_historical_point_in_time_evidence':True},
            'illustration':example,'source_page_count':len(pages),'reviewed_pages':sorted({item['page'] for item in all_proofs(case)}),
            'full_document_semantics_checked':False,'corporate_actions_checked':False,'market_window_correction_applied':False}


def prospectus_rule_status(directory:Path,announcements:dict,now:datetime)->dict:
    base={'version':VERSION,'availability':'missing','versions':[],'reviewed_versions':0,'selected_prospectus_versions':None,
          'corporate_actions_checked':False,'all_window_documents_reconciled':False,
          'note':'仅核对所列版本的具体规则、假设示例和历史复述；发布日期、内容截止日、财务截止日和本次取得时间分开。规则上限不是实际发生次数，每笔业务单位不是基金总份额倍数；不作为当前有效规则、实际事件或净现金流证明。'}
    if parser_digest()!=PARSER_DIGEST:return {**base,'availability':'reload_required'}
    if announcements.get('availability')!='observed' or announcements.get('fulltext',{}).get('availability')!='observed':return base
    try:
        capture,key=load_report_capture(directory,announcements,now)
        docs=[doc for cat in announcements['catalogs'] for doc in cat['required_documents']]
        selected={doc['document_id']:doc for doc in docs}
        if len(selected)!=len(docs):raise ValueError('duplicate prospectus inventory')
        count=sum('招募说明书' in doc['title'] for doc in docs)
    except (OSError,ValueError,TypeError,KeyError):return {**base,'availability':'invalid'}
    versions,failures=[],[]
    for case in CASES:
        try:
            doc=selected[case['document_id']];result=capture['documents'][case['document_id']]
            if (doc['code']!=case['code'] or doc['published_on']!=case['published_on'] or '招募说明书' not in doc['title']
                or result['format']!='pdf' or result['text_sha256']!=case['text_sha256']
                or result['responses'][-1]['response_sha256']!=case['raw_sha256']):raise ValueError('reviewed version changed')
            content_asof,_=version_dates(case)
            version=read_bound_report(directory,capture,doc,content_asof,announcements['through'],
                                      lambda pages:parse_prospectus_rules(pages,case))
            versions.append(version)
        except (OSError,ValueError,TypeError,KeyError,IndexError):
            failures.append({'code':case['code'],'document_id':case['document_id'],'reason':'reviewed_version_or_rules_changed'})
    return {**base,'availability':'partial' if versions else 'invalid','versions':versions,'reviewed_versions':len(versions),
            'selected_prospectus_versions':count,'failures':failures,'catalog_digest':announcements['content_digest'],
            'capture_digest':key,'parser_digest':PARSER_DIGEST}
