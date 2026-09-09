"""Measure fresh-process leaf imports with one interpreter and alternating order."""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    checkouts = {"baseline": args.baseline.resolve(), "candidate": Path(__file__).resolve().parents[1]}
    env = dict(os.environ, V8_DATA_ROOT=str(args.data_root.resolve()))
    report = {}
    for module in ("llm.boundaries", "freshness_manifest", "core_router", "llm.parser"):
        durations = {name: [] for name in checkouts}
        loaded = {}
        for repeat in range(5):
            order = list(checkouts) if repeat % 2 == 0 else list(reversed(checkouts))
            for name in order:
                code = (f"import time; start=time.perf_counter(); import {module}; "
                        "elapsed=time.perf_counter()-start; import sys,json; "
                        "print(json.dumps([elapsed,len(sys.modules),'answer_engine' in sys.modules]))")
                elapsed, count, engine_loaded = json.loads(subprocess.check_output(
                    [sys.executable, "-c", code], cwd=checkouts[name], env=env, text=True,
                ))
                durations[name].append(elapsed)
                loaded[name] = dict(module_count=count, answer_engine_loaded=engine_loaded)
        report[module] = dict(seconds=durations, loaded=loaded,
                             median_ms={name: statistics.median(values)*1000 for name, values in durations.items()})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({module: result["median_ms"] for module, result in report.items()}, indent=2))


if __name__ == "__main__":
    main()
