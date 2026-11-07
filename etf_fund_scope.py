"""A single prospectus version explains distinct registers and rounding roles, not daily flows."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
from importlib.metadata import version
from io import BytesIO
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from etf_announcements import load_announcement_catalog
from etf_quarterly import compact
from settings import DATA_ROOT

VERSION='etf_fund_scope_business_roles_v1'
PROFILE_PATH=Path(__file__).with_name('etf_fund_scope_v1.json')
PROFILE=json.loads(PROFILE_PATH.read_text())
ROOT=DATA_ROOT/'local_data/v8_copilot/market_risk'
OUTPUT=ROOT/'etf_fund_scope'
ROLES={'version_dates','registrars','listed_identity','listed_transfer','iopv_rounding','share_classes','order_and_consideration',
       'off_subscription_rounding','off_redemption_rounding','registration_and_transfer','nav_rounding','distribution_mode','distribution_rounding'}
DATE=r'(20\d{2})年(\d{1,2})月(\d{1,2})日'


def processor_digest():
    root=Path(__file__).parent
    return digest({'files':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in
        (Path(__file__).name,PROFILE_PATH.name,'etf_announcements.py','etf_quarterly.py','canonical_json.py')},'pypdf':version('pypdf')})


PROCESSOR=processor_digest()


def stamp(value,now):
    result=datetime.fromisoformat(value)
    if result.tzinfo is None or result>now:raise ValueError('invalid observation time')
    return result


def one(pattern,text):
    matches=list(re.finditer(pattern,text))
    if len(matches)!=1:raise ValueError('missing or ambiguous business role')
    return matches[0]


def check(pattern,text):
    return one(pattern,text)


def parse_rules(pages,profile=PROFILE):
    doc=profile['document'];normalized=[compact(p) for p in pages]
    if (len(pages)!=doc['page_count'] or profile['fund_name'] not in normalized[0]
        or '基金管理人:'+profile['issuer'] not in normalized[0] or '更新的招募说明书' not in normalized[0]):
        raise ValueError('wrong primary prospectus identity')
    blocks={};locations={}
    for proof in profile['proofs']:
        role,page=proof['role'],proof['page']
        if role in blocks or role not in ROLES or type(page) is not int or not 1<=page<=len(pages):raise ValueError('invalid proof role or physical page')
        text=normalized[page-1];start,end=proof['start'],proof['end']
        if not start or not end or text.count(start)!=1:raise ValueError('ambiguous proof start')
        at=text.index(start);tail=text[at:]
        if tail.count(end)!=1:raise ValueError('ambiguous proof end')
        block=tail[:tail.index(end)+len(end)]
        if hashlib.sha256(block.encode()).hexdigest()!=proof['sha256']:raise ValueError('changed business-role passage')
        blocks[role]=block;locations[role]=page
    if set(blocks)!=ROLES:raise ValueError('incomplete scoped role review')
    cutoffs={}
    for key,label in [('financial','财务数据'),('NAV_performance','净值表现'),('personnel','主要人员情况'),('general_content','其他所载内容')]:
        found=one(label+'截止日为'+DATE,blocks['version_dates']);cutoffs[key]=date(*map(int,found.groups())).isoformat()
    if (any(value>doc['published_on'] for value in cutoffs.values()) or '未经审计' not in blocks['version_dates']):
        raise ValueError('inconsistent version cutoff roles')
    check(r'交易代码:'+doc['code'][:6]+r'\)',blocks['listed_identity'])
    check('分为场内份额与场外份额两种',blocks['share_classes'])
    check('场内上市交易以及申购、赎回等相关业务的登记结算由中国结算负责办理',blocks['registrars'])
    check('场外申购、赎回等相关业务的登记结算由'+re.escape(profile['issuer'])+'负责办理',blocks['registrars'])
    registration=blocks['registration_and_transfer']
    check('认购、二级市场买入或场内申购的基金份额属场内份额,由中国结算负责办理登记结算',registration)
    check('通过场外申购的基金份额属场外份额,由'+re.escape(profile['issuer'])+'负责办理登记结算',registration)
    check('条件许可情况下,在基金管理人制定并发布有关规则后,本基金场外份额可跨系统转托管为场内份额',registration)
    check('但除非基金管理人另行公告,场内份额不可跨系统转托管为场外份额',registration)
    check('申请办理跨系统转托管将基金份额转为场内份额后,方可上市交易',blocks['listed_transfer'])
    orders=blocks['order_and_consideration']
    check('场内份额采用份额申购和份额赎回',orders);check('场外份额采用金额申购、份额赎回',orders)
    check('场内份额的申购对价、赎回对价包括组合证券、现金替代、现金差额及其他对价',orders)
    check('场外份额的申购对价、赎回对价为现金',orders)
    check('参考净值的计算以四舍五入的方法保留小数点后4位',blocks['iopv_rounding'])
    check('有效份额单位为份,份额计算结果按四舍五入方法保留到整数位',blocks['off_subscription_rounding'])
    check('申购费用以人民币元为单位,四舍五入保留至小数点后两位',blocks['off_subscription_rounding'])
    check('赎回金额、赎回费用的单位为人民币元,四舍五入保留到小数点两位',blocks['off_redemption_rounding'])
    check('基金份额净值是按照.*精确到0.0001元,小数点后第五位四舍五入',blocks['nav_rounding'])
    check('场内及场外份额的收益分配方式均采用现金分红',blocks['distribution_mode'])
    check('每基金份额的应分配收益为.*保留小数点后3位,第4位舍去',blocks['distribution_rounding'])
    rules=[]
    for target,unit,digits,method,role in [('iopv','CNY_per_share',4,'half_up','iopv_rounding'),
        ('off_exchange_subscribed_shares','fund_share',0,'half_up','off_subscription_rounding'),
        ('off_exchange_subscription_fee','CNY',2,'half_up','off_subscription_rounding'),
        ('off_exchange_redemption_payment_and_fee','CNY',2,'half_up','off_redemption_rounding'),
        ('unit_NAV','CNY_per_share',4,'half_up','nav_rounding'),('distribution_per_share','CNY_per_share',3,'truncate','distribution_rounding')]:
        rules.append({'target':target,'unit':unit,'fractional_digits':digits,'method':method,'proof_page':locations[role],
                      'applies_to_exchange_daily_share_field':False})
    return {'cutoffs':cutoffs,'financial_audit_status':'version_states_unaudited',
            'registrars':{'exchange':'中国证券登记结算有限责任公司','off_exchange':profile['issuer'],'proof_pages':[locations['registrars'],locations['registration_and_transfer']]},
            'transfer':{'declared_direction':'off_exchange_to_exchange','conditional':True,'requires_published_rules':True,
                        'reverse_requires_separate_announcement':True,'actual_window_transfers':None,'daily_adjustment_applied':False,
                        'proof_pages':[locations['listed_transfer'],locations['registration_and_transfer']]},
            'routes':[{'register':'exchange','creation_application':'shares','redemption_application':'shares','consideration':['securities','cash_substitution','cash_difference','other'],
                       'proof_page':locations['order_and_consideration']},
                      {'register':'off_exchange','creation_application':'amount','redemption_application':'shares','consideration':['cash'],'proof_page':locations['order_and_consideration']}],
            'rounding_rules':rules,'distribution_mode_as_stated':'cash_both_registers','distribution_mode_proof_page':locations['distribution_mode'],
            'daily_exchange_share_rounding_rule':None,'current_business_availability_verified':False}


def collect_inputs(directory=OUTPUT,*,root=ROOT,now=None,full=False):
    now=now or datetime.now(timezone.utc);expected=PROFILE['document'];meta,catalogs=load_announcement_catalog(root/'etf_announcements',now)
    if meta['availability']!='observed' or meta['content_digest']!=expected['catalog_digest']:raise ValueError('fund catalog binding changed')
    docs=[r for r in catalogs[expected['code']]['records'] if r['document_id']==expected['document_id']]
    if len(docs)!=1 or any(docs[0][k]!=expected[k] for k in ('code','published_on','title','url')):raise ValueError('prospectus source is not the bound fund catalog item')
    ref=json.loads((directory/'source.json').read_text())
    if ref!=expected or ref['response_url']!=ref['url']:raise ValueError('source observation or URL changed')
    observed=stamp(ref['observed_at'],now)
    if observed.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()<ref['published_on']:raise ValueError('observation predates publication')
    pdf=(directory/(ref['raw_sha256']+'.pdf')).read_bytes();text=(directory/(ref['text_sha256']+'.json')).read_bytes()
    if (len(pdf)!=ref['bytes'] or not pdf.startswith(b'%PDF-') or hashlib.sha256(pdf).hexdigest()!=ref['raw_sha256']
        or hashlib.sha256(text).hexdigest()!=ref['text_sha256']):raise ValueError('source bytes changed')
    pages=json.loads(text)['pages']
    if full:
        from pypdf import PdfReader
        if [p.extract_text() or '' for p in PdfReader(BytesIO(pdf)).pages]!=pages:raise ValueError('cached text differs from primary PDF')
    return {'document':ref,'facts':parse_rules(pages,PROFILE),'proof_pages':sorted({1,*[p['page'] for p in PROFILE['proofs']]})}


def project(inputs):
    doc=inputs['document']
    return {'version':VERSION,'availability':'scoped_rules_reviewed','review_scope':'one_prospectus_version_business_roles_only',
            'document':doc,**inputs['facts'],'proof_pages':inputs['proof_pages'],'reviewed_documents':1,'reviewed_passages':len(ROLES),
            'whole_fund_daily_scope_verified':False,'share_precision_verified':False,'final_revision_verified':False,'corporate_actions_checked':False,
            'full_document_semantics_checked':False,'all_window_share_events_verified':False,'historical_PIT':False,'effect_measured':False,'estimated_net_subscription_yuan':None,
            'note':'仅核对这一发行版本的登记、业务和舍入对象；不是当期业务实施、逐日全基金范围、交易所日份额舍入或全窗事件证明。跨系统转托管的实际数量未知，不校正日序列；说明书版本与原105项选中文档范围分开计数。'}


def scope_status(directory=OUTPUT,*,root=ROOT,now=None):
    now=now or datetime.now(timezone.utc)
    base={'version':VERSION,'availability':'missing','reviewed_documents':None,'reviewed_passages':None,'proof_pages':[],
          'whole_fund_daily_scope_verified':False,'share_precision_verified':False,'final_revision_verified':False,'corporate_actions_checked':False,
          'full_document_semantics_checked':False,'all_window_share_events_verified':False,'historical_PIT':False,'effect_measured':False,'estimated_net_subscription_yuan':None}
    if processor_digest()!=PROCESSOR:return {**base,'availability':'reload_required'}
    try:
        raw=json.loads((directory/'current.json').read_text());then=stamp(raw['materialized_at'],now)
        if (raw['version']!=VERSION or raw['processor_digest']!=PROCESSOR or digest({k:v for k,v in raw.items() if k!='content_digest'})!=raw['content_digest']):
            raise ValueError('scope rules snapshot binding changed')
        inputs=collect_inputs(directory,root=root,now=then)
        if digest(inputs)!=raw['input_digest']:raise ValueError('scope rules inputs changed')
        if processor_digest()!=PROCESSOR:return {**base,'availability':'reload_required'}
        return {**base,**project(inputs),'content_digest':raw['content_digest'],'materialized_at':raw['materialized_at']}
    except (OSError,ValueError,TypeError,KeyError,IndexError,AttributeError):return {**base,'availability':'invalid' if (directory/'current.json').exists() else 'missing'}


def materialize(directory=OUTPUT,*,root=ROOT,now=None):
    now=now or datetime.now(timezone.utc);path=directory/'current.json'
    if processor_digest()!=PROCESSOR:raise ValueError('reload processor')
    if path.exists() and json.loads(path.read_text()).get('version')!=VERSION:raise ValueError('foreign output')
    inputs=collect_inputs(directory,root=root,now=now,full=True);report=project(inputs)
    raw={'version':VERSION,'processor_digest':PROCESSOR,'input_digest':digest(inputs),'materialized_at':now.isoformat()}
    if digest(collect_inputs(directory,root=root,now=now))!=raw['input_digest'] or processor_digest()!=PROCESSOR:raise ValueError('sources or processor changed')
    raw['content_digest']=digest(raw);atomic_write_json(directory/'snapshots'/(raw['content_digest']+'.json'),raw);atomic_write_json(path,raw)
    return {'availability':report['availability'],'reviewed_documents':1,'reviewed_passages':len(ROLES),'content_digest':raw['content_digest']}


if __name__=='__main__':
    argparse.ArgumentParser(description=__doc__).parse_args();print(json.dumps(materialize(),ensure_ascii=False))
