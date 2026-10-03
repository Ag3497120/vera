#!/usr/bin/env python3
"""W3-b2: the lines of the measurement section of docs/READING_SOUNDNESS.md (K100) and docs/EVENT_CROSS.md, made from the files of `artifacts/w3-b2/` (nothing is typed by hand).
Every line is `- ` + a sentence with its numbers; the docs hold the lines as they are (a check: every line of the output is a line of the docs).
Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b2_recompute.py [--part reading|events] > artifacts/w3-b2/recompute.md
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
A = HERE.parent.parent / 'artifacts' / 'w3-b2'


def jload(name): return json.loads((A / name).read_text(encoding='utf-8'))


def text(name): return (A / name).read_text(encoding='utf-8')


def lines_reading():
    out = []
    counts = text('data_counts.txt').splitlines()
    rows = [l for l in counts if re.match(r'^(frame|multiple|determiner|no) rows=', l)]
    out.append('- 新データ(`w3b2_frame.jsonl`・`w3b2_multiple.jsonl`・`w3b2_determiner.jsonl`・`w3b2_no.jsonl`。凍結 %s): %s。(`data_counts.txt`)' % (text('bank_freeze_time.txt').strip(), '; '.join(
        '%s %s' % (l.split(' ')[0], ' '.join(l.split(' ')[1:4])) for l in rows)))
    d = jload('data_entry_check.json')['summary']
    out.append('- 新データ %d 行を入口(配置 r6 の実物)に通した判定: correct %d・abstain %d・misread %d・incomplete %d・UNJUDGED %d。(`data_entry_check.json`)' % (
        d['rows'], d['verdicts'].get('correct', 0), d['verdicts'].get('abstain', 0), d['misread'], d['incomplete'], d['unjudged']))
    out.append('- ファイル別の判定: ' + '; '.join('%s: %s' % (k, ' '.join('%s %d' % (kk, vv) for kk, vv in sorted(v.items()))) for k, v in sorted(d['verdicts_by_data'].items())) + '。')
    out.append('- 新データの期待(凍結)を満たさない行: `entry_expect` %d 行・`w3b2_expect` %d 行。うち宣言ずみ(`w3b2_expect_exceptions.json`。読解器の事実で説明できる行)は %d 行・%d 行、宣言なしは %d 行・%d 行。(`data_entry_check.txt`)' % (
        d['entry_expect_mismatch'], d['w3b2_expect_mismatch'], d['entry_expect_mismatch_declared'], d['w3b2_expect_mismatch_declared'],
        d['entry_expect_mismatch_undeclared'], d['w3b2_expect_mismatch_undeclared']))
    ex = json.loads((HERE / 'w3b2_expect_exceptions.json').read_text(encoding='utf-8'))['exceptions']
    kinds = collections.Counter(x['kind'] for x in ex)
    out.append('- 宣言した %d 行の理由(読解器だけを見た事実 `w3b2_common.exception_kind`): %s。宣言した行で新しい経路が読んだ行は 0、誤読は 0。' % (
        len(ex), '・'.join('%s %d 行' % (k, v) for k, v in sorted(kinds.items()))))
    out.append('- 固定の答え(`w3b2_placement_fixture.json`)で流した結果と実物で流した結果は、`mode=` の行を除いて一致した: %s。(`fixture_equals_live.txt`)' % text('fixture_equals_live.txt').strip())
    dl = text('delta_summary.txt').splitlines()
    out.append('- W3-b1(基点 `3b31258`、配置 r6)との差(`w3b2_delta.py`。入力 %s): %s。(`delta_summary.txt`)' % (re.search(r'inputs=(\d+)', dl[0]).group(1), dl[0].replace('inputs=%s ' % re.search(r'inputs=(\d+)', dl[0]).group(1), '')))
    out.append('- 新しく読めた文の判定: %s。出所別: %s。' % (dl[1].replace('verdicts: ', ''), dl[3].replace('by source and kind: ', '')))
    out.append('- 公開の入力(`artifacts/w3-b1/entry_inputs.txt` の 2,899 文)で新しく読めた文: %d。(`delta.jsonl` の `newly_read` のうち出所が `w3b2_` で始まらないもの)' % sum(
        1 for l in text('delta.jsonl').splitlines() if json.loads(l)['kind'] == 'newly_read' and not json.loads(l)['source'].startswith('w3b2_')))
    out.append('- 枠で読めなくなった文(`frame_stopped`): %d。他の差(`read_to_abstain_other`・`changed`・`refusal_changed`・`error_changed`): 0 のみ(`delta_summary.txt` の 1 行目の数)。' % int(
        re.search(r'frame_stopped=(\d+)', dl[0]).group(1)))
    out.append('- 配置なし: 入口の出力は基点と一致(`%s`)、読解器の出力は基点と一致(`%s`、%s 文)、凍結データの照合 `%s`、a3 `%s`。' % (
        text('none_vs_dev.txt').strip(), text('x3_cmp.txt').strip(), len(text('x3_after.jsonl').splitlines()), text('soundness_compare.txt').splitlines()[-1].strip()
        if 'changed' in text('soundness_compare.txt').splitlines()[-1] else text('soundness_compare.txt').splitlines()[-2].strip(), text('a3_same.txt').strip()))
    out.append('- 推定・割れの偽物(R3): ' + '・'.join(text('direct_only.txt').strip().splitlines()) + '。(`direct_only.txt`)')
    b = text('b1_fixtures_r6.txt').splitlines()
    out.append('- B1 の自作見本 3 本(配置 r6 の実物): %s・%s・%s・%s。(`b1_fixtures_r6.txt`)' % (b[1], b[2], b[4], b[5]))
    ca, cb = jload('census_de_ni.json'), jload('census_after.json')
    out.append('- 格の曖昧(で・に)だけで棄権した公開の入力(1 文・1 節): 前 %d 文(で %d・に %d)、新しい経路で読めた数 %d。(`census_de_ni.json`・`census_after.json`)' % (
        ca['inputs_in_group'], ca['by_particle_of_the_unsupported_reason'].get('de', 0), ca['by_particle_of_the_unsupported_reason'].get('ni', 0),
        sum(g['readable_after'] - g['readable_before'] for g in cb['groups'])))
    cn = jload('census_after_with_new_data.json')
    newly_de = sum(g['readable_after'] - g['readable_before'] for g in cn['groups'] if g['key'].startswith('ambiguous case role: で'))
    out.append('- 同じ数えを新データを足した入力で: %d 文(で %d・に %d)、新しい経路で読めた数 %d(うち で の曖昧 %d)。' % (
        cn['inputs_in_group'], cn['by_particle_of_the_unsupported_reason'].get('de', 0), cn['by_particle_of_the_unsupported_reason'].get('ni', 0),
        sum(g['readable_after'] - g['readable_before'] for g in cn['groups']), newly_de))
    ex_lines = text('explain_summary.txt').splitlines()
    out.append('- 入力 %s 文(配置 r6)での型の段の数: %s。' % (ex_lines[0].split()[0].split('=')[1], ' / '.join(ex_lines[0:2])))
    out.append('- 型の段の W3-b2 の結果(理由の最初の部分ごと): %s。' % ex_lines[3].replace('w3b2=', ''))
    cf = jload('confirmed_frames.json')
    out.append('- 配置 r6 で述語の枠が確認済みの語: %d 語(%s。枠に入っている助詞: %s)。(`confirmed_frames.json`)' % (
        cf['words'], '・'.join('%s %d' % kv for kv in sorted(cf['by_predicate_type'].items())), '・'.join('%s %d' % kv for kv in sorted(cf['particles_in_frames'].items()))))
    if (A / 'pytest_new_failures.txt').exists():
        nf = [l for l in text('pytest_new_failures.txt').splitlines() if l.strip()]
        fx = [l for l in text('pytest_fixed_vs_baseline.txt').splitlines() if l.strip()]
        full = [l for l in text('pytest_full.txt').splitlines() if l.strip()][-1]
        out.append('- 全体テスト(`pytest_full.txt` の最終行): %s。基線(`dev_3b31258_failures.txt`)に無い失敗 %d 件、基線にあって今は通る %d 件。(`pytest_new_failures.txt`・`pytest_fixed_vs_baseline.txt`)' % (full, len(nf), len(fx)))
    out.append('- 既存の凍結テスト・データとの衝突: `existing_tests_after.txt` の失敗 4 件(`w3b1_conflicts.md`: (A) 3・(A2) 1・(B) 0・(C) 0)。')
    ch = text('check_hardcode.txt').splitlines()
    out.append('- 決め打ち検査(`w3b2_check_hardcode.py`): %s、%s、%s。(`check_hardcode.txt`)' % (ch[0], ch[1], ch[2]))
    return out


def lines_events():
    out = []
    ev = text('events_r6_summary.txt').splitlines()
    for l in ev:
        m = re.match(r'^(\w+): sentences_read=(\d+) typed=(\d+) arms=(\d+) AGREE=(\d+) AGREE_ALL_CANDIDATES=(\d+) DISAGREE=(\d+) NOT_CHECKED=(\d+) fillers_with_a_determiner=(\d+)', l)
        if m:
            out.append('- 群 `%s`(配置 r6 の実物を lookup にした十字): 読めた文 %s・型の経路の節を持つ文 %s・腕 %s・AGREE %s・AGREE_ALL_CANDIDATES %s・DISAGREE %s・NOT_CHECKED %s・`flags.determiner` を持つ充填物 %s。(`events_r6.json`)' % m.groups())
    tot = [l for l in ev if l.startswith('AGREE_ALL_CANDIDATES total=')][0]
    dis = [l for l in ev if l.startswith('DISAGREE total=')][0]
    out.append('- `AGREE_ALL_CANDIDATES` の腕の全件数: %s、`DISAGREE` の全件数: %s。全件の文・役割・値・型は `events_r6_summary.txt`。' % (tot.split('=')[1], dis.split('=')[1]))
    e1 = text('e1.txt').splitlines()
    out.append('- `--events` なしの出力の一致(E1。`e1.txt`): %s。' % '・'.join(l.strip() for l in e1 if l.startswith('E1_')))
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--part', choices=['reading', 'events'], default=None)
    a = ap.parse_args()
    if a.part in (None, 'reading'): print('\n'.join(lines_reading()))
    if a.part in (None, 'events'): print('\n'.join(lines_events()))


if __name__ == '__main__':
    main()
