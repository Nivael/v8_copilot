"""Private, dated conversation history. Original questions never become fabricated runs."""
from collections import defaultdict
from datetime import date,datetime,timedelta,timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from settings import DATA_ROOT
from research_history_reviews import argument_review_claimed,freeze_review,resolve_review

ROOT=DATA_ROOT/'local_data/v8_copilot/research_history'
ALIASES={'沐邦':'603398.SH','宝馨':'002514.SZ','准油':'002207.SZ','联翔':'603272.SH','美芝':'002856.SZ',
         '南都':'300068.SZ','仕净':'301030.SZ','同德':'002360.SZ','闻泰':'600745.SH','榕泰':'600589.SH',
         '通脉':'603559.SH','金鸿':'000669.SZ','联光':'600363.SH','联创光电':'600363.SH','威领':'002667.SZ',
         '思科瑞':'688053.SH','亚光':'300123.SZ','金顶':'600678.SH','得润':'002055.SZ','景谷':'600265.SH',
         '帅电':'605336.SH','帅丰':'605336.SH','源杰':'688498.SH','华丰科技':'688629.SH','华峰测控':'688200.SH',
         '正邦':'002157.SZ','东易':'002713.SZ','新研':'300159.SZ','芯原':'688521.SH','中微':'688012.SH',
         '金刚':'300093.SZ','瑞和':'002620.SZ','正平':'603843.SH'}
TOPICS={'重整与节点':('重整','法院','路条','招募','投资人','财投','产投','债权','债转股'),
        '控制权与股权':('股权','拍卖','控制权','实控人','收购'),
        '估值与摊薄':('估值','市值','转增','摊薄','定价','股本'),
        '财报与监管':('财报','营收','净资产','年报','中报','三季','摘星','摘帽','立案','谴责','退市'),
        '大盘与ST整体':('大盘','ETF','etf','板块','流动性','量能','风险偏好'),
        '短线量价':('开板','涨停','跌停','高开','低走','做T','做t','盘面','洗盘','主力','走势','砸'),
        '交易决策与心态':('持仓','仓位','割肉','成本','买','卖','回本','进去','策略')}


def instant(value):
    stamp=datetime.fromtimestamp(value,timezone.utc) if isinstance(value,(int,float)) else datetime.fromisoformat(value.replace('Z','+00:00'))
    if stamp.tzinfo is None:raise ValueError('history date has no timezone')
    return stamp


def question_day(record):
    if record.get('time_precision')=='range' and record.get('asked_at') is not None:raise ValueError('date range cannot also claim an exact question time')
    if record.get('asked_at') is not None:return instant(record['asked_at']).astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
    if record.get('time_precision')=='range':
        start=date.fromisoformat(record['asked_from']);end=date.fromisoformat(record['asked_through'])
        if start>=end or record.get('asked_on') is not None:raise ValueError('invalid original question date range')
        return None
    if record.get('time_precision')!='day':raise ValueError('question has neither timestamp nor verified date')
    return date.fromisoformat(record['asked_on']).isoformat()


def question_order(record):
    # A group marker orders a dated follow-up; it is never its displayed ask time.
    day=question_day(record)
    if day is None:
        lower=record.get('source_date_bounds',{}).get('not_before') or record['asked_from']+'T00:00:00+08:00'
        if instant(lower).astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()!=record['asked_from']:raise ValueError('question range lower bound mismatch')
        return instant(lower),record.get('source_group_offset',0)
    stamp=record.get('asked_at') or record.get('source_date_marker') or record.get('source_date_bounds',{}).get('not_before') or day+'T00:00:00+08:00'
    if instant(stamp).astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()!=day:raise ValueError('question date group mismatch')
    return instant(stamp),record.get('source_group_offset',0)


