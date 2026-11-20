"""Independently control the early short-spell index endpoints; retain primary precision."""
from pathlib import Path
from hashlib import sha256
from decimal import Decimal as D,ROUND_HALF_UP
from datetime import date,datetime,timezone
from zoneinfo import ZoneInfo
import json,gzip
from market_calendar import sessions_2026
from long_breadth_st_alignment import INPUT,INPUT_SHA
from long_breadth_wait_comparison import analyze_wait


def verify(ref=None):
    path=Path('JULY_INDEX_CONTROL_SOURCE_2026_11_21.json');ref=ref if ref is not None else json.loads(path.read_text());raw=(Path(ref['source_store'])/(ref['response_sha256']+'.json')).read_bytes()
    if ref['url']!='https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000985&startDate=20260701&endDate=20260709'or len(raw)!=ref['bytes']or sha256(raw).hexdigest()!=ref['response_sha256']:raise ValueError('index source changed')
    observed=datetime.fromisoformat(ref['observed_at'])
    if observed.tzinfo is None or observed>datetime.now(timezone.utc) or observed.astimezone(ZoneInfo('Asia/Shanghai')).date()<date(2026,7,9):raise ValueError('index observation invalid')
    body=json.loads(raw)
    if body['code']!='200' or body['success']is not True:raise ValueError('index source failed')
    dates=sessions_2026(date(2026,7,1),date(2026,7,9));rows=body['data']
    if [r['tradeDate']for r in rows]!=[d.replace('-','')for d in dates]or any(r['indexCode']!='000985'for r in rows):raise ValueError('index date/code changed')
    raw=INPUT.read_bytes()
    if sha256(raw).hexdigest()!=INPUT_SHA:raise ValueError('primary changed')
    m=json.loads(gzip.decompress(raw))['current_extension']['market_inputs'];primary={r['trade_date']:D(str(r['close']))for r in m['benchmarks']if r['benchmark_id']=='csi_all_share'}
    official={d:D(str(r['close']))for d,r in zip(dates,rows)}
    if any(not q.is_finite()or q<=0 for q in official.values())or any(primary[d].quantize(D('.01'),rounding=ROUND_HALF_UP)!=official[d]for d in dates):raise ValueError('index close conflict')
    wp=Path('LONG_BREADTH_WAIT_EVIDENCE_2026_11_21.json');wait=json.loads(wp.read_text())
    if analyze_wait()!=wait:raise ValueError('waiting replay differs')
    episode=next(e for e in wait['reading']['episodes']if e['first']=='2026-07-02');check=episode['checks'][0]
    before=(official['2026-07-02']/official[episode['anchor']]-1)*100;after=(official[episode['target_end']]/official['2026-07-02']-1)*100
    if abs(float(before)-check['already_market_pct'])>.002 or abs(float(after)-check['remaining_market_pct'])>.002:raise ValueError('window price conflict')
    return dict(version='july_short_spell_index_control_v1',source=ref,wait_evidence_sha256=sha256(wp.read_bytes()).hexdigest(),input_asset_sha256=INPUT_SHA,reading=dict(matched_closes=len(dates),dates=dates,symbol='000985.CSI',primary_before_pct=check['already_market_pct'],official_before_pct=float(before),primary_remaining_pct=check['remaining_market_pct'],official_remaining_pct=float(after),matched_at_two_decimal_precision=True),limits=['Primary higher precision returns remain displayed; rounded official endpoints are a control','Does not change source observation date or establish historical real-time availability','One extra source for the same spell, not independent strategy validation'])


if __name__=='__main__':
    e=verify();Path('JULY_SHORT_SPELL_INDEX_CONTROL_EVIDENCE_2026_11_21.json').write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n');print(e['reading'])
