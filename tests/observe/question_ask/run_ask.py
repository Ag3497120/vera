"""W3-c4 runner: run the questions of a question file through `vera ask --mode round5 --document ...` and score the final output (after the basis policy).

    run_ask.py --questions Q.jsonl --docs-dir DIR --tree {new,base} --mode {cli,inproc} [--placement JSON] [--vp DIR] --out O.jsonl --score S.json
               [--ask-mode round5] [--no-docs] [--ask-args "..."] [--ids a,b] [--limit N] [--rescore] [--base-tree DIR] [--tmp DIR] [--out-dir DIR] [--hashseed N]

`--questions`: one object per line {id, docs: [file name or directory under DIR], text, truth: {kind, fillers, evidence, ...}, category?}. A question with `docs: []` is asked with no --document.
`--mode cli`: a child process per question (`env -i`, PYTHONPATH=<tree>, VERA_PLACEMENT=<--vp> when given), the bytes of stdout are kept (O.d/<id>.json and O.jsonl).
`--mode inproc`: the same `cli.main([...])` in this process with `event_cross.default_lookup` replaced by the FilePlacement of `--placement` (the same path VERA_PLACEMENT takes).
`--rescore`: do not run; read the existing O.jsonl and score it again against --questions (to score the same outputs with another truth file).
Scoring: docs/OBSERVATION.md 事前登録 W3-c4 (採点): RAN / QC_ANSWER / QC_TIE / QC_NONE, classes CORRECT WRONG FALSE_NONE ABSTAINED NOT_RUN; `base_answer` for the rows the later stage did not run.
The score JSON has `counts` and `wrong` (ids) at the top; WRONG must be empty."""
import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
NEW_TREE = HERE.parents[2]
NFKC = lambda s: unicodedata.normalize('NFKC', s)
CLASSES = ('CORRECT', 'WRONG', 'FALSE_NONE', 'ABSTAINED', 'NOT_RUN')


def ask_argv(q, docs_dir, args):
    argv = ['ask', '--mode', args.ask_mode]
    if not args.no_docs:
        for d in q.get('docs') or []: argv += ['--document', str(Path(docs_dir).resolve() / d)]    # absolute: the child runs in the tree directory
    if args.ask_args: argv += args.ask_args.split()
    return argv + ['--', q['text']]


