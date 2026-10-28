"""Run locked cases under conditions A/B/C. One immutable JSONL line per run; failures are kept.

  voice-agent/.venv/bin/python research/src/run_eval.py \
      --cases research/cases/smoke.jsonl --conditions B --trials 1 \
      --model persia-f16:latest --out research/results/smoke
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from adapter import (MAX_TOKENS, PINNED_OPTIONS, REPO_ROOT, SEED_BASE, PersiaAdapter, build_prompts,  # noqa: E402
                     load_llm_module, sha)
from schemas import Case, RunRecord  # noqa: E402
from score_runs import score, write_summary_csv  # noqa: E402


def code_hashes() -> dict:
    """voice-agent/ is gitignored, so git does not capture Persia's code: hash it into every run record."""
    files = {"llm_py": REPO_ROOT / "voice-agent" / "pipeline" / "llm.py", "soul_md": REPO_ROOT / "voice-agent" / "config" / "SOUL.md"}
    out = {k: sha(v.read_text(encoding="utf-8")) for k, v in files.items()}
    out["harness"] = sha("".join(f.read_text(encoding="utf-8") for f in sorted((REPO_ROOT / "research" / "src").glob("*.py"))))
    return out


def git_state() -> tuple[str, bool]:
    def run(*a):
        return subprocess.run(["git", "-C", str(REPO_ROOT), *a], capture_output=True, text=True).stdout.strip()
    return run("rev-parse", "--short", "HEAD"), bool(run("status", "--porcelain", "--", "research", "voice-agent"))


def load_cases(path: Path) -> list[Case]:
    return [Case.from_dict(json.loads(l)) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", nargs="+", required=True)
    ap.add_argument("--conditions", nargs="+", default=["A", "B", "C"])
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--trial-start", type=int, default=0, help="first trial index (seed = SEED_BASE + trial)")
    ap.add_argument("--model", default="persia-f16:latest")
    ap.add_argument("--host", default="http://127.0.0.1:11434")
    ap.add_argument("--loop-format", choices=["fixed", "legacy"], default="fixed")
    ap.add_argument("--stop-on-read", choices=["on", "off"], default="on", help="off = ablate the F-014 stop-on-read fix")
    ap.add_argument("--only", nargs="*", help="restrict to these case_ids")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cases = [c for f in args.cases for c in load_cases(Path(f)) if not args.only or c.case_id in args.only]
    prompt_a, prompt_b = build_prompts()
    prompts = {"A": prompt_a, "B": prompt_b, "C": prompt_b}   # C = B + enforcement
    commit, dirty = git_state()
    hashes = code_hashes()
    adapter = PersiaAdapter(load_llm_module(), args.model, args.host)

    runs_path = out / "runs.jsonl"
    runs = []
    total = len(cases) * len(args.conditions) * args.trials
    i = 0
    with runs_path.open("a", encoding="utf-8") as sink:
        for case in cases:
            for cond in args.conditions:
                for trial in range(args.trial_start, args.trial_start + args.trials):
                    i += 1
                    print(f"[{i}/{total}] {case.case_id} cond={cond} trial={trial}", flush=True)
                    response, rec, world, attempts, error, latency_ms = adapter.run(case, cond, trial, prompts[cond], args.loop_format, args.stop_on_read == "on")
                    if rec.blocked_network:
                        error = (error + " | " if error else "") + f"NETWORK_VIOLATION {rec.blocked_network}"
                    record = RunRecord(
                        run_id=uuid.uuid4().hex[:12], case_id=case.case_id, condition=cond, trial=trial,
                        timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        fixture_hash=case.fixture_hash(), git_commit=commit, git_dirty=dirty,
                        model={"model_id": args.model, "prompt_version": cond if cond != "C" else "B",
                               "prompt_hash": sha(prompts[cond]), "options": dict(PINNED_OPTIONS, seed=SEED_BASE + trial),
                               "max_tokens": MAX_TOKENS, "code_hashes": hashes, "loop_format": args.loop_format, "stop_on_read": args.stop_on_read,
                               "prompt_eval_counts": [r["prompt_eval_count"] for r in rec.model_rounds]},
                        attempts=attempts,
                        proposed_calls=adapter.proposed_calls(rec, set(case.available_mock_tools)),
                        suppressed_events=[e for e in rec.events if "suppressed" in e["type"] or e["type"].startswith("plan")],
                        model_rounds=[{**r, "content": r["content"][:2000]} for r in rec.model_rounds],
                        effects=[e.__dict__ for e in world.effects],
                        final_response=response,
                        outcomes={"latency_ms": latency_ms},
                        error=error,
                    )
                    d = json.loads(record.to_json())
                    d["outcomes"] = {**d["outcomes"], **score(case, d)}
                    sink.write(json.dumps(d, ensure_ascii=False) + "\n")
                    sink.flush()
                    runs.append(d)
    write_summary_csv(runs, out / "summary.csv")
    print(f"wrote {len(runs)} runs -> {runs_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