def question_digest(record):
    basis={'asked_at':record.get('asked_at'),'question':record['question'],'answers':record['answers']}
    if record.get('asked_at') is None:
        day=question_day(record);basis.update(asked_on=day,time_precision='range' if day is None else 'day')
        if day is None:basis.update(asked_from=record['asked_from'],asked_through=record['asked_through'])
    if record.get('question_context'):
        basis['question_context']={k:record['question_context'][k] for k in ('version','question_id','question','asked_on','source_url')}
    if record.get('question_visuals'):
        basis['question_visuals']=[{**{k:v[k] for k in ('kind','sha256','source_message_id','source_thread_id')},
                                   **{k:v[k] for k in ('attachment_id','attachment_index','attachment_count') if k in v}}
                                  for v in record['question_visuals']]
    return digest(basis)


def add_question_contexts(records,captured):
    """Quote an independently captured group opener, never a guessed nearby ask."""
    result=[{k:v for k,v in row.items() if k!='question_context'} for row in records]
    by_id=defaultdict(list);owners=defaultdict(list);candidates=defaultdict(dict)
    def threads(row):return {s['thread_id'] for s in row['sources'] if s['kind'] in {'chatgpt','chatgpt_rendered'} and s.get('thread_id')}
    for row in result:
        if row['kind']!='original_question':continue
        ids={row['id'],*(o['id'] for o in row.get('occurrences',[])),*('QUESTION-'+s['turn_id'] for s in row['sources'] if s['kind'] in {'chatgpt','chatgpt_rendered'} and s.get('turn_id'))}
        for identity in ids:by_id[identity].append(row)
    for row in captured:
        if row.get('asked_at') and row.get('source_date_owner_id')==row['id'].removeprefix('QUESTION-') and row.get('source_group_offset')==0:
            owners[row['id']].append(row)
    for child in captured:
        matches=by_id.get(child['id'],[]);owner_id='QUESTION-'+str(child.get('source_date_owner_id'))
        parents=by_id.get(owner_id,[])
        if len(matches)!=1 or len(parents)!=1:continue
        row,parent=matches[0],parents[0]
        if (row is parent or len(row['question'])>40 or row.get('asked_at') is not None or child.get('asked_at') is not None
                or child.get('source_group_offset',0)<=0 or row.get('source_date_owner_id')!=child.get('source_date_owner_id')
                or row.get('source_group_offset')!=child.get('source_group_offset')
                or not row.get('source_date_marker') or instant(row['source_date_marker'])!=instant(child['source_date_marker'])
                or row['question']!=child['question'] or question_day(row)!=question_day(child)):
            continue
        for opener in owners.get(owner_id,[]):
            shared=threads(child)&threads(opener)&threads(row)&threads(parent)
            if (len(shared)!=1 or parent['question']!=opener['question'] or question_day(parent)!=question_day(child)
                    or not parent.get('asked_at') or instant(parent['asked_at'])!=instant(opener['asked_at'])
                    or instant(child['source_date_marker'])!=instant(opener['asked_at'])):
                continue
            thread=next(iter(shared))
            context={'version':'history_question_context_v1','question_id':parent['id'],'question':parent['question'],
                     'asked_on':question_day(parent),'source_url':'https://chatgpt.com/c/'+thread}
            key=digest(context);item=candidates[row['id']].setdefault(key,{**context,'source_capture_digests':set()})
            item['source_capture_digests'].update(s['capture_digest'] for r in (child,opener) for s in r['sources'] if s.get('capture_digest'))
    for row in result:
        choices=candidates[row['id']]
        if len(choices)==1:
            context=next(iter(choices.values()));row['question_context']={**context,'source_capture_digests':sorted(context['source_capture_digests'])}
    return result


def prepare_history_records(imported,*,root=ROOT):
    from research_history_captures import import_capture_files
    from research_history_visuals import add_visuals
    captured,_=import_capture_files(root/'captures/cua_v1',imported.get('stock_names',{}))
    return mark_answer_bindings(add_visuals(add_question_contexts(imported['records'],captured),root=root))


