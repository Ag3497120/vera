"""W3-c4: build artifacts/w3-c4/summary.txt (and, with --patch-docs, the measured block of docs/OBSERVATION.md and docs/BASIS_POLICY.md) from the files of artifacts/w3-c4/.
Every number is read from a file; nothing is typed by hand.   make_summary.py [--patch-docs]"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parents[2]
A = TREE / 'artifacts' / 'w3-c4'
TRIGGER = ('UNKNOWN_UNREAD', 'UNKNOWN_NO_EVIDENCE')
CLASSES = ('CORRECT', 'WRONG', 'FALSE_NONE', 'ABSTAINED', 'NOT_RUN')


def jl(path):
    out = {}
    for l in Path(path).read_text(encoding='utf-8').splitlines():
        if l.strip():
            r = json.loads(l); out[r['id']] = r
    return out


def jf(name): return json.loads((A / name).read_text(encoding='utf-8'))


def last_line(name, pat=r'(passed|failed)'):
    lines = [l for l in (A / name).read_text(encoding='utf-8').splitlines() if re.search(pat, l)]
    return lines[-1].strip() if lines else '(missing)'


def block():
    L = []
    q_docs = {}
    for qf in (HERE / 'questions.jsonl', HERE / 'w3c2' / 'questions.jsonl', HERE / 'b2like' / 'questions.jsonl'):
        for l in qf.read_text(encoding='utf-8').splitlines():
            if l.strip():
                q = json.loads(l); q_docs[q['id']] = q.get('docs') or []
    base = jl(A / 'a1_base1.jsonl')
    c = Counter()
    for i, r in base.items():
        v = json.loads(r['stdout']).get('verdict')
        key = 'no document' if not q_docs.get(i) else ('inside the closed set: %s' % v if v in TRIGGER else 'outside the closed set')
        c[key] += 1
        if key == 'outside the closed set': c['  (outside) verdict %s' % v] += 1
    L.append('[base verdicts of the 343 questions of A1 (a1_base1.jsonl, no placement; same in the r7 run is in a1_base_r7.jsonl)]')
    for k in sorted(c): L.append('  %s: %d' % (k, c[k]))
    for tag in ('a1_new', 'a1_new_r7'):
        s = jf(tag + '_score.json')
        L.append('[%s: all 343 questions, final output after the policy, cli, %s]' % (tag, 'VERA_PLACEMENT=r7' if tag.endswith('r7') else 'no placement'))
        L.append('  counts %s' % json.dumps(s['counts']))
        L.append('  question_cross.state of the questions the stage ran on: %s' % json.dumps(s['question_cross_states'], ensure_ascii=False))
        L.append('  mapped_to: %s; ERROR states: %d; WRONG ids: %s' % (json.dumps(s['mapped_to']), s['error_count'], s['wrong']))
    for tag, title in (('a2_place', 'new data (AQ), in process, placement_ask.json'), ('a2_r7', 'new data (AQ), cli, VERA_PLACEMENT=r7'),
                       ('w3c2_place', 'W3-c2 185 questions, in process, placement_q.json'), ('w3c2_r7', 'W3-c2 185 questions, cli, VERA_PLACEMENT=r7'),
                       ('w3c2_place_corr', 'W3-c2 185 questions with the W3-c2 corrections applied, in process'),
                       ('w3c2_r7_corr', 'W3-c2 185 questions with the W3-c2 corrections applied, cli, r7'),
                       ('b2like_place', 'B2-like (47 questions), in process, placement_ask.json'), ('b2like_r7', 'B2-like (47 questions), cli, r7')):
        p = A / (tag + '_score.json')
        if not p.exists(): L.append('[%s] missing' % tag); continue
        s = json.loads(p.read_text(encoding='utf-8'))
        L.append('[%s: %s]' % (tag, title))
        L.append('  n=%d counts %s' % (s['n'], json.dumps(s['counts'])))
        L.append('  WRONG ids: %s; FALSE_NONE ids: %s; ERROR states: %d' % (s['wrong'], s['false_none'], s['error_count']))
        L.append('  question_cross.state: %s' % json.dumps(s['question_cross_states'], ensure_ascii=False))
        L.append('  mapped_to: %s; existing path on the NOT_RUN rows: %s' % (json.dumps(s['mapped_to']), json.dumps(s['base_answer'])))
        L.append('  basis_policy.outcome of the answers: %s' % json.dumps(s['policy_outcomes']))
    # the language of the question's documents: which ran-and-answered, per placement (the English nouns have no type in the coarse placement r7)
    L.append('[later stage ran / mapped to ANSWER or TIE, by the language of the first document (AD08-10, QD08-10, BA04 are English)]')
    for tag, qf in (('a2_place', 'questions.jsonl'), ('a2_r7', 'questions.jsonl'), ('w3c2_place', 'w3c2/questions.jsonl'), ('w3c2_r7', 'w3c2/questions.jsonl'),
                    ('b2like_place', 'b2like/questions.jsonl'), ('b2like_r7', 'b2like/questions.jsonl')):
        qs = {json.loads(l)['id']: json.loads(l) for l in (HERE / qf).read_text(encoding='utf-8').splitlines() if l.strip()}
        cnt = Counter()
        for r in jf(tag + '_score.json')['rows']:
            if not r['ran']: continue
            d = (qs[r['id']]['docs'] or [''])[0]
            lg = 'en' if d.startswith(('QD08', 'QD09', 'QD10', 'AD08', 'AD09', 'AD10', 'BA04')) else 'ja'
            cnt[lg + ' ran'] += 1
            if r['mapped_to'] in ('ANSWER', 'AMBIGUOUS_QUESTION_CROSS_TIE'): cnt[lg + ' answered_or_tie'] += 1
        L.append('  %s: %s' % (tag, json.dumps(dict(sorted(cnt.items())))))
    for name in ('a1_cmp_noplace.txt', 'a1_cmp_r7.txt', 'a1_cmp_other_modes.txt'):
        p = A / name
        if p.exists():
            L.append('[%s]' % name)
            L.extend('  ' + l for l in p.read_text(encoding='utf-8').splitlines()[-6:])
    for name, label in (('pytest_related_before.txt', 'related tests before'), ('pytest_related_after.txt', 'related tests after'),
                        ('pytest_new_tests.txt', 'the new tests'), ('pytest_full.txt', 'full run')):
        if (A / name).exists(): L.append('[%s: %s] %s' % (name, label, last_line(name)))
    for name in ('determinism.txt', 'parity.txt'):
        if (A / name).exists():
            L.append('[%s]' % name)
            L.extend('  ' + l for l in (A / name).read_text(encoding='utf-8').splitlines()[-3:])
    L.extend(round2_block())
    L.extend(extra2_block())
    return L


def extra2_block():
    L = ['[extra2 (round 2 data, 42 questions, frozen in FROZEN_EXTRA2.json): round-1 code vs round-2 code, uncorrected and corrected truth (corrections.jsonl: X032, X037)]']
    for t, label in (('place', 'in process, placement_extra2.json'), ('r7', 'cli, VERA_PLACEMENT=r7')):
        for suf, tl in (('', 'truth as frozen'), ('_corr', 'truth with corrections.jsonl')):
            p = A / ('r2_extra2_%s%s_score.json' % (t, suf))
            if p.exists():
                s = json.loads(p.read_text(encoding='utf-8'))
                L.append('  %s, %s: counts %s, WRONG %s, ERROR %d' % (label, tl, json.dumps(s['counts']), s['wrong'], s['error_count']))
    for suf, tl in (('', 'truth as frozen'), ('_corr', 'truth with corrections.jsonl')):
        p = A / ('r2_extra2_before_place%s_score.json' % suf)
        if p.exists():
            s = json.loads(p.read_text(encoding='utf-8'))
            L.append('  round-1 code (the same questions, in process): %s: counts %s, WRONG %s' % (tl, json.dumps(s['counts']), s['wrong']))
    return L


ROUND2 = (('a2_place', 'a2_place'), ('a2_r7', 'a2_r7'), ('w3c2_place', 'w3c2_place'), ('w3c2_place_corr', 'w3c2_place'), ('w3c2_r7', 'w3c2_r7'), ('w3c2_r7_corr', 'w3c2_r7'),
          ('b2like_place', 'b2like_place'), ('b2like_r7', 'b2like_r7'), ('a1_new', 'a1_new'), ('a1_new_r7', 'a1_new_r7'))


def round2_block():
    """Round 2 (M1): what the written-predicate check changed, from the round-1 scores (artifacts/w3-c4/r1_scores/) and the round-2 scores + outputs. Nothing typed by hand."""
    L = ['[round 2 (M1, PREDICATE_FORM_DIFFERS / PREDICATE_POSITION_UNKNOWN): round-1 score -> round-2 score, per run; the ids that were CORRECT in round 1 and are not now]']
    for tag, out_name in ROUND2:
        pb, pn = A / 'r1_scores' / (tag + '_score.json'), A / (tag + '_score.json')
        if not pb.exists() or not pn.exists(): L.append('  %s: missing' % tag); continue
        b, n = json.loads(pb.read_text(encoding='utf-8')), json.loads(pn.read_text(encoding='utf-8'))
        outs = jl(A / (out_name + '.jsonl'))
        before = {r['id']: r['class'] for r in b['rows']}
        L.append('  %s: CORRECT %s -> %s, WRONG %s -> %s, ERROR %s -> %s, WRONG ids now %s' % (tag, b['counts'].get('CORRECT'), n['counts'].get('CORRECT'), b['counts'].get('WRONG'), n['counts'].get('WRONG'),
                                                                                   b['error_count'], n['error_count'], n['wrong']))
        why = Counter()
        lost = []
        for r in n['rows']:
            o = json.loads(outs[r['id']]['stdout']) if r['id'] in outs and outs[r['id']].get('stdout') else {}
            qc = o.get('question_cross') or {}
            if qc.get('reason') in ('PREDICATE_FORM_DIFFERS', 'PREDICATE_POSITION_UNKNOWN'): why[qc['reason']] += 1
            if before.get(r['id']) == 'CORRECT' and r['class'] != 'CORRECT': lost.append('%s(%s:%s)' % (r['id'], r['class'], qc.get('reason') or qc.get('state')))
        L.append('      stage abstained by the new check: %s; CORRECT -> not CORRECT: %s' % (json.dumps(dict(why)), ' '.join(lost) or 'none'))
    return L


def patch(path, begin, end, text):
    s = path.read_text(encoding='utf-8')
    if begin in s:
        pre, rest = s.split(begin, 1); _, post = rest.split(end, 1)
        s = pre + begin + '\n' + text + '\n' + end + post
    else:
        s = s.rstrip('\n') + '\n\n' + begin + '\n' + text + '\n' + end + '\n'
    path.write_text(s, encoding='utf-8')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--patch-docs', action='store_true')
    args = ap.parse_args()
    lines = block()
    (A / 'summary.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    if args.patch_docs:
        pol = ['（`tests/observe/question_ask/make_summary.py --patch-docs` が `artifacts/w3-c4/` のファイルから貼った区間。手で書き換えない。）', '',
               'A4 のテスト: `tests/test_ask_question_cross.py` の `test_policy_the_document_sentence_is_a_human_basis`・`test_policy_human_basis_without_human_present_too`・`test_policy_a_tie_is_an_abstention_and_keeps_the_candidates`。',
               'CLI での A4（`artifacts/w3-c4/a4_cli.txt`）:', '', '```']
        pol += (A / 'a4_cli.txt').read_text(encoding='utf-8').splitlines()
        pol += ['```', '', '後段が答えた（`door:"question_cross"`）問の `basis_policy.outcome` の分布（既定の方針。各 score の JSON の `policy_outcomes`。ANSWER の行は `ANSWER_HUMAN_BASIS`、TIE の行は `ABSTAIN`）:', '', '```']
        for tag in ('a2_place', 'a2_r7', 'w3c2_place', 'w3c2_r7', 'b2like_place', 'b2like_r7', 'a1_new_r7'):
            sj = jf(tag + '_score.json'); pol.append('%s: %s' % (tag, json.dumps(sj['policy_outcomes'])))
        pol += ['```']
        patch(TREE / 'docs' / 'BASIS_POLICY.md', '<!-- w3c4-measured:begin -->', '<!-- w3c4-measured:end -->', '\n'.join(pol))
        text = ('（`tests/observe/question_ask/make_summary.py --patch-docs` が `artifacts/w3-c4/` のファイルから貼った区間。手で書き換えない。）\n\n```\n' + '\n'.join(lines) + '\n```')
        patch(TREE / 'docs' / 'OBSERVATION.md', '<!-- w3c4-measured:begin -->', '<!-- w3c4-measured:end -->', text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
