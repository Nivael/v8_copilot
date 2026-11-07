"""Load dated human research judgments bound to source originals and price snapshots."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from canonical_json import digest


def reviewed_packet(path, root, *, basis=None):
    """A changed price basis or missing/changed original withdraws the current note."""
    value=json.loads(path.read_text())
    if value['version']!='trader_research_notes_v1' or digest({k:v for k,v in value.items() if k!='content_digest'})!=value['content_digest']:
        raise ValueError('research note changed')
    stamp=datetime.fromisoformat(value['checked_at'])
    if stamp.tzinfo is None or stamp>datetime.now(timezone.utc):raise ValueError('invalid research date')
    if basis is not None and value.get('basis_digest')!=basis:raise ValueError('research prices have changed')
    urls=set()
    for ref in value['sources']:
        if ref['kind']=='company_pdf':
            aid=ref['announcement_id']
            if not aid.isdecimal():raise ValueError('invalid document identity')
            directory=root/'company_updates/documents'
            document=json.loads((directory/(aid+'.json')).read_text())
            if (document['announcement_id']!=aid or document['code']!=ref['code'] or document['url']!=ref['url']
                or document['response_url']!=ref['url'] or document['raw_sha256']!=ref['raw_sha256']
                or document['existing_local_body_id_match'] or document['existing_local_text_match']):raise ValueError('document identity changed')
            raw=(directory/(ref['raw_sha256']+'.pdf')).read_bytes()
            if len(raw)!=document['bytes'] or sha256(raw).hexdigest()!=ref['raw_sha256']:raise ValueError('document original changed')
            for page in ref['pages']:
                text=document['pages'][page['page']-1]
                if sha256(text.encode()).hexdigest()!=page['text_sha256']:raise ValueError('reviewed page changed')
        elif ref['kind']=='published_disclosure':
            key=ref['raw_sha256']
            if len(key)!=64 or any(c not in '0123456789abcdef' for c in key):raise ValueError('invalid source key')
            directory=root/'capital_actions/sources'
            meta=json.loads((directory/(key+'.json')).read_text());raw=(directory/(key+'.html')).read_bytes()
            if meta['url']!=ref['url'] or meta['response_url']!=ref['url'] or sha256(raw).hexdigest()!=key:raise ValueError('disclosure original changed')
        else:raise ValueError('unknown research source')
        urls.add(ref['url'])
    for note in [*value['data'].get('notes',{}).values(),*value['data'].get('actions',[])]:
        if not note['sources'] or any(source['url'] not in urls for source in note['sources']):raise ValueError('unbound research citation')
    return value


def attach_swing_notes(data, basis, root):
    result=deepcopy(data)
    try:
        review=reviewed_packet(root/'swing_watch/research.json',root,basis=basis)
    except (OSError,ValueError,KeyError,TypeError,IndexError):return result
    result['analysis']=review['data']['analysis']
    result['analysis_as_of']=review['checked_at']
    for row in [*result.get('watchlist',[]),*[row for group in result['groups'] for row in group['rows']]]:
        if row['symbol'] in review['data']['notes']:row['note']=review['data']['notes'][row['symbol']]
    return result


def capital_actions(root):
    try:
        review=reviewed_packet(root/'capital_actions/current.json',root)
        return {**review['data'],'checked_at':review['checked_at']}
    except (OSError,ValueError,KeyError,TypeError,IndexError):return None
