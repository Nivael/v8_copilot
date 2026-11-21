"""Use saved official fields literally: OHLC is available, actual limits are not."""
from decimal import Decimal as D
from hashlib import sha256
from pathlib import Path
from html import unescape
import json
from canonical_json import digest
from market_breadth_export import export_rows,HEADERS,FIELDS
from recent_breadth_inputs import verify_szse_day
from risk_list_nov20_review import review


def analyze(e, folder, risk_evidence):
    folder=Path(folder)
    if digest(risk_evidence)!=e['risk_content_digest']:raise ValueError('dated risk evidence changed')
    risk=review(risk_evidence)
    group=risk['comparisons'][0]
    if group['source_as_of']!='2026-11-20' or group['main_a_shares']!=74:raise ValueError('dated mainboard scope changed')
    raw=(folder/'days/2026-11-20.json').read_bytes()
    if sha256(raw).hexdigest()!=e['szse_day_sha256']:raise ValueError('day packet bytes changed')
    packet=json.loads(raw);verify_szse_day(packet,folder)
    ref=packet['responses'][2];body=(folder/'responses'/(ref['response_sha256']+'.xlsx')).read_bytes()
    rows=export_rows(body)
    if HEADERS!=e['reported_columns']or FIELDS!=e['reported_fields']:raise ValueError('declared raw columns changed')
    # The established breadth replay checks eight columns; this review also
    # checks the complete twelve-column boundary controls before using OHLC.
    # The P/E column is named syl in XLSX extraction and syl1 in JSON controls.
    def normalized(r):
        if ('syl'in r)==('syl1'in r):raise ValueError('ambiguous P/E control field')
        return {k:unescape(str(r[k]if k!='syl'else r['syl']if'syl'in r else r['syl1'])).replace('\u00a0',' ').strip()for k in FIELDS}
    for source,segment in [(packet['responses'][0],rows[:10]),(packet['responses'][1],rows[-len(json.loads((folder/'responses'/(packet['responses'][1]['response_sha256']+'.json')).read_bytes())[0]['data']):])]:
        controls=json.loads((folder/'responses'/(source['response_sha256']+'.json')).read_bytes())[0]['data']
        if [normalized(r)for r in segment]!=[normalized(r)for r in controls]:raise ValueError('full-field boundary control differs')
    expected={r['ts_code']:r['name']for r in group['rows']};normalized_quotes={r['ts_code']:r for r in packet['block']['rows']};chosen=[]
    for row in rows:
        symbol=row['zqdm']+'.SZ'
        if symbol not in expected:continue
        if row['jyrq']!='2026-11-20'or ''.join(row['zqjc'].split())!=''.join(expected[symbol].split()):raise ValueError('selected date/name changed')
        nums={k:D(str(row[k]).replace(',',''))for k in ['qss','ks','zg','zd','ss','cjgs']}
        if any(not n.is_finite()for n in nums.values()):raise ValueError('nonfinite field')
        q=normalized_quotes[symbol];traded=nums['cjgs']>0
        if traded!=q['is_trading']or nums['ss']!=D(str(q['last']))or nums['qss']!=D(str(q['prev_close'])):raise ValueError('normalized quote mismatch')
        result={'symbol':symbol,'name':expected[symbol],'is_trading':traded,'close':str(nums['ss']),'reference':str(nums['qss'])}
        if not traded:
            result['status']='no_trade_reference_only'
        else:
            if min(nums[k]for k in ['qss','ks','zg','zd','ss'])<=0 or not nums['zd']<=min(nums['ks'],nums['ss'])<=max(nums['ks'],nums['ss'])<=nums['zg']:raise ValueError('invalid traded OHLC')
            same=nums['ks']==nums['zg']==nums['zd']==nums['ss']
            result.update(status='observed_trade',open=str(nums['ks']),high=str(nums['zg']),low=str(nums['zd']),
                          one_observed_price=same,close_at_low=nums['ss']==nums['zd'],
                          close_direction='higher'if nums['ss']>nums['qss']else'lower'if nums['ss']<nums['qss']else'flat')
        chosen.append(result)
    if len(chosen)!=len(expected)or {r['symbol']for r in chosen}!=set(expected):raise ValueError('selected coverage incomplete')
    traded=[r for r in chosen if r['is_trading']];one=[r for r in traded if r['one_observed_price']]
    return {'version':'szse_main_risk_ohlc_field_review_v1','date':'2026-11-20','official_dated_mainboard_members':74,
            'trading':len(traded),'nontrading':len(chosen)-len(traded),'one_price_trading':len(one),
            'one_price_higher':sum(r['close_direction']=='higher'for r in one),'one_price_lower':sum(r['close_direction']=='lower'for r in one),'one_price_flat':sum(r['close_direction']=='flat'for r in one),
            'close_at_daily_low':sum(r['close_at_low']for r in traded),'actual_limit_columns':[h for h in HEADERS if h in ('涨停价','跌停价','涨停价格','跌停价格')],
            'rows':chosen,'boundary':'只限有明确20日适用日期的深市主板风险警示74只，沪市、创业板、科创板及B股不在本统计。无成交参考价不计全天同价成交；全天同价需再分上涨/下跌/平盘，收盘等于日内最低也不等于跌停。十二列表中未提供实际限价，不据此补跌停数量、历史队列或可执行退出。','independent_validations_added':0}
