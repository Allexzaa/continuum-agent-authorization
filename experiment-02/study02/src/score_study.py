"""Separate scoring process: the only place (besides tests) that reads oracle/*.jsonl.

  python3 study02/src/score_study.py --cases study02/cases/dev_cases.jsonl --oracle study02/oracle/dev_oracle.jsonl --runs RUNS.jsonl --out SCORED.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluator import score_run
from schemas import Case2, OracleEntry


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--oracle", required=True)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--allow-diagnostic", action="store_true", help="score runs whose planner mode is not the declared think_off (development and diagnostic runs only)")
    a = ap.parse_args()
    cases = {c["case_id"]: Case2.from_dict(c) for c in [json.loads(l) for l in Path(a.cases).read_text(encoding="utf-8").splitlines() if l.strip()]}
    oracle = {o["case_id"]: OracleEntry.from_dict(o) for o in [json.loads(l) for l in Path(a.oracle).read_text(encoding="utf-8").splitlines() if l.strip()]}
    n = 0
    with Path(a.out).open("w", encoding="utf-8") as sink:
        for path in a.runs:
            for line in Path(path).read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                mode = r.get("planner_mode", "production")        # records written before the field existed ran the production planner
                if mode != "think_off" and not a.allow_diagnostic:
                    raise SystemExit(f"run {r['run_id']} used planner mode {mode!r}; the declared Study 02 loop is think_off (pass --allow-diagnostic for development or diagnostic runs)")
                s = score_run(cases[r["case_id"]], oracle[r["case_id"]], r)
                sink.write(json.dumps({"run_id": r["run_id"], "source": path, "case_id": r["case_id"], "condition": r["condition"], "trial": r["trial"],
                                       "model": r["model"].get("model"), "latency_ms": r["latency_ms"], "final_response": r["final_response"], **s}, ensure_ascii=False) + "\n")
                n += 1
    print(f"scored {n} runs -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
