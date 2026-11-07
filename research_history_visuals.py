"""Local, message-bound captures of attachments visibly opened in the original chat.

Only already-returned CUA images are collected. A rendered capture never claims
to be the uploaded original file or to verify statements inside that image.
"""
import base64
from collections import defaultdict
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import struct
from urllib.parse import urlsplit

from canonical_json import digest
from data_refresh import atomic_write_json

PREFIX='HISTORY_ATTACHMENT_OBSERVATION_V1:'
GROUP_PREFIX='HISTORY_ATTACHMENT_OBSERVATION_V2:'
VERSIONS={'history_attachment_observation_v1':(PREFIX,'history_attachment_capture_v1'),
          'history_attachment_observation_v2':(GROUP_PREFIX,'history_attachment_capture_v2')}
UUID=re.compile(r'^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$')
SHA=re.compile(r'^[a-f0-9]{64}$')
MAX_BYTES=8_000_000


def image_info(raw):
    if not 0<len(raw)<=MAX_BYTES:raise ValueError('attachment size outside local limit')
    if raw.startswith(b'\x89PNG\r\n\x1a\n') and raw[12:16]==b'IHDR' and len(raw)>=33:
        width,height=struct.unpack('>II',raw[16:24]);mime,extension='image/png','png'
    elif raw.startswith(b'\xff\xd8') and raw.endswith(b'\xff\xd9'):
        offset=2;width=height=0
        while offset+4<=len(raw):
            if raw[offset]!=255:raise ValueError('invalid JPEG marker')
            while offset<len(raw) and raw[offset]==255:offset+=1
            if offset>=len(raw):break
            marker=raw[offset];offset+=1
            if marker in {0xd8,0x01,*range(0xd0,0xd8)}:continue
            if marker in {0xd9,0xda}:break
            size=int.from_bytes(raw[offset:offset+2],'big')
            if size<2 or offset+size>len(raw):raise ValueError('invalid JPEG segment')
            if marker in {0xc0,0xc1,0xc2} and size>=8:
                height,width=struct.unpack('>HH',raw[offset+3:offset+7]);break
            offset+=size
        mime,extension='image/jpeg','jpg'
    else:raise ValueError('only PNG and JPEG attachment captures are supported')
    if not 0<width<=8192 or not 0<height<=8192 or width*height>16_000_000:raise ValueError('invalid attachment dimensions')
    return {'mime_type':mime,'extension':extension,'width':width,'height':height,'size_bytes':len(raw),'sha256':sha256(raw).hexdigest()}


def validate_observation(value):
    if value.get('version') not in VERSIONS or value.get('kind')!='rendered_capture':raise ValueError('unsupported attachment observation')
    identity=value['source_message_id']
    parts=urlsplit(value['source_url']);thread=parts.path.rsplit('/c/',1)[-1]
    if (not UUID.fullmatch(identity) or value['question_id']!='QUESTION-'+identity
            or parts.scheme!='https' or parts.netloc!='chatgpt.com' or not UUID.fullmatch(thread)
            or '/c/' not in parts.path or parts.query or parts.fragment):raise ValueError('attachment conversation identity mismatch')
    stamp=datetime.fromisoformat(value['observed_at'].replace('Z','+00:00'))
    if stamp.tzinfo is None or stamp>datetime.now(timezone.utc):raise ValueError('invalid attachment observation time')
    if not isinstance(value['question'],str) or not value['question'].strip():raise ValueError('attachment has no original question')
    for name in ('natural_width','natural_height'):
        if type(value['image'][name]) is not int or not 0<value['image'][name]<=16384:raise ValueError('invalid original image dimensions')
    for name in ('x','y','width','height'):
        number=value['capture'][name]
        if type(number) is not int or number<(1 if name in {'width','height'} else 0):raise ValueError('invalid capture bounds')
    if value['version']=='history_attachment_observation_v2':
        count,index=value['attachment_count'],value['attachment_index']
        if (type(count) is not int or not 2<=count<=5 or type(index) is not int or not 0<=index<count
                or not isinstance(value['capture_group_id'],str) or not UUID.fullmatch(value['capture_group_id'])
                or not isinstance(value['attachment_id'],str) or not UUID.fullmatch(value['attachment_id'])):
            raise ValueError('invalid attachment group identity')
    elif any(name in value for name in ('capture_group_id','attachment_id','attachment_index','attachment_count')):
        raise ValueError('single attachment observation cannot declare a group')
    return thread


