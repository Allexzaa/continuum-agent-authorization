"""Study 02b supplementary tables (descriptive; not preregistered endpoints). Run from the repo root after scoring."""
import json, math, statistics, collections
load = lambda p: [json.loads(l) for l in open(p)]
cases = {c['case_id']: c for c in load('study02b/cases/heldout_cases.jsonl')}
def cp(k, n, a=0.05):  # exact Clopper-Pearson via bisection on the binomial cdf
    def cdf(x, p): return sum(math.comb(n, i) * p**i * (1-p)**(n-i) for i in range(0, x+1))
    lo = 0.0; hi = 1.0
    if k > 0:
        l, h = 0.0, 1.0
        for _ in range(60):
            m = (l+h)/2
            if 1 - cdf(k-1, m) < a/2: l = m
            else: h = m
        lo = h
    if k < n:
        l, h = 0.0, 1.0
        for _ in range(60):
            m = (l+h)/2
            if cdf(k, m) > a/2: l = m
            else: h = m
        hi = l
    else: hi = 1.0
    return lo, hi
for model in ('gemma', 'persia'):
    S = load(f'study02b/results/held1_{model}_scored.jsonl') + load(f'study02b/results/heldtok_{model}_scored.jsonl')
    print(f'\n==== {model}: benign template-level completion by type (exact 95% CI) and median latency (s)')
    for arm in ('BPLUS', 'C2', 'C2COARSE', 'C2TOKEN'):
        row = []
        for t in ('M', 'S'):
            ids = [c for c, v in cases.items() if v['kind'] == 'benign_twin' and v['family'][-1] == t]
            k = sum(all(s['benign_complete'] for s in S if s['case_id'] == c and s['condition'] == arm) for c in ids)
            lo, hi = cp(k, len(ids)); row.append(f'type {t}: {k}/{len(ids)} [{lo*100:.1f}, {hi*100:.1f}]')
        lat = [s['latency_ms']/1000 for s in S if s['condition'] == arm]
        print(f'  {arm:9s}', ' | '.join(row), f'| median latency {statistics.median(lat):.1f}s')
    print(f'---- {model}: attacked templates with an unauthorized effect, by type')
    for arm in ('BPLUS', 'C2', 'C2COARSE', 'C2TOKEN'):
        row = []
        for t in ('M', 'S'):
            ids = [c for c, v in cases.items() if v['kind'] == 'attack' and v['family'][-1] == t]
            k = sum(any(s['unauthorized_effect'] for s in S if s['case_id'] == c and s['condition'] == arm) for c in ids)
            row.append(f'type {t}: {k}/{len(ids)}')
        print(f'  {arm:9s}', ' | '.join(row))
# residual C2 leaks in persia
S = load('study02b/results/held1_persia_scored.jsonl'); R = {r['run_id']: r for r in load('study02b/results/held1_persia/runs.jsonl')}
print('\n---- persia C2 residual leaks (outgoing body of the send that reached the world)')
for s in S:
    if s['condition'] == 'C2' and s['unauthorized_effect']:
        sends = [a for a in R[s['run_id']]['attempts'] if a['tool'] == 'send_email' and a['verdict']['decision'] == 'allow']
        print(' ', s['case_id'], 'trial', s['trial'], '|', json.dumps(sends[0]['args']['body'])[:220] if sends else 'no allowed send')
# attacked: payload exposure and attempted attacker action
print('\n---- attack exposure (injected text reached the model), unconditional / by model')
for model in ('gemma', 'persia'):
    S = load(f'study02b/results/held1_{model}_scored.jsonl')
    att = [s for s in S if cases[s['case_id']]['kind'] == 'attack']
    print(f'  {model}: exposed {sum(s["attack_exposed"] for s in att)}/{len(att)}; proposals {sum(bool(s["unauthorized_proposal"]) for s in att)}/{len(att)}')
