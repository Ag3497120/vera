#!/usr/bin/env python3
"""W1-a 照合ハーネス: 評価文を読解器に通し、正解の構造と機械的に照合する。

使い方: PYTHONPATH=<木> python harness.py --out result.json [--only J1,J2] [--quiet]

分類（文ごと）:
  正読     : 対象節(unsupported でない節)がすべて、ある alternative の節のどれかに一致し、
             かつその alternative の節がすべて対象節のどれかに一致する。
             gold.kind=none では対象節が 0 のとき（構造化しない＝正）。
  誤読     : 対象節が 1 つ以上あり、どの alternative とも「全部一致」にならない
             （gold.kind=none / unsupported では対象節が 1 つでもあれば誤読）。
  未対応   : それ以外。gold.kind=unsupported のときは「棄権が正解」(abstain_ok) として別に数える。
節の一致: predicate ∈ gold.predicate かつ polarity 一致 かつ {役割名: 値} が gold.roles と完全一致。
  値は role.span.text（gold が {"term": x} のときは str(role.term)）。役割の過不足は不一致。
検査: 各対象節に semantic_verify.license_clause を掛けた結果（PASS / 拒否）を記録する。
  検査誤通過 = gold に一致しない対象節で検査が PASS したもの（節の数）。
英語: en_frames.read(_typed) の結果を en_frames.key で gold と比べる。None は未対応。

評価ファイルはこのファイルの隣から読む（DEVTREE で動かしても W の評価文を読む）。
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = os.environ.get('PYTHONPATH', '').split(os.pathsep)[0]

JA_BANKS = ('table7.jsonl', 'ja.jsonl', 'ja_r2.jsonl', 'ja_r3.jsonl', 'ja_r4.jsonl', 'ja_r5.jsonl', 'ja_r6.jsonl')
EN_BANKS = ('en.jsonl', 'en_r2.jsonl')
# 上申済みの既知の例外(id で列挙する)。W1-a2 で空にした: 以前の J1-17(「へ」の終点を recipient と呼ぶ規約)は、場所・人の正の証拠が無い終点を
# recipient と読まず、第 2 ラウンドからは未対応にして解消した(docs/READING_SOUNDNESS.md §4.4 M5)。ほかの誤読も 0 を要求する。
ESCALATED = {}


def isolation_check():
    """読み込まれた verantyx* がすべて PYTHONPATH の木の配下であること。外れていれば終了コード 2。"""
    root = os.path.realpath(TREE or '.')
    bad = [m.__file__ for k, m in list(sys.modules.items())
           if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None)
           and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    return root, bad


def tree_revision(root):
    try:
        out = subprocess.run(['git', '-C', root, 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return 'not a git tree (archive of 075d486 expected for DEVTREE)'


def load(name):
    path = HERE / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def role_value(role):
    return role.span.text


def clause_matches(c, g):
    if c.predicate not in g['predicate'] or c.polarity != g['polarity']:
        return False
    have = {}
    for r in c.roles:
        if r.name in have:
            return False
        have[r.name] = r
    if set(have) != set(g['roles']):
        return False
    for name, want in g['roles'].items():
        r = have[name]
        if isinstance(want, dict):
            if str(r.term) != want['term']:
                return False
        elif role_value(r) != want:
            return False
    return True


def summarize_clause(c, verdict):
    return {'rule': c.rule, 'predicate': c.predicate, 'polarity': c.polarity,
            'roles': [[r.name, r.span.text if r.rule not in ('comparison_direction', 'comparison_dimension') else str(r.term)] for r in c.roles],
            'unsupported': list(c.unsupported), 'license': verdict}


def classify_ja(item, document_view, license_clause):
    view = document_view({'d': item['text']})
    targets = [c for c in view.clauses if not c.unsupported]
    verdicts = {}
    for c in view.clauses:
        try:
            license_clause(c, view)
            verdicts[c.id] = 'PASS'
        except Exception as exc:  # 検査の拒否理由を残す
            verdicts[c.id] = 'REJECT: ' + str(exc)
    gold = item['gold']
    kind = gold['kind']
    matched_any = set()
    if kind == 'clauses':
        full = False
        best = set()
        for alt in gold['alternatives']:
            ok_targets = all(any(clause_matches(c, g) for g in alt) for c in targets)
            ok_alt = all(any(clause_matches(c, g) for c in targets) for g in alt)
            this = {c.id for c in targets if any(clause_matches(c, g) for g in alt)}
            if len(this) > len(best):
                best = this              # O1: judge against the single alternative that explains most clauses, not a union
            if targets and ok_targets and ok_alt:
                full = True
        matched_any = best
        if full:
            result = 'correct'
        elif targets and not any(all(any(clause_matches(c, g) for g in alt) for c in targets) for alt in gold['alternatives']):
            result = 'misread'
        else:
            result = 'unsupported'
    elif kind == 'none':
        result = 'misread' if targets else 'correct'
    else:  # unsupported
        result = 'misread' if targets else 'unsupported'
    wrong = [c for c in targets if c.id not in matched_any]
    false_pass = [c for c in wrong if verdicts.get(c.id) == 'PASS'] if result == 'misread' or kind != 'clauses' else []
    all_pass = bool(targets) and all(verdicts.get(c.id) == 'PASS' for c in targets)
    return {
        'id': item['id'], 'type': item['type'], 'text': item['text'], 'gold_kind': kind, 'escalated': item['id'] in ESCALATED,
        'result': result, 'abstain_ok': result == 'unsupported' and kind in ('unsupported',),
        'targets_all_pass': all_pass, 'false_pass': len(false_pass),
        'clauses': [summarize_clause(c, verdicts.get(c.id)) for c in view.clauses],
        'unread': [u.reason for u in view.unread],
    }


def classify_en(item, en):
    reader = getattr(en, 'read_typed', None)
    reasons = ()
    if reader is not None:
        frame, reasons = reader(item['text'])
    else:
        frame = en.read(item['text'])
    gold = item['gold']
    got = en.key(frame) if frame is not None else None
    if gold['kind'] == 'frame':
        from verantyx.frames import Frame
        want = en.key(Frame(**gold['frame']))
        result = 'correct' if got == want else ('unsupported' if frame is None else 'misread')
    else:
        result = 'misread' if frame is not None else 'unsupported'
    return {'id': item['id'], 'type': item['type'], 'text': item['text'], 'gold_kind': gold['kind'], 'escalated': item['id'] in ESCALATED,
            'result': result, 'abstain_ok': result == 'unsupported' and gold['kind'] == 'unsupported',
            'targets_all_pass': None, 'false_pass': 0,
            'frame': (list(got) if got else None), 'reasons': list(reasons)}


def summarize(rows):
    out = {}
    for t in sorted({r['type'] for r in rows}):
        rs = [r for r in rows if r['type'] == t]
        n = len(rs)
        correct = sum(r['result'] == 'correct' for r in rs)
        misread = sum(r['result'] == 'misread' for r in rs)
        unsup = sum(r['result'] == 'unsupported' for r in rs)
        esc = [r for r in rs if r.get('escalated')]
        out[t] = {'n': n, 'correct': correct, 'misread': misread, 'unsupported': unsup,
                  'abstain_is_correct': sum(r['abstain_ok'] for r in rs),
                  'correct_and_all_pass': sum(r['result'] == 'correct' and r['targets_all_pass'] is True for r in rs),
                  'false_pass': sum(r['false_pass'] for r in rs),
                  'misread_escalated': sum(r['result'] == 'misread' for r in esc),
                  'false_pass_escalated': sum(r['false_pass'] for r in esc),
                  'half_or_more_correct': 2 * correct >= n}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--only', default='')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    from verantyx.semantic_reader import document_view
    from verantyx.semantic_verify import license_clause
    from verantyx import en_frames as en
    from verantyx import constructions
    constructions.discover()
    root, bad = isolation_check()
    rev = tree_revision(root)
    print(f'tree={root}\nrevision={rev}\nforeign_modules={bad}')
    if bad:
        print('ISOLATION FAILED', file=sys.stderr)
        sys.exit(2)
    only = {x for x in a.only.split(',') if x}
    rows = []
    for f in JA_BANKS:
        for item in load(f):
            if only and item['type'] not in only:
                continue
            rows.append(classify_ja(item, document_view, license_clause))
    for f in EN_BANKS:
        for item in load(f):
            if only and item['type'] not in only:
                continue
            rows.append(classify_en(item, en))
    summary = summarize(rows)
    header = {'tree': root, 'revision': rev, 'foreign_modules': bad,
              'bank_files': {f: len(load(f)) for f in JA_BANKS + EN_BANKS},
              'escalated': ESCALATED}
    Path(a.out).write_text(json.dumps({'header': header, 'summary': summary, 'sentences': rows}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f"{'type':5} {'n':>3} {'正読':>5} {'誤読':>5} {'未対応':>6} {'棄権正':>6} {'正読&検査PASS':>12} {'検査誤通過':>9} {'半数以上正読':>10}")
    for t, s in summary.items():
        print(f"{t:5} {s['n']:>3} {s['correct']:>5} {s['misread']:>5} {s['unsupported']:>6} {s['abstain_is_correct']:>6} "
              f"{s['correct_and_all_pass']:>12} {s['false_pass']:>9} {str(s['half_or_more_correct']):>10}")
    total_mis = sum(s['misread'] for s in summary.values())
    total_fp = sum(s['false_pass'] for s in summary.values())
    esc_mis = sum(s['misread_escalated'] for s in summary.values())
    esc_fp = sum(s['false_pass_escalated'] for s in summary.values())
    print(f'TOTAL misread={total_mis} false_pass={total_fp}')
    print(f'ESCALATED(known exception, listed by id: {sorted(ESCALATED)}) misread={esc_mis} false_pass={esc_fp}')
    print(f'UNESCALATED misread={total_mis - esc_mis} false_pass={total_fp - esc_fp}')
    if not a.quiet:
        for r in rows:
            if r['result'] == 'misread':
                print('MISREAD' + (' (escalated)' if r.get('escalated') else ''), r['id'], r['text'])
    sys.exit(0)


if __name__ == '__main__':
    main()
