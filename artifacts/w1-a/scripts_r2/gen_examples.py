# writes artifacts/w1-a/semantic_read_examples.txt: the 5 commands of X4, then every input of the two self-made samples, one process per input (cwd = scratch dir)
import json, subprocess, sys
W='/Users/motonisihikoudai/Projects/vera-impl/wt/W1-a-S'
S='/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W1-a2-impl2'
def run(arg):
    p=subprocess.run([S+'/py.sh', W, '-m', 'verantyx.semantic_read', arg], cwd=S, capture_output=True, text=True)
    return p.stdout.rstrip('\n'), p.returncode
out=['# X4: python -m verantyx.semantic_read (cwd=$WD, 木=$W)']
for arg in ['--text=先生が生徒に地図を渡した。','--text=ありがとう。','--text=Ann sent the report to Ben.','--text=']:
    o,c=run(arg); out+= [f'$ python -m verantyx.semantic_read {arg}', o, f'exit={c}']
p=subprocess.run([S+'/py.sh', W, '-m', 'verantyx.semantic_read', '--text=犬が走った。', '--lang', 'en'], cwd=S, capture_output=True, text=True)
out+=['$ python -m verantyx.semantic_read --text=犬が走った。 --lang en', p.stdout.rstrip('\n'), f'exit={p.returncode}']
for name in ('B1_v2','B1_v2_r2'):
    items=[json.loads(l) for l in open(f'{W}/tests/bank_score/fixtures/{name}/items.jsonl',encoding='utf-8')]
    out+=['', f'# the self-made B1 v2 sample, one process per input (tests/bank_score/fixtures/{name}/items.jsonl)']
    for it in items:
        o,c=run('--text='+it['input']); out+=[f"## {it['id']} {it['input']}", o, f'exit={c}']
open(W+'/artifacts/w1-a/semantic_read_examples.txt','w',encoding='utf-8').write('\n'.join(out)+'\n')
print(len(out))
