"""Study 02b runner: Study 02's harness (study02/src, unchanged) with --max-runs (for the automatic early check) and hashes of both source trees.
  python3 study02b/src/run_followup.py --cases CASES --model M --out DIR [--conditions ...] [--trials 2] [--max-runs N] [--resume]
Writes unscored run records only (scoring: study02/src/score_study.py with the Study 02b oracle)."""
from __future__ import annotations
import argparse, hashlib, json, random, sys, uuid
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "study02" / "src"))
import run_study as rs                                    # noqa: E402  (study02/src/run_study.py)
from adapter import MAX_TOKENS, PINNED_OPTIONS, SEED_BASE, Study2Adapter, load_llm_module, sha, system_prompt   # noqa: E402
from schemas import Case2                                 # noqa: E402


def tree_hashes() -> dict:
    out = {}
    for d in ("study02/agent_snapshot", "study02/src", "study02b/src"):
        for p in sorted((ROOT / d).rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and p.suffix in {".py", ".md"}:
                out[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def git_state():
    import subprocess
    run = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True).stdout.strip()
    return run("rev-parse", "HEAD"), bool(run("status", "--porcelain", "--", "study02", "study02b"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True); ap.add_argument("--model", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--conditions", nargs="+", default=["BPLUS", "C2", "C2COARSE"]); ap.add_argument("--trials", type=int, default=2)
    ap.add_argument("--max-runs", type=int, default=0); ap.add_argument("--resume", action="store_true"); ap.add_argument("--order-seed", type=int, default=11)
    ap.add_argument("--host", default="http://127.0.0.1:11434")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    cases = [Case2.from_dict(json.loads(l)) for l in Path(a.cases).read_text(encoding="utf-8").splitlines() if l.strip()]
    cells = [(c, cond, t) for c in cases for cond in a.conditions for t in range(a.trials)]
    random.Random(a.order_seed).shuffle(cells)
    done = rs.completed_cells(out / "runs.jsonl") if a.resume else set()
    todo = [x for x in cells if (x[0].case_id, x[1], x[2]) not in done]
    if a.max_runs:
        todo = todo[:a.max_runs]
    prompt, (commit, dirty), hashes, identity = system_prompt(), git_state(), tree_hashes(), rs.ollama_identity(a.host, a.model)
    ad = Study2Adapter(load_llm_module(), a.model, a.host)
    print(f"{len(todo)} runs to do ({len(done)} already complete)", flush=True)
    with (out / "runs.jsonl").open("a", encoding="utf-8") as sink:
        for i, (case, cond, trial) in enumerate(todo, 1):
            print(f"[{i}/{len(todo)}] {case.case_id} {cond} t{trial}", flush=True)
            resp, rec, world, attempts, error, latency = ad.run(case, cond, trial, prompt, True, "think_off")
            r = {"run_id": uuid.uuid4().hex[:12], "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "case_id": case.case_id, "case_hash": case.case_hash(),
                 "condition": cond, "trial": trial, "order_seed": a.order_seed, "git_commit": commit, "git_dirty": dirty, "code_sha256": hashes, "model": identity,
                 "prompt_sha256": sha(prompt), "options": dict(PINNED_OPTIONS, seed=SEED_BASE + trial), "max_tokens": MAX_TOKENS, "stop_on_read": "on", "planner_mode": "think_off",
                 "attempts": attempts, "proposed_calls": ad.proposed_calls(rec, set(case.available_tools)), "model_rounds": rec.model_rounds, "nonstream_calls": rec.nonstream,
                 "requests": rec.requests, "events": rec.events, "initial_state": world.initial_snapshot(), "final_state": world.snapshot(), "effects": [e.__dict__ for e in world.effects],
                 "final_response": resp, "latency_ms": latency, "error": error}
            sink.write(json.dumps(r, ensure_ascii=False) + "\n"); sink.flush()
    print("done", flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
