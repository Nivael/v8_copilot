"""Replay original 50-day history before using it in a longer window."""
from pathlib import Path
from datetime import datetime,timezone
from hashlib import sha256
import json
from build_recent_breadth import append_history
from recent_breadth_projection import materialize_inputs
from market_reading_updates import load_update,OUTPUT as UPDATE_ROOT
from market_risk import build_market_risk_status
from workbench_views import WATCHED,watch_basis


def verify():
    path=Path('MARKET_RECENT_BREADTH_EVIDENCE_2026_11_21.json');saved=json.loads(path.read_text())
    for name,key in saved['processor_files'].items():
        if sha256(Path(name).read_bytes()).hexdigest()!=key:raise ValueError('original processor changed')
    root=Path('/Volumes/Leibniz/dev/st_research/v8_copilot/wt/market-recent-breadth-20261121/out/market-recent-breadth-20261121')
    endpoint=Path('/Volumes/Leibniz/dev/st_research/local_data/v8_copilot/market_risk/trader_observations/latest_breadth')
    recent=materialize_inputs(root/'sse-capture',root/'szse-history',endpoint,root/'halt-notice',now=datetime.now(timezone.utc))
    # materialize_inputs stamps this replay's verification clock; raw source clocks remain exact.
    old_observed=datetime.fromisoformat(saved['recent']['input_observed_at'])
    new_observed=datetime.fromisoformat(recent['input_observed_at'])
    if old_observed.tzinfo is None or new_observed.tzinfo is None or not old_observed<=new_observed<=datetime.now(timezone.utc):raise ValueError('replay clock invalid')
    if {k:v for k,v in recent.items()if k!='input_observed_at'}!={k:v for k,v in saved['recent'].items()if k!='input_observed_at'}:raise ValueError('recent source replay differs')
    current=json.loads((UPDATE_ROOT/'current.json').read_text());base=build_market_risk_status();update=load_update(base,[watch_basis(base,s)for s in WATCHED])
    if update is None:raise ValueError('original update unavailable')
    merged=append_history(update[0]['combined_breadth_history'],recent,current['content_digest'])
    if merged!=saved['merged_history']:raise ValueError('original 50-day replay differs')
    return merged


if __name__=='__main__':
    r=verify();print(dict(days=len(r['points']),start=r['start'],through=r['through']))
