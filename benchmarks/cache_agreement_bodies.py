"""Fetch only reviewed casebook documents into an explicit isolated cache.

No research database mutations. Network is opt-in; failures remain visible and
return nonzero. Existing official URL, size, page and cache guards are reused.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from announcement_body import load_announcement_body
from announcement_inventory import OfficialAnnouncement
from settings import BASE_DB


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--casebook', type=Path, default=Path(__file__).parent / 'fixtures/investor_agreements_20260910.json')
    parser.add_argument('--db', type=Path, default=BASE_DB)
    parser.add_argument('--cache-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-network', action='store_true')
    parser.add_argument('--workers', type=int, choices=range(1, 7), default=4)
    args = parser.parse_args()
    casebook = json.loads(args.casebook.read_text())
    records = {}
    for case in casebook['cases']:
        for role in ('industrial', 'financial'):
            key = case[f'{role}_id']
            records[key] = (OfficialAnnouncement(key, case[f'{role}_inventory_date'],
                            case['name'] + ' ' + role, case[f'{role}_url'], 'cninfo', False),
                            case['body_digests'][role])

    def acquire(value: tuple) -> dict:
        record, expected = value
        started = time.perf_counter()
        try:
            body = load_announcement_body(record, source_db=args.db, cache_dir=args.cache_dir,
                                          allow_network=args.allow_network, timeout_seconds=12)
            actual = hashlib.sha256(body.text.encode()).hexdigest()
            return {'announcement_id': record.announcement_id, 'source': body.source,
                    'body_sha256': actual, 'matches_reviewed_text': actual == expected,
                    'seconds': time.perf_counter() - started,
                    **({'error': 'Text changed; review before reusing extracted terms'} if actual != expected else {})}
        except Exception as exc:
            return {'announcement_id': record.announcement_id, 'error': str(exc),
                    'seconds': time.perf_counter() - started}

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(acquire, records.values()))
    failures = sum('error' in row for row in results)
    payload = {'wall_seconds': time.perf_counter() - started, 'documents': len(results),
               'failures': failures, 'results': results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: value for key, value in payload.items() if key != 'results'}))
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