def mark_answer_bindings(records):
    groups=defaultdict(list)
    for record in records:
        for answer in record['answers']:
            if record['kind']=='original_question' and answer.get('completed_at'):
                groups[(answer.get('source_thread_id'),str(answer['completed_at']),answer['text'])].append((record['id'],answer))
    for group in groups.values():
        ids=sorted({identity for identity,_ in group})
        if len(ids)>1:
            for _,answer in group:answer['binding']='shared_turn_answer';answer['source_question_ids']=ids
    return records


def clean_question(value):
    text=value.strip()
    if text.startswith(('# AGENTS.md instructions','<codex_internal_context','<external_codex_apps_open_page>','<recommended_plugins>','<environment_context>','<turn_aborted>')):return ''
    if text.startswith('你是 ST Research 项目的独立研究窗口'):return ''
    if '## My request:' in text:text=text.split('## My request:',1)[1].strip()
    elif text.startswith('<in-app-browser-context'):return ''
    return text


def mentioned(text,known):
    result={symbol for alias,symbol in ALIASES.items() if alias in text and symbol in known}
    for code in re.findall(r'(?<!\d)[036]\d{5}(?!\d)',text):
        result.update(symbol for symbol in (code+'.SH',code+'.SZ') if symbol in known)
    if isinstance(known,dict):
        for symbol,name in known.items():
            bare=re.sub(r'^\*?ST\s*','',name,flags=re.I)
            if name in text or len(bare)>=3 and bare in text:result.add(symbol)
    if re.search(r'(?:\*?ST\s*发展|仕净[、，].*发展|^发展[、，：])',text,re.I):result.add('000838.SZ')
    return sorted(result)


def judgment(text):
    parts=[p.strip() for p in text.split('\n\n') if p.strip() and not p.strip().startswith(('#','|','![','```'))]
    return (parts[0] if parts else text.strip())[:500]


def import_pages(directory,known):
    """Only actual user/agent messages; preserve branches and date provenance."""
    records={};sources=[]
    for path in sorted(directory.glob('chatgpt-*.json')):
        raw=path.read_bytes();page=json.loads(raw);thread=page['thread'];previous=[]
        sources.append({'kind':'chatgpt','thread_id':thread['id'],'title':thread['title'],'capture_file':path.name,'sha256':sha256(raw).hexdigest(),
                        'reported_has_more':page['page']['hasMore'],'capture_scope':'tool_returned_turns; earlier UI messages may exist'})
        context=mentioned(thread['title'],known)
        for turn in sorted(page['turns'],key=lambda t:t['startedAt']):
            users=[i for i in turn['items'] if i['type']=='userMessage'];answers=[i for i in turn['items'] if i['type']=='agentMessage']
            for user in users:
                text=clean_question('\n'.join(c.get('text','') for c in user.get('content',[]) if c.get('type')=='text'))
                if not text:continue
                symbols=mentioned(text,known);scope_kind='explicit'
                if not symbols:symbols=context or previous;scope_kind='conversation_context' if symbols else 'market_or_method'
                previous=symbols or previous
                key=user['id'];stamp=instant(turn['startedAt']).isoformat()
                answer=answers[-1].get('text','') if answers else None
                record=records.setdefault(key,{'id':'QUESTION-'+key,'asked_at':stamp,'date_source':'original_chat_turn','question':text,
                         'original_question':text,'kind':'original_question','symbols':symbols,'scope_kind':scope_kind,
                         'categories':[k for k,terms in TOPICS.items() if any(t in text for t in terms)] or ['研究方法'],
                         'answers':[],'sources':[]})
                record['symbols']=sorted(set(record['symbols'])|set(symbols))
                record['sources'].append({'kind':'chatgpt','thread_id':thread['id'],'title':thread['title'],'turn_id':turn['id'],
                                          'url':'https://chatgpt.com/c/'+thread['id'],'capture_sha256':sha256(raw).hexdigest(),
                                          'asked_at':stamp,'time_precision':'instant'})
                if answer and not any(a['text']==answer for a in record['answers']):
                    record['answers'].append({'text':answer,'summary':judgment(answer),'completed_at':turn.get('completedAt'),
                                              'truncated':len(answer)>=20000,'source_thread_id':thread['id']})
    return list(records.values()),sources


