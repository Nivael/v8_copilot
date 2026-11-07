"""Link a verified unanswered turn to its later expanded ask without moving answers."""
from collections import defaultdict
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import re

from canonical_json import digest
from data_refresh import atomic_write_json

VERSION='history_unanswered_followup_v1'
EXPORT_VERSION='history_thread_export_v1'


def export_payload(packet):
    if (packet.get('version')!=EXPORT_VERSION or packet.get('source_tool')!='mcp__codex_app.read_thread'
            or packet.get('content_digest')!=digest({k:v for k,v in packet.items() if k!='content_digest'})):
        raise ValueError('thread export identity or digest changed')
    text=packet['original_output']
    if sha256(text.encode()).hexdigest()!=packet['original_output_sha256']:
        raise ValueError('thread export original bytes changed')
    value=json.loads(text);thread=value['thread']
    if (value.get('schemaVersion')!=1 or thread.get('kind')!='chatgpt'
            or not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',thread['id'])
            or not isinstance(value.get('turns'),list)):
        raise ValueError('unsupported original thread export')
    return value


def collect_thread_export(original_output,links,*,root):
    """Save only an explicitly returned read_thread text and selected original-turn IDs."""
    packet={'version':EXPORT_VERSION,'source_tool':'mcp__codex_app.read_thread',
            'captured_at':datetime.now(timezone.utc).isoformat(),'original_output':original_output,
            'original_output_sha256':sha256(original_output.encode()).hexdigest(),'links':links}
    packet['content_digest']=digest(packet);export_payload(packet)
    path=Path(root)/'captures/thread_exports_v1'/(packet['content_digest']+'.json')
    atomic_write_json(path,packet)
    return path


def add_unanswered_followups(records,*,root):
    from research_history import instant,question_day,question_digest
    result=[{k:v for k,v in row.items() if k!='unanswered_followup'} for row in records]
    by_id=defaultdict(list);choices=defaultdict(dict)
    for row in result:by_id[row['id']].append(row)
    def matches(row,turn,thread):
        users=[i for i in turn.get('items',[]) if i.get('type')=='userMessage']
        answers=[i['text'] for i in turn.get('items',[]) if i.get('type')=='agentMessage']
        sources=[s for s in row['sources'] if s['kind']=='chatgpt' and s.get('thread_id')==thread and s.get('turn_id')==turn['id']]
        return (row['kind']=='original_question' and sources and len(users)==1
                and turn.get('status')=='completed' and not turn.get('error')
                and row.get('asked_at') is not None and turn.get('startedAt') is not None
                and instant(row['asked_at'])==instant(turn['startedAt'])
                and row['question']=='\n'.join(c.get('text','') for c in users[0].get('content',[]) if c.get('type')=='text').strip()
                and [a['text'] for a in row['answers']]==answers
                and (not answers or all(a.get('completed_at') is not None and instant(a['completed_at'])==instant(turn['completedAt']) for a in row['answers'])))
    for path in sorted((Path(root)/'captures/thread_exports_v1').glob('*.json')):
        if path.is_symlink():raise ValueError('thread export must not be a symlink')
        packet=json.loads(path.read_text());value=export_payload(packet)
        if path.stem!=packet['content_digest']:raise ValueError('thread export filename changed')
        thread=value['thread']['id'];turns=defaultdict(list)
        for turn in value['turns']:turns['QUESTION-'+turn['id']].append(turn)
        for link in packet['links']:
            firsts=by_id[link['unanswered_id']];targets=by_id[link['expanded_id']]
            if len(firsts)!=1 or len(targets)!=1:continue
            row,target=firsts[0],targets[0];first_turns=turns[row['id']];target_turns=turns[target['id']]
            if len(first_turns)!=1 or len(target_turns)!=1:continue
            if (row is target or row['answers'] or not target['answers']
                    or not matches(row,first_turns[0],thread) or not matches(target,target_turns[0],thread)
                    or instant(row['asked_at'])>=instant(target['asked_at'])
                    or not target['question'].startswith(row['question']) or target['question']==row['question']
                    or not set(row['symbols']).issubset(target['symbols'])
                    or ((not row['symbols'] or row.get('market_scope')) and target['symbols'] and not target.get('market_scope'))):
                continue
            context={'version':VERSION,'question_id':target['id'],'question':target['question'],
                     'asked_at':target['asked_at'],'asked_on':question_day(target),
                     'source_url':'https://chatgpt.com/c/'+thread,'target_question_digest':question_digest(target)}
            choices[row['id']][digest(context)]=context
    for row in result:
        if len(choices[row['id']])==1:row['unanswered_followup']=next(iter(choices[row['id']].values()))
    return result