def collect_capture(log_path,call_id,*,root):
    """Read one explicitly selected CUA result, never browser profiles/downloads."""
    selected=None;authorized=False
    with log_path.open('rb') as stream:
        while True:
            offset=stream.tell();raw=stream.readline()
            if not raw:break
            try:event=json.loads(raw)
            except ValueError:continue
            payload=event.get('payload',{})
            if event.get('type')!='response_item' or payload.get('call_id')!=call_id:continue
            if payload.get('type')=='function_call':authorized=(payload.get('namespace'),payload.get('name'))==('mcp__cua_repl','js')
            if payload.get('type')=='function_call_output' and authorized:
                if selected is not None:raise ValueError('ambiguous attachment tool result')
                selected=(payload.get('output',[]),sha256(raw).hexdigest(),offset)
    if selected is None:raise ValueError('selected CUA attachment result was not found')
    outputs,record_sha,offset=selected;observations=[];images=[]
    for item in outputs:
        if item.get('type')=='input_text':
            for prefix,_ in VERSIONS.values():
                if item.get('text','').startswith(prefix):
                    observations.append((json.loads(item['text'][len(prefix):]),item['text'],prefix))
        if item.get('type')=='input_image':images.append(item['image_url'])
    if len(observations)!=1 or len(images)!=1:raise ValueError('attachment requires one observation and one returned image')
    observation,text,prefix=observations[0];validate_observation(observation)
    expected_prefix,wrapper_version=VERSIONS[observation['version']]
    if prefix!=expected_prefix:raise ValueError('attachment observation prefix/version mismatch')
    header,encoded=images[0].split(',',1)
    if header not in {'data:image/jpeg;base64','data:image/png;base64'} or len(encoded)>MAX_BYTES*4//3+4:raise ValueError('unsupported returned attachment image')
    raw=base64.b64decode(encoded,validate=True);info=image_info(raw)
    if header!='data:'+info['mime_type']+';base64' or (info['width'],info['height'])!=(observation['capture']['width'],observation['capture']['height']):raise ValueError('returned image does not match observation')
    directory=root/'visuals/assets';directory.mkdir(parents=True,exist_ok=True)
    path=directory/(info['sha256']+'.'+info['extension'])
    if path.exists():
        if path.read_bytes()!=raw:raise ValueError('existing attachment bytes changed')
    else:
        with path.open('xb') as stream:stream.write(raw)
    wrapper={'version':wrapper_version,'observation':observation,'asset':info,'original_output':text,
             'output_sha256':sha256(text.encode()).hexdigest(),'source_file':log_path.name,'source_record_sha256':record_sha,
             'byte_offset':offset,'tool_call_id':call_id}
    wrapper['content_digest']=digest(wrapper);atomic_write_json(root/'visuals/captures'/(wrapper['content_digest']+'.json'),wrapper)
    return wrapper


def asset_bytes(asset,*,root):
    if not SHA.fullmatch(asset['sha256']) or asset['extension'] not in {'jpg','png'}:raise ValueError('invalid local attachment identity')
    path=root/'visuals/assets'/(asset['sha256']+'.'+asset['extension'])
    if path.is_symlink():raise ValueError('attachment asset must be a local immutable file')
    with path.open('rb') as stream:raw=stream.read(MAX_BYTES+1)
    if image_info(raw)!=asset:raise ValueError('attachment bytes changed')
    return raw


def add_visuals(records,*,root):
    """Rebuild optional visuals from bound sidecars; ignore imported annotations.

    V1 remains single-image. V2 publishes only complete message-bound groups,
    each with its own observed index and stable attachment identity.
    """
    from research_history_prices import bound
    result=[{k:v for k,v in row.items() if k!='question_visuals'} for row in records]
    by_id=defaultdict(list);choices=defaultdict(list);groups=defaultdict(list)
    for row in result:by_id[row['id']].append(row)
    for path in sorted((root/'visuals/captures').glob('*.json')):
        value=bound(path)
        observation=value['observation'];thread=validate_observation(observation);text=value['original_output']
        prefix,version=VERSIONS[observation['version']]
        if value['version']!=version:raise ValueError('unexpected attachment wrapper')
        if text!=prefix+json.dumps(observation,separators=(',',':'),ensure_ascii=False) or sha256(text.encode()).hexdigest()!=value['output_sha256']:raise ValueError('original attachment observation changed')
        asset=value['asset'];asset_bytes(asset,root=root)
        if (asset['width'],asset['height'])!=(observation['capture']['width'],observation['capture']['height']):raise ValueError('attachment capture dimensions changed')
        matches=by_id[observation['question_id']]
        if len(matches)!=1:continue
        row=matches[0]
        count=observation.get('attachment_count',1)
        if row['kind']!='original_question' or row['question']!=observation['question'] or row.get('unavailable_attachments')!=count:continue
        if not any(s.get('thread_id')==thread and s.get('turn_id')==observation['source_message_id'] and s['kind'] in {'chatgpt','chatgpt_rendered'} for s in row['sources']):continue
        visual={'kind':'rendered_capture','sha256':asset['sha256'],'source_message_id':observation['source_message_id'],
                                  'source_thread_id':thread,'source_url':'https://chatgpt.com/c/'+thread,'captured_at':observation['observed_at'],
                                  'width':asset['width'],'height':asset['height'],'asset':asset,'capture_digest':value['content_digest'],
                                  'url':'/api/v1/workbench/history-assets/'+asset['sha256']}
        if observation['version']=='history_attachment_observation_v1':choices[row['id']].append([visual])
        else:
            visual.update({name:observation[name] for name in ('attachment_id','attachment_index','attachment_count')})
            groups[(row['id'],observation['capture_group_id'])].append(visual)
    latest=lambda visual:(datetime.fromisoformat(visual['captured_at'].replace('Z','+00:00')),visual['capture_digest'])
    for (identity,_),entries in groups.items():
        counts={v['attachment_count'] for v in entries}
        if len(counts)!=1:continue
        count=next(iter(counts));indexed=defaultdict(list)
        for visual in entries:indexed[visual['attachment_index']].append(visual)
        if set(indexed)!=set(range(count)):continue
        # A replay can update an image, but cannot silently change its identity.
        if any(len({v['attachment_id'] for v in values})!=1 for values in indexed.values()):continue
        selected=[max(indexed[i],key=latest) for i in range(count)]
        if len({v['attachment_id'] for v in selected})!=count:continue
        choices[identity].append(selected)
    for row in result:
        if choices[row['id']]:
            row['question_visuals']=max(choices[row['id']],key=lambda group:(max(latest(v)[0] for v in group),tuple(v['capture_digest'] for v in group)))
    return result


def main():
    import argparse
    from research_history import ROOT
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--log',type=Path,required=True);parser.add_argument('--call-id',required=True);args=parser.parse_args()
    value=collect_capture(args.log,args.call_id,root=ROOT)
    print(json.dumps({'capture_digest':value['content_digest'],'asset':value['asset']},ensure_ascii=False))


if __name__=='__main__':main()