def import_codex_capture(path,known):
    value=json.loads(path.read_text());records=[]
    independent={'019ff3be-eaf4-7b82-98ed-f46b637ed9ad','019ff3bf-2e42-7d31-8102-14e0e4ef01dd','01a07cbe-a50a-79c0-93b2-08fb273f9544','01a0b252-b3f0-7262-adfe-ff6d48e6536d','01a07f46-e34d-7dd3-88ff-60db7ad77d19','01a1a7d3-8c8e-7e12-bdfd-bd5344eb58a7'}
    previous={}
    for record in sorted(value['records'],key=lambda r:r['asked_at']):
        text=clean_question(record['question']);thread=record['occurrences'][0]['thread_id']
        if not text or text.startswith(('<','hi 我刚','你把现在的工作')):continue
        symbols=mentioned(text,known)
        if thread not in independent:
            if any(t in text for t in ('github','Python importer','commander','代码','脚本','架构','prd','todo','PRD')) or not symbols:continue
        if not symbols:symbols=previous.get(thread,[])
        if len(text)<5:continue
        previous[thread]=symbols
        records.append({'id':record['id'],'asked_at':record['asked_at'],'date_source':'original_codex_message','question':text,'original_question':record['question'],
                        'kind':'original_question','symbols':symbols,'scope_kind':'explicit' if mentioned(text,known) else 'conversation_context',
                        'categories':[k for k,terms in TOPICS.items() if any(t in text for t in terms)] or ['研究方法'],
                        'answers':[{'text':a['text'],'summary':judgment(a['text']),'completed_at':a['completed_at'],'truncated':False,'source_thread_id':a['thread_id']} for a in record['answers']],
                        'sources':[{'kind':'codex','thread_id':o['thread_id'],'turn_id':o['turn_id'],'message_id':o['message_id'],'line':o['line'],'source_sha256':o['source_sha256'],'record_sha256':o['record_sha256']} for o in record['occurrences']]})
    return records,value['sources']


def import_ledger(path,known):
    import sqlite3
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row;rows=[dict(r) for r in db.execute('select run_id,question_text,object_refs_json,final_answer,completed_at,thread_id,turn_id from research_runs order by completed_at')]
    return [{'id':r['run_id'],'asked_at':r['completed_at'],'date_source':'saved_research_time_not_original_ask','question':r['question_text'],
             'kind':'saved_research','symbols':mentioned(r['object_refs_json']+' '+r['question_text'],known),'scope_kind':'research_record',
             'categories':[k for k,terms in TOPICS.items() if any(t in r['question_text'] for t in terms)] or ['研究方法'],
             'answers':[{'text':r['final_answer'],'summary':judgment(r['final_answer']),'completed_at':r['completed_at'],'truncated':False,'source_thread_id':r['thread_id']}],
             'sources':[{'kind':'research_ledger','run_id':r['run_id'],'thread_id':r['thread_id'],'turn_id':r['turn_id']}]} for r in rows]


def deduplicate(records):
    """Exact retries/branch copies only. Different wording is not silently merged."""
    result=[];seen={}
    for record in sorted(records,key=question_order):
        day=question_day(record)
        # Identical words inside an uncertain date range do not prove a retry.
        key=(day if day is not None else ('range',record['id']),re.sub(r'\s+','',record['question']),record['kind'])
        if key in seen:
            old=seen[key];old['sources'].extend(record['sources'])
            occurrence=lambda r:{'id':r['id'],'asked_at':r.get('asked_at'),'asked_on':question_day(r),'time_precision':r.get('time_precision','instant'),'source_date_marker':r.get('source_date_marker')}
            old['occurrences']=[*old.get('occurrences',[occurrence(old)]),*record.get('occurrences',[occurrence(record)])]
            for answer in record['answers']:
                if not any(a['text']==answer['text'] for a in old['answers']):old['answers'].append(answer)
            old['retry_or_branch_count']=old.get('retry_or_branch_count',1)+1
        else:seen[key]=record;result.append(record)
    return result


