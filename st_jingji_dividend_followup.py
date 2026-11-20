"""A rounded result can coincide under multiple inputs without resolving a source conflict."""
from copy import deepcopy
from decimal import Decimal as D,ROUND_DOWN,ROUND_HALF_UP
from canonical_json import digest
import re

def jingji_dividend_followup(inputs,prior):
    packet=inputs.get('jingji_dividend_followup')
    if packet is None:return None
    if packet.get('version')!=1 or packet.get('content_digest')!=digest({k:v for k,v in packet.items()if k!='content_digest'}):raise ValueError('jingji packet changed')
    if digest(prior)!=PRIOR_DIGEST or digest(inputs['remaining_basis'])!=SOURCE_SCOPE_DIGEST:raise ValueError('jingji prior scope changed')
    if digest(packet['source'])!=NEW_SOURCE_DIGEST or digest(packet['result'])!=VIEW_DIGEST:raise ValueError('jingji source or interpretation changed')
    result=packet['result'];c=result['calculation'];a=D(c['printed_numerator']);eligible=D(c['printed_denominator']);total=D(c['total_shares']);cash=D(c['eligible_per_share_cash']);reference=D(c['reported_per_share']);before=D(c['eb_before'])
    checks={'printed_ten_exact':a/eligible*10,'printed_ten_truncated_6':(a/eligible*10).quantize(D('.000001'),rounding=ROUND_DOWN),'total_ten_exact':a/total*10,'total_ten_truncated_6':(a/total*10).quantize(D('.000001'),rounding=ROUND_DOWN),'total_per_share_exact':a/total,'total_per_share_truncated_7':(a/total).quantize(D('.0000001'),rounding=ROUND_DOWN),'eb_using_reported_reference_exact':before-reference,'eb_using_eligible_cash_exact':before-cash,'eb_using_reported_reference_rounded':(before-reference).quantize(D('.01'),rounding=ROUND_HALF_UP),'eb_using_eligible_cash_rounded':(before-cash).quantize(D('.01'),rounding=ROUND_HALF_UP)}
    if any(D(c[k])!=value for k,value in checks.items())or total-eligible!=D(c['excluded_shares']):raise ValueError('jingji calculation changed')
    text=re.sub(r'[\s,]','',packet['source']['texts'][2])
    if not all(value in text for value in ['20348617.67','616624778','622874778','0.326688','0.0326688','14.50','14.47']):raise ValueError('jingji printed source changed')
    if result['issuer_correction_verified']or result['unique_input_identified']or result['method_promotions']:raise ValueError('jingji unsupported certification')
    return deepcopy(result)

PRIOR_DIGEST='0ca864919702f8d0cada927086deff0e8211ba8d2b38336ebba6202adc9993a6'
SOURCE_SCOPE_DIGEST='2cf023df7366c1cb57142f6701199662ee82dbf9205cb2bc9f5454464f4da186'
NEW_SOURCE_DIGEST='056bab1e9f81cc98d8ead5d641e6288a1aacc9cd911926fe4a500eb9827472cb'
VIEW_DIGEST='ff82f2890fc22c72cc42b8fc2b7a8c948b7506ed2d2f322531d719ca54e8b803'
