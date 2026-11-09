"""Frozen, membership-aware closing-price audit; not an intraday compliance test."""
from collections import defaultdict
from decimal import Decimal as D, ROUND_HALF_UP
from hashlib import sha256
import re, unicodedata
from canonical_json import digest
from st_stock_price_crosscheck import quotes_from_source

KEYS=('calendar','through','members','activities','dynamic_reference_audit','pre_rule_membership','remaining_basis','dividend_basis','removal_action_basis')
RULE_DAY='2026-07-06'
def scope_digest(i):return digest({k:i[k] for k in KEYS})
def price_band(reference,rate):
    ref=D(str(reference));rate=D(str(rate));tick=D('.01')
    if not ref.is_finite() or ref<tick or not 0<rate<1:raise ValueError('invalid price boundary input')
    upper=max((ref*(1+rate)).quantize(tick,rounding=ROUND_HALF_UP),ref+tick)
    lower=max(tick,min((ref*(1-rate)).quantize(tick,rounding=ROUND_HALF_UP),ref-tick))
    return upper,lower

def eligible_rows(i):
    members={(r['symbol'],r['trade_date'])for r in i['members']}
    return [r for r in i['activities']if r['trade_date']>i['calendar'][0] and (r['symbol'],r['trade_date'])in members and r['symbol'].startswith(('000','001','002','003','600','601','603','605')) and r['suspension_status']=='trading'and r['terminal_phase_status']=='not_terminal'and r.get('volume',0)>0 and r.get('pre_close',0)>0 and r.get('close',0)>0]

def normalized(r,api,day):
    fields=('pre_close','close','pct_chg','vol','high','low')if api=='daily'else('up_limit','down_limit')
    return {'symbol':r['symbol'],'date':day,**{k:None if r[k]is None else str(D(str(r[k])).normalize())for k in fields}}

