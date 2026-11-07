from copy import deepcopy
from decimal import Decimal
import pytest
from reported_financial_checks import compare_reported_figures,check_positive_base_change


def figure(identity,value,**changes):
    return {'id':identity,'symbol':'301030.SZ','entity':'listed_consolidated','metric':'parent_equity',
            'unit':'CNY','period_start':None,'period_end':'2025-12-31','value':value,
            'source':{'url':'https://static.cninfo.com.cn/finalpage/2026-04-30/1225268782.PDF',
                      'sha256':'a'*64,'page':10,'published_on':'2026-04-30'},**changes}


def test_real_three_reported_year_end_baselines_remain_separate_without_choosing_the_latest():
    rows=[figure('annual','-444287100.32'),figure('q1_comparative','-279848187.09'),figure('q3_comparative','-467422424.18')]
    before=deepcopy(rows);report=compare_reported_figures(rows);group=report['groups'][0]
    assert rows==before and group['status']=='different_reported_values' and group['selected_value'] is None
    assert {r['value'] for r in group['figures']}=={r['value'] for r in rows}
    assert not report['financial_truth_verified'] and not report['point_in_time_vintage_verified'] and not report['silently_corrected']


def test_matching_numbers_only_prove_agreement_of_the_supplied_figures():
    result=compare_reported_figures([figure('a','-10.00'),figure('b','-10')])
    assert result['groups'][0]['status']=='agreement_in_supplied_figures'
    assert result['groups'][0]['selected_value'] is None and result['coverage']=='only_supplied_figures'
    assert not result['financial_truth_verified']


@pytest.mark.parametrize('change',[
    {'symbol':'002514.SZ'},{'entity':'listed_parent'},{'metric':'total_assets'},
    {'period_end':'2024-12-31'},{'period_start':'2025-01-01'},
])
def test_other_companies_entities_metrics_years_and_flows_do_not_become_same_balance_conflicts(change):
    result=compare_reported_figures([figure('a','-10'),figure('b','-20',**change)])
    assert len(result['groups'])==2 and all(r['status']=='single_reported_figure' for r in result['groups'])


def test_mixed_units_are_incomparable_even_if_the_numeric_strings_are_equal():
    result=compare_reported_figures([figure('a','100'),figure('b','100',unit='CNY_10000')])
    assert result['groups'][0]['status']=='incomparable_units' and result['groups'][0]['selected_value'] is None


@pytest.mark.parametrize('value',[None,True,1.5,'NaN','Infinity','1,000','1e3',''])
def test_missing_implicit_float_or_ambiguous_amounts_are_not_silently_normalized(value):
    with pytest.raises((ValueError,TypeError)):compare_reported_figures([figure('a',value)])


@pytest.mark.parametrize('source_change',[
    {'url':'javascript:alert(1)'},{'url':'https://user:secret@example.org/a.pdf'},
    {'sha256':'wrong'},{'page':True},{'page':0},{'published_on':'2025-12-30'},
])
def test_changed_or_missing_source_page_identity_and_report_clock_are_rejected(source_change):
    row=figure('a','1');row['source'].update(source_change)
    with pytest.raises((ValueError,TypeError)):compare_reported_figures([row])


def test_duplicate_cells_cannot_be_counted_as_independent_agreement():
    a=figure('a','1')
    with pytest.raises(ValueError):compare_reported_figures([a,deepcopy(a)])


def test_real_stated_revenue_percent_is_compared_with_its_published_amounts_without_rewriting_either():
    r=check_positive_base_change('616224091.90','2041039936.75','-43.73')
    assert r['status']=='arithmetic_differs' and Decimal(r['calculated_percent'])==pytest.approx(Decimal('-69.808331'))
    assert r['reported_percent']=='-43.73' and r['current']=='616224091.90' and not r['source_values_rewritten']


def test_ordinary_rounded_growth_is_supported_without_requiring_string_identity():
    assert check_positive_base_change('2','3','-33.33')['status']=='arithmetic_agrees'


@pytest.mark.parametrize('previous',['0','-100'])
def test_profit_loss_nonpositive_baselines_do_not_silently_borrow_a_growth_convention(previous):
    r=check_positive_base_change('-50',previous,'-50')
    assert r['status']=='nonpositive_base_not_checked' and r['calculated_percent'] is None


def test_invalid_arithmetic_inputs_and_tolerance_do_not_create_false_passes():
    for args in [('1','0','NaN'),('1','-2',True)]:
        with pytest.raises(ValueError):check_positive_base_change(*args)
    with pytest.raises(ValueError):check_positive_base_change('1','2','-50',tolerance_pp='-0.01')
