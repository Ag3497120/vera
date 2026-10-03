"""W3-c2: run every question of a question file through the entry (`verantyx.observe.run_entry`, the function `python -m verantyx.cli observe` calls) and score it.

    python tests/observe/question/run_questions.py --questions Q.jsonl --docs DIR --placement-dir DIR --out O.jsonl --score S.json --timing T.json [--corrections C.jsonl]

`--questions`: one object per line {id, doc, lang, text, hole?, placement?, direction?, truth?}. `--docs`: DIR/<doc>.jsonl is the structure ({id, text, lang} per line).
A question whose `truth` is null (or absent) is not scored: the report lists its status and, for FILLED / TIE, the fillers and the evidence ids (the form of a bank
without answers). Classification (docs/OBSERVATION.md 事前登録 D17, with the補足 of the evidence): CORRECT / WRONG / FALSE_NONE / ABSTAINED (see classify()).
Nothing here reads the data's expectations before the observation: `truth` is only compared after the entry has answered.
"""
import argparse
import json
import os
import sys
import time
import unicodedata
from collections import Counter, OrderedDict
from pathlib import Path

TREE = Path(__file__).resolve().parents[3]
if str(TREE) not in sys.path: sys.path.insert(0, str(TREE))

from verantyx import observe as O    # noqa: E402

NFKC = lambda s: unicodedata.normalize('NFKC', s)
FILLED_LIKE = ('FILLED', 'TIE')
NONE_LIKE = ('NO_ATTESTED_CELL', 'TYPE_EXCLUDED_ALL')


def classify(truth, status, answer):
    """(class, detail). `answer` is the `answer` object of the output (None when the output has none)."""
    if truth is None: return 'UNSCORED', None
    kind = truth['kind']
    fillers = {NFKC(f['surface']) for f in (answer or {}).get('fillers', [])}
    evidence = {e['reading'] for f in (answer or {}).get('fillers', []) for e in f['evidence']}
    want_f = {NFKC(x) for x in truth.get('fillers', [])}
    want_e = set(truth.get('evidence', []))
    if kind in ('YESNO', 'ILLFORMED'):
        return ('WRONG', 'answered a question that has no answer') if status in FILLED_LIKE else ('CORRECT', None)
    if status in FILLED_LIKE:
        ok_status = (status == 'FILLED') if kind == 'ONE' else (status == 'TIE') if kind == 'SPLIT' else False
        if kind == 'NONE': return 'WRONG', 'answered a question the document does not answer'
        if ok_status and fillers == want_f and evidence == want_e: return 'CORRECT', None
        return 'WRONG', {'got_status': status, 'got_fillers': sorted(fillers), 'got_evidence': sorted(evidence), 'want_fillers': sorted(want_f), 'want_evidence': sorted(want_e)}
    if kind == 'NONE': return ('CORRECT', None) if status == 'NO_ATTESTED_CELL' else ('ABSTAINED', None)
    if status in NONE_LIKE: return 'FALSE_NONE', None
    return 'ABSTAINED', None


def run_one(q, docs_dir, placement_dir):
    structure = Path(docs_dir) / (q['doc'] + '.jsonl')
    placement = str(Path(placement_dir) / q['placement']) if q.get('placement') else None
    t0 = time.perf_counter()
    res = O.run_entry(anchor_text=q['text'], anchor_kind='question', lang=q.get('lang'), direction=q.get('direction') or '',
                      structure_path=str(structure), no_index=True, placement_path=placement)
    return res, time.perf_counter() - t0