def price_band_view(i):
    p=i.get('price_band_audit')
    if p is None:return None
    if p['version']!=1 or p['through']!=i['through']or p['rule_day']!=RULE_DAY or p['scope_digest']!=scope_digest(i)or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('price band source binding changed')
    sources=p['rule_sources']
    if len(sources)!=9 or len({s['key']for s in sources})!=9 or any(not re.fullmatch('[0-9a-f]{64}',s['sha256'])for s in sources):raise ValueError('rule source set incomplete')
    # Replay receipts bind the selected actual-ST rows; byte verification happens before publication.
    grouped=defaultdict(list);rows=eligible_rows(i)
    if len({(r['symbol'],r['trade_date'])for r in rows})!=len(rows):raise ValueError('duplicate closing observation')
    for r in rows:grouped[r['trade_date']].append(r)
    receipts=p['provider_replay']
    if len(receipts)!=2*len(grouped)or {(r['api'],r['date'])for r in receipts}!={(a,d)for a in ('daily','stk_limit')for d in grouped}:raise ValueError('provider replay calendar differs')
    for receipt in receipts:
        selected=sorted((normalized({**r,'vol':r['volume']},receipt['api'],receipt['date'])for r in grouped[receipt['date']]),key=lambda r:r['symbol'])
        if len(selected)!=receipt['selected_rows']or digest(selected)!=receipt['selected_digest']:raise ValueError('provider selected rows differ')
    quotes={s['symbol']:quotes_from_source(s)for s in i['dynamic_reference_audit']['sources']if s['key']=='tencent_raw'}
    facts=[];references=[];unknown=[]
    for r in rows:
        day=r['trade_date'];symbol=r['symbol'];ref=D(str(r['pre_close']));close=D(str(r['close']));before=day<RULE_DAY
        if quotes.get(symbol,{}).get(day)!=close:raise ValueError('independent raw closing price differs')
        up,down=price_band(ref,'.05');actual_up,actual_down=price_band(ref,'.05'if before else'.10')
        if (actual_up,actual_down)!=(D(str(r['up_limit'])),D(str(r['down_limit']))):raise ValueError('actual limit formula differs')
        if not actual_down<=close<=actual_up:raise ValueError('closing price outside actual limit')
        fact={'symbol':symbol,'name':r['name'],'date':day,'reference':float(ref),'close':float(close),'pct':float((close/ref-1)*100),'reported_pct':r['pct_chg'],'old_upper':float(up),'old_lower':float(down),'actual_upper':float(actual_up),'actual_lower':float(actual_down),'over5':abs((close/ref-1)*100)>5,'reported_over5':abs(r['pct_chg'])>5,'old_up':close>up,'old_down':close<down,'actual_up':close==actual_up,'actual_down':close==actual_down}
        facts.append(fact);prior=[d for d in quotes[symbol]if d<day]
        if not prior:unknown.append({**fact,'previous_actual_date':None,'previous_actual_close':None})
        else:
            prev=max(prior);previous=quotes[symbol][prev]
            if previous!=ref:references.append({**fact,'previous_actual_date':prev,'previous_actual_close':float(previous)})
    # Verify the newly acquired issuer mirror rather than inferring its cash distribution from prices.
    cash=p['new_cash'];source=cash['source'];body=''.join(source['selected_pages'].values());text=re.sub(r'\s+','',unicodedata.normalize('NFKC',body)).replace(',','')
    if (cash['cash_per_share'],cash['total_shares'],cash['total_cash'],cash['record_on'],cash['ex_on'])!=('0.08','130000000','10400000','2026-05-25','2026-05-26'):raise ValueError('cash action facts differ')
    if cash['symbol']!='603721'or source['symbol']!='603721'or source['source_format']!='pdf_mirror'or source['host_is_official']or not source['protected_gate_passed']:raise ValueError('cash source identity or source level differs')
    for page,t in source['selected_pages'].items():
        if sha256(re.sub(r'\s+','',unicodedata.normalize('NFKC',t)).encode()).hexdigest()!=source['page_text_hashes'][int(page)-1]:raise ValueError('cash source page changed')
    if not all(t in text for t in ('603721','每股派发现金红利0.08元','130000000','10400000','2026/5/25','2026/5/26'))or D(cash['cash_per_share'])*D(cash['total_shares'])!=D(cash['total_cash']):raise ValueError('cash units or dates unsupported')
    case=next(r for r in references if r['symbol']==cash['symbol']and r['date']==cash['ex_on'])
    if D(str(case['previous_actual_close']))-D(cash['cash_per_share'])!=D(str(case['reference'])):raise ValueError('new cash reference does not reconstruct')
    # Existing body-backed action facts are reused; they are not new independent validations.
    action_refs={(r['symbol'],r['effective_on']):{'source':r['cash_source'],'conflict':r['source_conflict'],'kind':r['kind']}for r in i['remaining_basis']['rows']}
    for a in i['dividend_basis']['actions']:
        action_refs[(a['symbol'],a['ex_on'])]={'source':a['cash_source'],'conflict':None,'kind':'cash_dividend'}
    action_refs[(cash['symbol'],cash['ex_on'])]={'source':{k:v for k,v in source.items()if k not in ('selected_pages','page_text_hashes')},'conflict':None,'kind':'cash_dividend_pdf_mirror'}
    for r in references:
        proof=action_refs.get((r['symbol'],r['date']))
        if not proof:raise ValueError('reference change lacks bound issuer evidence')
        r.update(proof)
    nominal=p['limit_api_pre_close_differences'];lookup={(r['symbol'],r['date']):r for r in facts}
    if len({(r['symbol'],r['date'])for r in nominal})!=len(nominal):raise ValueError('duplicate API reference difference')
    for r in nominal:
        fact=lookup[(r['symbol'],r['date'])]
        if D(r['daily_reference'])!=D(str(fact['reference']))or r['limit_api_pre_close']==r['daily_reference']:raise ValueError('API field difference invalid')
    def aggregate(selected):
        counts={k:sum(bool(r[k])for r in selected)for k in ('over5','reported_over5','old_up','old_down','actual_up','actual_down')};n=len(selected)
        return {'start':min((r['date']for r in selected),default=None),'through':max((r['date']for r in selected),default=None),'days':len({r['date']for r in selected}),'observations':n,**counts,'old_crossings':counts['old_up']+counts['old_down'],'actual_limit_closes':counts['actual_up']+counts['actual_down'],'old_crossing_pct':100*(counts['old_up']+counts['old_down'])/n if n else None,'actual_limit_pct':100*(counts['actual_up']+counts['actual_down'])/n if n else None}
    windows={}
    before=sorted(d for d in grouped if d<RULE_DAY);after=sorted(d for d in grouped if d>=RULE_DAY)
    for key,n in [('20',20),('40',40),('all',None)]:
        left=set(before[-n:]if n else before);right=set(after[:n]if n else after)
        windows[key]={'before':aggregate([r for r in facts if r['date']in left]),'after':aggregate([r for r in facts if r['date']in right])}
    examples=sorted((r for r in facts if r['date']<RULE_DAY and r['over5']),key=lambda r:(r['reference'],r['date'],r['symbol']))
    if any(r['old_up']or r['old_down']for r in facts if r['date']<RULE_DAY):raise ValueError('pre-rule old boundary crossing requires investigation')
    members={(r['symbol'],r['trade_date'])for r in i['members']};former=[]
    companies={c['symbol']:c for c in i['dynamic_reference_audit']['original_prices']['companies']}
    for event in i['pre_rule_membership']['rows']:
        if event['kind']!='warning_removed':continue
        symbol=event['symbol'];day=event['effective_on'];r=next(r for r in companies[symbol]['rows']if r['date']==day);ref=D(str(r['pre_close']));close=D(str(r['raw_close']));up,down=price_band(ref,'.05')
        if (symbol,day)in members:raise ValueError('former ST removal date remains in denominator')
        former.append({'symbol':symbol,'date':day,'name':companies[symbol]['name'],'close':float(close),'reference':float(ref),'old_crossing':close>up or close<down,'in_st_denominator':False})
    return {'through':i['through'],'windows':windows,'observations':len(facts),'row_digest':digest(facts),'rounding_examples':examples,'reference_changes':references,'previous_quote_unknown':unknown,'api_reference_differences':nominal,'former_st_resumptions':former,'rules':sources,'provider_responses':len(receipts),'new_market_queries':0,'actual_formula_mismatches':0,'outside_actual_closes':0,'boundary':p['scope_note'],'acquisition_gaps':p['acquisition_gaps'],'new_cash':{**cash,'source':{k:v for k,v in source.items()if k not in ('selected_pages','page_text_hashes')}}}
