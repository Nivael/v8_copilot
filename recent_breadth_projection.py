"""Rebuild recent two-venue breadth only after all quotes and missing intervals reconcile."""
from pathlib import Path
from datetime import datetime,timezone,date
from decimal import Decimal
from hashlib import sha256
import json,re,unicodedata
from canonical_json import digest
from sse_history_archive import project,read_basis,read_endpoint,body,parse_prices
from market_breadth import cross_section
from recent_breadth_inputs import verify_szse_capture


def compact(text):return re.sub(r'\s+','',unicodedata.normalize('NFKC',text))

def verified_suspensions(folder,now):
    folder=Path(folder);r=json.loads((folder/'complete.json').read_text())
    if r['version']!='recent_sse_suspension_capture_v1' or digest({k:v for k,v in r.items()if k!='content_digest'})!=r['content_digest']:raise ValueError('suspension capture changed')
    actual=[];refs=r['source_refs'];total=None
    for i,ref in enumerate(refs):
        params={'isPagination':'true','sqlId':'GW_PL_JYTS_TFPXX','pageHelp.pageSize':100,'productCode':'','keyWords':'','startStopDate':r['start_query'].replace('-',''),'endStopDate':r['through_query'].replace('-',''),'pageHelp.pageNo':i+1}
        if ref['url']!='https://query.sse.com.cn/commonSoaQuery.do'or ref['params']!=params:raise ValueError('suspension full query changed')
        d=body(folder,ref,now);h=d['pageHelp'];n=h['total']
        if(d['actionErrors']!=[]or d['fieldErrors']!={}or d['isPagination']!='true'or d['sqlId']!=params['sqlId']or d['result']!=h['data']
           or type(n)is not int or n<0 or h['pageNo']!=i+1 or h['pageSize']!=100 or h['pageCount']!=len(refs)
           or len(refs)!=max(1,(n+99)//100)or len(d['result'])!=min(100,n-i*100)or(total is not None and total!=n)):raise ValueError('suspension pagination incomplete')
        total=n;actual.extend(d['result'])
    if actual!=r['rows']or len({digest(v)for v in actual})!=len(actual):raise ValueError('suspension rows changed')
    return r

def halt_coverage(rows,populations,endpoint,reviewed_starts):
    """Open intervals require a separately reviewed start plus an inactive final cross-section."""
    pairs=set();proofs=[]
    for row in rows:
        code=row['productCode']
        if row['controlType']!='TR'or not re.fullmatch(r'(?:60|68)\d{4}',code):continue
        start=datetime.strptime(row['startStopDate'],'%Y%m%d').date().isoformat()
        end=datetime.strptime(row['endStopDate'],'%Y%m%d').date().isoformat()if row['endStopDate']else None
        covered=[day for day,codes in populations.items()if code in codes and start<=day and(end is None or day<=end)]
        if not covered:continue
        if(end and end<start)or row['type']not in('LXTP','LSTP'):raise ValueError('unsupported halt interval')
        if row['type']=='LSTP':
            if end!=start:raise ValueError('temporary halt dates changed')
            if row['stopTime']!='WH':continue
        elif row['stopTime']not in('','WH'):raise ValueError('unsupported continuous halt time')
        if end is None and(reviewed_starts.get(code)!=start or endpoint.get(code,{}).get('is_trading')is not False or row['endStopReason']!=''):
            raise ValueError('open halt interval lacks reviewed start and independent inactive close')
        pairset={(day,code)for day in covered}
        if pairset&pairs:raise ValueError('overlapping suspension records')
        pairs|=pairset;proofs.append({'symbol':code,'start':start,'last_suspended_on':end,'days':covered})
    return pairs,proofs

def reviewed_halt_start(folder):
    from pypdf import PdfReader
    from sse_gap_review import read_documents,verify_claim,PROFILE,ROOT
    root=Path(folder).parent;profile=json.loads(Path(__file__).with_name('recent_halt_clauses_v1.json').read_text())
    if profile['version']!='recent_halt_clauses_v1':raise ValueError('halt review version changed')
    starts={};proofs=[]
    for row in profile['documents']:
        source=json.loads((root/row['source_file']).read_text());pdf=root/row['pdf_file']
        if(source['symbol']!=row['symbol']or source['announcement_id']!=row['announcement_id']or source['url']!=row['url']
           or source['sha256']!=row['sha256']or sha256(pdf.read_bytes()).hexdigest()!=row['sha256']
           or source['pages']!=row['page_count']or not source['protected_gate_passed']):raise ValueError('halt source identity changed')
        texts=[p.extract_text()or''for p in PdfReader(pdf).pages]
        if texts!=source['texts']:raise ValueError('halt notice projection changed')
        if compact(row['symbol'])not in compact(texts[0]):raise ValueError('halt notice subject missing')
        for claim in row['claims']:
            if not set(claim['physical_pages'])<=set(row['reviewed_pages']):raise ValueError('unreviewed halt claim page')
            text=compact(''.join(texts[i-1]for i in claim['physical_pages']))
            day=date.fromisoformat(claim['effective_on']);token=f'{day.year}年{day.month}月{day.day}日'
            if compact(claim['clause'])not in text or compact(token)not in compact(claim['clause']):raise ValueError('halt date-role clause missing')
            if claim['role']=='halt_start':starts[row['symbol']]=claim['effective_on']
        proofs.append(row)
    # Reuse original locally retained documents, without downloading or uploading protected bodies.
    docs=read_documents(ROOT/'sse_gap_review/documents',datetime.now(timezone.utc))
    for item in PROFILE['episodes']:
        if item['symbol']not in profile['reused_start_symbols']:continue
        for claim in item['claims']:
            role,day=verify_claim(claim,docs,item)
            if role=='halt_start':
                starts[item['symbol']]=day.isoformat()if hasattr(day,'isoformat')else day
                src=docs[claim['document_id']]
                proofs.append({'symbol':item['symbol'],'reused':True,'start_on':item['start_on'],'url':src['source_url'],'sha256':src['raw_sha256'],'physical_pages':claim['pages']})
    return starts,proofs


def combine_day(day,expected_codes,records,halt_pairs,szse_rows):
    if set(records)-set(expected_codes):raise ValueError('price outside daily listing population')
    rows=[];classified=[]
    for code in expected_codes:
        rec=records.get(code)
        if rec is None:
            if(day,code)not in halt_pairs:raise ValueError('unexplained missing quote '+day+' '+code)
            rows.append({'ts_code':code+'.SH','is_trading':False});classified.append(code)
        elif rec['is_trading']:
            if(day,code)in halt_pairs:raise ValueError('halt source conflicts with positive trading activity')
            last,previous=Decimal(rec['last']),Decimal(rec['prev_close'])
            rows.append({'ts_code':code+'.SH','last':float(last),'prev_close':float(previous),'pct_chg':float((last/previous-1)*100),'amount':float(rec['amount']),'is_trading':True})
        else:rows.append({'ts_code':code+'.SH','is_trading':False})
    return {'date':day,'all':cross_section(rows+szse_rows),'SSE':cross_section(rows),'SZSE':cross_section(szse_rows),'missing_prices_classified_as_halted':classified,'unexplained_missing':[]}

def materialize_inputs(capture,szse_folder,endpoint_folder,notice_folder,*,now=None):
    now=now or datetime.now(timezone.utc);capture=Path(capture);szse_folder=Path(szse_folder)
    archive=project(capture,Path(endpoint_folder),now);basis=read_basis(capture,now);sx=verify_szse_capture(szse_folder,now=now)
    calendar=list(sx['points'][i]['date']for i in range(len(sx['points'])))
    populations={d:basis['populations'][d]for d in calendar}
    endpoint=read_endpoint(Path(endpoint_folder),basis['endpoint_digest'],basis['window']['end'],now)
    susp=verified_suspensions(capture/'suspensions',now);starts,notice=reviewed_halt_start(notice_folder)
    pairs,halt_proofs=halt_coverage(susp['rows'],populations,endpoint,starts)
    raw=json.loads((capture/'full_prices/complete.json').read_text());byday={d:{}for d in calendar}
    for ref in raw['source_refs']:
        records=parse_prices(body(capture/'full_prices',ref,now),ref,basis,now)
        for day in calendar:
            if day in records:byday[day][ref['code']]=records[day]
    points=[]
    for day in calendar:
        sz=json.loads((szse_folder/'days'/(day+'.json')).read_text())['block']['rows']
        points.append(combine_day(day,populations[day],byday[day],pairs,sz))
    last=points[-1]
    # Entire last cross-section must agree with the independently published full snapshot.
    original=json.loads((Path(endpoint_folder)/'snapshots'/(basis['endpoint_digest']+'.json')).read_text())
    if original['content_digest']!=basis['endpoint_digest']:raise ValueError('independent endpoint snapshot changed')
    for venue in ('SSE','SZSE'):
        if last[venue]!=cross_section(original['venues'][venue]['rows']):raise ValueError('full final breadth cross-check differs')
    return {'version':'recent_two_venue_breadth_v1','availability':'observed','complete_market_history':True,'historical_PIT':False,
            'start':calendar[0],'through':calendar[-1],'points':points,'sources':{'sse_basis':basis['basis_capture_digest'],'sse_prices_plan':raw['plan_digest'],'szse':sx['source_digest'],'suspensions':susp['content_digest'],'endpoint':basis['endpoint_digest']},
            'price_source_count':archive['price_responses'],'historical_pool':len(basis['pool']),'endpoint_members':len(endpoint),
            'sse_archive_summary':{k:v for k,v in archive.items()if k not in('days','source_refs')},'halts':halt_proofs,'halt_notice':notice,'input_observed_at':now.isoformat()}
