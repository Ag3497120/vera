"""Summary table of results/base_*.json -> results/summary.md (and stdout)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import grade as G
conds = ['0', '300', '300full', '3000', '30000', '100000', '269710']
L = ['| cond | path | correct/wrong/abstain (60) | loose | fict answered /20 | attr answered /10 | gold_held | n_sent | cores | file |',
     '|---|---|---|---|---|---|---|---|---|---|']
for c in conds:
    p = os.path.join(HERE, 'results', f'base_{c}.json')
    if not os.path.exists(p):
        continue
    d = json.load(open(p))
    for path in ('a1', 'a2', 'a2raw', 'a3', 'b1', 'b2'):
        R = [r for r in d['rows'] if r['path'] == path]
        if not R:
            continue
        t = G.tally(R)
        L.append(f"| {c} | {path} | {t['correct']}/{t['wrong']}/{t['abstain']} | {t['loose']} | {t['fict_answered']} | "
                 f"{t['attr_answered']} | {t['gold_held']} | {d['n_sent']} | {d['n_cores']} | results/base_{c}.json |")
s = '\n'.join(L)
open(os.path.join(HERE, 'results', 'summary.md'), 'w').write(s + '\n')
print(s)
