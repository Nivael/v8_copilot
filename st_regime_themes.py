"""Question-oriented, descriptive views of the frozen ST comparison input."""
from collections import Counter
from math import prod
from statistics import mean
from canonical_json import digest
from st_sample_integrity import load_integrity
from st_fixed_quote_audit import fixed_quote_audit_view
from st_dividend_basis import dividend_basis_view,update_quote_audit
from st_disclosure_chains import disclosure_chain_view
from st_experience_case_audit import experience_case_audit
from st_price_band_audit import price_band_view
from st_removal_era_comparison import removal_era_comparison
from st_pre_rule_membership import pre_rule_membership_view,boundary_price_inputs
from st_dynamic_reference_audit import dynamic_reference_audit
from st_exit_quote_replay import exit_quote_replay
from st_remaining_basis import remaining_basis_view,apply_remaining_status
from st_member_transitions import member_transition_view
from st_member_entries import member_entry_view
from st_index_crosscheck import crosscheck_view
from st_stock_price_crosscheck import price_check_view
from st_label_changes import label_change_view
from st_membership_audit import membership_audit_view
from st_halt_stages import halt_stage_view
from st_halt_price_crosscheck import halt_price_check_view
from st_case_price_crosscheck import case_price_check_view
from st_company_risk_cases import company_risk_case_view
from st_removal_followup import removal_followup_view
from st_removal_cohort import removal_cohort_view
from st_strong_removal_cases import strong_removal_cases_view
from st_shenwu_execution import shenwu_execution_view
from st_tianji_conditions import tianji_conditions_view


def compound(rows, field):
    return (prod(1 + r[field] / 100 for r in rows) - 1) * 100 if rows else None


def event_context(event, symbol, inputs, daily):
    calendar = inputs['calendar']
    day = event['published_on']
    eligible = [d for d in calendar if d <= day]
    anchor = eligible[-1] if eligible else None
    prices = {(r['symbol'],r['trade_date']):r for r in inputs['fixed_prices']}
    first = prices.get((symbol, anchor))
    start = first['close'] if first else None
    windows = {}
    for n in (1,5,20):
        remaining = [d for d in calendar if anchor and d > anchor]
        end = remaining[n-1] if len(remaining) >= n else None
        last = prices.get((symbol,end))
        close = last['close'] if last else None
        rows = [r for r in daily if anchor and end and anchor < r['date'] <= end]
        valid = bool(end and len(rows) == n)
        suspended_reference=bool(first and first.get('has_trade') is False or last and last.get('has_trade') is False)
        usable=bool(start and close and valid and not suspended_reference)
        windows[str(n)] = {'through':end,'stock_pct':(close/start-1)*100 if usable else None,
                          'market_pct':compound(rows,'market_pct') if valid else None,
                          'st_pct':compound(rows,'return_pct') if valid else None,
                          'gap':None if usable else '起止含停牌日参考值，不能作实际交易收盘，未填零' if suspended_reference else '起止缺价或后续交易日不足，未填零'}
    return {'anchor':anchor,'date_precision':'day','not_earliest_reaction':True,'windows':windows}


def coalesce_event_records(records):
    """One source-bound episode may have several recorded views; never count views as replications."""
    groups={}
    for row in records:
        identity={k:row.get(k) for k in ('symbol','id','published_on','occurred_on','entity_scope','change_kind','report_period_end','scheduled_for','alternate_published_on','date_uncertainty')}
        identity['source_sha256']=row['source']['sha256']
        key=digest(identity);groups.setdefault(key,[]).append(row)
    result=[]
    for key,group in groups.items():
        unique=list({digest(row):row for row in group}.values())
        unique.sort(key=lambda r:(r.get('title',''),r['source'].get('page',0),digest(r)))
        primary={**unique[0],'event_key':'EVENT-'+key[:24],'source_record_count':len(group)}
        if len(group)>1:
            primary['source_records']=[dict(r) for r in unique]
            for field in ('change','interpretation','watch','evidence_detail'):
                if any(field in r for r in unique):primary[field]='；'.join(dict.fromkeys(r[field] for r in unique if r.get(field)))
            if any('lens_ids' in r for r in unique):primary['lens_ids']=sorted({lens for r in unique for lens in r.get('lens_ids',[])})
        result.append(primary)
    return sorted(result,key=lambda r:(r['published_on'],r['symbol'],r.get('title',''),r['event_key']))


