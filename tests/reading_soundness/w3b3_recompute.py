#!/usr/bin/env python3
"""W3-b3: the lines of numbers that docs/READING_SOUNDNESS.md section 10C and docs/EVENT_CROSS.md quote, computed from the files of artifacts/w3-b3/ (nothing is typed by hand). The
documents hold these lines as they are; `missing 0` is the check (tests/reading_soundness/w3b3_recompute.py > recompute.md, then every non-blank line of it is looked up in the two docs).
Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b3_recompute.py [--artifacts DIR]
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w3b3_common as C


def read(p): return Path(p).read_text(encoding='utf-8')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--artifacts', default=str(C.TREE / 'artifacts' / 'w3-b3'))
    A = Path(ap.parse_args().artifacts)
    L = []
    emit = L.append
    times = [read(A / n).strip() for n in ('bank_freeze_time.txt', 'placement_fixture_time.txt', 'tests_freeze_time.txt', 'impl_start_time.txt')]
    pre = dict(l.split(': ', 1) for l in read(A / 'prereg_time.txt').splitlines())
    emit('- 事前登録の時刻の順（`prereg_time.txt`・`bank_freeze_time.txt`・`placement_fixture_time.txt`・`tests_freeze_time.txt`・`impl_start_time.txt`）: 登録 %s < データの凍結 %s < 固定の答え %s < テストの凍結 %s < 実装の開始 %s' % (pre['registered'], *times))
    inputs = [l for l in read(A / 'entry_inputs.txt').splitlines() if l.strip()]
    # S1
    emit('- S1-1 読解器 `document_view`（x3: 凍結した日本語の銀行と 13 の例文ファイル。%d 文）: %s（`x3_cmp.txt`）' % (len([l for l in read(A / 'x3_after.jsonl').splitlines() if l.strip()]), read(A / 'x3_cmp.txt').strip()))
    emit('- S1-2 凍結データの照合（`harness.py`）: %s（`soundness_compare.txt`）。a3: %s（`a3_same.txt`）' % (read(A / 'soundness_compare.txt').strip().splitlines()[0], read(A / 'a3_same.txt').strip()))
    emit('- S1-3 入口・配置なし（%d 入力）: %s（`none_vs_dev.txt`）' % (len(inputs), read(A / 'none_vs_dev.txt').strip()))
    d = read(A / 'delta_summary.txt').splitlines()
    emit('- S1-4 入口・配置 r6、基点との差（`w3b3_delta.py`。終了コード %s）: %s' % (read(A / 'delta_exit.txt').strip().replace('exit=', ''), d[0]))
    emit('- S1-4 新しく読めた文の判定: %s。出所: %s（`delta_summary.txt`）' % (d[1].replace('verdicts: ', ''), d[2].replace('by source and kind: ', '')))
    q = read(A / 'queries_compare.txt').splitlines()[0]
    emit('- S1-4 配置への問い合わせ（基点との比較。`queries_compare.txt`）: %s' % q)
    for l in read(A / 'direct_only.txt').splitlines(): emit('- S1-5 推定・割れた配置の偽物（`direct_only.txt`）: %s' % l)
    # explain summary
    for l in read(A / 'explain_summary.txt').splitlines():
        if l.startswith('group='): emit('- 引き金（`explain_summary.txt`）: %s' % l)
    for g in ('public', 'new_data'):
        s = json.loads(re.search(r'  %s_triggered=(.*)' % g, read(A / 'explain_summary.txt')).group(1)); r = json.loads(re.search(r'  %s_read=(.*)' % g, read(A / 'explain_summary.txt')).group(1))
        emit('- 切れ目の種類ごとの引き金の数と読めた数（群 %s。`explain_summary.txt`）: %s' % (g, ', '.join('%s %d/%d' % (k, v, r.get(k, 0)) for k, v in sorted(s.items()))))
        for key in ('stopped', 'stopped_detail', 'not_triggered'):
            emit('- 棄権の理由の型ごとの数（群 %s・%s。`explain_summary.txt`）: %s' % (g, key, re.search(r'  %s_%s=(.*)' % (g, key), read(A / 'explain_summary.txt')).group(1)))
    # data
    j = json.loads(read(A / 'data_entry_check.json'))
    sm = j['summary']
    emit('- 新データ（relative 60・connective 60・parallel 30・w1a4 53。`data_entry_check.json`）: 判定 %s、誤読 %d・不完全 %d・判定不能 %d' % (json.dumps(sm['verdicts'], ensure_ascii=False, sort_keys=True), sm['misread'], sm['incomplete'], sm['unjudged']))
    emit('- 新データの予想との食い違い: entry_expect %d・w3b3_expect %d・structure_expect %d（全件は `expect_mismatches.md`）' % (sm['entry_expect_mismatch'], sm['w3b3_expect_mismatch'], sm['structure_expect_mismatch']))
    emit('- 新データの判定（ファイルごと。`data_entry_check.json`）: %s' % json.dumps(sm['verdicts_by_data'], ensure_ascii=False, sort_keys=True))
    emit('- fixture と live の判定（`fixture_equals_live.txt`）: %s' % read(A / 'fixture_equals_live.txt').strip())
    rows = j['rows']
    read_rows = [r for r in rows if r['explain'] and r['explain']['read']]
    by_cut = collections.Counter(r['explain']['cut']['kind'] for r in read_rows)
    emit('- 新データで入口が読んだ行: %d（切れ目の種類ごと: %s）' % (len(read_rows), json.dumps(dict(sorted(by_cut.items())), ensure_ascii=False)))
    conv = [r for r in rows if r['data'] in ('relative', 'connective', 'parallel')]
    # the rows the convention reads (behavior read) that the entry does not: by the first gate
    loss = collections.Counter()
    for r in conv:
        row = next(x for x in C.load_data(r['data']) if x['id'] == r['id'])
        if row['behavior'] != 'read' or r['explain']['read']: continue
        why = r['explain']['reason'] or ''
        key = why.split(':')[0]
        if key in ('CLAUSE_FORM_NOT_READ', 'HEAD_ROLE_UNDETERMINED', 'ELLIPSIS_UNDETERMINED', 'RELATION_TYPE_UNDETERMINED', 'CLAUSE_SCOPE_AMBIGUOUS'): key = key + ':' + why.split(':')[1].split('=')[0]
        loss[key] += 1
    emit('- 被覆の損失の内訳（規約どおり読める `behavior: read` の行のうち入口が読まなかった行を、止めた門ごとに。派生の疑いの門 `PLACEMENT_PREDICATE_POSSIBLY_DERIVED`・語尾の門 `PLACEMENT_PREDICATE_TAIL_UNINTERPRETED`・目的語の門 `ELLIPSIS_UNDETERMINED:object`・主辞の腕の各理由は細目まで。`data_entry_check.json`）: %s' % json.dumps(dict(sorted(loss.items())), ensure_ascii=False))
    gate = collections.Counter()
    for r in rows:
        why = (r['explain'] or {}).get('reason') or ''
        for g in ('PLACEMENT_PREDICATE_POSSIBLY_DERIVED', 'PLACEMENT_PREDICATE_TAIL_UNINTERPRETED'):
            if g in why: gate[g] += 1
        if why.startswith('ELLIPSIS_UNDETERMINED:object'): gate['ELLIPSIS_UNDETERMINED:object'] += 1
        if why.startswith('HEAD_ROLE_UNDETERMINED'): gate['HEAD_ROLE_UNDETERMINED:' + why.split(':')[1].split('=')[0]] += 1
    emit('- 新データの全行（203）で止めた門のうち、既存の門と目的語の門と主辞の腕の理由ごとの数（`data_entry_check.json`）: %s' % json.dumps(dict(sorted(gate.items())), ensure_ascii=False))
    tm = json.loads(read(A / 'timing_r6.json'))
    emit('- 実行時間（入口・配置 r6・今の木。基点と並行に流したので、基点との比較には使わない。`timing_r6.json`）: %d 入力、壁時計 %s 秒、1 入力あたり 中央値 %s ms・最大 %s ms（1 分平均の負荷 %s → %s）' % (
        tm['inputs'], tm['wall_seconds'], tm['median_ms_per_input'], tm['max_ms_per_input'], tm['load_1min_before'], tm['load_1min_after']))
    # S3
    emit('- S3 W1-a4 の誤読の全 53 文: %s、`readable: false` %s 文、基点（dev・r6）と出力が一致 %s 文（`s3_pytest.txt`・`s3_live.txt`・`s3_vs_dev.txt`）' % (
        read(A / 's3_pytest.txt').strip().splitlines()[-1], re.search(r'readable false (\d+)', read(A / 's3_vs_dev.txt')).group(1), re.search(r'equals dev \(r6\) (\d+)', read(A / 's3_vs_dev.txt')).group(1)))
    emit('- S3 の判定（`s3_live.txt`）: %s' % [l for l in read(A / 's3_live.txt').splitlines() if l.startswith('verdicts=')][0])
    # S4 preparation
    emit('- S4 の下準備・自作の B1 見本 3 本（配置 r6。`b1_fixtures_r6.txt`）: %s、誤読 %s・不完全 %s' % (re.search(r'verdicts=(.*)', read(A / 'b1_fixtures_r6.txt')).group(1).split('verdicts_by_data')[0].strip(),
                                                                                       re.search(r'misread=(\d+)', read(A / 'b1_fixtures_r6.txt')).group(1), re.search(r'incomplete=(\d+)', read(A / 'b1_fixtures_r6.txt')).group(1)))
    for l in read(A / 'multiple_census.txt').splitlines():
        g = l.split(' ', 1)[0]
        emit('- S4 の下準備・`multiple predicates` の棄権（群 %s。dev と今、配置 r6。`multiple_census.txt`）: %s' % (g, l.split(' ', 1)[1]))
    # S5
    o = json.loads(read(A / 'observe_edge.json'))
    ro = json.loads(read(A / 'observe_edge_reobserve.json'))
    emit('- S5 観測の EDGE（`observe_edge.txt`）: ケース %d・EDGE で出た升があるケース %d・EDGE で出た升の数 %d' % (len(o['cases']), sum(1 for c in o['cases'] if c.get('cells_by_edge')), o['cells_by_edge_total']))
    emit('- S5 再観測（`observe_edge_reobserve.json`）: 升 %d・REOBSERVED %d・MISMATCH %d' % (ro['elements'], ro['reobserved'], ro['mismatch']))
    emit('- S5 観測のテスト（配置つき。`pytest_observe_with_placement.txt`・`_dev.txt`）: 今 %s、基点 %s' % (read(A / 'pytest_observe_with_placement.txt').strip().splitlines()[-1], read(A / 'pytest_observe_with_placement_dev.txt').strip().splitlines()[-1]))
    # S6
    full = read(A / 'pytest_full.txt').strip().splitlines()[-1]
    emit('- S6 全体テスト（`pytest_full.txt`）: %s。基線 `dev_c875ed3_failures.txt`（%d 行）に無い失敗 %d 件（`pytest_new_failures.txt`）、基線にあって今は通る %d 件（`pytest_fixed_vs_baseline.txt`）' % (
        full, len([l for l in read(C.TREE.parent.parent / 'baselines' / 'dev_c875ed3_failures.txt').splitlines() if l.strip()]), len([l for l in read(A / 'pytest_new_failures.txt').splitlines() if l.strip()]),
        len([l for l in read(A / 'pytest_fixed_vs_baseline.txt').splitlines() if l.strip()])))
    emit('- S6 新しいテスト（`pytest_w3b3.txt`）: %s' % read(A / 'pytest_w3b3.txt').strip().splitlines()[-1])
    # round 2 (review r1, M1)
    r2 = A / 'r2'
    t = [read(r2 / n).strip() for n in ('docs_change_time.txt', 'test_r2_freeze_time.txt', 'fix_time.txt')]
    emit('- 第 2 ラウンド M1 の時刻の順（`r2/docs_change_time.txt`・`r2/test_r2_freeze_time.txt`・`r2/fix_time.txt`）: 変更記録 %s < 新しいテストの凍結 %s < 直した時刻 %s' % tuple(t))
    emit('- 第 2 ラウンド M1 の新しいテスト `tests/test_semantic_read_w3b3_r2.py` を直す前の木で流した結果（`r2/test_r2_on_unfixed_tree.txt`）: %s' % read(r2 / 'test_r2_on_unfixed_tree.txt').strip().splitlines()[-1])
    emit('- 第 2 ラウンド M1 の新しいテストを直した後の木で流した結果（`r2/pytest_r2_only_after_fix.txt`）: %s' % read(r2 / 'pytest_r2_only_after_fix.txt').strip().splitlines()[-1])
    p2 = [l for l in read(r2 / 'self_probe_r2.txt').splitlines() if l.startswith(('READ', 'ABST'))]
    emit('- 第 2 ラウンドの自作の確認（`r2/self_probe_r2.txt`。配置 r6、に の句が時・場所・受け手の関係節。同じ書き手なので証拠にならない）: %d 文、読んだ %d 文、棄権 %d 文' % (len(p2), sum(1 for l in p2 if l.startswith('READ')), sum(1 for l in p2 if l.startswith('ABST'))))
    # round 4 (review r3, M1-r3)
    r4 = A / 'r4'
    t = [read(r4 / n).strip() for n in ('docs_change_time.txt', 'test_r4_freeze_time.txt', 'fix_time.txt')]
    emit('- 第 4 ラウンド M1-r3 の時刻の順（`r4/docs_change_time.txt`・`r4/test_r4_freeze_time.txt`・`r4/fix_time.txt`）: 変更記録 %s < 新しいテストの凍結 %s < 直した時刻 %s' % tuple(t))
    emit('- 第 4 ラウンド M1-r3 の新しいテスト `tests/test_semantic_read_w3b3_m1r3.py` を直す前の木で流した結果（`r4/test_r4_on_unfixed_tree.txt`）: %s' % read(r4 / 'test_r4_on_unfixed_tree.txt').strip().splitlines()[-1])
    emit('- 第 4 ラウンド M1-r3 の新しいテストを直した後の木で流した結果（`r4/pytest_r4_only_after_fix.txt`）: %s' % read(r4 / 'pytest_r4_only_after_fix.txt').strip().splitlines()[-1])
    emit('- 第 4 ラウンド M1-r3 の入口での比較（配置 r6。`r4/m1r3_compare.txt`）: %s' % read(r4 / 'm1r3_compare.txt').strip().splitlines()[-1])
    cmp4 = [l.split()[0] for l in read(r4 / 'rerun_cmp.txt').splitlines() if l.strip()]
    emit('- 第 4 ラウンドの流し直しの照合（`r4/rerun_cmp.txt`）: SAME %d・SAME_COUNT %d・DIFF %d' % (cmp4.count('SAME'), cmp4.count('SAME_COUNT'), cmp4.count('DIFF')))
    emit('- 第 4 ラウンドの `test_s6_…`（コミットした写し。`r4/s6_in_committed_copy.txt`）: %s' % [l for l in read(r4 / 's6_in_committed_copy.txt').splitlines() if l.strip()][-1])
    emit('- 第 4 ラウンドの docstring の直し（H176。`r4/fix_docstring_time.txt`・`r4/pytest_r4_after_docstring_fix.txt`）: 直した時刻 %s、直した後の新しいテスト: %s' % (read(r4 / 'fix_docstring_time.txt').strip(), read(r4 / 'pytest_r4_after_docstring_fix.txt').strip().splitlines()[-1]))
    hc = read(A / 'check_hardcode.txt').splitlines()
    emit('- S6 決め打ち検査（`check_hardcode.txt`）: %s、%s。配置の答えの欄の直接の読み（`placement_field_uses.txt`）: %d 行' % (hc[1], hc[2], len([l for l in read(A / 'placement_field_uses.txt').splitlines() if l.strip()])))
    probes = [l for n in ('self_probe_1.txt', 'self_probe_2.txt') for l in read(A / n).splitlines() if l.startswith(('READ', 'no '))]
    rel = sum(1 for l in probes if l.startswith('READ') and "'type': 'relative'" in l)
    emit('- 実装の後に自分で書いた別の未公開の文（`self_probe_1.txt`・`self_probe_2.txt`。同じ書き手なので証拠にならない）: %d 文、読んだ %d 文（関係節 %d 文・接続 %d 文）、棄権 %d 文' % (
        len(probes), sum(1 for l in probes if l.startswith('READ')), rel, sum(1 for l in probes if l.startswith('READ')) - rel, sum(1 for l in probes if l.startswith('no '))))
    # events
    sys.path.insert(0, str(C.TREE))
    from verantyx import event_cross as EC
    outs = [json.loads(l)['out'] for l in read(A / 'entry_r6.jsonl').splitlines() if l.strip()]
    readable = [o for o in outs if o.get('readable') and any('head' in r for r in o['relations'])]
    n_emb = n_bad = n_all = 0
    for out in [o for o in outs if o.get('readable')]:
        cr = EC.build_crosses(out, EC.StubLookup())
        n_all += 1
        if cr.status != 'CROSSED': n_bad += 1
        for c in cr.crosses:
            for arm in c.arms.values():
                n_emb += sum(1 for f in arm.fillers if f.embedded is not None)
    emit('- 十字（`entry_r6.jsonl` の読めた %d 文を `StubLookup` で十字にした）: `head` を持つ関係の文 %d・埋め込みの十字 %d・十字にできなかった文（INPUT_REJECTED を含む）%d' % (n_all, len(readable), n_emb, n_bad))
    emit('- 十字の E1（`e1.txt`）: %s' % ', '.join(l.strip() for l in read(A / 'e1.txt').splitlines() if l.strip()))
    print('\n'.join(L))


if __name__ == '__main__':
    main()
