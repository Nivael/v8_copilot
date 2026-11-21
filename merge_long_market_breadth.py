"""Join replayed 44+3+50 windows without replacing original evidence."""
from pathlib import Path
from datetime import date
from hashlib import sha256
import json
from canonical_json import digest
from market_calendar import sessions_2026
from build_early_market_breadth import build as early_build
from build_september_breadth_bridge import build as bridge_build
from verify_recent_breadth_for_merge import verify as recent_verify
from market_reading_updates import OUTPUT as UPDATE_ROOT
from market_risk import MARKET_RISK_DIR
from trader_swing_reading import closing_day
from market_breadth import cross_section


def merge(early,bridge,recent):
    points=early['points']+bridge['points']+recent['points']
    calendar=sessions_2026(date(2026,7,1),date(2026,11,20))
    if [p['date']for p in points]!=calendar:raise ValueError('overlap or missing trading session')
    for p in points:
        if p.get('unexplained_missing'):raise ValueError('unexplained source gap')
        for k in ['observed_trading_stocks','listed_source_stocks','nontrading_stocks','advancing','declining','flat','declining_5pct_or_more']:
            if p['all'][k]!=p['SSE'][k]+p['SZSE'][k]:raise ValueError('venue denominator differs')
        a=p['all']
        if a['advancing']+a['declining']+a['flat']!=a['observed_trading_stocks'] or a['observed_trading_stocks']+a['nontrading_stocks']!=a['listed_source_stocks']:raise ValueError('activity partition differs')
    return points


def build():
    paths=['EARLY_MARKET_BREADTH_EVIDENCE_2026_11_21.json','SEPTEMBER_BREADTH_BRIDGE_EVIDENCE_2026_11_21.json','MARKET_RECENT_BREADTH_EVIDENCE_2026_11_21.json'];old=[json.loads(Path(p).read_text())for p in paths]
    early=early_build(old[0]['szse_source_folder']);bridge=bridge_build();recent=recent_verify()
    if early!=old[0]or bridge!=old[1]or recent!=old[2]['merged_history']:raise ValueError('saved window differs from raw replay')
    # The old Nov5/6 projections retained only all-market totals. Rebuild venue splits from their bound raw closes.
    steps={s['through']:s for s in json.loads((UPDATE_ROOT/'current.json').read_text())['steps']}
    enriched=[];venue_bindings={}
    for original in recent['points']:
        point=dict(original)
        if 'SSE'not in point or 'SZSE'not in point:
            day=point['date'];all_rows=[];venue_bindings[day]={}
            for venue in ['SSE','SZSE']:
                rows,key=closing_day(MARKET_RISK_DIR,day,venue)
                if key!=steps[day]['bindings']['closes'][venue]:raise ValueError('daily venue binding differs')
                point[venue]=cross_section(list(rows.values()));all_rows.extend(rows.values());venue_bindings[day][venue]=key
            if cross_section(all_rows)!=point['all']:raise ValueError('daily venue totals differ from old projection')
        enriched.append(point)
    recent={**recent,'points':enriched}
    points=merge(early,bridge,recent)
    evidence=dict(version='long_market_breadth_v1',scope='SSE_SZSE_ordinary_A_shares',historical_PIT=False,start=points[0]['date'],through=points[-1]['date'],sessions=len(points),source_sha256={p:sha256(Path(p).read_bytes()).hexdigest()for p in paths},supplemental_venue_bindings=venue_bindings,points=points,limits=['Observed retrospectively; not evidence of then-available execution','Fixed minus five percent statistic is not actual limit down','97 dates are not 97 independent strategy validations','No index/ST alignment or calibrated crisis score in this artifact'])
    evidence['content_digest']=digest(evidence);return evidence


if __name__=='__main__':
    e=build();Path('LONG_MARKET_BREADTH_EVIDENCE_2026_11_21.json').write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n');print(dict(sessions=e['sessions'],start=e['start'],through=e['through'],content_digest=e['content_digest']))
