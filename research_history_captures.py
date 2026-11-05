"""Preserve returned DOM captures from an explicitly selected local tool log.

This reads already-returned CUA output, never browser profiles, app state or a
hidden browser endpoint. Only the dedicated capture marker from CUA is accepted.
"""
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from research_history import TOPICS,clean_question,instant,judgment,mentioned
from research_history_prices import bound

PREFIX='HISTORY_DOM_V1:'
UUID=re.compile(r'^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$')


def marked_captures(text):
    """CUA can coalesce several writes into one text item; bound each JSON value."""
    offset=0;decoder=json.JSONDecoder();marker=re.compile(re.escape(PREFIX)+r'(?=\{)')
    while match:=marker.search(text,offset):
        start=match.start()
        capture,end=decoder.raw_decode(text,start+len(PREFIX))
        yield start,end,validate_capture(capture)
        # Skip markers inside the JSON string content itself.
        offset=end


def validate_capture(value):
    if value.get('version')!='history_dom_capture_v1' or not UUID.fullmatch(value['thread_id']):raise ValueError('invalid conversation capture identity')
    stamp=instant(value['captured_at'])
    if stamp>datetime.now(timezone.utc):raise ValueError('future capture')
    url=value.get('url')
    if url:
        parts=urlsplit(url)
        if parts.scheme!='https' or parts.netloc!='chatgpt.com' or not parts.path.endswith('/c/'+value['thread_id']):raise ValueError('conversation URL mismatch')
    ids=set()
    for row in value['turns']:
        if not UUID.fullmatch(row['id']) or row['id'] in ids:raise ValueError('invalid original message identity')
        ids.add(row['id'])
        if not isinstance(row['has_own_time'],bool) or not isinstance(row['question'],str):raise ValueError('invalid original message')
        if row.get('date_marker') and instant(row['date_marker'])>stamp:raise ValueError('future question date')
        if row.get('date_bounds'):
            lower=row['date_bounds'].get('not_before');upper=row['date_bounds'].get('not_after')
            if any(instant(v)>stamp for v in (lower,upper) if v):raise ValueError('future question date bound')
            if lower and upper and instant(lower)>instant(upper):raise ValueError('reversed question date bounds')
        if row['has_own_time'] and not row.get('date_marker'):raise ValueError('missing independent timestamp')
        owner=row.get('date_marker_owner')
        if owner and (not UUID.fullmatch(owner) or row['has_own_time'] and owner!=row['id']):raise ValueError('timestamp owner mismatch')
        if row.get('question_node') not in {None,'user_content','user_bubble'}:raise ValueError('unknown question text node')
        if row.get('group_offset',0)<0:raise ValueError('invalid source order')
        for answer in row['answers']:
            if not isinstance(answer['text'],str) or answer.get('id') and not UUID.fullmatch(answer['id']):raise ValueError('invalid original answer')
    return value


def collect_outputs(log_path,directory,*,tail_bytes=8_000_000):
    """Select our marked CUA results from an append-only conversation tool log."""
    found=[];calls={}
    with log_path.open('rb') as stream:
        stream.seek(max(0,log_path.stat().st_size-tail_bytes))
        if stream.tell():stream.readline()
        while True:
            offset=stream.tell();raw=stream.readline()
            if not raw:break
            try:event=json.loads(raw)
            except ValueError:continue
            payload=event.get('payload',{})
            if event.get('type')!='response_item':continue
            if payload.get('type')=='function_call':
                calls[payload['call_id']]=(payload.get('namespace'),payload.get('name'));continue
            if payload.get('type')!='function_call_output' or calls.get(payload.get('call_id'))!=('mcp__cua_repl','js'):continue
            outputs=payload.get('output',[])
            if not isinstance(outputs,list):continue
            for item_index,item in enumerate(outputs):
                text=item.get('text','')
                for start,end,capture in marked_captures(text):
                    original=text[start:end]
                    value={'version':'research_history_dom_original_v1','capture':capture,'original_output':original,
                           'output_sha256':sha256(original.encode()).hexdigest(),'source_file':log_path.name,
                           'source_record_sha256':sha256(raw).hexdigest(),'byte_offset':offset,'tool_call_id':payload['call_id']}
                    if original!=text:
                        value.update(tool_output_text=text,tool_output_sha256=sha256(text.encode()).hexdigest(),
                                     capture_text_range=[start,end],output_item_index=item_index)
                    value['content_digest']=digest(value);path=directory/(value['content_digest']+'.json')
                    if not path.exists():atomic_write_json(path,value)
                    found.append(path)
    return found


