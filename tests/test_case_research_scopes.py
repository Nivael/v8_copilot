from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest

import case_research_scopes as s
from canonical_json import digest
from data_refresh import atomic_write_json
from research_repository import ResearchRunCreate, ResearchRunLedger


def recorded(ledger, text):
    result = ledger.record(ResearchRunCreate(request_id=text, question_text=text, normalized_intent='research',
        evidence_pack_ids=['EP-AAAAAAAAAAAAAAAAAAAA'], final_answer=text,
        validation_report={'valid': True}, source_freshness={}, agent_surface='test'))
    with sqlite3.connect(ledger.path) as db:
        db.row_factory = sqlite3.Row
        return dict(db.execute('select ' + ','.join(s.RUN_FIELDS) + ' from research_runs where run_id=?',
                               (result.run_id,)).fetchone())


def test_explicit_history_role_keeps_record_and_only_changes_case_selection(tmp_path):
    ledger = ResearchRunLedger(tmp_path / 'runs.db')
    first = recorded(ledger, '当前公司研究')
    later = recorded(ledger, '历史制度核对')
    args = dict(ledger_db=ledger.path, directory=tmp_path / 'roles')
    value = s.mark_historical_review(later['run_id'], '仅核旧问依据', **args)
    assert s.current_company_runs([later, first], path=tmp_path/'roles/current.json') == [first]
    assert (tmp_path/'roles/history'/(value['content_digest']+'.json')).is_file()
    # The original ledger remains byte-for-byte the same logical records.
    with sqlite3.connect(ledger.path) as db:
        db.row_factory = sqlite3.Row
        actual = [dict(r) for r in db.execute('select ' + ','.join(s.RUN_FIELDS) + ' from research_runs order by completed_at')]
    assert actual == [first, later]
    assert s.mark_historical_review(later['run_id'], '重复标注', **args) == value
    assert s.current_company_runs([first], path=tmp_path/'roles/current.json') == [first]


@pytest.mark.parametrize('field', ['question_text', 'object_refs_json', 'final_answer',
                                  'experience_hits_json', 'source_freshness_json', 'completed_at'])
def test_changed_run_cannot_silently_reuse_role(tmp_path, field):
    ledger = ResearchRunLedger(tmp_path / 'runs.db'); run = recorded(ledger, '旧制度核对')
    s.mark_historical_review(run['run_id'], '历史用途', ledger_db=ledger.path, directory=tmp_path/'roles')
    changed = {**run, field: run[field] + 'x'}
    with pytest.raises(ValueError, match='no longer matches'):
        s.current_company_runs([changed], path=tmp_path/'roles/current.json')


@pytest.mark.parametrize('change', ['digest', 'purpose', 'future', 'naive', 'duplicate', 'reason', 'before_run'])
def test_invalid_metadata_cannot_hide_or_reclassify_a_run(tmp_path, change):
    ledger = ResearchRunLedger(tmp_path/'runs.db'); run = recorded(ledger, '历史核对')
    value = s.mark_historical_review(run['run_id'], '历史用途', ledger_db=ledger.path, directory=tmp_path/'roles')
    value = deepcopy(value); entry = value['assignments'][0]
    if change == 'digest': entry['reason'] = '被更改'
    if change == 'purpose': entry['purpose'] = 'current_company'
    if change == 'future': entry['reviewed_at'] = (datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
    if change == 'naive': entry['reviewed_at'] = '2020-01-01T00:00:00'
    if change == 'before_run': entry['reviewed_at'] = '2020-01-01T00:00:00+00:00'
    if change == 'duplicate': value['assignments'].append(deepcopy(entry))
    if change == 'reason': entry['reason'] = ' '
    if change != 'digest': value['content_digest'] = digest({k:v for k,v in value.items() if k!='content_digest'})
    atomic_write_json(tmp_path/'roles/current.json', value)
    with pytest.raises(ValueError): s.current_company_runs([run], path=tmp_path/'roles/current.json')


def test_unclassified_legacy_runs_are_preserved_and_unknown_run_is_not_written(tmp_path):
    ledger = ResearchRunLedger(tmp_path/'runs.db'); run = recorded(ledger, '当前判断')
    assert s.current_company_runs([run], path=tmp_path/'missing.json') == [run]
    with pytest.raises(ValueError, match='not found'):
        s.mark_historical_review('RUN-MISSING', '历史用途', ledger_db=ledger.path, directory=tmp_path/'roles')
    assert not (tmp_path/'roles').exists()


@pytest.mark.parametrize('reason', ['', ' ', 'x'*401])
def test_invalid_assignment_does_not_publish(tmp_path, reason):
    ledger = ResearchRunLedger(tmp_path/'runs.db'); run = recorded(ledger, '制度核对')
    with pytest.raises(ValueError):
        s.mark_historical_review(run['run_id'], reason, ledger_db=ledger.path, directory=tmp_path/'roles')
    assert not (tmp_path/'roles').exists()
