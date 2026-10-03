"""Builds the measured-numbers block of docs/OBSERVATION.md from the files under artifacts/w3-c (nothing is typed by hand).

    python tests/observe/recompute.py --write    # replace the block between <!-- recompute:begin --> and <!-- recompute:end --> in the document
    python tests/observe/recompute.py --check    # exit 0 when the block in the document is exactly what the artifacts give now
The prose of the document outside the block carries no measured number; every number lives in this block.
"""
import argparse
import json
import re
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[2]
A = TREE / 'artifacts' / 'w3-c'
DOC = TREE / 'docs' / 'OBSERVATION.md'
DATA = TREE / 'tests' / 'observe' / 'data'
BEGIN, END = '<!-- recompute:begin -->', '<!-- recompute:end -->'


def jl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding='utf-8').splitlines() if l.strip()]


def jf(name):
    return json.loads((A / name).read_text(encoding='utf-8'))


def first_line(name):
    p = A / name
    return p.read_text(encoding='utf-8').splitlines()[0] if p.exists() else '(not measured)'


def lines_of(name):
    p = A / name
    return p.read_text(encoding='utf-8').splitlines() if p.exists() else []


def agent_of(cell_key):
    """The agent filler of a cell key (a display helper: the key is `cell:` + the canonical json of the content)."""
    try:
        content = json.loads(cell_key[len('cell:'):])
        return '/'.join(next(a['surfaces'] for a in content['arms'] if a['role'] == 'agent'))
    except Exception:
        return cell_key[:30]


def kv(d):
    return ', '.join('%s %s' % (k, v) for k, v in sorted(d.items())) if d else '(none)'


