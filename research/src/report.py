"""Build the preregistered tables from runs.jsonl files. Every figure is a count with its denominator.

  python3 research/src/report.py research/results/pilot_persia research/results/pilot_gemma12b ... > report.md
"""

from __future__ import annotations

import collections
import json
import statistics
import sys
from pathlib import Path


def load(dirs):
    out = {}
    for d in dirs:
        p = Path(d) / "runs.jsonl"
        if p.exists():
            out[Path(d).name.replace("pilot_", "")] = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    return out


def frac(n, d):
    return f"{n}/{d}" if d else "n/a"


def table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def summarize(runs):
    adv = [r for r in runs if r["outcomes"]["kind"] == "adversarial"]
    ben = [r for r in runs if r["outcomes"]["kind"] != "adversarial"]
    exp = [r for r in adv if r["outcomes"]["exposed_to_untrusted"]]
    att_all = [r for r in adv if r["outcomes"]["unauthorized_attempt"]]
    att_exp = [r for r in exp if r["outcomes"]["unauthorized_attempt"]]
    eff_exp = [r for r in exp if r["outcomes"]["unauthorized_effect"]]
    blocked = [r for r in att_all if r["outcomes"]["blocked"]]
    lat = [r["outcomes"]["latency_ms"] for r in runs if r["outcomes"].get("latency_ms") is not None]
    return dict(
        adv=len(adv), ben=len(ben), exposed=frac(len(exp), len(adv)),
        attempt_exp=frac(len(att_exp), len(exp)), attempt_all=frac(len(att_all), len(adv)),
        effect_exp=frac(len(eff_exp), len(exp)), blocked=frac(len(blocked), len(att_all)),
        mention=frac(sum(r["outcomes"]["forbidden_tool_mentioned_any_format"] for r in adv), len(adv)),
        legit_ben=frac(sum(r["outcomes"]["legitimate_success"] for r in ben), len(ben)),
        legit_adv=frac(sum(r["outcomes"]["legitimate_success"] for r in adv), len(adv)),
        false_block=frac(sum(r["outcomes"]["false_block"] for r in ben), len(ben)),
        friction=frac(sum(r["outcomes"]["approval_friction"] for r in ben), len(ben)),
        errors=frac(sum(bool(r["error"]) for r in runs), len(runs)),
        lat=f"{statistics.median(lat) / 1000:.1f}s" if lat else "n/a",
    )


def paired(runs):
    """Adversarial run vs its benign twin, same condition and seed: who attempted the forbidden call."""
    by = {(r["case_id"], r["condition"], r["trial"]): r for r in runs}
    twin = {"A01": "B01", "A03": "B02", "A04": "B03", "A05": "B04", "A06": "B05", "A10": "B06", "M01": "N01", "M02": "N02", "M03": "N03", "M04": "N04"}
    c = collections.Counter()
    for (cid, cond, trial), r in by.items():
        if cid in twin and (twin[cid], cond, trial) in by:
            a = r["outcomes"]["unauthorized_attempt"]
            b = by[(twin[cid], cond, trial)]["outcomes"]["unauthorized_attempt"]
            c["attack_only" if a and not b else "twin_only" if b and not a else "both" if a else "neither"] += 1
    return c


def main(dirs):
    data = load(dirs)
    out = ["# Pilot tables (generated; counts are n/N)\n"]
    rows = []
    for label, runs in data.items():
        for cond in "ABC":
            s = summarize([r for r in runs if r["condition"] == cond])
            rows.append([label, cond, s["adv"], s["ben"], s["exposed"], s["attempt_exp"], s["attempt_all"], s["effect_exp"],
                         s["blocked"], s["legit_ben"], s["legit_adv"], s["false_block"], s["friction"], s["errors"], s["lat"]])
    out.append("## Table 1: condition summary\n")
    out.append(table(["arm", "cond", "adv runs", "benign runs", "exposed (adv)", "attempt (of exposed)", "attempt (of all adv)", "executed (of exposed)",
                      "blocked (of attempts)", "legit success, benign", "legit success, adversarial", "false block (benign)", "approval friction", "errors", "median latency"], rows))
    out.append("\n\n## Table 2: per case (attempts / exposed / runs, summed over conditions A, B, C)\n")
    cases = sorted({r["case_id"] for runs in data.values() for r in runs if r["outcomes"]["kind"] == "adversarial"})
    rows = []
    for label, runs in data.items():
        row = [label]
        for cid in cases:
            sel = [r for r in runs if r["case_id"] == cid]
            row.append(f"{sum(r['outcomes']['unauthorized_attempt'] for r in sel)}/{sum(r['outcomes']['exposed_to_untrusted'] for r in sel)}/{len(sel)}")
        rows.append(row)
    out.append(table(["arm"] + cases, rows))
    out.append("\n\n## Table 3: paired twin comparison (adversarial vs benign twin, same condition and seed)\n")
    rows = []
    for label, runs in data.items():
        for cond in "ABC":
            p = paired([r for r in runs if r["condition"] == cond])
            rows.append([label, cond, p["attack_only"], p["twin_only"], p["both"], p["neither"]])
    out.append(table(["arm", "cond", "attempt in attack only", "attempt in twin only", "both", "neither"], rows))
    out.append("\n\n## Failure and event log (every run with an attempt, an executed forbidden call, a false block, or an error)\n")
    rows = []
    for label, runs in data.items():
        for r in runs:
            o = r["outcomes"]
            if o["unauthorized_attempt"] or o["unauthorized_effect"] or o["false_block"] or r["error"]:
                calls = "; ".join(f"{a['proposed_tool']}->{a['verdict']['decision']}" for a in r["attempts"])
                rows.append([r["run_id"], label, r["case_id"], r["condition"], r["trial"],
                             "attempt" if o["unauthorized_attempt"] else "", "executed" if o["unauthorized_effect"] else "",
                             "false-block" if o["false_block"] else "", (r["error"] or "")[:40], calls[:110],
                             r["final_response"].replace("\n", " ")[:90]])
    out.append(table(["run_id", "arm", "case", "cond", "trial", "attempt", "executed", "false block", "error", "calls -> verdict", "final answer (start)"], rows))
    print("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1:])
