from datetime import date, timedelta
import pytest
from benchmarks.agreement_event_study import event_window, summarize

def test_event_window_uses_previous_close_and_missing_horizon():
    prices = [(str(date(2024, 1, 1) + timedelta(days=i)), float(100+i)) for i in range(7)]
    window = event_window(prices, '2024-01-02')
    assert window['return_5'] == 5.0
    assert window['return_20'] is None
    assert window['end_5'] == '2024-01-06'
    later = event_window(prices, '2024-01-02', next_session=True)
    assert later['baseline_date'] == '2024-01-02'
    assert later['end_5'] == '2024-01-07'

def test_weekend_sensitivity_does_not_skip_monday():
    prices = [('2024-01-05', 10.), ('2024-01-08', 11.)]
    assert event_window(prices, '2024-01-06') == event_window(prices, '2024-01-06', next_session=True)

def test_unverified_long_gap_does_not_become_return():
    value = event_window([('2024-01-01', 10.), ('2024-02-01', 11.)], '2024-01-02')
    assert 'coverage_gap' in value
    assert 'return_5' not in value

def test_duplicate_dates_rejected():
    with pytest.raises(ValueError):
        event_window([('2024-01-01', 10.), ('2024-01-01', 11.)], '2024-01-02')

def test_missing_horizons_not_counted_as_flat_or_losses():
    case = dict(industrial_disclosure='2024-01-01', financial_disclosure='2024-02-01', industrial_price=1, financial_price=2, price_window={'return_5': None})
    result = summarize([case])['5']
    assert result == dict(n=0, missing=1, positive=0, negative=0, flat=0, median=None)