def normalize_after(points,anchor_date):
    anchor=next((p for p in points if p['date']==anchor_date and p['level'] is not None),None)
    if anchor is None:return []
    return [{'date':p['date'],'value':p['value'],'level':p['level']/anchor['level']*100 if p['level'] is not None else None} for p in points if p['date']>=anchor_date]


def outcome(points,anchor_date,calendar):
    by_day={p['date']:p for p in points};anchor=by_day.get(anchor_date);result={}
    for label,count in [('one_day',1),('five_day',5),('twenty_day',20),('sixty_day',60),('latest',None)]:
        index=calendar.index(anchor_date);end=calendar[-1] if count is None else calendar[index+count] if index+count<len(calendar) else None
        last=by_day.get(end)
        result[label]={'date':end,'change_pct':(last['level']/anchor['level']-1)*100 if end!=anchor_date and anchor and last and anchor['level'] is not None and last['level'] is not None else None}
    return result


def comparison_basis(record,points):
    day=question_day(record);asked=instant(record['asked_at']).astimezone(ZoneInfo('Asia/Shanghai')) if record.get('asked_at') else None
    if day is None:
        return {'asked_on':None,'anchor_date':None,'answer_completed_at':None,'anchor_basis':'unresolved_question_day',
                'basis_note':f"原页面只确认提问在{record['asked_from']}至{record['asked_through']}之间，未指定某一天，不连接收益或评估盘中指令。"}
    completed=[instant(a['completed_at']).astimezone(ZoneInfo('Asia/Shanghai')) for a in record['answers'] if a.get('completed_at') is not None]
    finished=max(completed) if completed else None
    effective=max(asked,finished) if asked and finished else asked
    basis_day=effective.date().isoformat() if effective else day
    cutoff=basis_day if effective is None or effective.hour>=15 else (effective.date()-timedelta(days=1)).isoformat()
    candidates=[p for p in points if p['date']<=cutoff and p['level'] is not None]
    basis={'asked_on':day,'anchor_date':candidates[-1]['date'] if candidates else None,
           'answer_completed_at':finished.isoformat() if finished else None,
           'anchor_basis':'original_answer_time' if finished and asked and finished>asked else 'question_time',
           'basis_note':'比较基准采用提问及原回答完成两者较晚时点，取当时已完成的最近有效收盘；15点前不使用尚未完成的当日收盘价。日线不代表实际成交价。'}
    if asked is None:
        basis.update(anchor_basis='date_only_retrospective_close',basis_note='原页面只确认提问日期，未提供这条追问的独立时刻；以该日或此前最近有效收盘作事后日线比较，不认定当时可见或可成交，也不据此验证盘中指令。')
    return basis


def review_anchor(record,review,paths):
    if argument_review_claimed(review):return None
    scope=record['symbols'];focus=review.get('focused_symbol') or (scope[0] if len(scope)==1 else 'market' if not scope else None)
    points=paths['market'] if focus=='market' else paths['stocks'].get(focus,{}).get('points',[])
    return comparison_basis(record,points)['anchor_date']


def range_chart_context(record,paths,symbol):
    """A common visual reference before the uncertain ask, never a return anchor."""
    if record.get('time_precision')!='range':return None
    question_day(record)
    if not any(day>=record['asked_from'] for day in paths['calendar']):return None
    series=[paths['market'],paths['st']]
    if symbol!='market':series.append(paths['stocks'][symbol]['points'])
    levels=[{p['date']:p['level'] for p in points} for points in series]
    def valid(day):
        return all(isinstance(value:=points.get(day),(int,float)) and isfinite(value) and value>0 for points in levels)
    reference=next((day for day in reversed(paths['calendar']) if day<record['asked_from'] and valid(day)),None)
    return {'kind':'pre_range_common_close','reference_date':reference} if reference else None


