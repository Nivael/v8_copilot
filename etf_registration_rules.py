"""Scoped CSDC document clauses describe channels, not acquired daily fund data."""
from datetime import date,datetime,timezone
from hashlib import sha256
from importlib.metadata import version
from io import BytesIO
import json
from pathlib import Path
import re
from urllib.parse import quote,urljoin,urlsplit,urlunsplit
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from etf_quarterly import compact
from settings import DATA_ROOT

VERSION='etf_registration_scoped_rules_v1'
PROFILE_PATH=Path(__file__).with_name('etf_registration_rules_v1.json')
PROFILE=json.loads(PROFILE_PATH.read_text())
OUTPUT=DATA_ROOT/'local_data/v8_copilot/market_risk/etf_registration_rules'
ROLES={'sh_daily','sh_effective','sz_route','sz_daily','sz_exchange','sz_effective','central_permission','central_backup_scope',
       'central_incremental','central_error','central_exclusion','central_effective'}
DATE=r'(20\d{2})年(\d{1,2})月(\d{1,2})日'


def processor_digest():
    root=Path(__file__).parent
    return digest({'files':{name:sha256((root/name).read_bytes()).hexdigest() for name in
        (Path(__file__).name,PROFILE_PATH.name,'etf_quarterly.py','canonical_json.py')},'pypdf':version('pypdf')})


PROCESSOR=processor_digest()


def stamp(value,now):
    result=datetime.fromisoformat(value)
    if result.tzinfo is None or result>now:raise ValueError('invalid observation time')
    return result


def check(pattern,text):
    found=list(re.finditer(pattern,text))
    if len(found)!=1:raise ValueError('missing or ambiguous clause role')
    return found[0]


def clauses(pages,doc):
    normalized=[compact(p) for p in pages]
    if (len(pages)!=doc['source']['pages'] or sha256(normalized[0].encode()).hexdigest()!=doc['cover_sha256']
        or doc['cover_title'] not in normalized[0] or doc['document_number'] not in normalized[0]):raise ValueError('wrong primary document identity')
    blocks={}
    for proof in doc['proofs']:
        role,page=proof['role'],proof['page']
        if role in blocks or role not in ROLES or type(page) is not int or not 1<=page<=len(pages):raise ValueError('invalid clause page or role')
        text=normalized[page-1];start,end=proof['start'],proof['end']
        if not start or not end or text.count(start)!=1:raise ValueError('ambiguous clause start')
        tail=text[text.index(start):]
        if tail.count(end)!=1:raise ValueError('ambiguous clause end')
        block=tail[:tail.index(end)+len(end)]
        if sha256(block.encode()).hexdigest()!=proof['sha256']:raise ValueError('changed scoped clause')
        blocks[role]=block
    return blocks


