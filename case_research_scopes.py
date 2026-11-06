"""Keep explicitly classified historical checks out of current company judgments."""
import argparse
from datetime import datetime, timezone
import json
import sqlite3

from canonical_json import digest
from data_refresh import atomic_write_json
from settings import DATA_ROOT, RESEARCH_RUN_LEDGER_DB

VERSION = 'workbench_research_scopes_v1'
OUTPUT = DATA_ROOT / 'local_data/v8_copilot/workbench_views/research_scopes'
RUN_FIELDS = ('run_id', 'question_text', 'object_refs_json', 'final_answer',
              'experience_hits_json', 'source_freshness_json', 'completed_at')


def instant(value):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('research scope date has no timezone')
    return stamp


def load_scopes(path):
    if not path.exists():
        return {'version': VERSION, 'assignments': []}
    value = json.loads(path.read_text())
    if (not isinstance(value, dict) or set(value) != {'version', 'assignments', 'content_digest'} or value['version'] != VERSION
            or digest({k: v for k, v in value.items() if k != 'content_digest'}) != value['content_digest']
            or not isinstance(value['assignments'], list)):
        raise ValueError('research scope packet changed')
    seen = set()
    for row in value['assignments']:
        if (not isinstance(row, dict) or set(row) != {'run_id', 'run_digest', 'purpose', 'reason', 'reviewed_at'}
                or not isinstance(row['run_id'], str) or not row['run_id'] or row['run_id'] in seen
                or row['purpose'] != 'historical_review' or not isinstance(row['reason'], str)
                or not 1 <= len(row['reason'].strip()) <= 400
                or not isinstance(row['run_digest'], str) or len(row['run_digest']) != 64
                or any(c not in '0123456789abcdef' for c in row['run_digest'])
                or not isinstance(row['reviewed_at'], str) or instant(row['reviewed_at']) > datetime.now(timezone.utc)):
            raise ValueError('invalid historical research scope')
        seen.add(row['run_id'])
    return value


def current_company_runs(runs, *, path=OUTPUT / 'current.json'):
    roles = {r['run_id']: r for r in load_scopes(path)['assignments']}
    result = []
    for run in runs:
        role = roles.get(run['run_id'])
        if role is None:
            result.append(run)
        elif (role['run_digest'] != digest({k: run[k] for k in RUN_FIELDS})
              or instant(role['reviewed_at']) < instant(run['completed_at'])):
            raise ValueError('historical research scope no longer matches its run')
    return result


def mark_historical_review(run_id, reason, *, ledger_db=RESEARCH_RUN_LEDGER_DB, directory=OUTPUT):
    """Explicit reading metadata only; never rewrite or remove the recorded run."""
    with sqlite3.connect(ledger_db.as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        row = db.execute('select ' + ','.join(RUN_FIELDS) + ' from research_runs where run_id=?', (run_id,)).fetchone()
    if row is None:
        raise ValueError('research run not found')
    run = dict(row)
    value = load_scopes(directory / 'current.json')
    current_company_runs([run], path=directory / 'current.json')
    if any(role['run_id'] == run_id for role in value['assignments']):
        return value
    entry = {'run_id': run_id, 'run_digest': digest(run), 'purpose': 'historical_review',
             'reason': reason, 'reviewed_at': datetime.now(timezone.utc).isoformat()}
    body = {'version': VERSION, 'assignments': [*value['assignments'], entry]}
    body['content_digest'] = digest(body)
    # Validate the prospective packet before publishing either pointer or archive.
    if (not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 400
            or instant(run['completed_at']) > instant(entry['reviewed_at'])):
        raise ValueError('invalid historical research scope reason or time')
    atomic_write_json(directory / 'history' / (body['content_digest'] + '.json'), body)
    atomic_write_json(directory / 'current.json', body)
    return body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--reason', required=True)
    args = parser.parse_args()
    value = mark_historical_review(args.run_id, args.reason)
    print(json.dumps({'run_id': args.run_id, 'purpose': 'historical_review', 'content_digest': value['content_digest']}))


if __name__ == '__main__':
    main()
