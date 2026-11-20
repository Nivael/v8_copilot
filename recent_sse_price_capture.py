"""Resumable bounded official SSE price capture, without publishing market conclusions."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from hashlib import sha256
import argparse,json,os,time
from pathlib import Path
from threading import Lock
from urllib.request import Request,urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
from decimal import Decimal
from canonical_json import digest
from data_refresh import atomic_write_json
from sse_history_archive import read_basis,parse_prices,PRICE_URL,PARAMS,body

class OfficialPrices:
    def __init__(self,interval=.4):
        self.interval=interval;self.lock=Lock();self.next_request=0.
    def get(self,code):
        url=PRICE_URL+code+'?'+urlencode(PARAMS)
        for attempt in range(2):
            with self.lock:
                target=max(time.monotonic(),self.next_request);self.next_request=target+self.interval
            time.sleep(max(0,target-time.monotonic()))
            try:
                with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'}),timeout=20)as response:
                    raw=response.read(4_000_001)
                if len(raw)>4_000_000:raise ValueError('oversized official price response')
                return raw
            except HTTPError as e:
                if e.code<500 or e.code==501 or attempt:raise
            except OSError:
                if attempt:raise
            time.sleep(2)

def capture(basis,folder,get,*,workers=2,progress=None):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    plan={'version':'sse_full_price_capture_plan_v1','through':basis['window']['end'],'start':basis['window']['start'],
          'basis_digest':basis['basis_capture_digest'],'codes':sorted(basis['pool']),'params':PARAMS}
    plan_path=folder/'plan.json'
    if plan_path.exists() and json.loads(plan_path.read_text())!=plan:raise ValueError('existing capture plan changed')
    atomic_write_json(plan_path,plan);(folder/'refs').mkdir(exist_ok=True)
    refs={};errors={};started=datetime.now(timezone.utc).isoformat()
    def one(code):
        cached=folder/'refs'/(code+'.json');now=datetime.now(timezone.utc)
        if cached.exists():
            ref=json.loads(cached.read_text())
            if ref['code']!=code or ref.get('status')!='captured':raise ValueError('cached capture identity changed')
            parse_prices(body(folder,ref,now),ref,basis,now)
            return ref,True
        raw=get(code);observed=datetime.now(timezone.utc).isoformat();key=sha256(raw).hexdigest()
        ref={'code':code,'status':'captured','url':PRICE_URL+code,'params':PARAMS,'sha256':key,'bytes':len(raw),'observed_at':observed}
        parse_prices(json.loads(raw,parse_float=Decimal),ref,basis,datetime.now(timezone.utc))
        target=folder/(key+'.raw')
        if target.exists() and target.read_bytes()!=raw:raise ValueError('immutable raw collision')
        if not target.exists():target.write_bytes(raw)
        atomic_write_json(cached,ref)
        return ref,False
    reused=0
    def report(status):
        row={'version':'sse_recent_capture_progress_v1','status':status,'process_id':os.getpid(),'started_at':started,
             'observed_at':datetime.now(timezone.utc).isoformat(),'through':plan['through'],'expected':len(plan['codes']),
             'captured':len(refs),'reused':reused,'failed':len(errors),'errors':errors,'plan_digest':digest(plan),
             'not_market_publication':True}
        atomic_write_json(folder/'progress.json',row)
        if progress:progress(row)
    report('running')
    with ThreadPoolExecutor(max_workers=workers)as pool:
        tasks={pool.submit(one,code):code for code in plan['codes']}
        for future in as_completed(tasks):
            code=tasks[future]
            try:
                ref,old=future.result();refs[code]=ref;reused+=int(old)
            except Exception as e:errors[code]={'error_type':type(e).__name__,'http_status':getattr(e,'code',None)}
            if (len(refs)+len(errors))%25==0 or code in errors:report('running')
    status='captured' if not errors and len(refs)==len(plan['codes']) else 'partial'
    result={'version':'sse_full_price_capture_v1','status':status,'plan_digest':digest(plan),'started_at':started,
            'completed_at':datetime.now(timezone.utc).isoformat(),'source_refs':[refs[c]for c in sorted(refs)]}
    atomic_write_json(folder/('complete.json' if status=='captured' else 'partial.json'),result);report(status)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True);a=p.parse_args()
    basis=read_basis(a.capture,datetime.now(timezone.utc))
    result=capture(basis,a.capture/'full_prices',OfficialPrices().get,progress=lambda r:print(json.dumps({k:v for k,v in r.items()if k!='errors'}),flush=True))
    return 0 if result['status']=='captured' else 2
if __name__=='__main__':raise SystemExit(main())
