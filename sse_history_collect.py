"""Explicit SSE historical-source collection; network work never runs from GET readers."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from threading import Lock
import time
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
import sse_history_archive as archive

CAPTURE_VERSION='sse_historical_source_collection_v1'


class SourceClient:
    def __init__(self, *, repair=False):
        self.repair=repair;self.lock=Lock();self.next_slot=0

    def request(self,folder,url,params,*,code=None,validate=None):
        key=digest({'url':url,'params':params});cache=folder/'cache'/(key+'.json')
        if self.repair:
            try:
                ref=json.loads(cache.read_text())
                if ref['url']!=url or ref['params']!=params or code is not None and ref['code']!=code: raise ValueError('cache query differs')
                payload=archive.body(folder,ref,datetime.now(timezone.utc))
                if validate:validate(payload,ref)
                return payload,ref
            except (OSError,ValueError,KeyError,TypeError):pass
        full=url+'?'+urlencode(params)
        for attempt in range(3):
            try:
                with self.lock:
                    scheduled=max(time.monotonic(),self.next_slot);self.next_slot=scheduled+.4
                time.sleep(max(0,scheduled-time.monotonic()))
                with urlopen(Request(full,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'}),timeout=20) as response:
                    if response.url!=full: raise ValueError('source redirect')
                    data=response.read(4_000_001);length=response.headers.get('Content-Length')
                if len(data)>4_000_000 or length is not None and int(length)!=len(data): raise ValueError('incomplete source response')
                json.loads(data);break
            except (OSError,TimeoutError):
                if attempt==2:raise
                time.sleep(2*(attempt+1))
        sha=hashlib.sha256(data).hexdigest();folder.mkdir(parents=True,exist_ok=True);path=folder/(sha+'.raw')
        if path.exists():
            if path.read_bytes()!=data:raise ValueError('immutable source collision')
        else:
            temporary=path.with_suffix('.tmp');temporary.write_bytes(data);temporary.replace(path)
        ref={'url':url,'params':params,'observed_at':datetime.now(timezone.utc).isoformat(),'sha256':sha,'bytes':len(data)}
        if code is not None:ref.update(code=code,status='captured')
        payload=archive.body(folder,ref,datetime.now(timezone.utc))
        if validate:validate(payload,ref)
        atomic_write_json(cache,ref)
        return payload,ref


def collect(client, *, through, capture, endpoint_dir=archive.ROOT/'public_breadth', output=archive.OUTPUT, now=None, progress=None):
    clock=lambda:now or datetime.now(timezone.utc)
    started=clock();window=archive.recent_calendar_window(through)
    if window['availability']!='defined' or through>=started.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat():raise ValueError('completed window required')
    endpoint=json.loads((endpoint_dir/'current.json').read_text());endpoint_key=endpoint['content_digest']
    archive.read_endpoint(endpoint_dir,endpoint_key,through,started)
    job=capture/'collection.json'
    if job.exists():
        old=json.loads(job.read_text())
        if old['version']!=CAPTURE_VERSION or old['through']!=through or old['endpoint_digest']!=endpoint_key:raise ValueError('foreign capture/window')
    elif capture.exists() and any(capture.iterdir()):raise ValueError('unowned nonempty capture directory')
    record={'version':CAPTURE_VERSION,'through':through,'endpoint_digest':endpoint_key,'started_at':started.isoformat(),'status':'collecting',
            'completed_price_sources':0,'expected_price_sources':None}
    def report(**values):
        record.update(values,recorded_at=clock().isoformat());atomic_write_json(job,record)
        if progress:progress(dict(record))
    report()
    try:
        refs=[]
        for board in ('1','8'):
            page=pages=1
            while page<=pages:
                params={**archive.REGISTRY_PARAMS,'STOCK_TYPE':board,'pageHelp.pageNo':page,'pageHelp.beginPage':page,'pageHelp.endPage':page}
                payload,ref=client.request(capture/'universe',archive.REGISTRY_URL,params)
                pages=payload['pageHelp']['pageCount']
                if type(pages) is not int or not 1<=pages<=20:raise ValueError('unexpected registry extent')
                refs.append(ref);page+=1
        for day in window['calendar']:
            _,ref=client.request(capture/'universe',archive.QUERY_URL,{**archive.OVERVIEW_PARAMS,'SEARCH_DATE':day});refs.append(ref)
        atomic_write_json(capture/'universe/complete.json',{'window':window,'source_refs':refs,'endpoint_snapshot':endpoint_key})
        basis=archive.read_basis(capture,clock());codes=sorted(basis['pool']);report(expected_price_sources=len(codes))
        plan={'version':'sse_full_price_capture_plan_v1','through':through,'start':window['start'],'basis_digest':basis['basis_capture_digest'],
              'codes':codes,'params':archive.PARAMS}
        atomic_write_json(capture/'full_prices/plan.json',plan);prices=[]
        def fetch(code):
            payload,ref=client.request(capture/'full_prices',archive.PRICE_URL+code,archive.PARAMS,code=code,
                                       validate=lambda payload,ref:archive.parse_prices(payload,ref,basis,clock()))
            archive.parse_prices(payload,ref,basis,clock());return ref
        pool=ThreadPoolExecutor(max_workers=2)
        try:
            for future in as_completed([pool.submit(fetch,code) for code in codes]):
                prices.append(future.result())
                if len(prices)%25==0 or len(prices)==len(codes):report(completed_price_sources=len(prices))
        finally:
            pool.shutdown(wait=True,cancel_futures=True)
        atomic_write_json(capture/'full_prices/complete.json',{'version':'sse_full_price_capture_v1','plan_digest':digest(plan),
            'started_at':started.isoformat(),'completed_at':clock().isoformat(),'status':'captured','source_refs':sorted(prices,key=lambda r:r['code'])})
        result=archive.materialize(capture,output=output,endpoint_dir=endpoint_dir,now=clock());report(status='complete');return result
    except Exception as exc:
        report(status='failed',error_type=type(exc).__name__)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--through',required=True);parser.add_argument('--repair',action='store_true');args=parser.parse_args()
    print(json.dumps(collect(SourceClient(repair=args.repair),through=args.through,capture=archive.OUTPUT/'staging'/args.through,
                             progress=lambda value:print(json.dumps(value),flush=True)),ensure_ascii=False));return 0


if __name__=='__main__':raise SystemExit(main())
