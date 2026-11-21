"""Read-only source-to-reading verification. Does not collect, publish, or record."""
import argparse
import json
from pathlib import Path
from hashlib import sha256
from tencent_nov20_market_audit import build as market
from nov20_szse_limit_crosscheck import reading as szse
from fixed_nov20_limit_audit import reading as fixed
from fixed_limit_transition import analyze as transition
from fixed_nov20_gap_context import reading as gap


def check(path, computed):
    raw=Path(path).read_bytes()
    if json.loads(raw)!=computed:raise ValueError('saved result differs: '+path)
    return dict(path=path,sha256=sha256(raw).hexdigest(),verified=True)


def verify():
    # These independent processors intentionally replay their own dependencies.
    # No builder main functions or ledger-writing entry points are invoked.
    evidence=[('TENCENT_NOV20_MARKET_AUDIT_2026_11_21.json',market),('NOV20_SZSE_LIMIT_CROSSCHECK_2026_11_21.json',szse),('FIXED_NOV20_LIMIT_AUDIT_2026_11_21.json',fixed),('FIXED_LIMIT_TRANSITION_2026_11_21.json',transition),('FIXED_NOV20_GAP_CONTEXT_2026_11_21.json',gap)]
    results=[check(path,processor()) for path,processor in evidence]
    from build_tencent_market_limit_reading import reading as market_view
    from build_nov20_szse_limit_reading import reading as szse_view
    from build_fixed_nov20_limit_reading import reading as fixed_view
    from build_fixed_limit_transition_reading import reading as transition_view
    from build_fixed_gap_context_reading import reading as gap_view
    views=[('web/src/tencentMarketDailyLimits.json',market_view),('web/src/nov20SzseLimitComplete.json',szse_view),('web/src/fixedNov20Limits.json',fixed_view),('web/src/fixedLimitTransition.json',transition_view),('web/src/fixedGapContext.json',gap_view)]
    results.extend(check(path,processor()) for path,processor in views)
    return dict(version='nov20_limit_reading_verification_v1',results=results,verified_files=len(results),new_source_requests=0,new_research_records=0,limitations=['Checks saved source bytes, computation and generated JSON; not live provider freshness','Does not independently certify supplier limits, legal ST completeness or executable exits','Does not run browser, frontend or full backend tests','Research append proof is historical, not a fresh database integrity audit'])

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);args=parser.parse_args()
    result=verify()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
