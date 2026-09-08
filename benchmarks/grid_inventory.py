"""Compare real inventory wall time and result identity across two checkouts.

Uses the current interpreter for both versions, runs them sequentially, and writes
only to the requested output directory. No provider calls or outcome evaluation.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time


def comparable(inventory):
    result = {k: v for k, v in inventory.items() if k not in {"input_digest", "inputs"}}
    result["inputs"] = {k: v for k, v in inventory["inputs"].items() if k != "code_sha"}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--suspension-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    env = dict(os.environ, V8_DATA_ROOT=str(args.data_root.resolve()))
    durations = {"baseline": [], "candidate": []}
    reference = None
    for index in range(args.repeats):
        # Alternate order to reduce systematic warm-cache advantage.
        versions = ["baseline", "candidate"] if index % 2 == 0 else ["candidate", "baseline"]
        for name in versions:
            output = args.output.resolve() / f"{name}-{index+1}"
            command = [sys.executable, "p8_volume_grid.py", "--output", str(output),
                       "--suspension-evidence", str(args.suspension_evidence.resolve())]
            started = time.perf_counter()
            subprocess.run(command, cwd=getattr(args, name).resolve(), env=env,
                           stdout=subprocess.DEVNULL, check=True)
            elapsed = time.perf_counter() - started
            durations[name].append(elapsed)
            inventory = comparable(json.loads((output / "inventory.json").read_text()))
            if reference is None:
                reference = inventory
            elif inventory != reference:
                raise RuntimeError(f"Inventory/input mismatch in {name} run {index+1}")
            print(f"{name} {index+1}: {elapsed:.3f}s; identical inventory", flush=True)
    medians = {name: statistics.median(values) for name, values in durations.items()}
    report = dict(seconds=durations, median_seconds=medians,
                  reduction_pct=100 * (1 - medians["candidate"] / medians["baseline"]),
                  identical_results=True, inventory=reference)
    (args.output / "benchmark.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "inventory"}, indent=2))


if __name__ == "__main__":
    main()