def import_capture_files(directory,known):
    rows=[];sources=[]
    for path in sorted(directory.glob('*.json')):
        value=bound(path)
        if value['version']!='research_history_dom_original_v1':raise ValueError('unexpected capture wrapper')
        raw=value['original_output']
        if not raw.startswith(PREFIX) or sha256(raw.encode()).hexdigest()!=value['output_sha256'] or json.loads(raw[len(PREFIX):])!=value['capture']:raise ValueError('original capture changed')
        if 'tool_output_text' in value:
            text=value['tool_output_text'];start,end=value['capture_text_range']
            if (not isinstance(start,int) or not isinstance(end,int) or not 0<=start<end<=len(text)
                    or text[start:end]!=raw or sha256(text.encode()).hexdigest()!=value['tool_output_sha256']):
                raise ValueError('coalesced tool output changed')
        capture=validate_capture(value['capture']);context=mentioned(capture['title'],known)
        source={'kind':'chatgpt_rendered','thread_id':capture['thread_id'],'title':capture['title'],'capture_digest':value['content_digest'],
                'source_record_sha256':value['source_record_sha256'],'capture_scope':'visible_returned_DOM; not a claim of complete thread'}
        sources.append(source)
        for index,turn in enumerate(capture['turns']):
            question=clean_question(turn['question'])
            if not question:continue
            date_fields={};exact=turn['has_own_time'];marker=instant(turn['date_marker']) if turn.get('date_marker') else None
            if marker:
                day=marker.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat();precision='instant' if exact else 'day'
            else:
                bounds=turn.get('date_bounds',{});lower=bounds.get('not_before');upper=bounds.get('not_after')
                if not lower or not upper:continue
                lower_day=instant(lower).astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat();upper_day=instant(upper).astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
                day=lower_day if lower_day==upper_day else None;precision='day' if day else 'range'
                date_fields={'source_date_bounds':bounds,**({'asked_from':lower_day,'asked_through':upper_day} if precision=='range' else {})}
            symbols=mentioned(question,known)
            rows.append({'id':'QUESTION-'+turn['id'],'asked_at':marker.isoformat() if exact else None,'asked_on':day,
                         'time_precision':precision,'source_date_marker':turn.get('date_marker'),**date_fields,
                         'source_date_owner_id':turn.get('date_marker_owner'),
                         'source_group_offset':turn.get('group_offset',index),'question':question,'original_question':question,
                         'date_source':'original_chat_rendered_timestamp' if exact else 'original_chat_rendered_time_bounds' if date_fields else 'original_chat_rendered_date_group',
                         'kind':'original_question','symbols':symbols or context,'scope_kind':'explicit' if symbols else 'conversation_context',
                         'question_representation':turn.get('question_node','user_bubble'),
                         'unavailable_attachments':turn.get('attachment_count',0),
                         'categories':[k for k,terms in TOPICS.items() if any(t in question for t in terms)] or ['研究方法'],
                         'answers':[{'text':a['text'],'summary':judgment(a['text']),'completed_at':None,'truncated':False,
                                     'source_thread_id':capture['thread_id'],'source_message_id':a.get('id'),
                                     'capture_scope':'rendered_answer_text','links':a.get('links',[])} for a in turn['answers'] if a['text'].strip()],
                         'sources':[{**source,'turn_id':turn['id'],'url':'https://chatgpt.com/c/'+capture['thread_id'],
                                     'asked_at':marker.isoformat() if exact else None,'asked_on':day,'time_precision':precision,**date_fields}]})
    return rows,sources


def merge_records(existing,additions):
    """Stable message IDs enrich an original rather than creating a second ask."""
    result=[{**r} for r in existing];by_id={}
    def register(record):
        by_id[record['id']]=record
        for source in record['sources']:
            if source['kind'] in {'chatgpt','chatgpt_rendered'} and source.get('turn_id'):by_id['QUESTION-'+source['turn_id']]=record
        for occurrence in record.get('occurrences',[]):by_id[occurrence['id']]=record
    for record in result:register(record)
    for record in additions:
        if record['id'] not in by_id:result.append(record);register(record);continue
        old=by_id[record['id']];old['sources']=list({digest(source):source for source in [*old['sources'],*record['sources']]}.values())
        rendered_only=all(source['kind']=='chatgpt_rendered' for source in old['sources'])
        if record.get('question_representation')=='user_content' and old.get('question_representation')!='user_content' and rendered_only:
            old.update({k:record[k] for k in ['question','original_question','question_representation','categories']})
        if not old['answers']:old['answers']=record['answers']
        if old['question']==record['question']:
            # Attachment controls may appear after the initial text render.
            old['unavailable_attachments']=max(old.get('unavailable_attachments',0),record.get('unavailable_attachments',0))
        # Keep exact tool timestamps and the original answer representation.
        was_range=old.get('time_precision')=='range'
        if was_range and record.get('time_precision') in {'day','instant'}:
            resolved_day=instant(record['asked_at']).astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat() if record.get('asked_at') else record['asked_on']
            if not old['asked_from']<=resolved_day<=old['asked_through']:raise ValueError('new original date conflicts with captured bounds')
        # A prior explicit day-only correction cannot be undone by replaying an old clock.
        if old.get('asked_at') is None and record.get('asked_at') and (was_range or old.get('time_precision')!='day'):
            old.update({k:record[k] for k in ['asked_at','asked_on','time_precision','date_source']})
            if was_range:old.update({k:record[k] for k in ['source_date_marker','source_date_owner_id','source_group_offset']})
        elif old.get('time_precision')=='range' and record.get('time_precision')=='day':
            old.update({k:record[k] for k in ['asked_at','asked_on','time_precision','date_source','source_date_marker','source_date_owner_id','source_group_offset']})
        if old.get('time_precision')!='range':
            for name in ('asked_from','asked_through'):old.pop(name,None)
        register(old)
    return result


def main():
    import argparse
    from research_history import ROOT,deduplicate
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--log',type=Path,required=True);parser.add_argument('--import-file',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    directory=ROOT/'captures/cua_v1';paths=collect_outputs(args.log,directory)
    imported=json.loads(args.import_file.read_text());rows,sources=import_capture_files(directory,imported['stock_names'])
    imported['records']=deduplicate(merge_records(imported['records'],rows));imported['sources']=list({digest(source):source for source in [*imported['sources'],*sources]}.values())
    atomic_write_json(args.output,imported)
    print(json.dumps({'captures':len(paths),'captured_rows':len(rows),'merged_records':len(imported['records'])}))


if __name__=='__main__':main()
