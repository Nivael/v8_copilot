from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

from canonical_json import digest
from market_breadth import SOURCES
from market_breadth_history import load_breadth_history, refresh_breadth_history
from market_breadth_refresh import quote
from market_periods import recent_calendar_window

NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)
DAYS = recent_calendar_window('2026-11-04')['calendar']


class Client:
    """Synthetic complete exchange-day fixtures; never current real market facts."""
    def __init__(self, store, fail=None): self.store, self.fail, self.calls = store, fail, []
    def get_venue(self, venue, day):
        assert venue=='SZSE'
        self.calls.append(day)
        if day==self.fail: raise TimeoutError('upstream failure')
        rows=[quote('000001','样本公司',day,9,10,-10,100,900,venue='SZSE')]
        if day < '2026-10-23':
            rows.append(quote('000016','*ST历史样本',day,2,2,0,0,0,venue='SZSE'))
        block={'reported_total':len(rows)+2,'received_total':len(rows)+2,'excluded_b_shares':1,
               'excluded_preferred_codes':['140001'],'amount_unit':'CNY','volume_unit':'shares','rows':rows}
        body=json.dumps({'synthetic_normalized_day':block},ensure_ascii=False).encode()
        key=hashlib.sha256(body).hexdigest()
        (self.store/'responses').mkdir(parents=True,exist_ok=True)
        (self.store/'responses'/f'{key}.json').write_bytes(body)
        ref={'venue':'SZSE','url':SOURCES['SZSE']['api_url'],'params':{'SHOWTYPE':'JSON','CATALOGID':'1815_stock_snapshot',
             'TABKEY':'tab1','txtBeginDate':day,'txtEndDate':day,'PAGENO':1},'response_sha256':key,'observed_at':NOW.isoformat()}
        return block,[ref]


def refresh(directory, client=None, **kwargs):
    return refresh_breadth_history(client or Client(directory.parent/'public_breadth'),through='2026-11-04',output=directory,now=NOW,**kwargs)


def test_complete_calendar_uses_each_days_report_members_and_keeps_the_other_exchange_missing(tmp_path):
    folder=tmp_path/'history';result=refresh(folder)
    assert result['status']=='complete' and result['completed_days']==38
    before=(folder/'current.json').read_bytes()
    status=load_breadth_history(folder,NOW)
    assert status['start']=='2026-09-04' and status['through']=='2026-11-04' and status['observed_days']==38
    assert status['points'][0]['listed_source_stocks']==2 and status['points'][-1]['listed_source_stocks']==1
    assert status['points'][0]['st_name_group']['listed_source_stocks']==1
    assert status['points'][-1]['st_name_group']['listed_source_stocks']==0
    assert status['points'][0]['observed_trading_stocks']==1 and status['points'][0]['flat']==0
    assert status['points'][0]['declining_share_pct']==100 and status['points'][0]['nontrading_stocks']==1
    assert status['complete_market_history'] is False and status['missing_venues']==['SSE']
    assert before==(folder/'current.json').read_bytes()


def test_interrupted_first_window_resumes_verified_days_and_does_not_publish_a_shorter_path(tmp_path):
    folder=tmp_path/'history';client=Client(tmp_path/'public_breadth',fail=DAYS[2])
    failed=refresh(folder,client)
    assert failed['status']=='failed' and failed['completed_days']==2 and failed['current_snapshot_preserved']
    assert not (folder/'current.json').exists()
    repair=Client(tmp_path/'public_breadth')
    result=refresh(folder,repair,repair=True)
    assert result['status']=='complete' and result['reused_days']==2 and repair.calls==DAYS[2:]


def test_failed_fresh_refresh_preserves_the_previous_complete_window(tmp_path):
    folder=tmp_path/'history';refresh(folder)
    before=(folder/'current.json').read_bytes()
    result=refresh(folder,Client(tmp_path/'public_breadth',fail=DAYS[1]))
    assert result['status']=='failed' and result['completed_days']==1
    assert before==(folder/'current.json').read_bytes()


def test_cache_repair_preserves_original_source_observation_time(tmp_path):
    folder=tmp_path/'history';refresh(folder)
    later=NOW+timedelta(hours=1)
    client=Client(tmp_path/'public_breadth')
    fixed=refresh_breadth_history(client,through='2026-11-04',output=folder,now=later,repair=True)
    loaded=load_breadth_history(folder,later)
    assert fixed['reused_days']==38 and client.calls==[]
    assert loaded['fetched_at']==NOW.isoformat() and loaded['materialized_at']==later.isoformat()


