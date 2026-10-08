"""W3-c7 round 4: revise the expectations of the 41 rows (auditor ruling 1, 2026-10-05 09:03:42 +0900).
Input: the copy of the round-1 freeze (artifacts/w3-c7/frozen_r1/), never the current files. Idempotent.
--check: write nothing, only compare the current files with what this script would write (exit 0/1)."""
import hashlib
import json
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parent.parent.parent.parent
ART = TREE / 'artifacts' / 'w3-c7'
SRC = ART / 'frozen_r1'
DST = TREE / 'tests' / 'reading_soundness'
NAMES = ('multi', 'te', 'quote', 'sharing', 'anaphora')
DERIVED = 'CLAUSE_FORM_NOT_READ:PLACEMENT_PREDICATE_POSSIBLY_DERIVED'
WHY = 'derived_gate_k117_5'
KEYS = ('behavior', 'entry_expect', 'w3c7_expect', 'structure_expect', 'expect', 'abstain_why')


def die(msg):
    print('ERROR', msg)
    sys.exit(1)


def main():
    check = '--check' in sys.argv[1:]
    # 1. the copy must be the round-1 freeze
    for line in (ART / 'data_freeze.sha256').read_text().splitlines():
        h, p = line.split()
        got = hashlib.sha256((SRC / Path(p).name).read_bytes()).hexdigest()
        if got != h:
            die('frozen_r1 copy differs from data_freeze.sha256: ' + p)
    # 2. the 41 ids
    tsv = {l.split('\t')[0] for l in (ART / 'proposed_expectation_changes.tsv').read_text(encoding='utf-8').splitlines() if l.strip()}
    chk = json.loads((ART / 'data_check_frozen.json').read_text(encoding='utf-8'))
    mism = {r['id'] for r in chk['rows'] if r['entry_mismatch'] or r['expect_mismatch'] or r['structure_mismatch']}
    if tsv != mism or len(tsv) != 41:
        die('id sets differ: tsv=%d mismatch=%d' % (len(tsv), len(mism)))
    out = {}
    records = []
    md = []
    n_read = n_abs = 0
    for name in NAMES:
        text = (SRC / ('w3c7_%s.jsonl' % name)).read_text(encoding='utf-8')
        lines = [l for l in text.splitlines() if l.strip()]
        new_lines = []
        for l in lines:
            row = json.loads(l)
            if row['id'] in tsv:
                before = json.loads(l)
                if row['entry_expect'] == 'read':
                    n_read += 1
                    row['behavior'] = 'abstain'
                    row['entry_expect'] = 'abstain'
                    row['structure_expect'] = None
                    row['expect'] = {'readable': False, 'clauses': [], 'relations': [], 'must_not': before['expect']['must_not']}
                else:
                    n_abs += 1
                row['w3c7_expect'] = DERIVED
                row['abstain_why'] = WHY
                changed = [k for k in before if before[k] != row[k]]
                assert set(changed) <= set(KEYS)
                assert tuple(before) == tuple(row)
                records.append({'id': row['id'], 'file': 'w3c7_%s.jsonl' % name, 'input': row['input'], 'before': before, 'after': row, 'changed_keys': changed})
                bj = json.dumps({k: before[k] for k in changed}, ensure_ascii=False)
                aj = json.dumps({k: row[k] for k in changed}, ensure_ascii=False)
                md.append('- `%s`（`w3c7_%s.jsonl`）`%s`: 前 `%s` → 後 `%s`' % (row['id'], name, row['input'], bj, aj))
                new_lines.append(json.dumps(row, ensure_ascii=False))
            else:
                new_lines.append(l)
                assert json.dumps(json.loads(l), ensure_ascii=False) == l
        out[name] = '\n'.join(new_lines) + '\n'
    if (n_read, n_abs) != (32, 9) or len(records) != 41:
        die('counts: read=%d abstain=%d' % (n_read, n_abs))
    rec_text = ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records)
    md_text = '\n'.join(md) + '\n'
    files = {DST / ('w3c7_%s.jsonl' % n): out[n] for n in NAMES}
    files[ART / 'expectation_changes.r4.jsonl'] = rec_text
    files[ART / 'expectation_changes.r4.md'] = md_text
    if check:
        bad = [str(p) for p, t in files.items() if not p.exists() or p.read_text(encoding='utf-8') != t]
        if bad:
            print('DIFFERENT', bad)
            sys.exit(1)
        print('OK current files equal the script output')
        return
    for p, t in files.items():
        p.write_text(t, encoding='utf-8')
    print('wrote', len(files), 'files; revised read=%d abstain=%d' % (n_read, n_abs))


main()
