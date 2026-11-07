"""Synthetic source archives for collector tests, with explicit original-response bindings."""
import hashlib
import json

from etf_daily_sources import SSE_API, SSE_SQL
from etf_public_refresh import refresh_public_etfs as refresh_sse
from etf_szse_refresh import refresh_szse_etfs as refresh_szse
from etf_szse_history import API_URL, history_url
from urllib.parse import urlencode


def save(output, payload, ref, now):
    folder=output/'responses';folder.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(payload,ensure_ascii=False).encode();key=hashlib.sha256(raw).hexdigest();(folder/(key+'.json')).write_bytes(raw)
    return {**ref,'response_sha256':key,'observed_at':now.isoformat()}


def refresh_public_etfs(client,**kw):
    class Captured:
        def get_day(self,day):
            rows,refs=client.get_day(day)
            if refs:return rows,refs
            source=[{'SEC_CODE':r['ts_code'][:6],'STAT_DATE':r['trade_date'],'TOT_VOL':str(r['fd_share'])} for r in rows]
            query={'sqlId':SSE_SQL,'isPagination':'true','STAT_DATE':day,'pageHelp.pageSize':1000,'pageHelp.pageNo':1,'pageHelp.beginPage':1,'pageHelp.endPage':1,'pageHelp.cacheSize':1}
            ref={'query_date':day,'page':1,'url':SSE_API+'?'+urlencode(query),'complete_daily_rows':len(source)}
            payload={'sqlId':SSE_SQL,'result':source,'pageHelp':{'pageNo':1,'pageCount':1,'total':len(source)}}
            return rows,[save(kw['output'],payload,ref,kw['now'])]
    return refresh_sse(Captured(),**kw)


def refresh_szse_etfs(client,**kw):
    class Captured:
        api_url=getattr(client,'api_url',API_URL)
        def get_history(self,code,calendar,*,nav=False):
            rows,refs=client.get_history(code,calendar,nav=nav)
            if refs:return rows,refs
            data=[{'fund_code':code[:6],'nav_date' if nav else 'size_date':r['nav_date' if nav else 'trade_date'],
                   'nav_per_share' if nav else 'current_size':str(r['unit_nav' if nav else 'fd_share'])} for r in rows]
            chunks=[data[i:i+20] for i in range(0,len(data),20)] if not nav else [data]
            refs=[]
            for page,chunk in enumerate(chunks,1):
                payload=[{'metadata':{'catalogid':'fund_jjjz' if nav else 'fund_jjgm','pageno':0 if nav else page,
                    'pagecount':0 if nav else len(chunks),'pagesize':-1 if nav else 20,'recordcount':0 if nav else len(data),
                    'cols':{'nav_per_share' if nav else 'current_size':'单位基金净值(元)' if nav else '基金规模(万份)'}},'data':chunk}]
                ref={'code':code,'kind':'NAV' if nav else 'shares','page':page,'url':history_url(self.api_url,code,calendar,nav=nav,page=page)}
                refs.append(save(kw['output'],payload,ref,kw['now']))
            return rows,refs
    return refresh_szse(Captured(),**kw)
