"""W5-d2: notes on the r7 run of the 185 questions: FALSE_NONE ids that were not FALSE_NONE without VERA_PLACEMENT (with the excluded reasons), FILLED/TIE rows that
have a TYPE_UNCHECKED filler beside the answer, and the attack question EN08-01 (A01). Usage: g2_r7_notes.py <r2 dir> <r1 dir>"""
import json, sys
r2, r1 = sys.argv[1:3]
def rows(p): return {json.loads(l)['id']: json.loads(l) for l in open(p, encoding='utf-8')}
for mode in ('place', 'noplace'):
    base = rows(f'{r1}/g2_185_{mode}.jsonl'); now = rows(f'{r2}/g2_185_{mode}_r7.jsonl')
    print(f'== 185 {mode}: FALSE_NONE now but not without VERA_PLACEMENT')
    for k, v in now.items():
        if v['class'] == 'FALSE_NONE' and base[k]['class'] != 'FALSE_NONE':
            print(' ', k, v['status'], 'excluded=', v['excluded'], 'before:', base[k]['status'], base[k]['class'])
    print(f'== 185 {mode}: FALSE_NONE in both')
    print(' ', [k for k, v in now.items() if v['class'] == 'FALSE_NONE' and base[k]['class'] == 'FALSE_NONE'])
    print(f'== 185 {mode}: FILLED/TIE with a TYPE_UNCHECKED excluded filler beside')
    print(' ', [(k, v['status']) for k, v in now.items() if v['status'] in ('FILLED', 'TIE') and any(e['reason'] == 'TYPE_UNCHECKED' for e in v['excluded'])])
atk = rows(f'{r2}/g2_attack120_r7.jsonl')
print('== attack 120 (r7)')
print('  EN08-01', atk.get('EN08-01'))
print('  FILLED/TIE with a TYPE_UNCHECKED beside:', [(k, v['status'], v['fillers'], v['excluded']) for k, v in atk.items() if v['status'] in ('FILLED', 'TIE') and any(e['reason'] == 'TYPE_UNCHECKED' for e in v['excluded'])])
print('  unchecked fillers in FILLED/TIE:', sum(v['unchecked_fillers'] for v in atk.values()))