@pytest.mark.parametrize('change',['short_window','missing_day','scope','fingerprint','future','wrong_query','filtered_query','wrong_date','unknown_preferred'])
def test_rebound_history_or_day_snapshots_are_rejected_even_with_new_digests(tmp_path,change):
    folder=tmp_path/'history';refresh(folder)
    path=folder/'current.json';raw=json.loads(path.read_text())
    if change=='short_window': raw['calendar']=raw['calendar'][1:]
    elif change=='missing_day':raw['daily_snapshots'].pop(DAYS[3])
    elif change=='scope':raw['scope']='SSE_SZSE_A_shares'
    elif change=='fingerprint':raw['processor_digest']='different'
    elif change=='future':raw['fetched_at']='2026-11-06T00:00:00+00:00'
    else:
        key=raw['daily_snapshots'][DAYS[0]];day=json.loads((folder/'days'/f'{key}.json').read_text())
        if change=='wrong_query':day['responses'][0]['params']['PAGENO']=2
        elif change=='filtered_query':day['responses'][0]['params']['txtDMorJC']='000001'
        elif change=='wrong_date':day['block']['rows'][0]['trade_date']=DAYS[1]
        else:day['block']['excluded_preferred_codes']=['140099']
        day.pop('content_digest');key=digest(day);day['content_digest']=key
        (folder/'days'/f'{key}.json').write_text(json.dumps(day));raw['daily_snapshots'][DAYS[0]]=key
    raw.pop('content_digest');raw['content_digest']=digest(raw);path.write_text(json.dumps(raw))
    assert load_breadth_history(folder,NOW)['availability']=='invalid'


def test_repair_does_not_reuse_a_day_whose_archived_source_bytes_changed(tmp_path):
    folder=tmp_path/'history';refresh(folder)
    pointer=json.loads((folder/'staging'/f'{DAYS[0]}.json').read_text())
    day=json.loads((folder/'days'/f"{pointer['content_digest']}.json").read_text())
    key=day['responses'][0]['response_sha256']
    (tmp_path/'public_breadth/responses'/f'{key}.json').write_bytes(b'corrupted')
    client=Client(tmp_path/'public_breadth');result=refresh(folder,client,repair=True)
    assert result['status']=='complete' and result['reused_days']==37 and client.calls==DAYS[:1]


def test_code_change_during_collection_cannot_publish_a_mixed_processor_window(tmp_path,monkeypatch):
    folder=tmp_path/'history';refresh(folder);before=(folder/'current.json').read_bytes()
    from market_breadth_history import PROCESSOR_DIGEST
    values=iter([PROCESSOR_DIGEST,PROCESSOR_DIGEST,'changed'])
    # Entry validation, old snapshot read, then the final publication guard.
    monkeypatch.setattr('market_breadth_history.processor_digest',lambda:next(values))
    result=refresh(folder,repair=True)
    assert result['status']=='failed' and result['error_type']=='ProcessorChanged'
    assert before==(folder/'current.json').read_bytes()


def test_history_does_not_advance_market_target_or_turn_ST_names_into_style_coverage(tmp_path, monkeypatch):
    from market_risk import build_market_risk_status, market_update_status
    folder=tmp_path/'public_breadth_history';refresh(folder)
    args={'snapshot_dir':tmp_path,'database':tmp_path/'missing.db','manifest_path':tmp_path/'missing.json','now':NOW}
    missing=build_market_risk_status(**args)
    assert missing['requested_through'] is None and missing['status']=='unavailable'
    assert missing['market_coverage']['historical_breadth_venues_at_target']==0
    monkeypatch.setattr('market_risk._public_indices', lambda *args: (
        {'availability':'observed','through':'2026-11-04','content_digest':'synthetic'},
        [{'code':'csi_all_share','name':'synthetic','historical_only':False,'through':'2026-11-04'}]))
    result=build_market_risk_status(**args)
    assert result['market_coverage']['historical_breadth_venues_at_target']==1
    assert result['market_coverage']['breadth_at_target'] is False
    assert result['market_coverage']['st_style_at_target'] is False
    assert result['current_risk_assessment']=='not_calibrated'
    assert result['node_market_comparison']['status']=='not_evaluated'
    assert result['breadth_history']['matches_market_target'] is True
    monkeypatch.setattr('market_risk._public_indices', lambda *args: ({'availability':'missing'},[]))
    row=next(row for row in market_update_status(snapshot_dir=tmp_path,now=NOW) if row['source_id']=='exchange_breadth_history')
    assert row['series_at_target']==1 and row['declared_series']==2
    assert row['observation_count']==sum(p['listed_source_stocks'] for p in result['breadth_history']['points'])


@pytest.mark.parametrize('change',['future','future_target','naive','overcount','boolean','short_complete','scope'])
def test_pending_history_progress_is_checked_without_claiming_job_liveness(tmp_path, change):
    from market_risk import breadth_history_status
    refresh(tmp_path,Client(tmp_path.parent/'public_breadth',fail=DAYS[2]))
    path=tmp_path/'last_attempt.json';raw=json.loads(path.read_text())
    good=breadth_history_status(tmp_path,NOW)
    assert good['availability']=='missing' and good['last_recorded_attempt']['completed_days']==2
    assert 'process_id' not in good['last_recorded_attempt']
    if change=='future':raw['recorded_at']='2026-11-06T00:00:00+00:00'
    elif change=='future_target':raw['requested_through']='2026-11-05'
    elif change=='naive':raw['started_at']='2026-11-05T00:00:00'
    elif change=='overcount':raw['completed_days']=39
    elif change=='boolean':raw['completed_days']=True
    elif change=='short_complete':raw['status']='complete'
    else:raw['scope']='SSE_SZSE_A_shares'
    path.write_text(json.dumps(raw))
    assert breadth_history_status(tmp_path,NOW)['last_recorded_attempt'] is None
