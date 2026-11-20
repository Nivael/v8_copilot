PRIOR_DIGEST='7d39ba1b3c8885d95600f96a43ca74d4c54654805abc0047095e85f8319d8344'
COMPANY_DIGEST='a655dc67452e3eaefaf5f972be91f31f3011dd1e4f10fb1eda14441ca5d6b355'
AUTHORITIES_DIGEST='f11c3877416417265f2920482ca865d931944b1a008284077d8cdea974d93903'
RESULT_DIGEST='ef7a836b009b8f45415a46011683362dd5bcd2c4759c65d5a82db2a8044ddc83'
"""Policy existence, disclosure timing and accounting certification are separate claims."""
from base64 import b64decode
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import re
from canonical_json import digest

def baili_policy_followup(inputs, prior):
    packet=inputs.get('baili_policy_followup')
    if packet is None:return None
    if packet.get('version')!=1 or packet.get('content_digest')!=digest({k:v for k,v in packet.items()if k!='content_digest'}):raise ValueError('baili packet changed')
    if digest(prior)!=PRIOR_DIGEST:raise ValueError('baili prior changed')
    company=[s for s in inputs['twentyseventh_period_followup']['sources']if s['announcement_id']in ['1225534310','1225631527']]
    if digest(company)!=COMPANY_DIGEST:raise ValueError('baili company evidence changed')
    if digest(packet['authorities'])!=AUTHORITIES_DIGEST:raise ValueError('baili official evidence changed')
    for source in packet['authorities']:
        if sha256(b64decode(source['html_base64'])).hexdigest()!=source['sha256'] or sha256(source['text'].encode()).hexdigest()!=source['text_sha256']:raise ValueError('baili source bytes changed')
    norm=lambda text:re.sub(r'\s+','',text)
    texts={s['key']:norm(s['text'])for s in packet['authorities']}
    if not all(value in texts['mof-policy']for value in ['2026年7月16日','2026年07月17日','2026年9月1日','2027年9月1日','2%','4%']):raise ValueError('baili policy identity')
    if '前期财务报告批准报出时能够取得的可靠信息'not in texts['cas28'] or '未来应纳税所得额'not in texts['cas18']:raise ValueError('baili accounting identity')
    h=next(s for s in company if s['announcement_id']=='1225534310');c=next(s for s in company if s['announcement_id']=='1225631527')
    if '关于调整部分电池消费税政策的公告'not in h['selected_pages']['10']or '董事会批准报送日期：2026年8月28日'not in norm(h['selected_pages']['190'])or '半年度报告披露后新发布'not in norm(c['selected_pages']['3']):raise ValueError('baili chronology evidence')
    result=packet['result']
    if digest(result)!=RESULT_DIGEST:raise ValueError('baili interpretation changed')
    financial=result['verified']
    if Decimal(financial['asset_before'])-Decimal(financial['asset_reduction'])!=Decimal(financial['asset_after']):raise ValueError('baili asset identity')
    if financial['policy_after_h1_disclosure']or financial['accounting_treatment_certified']or financial['cash_payment_proven']or result['method_promotions']:raise ValueError('baili unsupported certification')
    return deepcopy(result)
