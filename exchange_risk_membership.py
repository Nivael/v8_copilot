"""Explicit exchange risk-list observations; never backfill historical membership."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html import unescape
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from settings import DATA_ROOT

VERSION = 'exchange_risk_list_observation_v1'
OUTPUT = DATA_ROOT/'local_data/v8_copilot/market_risk/exchange_risk_membership'
SSE_API = 'https://query.sse.com.cn/commonSoaQuery.do'
SZSE_API = 'http://www.szse.cn/api/report/ShowReport/data'
SSE_JS = 'https://www.sse.com.cn/xhtml/home/2021public/querySearch/search_listedCompanyInfo_2021.js'
SZSE_PAGE = 'http://www.szse.cn/disclosure/listed/warn/index.html'
PROOFS = {
    'sse_definition': (SSE_JS, '4c224fa9cd55a5eba26e06ef122b05d1b55e1fd39f2fc13a28bd30db8c4bc0d7'),
    'szse_definition': (SZSE_PAGE, '822ce1b18a6cf6a6bfa119f56089856321ba51423788e19f8f8d83f1a8251c22'),
}
GROUPS = {
    'sse_main_risk': {'venue':'SSE','board':'main','kind':'risk_warning','url':'https://www.sse.com.cn/disclosure/listedinfo/riskplate/',
                      'params':{'sqlId':'PL_SSGSXX_FXJSBGPLB','domesticIndicator':'S','productType':'0'}},
    'sse_main_delisting': {'venue':'SSE','board':'main','kind':'delisting','url':'https://www.sse.com.cn/disclosure/listedinfo/riskplate/',
                           'params':{'sqlId':'PL_SSGSXX_FXJSBGPLB','domesticIndicator':'P','productType':'0'}},
    'sse_star_risk': {'venue':'SSE','board':'star','kind':'risk_warning','url':'https://www.sse.com.cn/disclosure/listedinfo/starriskplate/',
                      'params':{'sqlId':'SSE_PL_SSGSXX_KCBFXTS_L','type':'0'}},
    'sse_star_delisting': {'venue':'SSE','board':'star','kind':'delisting','url':'https://www.sse.com.cn/disclosure/listedinfo/starriskplate/',
                           'params':{'sqlId':'SSE_PL_SSGSXX_KCBFXTS_L','type':'1'}},
    'szse_risk': {'venue':'SZSE','board':'main_and_gem','kind':'risk_warning','url':SZSE_PAGE,'tab':'tab1'},
    'szse_delisting': {'venue':'SZSE','board':'main_and_gem','kind':'delisting','url':SZSE_PAGE,'tab':'tab2'},
}
KIND_NAMES = {'risk_warning':'风险警示股票','delisting':'退市整理股票'}


def processor_digest():
    return digest({name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                   for name in (Path(__file__).name,'canonical_json.py')})


PROCESSOR = processor_digest()


def integer(value, *, minimum=0, maximum=1000):
    if isinstance(value,bool) or not isinstance(value,int) or not minimum <= value <= maximum:
        raise ValueError('invalid list count/page')
    return value


def local_day(value):
    return value.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()


def parameters(group, page=1):
    item = GROUPS[group]
    return item.get('params') or {'SHOWTYPE':'JSON','CATALOGID':'fxjsb','TABKEY':item['tab'],'PAGENO':str(page)}


def definition_fragment(key, text):
    if key == 'sse_definition':
        if text.count('var riskplate = {')!=1 or text.count('var kcbriskplate = {')!=1 or text.count('//科创板风险警示end')!=1:
            raise ValueError('ambiguous SSE risk definition')
        start = text.index('var riskplate = {')
        marker = '//科创板风险警示end'
        return text[start:text.index(marker,start)+len(marker)]
    matches = re.findall(r'<div class="report-container" data-s-catalog-id="fxjsb" data-s-data-url=""></div>',text)
    if len(matches) != 1: raise ValueError('changed SZSE risk catalog')
    return matches[0]


def normalize_row(group, code, name):
    item = GROUPS[group]
    if not isinstance(code,str) or not isinstance(name,str): raise ValueError('invalid security identity')
    if item['venue'] == 'SZSE':
        # Do not execute downloaded markup or use it as a navigable link.
        match = re.fullmatch(r"<a href=['\"]https?://www\.szse\.cn/certificate/individual/index\.html\?code="+re.escape(code)+r"['\"] target=['\"]_blank['\"]><u>([^<>]+)</u></a>",name)
        if not match: raise ValueError('unreviewed SZSE name markup/identity')
        name = unescape(match[1])
    if not name.strip() or len(name)>40 or re.search(r'[<>\x00-\x1f]',name): raise ValueError('invalid security name')
    a = (r'60\d{4}' if item['board']=='main' else r'688\d{3}') if item['venue']=='SSE' else r'[03]\d{5}'
    b = r'900\d{3}' if item['venue']=='SSE' and item['board']=='main' else r'200\d{3}' if item['venue']=='SZSE' else r'(?!)'
    share_class = 'A' if re.fullmatch(a,code) else 'B' if re.fullmatch(b,code) else None
    if share_class is None: raise ValueError('undeclared security scope')
    return {'ts_code':code+('.SH' if item['venue']=='SSE' else '.SZ'),'name':name.strip(),
            'share_class':share_class,'kind':item['kind'],'venue':item['venue'],'group':group}


def sse_table(group, data):
    item = GROUPS[group]; rows = data['result']; page = data['pageHelp']
    total = integer(page['total']); nonempty = bool(total)
    if (data['sqlId']!=item['params']['sqlId'] or data['actionErrors'] or data['fieldErrors'] or data['actionMessages']
        or data['isPagination']!='false' or data['queryDate']!='' or page['data']!=rows
        or integer(page['pageNo'],minimum=1)!=1 or integer(page['pageCount'])!=int(nonempty)
        or integer(page['pageSize'])!=total or integer(page['pageSizeWithOutLimit'])!=total or len(rows)!=total
        or item['board']=='star' and data['type']!=item['params']['type']):
        raise ValueError('incomplete or mismatched SSE table')
    keys = ('INSTRUMENT_ID','INSTRUMENT_SHORT') if item['board']=='main' else ('secCode','secNameCn')
    return [normalize_row(group,row[keys[0]],row[keys[1]]) for row in rows]


def szse_table(group, data, page, observed_on):
    item = GROUPS[group]
    # Other tabs are unloaded placeholders even when their counters say zero.
    selected = [row for row in data if row['metadata']['tabkey']==item['tab']]
    if len(selected)!=1: raise ValueError('selected SZSE tab missing/duplicated')
    table = selected[0]; meta = table['metadata']; rows = table['data']
    total = integer(meta['recordcount']); size = integer(meta['pagesize'],minimum=1,maximum=100)
    pages = integer(meta['pagecount']); expected_pages = (total+size-1)//size
    if (meta['catalogid']!='fxjsb' or meta['name']!=KIND_NAMES[item['kind']]
        or meta['cols']!={'zqdm':'证券代码','gsjc':'证券简称'} or meta['conditions']!=[]
        or meta['subname'].strip()!=observed_on or integer(meta['pageno'],minimum=1)!=page
        or pages!=expected_pages or not 1 <= page <= max(1,pages)
        or len(rows)!=max(0,min(size,total-(page-1)*size))):
        raise ValueError('incomplete or misdated selected SZSE tab')
    return [normalize_row(group,row['zqdm'],row['gsjc']) for row in rows], (total,pages,size)


def read_response(directory, ref, *, url, params, started, completed):
    requested = url+('?' + urlencode(params) if params else '')
    observed = datetime.fromisoformat(ref['observed_at'])
    if (ref['url']!=url or ref['params']!=params or ref['final_url']!=requested or observed.tzinfo is None
        or not started <= observed <= completed or local_day(observed)!=local_day(started)):
        raise ValueError('request/time binding changed')
    sha = ref['response_sha256']
    if not re.fullmatch(r'[0-9a-f]{64}',sha): raise ValueError('invalid response digest')
    path = directory/'responses'/(sha+'.raw')
    if not 0<path.stat().st_size<=2_000_000: raise ValueError('oversized/empty response file')
    raw = path.read_bytes()
    if not 0<len(raw)<=2_000_000 or len(raw)!=integer(ref['bytes'],minimum=1,maximum=2_000_000) or hashlib.sha256(raw).hexdigest()!=sha:
        raise ValueError('response bytes changed')
    return raw.decode('utf-8')


def project(raw, directory, now):
    started = datetime.fromisoformat(raw['started_at']); completed = datetime.fromisoformat(raw['completed_at'])
    if (started.tzinfo is None or completed.tzinfo is None or not started<=completed<=now
        or local_day(started)!=local_day(completed) or raw['observed_on']!=local_day(started)):
        raise ValueError('invalid observation dates')
    if raw.get('reparsed_at'):
        replayed=datetime.fromisoformat(raw['reparsed_at'])
        if replayed.tzinfo is None or not completed<=replayed<=now: raise ValueError('invalid replay time')
    refs = raw['responses']; used = set(); rows=[]; groups=[]
    def body(key, url, params):
        matches=[(index,ref) for index,ref in enumerate(refs) if ref['key']==key]
        if len(matches)!=1: raise ValueError('missing/duplicate source page')
        index,ref=matches[0];used.add(index)
        return read_response(directory,ref,url=url,params=params,started=started,completed=completed)
    for key,(url,expected) in PROOFS.items():
        fragment=definition_fragment(key,body(key,url,{}))
        if hashlib.sha256(fragment.encode()).hexdigest()!=expected: raise ValueError('source definition changed')
    for key,item in GROUPS.items():
        if item['venue']=='SSE':
            records=sse_table(key,json.loads(body(key,SSE_API,parameters(key))))
            pages=1;source_date=None
        else:
            records,meta=szse_table(key,json.loads(body(key+':1',SZSE_API,parameters(key))),1,raw['observed_on'])
            for page in range(2,meta[1]+1):
                additional,next_meta=szse_table(key,json.loads(body(key+':'+str(page),SZSE_API,parameters(key,page))),page,raw['observed_on'])
                if next_meta!=meta: raise ValueError('SZSE table changed between pages')
                records.extend(additional)
            if len(records)!=meta[0]: raise ValueError('incomplete selected SZSE table')
            pages=max(1,meta[1]);source_date=raw['observed_on']
        rows.extend(records)
        groups.append({'group':key,'venue':item['venue'],'board':item['board'],'kind':item['kind'],'source_url':item['url'],
                       'source_as_of':source_date,'source_rows':len(records),'pages_read':pages,
                       'a_shares':sum(row['share_class']=='A' for row in records),'b_shares':sum(row['share_class']=='B' for row in records)})
    if len(used)!=len(refs) or len({row['ts_code'] for row in rows})!=len(rows): raise ValueError('extra response or duplicate/overlapping security')
    if not rows or not any(row['kind']=='risk_warning' and row['share_class']=='A' for row in rows): raise ValueError('empty observation')
    return {'availability':'observed','observed_on':raw['observed_on'],'started_at':raw['started_at'],'completed_at':raw['completed_at'],
            'reparsed_at':raw.get('reparsed_at'),
            'is_today_observation':local_day(now)==raw['observed_on'],'common_source_as_of':None,'historical_membership_ready':False,
            'historical_first_observation':False,'groups':groups,'rows':rows,'responses':refs,
            'risk_warning_a_shares':sum(row['kind']=='risk_warning' and row['share_class']=='A' for row in rows),
            'delisting_a_shares':sum(row['kind']=='delisting' and row['share_class']=='A' for row in rows),
            'excluded_b_shares':sum(row['share_class']=='B' for row in rows),
            'note':'本次读取的交易所分类名单；深市表标明数据日，沪市表未声明数据日。不同于收盘名称组，不回填历史成员、收益或近期对照。'}


def list_status(directory=OUTPUT, *, now=None):
    now=now or datetime.now(timezone.utc);base={'version':VERSION,'availability':'missing','historical_membership_ready':False}
    if processor_digest()!=PROCESSOR: return {**base,'availability':'reload_required'}
    try:
        raw=json.loads((directory/'current.json').read_text())
        if raw['version']!=VERSION or raw['processor_digest']!=PROCESSOR or digest({k:v for k,v in raw.items() if k!='content_digest'})!=raw['content_digest']:
            raise ValueError('invalid risk-list snapshot binding')
        return {**base,'content_digest':raw['content_digest'],'processor_digest':PROCESSOR,**project(raw,directory,now)}
    except (OSError,ValueError,TypeError,KeyError,IndexError,AttributeError,OverflowError):
        return {**base,'availability':'invalid' if (directory/'current.json').exists() else 'missing'}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*_): raise ValueError('redirect not accepted')


class Collector:
    def __init__(self,directory): self.directory=directory;self.responses=[]

    def fetch(self,key,url,params):
        requested=url+('?' + urlencode(params) if params else '')
        request=Request(requested,headers={'User-Agent':'ST-Research-Copilot/8 local-research','Referer':SZSE_PAGE if 'szse.cn' in url else GROUPS['sse_main_risk']['url']})
        with build_opener(NoRedirect).open(request,timeout=20) as response:
            if response.geturl()!=requested: raise ValueError('request changed')
            raw=response.read(2_000_001)
        if not 0<len(raw)<=2_000_000: raise ValueError('oversized/empty response')
        sha=hashlib.sha256(raw).hexdigest();target=self.directory/'responses'/(sha+'.raw');target.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as temporary: temporary.write(raw);temporary_path=Path(temporary.name)
        temporary_path.replace(target)
        self.responses.append({'key':key,'url':url,'params':params,'final_url':requested,'observed_at':datetime.now(timezone.utc).isoformat(),'response_sha256':sha,'bytes':len(raw)})
        return raw.decode('utf-8')


def collect(*, output=OUTPUT, collector=None, now=None):
    if processor_digest()!=PROCESSOR: raise ValueError('reload before collecting')
    if (output/'current.json').exists() and json.loads((output/'current.json').read_text()).get('version')!=VERSION:
        raise ValueError('output belongs to another source')
    started=now or datetime.now(timezone.utc);collector=collector or Collector(output)
    for key,(url,_) in PROOFS.items():collector.fetch(key,url,{})
    for key,item in GROUPS.items():
        if item['venue']=='SSE':collector.fetch(key,SSE_API,parameters(key))
        else:
            text=collector.fetch(key+':1',SZSE_API,parameters(key))
            _,meta=szse_table(key,json.loads(text),1,local_day(started))
            for page in range(2,meta[1]+1):collector.fetch(key+':'+str(page),SZSE_API,parameters(key,page))
    raw={'version':VERSION,'processor_digest':PROCESSOR,'observed_on':local_day(started),'started_at':started.isoformat(),
         'completed_at':(now or datetime.now(timezone.utc)).isoformat(),'responses':collector.responses}
    result=project(raw,output,now or datetime.now(timezone.utc));raw['content_digest']=digest(raw)
    atomic_write_json(output/'snapshots'/(raw['content_digest']+'.json'),raw);atomic_write_json(output/'current.json',raw)
    return {key:result[key] for key in ('availability','observed_on','risk_warning_a_shares','delisting_a_shares','excluded_b_shares')}


def reparse(*, output=OUTPUT, now=None):
    """Replay byte-bound archives without claiming a new network observation."""
    now=now or datetime.now(timezone.utc)
    if processor_digest()!=PROCESSOR: raise ValueError('reload before replay')
    raw=json.loads((output/'current.json').read_text())
    if raw['version']!=VERSION or digest({k:v for k,v in raw.items() if k!='content_digest'})!=raw['content_digest']:
        raise ValueError('invalid source snapshot for replay')
    result=project(raw,output,now)
    raw.pop('content_digest');raw['processor_digest']=PROCESSOR;raw['reparsed_at']=now.isoformat();raw['content_digest']=digest(raw)
    atomic_write_json(output/'snapshots'/(raw['content_digest']+'.json'),raw);atomic_write_json(output/'current.json',raw)
    return {**{key:result[key] for key in ('availability','observed_on','risk_warning_a_shares','delisting_a_shares','excluded_b_shares')},
            'reparsed_at':raw['reparsed_at'],'content_digest':raw['content_digest']}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=OUTPUT)
    parser.add_argument('--reparse',action='store_true',help='Replay this source archive; preserve original acquisition times')
    args=parser.parse_args();result=reparse(output=args.output) if args.reparse else collect(output=args.output)
    print(json.dumps(result,ensure_ascii=False));return 0


if __name__=='__main__':raise SystemExit(main())
