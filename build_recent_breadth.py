"""Explicitly rebuild recent breadth and append to verified old history, without changing old snapshots."""
from pathlib import Path
from datetime import date,datetime,timezone
from hashlib import sha256
import argparse,json
from canonical_json import digest
from market_calendar import sessions_2026
from recent_breadth_projection import materialize_inputs
from market_breadth_sequence import analyze
from market_price_reading import _verify,OUTPUT as INDEX_ROOT
from market_reading_updates import load_update,OUTPUT as UPDATE_ROOT
from market_risk import build_market_risk_status
from workbench_views import WATCHED,watch_basis
from data_refresh import atomic_write_json


def append_history(old,recent,old_binding):
    if old['availability']!='observed'or not recent['complete_market_history']:raise ValueError('verified two-venue inputs required')
    points=old['points']+recent['points']
    if [p['date']for p in points]!=sessions_2026(date.fromisoformat(old['start']),date.fromisoformat(recent['through'])):raise ValueError('history overlap or missing session')
    out={'version':'two_venue_breadth_history_extension_v1','availability':'observed','complete_market_history':True,'historical_PIT':False,
         'start':old['start'],'through':recent['through'],'points':points,'source_bindings':{'old_base':old['base_reference_digest'],'old_daily_update':old_binding,'recent_inputs':recent['sources']}}
    out['content_digest']=digest(out);return out


def payload(merged,recent,index):
    seq=analyze(merged,index);calendar=index['calendar'];q=index['indices']['000985.CSI'];lookup={p['trade_date']:i for i,p in enumerate(q)}
    rows=[];status={p['date']:p for p in seq['days']}
    for d in recent['points']:
        a=d['all'];i=lookup[d['date']];n=a['observed_trading_stocks']
        if i<1:raise ValueError('prior index close needed')
        rows.append({'date':d['date'],'trading':n,'listed':a['listed_source_stocks'],'nontrading':a['nontrading_stocks'],
                     'advancing':a['advancing'],'declining':a['declining'],'flat':a['flat'],'advancing_pct':a['advancing']/n*100,
                     'median_return_pct':a['median_return_pct'],'declining_5pct_or_more':a['declining_5pct_or_more'],
                     'declining_5pct_or_more_pct':a['declining_5pct_or_more']/n*100,
                     'market_day_pct':(q[i]['close']/q[i-1]['close']-1)*100,'streak':status[d['date']]['streak']})
    last_signal=seq['signals'][-1];i=lookup[last_signal['date']];observed=min(5,len(calendar)-1-i);end=calendar[i+observed]
    return {'version':'recent_market_participation_reading_v1','as_of':recent['through'],'start':recent['start'],'rows':rows,
            'history_start':merged['start'],'history_days':len(merged['points']),'history_digest':merged['content_digest'],
            'sequence':seq,'latest_signal_observed_following_sessions':observed,'latest_signal_partial_through':end,
            'latest_signal_partial_market_pct':(q[i+observed]['close']/q[i]['close']-1)*100,
            'source_counts':{'sse_prices':recent['price_source_count'],'sse_historical_pool':recent['historical_pool'],'sse_last_members':recent['endpoint_members'],
                'sse_quote_window_start':recent['sse_archive_summary']['start'],'sse_quote_window_through':recent['sse_archive_summary']['through'],
                'new_recent_sessions':len(recent['points']),'classified_missing_stock_days':sum(len(d['missing_prices_classified_as_halted'])for d in recent['points'])},
            'boundaries':['“跌幅至少5%”是固定幅度统计，不是按板块和特殊日期核验的跌停家数。','两个旧提示、一个新增提示都在同一市场阶段，不新增独立制度试验或方法晋级。','广度完整不等于历史当时已取得、可以在同一收盘价成交，或已经核验T+1、滑点及一字跌停退出。','本轮只补广度过程；旧动态ST参考与ETF仍按其原日期显示，不把它们推进到11月20日。']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--endpoint-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);a=p.parse_args();now=datetime.now(timezone.utc)
    recent=materialize_inputs(a.source_root/'sse-capture',a.source_root/'szse-history',a.endpoint_root,a.source_root/'halt-notice',now=now)
    current=json.loads((UPDATE_ROOT/'current.json').read_text());base=build_market_risk_status();update=load_update(base,[watch_basis(base,s)for s in WATCHED]);assert update is not None
    if json.loads((UPDATE_ROOT/'current.json').read_text())!=current:raise ValueError('old daily update changed during replay')
    merged=append_history(update[0]['combined_breadth_history'],recent,current['content_digest'])
    index=json.loads((INDEX_ROOT/'current.json').read_text());_verify(index,INDEX_ROOT,now);reading=payload(merged,recent,index)
    files=('build_recent_breadth.py','recent_breadth_projection.py','recent_breadth_inputs.py','recent_halt_clauses_v1.json','market_breadth_sequence.py')
    evidence={'version':'recent_market_participation_evidence_v1','checked_at':now.isoformat(),'reading':reading,'merged_history':merged,'recent':recent,'benchmark':index,
              'sse_complete_file_sha256':sha256((a.source_root/'sse-capture/full_prices/complete.json').read_bytes()).hexdigest(),
              'processor_files':{n:sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()for n in files}}
    atomic_write_json(a.evidence,evidence);reading['evidence_sha256']=sha256(a.evidence.read_bytes()).hexdigest();atomic_write_json(a.output,reading)
    archive=a.source_root/'derived/snapshots';atomic_write_json(archive/(digest(evidence)+'.json'),evidence)
    print(json.dumps({'recent_days':len(reading['rows']),'historical_days':reading['history_days'],'through':reading['as_of'],'signals':reading['sequence']['signals'],'classified_missing':reading['source_counts']['classified_missing_stock_days']},ensure_ascii=False))
if __name__=='__main__':main()
