"""Bind frozen exchange catalogs and already-verified historical facts to fresh prices.

This only reuses materialized facts. It never fetches or reads PDF bodies.
"""
import argparse
import gzip
import json
from pathlib import Path
from canonical_json import digest


def bind(inputs, catalogs, history):
    for value in catalogs.values():
        if value['content_digest'] != digest({k:v for k,v in value.items() if k!='content_digest'}):
            raise ValueError('catalog binding changed')
        if not value['endpoint_window_complete'] or value['through'] != inputs['through']:
            raise ValueError('catalog window incomplete or different')
    if history['content_digest'] != digest({k:v for k,v in history.items() if k!='content_digest'}):
        raise ValueError('history binding changed')
    events = {}
    for sym, detail in history['details'].items():
        symbol = sym[:6]
        if symbol not in catalogs:
            continue
        for question in detail.get('questions',[]):
            for event in (question.get('review') or {}).get('event_timeline',{}).get('events',[]):
                if not '2026-07-01' <= str(event.get('published_on') or '') <= inputs['through']:
                    continue
                source = event.get('source') or {}
                if not all(source.get(k) for k in ('sha256','page','url')):
                    continue
                key = (symbol,source['sha256'],event['title'])
                clean = {k:v for k,v in event.items() if k!='context'}
                clean['symbol'] = symbol
                # Explicit, documented source conflict, not a general title/date guess.
                if symbol=='002514' and clean['published_on']=='2026-07-04' and '公开日期有冲突' in clean['title']:
                    clean['alternate_published_on'] = '2026-07-06'
                    clean['date_uncertainty'] = '目录及URL为7月4日，PDF落款为7月6日，首发分钟未核；两种日期均计算，不能确定最早反应。'
                clean['catalog_id_present'] = any(r['announcement_id']==source.get('announcement_id') for r in catalogs[symbol]['rows'])
                if key in events and events[key]['published_on'] != clean['published_on']:
                    raise ValueError('conflicting event date')
                events[key] = clean
    packet = {'start':'2026-07-01','through':inputs['through'],'catalogs':catalogs,
              'history_digest':history['content_digest'],
              'verified_events':sorted(events.values(),key=lambda e:(e['published_on'],e['symbol'],e['title']))}
    packet['content_digest'] = digest(packet)
    return {**inputs,'announcement_study':packet}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--catalogs',type=Path,required=True)
    parser.add_argument('--history',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = bind(json.loads(gzip.decompress(args.input.read_bytes())),json.loads(args.catalogs.read_text()),json.loads(args.history.read_text()))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(gzip.compress(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode(),mtime=0))
    print(json.dumps({'input_digest':digest(result),'events':len(result['announcement_study']['verified_events'])}))


if __name__=='__main__':
    main()