def parse_facts(blocks):
    if set(blocks)!=ROLES:raise ValueError('incomplete registration rule review')
    check('每日上交所闭市后,通过参与人远程操作平台\\(PROP\\)向基金管理人发送当日登记在册的ETF全体场内持有人名册',blocks['sh_daily'])
    check('基金管理人可通过D-COM系统接受每日的ETF份额持有明细数据\\(详见GLRMX.DBF\\)',blocks['sz_daily'])
    check('其余数据文件均由本公司和基金管理人直接交换',blocks['sz_exchange'])
    check('不通过代办证券公司经纪交易单元,而通过基金管理人直销申报跨市场股票ETF场外组合证券申购赎回申请',blocks['sz_route'])
    check('完成相应系统测试,签订相关业务协议,并向本公司申请成为平台参与人',blocks['central_permission'])
    check('份额登记机构按照有关规定,向平台报送公募基金份额登记数据',blocks['central_backup_scope'])
    check('于T\\+1日21:00前将T日',blocks['central_incremental'])
    check('每日向平台报送增量备份数据',blocks['central_incremental'])
    check('全量备份数据,原则上不得少于每年两次',blocks['central_incremental'])
    check('备份数据格式检查不合格的反馈文件\\(ERR格式反馈\\)',blocks['central_error'])
    check('于T\\+1日21:00前完成错误修正',blocks['central_error'])
    check('ETF\\)等产品的证券交易所场内份额,相关业务开展不适用本指引',blocks['central_exclusion'])
    effective={}
    for key,role,lead in [('sh-guide','sh_effective','本业务指南自'),('sz-guide','sz_effective','本指南自'),('central-exchange','central_effective','本指引自')]:
        found=check(lead+DATE+'起施行',blocks[role]);effective[key]=date(*map(int,found.groups())).isoformat()
    return {'effective_dates':effective,'shanghai':{'channel':'PROP','recipient':'基金管理人','frequency':'每日上交所闭市后','scope':'全体场内持有人名册','proof_page':17},
            'shenzhen':{'channel':'D-COM','recipient':'基金管理人','frequency':'每日','file_name':'GLRMX.DBF','scope':'ETF份额持有明细','proof_page':33,'direct_exchange_page':38,
                        'off_exchange_route_page':11,'off_exchange_route_means':'基金管理人直销申报通道','off_exchange_share_class_inferred':False,'actual_investor_identity_inferred':False},
            'central':{'institutional_access_required':True,'daily_backup_kind':'incremental','full_backup_min_per_year':2,'backup_deadline_as_stated':'T+1日21:00',
                       'format_error_correction_deadline_as_stated':'T+1日21:00','error_check_scope':'file_format','exchange_ETF_share_business_excluded':True,
                       'deadline_is_exchange_ETF_revision_confirmation':False,'permission_page':3,'backup_scope_page':8,'backup_page':9,'exclusion_page':18}}


def collect(directory=OUTPUT,now=None,full=False):
    now=now or datetime.now(timezone.utc);expected=PROFILE['index'];index_meta=json.loads((directory/'index.source.json').read_text())
    index=(directory/'index.html').read_bytes()
    if index_meta!=expected or sha256(index).hexdigest()!=expected['sha256']:raise ValueError('index source changed')
    index_time=stamp(expected['observed_at'],now);text=index.decode('utf-8');all_blocks={};docs=[]
    for doc in PROFILE['documents']:
        ref=doc['source'];source=json.loads((directory/(ref['label']+'.source.json')).read_text())
        if source!=ref:raise ValueError('document source metadata changed')
        observed=stamp(ref['observed_at'],now)
        if observed<index_time or doc['published_on']>observed.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat():raise ValueError('document publication/observation role conflict')
        matching=[]
        for row in re.findall(r'<li\b[^>]*>(.*?)</li>',text,re.S):
            links=re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>',row,re.S);dates=re.findall(r'<span class="date">([^<]+)</span>',row)
            for href,title in links:
                u=urlsplit(urljoin(expected['url'],href));url=urlunsplit(u._replace(path=quote(u.path,safe='/')))
                if url==ref['url'] and title.strip()==doc['listed_title']:matching.append(dates)
        if matching!=[[doc['published_on']]]:raise ValueError('document not bound to its own index date/link')
        pdf=(directory/(ref['raw_sha256']+'.pdf')).read_bytes();body=(directory/(ref['text_sha256']+'.json')).read_bytes()
        if (len(pdf)!=ref['bytes'] or not pdf.startswith(b'%PDF-') or sha256(pdf).hexdigest()!=ref['raw_sha256']
            or sha256(body).hexdigest()!=ref['text_sha256']):raise ValueError('changed primary PDF/text bytes')
        pages=json.loads(body)['pages']
        if full:
            from pypdf import PdfReader
            if [p.extract_text() or '' for p in PdfReader(BytesIO(pdf)).pages]!=pages:raise ValueError('cached text differs from original PDF')
        blocks=clauses(pages,doc)
        if set(blocks)&set(all_blocks):raise ValueError('duplicate clause role across documents')
        all_blocks.update(blocks)
        docs.append({**ref,'title':doc['listed_title'],'published_on':doc['published_on'],'proof_pages':sorted({1,*[p['page'] for p in doc['proofs']]}),
                     'clause_count':len(blocks),'effective_proof_page':next(p['page'] for p in doc['proofs'] if p['role'].endswith('effective'))})
    if {d['label'] for d in docs}!={'sh-guide','sz-guide','central-exchange'} or len(docs)!=3:raise ValueError('incomplete document scope')
    facts=parse_facts(all_blocks)
    for doc in docs:
        doc['effective_on']=facts['effective_dates'][doc['label']]
        if doc['published_on']>doc['effective_on']:raise ValueError('effective date predates publication')
    return {'documents':docs,'facts':facts,'index':expected}


