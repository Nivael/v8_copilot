from copy import deepcopy
import pytest
from event_learning import audit_events,following_windows,reconcile_holdings


def event(**changes):
    return {'id':'notice','published_on':'2026-06-02','publication_precision':'day','occurred_on':'2026-05-30','entity_scope':'shareholder','source_id':'official','fact':'前次拍卖流拍，后续二拍待进行','state_before':'auction_scheduled','state_after':'auction_failed','change_kind':'progress',**changes}


def test_occurrence_before_question_can_be_disclosed_after_question_without_backdating_public_knowledge():
    row=event();before=deepcopy(row);report=audit_events([row])
    assert row==before and report['chronology_checked'] and not report['causal_effect_identified'] and not report['cross_case_generalization_tested']


@pytest.mark.parametrize('changes',[
    {'occurred_on':'2026-06-18'},
    {'publication_precision':'instant'},
    {'entity_scope':'unknown'},
    {'source_id':''},
    {'state_after':''},
    {'inferred_transition':'issuer_control_changed'},
    {'change_kind':'reaffirmation','reaffirms':'earlier'},
    {'change_kind':'reaffirmation','state_before':'auction_failed','reaffirms':'missing'},
    {'change_kind':'outcome_report','price_cause_claim':{'move_started_on':'2026-06-03','identified':False}},
    {'price_cause_claim':{'move_started_on':'2026-06-01','identified':False}},
    {'price_cause_claim':{'move_started_on':'2026-06-02','identified':False}},
    {'price_cause_claim':{'move_started_on':'2026-06-03','identified':True}},
])
def test_rejects_leakage_reaction_as_cause_and_unfounded_entity_or_stage_transitions(changes):
    with pytest.raises(ValueError):audit_events([event(**changes)])


def test_planned_event_and_repeated_risk_remain_distinct_from_completed_new_evidence():
    planned=event(state_after='scheduled',occurred_on='2026-06-18')
    repeated=event(id='repeat',published_on='2026-06-12',state_before='auction_failed',change_kind='reaffirmation',reaffirms='notice')
    assert audit_events([planned])['events']==1 and audit_events([event(),repeated])['events']==2
    with pytest.raises(ValueError):audit_events([repeated,planned])
    with pytest.raises(ValueError):audit_events([planned,planned])


@pytest.mark.parametrize('disclosure,anchor,end',[
    ('2026-06-05','2026-06-05','2026-06-08'),
    ('2026-06-06','2026-06-05','2026-06-08'),
])
def test_day_only_and_weekend_notices_use_later_complete_sessions_and_same_reference(disclosure,anchor,end):
    days=['2026-06-04','2026-06-05','2026-06-08','2026-06-09'];rows=[{'date':d,'level':v} for d,v in zip(days,[100,90,99,108])]
    value=following_windows(rows,rows,rows,days,disclosure)
    assert value['reference_close']==anchor and value['not_earliest_reaction']
    assert value['windows']['1']['through']==end and value['windows']['1']['change_pct']==dict(stock='10.0',market='10.0',st='10.0')
    assert value['windows']['5']['change_pct']==dict(stock=None,market=None,st=None)


def test_missing_quote_does_not_move_anchor_or_claim_zero_return():
    days=['2026-06-04','2026-06-05','2026-06-08'];stock=[{'date':d,'level':v} for d,v in zip(days,[100,None,99])];benchmark=[{'date':d,'level':100} for d in days]
    value=following_windows(stock,benchmark,benchmark,days,'2026-06-05')
    assert value['reference_close']=='2026-06-05' and value['windows']['1']['change_pct']==dict(stock=None,market='0',st='0')


def test_detects_real_disclosed_auction_count_conflict_without_fixing_it():
    value=reconcile_holdings(185101714,176101714,5500000+5500000)
    assert value=={'consistent':False,'stated_reduction':9000000,'listed_transfer':11000000,'unreconciled_difference':-2000000,'silently_corrected':False}
    assert reconcile_holdings(185101714,174981714,10120000)['consistent']


def test_duplicate_or_foreign_price_dates_do_not_silently_replace_evidence():
    days=['2026-06-04','2026-06-05','2026-06-08'];rows=[{'date':d,'level':100} for d in days]
    for changed in [[*rows,rows[0]],[*rows,{'date':'2026-06-09','level':101}]]:
        with pytest.raises(ValueError):following_windows(changed,rows,rows,days,'2026-06-05')
