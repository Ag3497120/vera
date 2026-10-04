"""W3-c4 parity: `observe.observe_question_records(q, records, lang=...)` (in memory) must equal the `answer` and the whole output of `observe.run_entry(anchor_kind='question',
structure_path=<the same records as jsonl>, no_index=True)` (the function `vera observe` calls), for the 185 questions of W3-c2, under two placements:
(a) none (VERA_PLACEMENT unset), (b) `event_cross.default_lookup` replaced by the FilePlacement of tests/observe/question/placement_q.json (the same path that VERA_PLACEMENT takes).
Two variants of the structure: with the `lang` of each sentence, and without it. `structure.file_sha256` is the only key not compared (the in-memory one hashes the records, the file one the bytes).
Usage: parity.py [--limit N] [--out FILE]"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parents[2]
sys.path.insert(0, str(TREE))
os.environ.pop('VERA_PLACEMENT', None)
from verantyx import event_cross as EC    # noqa: E402
from verantyx import observe as O    # noqa: E402

SRC = HERE.parent / 'question'


def strip_sha(out):
    out = json.loads(json.dumps(out))
    out.get('structure', {}).pop('file_sha256', None)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--limit', type=int); ap.add_argument('--out')
    args = ap.parse_args()
    qs = [json.loads(l) for l in (SRC / 'questions.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    if args.limit: qs = qs[:args.limit]
    docs = {p.stem: [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()] for p in (SRC / 'docs').glob('QD*.jsonl')}
    fp = O.FilePlacement.from_path(str(SRC / 'placement_q.json'))
    real_default = EC.default_lookup
    lines, mismatches, total = [], 0, 0
    with tempfile.TemporaryDirectory() as tmp:
        files = {}
        for variant in ('with_lang', 'no_lang'):
            for name, rows in docs.items():
                recs = [{'id': r['id'], 'text': r['text'], **({'lang': r['lang']} if variant == 'with_lang' and r.get('lang') else {})} for r in rows]
                path = Path(tmp) / ('%s.%s.jsonl' % (name, variant))
                path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in recs), encoding='utf-8')
                files[(variant, name)] = (recs, str(path))
        for placement in ('none', 'placement_q'):
            EC.default_lookup = (lambda *a, **k: fp) if placement == 'placement_q' else real_default
            try:
                for variant in ('with_lang', 'no_lang'):
                    n_ok = 0
                    for q in qs:
                        recs, path = files[(variant, q['doc'])]
                        total += 1
                        a = O.observe_question_records(q['text'], recs, lang=q.get('lang'))
                        res = O.run_entry(anchor_text=q['text'], anchor_kind='question', lang=q.get('lang'), structure_path=path, no_index=True)
                        b = json.loads(res.stdout)
                        same = (res.exit_code == 0 and a.get('answer') == b.get('answer') and strip_sha(a) == strip_sha(b))
                        if same: n_ok += 1
                        else:
                            mismatches += 1
                            lines.append('MISMATCH placement=%s variant=%s id=%s answer_equal=%s' % (placement, variant, q['id'], a.get('answer') == b.get('answer')))
                    lines.append('placement=%-11s variant=%-9s questions=%d identical=%d' % (placement, variant, len(qs), n_ok))
            finally:
                EC.default_lookup = real_default
    lines.append('compared outputs: %d; mismatches: %d' % (total, mismatches))
    lines.append('not compared: structure.file_sha256 (records hash vs file bytes hash)')
    text = '\n'.join(lines) + '\n'
    if args.out: Path(args.out).write_text(text, encoding='utf-8')
    print(text, end='')
    return 1 if mismatches else 0


if __name__ == '__main__':
    sys.exit(main())
