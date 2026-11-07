from datetime import datetime, timezone
import pytest

from market_snapshot_age import close_reference, close_distance


@pytest.mark.parametrize('instant,expected',[
    ('2026-11-05T06:59:59+00:00','2026-11-04'),
    ('2026-11-05T07:00:00+00:00','2026-11-05'),
    ('2026-11-05T15:59:59+00:00','2026-11-05'),
    ('2026-11-05T16:00:00+00:00','2026-11-05'),
    ('2026-11-08T08:00:00+00:00','2026-11-06'),
    ('2026-10-05T08:00:00+00:00','2026-09-30'),
    ('2026-10-08T06:59:59+00:00','2026-09-30'),
    ('2026-10-08T07:00:00+00:00','2026-10-08'),
    ('2026-09-28T06:59:59+00:00','2026-09-24'),
])
def test_only_scheduled_closed_sessions_count_with_beijing_clock_weekends_and_holidays(instant,expected):
    result=close_reference(datetime.fromisoformat(instant))
    assert result['availability']=='calendar_computed' and result['latest_scheduled_close']==expected
    assert result['schedule_only'] is True and result['provider_deadline_verified'] is False
    assert result['automatic_update_observed'] is False


@pytest.mark.parametrize('instant',['2025-11-05T08:00:00+00:00','2027-01-04T08:00:00+00:00','2026-07-03T08:00:00+00:00','2026-07-06T06:59:59+00:00'])
def test_unknown_calendar_or_pre_effective_hours_version_never_guesses_the_latest_close(instant):
    ref=close_reference(datetime.fromisoformat(instant))
    assert ref['availability']=='unavailable' and ref['latest_scheduled_close'] is None
    assert close_distance(['2026-11-04'],ref)['reason']=='reference_unavailable'


def test_naive_clock_is_rejected_instead_of_assuming_a_timezone():
    with pytest.raises(ValueError,match='timezone'):close_reference(datetime(2026,11,5))


def test_distance_compares_actual_series_endpoints_not_fetch_time_target_or_window_start():
    ref=close_reference(datetime(2026,11,5,8,tzinfo=timezone.utc))
    result=close_distance(['2026-11-04','2026-11-03','2026-11-04'],ref)
    assert (result['minimum_sessions'],result['maximum_sessions'],result['series_compared'])==(1,2,3)
    assert close_distance(['2026-11-05'],ref)['minimum_sessions']==0
    # Seven calendar days of national holidays contribute no phantom trading days.
    ref=close_reference(datetime(2026,10,8,8,tzinfo=timezone.utc))
    assert close_distance(['2026-09-30'],ref)['minimum_sessions']==1


@pytest.mark.parametrize('dates,reason',[
    ([], 'no_verified_data_dates'),(['2026-11-06'],'data_after_reference'),
    (['2026-11-01'],'data_date_not_a_session'),(['2026-10-01'],'data_date_not_a_session'),
    (['2025-12-31'],'invalid_or_unsupported_data_date'),(['20261104'],'invalid_or_unsupported_data_date'),
    (['2026-02-30'],'invalid_or_unsupported_data_date'),(['not-date'],'invalid_or_unsupported_data_date'),
    (['2026-11-04',None],'invalid_or_unsupported_data_date'),
])
def test_missing_future_non_session_and_invalid_dates_are_unknown_not_zero_or_partial(dates,reason):
    result=close_distance(dates,close_reference(datetime(2026,11,5,8,tzinfo=timezone.utc)))
    assert result['availability']=='unavailable' and result['reason']==reason
    assert result['minimum_sessions'] is result['maximum_sessions'] is None and result['series_compared']==0


def test_market_status_keeps_source_target_separate_from_calendar_reference(tmp_path):
    from market_risk import build_market_risk_status,market_update_status
    now=datetime(2026,11,5,8,tzinfo=timezone.utc)
    status=build_market_risk_status(snapshot_dir=tmp_path,database=tmp_path/'missing.db',manifest_path=tmp_path/'missing.json',now=now)
    assert status['requested_through'] is None and status['target_close_distance']['reason']=='no_verified_data_dates'
    assert status['close_reference']['latest_scheduled_close']=='2026-11-05'
    assert status['current_risk_assessment']=='not_calibrated'
    sources=market_update_status(snapshot_dir=tmp_path,now=now)
    daily=[r for r in sources if 'close_distance' in r]
    assert len(daily)==6 and all(r['close_distance']['minimum_sessions'] is None for r in daily)
    assert all('close_distance' not in r for r in sources if r.get('date_basis') in ('prospectus_publication','regulation_publication','catalog_search_cutoff','asset_disclosure','current_list_observation'))


def test_update_row_uses_each_verified_series_endpoint_not_requested_or_fetched_day(tmp_path,monkeypatch):
    import market_risk
    now=datetime(2026,11,5,8,tzinfo=timezone.utc)
    meta={'availability':'observed','through':'2026-11-05','fetched_at':now.isoformat(),'content_digest':'old-source'}
    monkeypatch.setattr(market_risk,'_public_indices',lambda *args:(dict(meta),[
        {'through':'2026-11-04','observation_count':61},{'through':'2026-11-03','observation_count':61}]))
    row=next(r for r in market_risk.market_update_status(snapshot_dir=tmp_path,now=now) if r['source_id']=='official_indices')
    assert row['requested_through']=='2026-11-05' and row['fetched_at']==now.isoformat()
    assert row['observed_through_min']=='2026-11-03' and row['observed_through_max']=='2026-11-04'
    assert row['series_at_target']==0 and row['observation_count']==122
    assert (row['close_distance']['minimum_sessions'],row['close_distance']['maximum_sessions'])==(1,2)
    # A new fetch label cannot make an unverified source acquire a date-distance claim.
    meta['availability']='invalid'
    row=next(r for r in market_risk.market_update_status(snapshot_dir=tmp_path,now=now) if r['source_id']=='official_indices')
    assert row['close_distance']['reason']=='no_verified_data_dates'