def project(inputs):
    return {'version':VERSION,'availability':'scoped_rules_reviewed','reviewed_versions':3,'reviewed_clauses':12,
            'source_pages':sum(d['pages'] for d in inputs['documents']),'identity_and_proof_pages':sum(len(d['proof_pages']) for d in inputs['documents']),
            **inputs,'daily_registration_data_acquired':False,'full_document_semantics_checked':False,'full_window_versions_checked':False,
            'whole_fund_daily_scope_verified':False,'share_precision_verified':False,'final_revision_verified':False,'corporate_actions_checked':False,
            'historical_PIT':False,'effect_measured':False,'estimated_net_subscription_yuan':None,
            'note':'只核对三份目录列示2026版的指定条款，不是实际日登记数据、完整历史窗规则或八只基金业务已实施的证明。机构通道不等于公开日总份额；中央平台备份时点不能套成交易所ETF份额最终修订时点，场外直销申报也不等于场外份额类别或实际投资者身份。'}


def rules_status(directory=OUTPUT,now=None):
    now=now or datetime.now(timezone.utc);base={'version':VERSION,'availability':'missing','reviewed_versions':None,'reviewed_clauses':None,'documents':[],
        'daily_registration_data_acquired':False,'full_document_semantics_checked':False,'full_window_versions_checked':False,
        'whole_fund_daily_scope_verified':False,'share_precision_verified':False,'final_revision_verified':False,'corporate_actions_checked':False,
        'historical_PIT':False,'effect_measured':False,'estimated_net_subscription_yuan':None}
    if processor_digest()!=PROCESSOR:return {**base,'availability':'reload_required'}
    try:
        raw=json.loads((directory/'current.json').read_text());then=stamp(raw['materialized_at'],now)
        if raw['version']!=VERSION or raw['processor_digest']!=PROCESSOR or digest({k:v for k,v in raw.items() if k!='content_digest'})!=raw['content_digest']:raise ValueError('changed rule snapshot')
        inputs=collect(directory,then)
        if digest(inputs)!=raw['input_digest']:raise ValueError('changed rule inputs')
        if processor_digest()!=PROCESSOR:return {**base,'availability':'reload_required'}
        return {**base,**project(inputs),'content_digest':raw['content_digest'],'materialized_at':raw['materialized_at']}
    except (OSError,ValueError,TypeError,KeyError,IndexError,AttributeError):return {**base,'availability':'invalid' if (directory/'current.json').exists() else 'missing'}


def materialize(directory=OUTPUT,now=None):
    now=now or datetime.now(timezone.utc);path=directory/'current.json'
    if processor_digest()!=PROCESSOR:raise ValueError('reload changed processor')
    if path.exists() and json.loads(path.read_text()).get('version')!=VERSION:raise ValueError('foreign output')
    inputs=collect(directory,now,full=True);raw={'version':VERSION,'processor_digest':PROCESSOR,'input_digest':digest(inputs),'materialized_at':now.isoformat()}
    if digest(collect(directory,now))!=raw['input_digest'] or processor_digest()!=PROCESSOR:raise ValueError('sources or processor changed')
    raw['content_digest']=digest(raw);atomic_write_json(directory/'snapshots'/(raw['content_digest']+'.json'),raw);atomic_write_json(path,raw)
    return {'availability':'scoped_rules_reviewed','reviewed_versions':3,'reviewed_clauses':12,'content_digest':raw['content_digest']}


if __name__=='__main__':print(json.dumps(materialize(),ensure_ascii=False))
