"""Builds the generated blocks of the question section of docs/OBSERVATION.md from the files under artifacts/w3-c2 (nothing in them is typed by hand).

    python tests/observe/question/recompute_q.py --write    # replace the two blocks (w3c2-entry, w3c2-measured) in the document
    python tests/observe/question/recompute_q.py --check    # exit 0 when the blocks in the document are exactly what the artifacts give now
The entry block runs the real command (`python -m verantyx.cli observe ...`, a subprocess with a clean environment) on three questions of the frozen data and pastes the
fixed part of its output (focus, status, fillers with the ids of the sentences, the structure counts); the measured block is built from q2_score*.json and the other files.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parents[2]
A = TREE / 'artifacts' / 'w3-c2'
DOC = TREE / 'docs' / 'OBSERVATION.md'
Q = HERE
MARKS = {'entry': ('<!-- w3c2-entry:begin -->', '<!-- w3c2-entry:end -->'), 'measured': ('<!-- w3c2-measured:begin -->', '<!-- w3c2-measured:end -->')}
EXAMPLES = (('FILLED', 'QD05', '母は台所で何を作った？'), ('TIE', 'QD01', '誰が生徒に地図を渡した？'), ('NO_ATTESTED_CELL', 'QD01', '誰が生徒に手紙を送った？'))


def entry_block():
    rel = lambda p: str(Path(p).relative_to(TREE))
    out = ['### 入口の実行出力（`recompute_q.py` が実際に走らせて貼った。手で書き換えない）', '']
    env = {'HOME': os.environ.get('HOME', ''), 'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(TREE), 'PYTHONHASHSEED': '0'}
    for want, doc, text in EXAMPLES:
        args = ['--anchor-text', text, '--anchor-kind', 'question', '--structure', rel(Q / 'docs' / (doc + '.jsonl')), '--no-index']
        done = subprocess.run([sys.executable, '-m', 'verantyx.cli', 'observe', *args], capture_output=True, text=True, env=env, cwd=str(TREE), timeout=180)
        d = json.loads(done.stdout)
        a = d['answer']
        show = {'exit_code': done.returncode, 'focus': {k: (v if k != 'candidates' else '[%d cells]' % len(v)) for k, v in d['focus'].items() if k != 'cell_key'},
                'answer.status': a['status'], 'answer.question': a['question'],
                'answer.fillers': [{'surface': f['surface'], 'evidence': [{'reading': e['reading'], 'cross_index': e['cross_index'], 'text': e['text']} for e in f['evidence']],
                                    'hole_type_check': f['hole_type_check']['verdict'] + (':' + f['hole_type_check']['reason'] if f['hole_type_check']['reason'] else '')}
                                   for f in a['fillers']],
                'answer.structure': a['structure'], 'answer.reasons': a['reasons'], 'abstain': d['abstain']}
        assert a['status'] == want, (want, a['status'])
        out += ['`%s`（%s）' % ('python -m verantyx.cli observe ' + ' '.join("'%s'" % x if (' ' in x or '？' in x) else x for x in args), want), '```json',
                json.dumps(show, ensure_ascii=False, indent=1), '```', '']
    return '\n'.join(out).rstrip('\n')


def jf(name):
    return json.loads((A / name).read_text(encoding='utf-8'))


def lines_of(name):
    p = A / name
    return [l for l in p.read_text(encoding='utf-8').splitlines() if l.strip()] if p.exists() else []


def tally(d):
    return '%d / %d / %d / %d' % (d['CORRECT'], d['WRONG'], d['FALSE_NONE'], d['ABSTAINED'])


def cause_of(row, truth):
    if truth['extension_support'] and row.get('extending'): return '腕が多い文だけが正解を述べる（一致の定義 D9 で一致しない。`structure.extending` に出ている）'
    if truth['unread_support']: return '正解を述べる文が読解器に読めない（`structure.unread_ids` に出ている）'
    return '原因は分類できない（要調査）'


def measured_block():
    s = jf('q2_score.json')
    qs = {q['id']: q for q in (json.loads(l) for l in (Q / 'questions.jsonl').read_text(encoding='utf-8').splitlines() if l.strip())}
    t = s['totals']
    L = ['### 測定結果（`tests/observe/question/recompute_q.py` が `artifacts/w3-c2/` から作った区間。手で書き換えない）', '']
    L.append('**Q2**（出典: `artifacts/w3-c2/q2_score.json`、検査データ `tests/observe/question/`、凍結 %s）: 全 %d 問。CORRECT %d・WRONG %d・FALSE_NONE %d・ABSTAINED %d（正答率 %.1f%%。誤った答え %d）。' % (
        json.loads((Q / 'FROZEN_Q.json').read_text(encoding='utf-8'))['frozen_at'], t['n'], t['CORRECT'], t['WRONG'], t['FALSE_NONE'], t['ABSTAINED'], 100.0 * t['CORRECT'] / t['n'], t['WRONG']))
    ca = s['totals_with_corrections']
    L.append('正解の訂正（`corrections.jsonl`）: %s。訂正を当てた結果: CORRECT %d・WRONG %d・FALSE_NONE %d・ABSTAINED %d。' % (
        '無し' if not ca['corrections_applied'] else ','.join(ca['corrections_applied']), ca['CORRECT'], ca['WRONG'], ca['FALSE_NONE'], ca['ABSTAINED']))
    L += ['', '| 穴の型 | 問 | CORRECT / WRONG / FALSE_NONE / ABSTAINED |', '|---|---|---|']
    n_by = {}
    for q in qs.values(): n_by[q['hole']] = n_by.get(q['hole'], 0) + 1
    for k, v in sorted(s['by_hole'].items()): L.append('| %s | %d | %s |' % (k, n_by[k], tally(v)))
    L += ['', '| 言語 | CORRECT / WRONG / FALSE_NONE / ABSTAINED |', '|---|---|']
    for k, v in sorted(s['by_lang'].items()): L.append('| %s | %s |' % (k, tally(v)))
    L += ['', '| 正解の種類 | CORRECT / WRONG / FALSE_NONE / ABSTAINED |', '|---|---|']
    for k, v in sorted(s['by_truth_kind'].items()): L.append('| %s | %s |' % (k, tally(v)))
    L += ['', '`answer.status` の件数: ' + '・'.join('%s %d' % (k, v) for k, v in sorted(s['status_counts'].items())) + '。']
    L += ['', '棄権（ABSTAINED）の理由を穴の型別に（`READ:` は読解器の理由、それ以外は観測の状態）:']
    for h, c in sorted(s['abstained_reasons_by_hole'].items()): L.append('- %s: %s' % (h, '・'.join('%s %d' % (k, v) for k, v in sorted(c.items()))))
    L += ['', 'FALSE_NONE（正解があるのに「無い」と返したもの）の 1 件ずつの原因:']
    for r in s['false_none']: L.append('- %s 「%s」（穴 %s、状態 %s）: %s' % (r['id'], r['text'], r['hole'], r['status'], cause_of(r, qs[r['id']]['truth'])))
    if not s['false_none']: L.append('- （無し）')
    L += ['', '誤った答え（WRONG）: %s。' % ('無し' if not s['wrong'] else ' / '.join('%s 「%s」' % (r['id'], r['text']) for r in s['wrong']))]
    rounds = sorted(p.name for p in A.glob('q2_score.r*.json'))
    L.append('規則を直した回ごとの記録（`q2_score.rN.json`）: ' + '。'.join('%s は WRONG %d（%s）' % (n, jf(n)['totals']['WRONG'], ','.join(r['id'] for r in jf(n)['wrong']) or '無し') for n in rounds) + '。')
    tm = jf('q2_timing.json')
    L.append('所要時間（`q2_timing.json`）: ' + ('負荷のため計測せず（load %s）' % tm['load'] if 'skipped' in tm else '%d 問で合計 %.2f 秒（1 問あたり 中央値 %.4f 秒・最大 %.3f 秒。1 分平均の負荷 %.2f）' % (
        tm['questions'], tm['total_secs'], tm['median_secs'], tm['max_secs'], tm['load_1min'])) + '。')
    L += ['', '**Q1（平叙文の出力が 1 バイトも変わらない）**（出典: `q1_read_cmp.txt`・`q1_observe_cmp.txt`）:']
    L += ['- 読解 ' + l for l in lines_of('q1_read_cmp.txt')] or ['- （未測定）']
    L += ['- 観測 ' + l for l in lines_of('q1_observe_cmp.txt')]
    L += ['', '**Q4**: `q4_observe_grep.txt` %d 行（内訳は判断記録 J10）。`q4_no_data_words.txt`: %s。`check_hardcode.txt`: %s / %s。' % (
        len(lines_of('q4_observe_grep.txt')), (lines_of('q4_no_data_words.txt') or ['(未測定)'])[0], (lines_of('check_hardcode.txt') + ['', '', '', ''])[1], (lines_of('check_hardcode.txt') + ['', '', '', ''])[2])]
    L += ['', '**共通**: `common_numstat.txt`（基点 2478fc7 に対する追加・削除の行数、削除列はすべて 0）:']
    L += ['- ' + l for l in lines_of('common_numstat.txt')] or ['- （未測定）']
    L += ['', '**Q6**: `pytest_related.txt` の最終行: %s。全体テスト `pytest_full.txt` の最終行: %s。基線にない失敗 `pytest_new_failures.txt`: %d 行。増えた成功 `pytest_fixed.txt`: %d 行。' % (
        (lines_of('pytest_related.txt') or ['(未測定)'])[-1], (lines_of('pytest_full.txt') or ['(未測定)'])[-1], len(lines_of('pytest_new_failures.txt')), len(lines_of('pytest_fixed.txt')))]
    return '\n'.join(L)


def render_doc(text):
    for key, fn in (('entry', entry_block), ('measured', measured_block)):
        b, e = MARKS[key]
        i, j = text.index(b), text.index(e)
        text = text[:i + len(b)] + '\n' + fn() + '\n' + text[j:]
    return text


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true'); ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    old = DOC.read_text(encoding='utf-8')
    new = render_doc(old)
    if args.write:
        DOC.write_text(new, encoding='utf-8'); return 0
    return 0 if new == old else 1


if __name__ == '__main__':
    raise SystemExit(main())
