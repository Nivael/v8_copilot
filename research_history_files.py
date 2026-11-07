"""Message-bound files recovered through the original chat's download controls.

These are archived copies, not verified financial facts. Existing screenshot
captures keep their independent collector and provenance rules.
"""
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from canonical_json import digest
from data_refresh import atomic_write_json
from research_history_visuals import SHA,UUID,image_info

MAX_BYTES=8_000_000

def _observation(value):
    if value.get('version')!='history_download_observation_v1':raise ValueError('unsupported history file observation')
    message=value['source_message_id'];thread=value['source_thread_id'];url=urlsplit(value['source_url'])
    if (not UUID.fullmatch(message) or not UUID.fullmatch(thread) or value['question_id']!='QUESTION-'+message
            or url.scheme!='https' or url.netloc!='chatgpt.com' or url.path!='/c/'+thread or url.query or url.fragment):raise ValueError('history file identity mismatch')
    stamp=datetime.fromisoformat(value['observed_at'].replace('Z','+00:00'))
    if stamp.tzinfo is None or stamp>datetime.now(timezone.utc):raise ValueError('invalid history file clock')
    if not isinstance(value['question'],str) or not value['question'].strip():raise ValueError('history file has no original question')
    if value['media_kind'] not in {'image','document'}:raise ValueError('unsupported history file kind')
    if not isinstance(value['label'],str) or not 0<len(value['label'])<=150:raise ValueError('invalid history file label')
    if value.get('attachment_index')!=0 or type(value.get('attachment_count')) is not int or value['attachment_count']!=1:raise ValueError('this version requires a single attachment of its media kind')
    for field in ['binding_record_sha256','download_record_sha256']:
        if not SHA.fullmatch(value[field]):raise ValueError('missing history file source record')
    for field in ['binding_tool_call_id','download_tool_call_id']:
        if not isinstance(value[field],str) or not 0<len(value[field])<=200:raise ValueError('missing history file tool binding')
    name=value.get('file_name')
    if name is not None and (not isinstance(name,str) or Path(name).name!=name or '/' in name or '\\' in name or not 0<len(name)<=150 or any(ord(c)<32 for c in name)):raise ValueError('invalid history file name')
    if value['media_kind']=='document' and (not name or Path(name).suffix.lower() not in {'.md','.txt'}):raise ValueError('only text reference documents are supported')

def _asset(raw,observation):
    from hashlib import sha256
    if not 0<len(raw)<=MAX_BYTES:raise ValueError('history file size outside limit')
    if observation['media_kind']=='image':return image_info(raw)
    text=raw.decode('utf-8-sig')
    if not text.strip() or '\0' in text:raise ValueError('history document is not readable text')
    return {'sha256':sha256(raw).hexdigest(),'size_bytes':len(raw),'mime_type':'text/plain','extension':Path(observation['file_name']).suffix.lower()[1:]}

def archive_file(raw,observation,*,root):
    _observation(observation);asset=_asset(raw,observation)
    directory=root/'files/assets';directory.mkdir(parents=True,exist_ok=True)
    path=directory/(asset['sha256']+'.'+asset['extension'])
    if path.exists():
        if path.is_symlink() or path.read_bytes()!=raw:raise ValueError('history file bytes changed')
    else:
        with path.open('xb') as f:f.write(raw)
    wrapper={'version':'history_download_capture_v1','observation':observation,'asset':asset};wrapper['content_digest']=digest(wrapper)
    atomic_write_json(root/'files/captures'/(wrapper['content_digest']+'.json'),wrapper)
    return wrapper

def file_bytes(asset,*,root):
    if not SHA.fullmatch(asset['sha256']) or asset['extension'] not in {'md','txt','jpg','png'}:raise ValueError('invalid history file asset')
    path=root/'files/assets'/(asset['sha256']+'.'+asset['extension'])
    if path.is_symlink():raise ValueError('history file must be an immutable local copy')
    with path.open('rb') as f:raw=f.read(MAX_BYTES+1)
    media='document' if asset['extension'] in {'md','txt'} else 'image'
    if _asset(raw,{'media_kind':media,'file_name':'reference.'+asset['extension']})!=asset:raise ValueError('history file asset mismatch')
    return raw

def add_files(records,*,root):
    from research_history_prices import bound
    result=[{k:v for k,v in row.items() if k!='question_files'} for row in records];by_id={}
    for row in result:by_id.setdefault(row['id'],[]).append(row)
    selected={}
    for path in sorted((root/'files/captures').glob('*.json')):
        value=bound(path)
        if value['version']!='history_download_capture_v1':raise ValueError('invalid history file capture')
        observation=value['observation'];_observation(observation);asset=value['asset'];file_bytes(asset,root=root)
        matches=by_id.get(observation['question_id'],[])
        if len(matches)!=1:continue
        row=matches[0]
        if row['kind']!='original_question' or row['question']!=observation['question']:continue
        if not any(s.get('thread_id')==observation['source_thread_id'] and s.get('turn_id')==observation['source_message_id'] and s['kind'] in {'chatgpt','chatgpt_rendered'} for s in row['sources']):continue
        if observation['media_kind']=='image':
            if row.get('unavailable_attachments')!=1:continue
        elif '[User attached 1 file; file contents were not included]' not in row['question']:continue
        key=(row['id'],observation['media_kind']);rank=(datetime.fromisoformat(observation['observed_at'].replace('Z','+00:00')),value['content_digest'])
        if key not in selected or rank>selected[key][0]:selected[key]=(rank,observation,asset,value['content_digest'])
    for row in result:
        files=[]
        for kind in ['document','image']:
            entry=selected.get((row['id'],kind))
            if not entry:continue
            _,o,a,capture=entry
            files.append({'media_kind':kind,'label':o['label'],'file_name':o.get('file_name'),'sha256':a['sha256'],'mime_type':a['mime_type'],'size_bytes':a['size_bytes'],
                          **{k:a[k] for k in ['width','height'] if k in a},'captured_at':o['observed_at'],'source_url':o['source_url'],'source_message_id':o['source_message_id'],'source_thread_id':o['source_thread_id'],
                          'capture_digest':capture,'asset':a,'url':'/api/v1/workbench/history-files/'+a['sha256']})
        if files:row['question_files']=files
    return result