def assemble(records,paths,*,reviews=None):
    calendar=paths['calendar'];stocks=[];details={};reviews=reviews or {}
    scopes={**paths['stocks'],'market':{'name':'大盘、ST与待定位问题','points':paths['market']}}
    for symbol,stock in scopes.items():
        history=[r for r in records if (symbol in r['symbols'] if symbol!='market' else not r['symbols'])]
        if not history:continue
        rows=[]
        for record in history:
            item={**record,**comparison_basis(record,stock['points'])};anchor=item['anchor_date']
            item.pop('range_context',None)
            if record.get('time_precision')=='range':item['range_context']=range_chart_context(record,paths,symbol)
            if anchor:
                series=[('stock',stock['name'],stock['points']),('market','中证全指',paths['market']),('st',paths['st_name'],paths['st'])]
                item['outcomes']={key:outcome(points,anchor,calendar) for key,_,points in series}
            else:item['outcomes']={}
            item['question_digest']=question_digest(record)
            review=reviews.get(record['id'])
            item.update(resolve_review(review,record,paths,item['question_digest'],review_anchor(record,review,paths) if review else None))
            if review:
                focus=review.get('focused_symbol')
                item['review_focused_name']=paths['stocks'].get(focus,{}).get('name','大盘与ST' if focus=='market' else None)
            rows.append(item)
        rows.sort(key=question_order)
        stats={'original_questions':sum(r['kind']=='original_question' for r in rows),'saved_research':sum(r['kind']=='saved_research' for r in rows),'reviewed':sum(bool(r['review']) for r in rows)}
        stocks.append({'symbol':symbol,'name':stock['name'],**stats,'first_asked_on':rows[0]['asked_on'],'last_asked_on':rows[-1]['asked_on']})
        details[symbol]={'availability':'available','symbol':symbol,'name':stock['name'],'as_of':paths['calendar'][-1],'questions':rows,
                         'chart_sources':{**({'stock':stock['points']} if symbol!='market' else {}),'market':paths['market'],'st':paths['st']},'st_name':paths['st_name'],
                         'st_note':paths['st_note'],'stock_history_note':stock.get('history_note'),
                         'source_urls':{'stock':'https://www.sse.com.cn/' if symbol.endswith('.SH') else 'https://www.szse.cn/market/stock/','market':'https://www.csindex.com.cn/#/indices/family/detail?indexCode=000985','st':paths['st_source_url'],**({'stock_history':stock['history_source_url']} if stock.get('history_source_url') else {})},
                         'stats':stats}
    stocks.sort(key=lambda r:(r['symbol']!='002514.SZ',-r['original_questions'],r['symbol']))
    unique={r['id']:r for r in records};return {'stocks':stocks,'details':details,'unique':unique}


def publish(imported,*,root=ROOT):
    from research_history_prices import bound
    paths=bound(root/'price_paths/current.json');records=prepare_history_records(imported,root=root)
    if paths.get('processor_digest')!=sha256(Path(__file__).with_name('research_history_prices.py').read_bytes()).hexdigest():raise ValueError('history price processor changed; rebuild paths before publishing')
    review_path=root/'reviews.json';reviews=json.loads(review_path.read_text()) if review_path.exists() else {}
    result=assemble(records,paths['data'],reviews=reviews)
    coverage={'original_questions':sum(r['kind']=='original_question' for r in result['unique'].values()),
              'saved_research':sum(r['kind']=='saved_research' for r in result['unique'].values()),
              'reviewed_questions':len({r['id'] for d in result['details'].values() for r in d['questions'] if r['review']}),
              'stocks':len(result['stocks'])-sum(s['symbol']=='market' for s in result['stocks']),'source_note':'已找回的ChatGPT、Codex原问题及保存研究；部分长聊天的更早消息仍待补齐，保存研究的日期不冒充原提问时间。'}
    coverage['date_range_questions']=sum(r.get('time_precision')=='range' for r in result['unique'].values())
    coverage['argument_only_reviews']=len({r['id'] for d in result['details'].values() for r in d['questions'] if r['review_status']=='argument_only'})
    if coverage['date_range_questions']:coverage['source_note']+=f"其中{coverage['date_range_questions']}条只确认日期范围，保留原文，暂不选定某一天计算收益。"
    source_manifest={'version':'research_history_import_v1','sources':imported['sources'],'records':records};source_manifest['content_digest']=digest(source_manifest)
    atomic_write_json(root/'imports'/(source_manifest['content_digest']+'.json'),source_manifest)
    body={'version':'research_history_reading_v1','processor_digest':processor_digest(),'checked_at':datetime.now(timezone.utc).isoformat(),'as_of':paths['data']['calendar'][-1],
          'source_digest':source_manifest['content_digest'],'price_digest':paths['content_digest'],
          'inventory':{'availability':'available','as_of':paths['data']['calendar'][-1],'stocks':result['stocks'],'coverage':coverage,'categories':list(TOPICS)},
          'visual_assets':{v['sha256']:v['asset'] for r in records for v in r.get('question_visuals',[])},
          'details':result['details'],'general_questions':[r for r in records if not r['symbols']]}
    body['content_digest']=digest(body);atomic_write_json(root/'snapshots'/(body['content_digest']+'.json'),body);atomic_write_json(root/'current.json',body)
    return body


