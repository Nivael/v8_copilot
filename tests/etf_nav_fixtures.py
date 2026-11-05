"""Portable synthetic primary responses, explicitly distinct from live issuer data."""
from hashlib import sha256
import json

from etf_issuer_nav import NAV_DEFINITIONS
from etf_nav_refresh import refresh_issuer_navs as refresh
from etf_nav_sources import CHINAAMC_API, EFUNDS_SCHEMA, HUATAI_API, HUATAI_SITE, NF_API


def archive(directory,code,calendar,rows,now):
    provider=NAV_DEFINITIONS[code]['provider'];refs=[];data={r['nav_date']:str(r['unit_nav']) for r in rows}
    def save(url,body,params=None,method='GET',**extra):
        raw=(body if isinstance(body,str) else json.dumps(body)).encode();key=sha256(raw).hexdigest()
        folder=directory/'responses';folder.mkdir(exist_ok=True,parents=True);(folder/(key+'.raw')).write_bytes(raw)
        refs.append({'code':code,'url':url,'method':method,'params':params or {},'observed_at':now.isoformat(),
                     'response_sha256':key,'bytes':len(raw),'content_type':'synthetic-test-only',**extra})
    if provider=='jsfund':
        body=''.join(f'<tr><td>{d}</td><td>{data[d]}</td><td>99</td></tr>' for d in reversed(calendar))
        save(NAV_DEFINITIONS[code]['url'],f'<html><input name="FundCode" value="{code[:6]}"><option value="{code[:6]}" selected>ETF</option><table class="mm_r_table7"><tr><td>日期</td><td>份额净值</td><td>累计净值</td></tr>{body}</table></html>')
    elif provider=='efunds':
        literal=f'https://cdn.efunds.com.cn/market/2.0/{code[:6]}_1y.js'
        save(NAV_DEFINITIONS[code]['url'],f'<html><script>var fundCode="{code[:6]}";</script>单位净值(元)<script src="{literal}"></script></html>')
        save(EFUNDS_SCHEMA,'2 EnumSourceTypeNetValue 单位净值')
        body=''.join(f'{d.replace("-","")}_1_{data[d]}_99_0;' for d in calendar)
        save(literal,f'mk_{code[:6]}_1y="0_1_2_3_4;{body}";')
    else:
        size=20 if provider=='chinaamc' else 10;chunks=[calendar[::-1][i:i+size] for i in range(0,len(calendar),size)]
        for page,days in enumerate(chunks,1):
            if provider=='chinaamc':
                params={'fundcode':code[:6],'beginDate':calendar[0],'endDate':calendar[-1],'isQuery':'true' if page==1 else '', 'pageIndex':page}
                body=''.join(f'<tr><td>{d}</td><td>{data[d]}</td><td>99</td><td>999</td></tr>' for d in days)
                save(CHINAAMC_API,f'<html><input name="fundcode" value="{code[:6]}"><input name="beginDate" value="{calendar[0]}"><input name="endDate" value="{calendar[-1]}"><table id="hoverBox1"><tr><td>净值日期</td><td>单位净值</td><td>累计净值</td><td>资产净值</td></tr></table><table id="hoverBox1_1">{body}</table><script>let currentPage = \'{page}\'; let totalPage = \'{len(chunks)}\';</script></html>',params,'POST')
            elif provider=='huatai_pb':
                params={'fundcode':code[:6],'from':calendar[0],'to':calendar[-1],'pages':f'{page}-10','siteId':HUATAI_SITE}
                save(HUATAI_API,{'currentPage':page,'totalPage':len(chunks),'totalCount':len(calendar),'dataList':[{'date':d,'fundcode':code[:6],'netvalue':data[d],'totalnetvalue':'99'} for d in days]},params)
            else:
                params={'fundCode':code[:6],'curPage':page,'pageSize':10}
                save(NF_API,{'code':'ETS-5BP00000','data':{'jjjzList':{'pageNum':page,'pageSize':10,'size':len(days),'total':len(calendar),'pages':len(chunks),
                    'list':[{'fdate':d.replace('-',''),'fdate_ex':d,'fundCode':None,'fundNav':data[d],'ljfundNav':'99'} for d in days]}}},params,'POST',
                    reported_history_total=len(calendar),pagination_basis='exact_requested_trading_calendar')
    return refs


def refresh_issuer_navs(client,**kw):
    class Captured:
        def get_navs(self,code,calendar):
            rows,refs=client.get_navs(code,calendar)
            return rows,refs or archive(kw['output'],code,calendar,rows,kw['now'])
    return refresh(Captured(),**kw)