def abstain_reasons(out):
    a = out.get('answer')
    if a is None: return ['NO_ANSWER_KEY:' + str((out.get('abstain') or {}).get('reason'))]
    if a['status'] == 'QUESTION_NOT_READ':
        return ['READ:' + r for r in (((out.get('abstain') or {}).get('detail') or {}).get('reasons') or [])] or ['READ:unknown']
    return [a['status']]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--questions', required=True); ap.add_argument('--docs', required=True); ap.add_argument('--placement-dir', default='.')
    ap.add_argument('--out', required=True); ap.add_argument('--score', required=True); ap.add_argument('--timing', required=True)
    ap.add_argument('--corrections')
    args = ap.parse_args(argv)
    qs = [json.loads(l) for l in open(args.questions, encoding='utf-8') if l.strip()]
    corr = {}
    if args.corrections and os.path.exists(args.corrections):
        for l in open(args.corrections, encoding='utf-8'):
            if l.strip():
                c = json.loads(l); corr[c['id']] = c['after']
    load = os.getloadavg()[0]
    outs, rows, timing = [], [], OrderedDict()
    for q in qs:
        res, secs = run_one(q, args.docs, args.placement_dir)
        outs.append({'id': q['id'], 'exit_code': res.exit_code, 'stdout': res.stdout, 'error': res.error})
        out = json.loads(res.stdout) if res.stdout else {}
        answer = out.get('answer')
        status = answer['status'] if answer else 'NO_ANSWER_KEY'
        row = {'id': q['id'], 'doc': q['doc'], 'lang': q.get('lang'), 'hole': q.get('hole'), 'text': q['text'], 'status': status, 'exit_code': res.exit_code,
               'truth_kind': (q.get('truth') or {}).get('kind'), 'reasons': abstain_reasons(out), 'secs': secs}
        for name, truth in (('as_frozen', q.get('truth')), ('corrected', dict(q['truth'], **corr[q['id']]) if q['id'] in corr and q.get('truth') else q.get('truth'))):
            cls, detail = classify(truth, status, answer)
            row[name] = cls
            if name == 'as_frozen': row['detail'] = detail
        if answer:
            row['fillers'] = [{'surface': f['surface'], 'evidence': [e['reading'] for e in f['evidence']]} for f in answer['fillers']]
            row['structure'] = {k: answer['structure'][k] for k in ('unread', 'crosses_compared', 'crosses_matched')}
            row['extending'] = len(answer['structure']['extending'])
            row['answer_reasons'] = answer['reasons']
        rows.append(row)
        timing[q['id']] = secs
    Path(args.out).write_text(''.join(json.dumps(o, ensure_ascii=False) + '\n' for o in outs), encoding='utf-8')

    def tally(select, key):
        t = Counter(r[key] for r in rows if select(r))
        return {c: t.get(c, 0) for c in ('CORRECT', 'WRONG', 'FALSE_NONE', 'ABSTAINED', 'UNSCORED')}

    totals = dict(tally(lambda r: True, 'as_frozen'), n=len(rows))
    score = OrderedDict()
    score['totals'] = totals
    score['totals_with_corrections'] = dict(tally(lambda r: True, 'corrected'), n=len(rows), corrections_applied=sorted(corr))
    score['by_hole'] = {k: tally(lambda r, k=k: r['hole'] == k, 'as_frozen') for k in sorted({str(r['hole']) for r in rows})}
    score['by_lang'] = {k: tally(lambda r, k=k: r['lang'] == k, 'as_frozen') for k in sorted({str(r['lang']) for r in rows})}
    score['by_truth_kind'] = {k: tally(lambda r, k=k: r['truth_kind'] == k, 'as_frozen') for k in sorted({str(r['truth_kind']) for r in rows})}
    score['status_counts'] = dict(sorted(Counter(r['status'] for r in rows).items()))
    abst = {}
    for r in rows:
        if r['as_frozen'] == 'ABSTAINED':
            for reason in r['reasons']: abst.setdefault(str(r['hole']), Counter())[reason] += 1
    score['abstained_reasons_by_hole'] = {h: dict(sorted(c.items())) for h, c in sorted(abst.items())}
    keep = ('id', 'hole', 'truth_kind', 'text', 'status', 'detail', 'reasons', 'fillers', 'structure', 'extending', 'answer_reasons')
    score['wrong'] = [{k: r.get(k) for k in keep} for r in rows if r['as_frozen'] == 'WRONG']
    score['false_none'] = [{k: r.get(k) for k in keep} for r in rows if r['as_frozen'] == 'FALSE_NONE']
    score['unscored'] = [{k: r.get(k) for k in keep} for r in rows if r['as_frozen'] == 'UNSCORED' and r['status'] in FILLED_LIKE]
    score['nonzero_exit'] = [r['id'] for r in rows if r['exit_code'] != 0]
    Path(args.score).write_text(json.dumps(score, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    if load > 8:
        Path(args.timing).write_text(json.dumps({'skipped': 'load', 'load': load}) + '\n', encoding='utf-8')
    else:
        secs = sorted(timing.values())
        Path(args.timing).write_text(json.dumps({'load_1min': load, 'questions': len(secs), 'total_secs': sum(secs), 'min_secs': secs[0], 'median_secs': secs[len(secs) // 2],
                                                 'max_secs': secs[-1], 'per_question_secs': timing}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(totals, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
