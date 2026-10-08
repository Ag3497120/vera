"""Round 2: the inputs of the entry dumps = artifacts/w3-b4/entry_inputs.txt, then the sentences of tests/reading_soundness/w3b3_{connective,parallel,relative,w1a4}.jsonl, then ja_r12.jsonl
(duplicates removed, this order = the order of round 1; the first 3,851 lines are the file of round 1). Writes artifacts/w1-a5/r2/entry_inputs.txt (JSON lines {text, source}).
Usage: python mk_entry_inputs_r2.py   (from the tree)"""
import json
import pathlib

TREE = pathlib.Path(__file__).resolve().parents[3]
rows = [json.loads(l) for l in (TREE / 'artifacts' / 'w3-b4' / 'entry_inputs.txt').read_text(encoding='utf-8').splitlines() if l.strip()]
seen = {r['text'] for r in rows}
for src in ('w3b3_connective.jsonl', 'w3b3_parallel.jsonl', 'w3b3_relative.jsonl', 'w3b3_w1a4.jsonl', 'ja_r12.jsonl'):
    for line in (TREE / 'tests' / 'reading_soundness' / src).read_text(encoding='utf-8').splitlines():
        if not line.strip(): continue
        text = json.loads(line)['text']
        if text in seen: continue
        seen.add(text); rows.append({'text': text, 'source': src})
(TREE / 'artifacts' / 'w1-a5' / 'r2' / 'entry_inputs.txt').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
print(len(rows))
