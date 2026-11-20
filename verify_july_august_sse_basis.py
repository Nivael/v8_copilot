"""Read-only listing/exit reconstruction, with daily official count controls."""
from pathlib import Path
from datetime import datetime,timezone,date
from collections import defaultdict
import json
from sse_history_archive import body,ordinary_date,REGISTRY_PARAMS,OVERVIEW_PARAMS,REGISTRY_URL,QUERY_URL
from market_calendar import sessions_2026


def verify(e):
    now=datetime.now(timezone.utc);folder=Path(e['source_store']);pages=defaultdict(list);pool={}
    for ref in e['registry_refs']:
        x=body(folder,ref,now);p=ref['params'];board=p['STOCK_TYPE'];page=p['pageHelp.pageNo']
        if ref['url']!=REGISTRY_URL or p!={**REGISTRY_PARAMS,'STOCK_TYPE':board,'pageHelp.pageNo':page,'pageHelp.beginPage':page,'pageHelp.endPage':page}:raise ValueError('registry request changed')
        h=x['pageHelp'];total=h['total']
        if x['sqlId']!=REGISTRY_PARAMS['sqlId'] or x['actionErrors']!=[] or x['fieldErrors']!={} or h['data']!=x['result'] or h['pageNo']!=page or h['pageSize']!=500 or len(x['result'])!=min(500,total-(page-1)*500):raise ValueError('registry page changed')
        pages[board].append((page,total,x['result']))
    if set(pages)!={'1','8'}:raise ValueError('boards missing')
    allrows={}
    for board,group in pages.items():
        group.sort();total=group[0][1]
        if [r[0]for r in group]!=list(range(1,(total+499)//500+1))or any(r[1]!=total for r in group):raise ValueError('pages missing')
        for _,_,rows in group:
            for r in rows:
                code=r['A_STOCK_CODE']
                if code in allrows or r['STOCK_TYPE']!=board or not code.startswith('60'if board=='1'else'68'):raise ValueError('security identity changed')
                listed=ordinary_date(r['LIST_DATE']);ended=ordinary_date(r['DELIST_DATE'])if r['DELIST_DATE']!='-'else None
                allrows[code]=dict(code=code,name=r['COMPANY_ABBR'],listed=listed,ended=ended,board=board)
    pool={c:r for c,r in allrows.items()if r['listed']<='2026-08-31'and(r['ended']is None or r['ended']>'2026-07-01')}
    if pool!=e['pool']:raise ValueError('reconstructed pool differs')
    days=sessions_2026(date(2026,7,1),date(2026,8,31));controls=[]
    if [r['params']['SEARCH_DATE']for r in e['overview_refs']]!=days:raise ValueError('calendar coverage changed')
    for ref in e['overview_refs']:
        day=ref['params']['SEARCH_DATE'];x=body(folder,ref,now)
        if ref['url']!=QUERY_URL or ref['params']!={**OVERVIEW_PARAMS,'SEARCH_DATE':day}or x['sqlId']!=OVERVIEW_PARAMS['sqlId']or x['actionErrors']!=[]or x['fieldErrors']!={}:raise ValueError('overview request changed')
        groups={r['PRODUCT_CODE']:r for r in x['result']}
        if len(groups)!=len(x['result'])or not {'01','02','03','17'}<=groups.keys()or any(r['TRADE_DATE']!=day.replace('-','')for r in groups.values()):raise ValueError('overview scope changed')
        counts={k:int(r['LIST_NUM'])for k,r in groups.items()}
        if counts['17']!=counts['01']+counts['02']+counts['03']:raise ValueError('overview total differs')
        active=[c for c,r in pool.items()if r['listed']<=day and(r['ended']is None or r['ended']>day)];main=sum(c.startswith('60')for c in active);star=len(active)-main
        if(main,star)!=(counts['01'],counts['03']):raise ValueError('historical population differs')
        controls.append(dict(date=day,main_registry=main,star_registry=star,main_reported=counts['01'],star_reported=counts['03'],matched=True))
    if controls!=e['controls']or not e['all_days_matched']:raise ValueError('projection changed')
    return dict(pool=len(pool),days=len(days),all_days_matched=True)

if __name__=='__main__':
    print(verify(json.loads(Path('JULY_AUGUST_SSE_BASIS_EVIDENCE_2026_11_21.json').read_text())))