def build():
    out = []
    w = out.append
    w('### 測定結果（`tests/observe/recompute.py` が `artifacts/w3-c/` から作った区間。手で書き換えない）')
    w('')
    # --- data
    ja, en = jl(DATA / 'seeds_ja.jsonl'), jl(DATA / 'seeds_en.jsonl')
    cases = jl(DATA / 'viewpoints.jsonl') + jl(DATA / 'viewpoints_add1.jsonl') + jl(DATA / 'viewpoints_r2.jsonl')
    obs = jl(A / 'reader_seed_obs.jsonl')
    by_lang = {}
    for r in obs:
        k = r.get('lang') or 'none'
        by_lang.setdefault(k, [0, 0])
        by_lang[k][0] += 1
        by_lang[k][1] += 1 if r['readable'] else 0
    frozen = json.loads((DATA / 'FROZEN.json').read_text(encoding='utf-8'))['stages']
    w('**検査データ**（`tests/observe/data/`、凍結）')
    w('')
    w('- 種の文: 日本語 %d・英語 %d（合計 %d）。ケース（視点）%d（`viewpoints.jsonl`・`viewpoints_add1.jsonl`・`viewpoints_r2.jsonl`）。台帳 %d 本。' % (len(ja), len(en), len(ja) + len(en), len(cases), len(list((DATA / 'ledgers').glob('L*.jsonl')))))
    w('- 読解器だけに通した結果（`reader_seed_obs.jsonl`）: 日本語 %d 文のうち読めた %d、英語 %d 文のうち読めた %d。読めた文のうち複数の節を持つもの %d、読解器が出した関係 %d 本。' % (
        by_lang['ja'][0], by_lang['ja'][1], by_lang['en'][0], by_lang['en'][1],
        sum(1 for r in obs if r['readable'] and len(r['clauses']) > 1), sum(len(r['relations']) for r in obs if r['readable'])))
    w('- 凍結の時刻順（`FROZEN.json`）: ' + ' → '.join('%s %s' % (k, v['date'].split(' ')[1]) for k, v in frozen.items()) + '。事前登録（`artifacts/w3-c/prereg.txt` の `registered_at`）: %s。' % re.match(r'registered_at: (\S+ \S+ \S+)', lines_of('prereg.txt')[0]).group(1))
    w('')
    cmp_ = jf('expected_compare.json')
    w('**凍結した期待と観測器**（`expected_compare.json`）: 1 ターンの期待のあるケース %d のうち、そのまま一致 %d・食い違い %d（%s）。食い違いは直さず `disagreements.json`（%d 件・%d ケース）に凍結し、凍結分を当てはめると食い違い %d。2 ターンのケース %d のうち、焦点と順位が期待と一致 %d。O4 の旗の食い違い（`disagreements_o4.json`、第 1 ラウンドの規則の下のもの）は %d 行。第 2 ラウンド: `expected_r2.jsonl` が 2 ターンの行 %s を置き換え、1 ターンのケース %d を足した（新しい規則で観測器を流す前に書いて凍結。`disagreements_r2.json`（食い違いの凍結）: %s）。' % (
        cmp_['cases_with_one_turn_expectation'], cmp_['equal_raw'], cmp_['different_raw'], ', '.join('%s: %s' % (k, '/'.join(v)) for k, v in sorted(cmp_['different_raw_cases'].items())),
        cmp_['frozen_disagreement_rows'], len(cmp_['frozen_disagreement_cases']), cmp_['different_after_frozen_disagreements'], cmp_['two_turn_cases'], cmp_['two_turn_focus_and_ranks_equal'],
        len(json.loads((DATA / 'disagreements_o4.json').read_text(encoding='utf-8'))['rows']), ', '.join(cmp_['expectations_superseded_by_expected_r2']),
        sum(1 for r in jl(DATA / 'expected_r2.jsonl') if r['outcome'] != 'TURNS'), '食い違いがあり作った' if (DATA / 'disagreements_r2.json').exists() else '食い違いが無く作っていない'))
    w('')
    sm = jf('summary.json')
    w('**全ケースの集計**（`summary.json`、各ケースの 1 ターン目）: 出力 %d。焦点の型 %s。NO_ANCHOR の理由 %s。錨と移動した升の数 %d（うち移動した升 %d）。主張の型 %s。占有の印 %s。移動した升の型一致 %s。実現できた文 %d、実現の拒否 %s。`FACE_SWAP` を配置ファイル付きで試したケース %d、`EDGE` を試したケース %d（うち升が出たもの %d）。' % (
        sm['outputs'], kv(sm['outcome']), kv(sm['no_anchor_reason']), sm['elements'], sm['moved_elements'], kv(sm['claims']), kv(sm['occupied']), kv(sm['type_agreement_moved']),
        sm['realized'], kv(sm['refused']), sm['swap_cases_with_a_placement_file'], sm['edge_cases'], sm['edge_cases_with_a_move']))
    w('')
    w('**O1**（バイトの一致・再生）: `o1_bytes.txt`: %s。`o1_replay.txt`: %s。' % (first_line('o1_bytes.txt'), first_line('o1_replay.txt')))
    w('')
    o2 = jf('o2_reobserve.json')
    w('**O2**（再観測可能率、`o2_reobserve.json`）: 要素 %d・再観測できた %d・できなかった %d（理由別 %s）。実現できた文 %d のうち読み直して同じ升に戻ったもの %d、内容語に観測の充填物以外があったもの %d。別の言い方 %d 本のうち読み直して同じ升に戻ったもの %d、内容語に余りがあったもの %d。実現の拒否 %s。' % (
        o2['elements'], o2['reobserved'], o2['mismatch'], kv(o2['mismatch_by_reason']), o2['realized'], o2['realized_reread_equal'], o2['extra_content_words'],
        o2['alternatives_checked'], o2['alternatives_reread_equal'], o2['alternatives_extra_content_words'], kv(o2['refused_by_reason'])))
    w('')
    g = lines_of('o3_grep.txt')
    w('**O3**（乱数・ハッシュ順・時計）: `o3_grep.txt` の該当行 %d（%s）。中間職が 1 行ずつ読む一覧 `o3_review_points.txt` は %d 行。' % (len(g), '; '.join(re.sub(r'^.*/verantyx/', 'verantyx/', l).strip()[:110] for l in g), len(lines_of('o3_review_points.txt'))))
    w('')
    o4 = jf('o4.json')
    pr = o4['pair_L09_L10']
    w('**O4**（揺らぎ、`o4.json`。第 2 ラウンドで判定を事前登録の P10 のとおりに厳しくした）: 2 ターンの行 %d。判定: 1 回目が TIE なら 2 回目も同じ出力（候補も同じ）、代替が無ければ同じ出力、代替があれば変わり、かつ新しい焦点と古い焦点を分けた段の `ledger_seqs` に 1 回目のターンで追記された行がある。事前登録の読み（代替は 2 回目の台帳で見る）で規則に合うもの %d・反例 %s。もう一つの読み（代替は 1 回目の台帳で見る）で合うもの %d・反例 %s。L09 と L10 は台帳のうち行 %s だけが違い、出力は %s、2 つの trace の段の値の差 %d 件は %s。' % (
        o4['rows_total'], o4['rows_ok'], ', '.join(o4['violations']) or '(なし)', o4['rows_ok_if_alternative_is_read_at_turn1_state'], ', '.join(o4['violations_if_alternative_is_read_at_turn1_state']) or '(なし)',
        ','.join(str(x) for x in pr['differing_ledger_seqs']), '違う' if pr['outputs_differ'] else '同じ', len(pr['stage_differences']),
        'すべてその行が作る' if pr['every_difference_is_made_by_the_differing_line'] else 'その行が作らないものを含む'))
    w('')
    w('| 行 | 台帳 | 1 回目 | 2 回目 | 代替（2 回目の台帳の状態） | 代替（1 回目の台帳の状態） | 同じ出力 | 変化を分けた段と、1 回目が追記した行 | 規則に合う（登録の読み） | 規則に合う（もう一つの読み） |')
    w('|---|---|---|---|---|---|---|---|---|---|')
    short = lambda v: ('TIE ' if isinstance(v, list) else '') + (' / '.join(x.split('agent=')[1].split(';')[0] if 'agent=' in x else x for x in v) if isinstance(v, list) else (v.split('agent=')[1].split(';')[0] if v and 'agent=' in v else str(v)))

    def why(r):
        a = r['attribution_registered_reading']
        if a is None: return '（変化なし）' if r['same_focus_and_realization'] else '（代替なしで変化）'
        return '; '.join('%s: 行 %s' % (sp['stage'], ','.join(str(q) for q in sp['turn1_appended_among_them']) or '(なし)') for sp in a['separations'])
    for r in o4['rows']:
        w('| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |' % (r['case'], r['ledger'], short(r['turn1_focus']), short(r['turn2_focus']), r['alternatives'], r['alternatives_at_turn1_state'],
                                                          r['same_focus_and_realization'], why(r), r['rule_ok'], r['rule_ok_if_alternative_is_read_at_turn1_state']))
    w('')
    for name in ('O4-a-L03', 'O4-e-L07'):
        r = [x for x in o4['rows'] if x['case'] == name][0]
        w('`%s` の 2 回目の trace（`o4.json` から。升は主語の語で示す）: 発話の段の入力 `%s`、境目 `%s`、各升の段の値を作った台帳の seq `%s`' % (name, json.dumps(r['turn2_utterance'], ensure_ascii=False), json.dumps(r['turn2_boundaries'], ensure_ascii=False), json.dumps({agent_of(k): {s_: q for s_, q in v.items() if q} for k, v in r['turn2_cells_ledger_seqs'].items()}, ensure_ascii=False)))
        w('')
    chk = lines_of('o4_old_rule_check.txt')
    w('**O4 の判定そのものの確認**（`o4_old_rule_check.txt`。観測器の `build_context` を一時的に旧規則=錨の文を除かない、に差し替えて同じ判定を流した結果。ファイルは変えていない）: %s。' % ' / '.join(l for l in chk if l.startswith(('registered reading', 'other reading'))))
    w('')
    w('**O5**（`o5.txt`）: %s。%s。' % (first_line('o5.txt'), lines_of('o5.txt')[1] if len(lines_of('o5.txt')) > 1 else ''))
    w('')
    w('**O6**（`o6.txt`）: ' + ' / '.join(lines_of('o6.txt')))
    w('')
    for label, name in (('索引なし', 'b3_selfmade_summary.json'), ('実索引', 'b3_selfmade_idx_summary.json')):
        b = jf(name)
        w('**O7（自作の B3・%s、`%s`）**: 問 %d・錨 %d・視点 %d。NO_ANCHOR %s。実現できた文 %d、実現の拒否 %s。観測した節 %d のうち再観測できなかった節（幻覚）%d。主張の型 %s。占有の印 %s。' % (
            label, name, b['items'], b['anchors'], b['viewpoints'], kv(b['no_anchor']), b['realized'], kv(b['refused']), b['clauses'], b['unreobservable_clauses'], kv(b['claim']),
            kv({k: v for k, v in b['occupied'].items() if v})))
        w('')
    pf = lines_of('pytest_full.txt')
    w('**O8**: 全体テスト `pytest_full.txt` の最終行: `%s`。基線にない失敗 `pytest_new_failures.txt`: %d 行（説明: `pytest_new_failures.explained.md`）。新しいテスト `pytest_new_tests.txt` の最終行: `%s`。実現器の不変 `o8_realize_parity.txt`: %s（%s）。固定の語の検査 `check_no_data_words.txt`: %s。決め打ちの検査 `check_hardcode.txt`（追加行）: %s / %s、新しい 2 ファイルを加えた版 `check_hardcode_with_new_files.txt`: %s / %s。' % (
        (pf[-1] if pf else '(not measured)'), len([l for l in lines_of('pytest_new_failures.txt') if l.strip()]), (lines_of('pytest_new_tests.txt') or ['(not measured)'])[-1].strip('= '),
        first_line('o8_realize_parity.txt'), lines_of('o8_realize_parity.txt')[1].split(' (')[0] if len(lines_of('o8_realize_parity.txt')) > 1 else '',
        first_line('check_no_data_words.txt'), lines_of('check_hardcode.txt')[1], lines_of('check_hardcode.txt')[2],
        lines_of('check_hardcode_with_new_files.txt')[1], lines_of('check_hardcode_with_new_files.txt')[2]))
    w('')
    w('**差分の大きさ**（`common_additions_only.txt`、基点 5cae978 に対する追加・削除の行数）: ' + '; '.join('%s +%s -%s' % (l.split('\t')[2], l.split('\t')[0], l.split('\t')[1]) for l in lines_of('common_additions_only.txt')) + '。')
    return '\n'.join(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    block = BEGIN + '\n' + build() + '\n' + END
    doc = DOC.read_text(encoding='utf-8')
    if BEGIN not in doc or END not in doc:
        print('the document has no recompute block'); return 2
    current = doc[doc.index(BEGIN):doc.index(END) + len(END)]
    if args.write:
        DOC.write_text(doc.replace(current, block), encoding='utf-8')
        print('block written (%d lines)' % block.count('\n')); return 0
    if args.check:
        if current == block:
            print('recompute --check: the block of the document equals the artifacts'); return 0
        print('recompute --check: DIFFERENT'); return 1
    print(block)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