def build_themes(inputs, daily):
    after = [r for r in daily if r['date'] >= '2026-07-06']
    months = []
    for month in sorted({r['date'][:7] for r in after}):
        rows = [r for r in after if r['date'].startswith(month)]
        months.append({'month':month,'start':rows[0]['date'],'through':rows[-1]['date'],'days':len(rows),
                       'st_pct':compound(rows,'return_pct'),'market_pct':compound(rows,'market_pct'),
                       'small_pct':compound(rows,'small_cap_pct'),
                       'positive_breadth_pct':mean(r['positive_pct'] for r in rows)})
    extreme = sorted(sorted(after,key=lambda r:abs(r['market_pct']),reverse=True)[:8],key=lambda r:r['date'])
    integrity=load_integrity(inputs)
    cohort=removal_cohort_view(inputs,daily)
    result = {'price_band_audit':price_band_view(inputs), 'removal_era_comparison':removal_era_comparison(inputs,daily), 'pre_rule_membership':pre_rule_membership_view(inputs), 'dynamic_reference_audit':dynamic_reference_audit(inputs,daily), 'remaining_basis':remaining_basis_view(inputs), 'dividend_basis':dividend_basis_view(inputs), 'fixed_quote_audit':fixed_quote_audit_view(inputs,daily), 'earnings_warning':tianji_conditions_view(inputs,daily), 'shenwu_execution':shenwu_execution_view(inputs), 'strong_removal_cases':strong_removal_cases_view(inputs,cohort,daily), 'removal_cohort':cohort, 'removal_followup':removal_followup_view(inputs,daily), 'case_price_crosscheck':case_price_check_view(inputs,daily), 'company_risk_cases':company_risk_case_view(inputs,daily), 'halt_price_crosscheck':halt_price_check_view(inputs,daily), 'halt_stages':halt_stage_view(inputs), 'membership_audit':membership_audit_view(inputs), 'label_changes':label_change_view(inputs,daily), 'stock_price_crosscheck':price_check_view(inputs,daily), 'index_crosscheck':crosscheck_view(inputs,daily), 'member_entries':member_entry_view(inputs,daily), 'member_transitions':member_transition_view(inputs), 'sample_integrity': {'through':integrity['through'],'cases':integrity['cases'],'boundary':integrity['price_verification']['boundary']} if integrity else None, 'months':months,'market_days':[{k:r[k] for k in ('date','market_pct','return_pct','positive_pct')} for r in extreme]}
    update_quote_audit(result['fixed_quote_audit'],result['dividend_basis'])
    apply_remaining_status(result['fixed_quote_audit'],result['remaining_basis'],result['dividend_basis'])
    replay=exit_quote_replay(inputs,daily,result['fixed_quote_audit'])
    result['exit_quote_replay']=replay['view'] if replay else None
    if replay:result['fixed_quote_audit']=replay['audit']
    packet = inputs.get('announcement_study')
    if not packet:
        result['experience_case_audit']=experience_case_audit(inputs,result['removal_era_comparison'],None)
        return result
    if packet['content_digest'] != digest({k:v for k,v in packet.items() if k!='content_digest'}):
        raise ValueError('announcement source packet changed')
    catalogs = packet['catalogs']
    events = []
    names = {s:c['name'] for s,c in catalogs.items()}
    names.update({r['symbol']:r['name']for r in (inputs.get('pre_rule_membership')or{}).get('rows',[])})
    boundary_inputs=boundary_price_inputs(inputs)
    for event in coalesce_event_records(packet['verified_events']):
        symbol = event['symbol']
        context=event_context(event,symbol,boundary_inputs if event['id'].startswith(('pre_rule_boundary_','removal_action_basis_','price_band_reference_'))else inputs,daily)
        alternative=event_context({**event,'published_on':event['alternate_published_on']},symbol,boundary_inputs if event['id'].startswith(('pre_rule_boundary_','removal_action_basis_','price_band_reference_'))else inputs,daily) if event.get('alternate_published_on') else None
        events.append({**event,'name':names[symbol],'observation':context,'alternate_observation':alternative})
    if result['earnings_warning']:
        result['earnings_warning']['events']=[e for e in events if e['id'] in result['earnings_warning']['event_ids']]
    if result['shenwu_execution']:
        result['shenwu_execution']['observations']=[e for e in events if e['id'] in result['shenwu_execution']['event_ids']]
    if result['company_risk_cases']:
        result['company_risk_cases']['events']=[e for e in events if e['id'] in result['company_risk_cases']['event_ids']]
        subsidiary=result['company_risk_cases'].get('subsidiary_civil')
        if subsidiary:
            selected=[e for e in events if e['id'] in subsidiary['event_ids']]
            observations=[{'published_on':e['published_on'],'anchor':e['observation']['anchor'],**e['observation']['windows']['20']} for e in selected]
            if len(observations)==2 and all(x['anchor'] and x['through'] for x in observations):
                dates=[{d for d in inputs['calendar'] if x['anchor']<d<=x['through']} for x in observations]
                subsidiary['price_comparison']={'window_days':20,'observations':observations,'overlap_market_days':len(dates[0]&dates[1]),'full_window':result['company_risk_cases']['comparison'][0]['price_window']}
            else:subsidiary['price_comparison']=None
    if result['membership_audit']:
        for check in result['membership_audit'].get('issuer_checks',[]):
            check['events']=[e for e in events if e['id'] in [*check['event_ids'],*(check.get('followup') or {}).get('event_ids',[])]]
            prices={r['trade_date']:r for r in inputs['fixed_prices'] if r['symbol']==check['symbol']}
            first=prices.get(check['anchor']);last=prices.get(inputs['through']);usable=bool(first and last and first.get('has_trade') is True and last.get('has_trade') is True)
            window=[r for r in daily if check['anchor']<r['date']<=inputs['through']]
            check['full_window']={'anchor':check['anchor'],'through':inputs['through'],'market_days':len(window),'stock_pct':(last['close']/first['close']-1)*100 if usable else None,'market_pct':compound(window,'market_pct'),'st_pct':compound(window,'return_pct')}
    result['announcements'] = {'from':packet['start'],'through':packet['through'],
        'companies':len(catalogs),'catalog_rows':sum(len(c['rows']) for c in catalogs.values()),
        'catalog_pages':sum(len(c['source_refs']) for c in catalogs.values()),
        'verified_events':events,'raw_fact_records':len(packet['verified_events']),'deduplicated_event_count':len(events),'coalesced_records':len(packet['verified_events'])-len(events),'event_grouping_basis':'same_symbol_event_id_source_dates_entity_and_kind','verified_companies':len({e['symbol'] for e in events}),
        'verified_documents':len({(e['symbol'],s['sha256']) for e in events for s in [e['source'],*e.get('supporting_sources',[])]}),
        'catalog_by_month':dict(sorted(Counter(r['announcement_date'][:7] for c in catalogs.values() for r in c['rows']).items())),
        'history_digest':packet['history_digest'],'source_packet_digest':packet['content_digest'],
        'body_reads_this_refresh':packet.get('body_reads_this_refresh',0),
        'boundary':'目录覆盖156家指定公司与7月1日至11月6日窗口；正文事实来自已核原件与历史资料的选样，不能代表全体公告。同一事项的重复视角合并展示，原事实记录保留；阅读事项数不代表独立案例或验证次数，跨公告重复事项仍需另核。日期仅精确到日，行情从披露日或之前最近收盘后起算，不认证最早反应或公告因果。'}
    changes = inputs.get('refresh_provenance',{}).get('prior_activity_differences',[])
    result['refresh'] = {'through':inputs['through'],'prior_input_digest':inputs.get('refresh_provenance',{}).get('prior_input_digest'),
                          'activity_differences':len(changes)}
    result['disclosure_chains']=disclosure_chain_view(inputs,result['announcements'])
    result['experience_case_audit']=experience_case_audit(inputs,result['removal_era_comparison'],result.get('announcements'))
    return result