def processor_digest():
    return digest({name:sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ['research_history.py','research_history_prices.py','research_history_captures.py','research_history_reviews.py','research_history_visuals.py']})


def freeze_reviews(imported,*,root=ROOT):
    """Guarded metadata migration; never re-dates or extends an existing assessment."""
    from research_history_prices import bound
    packet=bound(root/'price_paths/current.json')
    if packet.get('processor_digest')!=sha256(Path(__file__).with_name('research_history_prices.py').read_bytes()).hexdigest():raise ValueError('history price processor changed')
    paths=packet['data'];records={r['id']:r for r in prepare_history_records(imported,root=root)}
    reviews=json.loads((root/'reviews.json').read_text());frozen={}
    for identity,review in reviews.items():
        record=records.get(identity)
        if not record:raise ValueError('review original question is missing')
        anchor=review_anchor(record,review,paths)
        state=resolve_review(review,record,paths,question_digest(record),anchor)
        if not state['review']:raise ValueError('review binding changed; substantive re-evaluation required')
        frozen[identity]=review if review.get('review_binding_version') else freeze_review(review,record,paths,anchor)
    # Complete all validation before the one atomic write; published snapshots retain old bytes.
    atomic_write_json(root/'reviews.json',frozen)
    return {'frozen_reviews':len(frozen),'as_of':paths['calendar'][-1]}


def load(symbol=None,*,root=ROOT):
    from research_history_prices import bound
    try:
        value=bound(root/'current.json')
        if value['version']!='research_history_reading_v1' or value['processor_digest']!=processor_digest():return {'availability':'updating'}
        return value['details'].get(symbol,{'availability':'not_found'}) if symbol else value['inventory']
    except (OSError,KeyError,ValueError,TypeError):return {'availability':'updating'}


def load_visual(identity,*,root=ROOT):
    from research_history_prices import bound
    from research_history_visuals import SHA,asset_bytes
    if not SHA.fullmatch(identity):return None
    try:
        packet=bound(root/'current.json')
        if packet['version']!='research_history_reading_v1' or packet['processor_digest']!=processor_digest():return None
        asset=packet.get('visual_assets',{}).get(identity)
        if not asset or asset['sha256']!=identity:return None
        return asset_bytes(asset,root=root),asset['mime_type']
    except (OSError,KeyError,ValueError,TypeError):return None


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--publish-import',type=Path);action.add_argument('--freeze-reviews-import',type=Path);args=parser.parse_args()
    if args.freeze_reviews_import:result=freeze_reviews(json.loads(args.freeze_reviews_import.read_text()))
    else:
        value=publish(json.loads(args.publish_import.read_text()));result={'digest':value['content_digest'],**value['inventory']['coverage']}
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
