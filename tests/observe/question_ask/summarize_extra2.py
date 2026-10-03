"""W3-c4 round 2: summary of the extra2 run (written predicate forms). Reads questions.jsonl + a run_ask output jsonl (+ optionally the score of the round-1 code on the same
questions) and prints, from the files only: counts, the reason distribution, the anticipated reason (expect_reason, author's guess, not a condition) vs the actual one,
the questions that answered / tied at the later stage, and the ids that were CORRECT before and are not now."""
import argparse
import json
from collections import Counter
from pathlib import Path


def rows(path):
    out = {}
    for l in Path(path).read_text(encoding='utf-8').splitlines():
        if not l.strip(): continue
        r = json.loads(l)
        out[r['id']] = json.loads(r['stdout']) if r.get('stdout') else {}
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--questions', required=True); ap.add_argument('--run', required=True); ap.add_argument('--score', required=True)
    ap.add_argument('--before-score'); ap.add_argument('--title', default='')
    a = ap.parse_args()
    qs = {json.loads(l)['id']: json.loads(l) for l in Path(a.questions).read_text(encoding='utf-8').splitlines() if l.strip()}
    out = rows(a.run); score = json.loads(Path(a.score).read_text(encoding='utf-8'))
    cls = {r['id']: r['class'] for r in score['rows']}
    print('== %s' % a.title)
    print('counts', score['counts'], 'wrong', score['wrong'], 'errors', score['error_count'])
    reasons, match, stage = Counter(), Counter(), []
    for i, q in qs.items():
        o = out.get(i) or {}; qc = o.get('question_cross') or {}
        ran = any(t.get('part') == 'question_cross' for t in o.get('trace') or [])
        if o.get('door') == 'question_cross' or o.get('verdict') == 'AMBIGUOUS_QUESTION_CROSS_TIE': stage.append((i, o.get('verdict'), o.get('text') or [c['text'] for c in o.get('candidates', [])]))
        if not ran: reasons['(stage did not run)'] += 1; continue
        why = qc.get('reason') if qc.get('mapped_to') == 'ORIGINAL' and qc.get('state') in ('FILLED', 'TIE') else (qc.get('state') if qc.get('mapped_to') == 'ORIGINAL' else qc.get('mapped_to'))
        reasons['%s' % why] += 1
        if 'expect_reason' in q:
            got = qc.get('reason') if qc.get('state') in ('FILLED', 'TIE') else qc.get('state')
            match['anticipated reason matched' if got == q['expect_reason'] else 'a different reason (reader or stage abstained for another cause)'] += 1
    print('reasons / outcome of the stage (ran):', dict(sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))))
    print('anticipated reason (author guess, not a condition):', dict(match))
    print('answers/ties made by the later stage:', stage)
    if a.before_score:
        before = {r['id']: r['class'] for r in json.loads(Path(a.before_score).read_text(encoding='utf-8'))['rows']}
        lost = sorted(i for i in cls if before.get(i) == 'CORRECT' and cls[i] != 'CORRECT')
        fixed = sorted(i for i in cls if before.get(i) == 'WRONG' and cls[i] != 'WRONG')
        print('CORRECT before, not now:', lost, '| WRONG before, not now:', fixed, '| WRONG now:', sorted(i for i in cls if cls[i] == 'WRONG'))


if __name__ == '__main__':
    main()
