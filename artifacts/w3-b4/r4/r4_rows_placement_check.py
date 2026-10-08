import json, sys, os
sys.path.insert(0, 'artifacts/w3-b4/tools')
import mk_data_core as C
rows = [json.loads(l) for l in open('tests/reading_soundness/ja_r10_w3b4.jsonl', encoding='utf-8')][333:]
ok = True
for r in rows:
    for w, spec in r['placement'].items():
        same = C.r7_spec(w) == spec
        ok &= same
        print(r['id'], w, 'same' if same else 'DIFFERENT', spec)
print('all same' if ok else 'MISMATCH')
