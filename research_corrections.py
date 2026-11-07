"""Verified reading notes; recorded research and original conversations stay immutable."""
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3

from canonical_json import digest
from case_research_scopes import RUN_FIELDS, instant
from data_refresh import atomic_write_json
from settings import RESEARCH_RUN_LEDGER_DB

VERSION = 'research_corrections_v1'
FIELDS = (*RUN_FIELDS, 'validation_report_json')
SHA = re.compile(r'^[a-f0-9]{64}$')
RUN_ID = re.compile(r'^RUN-[A-F0-9]{24}$')


def correction_path(ledger_db=RESEARCH_RUN_LEDGER_DB):
    return ledger_db.parent / 'research_corrections/current.json'


def text(value, maximum):
    return isinstance(value, str) and 0 < len(value.strip()) <= maximum


def validate_packet(value):
    if (not isinstance(value, dict) or set(value) != {'version', 'entries', 'content_digest'}
            or value['version'] != VERSION or not isinstance(value['entries'], list)
            or digest({k: v for k, v in value.items() if k != 'content_digest'}) != value['content_digest']):
        raise ValueError('research correction packet changed')
    seen = {}
    for entry in value['entries']:
        if (not isinstance(entry, dict) or set(entry) != {
                'old_run_id', 'old_run_digest', 'replacement_run_id', 'replacement_run_digest',
                'original_question', 'headline', 'summary', 'corrected_at'}
                or not text(entry['headline'], 160) or not text(entry['summary'], 1000)
                or not isinstance(entry['corrected_at'], str)
                or instant(entry['corrected_at']) > datetime.now(timezone.utc)):
            raise ValueError('invalid research correction')
        for prefix in ('old', 'replacement'):
            if (not isinstance(entry[prefix + '_run_id'], str) or not RUN_ID.fullmatch(entry[prefix + '_run_id'])
                    or not isinstance(entry[prefix + '_run_digest'], str) or not SHA.fullmatch(entry[prefix + '_run_digest'])):
                raise ValueError('invalid correction run binding')
        old, new = entry['old_run_id'], entry['replacement_run_id']
        if old == new or old in seen:
            raise ValueError('duplicate or self-referential research correction')
        seen[old] = new
        original = entry['original_question']
        if original is not None and (not isinstance(original, dict) or set(original) != {'id', 'digest', 'answer_quote'}
                or not text(original['id'], 128) or not isinstance(original['digest'], str)
                or not SHA.fullmatch(original['digest']) or not text(original['answer_quote'], 2000)):
            raise ValueError('invalid correction original binding')
    for start in seen:
        visited = set()
        while start in seen:
            if start in visited:
                raise ValueError('cyclic research corrections')
            visited.add(start)
            start = seen[start]
    return value


def load_packet(path):
    if not path.exists():
        value = {'version': VERSION, 'entries': []}
        return {**value, 'content_digest': digest(value)}
    return validate_packet(json.loads(path.read_text()))


def _shared_original_question(db, entry, *, question=None):
    """Recover a legacy unknown subject only from both immutable validated packs.

    A display association or a newly supplied correction label is insufficient.
    Both recorded studies must contain the same original question as a catalogued
    evidence row; publication also checks that text against the actual original.
    """
    original = entry['original_question']
    if not original:
        return False
    questions = []
    for prefix in ('old', 'replacement'):
        row = db.execute('select evidence_pack_ids_json,validation_report_json from research_runs where run_id=?',
                         (entry[prefix + '_run_id'],)).fetchone()
        report = json.loads(row['validation_report_json'])
        pack_id = report.get('pack_id')
        if report.get('valid') is not True or pack_id not in json.loads(row['evidence_pack_ids_json']):
            return False
        saved = db.execute('select pack_digest,payload_json from evidence_packs where pack_id=?', (pack_id,)).fetchone()
        if saved is None:
            return False
        pack = json.loads(saved['payload_json'])
        if (digest({k: v for k, v in pack.items() if k not in {'pack_id', 'pack_digest'}}) != saved['pack_digest']
                or pack.get('pack_id') != pack_id or pack.get('pack_digest') != saved['pack_digest']
                or report.get('pack_digest') != saved['pack_digest']):
            return False
        rows = [r for r in pack['rows'] if r.get('question_id') == original['id']]
        if len(rows) != 1 or not text(rows[0].get('question'), 100000):
            return False
        catalogued = json.loads(pack['validation_catalog'].get('query_row:' + rows[0]['row_id'], '{}'))
        if catalogued != {k: v for k, v in rows[0].items() if k != 'row_id'}:
            return False
        questions.append(rows[0]['question'])
    return questions[0] == questions[1] and (question is None or questions[0] == question)


