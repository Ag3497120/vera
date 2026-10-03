"""W5-d2: counts of a g3_synth run (runs.jsonl of run_bank.py): items, misroutes (undecided answered with an agent, or a route answered with another agent),
common_noun_routed (the routed agent is one of the item's wrong_agents that is a common noun: every wrong agent except 'ハル', the name of the mapped agent),
routed_any_agent, route_correct. The definitions reproduce round 1's g3_synth_counts.json from its runs_*.jsonl (checked by the same call with --check-r1).
Usage: g3_synth_counts.py <runs.jsonl>"""
import json, sys
def counts(path):
    rows = [json.loads(l) for l in open(path, encoding='utf-8')]
    c = dict(items=len(rows), misroutes=0, common_noun_routed=0, routed_any_agent=0, route_correct=0)
    for r in rows:
        exp, out = r['expect'], r['output']
        agent = out.get('agent')
        if agent is not None: c['routed_any_agent'] += 1
        if exp['decision'] == 'undecided' and agent is not None: c['misroutes'] += 1
        if exp['decision'] == 'route' and agent is not None and agent != exp['agent']: c['misroutes'] += 1
        if exp['decision'] == 'route' and agent == exp['agent']: c['route_correct'] += 1
        if agent is not None and agent in exp.get('wrong_agents', []) and agent != 'ハル': c['common_noun_routed'] += 1
    return c
if __name__ == '__main__':
    print(json.dumps(counts(sys.argv[1])))