def run_cli(q, docs_dir, args, tree, store):
    env = {'HOME': os.environ.get('HOME', ''), 'PATH': '/usr/bin:/bin', 'PYTHONPATH': str(tree), 'PYTHONDONTWRITEBYTECODE': '1'}
    if args.vp: env['VERA_PLACEMENT'] = args.vp
    if args.hashseed is not None: env['PYTHONHASHSEED'] = str(args.hashseed)
    cmd = [args.python, '-m', 'verantyx.cli', '--store', store] + ask_argv(q, docs_dir, args)
    # cwd is the tree itself: `python -m` puts the current directory FIRST on sys.path (so the cwd decides which copy of `verantyx` is imported, not PYTHONPATH alone), and the
    # product finds its source assets relative to the cwd (from another directory the document path answers UNKNOWN_SOURCE_ASSET).
    r = subprocess.run(cmd, env=env, cwd=str(tree), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return r.returncode, r.stdout.decode('utf-8', 'replace'), r.stderr.decode('utf-8', 'replace')[-400:]


def loaded_from(args, tree, store):
    """Where the child process really imports `verantyx.cli` from (it must be under the tree that was asked for)."""
    env = {'HOME': os.environ.get('HOME', ''), 'PATH': '/usr/bin:/bin', 'PYTHONPATH': str(tree), 'PYTHONDONTWRITEBYTECODE': '1'}
    r = subprocess.run([args.python, '-m', 'verantyx.cli', '--help'], env=env, cwd=str(tree), stdout=subprocess.PIPE)
    r = subprocess.run([args.python, '-c', 'import verantyx.cli as c; print(c.__file__)'], env=env, cwd=str(tree), stdout=subprocess.PIPE)
    path = r.stdout.decode().strip()
    assert Path(path).resolve().is_relative_to(Path(tree).resolve()), 'child loaded %s, not the tree %s' % (path, tree)
    return path


def make_inproc(tree, placement):
    sys.path.insert(0, str(tree))
    os.environ.pop('VERA_PLACEMENT', None)
    from verantyx import cli, event_cross as EC, observe as O
    assert str(Path(cli.__file__).resolve()).startswith(str(Path(tree).resolve())), cli.__file__
    if placement:
        fp = O.FilePlacement.from_path(placement)
        EC.default_lookup = lambda *a, **k: fp

    def run(q, docs_dir, args, store):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cli.main(['--store', store] + ask_argv(q, docs_dir, args))
        return rc, buf.getvalue(), ''
    return run


def trace_has_qc(o):
    return any(isinstance(t, dict) and t.get('part') == 'question_cross' for t in (o.get('trace') or []))


def classify(q, o):
    """(class, base_answer or None, detail) for one final output `o` (a dict) and its question."""
    truth = q.get('truth') or {}
    kind = truth.get('kind')
    ran = trace_has_qc(o)
    qc_answer = o.get('door') == 'question_cross' and o.get('verdict') == 'ANSWER'
    qc_tie = o.get('verdict') == 'AMBIGUOUS_QUESTION_CROSS_TIE'
    qc_none = (o.get('question_cross') or {}).get('state') in ('NO_ATTESTED_CELL', 'TYPE_EXCLUDED_ALL')
    want_f = {NFKC(x) for x in truth.get('fillers', [])}
    want_e = set(truth.get('evidence', []))
    if not ran:
        base = 'NO_ANSWER'
        if o.get('verdict') == 'ANSWER':
            # the existing path writes its answer as `role: value[、role: value]`; the values are compared with the one filler of a ONE truth
            values = {NFKC(part.split(': ', 1)[-1].strip()) for part in (o.get('text') or '').split('、')}
            if kind == 'ONE': base = 'BASE_MATCH' if (len(want_f) == 1 and want_f <= values) else 'BASE_MISMATCH'
            elif kind in ('YESNO', 'ILLFORMED'): base = 'BASE_NOT_JUDGED'
            else: base = 'BASE_MISMATCH'
        return 'NOT_RUN', base, None
    if kind in ('YESNO', 'ILLFORMED'):
        return ('WRONG', None, 'answered a question that has no answer') if (qc_answer or qc_tie) else ('CORRECT', None, None)
    if kind == 'NONE':
        if qc_answer or qc_tie: return 'WRONG', None, 'answered a question the document does not answer'
        return ('CORRECT', None, None) if (o.get('question_cross') or {}).get('state') == 'NO_ATTESTED_CELL' else ('ABSTAINED', None, None)
    if kind == 'ONE':
        if qc_answer:
            ids = [s.get('sentence_id') for s in o.get('sources') or []]
            ok = (NFKC(o.get('text') or '') in want_f and len(want_f) == 1 and set(ids) == want_e and bool(ids) and ids[0] == min(want_e))
            return ('CORRECT', None, None) if ok else ('WRONG', None, {'text': o.get('text'), 'ids': ids, 'want': sorted(want_f), 'want_ids': sorted(want_e)})
        if qc_tie:
            cands = o.get('candidates') or []
            got_f = {NFKC(c.get('text') or '') for c in cands}
            got_e = {s.get('sentence_id') for c in cands for s in c.get('sources') or []}
            if len(want_f) == 1 and got_f == want_f and got_e == want_e and (o.get('question_cross') or {}).get('reason', '').startswith('SURFACES_DIFFER'):
                return 'ABSTAINED', None, 'SURFACES_DIFFER'        # J2: the true answer written two ways is a TIE (typed abstention carrying both), not a wrong answer
            return 'WRONG', None, {'got': 'TIE', 'want': sorted(want_f)}
        return ('FALSE_NONE', None, None) if qc_none else ('ABSTAINED', None, None)
    if kind == 'SPLIT':
        if qc_tie:
            cands = o.get('candidates') or []
            got_f = {NFKC(c.get('text') or '') for c in cands}
            got_e = {s.get('sentence_id') for c in cands for s in c.get('sources') or []}
            ok = got_f == want_f and got_e == want_e
            return ('CORRECT', None, None) if ok else ('WRONG', None, {'got': sorted(got_f), 'ids': sorted(got_e), 'want': sorted(want_f), 'want_ids': sorted(want_e)})
        if qc_answer: return 'WRONG', None, {'got': 'ANSWER', 'text': o.get('text'), 'want': sorted(want_f)}
        return ('FALSE_NONE', None, None) if qc_none else ('ABSTAINED', None, None)
    return 'ABSTAINED', None, None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--questions', required=True); ap.add_argument('--docs-dir', required=True)
    ap.add_argument('--tree', choices=('new', 'base'), default='new'); ap.add_argument('--mode', choices=('cli', 'inproc'), default='cli')
    ap.add_argument('--placement'); ap.add_argument('--vp')
    ap.add_argument('--out', required=True); ap.add_argument('--score', required=True)
    ap.add_argument('--ask-mode', default='round5'); ap.add_argument('--no-docs', action='store_true'); ap.add_argument('--ask-args', default='')
    ap.add_argument('--ids'); ap.add_argument('--limit', type=int); ap.add_argument('--rescore', action='store_true'); ap.add_argument('--hashseed', type=int, help='PYTHONHASHSEED of the child process (cli mode)'); ap.add_argument('--out-dir', help='where the one-file-per-question copies go (default OUT.d)')
    ap.add_argument('--base-tree', default=None, help='the tree of the base commit (git archive); required with --tree base'); ap.add_argument('--tmp'); ap.add_argument('--python', default=sys.executable)
    args = ap.parse_args(argv)
    qs = [json.loads(l) for l in Path(args.questions).read_text(encoding='utf-8').splitlines() if l.strip()]
    if args.ids: qs = [q for q in qs if q['id'] in set(args.ids.split(','))]
    if args.limit: qs = qs[:args.limit]
    if args.tree == 'base' and not args.base_tree: ap.error('--tree base needs --base-tree DIR (a git archive of the base commit)')
    tree = NEW_TREE if args.tree == 'new' else Path(args.base_tree)
    out_path = Path(args.out); out_dir = Path(args.out_dir) if args.out_dir else Path(str(out_path) + '.d')
    raw = {}
    loaded = None
    if args.rescore:
        for l in out_path.read_text(encoding='utf-8').splitlines():
            if l.strip():
                r = json.loads(l); raw[r['id']] = r
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        tmp = args.tmp or tempfile.mkdtemp(prefix='w3c4_run_')
        Path(tmp).mkdir(parents=True, exist_ok=True)
        store = str(Path(tmp) / 'st.json')
        inproc = make_inproc(tree, args.placement) if args.mode == 'inproc' else None
        loaded = loaded_from(args, tree, store) if args.mode == 'cli' else None
        rows = []
        for q in qs:
            rc, stdout, err = inproc(q, args.docs_dir, args, store) if inproc else run_cli(q, args.docs_dir, args, tree, store)
            (out_dir / (q['id'] + '.json')).write_text(stdout, encoding='utf-8')
            raw[q['id']] = {'id': q['id'], 'exit_code': rc, 'stdout': stdout, 'stderr_tail': err}
            rows.append(raw[q['id']])
        out_path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    counts = Counter(); states = Counter(); mapped = Counter(); bases = Counter(); by_cat = {}; by_kind = {}
    wrong, false_none, errors, bad_json, nonzero, details, notation_tie = [], [], [], [], [], {}, []
    per_row = []
    for q in qs:
        r = raw[q['id']]
        if r['exit_code'] not in (0, 1): nonzero.append(q['id'])
        try: o = json.loads(r['stdout'])
        except ValueError: o = None; bad_json.append(q['id'])
        if not isinstance(o, dict):
            cls, base, det = 'ABSTAINED', None, 'unparsable output'
            o = {}
        else:
            cls, base, det = classify(q, o)
        counts[cls] += 1
        by_cat.setdefault(q.get('category', '-'), Counter())[cls] += 1
        by_kind.setdefault((q.get('truth') or {}).get('kind', '-'), Counter())[cls] += 1
        qc = o.get('question_cross') or {}
        if trace_has_qc(o):
            states[qc.get('state') or next(t['state'] for t in o['trace'] if t.get('part') == 'question_cross')] += 1
            mapped[qc.get('mapped_to') or next(t['mapped_to'] for t in o['trace'] if t.get('part') == 'question_cross')] += 1
        if base: bases[base] += 1
        if cls == 'WRONG': wrong.append(q['id']); details[q['id']] = det
        if cls == 'FALSE_NONE': false_none.append(q['id'])
        if det == 'SURFACES_DIFFER': notation_tie.append(q['id'])
        if qc.get('state') == 'ERROR': errors.append(q['id'])
        per_row.append({'id': q['id'], 'class': cls, 'base_answer': base, 'verdict': o.get('verdict'), 'door': o.get('door'),
                        'state': qc.get('state'), 'mapped_to': qc.get('mapped_to'), 'category': q.get('category'), 'kind': (q.get('truth') or {}).get('kind'),
                        'ran': trace_has_qc(o), 'outcome': (o.get('basis_policy') or {}).get('outcome')})
    score = {'n': len(qs), 'tree': args.tree, 'loaded_from': loaded, 'mode': args.mode, 'placement': (Path(args.placement).name if args.placement else None), 'vp': bool(args.vp),
             'counts': {c: counts.get(c, 0) for c in CLASSES}, 'wrong': wrong, 'wrong_details': details, 'notation_tie': notation_tie, 'false_none': false_none, 'error_ids': errors,
             'error_count': len(errors), 'question_cross_states': dict(sorted(states.items())), 'mapped_to': dict(sorted(mapped.items())),
             'base_answer': dict(sorted(bases.items())), 'by_category': {k: {c: v.get(c, 0) for c in CLASSES} for k, v in sorted(by_cat.items())},
             'by_truth_kind': {k: {c: v.get(c, 0) for c in CLASSES} for k, v in sorted(by_kind.items())}, 'unparsable': bad_json, 'nonzero_exit': nonzero,
             'policy_outcomes': dict(sorted(Counter(r['outcome'] for r in per_row if r['door'] == 'question_cross' and r['outcome']).items())), 'rows': per_row}
    Path(args.score).write_text(json.dumps(score, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({'n': score['n'], 'counts': score['counts'], 'wrong': wrong, 'error_count': len(errors)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