def verified_packet(*, ledger_db=RESEARCH_RUN_LEDGER_DB, path=None):
    value = load_packet(path or correction_path(ledger_db))
    ids = {entry[prefix + '_run_id'] for entry in value['entries'] for prefix in ('old', 'replacement')}
    if not ids:
        return value, {}
    with closing(sqlite3.connect(ledger_db.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        records = {r['run_id']: dict(r) for r in db.execute(
            'select ' + ','.join(FIELDS) + ' from research_runs where run_id in (' + ','.join('?' for _ in ids) + ')', sorted(ids))}
    for entry in value['entries']:
        old, new = (records.get(entry[prefix + '_run_id']) for prefix in ('old', 'replacement'))
        if old is None or new is None:
            raise ValueError('correction research run not found')
        if any(digest(records[entry[prefix + '_run_id']]) != entry[prefix + '_run_digest'] for prefix in ('old', 'replacement')):
            raise ValueError('research correction no longer matches its run')
        if (instant(new['completed_at']) <= instant(old['completed_at'])
                or instant(entry['corrected_at']) < instant(new['completed_at'])
                or json.loads(new['validation_report_json']).get('valid') is not True):
            raise ValueError('replacement must be a later validated research run')
        before, after = (set(json.loads(row['object_refs_json'])) for row in (old, new))
        if (before or after) and not before.intersection(after):
            with closing(sqlite3.connect(ledger_db.resolve().as_uri() + '?mode=ro', uri=True)) as db:
                db.row_factory = sqlite3.Row
                if before != {'unknown'} or not after or not _shared_original_question(db, entry):
                    raise ValueError('correction research subjects do not overlap')
    return value, records


def public_note(entry):
    return {**{key: entry[key] for key in ('old_run_id', 'replacement_run_id', 'headline', 'summary', 'corrected_at')},
            'original_question_id': entry['original_question']['id'] if entry['original_question'] else None}


def annotations(records, packet, runs, *, ledger_db=RESEARCH_RUN_LEDGER_DB):
    """Bind display-only notes to both exact saved studies and the quoted original."""
    from research_history import question_digest
    by_id = {row['id']: row for row in records}
    result = {}
    for entry in packet['entries']:
        for prefix, role in [('old', 'corrected_study'), ('replacement', 'replacement_study')]:
            identity = entry[prefix + '_run_id']
            saved, run = by_id.get(identity), runs[identity]
            if (saved is None or saved['kind'] != 'saved_research'
                    or saved['question'] != run['question_text']
                    or len(saved['answers']) != 1 or saved['answers'][0]['text'] != run['final_answer']
                    or instant(saved['asked_at']) != instant(run['completed_at'])
                    or not any(s.get('kind') == 'research_ledger' and s.get('run_id') == identity for s in saved['sources'])):
                raise ValueError('correction saved study is missing or changed')
            result.setdefault(identity, []).append({**public_note(entry), 'role': role})
        original = entry['original_question']
        if original:
            row = by_id.get(original['id'])
            if (row is None or row['kind'] != 'original_question' or question_digest(row) != original['digest']
                    or not any(original['answer_quote'] in answer['text'] for answer in row['answers'])):
                raise ValueError('correction original question or answer changed')
            before, after = (set(json.loads(runs[entry[prefix + '_run_id']]['object_refs_json']))
                             for prefix in ('old', 'replacement'))
            if not before.intersection(after):
                with closing(sqlite3.connect(ledger_db.resolve().as_uri() + '?mode=ro', uri=True)) as db:
                    db.row_factory = sqlite3.Row
                    if not _shared_original_question(db, entry, question=row['question']):
                        raise ValueError('legacy correction evidence differs from the actual original')
            result.setdefault(original['id'], []).append({**public_note(entry), 'role': 'original_review'})
    return result


def corrected_run_ids(*, ledger_db=RESEARCH_RUN_LEDGER_DB, path=None):
    packet, _ = verified_packet(ledger_db=ledger_db, path=path)
    require_published_binding(packet, ledger_db)
    return {entry['old_run_id'] for entry in packet['entries']}


def require_published_binding(packet, ledger_db):
    history = ledger_db.parent / 'research_history/current.json'
    if history.exists():
        value = json.loads(history.read_text())
        if (digest({k:v for k,v in value.items() if k!='content_digest'}) != value.get('content_digest')
                or value.get('corrections_digest', packet['content_digest']) != packet['content_digest']):
            raise ValueError('published research corrections are missing or out of date')


def reading_view(*, ledger_db=RESEARCH_RUN_LEDGER_DB, path=None):
    try:
        packet, _ = verified_packet(ledger_db=ledger_db, path=path)
        require_published_binding(packet, ledger_db)
        return {'availability': 'available', 'content_digest': packet['content_digest'],
                'corrections': [public_note(entry) for entry in packet['entries']]}
    except (OSError, KeyError, ValueError, TypeError, sqlite3.Error):
        return {'availability': 'updating', 'corrections': []}


def publish(entries, *, ledger_db=RESEARCH_RUN_LEDGER_DB, directory=None, records):
    """Validate before either write; the ledger is opened read-only throughout."""
    directory = directory or correction_path(ledger_db).parent
    body = {'version': VERSION, 'entries': entries}
    body['content_digest'] = digest(body)
    validate_packet(body)
    # Validate the prospective packet through the same reader without publishing it.
    from tempfile import TemporaryDirectory
    with TemporaryDirectory(prefix='v8-correction-check-') as temporary:
        candidate = Path(temporary) / 'candidate.json'
        atomic_write_json(candidate, body)
        packet, runs = verified_packet(ledger_db=ledger_db, path=candidate)
        annotations(records, packet, runs, ledger_db=ledger_db)
    atomic_write_json(directory / 'history' / (body['content_digest'] + '.json'), body)
    atomic_write_json(directory / 'current.json', body)
    return body


def main():
    import argparse
    from research_history import prepare_history_records
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entries', type=Path, required=True)
    parser.add_argument('--history-import', type=Path, required=True)
    args = parser.parse_args()
    records = prepare_history_records(json.loads(args.history_import.read_text()))
    packet = publish(json.loads(args.entries.read_text()), records=records)
    print(json.dumps({'content_digest': packet['content_digest'], 'corrections': len(packet['entries'])}))


if __name__ == '__main__':
    main()
