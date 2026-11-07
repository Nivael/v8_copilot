from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
from urllib.parse import urlencode

import pytest

from broad_etf_reading import EXTRAS,GROUPS,NAMES,read_extra_shares,read_indices,summarize
from canonical_json import digest
from data_refresh import atomic_write_json
from market_calendar import sessions_2026
from market_risk import ETF_SHARE_SQL


def calendar():return sessions_2026(date(2026,1,5),date(2026,2,15))[:21]


def test_group_comparison_uses_fund_breadth_and_never_sums_share_units_into_money():
    days=calendar();paths={code:[Decimal(100+i) for i in range(21)] for code in NAMES}
    indices={value[0]:[Decimal(100-i) for i in range(21)] for value in GROUPS.values()}
    result=summarize(paths,indices,days,days[0])
    assert result['sample_funds']==12 and len(result['groups'])==6
    assert result['headline']=='6组宽基样本的份额同步增加'
    assert result['estimated_cash_flow_yuan'] is None
    assert result['groups'][0]['sample_count']==4
    assert result['groups'][0]['reading']=='样本份额都增加，价格尚未同步回升'
    paths['510300.SH']=[Decimal(100-i) for i in range(21)]
    assert summarize(paths,indices,days,days[0])['groups'][0]['increasing_5d']==3
    paths['510300.SH'].pop()
    with pytest.raises(ValueError,match='calendar'):summarize(paths,indices,days,days[0])


def test_index_sources_need_exact_index_dates_queries_and_original_bytes(tmp_path):
    days=calendar();root=tmp_path/'trader_observations/broad_indices';root.mkdir(parents=True)
    refs=[]
    for code in {g[0] for g in GROUPS.values()}:
        raw=json.dumps({'code':'200','data':[{'tradeDate':day.replace('-',''),'indexCode':code,'close':'100.1'} for day in days]}).encode()
        key=sha256(raw).hexdigest();(root/'responses').mkdir(exist_ok=True);(root/'responses'/(key+'.json')).write_bytes(raw)
        refs.append({'code':code,'url':'https://www.csindex.com.cn/csindex-home/perf/index-perf?'+urlencode({'indexCode':code,'startDate':days[0].replace('-',''),'endDate':days[-1].replace('-','')}),
                     'response_sha256':key,'bytes':len(raw),'observed_at':'2026-02-20T00:00:00Z'})
    meta={'version':'broad_index_sources_v1','start':days[0],'through':days[-1],'responses':refs};meta['content_digest']=digest(meta);atomic_write_json(root/'current.json',meta)
    values,_=read_indices(tmp_path,days)
    assert len(values)==6 and all(len(path)==21 for path in values.values())
    target=root/'responses'/(refs[0]['response_sha256']+'.json');target.write_bytes(target.read_bytes()+b' ')
    with pytest.raises(ValueError,match='original'):read_indices(tmp_path,days)


def test_extra_funds_are_extracted_only_from_the_complete_dated_exchange_response(tmp_path):
    day='2026-11-04';root=tmp_path/'public_etf';(root/'responses').mkdir(parents=True)
    payload={'pageHelp':{'total':4,'pageNo':1,'pageCount':1},'result':[{'SEC_CODE':code[:6],'STAT_DATE':day,'TOT_VOL':'100.10'} for code in sorted(EXTRAS)]}
    raw=json.dumps(payload).encode();key=sha256(raw).hexdigest();(root/'responses'/(key+'.json')).write_bytes(raw)
    params={'sqlId':ETF_SHARE_SQL,'isPagination':'true','STAT_DATE':day,'pageHelp.pageSize':1000,'pageHelp.pageNo':1,'pageHelp.beginPage':1,'pageHelp.endPage':1,'pageHelp.cacheSize':1}
    meta={'calendar':[day],'share_unit':'ten_thousand_shares','source_sql':ETF_SHARE_SQL,'responses':[{'query_date':day,'page':1,'url':'https://query.sse.com.cn/commonQuery.do?'+urlencode(params),'response_sha256':key}]}
    meta['content_digest']=digest(meta);atomic_write_json(root/'current.json',meta)
    data={'public_etf_snapshot':{'content_digest':meta['content_digest']}}
    paths,_=read_extra_shares(data,tmp_path,[day])
    assert set(paths)==EXTRAS and all(path==[Decimal('100.10')] for path in paths.values())
    with pytest.raises(ValueError,match='bound'):read_extra_shares({'public_etf_snapshot':{'content_digest':'changed'}},tmp_path,[day])
