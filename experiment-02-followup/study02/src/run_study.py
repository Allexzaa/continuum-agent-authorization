"""Runner. Writes immutable run records WITHOUT scoring (scoring is a separate process: score_study.py, which alone reads the oracle).

  python3 study02/src/run_study.py --cases study02/cases/dev_cases.jsonl --model gemma4:12b --trials 2 --out study02/results/dev_gemma
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests

import adapter
from adapter import MAX_TOKENS, PINNED_OPTIONS, SEED_BASE, Study2Adapter, load_llm_module, sha, system_prompt
from policies import CONDITIONS
from schemas import Case2

STUDY = Path(__file__).resolve().parents[1]
REPO = STUDY.parent


def full_hashes() -> dict:
    files = [p for d in ("agent_snapshot", "src") for p in sorted((STUDY / d).rglob("*")) if p.is_file() and "__pycache__" not in p.parts and p.suffix in {".py", ".md"}]
    return {str(p.relative_to(STUDY)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def git_state() -> tuple[str, bool]:
    def run(*a):
        return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True).stdout.strip()
    return run("rev-parse", "HEAD"), bool(run("status", "--porcelain", "--", "study02"))


def ollama_identity(host: str, model: str) -> dict:
    try:
        tags = requests.get(f"{host}/api/tags", timeout=10).json()["models"]
        digest = next((m["digest"] for m in tags if m["name"] == model), None)
        show = requests.post(f"{host}/api/show", json={"model": model}, timeout=30).json()
        return {"model": model, "digest": digest, "details": show.get("details"), "parameters": show.get("parameters"),
                "template_sha256": sha(show.get("template", "")), "runtime_version": requests.get(f"{host}/api/version", timeout=10).json().get("version")}
    except Exception as exc:        # recorded, never silent
        return {"model": model, "error": f"{type(exc).__name__}: {exc}"}


def completed_cells(path: Path) -> set[tuple]:
    """Cells (case_id, condition, trial) already written to runs.jsonl; a truncated last line (interrupted write) is ignored."""
    done = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            done.add((r["case_id"], r["condition"], r["trial"]))
    return done


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--conditions", nargs="+", default=CONDITIONS)
    ap.add_argument("--trials", type=int, default=2)
    ap.add_argument("--trial-start", type=int, default=0)
    ap.add_argument("--model", required=True)
    ap.add_argument("--host", default="http://127.0.0.1:11434")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--order-seed", type=int, default=7)
    ap.add_argument("--stop-on-read", choices=["on", "off"], default="on")
    ap.add_argument("--planner", choices=["production", "off", "think_off"], default="think_off",
                    help="think_off is the DECLARED Study 02 loop (amendment A3: the planner call turns thinking off so a thinking model can return its plan); "
                         "production and off are diagnostics only and are rejected by score_study.py unless --allow-diagnostic")
    ap.add_argument("--resume", action="store_true", help="skip cells already present in OUT/runs.jsonl (the shuffled order is unchanged, so an interrupted run continues where it stopped)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cases = [Case2.from_dict(json.loads(l)) for l in Path(args.cases).read_text(encoding="utf-8").splitlines() if l.strip()]
    cases = [c for c in cases if not args.only or c.case_id in args.only]
    cells = [(c, cond, t) for c in cases for cond in args.conditions for t in range(args.trial_start, args.trial_start + args.trials)]
    random.Random(args.order_seed).shuffle(cells)          # randomized execution order, recorded
    if args.resume:
        done = completed_cells(out / "runs.jsonl")
        print(f"resume: {len(done)} cells already complete", flush=True)
    else:
        done = set()
    prompt = system_prompt()
    commit, dirty = git_state()
    hashes, identity = full_hashes(), ollama_identity(args.host, args.model)
    ad = Study2Adapter(load_llm_module(), args.model, args.host)
    with (out / "runs.jsonl").open("a", encoding="utf-8") as sink:
        for i, (case, cond, trial) in enumerate(cells, 1):
            if (case.case_id, cond, trial) in done:
                continue
            print(f"[{i}/{len(cells)}] {case.case_id} {cond} trial={trial}", flush=True)
            response, rec, world, attempts, error, latency = ad.run(case, cond, trial, prompt, args.stop_on_read == "on", args.planner)
            record = {
                "run_id": uuid.uuid4().hex[:12], "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "case_id": case.case_id, "case_hash": case.case_hash(), "condition": cond, "trial": trial, "order_index": i, "order_seed": args.order_seed,
                "git_commit": commit, "git_dirty": dirty, "code_sha256": hashes, "model": identity,
                "prompt_sha256": sha(prompt), "options": dict(PINNED_OPTIONS, seed=SEED_BASE + trial), "max_tokens": MAX_TOKENS, "stop_on_read": args.stop_on_read, "planner_mode": args.planner,
                "attempts": attempts, "proposed_calls": ad.proposed_calls(rec, set(case.available_tools)),
                "model_rounds": rec.model_rounds, "nonstream_calls": rec.nonstream, "requests": rec.requests, "events": rec.events,
                "initial_state": world.initial_snapshot(), "final_state": world.snapshot(), "effects": [e.__dict__ for e in world.effects],
                "final_response": response, "latency_ms": latency, "error": error,
            }
            sink.write(json.dumps(record, ensure_ascii=False) + "\n")
            sink.flush()
    print(f"wrote {len(cells)} runs -> {out / 'runs.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
