"""Synthetic source-shaped clauses check dates, units, rounding and disclosure order."""
from copy import deepcopy

import pytest

from etf_share_event_profiles import D, EXTRA_CASES, ROUNDING, layout, parse_profile
from etf_share_events import CASES, reconcile_case
from market_risk import ETF_BASKET

CODE='510300.SH'
SUBJECT='华泰柏瑞沪深300交易型开放式指数证券投资基金'
NEAREST='折算后的基金份额采取四舍五入的方法计算保留到整数位。'
FLOOR='折算后的基金份额采用截位法保留至整数位，不足1份部分归入基金资产。'
CEIL='即小数点后基金份额均进位为1份。'


def profile(rounding='nearest_whole_share',**kwargs):
    return layout(r'确定('+D+r')为'+SUBJECT+r'的基金份额折算日',
                  registration=r'于('+D+r')进行了变更登记',rounding=rounding,**kwargs)


def result(rule=NEAREST):
    return [f'{SUBJECT}基金份额折算结果的公告。确定2012年5月11日为{SUBJECT}的基金份额折算日。'
            '基金份额折算比例为0.37094933，折算前基金份额总额为200.00份，折算后基金份额总额为74.00份。'
            f'本基金管理人已根据上述折算比例进行了折算，并于2012年5月14日进行了变更登记。{rule}'
            '基金份额净值采用四舍五入法保留到小数点后4位。']


@pytest.mark.parametrize('text,rule',[(NEAREST,'nearest_whole_share'),(FLOOR,'floor_to_whole_share'),(CEIL,'ceil_to_whole_share'),('', 'not_stated')])
def test_whole_share_rule_is_separate_from_NAV_rounding_and_date_of_registration(text,rule):
    parsed=parse_profile(result(text),CODE,'conversion','result',profile(rule))
    assert parsed['event_date']=='2012-05-11' and parsed['registration_date']=='2012-05-14'
    assert parsed['holder_rounding']==rule
    assert parsed['reported_totals'][0]['after_minus_simple_ratio_shares']=='-0.1898660000'
    assert 'record_date' not in parsed  # A registration date is not an invented record date.


@pytest.mark.parametrize('change',['wrong_code','wrong_subject','conflicting_ratio','conflicting_rounding','wrong_rule','earlier_registration','zero_total','missing_result','missing_implementation'])
def test_relabelled_or_contradictory_source_clauses_are_rejected(change):
    pages=result();rules=profile()
    if change=='wrong_code':pages[0]+='基金代码：510330。'
    elif change=='wrong_subject':pages[0]=pages[0].replace(SUBJECT,'其他基金')
    elif change=='conflicting_ratio':pages[0]+='基金份额折算比例为0.4998。'
    elif change=='conflicting_rounding':pages[0]+=FLOOR
    elif change=='wrong_rule':pages[0]=pages[0].replace(NEAREST,FLOOR)
    elif change=='earlier_registration':pages[0]=pages[0].replace('2012年5月14日','2012年5月10日')
    elif change=='zero_total':pages[0]=pages[0].replace('200.00份','0份')
    elif change=='missing_result':pages[0]=pages[0].replace('基金份额折算结果的公告','基金份额折算计划的公告')
    else:pages[0]=pages[0].replace('本基金管理人已根据上述折算比例','本基金管理人将根据上述折算比例')
    with pytest.raises(ValueError):parse_profile(pages,CODE,'conversion','result',rules)


def test_identical_repeated_ratios_are_one_fact_with_both_source_pages_not_extra_events():
    pages=result()+['基金份额折算比例为0.37094933。']
    parsed=parse_profile(pages,CODE,'conversion','result',profile())
    assert parsed['ratio']=='0.37094933' and parsed['evidence_pages']==[1,2]
    pages[1]='基金份额折算比例为0.4998。'
    with pytest.raises(ValueError):parse_profile(pages,CODE,'conversion','result',profile())


def test_optional_plan_ratio_is_not_reconstructed_from_the_implementation_result():
    case={'id':'synthetic','code':CODE,'kind':'conversion','resolution':'implemented'}
    proposal={'event_date':'2012-05-11','registration_date':'2012-05-14','ratio':None,'holder_rounding':'floor_to_whole_share'}
    implemented=parse_profile(result(''),CODE,'conversion','result',profile('not_stated'))
    docs=[({'document_id':'plan','published_on':'2012-05-07'},'plan',proposal),
          ({'document_id':'result','published_on':'2012-05-15'},'result',implemented)]
    before=deepcopy(docs);event=reconcile_case(case,docs)
    assert docs==before and event['planned_ratio'] is None and event['effective_ratio']=='0.37094933'
    assert event['holder_rounding']=='not_stated' and event['plan_holder_rounding']==['floor_to_whole_share']


def test_later_ratio_disclosure_preserves_earlier_unknown_plan():
    case={'id':'synthetic','code':CODE,'kind':'conversion','resolution':'implemented'}
    first={'event_date':'2012-05-11','ratio':None}
    later={'event_date':'2012-05-11','ratio':'0.37094933'}
    final={'event_date':'2012-05-11','ratio':'0.37094933'}
    docs=[({'document_id':'plan','published_on':'2012-05-07'},'plan',first),
          ({'document_id':'reminder','published_on':'2012-05-11'},'reminder',later),
          ({'document_id':'result','published_on':'2012-05-15'},'result',final)]
    event=reconcile_case(case,docs)
    assert event['planned_ratio']=='0.37094933' and docs[0][2]['ratio'] is None


@pytest.mark.parametrize('allowed,role,published,valid',[(True,'reminder','2012-05-12',True),(False,'reminder','2012-05-12',False),(True,'plan','2012-05-12',False),(True,'reminder','2012-05-16',False)])
def test_post_event_reminder_needs_explicit_case_scope_and_cannot_postdate_result(allowed,role,published,valid):
    case={'id':'synthetic','code':CODE,'kind':'conversion','resolution':'implemented','allow_post_event_reminder':allowed}
    facts={'event_date':'2012-05-11','ratio':'0.37094933'}
    docs=[({'document_id':'plan','published_on':'2012-05-07'},'plan',deepcopy(facts)),
          ({'document_id':'reminder','published_on':published},role,deepcopy(facts)),
          ({'document_id':'result','published_on':'2012-05-15'},'result',deepcopy(facts))]
    if valid:assert reconcile_case(case,docs)['event_date']=='2012-05-11'
    else:
        with pytest.raises(ValueError):reconcile_case(case,docs)


def test_result_only_scope_is_explicit_and_cannot_silently_replace_a_required_plan():
    case={'id':'synthetic','code':CODE,'kind':'conversion','resolution':'implemented'}
    docs=[({'document_id':'result','published_on':'2012-05-15'},'result',{'event_date':'2012-05-11','ratio':'0.37094933'})]
    with pytest.raises(ValueError):reconcile_case(case,docs)
    case['source_scope']='result_only'
    assert reconcile_case(case,docs)['source_scope']=='result_only'


def test_review_registry_covers_the_declared_eight_products_without_reusing_documents_or_event_ids():
    assert {case['code'] for case in CASES}==set(ETF_BASKET)
    assert len({case['id'] for case in CASES})==len(CASES)
    sources=[key for case in CASES for key,_ in case['documents']]
    assert len(set(sources))==len(sources)
    assert all(case['kind'] in ('conversion','split') for case in EXTRA_CASES)
    assert 'nearest_whole_share' in ROUNDING and 'floor_to_whole_share' in ROUNDING
