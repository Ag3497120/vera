#!/usr/bin/env python3
"""A7: docs/READING_SOUNDNESS.md の数値表を artifacts/w1-a/ の出力から再計算して Markdown で出す。

使い方: python tests/reading_soundness/recompute.py [--dir artifacts/w1-a]
入力: soundness_{dev,start,after}.json (harness.py の出力)、coverage_before.json / coverage_after.json、
      dropped.tsv / gained.tsv / changed.tsv と *_classified.tsv、before_pytest.txt / after_pytest.txt、w1a2_{start,after}_pytest.txt、
      w1a2r2_new_failures.txt、w1a2r2_after_pytest.txt、r2_review_check_{after,dev}.txt、x3_table.tsv、bank_score_b1_selfmade{,_r2}/summary.json、bank_*.sha256、b1v2_fixture_freeze.sha256。
      W1-a2: 開始時点から修正後への変化、X3 の表の要約、読解の入口の見本の結果(入口を同じ木で呼ぶ)、入口が出さない型の表(semantic_read.NOT_PRODUCED)を足した。
文書の結果表はこの出力をそのまま貼る。
"""
import argparse, csv, json, re
from pathlib import Path


def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))


def tsv(p): return list(csv.DictReader(open(p, encoding='utf-8'), delimiter='\t'))


def last_summary(p):
    for line in reversed(Path(p).read_text(encoding='utf-8').splitlines()):
        if re.search(r'\d+ passed', line) or re.search(r'\d+ failed', line): return line.strip()
    return ''


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='artifacts/w1-a'); a = ap.parse_args(); d = Path(a.dir)
    dev, aft = load(d / 'soundness_dev.json'), load(d / 'soundness_after.json')
    print('## 型ごとの結果(出典: soundness_dev.json / soundness_after.json)\n')
    print('| 型 | 文数 | dev 正読 | dev 誤読 | dev 未対応 | dev 検査誤通過 | 修正後 正読 | 修正後 誤読 | うち上申済み | 修正後 未対応 | 修正後 棄権が正解 | 修正後 正読かつ全節検査PASS | 修正後 検査誤通過 | 正読が半数以上 |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    tot = {k: [0, 0, 0, 0, 0, 0, 0] for k in ('dev', 'aft')}; esc = 0
    for t in sorted(aft['summary']):
        s, v = aft['summary'][t], dev['summary'].get(t, {})
        print(f"| {t} | {s['n']} | {v.get('correct','-')} | {v.get('misread','-')} | {v.get('unsupported','-')} | {v.get('false_pass','-')} | "
              f"{s['correct']} | {s['misread']} | {s.get('misread_escalated', 0)} | {s['unsupported']} | {s['abstain_is_correct']} | {s['correct_and_all_pass']} | {s['false_pass']} | {s['half_or_more_correct']} |")
        esc += s.get('misread_escalated', 0)
        for name, x in (('dev', v), ('aft', s)):
            if x: tot[name] = [a0 + b for a0, b in zip(tot[name], (x['n'], x['correct'], x['misread'], x['unsupported'], x['abstain_is_correct'], x['correct_and_all_pass'], x['false_pass']))]
    print(f"| 合計 | {tot['aft'][0]} | {tot['dev'][1]} | {tot['dev'][2]} | {tot['dev'][3]} | {tot['dev'][6]} | {tot['aft'][1]} | {tot['aft'][2]} | {esc} | {tot['aft'][3]} | {tot['aft'][4]} | {tot['aft'][5]} | {tot['aft'][6]} | - |")
    print(f"\nharness 実行の木: dev = `{dev['header']['tree']}` ({dev['header']['revision']}), 修正後 = `{aft['header']['tree']}` ({aft['header']['revision']})")
    print(f"評価文の件数(ファイル別): {aft['header']['bank_files']}")
    cb, ca = load(d / 'coverage_before.json'), load(d / 'coverage_after.json')
    dr, ga, ch = tsv(d / 'dropped.tsv'), tsv(d / 'gained.tsv'), tsv(d / 'changed.tsv')
    drc, gac = tsv(d / 'coverage_dropped_classified.tsv'), tsv(d / 'coverage_gained_classified.tsv')
    from collections import Counter
    print('\n## カバレッジ(出典: coverage_before.json / coverage_after.json / dropped.tsv / gained.tsv / changed.tsv)\n')
    print('| 指標 | 修正前(dev) | 修正後 |\n|---|---|---|')
    for k in ('documents', 'sentences_approx', 'supported_sentences', 'supported_pct', 'only_unsupported_sentences', 'unread_spans'):
        print(f'| {k} | {cb[k]} | {ca[k]} |')
    print(f"\n- supported から外れた文(dropped.tsv): {len(dr)} 件。分類(coverage_dropped_classified.tsv): {dict(Counter(r['class'] for r in drc))}")
    import re as _re
    def _kind(t):
        if _re.search(r'空の節|役割 0|役割が空|空節', t): return '役割 0 の空の節'
        if _re.search(r'agent=|recipient=|受け手|動作主', t) and _re.search(r'時間|場所|方角|時代|結果|起点|時期|断片|対象|主題', t): return '時間・場所・方角・結果・対象を参与者にした'
        if _re.search(r'括弧|助詞|切|語の途中|読み', t): return '語の途中・括弧・助詞をまたぐ役割句'
        if _re.search(r'落と|先行|黙って', t): return '先行する語を黙って落とした'
        return 'そのほか'
    print(f"- dropped の分類理由欄の語から機械的に分けた内訳(recompute.py の `_kind`。目安であり、分類の正本は各行の理由): {dict(Counter(_kind(r['reason']) for r in drc))}")
    print(f"- 新たに supported になった文(gained.tsv): {len(ga)} 件。分類(coverage_gained_classified.tsv): {dict(Counter(r['class'] for r in gac))}")
    print(f"- どちらも supported だが supported 節の構造が変わった文(changed.tsv): {len(ch)} 件")
    print(f"- 検算: 修正前 {cb['supported_sentences']} - {len(dr)} + {len(ga)} = {cb['supported_sentences'] - len(dr) + len(ga)} (修正後 {ca['supported_sentences']})")
    print('\n## 全テスト(出典: before_pytest.txt / after_pytest.txt)\n')
    print(f"- 作業前: `{last_summary(d / 'before_pytest.txt')}`\n- 作業後: `{last_summary(d / 'after_pytest.txt')}`")
    print('\n## 凍結ハッシュ(出典: bank_freeze.sha256 = 第 1 ラウンドの 4 ファイル、bank_freeze_r2.sha256 = 第 2 ラウンドの 3 ファイル、bank_freeze_r3.sha256 = 第 3 ラウンドの 2 ファイル、bank_freeze_r4.sha256 = W1-a2 第 1 ラウンドの 2 ファイル、bank_freeze_r5.sha256 = W1-a2 第 2 ラウンドの 2 ファイル、bank_freeze_r6.sha256 = W1-a2 第 3 ラウンドの 1 ファイル ja_r6.jsonl)と、いまの評価ファイルの sha256\n')
    import hashlib
    here = Path(__file__).resolve().parent
    frozen = {}
    for name in ('bank_freeze.sha256', 'bank_freeze_r2.sha256', 'bank_freeze_r3.sha256', 'bank_freeze_r4.sha256', 'bank_freeze_r5.sha256', 'bank_freeze_r6.sha256'):
        for line in (d / name).read_text(encoding='utf-8').splitlines():
            if line.strip():
                digest, path = line.split(); frozen[Path(path).name] = digest
    print('| ファイル | 凍結時の sha256 | いまの sha256 | 一致 |\n|---|---|---|---|')
    for fname, digest in sorted(frozen.items()):
        now = hashlib.sha256((here / fname).read_bytes()).hexdigest()
        print(f'| {fname} | `{digest}` | `{now}` | {"一致" if now == digest else "不一致"} |')
    print('\n上申済みの既知の例外(harness.py の ESCALATED、id で列挙): ' + (', '.join(f'{k} ({v})' for k, v in aft['header'].get('escalated', {}).items()) or 'なし(W1-a2 で空にした)'))
    root = d.resolve().parent.parent
    fx = root / 'tests' / 'bank_score' / 'fixtures' / 'B1_v2' / 'items.jsonl'
    digest = hashlib.sha256(fx.read_bytes()).hexdigest()
    want = (d / 'b1v2_fixture_freeze.sha256').read_text(encoding='utf-8').split()[0]
    print(f'\nB1 v2 の自作の見本(`tests/bank_score/fixtures/B1_v2/items.jsonl`、`b1v2_fixture_freeze.sha256`): 凍結 `{want}` / いま `{digest}` / {"一致" if want == digest else "不一致"}')
    fx2 = root / 'tests' / 'bank_score' / 'fixtures' / 'B1_v2_r2' / 'items.jsonl'
    digest2 = hashlib.sha256(fx2.read_bytes()).hexdigest()
    want2 = (d / 'b1v2_r2_fixture_freeze.sha256').read_text(encoding='utf-8').split()[0]
    print(f'\nB1 v2 の第 2 ラウンドの自作の見本(`tests/bank_score/fixtures/B1_v2_r2/items.jsonl`、`b1v2_r2_fixture_freeze.sha256`): 凍結 `{want2}` / いま `{digest2}` / {"一致" if want2 == digest2 else "不一致"}')
    fx3 = root / 'tests' / 'bank_score' / 'fixtures' / 'B1_v2_r3' / 'items.jsonl'
    digest3 = hashlib.sha256(fx3.read_bytes()).hexdigest()
    want3 = (d / 'b1v2_r3_fixture_freeze.sha256').read_text(encoding='utf-8').split()[0]
    print(f'\nB1 v2 の第 3 ラウンドの自作の見本(`tests/bank_score/fixtures/B1_v2_r3/items.jsonl`、`b1v2_r3_fixture_freeze.sha256`): 凍結 `{want3}` / いま `{digest3}` / {"一致" if want3 == digest3 else "不一致"}')
    w1a2(d, dev, aft, root)
    w1a3(d)


def w1a2(d, dev, aft, root):
    from collections import Counter
    start = load(d / 'soundness_start.json')
    print('\n## W1-a2: 開始時点(HEAD 8d69747、製品コードの変更前)から修正後への変化(出典: soundness_start.json / soundness_after.json)\n')
    print('| 型 | 文数 | 開始 正読 | 開始 誤読 | 開始 未対応 | 修正後 正読 | 修正後 誤読 | 修正後 未対応 |\n|---|---|---|---|---|---|---|---|')
    for t in sorted(aft['summary']):
        a0, b0 = start['summary'].get(t), aft['summary'][t]
        if a0 and (a0['correct'], a0['misread'], a0['unsupported']) != (b0['correct'], b0['misread'], b0['unsupported']):
            print(f"| {t} | {b0['n']} | {a0['correct']} | {a0['misread']} | {a0['unsupported']} | {b0['correct']} | {b0['misread']} | {b0['unsupported']} |")
    s_by = {r['id']: r['result'] for r in start['sentences']}; a_by = {r['id']: r['result'] for r in aft['sentences']}
    moves = Counter((s_by[i], a_by[i]) for i in a_by if i in s_by and s_by[i] != a_by[i])
    print('\n開始時点から修正後で結果が変わった文(出典: 同上): ' + ', '.join(f'{k[0]}→{k[1]} {v}' for k, v in sorted(moves.items())))
    lost = sorted(i for i in a_by if i in s_by and s_by[i] == 'correct' and a_by[i] != 'correct')
    print(f"- 開始時点で正読だったが修正後は正読でなくなった文: {len(lost)} 件(id: {', '.join(lost) if lost else 'なし'})")
    print(f"- 修正後の誤読: {sum(1 for v in a_by.values() if v == 'misread')} 件、新しい自作文 N1〜N4 系(N1・N1c・N2・N2c・N3・N3c・N4)の文数: {sum(aft['summary'][t]['n'] for t in aft['summary'] if t.startswith('N'))}")
    x3 = [l.split('\t') for l in (d / 'x3_table.tsv').read_text(encoding='utf-8').splitlines()[1:] if l]
    labels = Counter(r[5] for r in x3); kinds = Counter(r[3] for r in x3); hows = Counter(r[6] for r in x3)
    print('\n## W1-a2 X3: 基点 dev との比較(出典: x3_table.tsv。x3_dev.jsonl と x3_after.jsonl から x3_compare.py が作る)\n')
    print(f"- 修正後に新しく対応済みになった (役割, 値): {len(x3)} 行(種類 {dict(kinds)}、判定の付け方 {dict(hows)})")
    print(f"- 判定の内訳: {dict(labels)}。未分類 {labels['UNCLASSIFIED']}、REGRESSED {labels['REGRESSED']}、WRONG {labels['WRONG']}、MISREAD {labels['MISREAD']}")
    ss = {r[0] for r in x3}
    print(f"- 対象の文: 評価バンク(table7・ja・ja_r2・ja_r3・ja_r4・ja_r5・ja_r6)・review_r3_examples_ja.txt・b1v2_r3_inputs_ja.txt・w1a2r3_probe_ja.txt・r3_probe_ja.txt・review_r1_examples_ja.txt・r4_review_examples_ja.txt・b1v2_inputs_ja.txt・review_r2_examples_ja.txt・b1v2_r2_inputs_ja.txt・w1a2r2_probe_ja.txt・w1a2r3_probe_ja.txt・w1a3_review_r3_examples_ja.txt・w1a3_r4_inputs_ja.txt・coverage_texts_ja.txt(カバレッジの標本の文)の重複を除いた {sum(1 for _ in open(d / 'x3_after.jsonl', encoding='utf-8'))} 文(x3_after.jsonl)、うち表に出た文 {len(ss)}")
    for tag, sub_dir, label in (('', 'bank_score_b1_selfmade', 'B1_v2'), ('(第 2 ラウンドの見本)', 'bank_score_b1_selfmade_r2', 'B1_v2_r2'),
                                   ('(第 3 ラウンドの見本)', 'bank_score_b1_selfmade_r3', 'B1_v2_r3')):
        b = d / sub_dir
        if (b / 'summary.json').exists():
            sm = load(b / 'summary.json'); mt = load(b / 'run_meta.json')
            cls = {k: v['count'] for k, v in sm['classes'].items()}
            print(f'\n## W1-a2 X5{tag}: 採点器 `--entry mod-semantic-read` で {label} を流した結果(出典: {sub_dir}/summary.json, run_meta.json)\n')
            print(f"- 問題数 {sm['total']}、入口の呼び出し {mt['vera_calls']}、出自の外 {mt['provenance_total']['outside_count']}、出自を確かめられなかった子プロセス {mt['provenance_total']['processes_unverified']}、未到達 {cls['unreachable']}、実行時エラー {cls['runtime_error']}、採点不能 {cls['unscorable']}")
            print('- 9 分類: ' + ', '.join(f'{k} {v}' for k, v in sorted(cls.items())))
            hl = sm['headline']
            print(f"- correct_rate {hl['correct_rate']['all']}、wrong_rate {hl['wrong_rate']['all']}、false_compliance_rate {hl['false_compliance_rate']['all']}(誤読 {cls['misread']} 件)")
    import sys
    sys.path.insert(0, str(root))
    try:
        from verantyx import semantic_read as SR
        from tools.bank_score.v2 import b1
    except Exception as e:                                  # pragma: no cover
        print(f'\n(入口を読み込めない: {e})'); return
    allrows = {}
    for fname in ('B1_v2', 'B1_v2_r2', 'B1_v2_r3'):
        items = [json.loads(l) for l in (root / 'tests' / 'bank_score' / 'fixtures' / fname / 'items.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
        rows = []
        for it in items:
            out = SR.read(it['input'])
            v = b1.judge(it['expect'], it['lang'], {k: out[k] for k in ('readable', 'clauses', 'relations')})['verdict']
            rows.append((it['lang'], it['expect']['readable'], out['readable'], v, (out['abstain'] or {}).get('kind'), tuple((out['abstain'] or {}).get('reasons', ()))))
        allrows[fname] = rows
        print(f'\n## W1-a2 X4: 読解の入口の見本(自作 {fname} の {len(rows)} 問を `semantic_read.read` に通した結果。出典: tests/bank_score/fixtures/{fname}/items.jsonl、artifacts/w1-a/semantic_read_examples.txt)\n')
        print('| 入力の種類 | 問題数 | 入口が readable=true | 入口が readable=false | 正答 | 棄権(正解は読める) | 不完全 | 誤読 |\n|---|---|---|---|---|---|---|---|')
        for name, f in (('日本語・読める', lambda r: r[0] == 'ja' and r[1]), ('英語・読める', lambda r: r[0] == 'en' and r[1]), ('読めない入力(日英)', lambda r: not r[1])):
            sel = [r for r in rows if f(r)]
            c = Counter(r[3] for r in sel)
            print(f"| {name} | {len(sel)} | {sum(r[2] for r in sel)} | {sum(not r[2] for r in sel)} | {c['correct']} | {c['abstain']} | {c['incomplete']} | {c['misread']} |")
    rows = allrows['B1_v2'] + allrows['B1_v2_r2'] + allrows['B1_v2_r3']
    kinds2 = Counter(r[4] for r in rows if not r[2])
    reasons = Counter(x.split(':')[0] for r in rows if not r[2] for x in r[5])
    print(f"\n- 入口が `readable: false` にした {sum(1 for r in rows if not r[2])} 問の kind: {dict(kinds2)}。理由の型の内訳: {dict(sorted(reasons.items()))}")
    print('\n### 入口が出さない型(`verantyx/semantic_read.py` の `NOT_PRODUCED`。出さないものは棄権し、近い型に押し込まない)\n')
    for k, v in SR.NOT_PRODUCED.items():
        print(f'- `{k}`: {v}')
    print(f"\n入口が棄権の理由として返す型(`semantic_read.py` が使う閉じた一覧): 見本での理由の型 {sorted(reasons)}")
    n_start = last_summary(d / 'w1a2_start_pytest.txt'); n_after = last_summary(d / 'w1a2r3_after_pytest.txt')
    newf = [l for l in (d / 'w1a2r3_new_failures.txt').read_text(encoding='utf-8').splitlines() if l.strip()] if (d / 'w1a2r3_new_failures.txt').exists() else []
    print('\n## W1-a2 X6: 全テスト(出典: w1a2_start_pytest.txt / w1a2r3_after_pytest.txt / w1a2r3_new_failures.txt)\n')
    print(f"- 開始時点(第 1 ラウンドの前): `{n_start}`\n- 修正後(第 3 ラウンド): `{n_after}`\n- 基線(dev_191db17_failures.txt)に無い失敗: {len(newf)} 件" + (' (' + '; '.join(newf) + ')' if newf else ''))
    # ---- round 2 ----
    print('\n## W1-a2 第 2 ラウンド: レビューの型 R1〜R4c の自作文(ja_r5.jsonl、凍結 bank_freeze_r5.sha256。出典: soundness_dev.json / soundness_after.json)\n')
    print('| 型 | 文数 | dev 正読 | dev 誤読 | dev 未対応 | 修正後 正読 | 修正後 誤読 | 修正後 未対応 |\n|---|---|---|---|---|---|---|---|')
    rt = [0] * 7
    for t in sorted(aft['summary']):
        if not t.startswith('R'): continue
        b0, a1 = dev['summary'].get(t, {}), aft['summary'][t]
        print(f"| {t} | {a1['n']} | {b0.get('correct', '-')} | {b0.get('misread', '-')} | {b0.get('unsupported', '-')} | {a1['correct']} | {a1['misread']} | {a1['unsupported']} |")
        for k, x in enumerate((a1['n'], b0.get('correct', 0), b0.get('misread', 0), b0.get('unsupported', 0), a1['correct'], a1['misread'], a1['unsupported'])): rt[k] += x
    print(f"| 合計 | {rt[0]} | {rt[1]} | {rt[2]} | {rt[3]} | {rt[4]} | {rt[5]} | {rt[6]} |")
    for tag, fn in (('修正後', 'r2_review_check_after.txt'), ('dev', 'r2_review_check_dev.txt')):
        f = d / fn
        if f.exists():
            last = [l for l in f.read_text(encoding='utf-8').splitlines() if l.startswith('checks=')]
            print(f"- review.r1.md の反例の回帰確認(w1a2_review_r1_check.py、{tag}、出典: {fn}): {last[-1] if last else '-'}")

    # ---- round 3 ----
    print('\n## W1-a2 第 3 ラウンド: レビュー(review.r2.md)の型 S1〜S4c の自作文(ja_r6.jsonl、凍結 bank_freeze_r6.sha256。出典: soundness_dev.json / soundness_after.json)\n')
    print('| 型 | 文数 | dev 正読 | dev 誤読 | dev 未対応 | 修正後 正読 | 修正後 誤読 | 修正後 未対応 |\n|---|---|---|---|---|---|---|---|')
    st = [0] * 7
    for t in sorted(aft['summary']):
        if not t.startswith('S'): continue
        b0, a1 = dev['summary'].get(t, {}), aft['summary'][t]
        print(f"| {t} | {a1['n']} | {b0.get('correct', '-')} | {b0.get('misread', '-')} | {b0.get('unsupported', '-')} | {a1['correct']} | {a1['misread']} | {a1['unsupported']} |")
        for k, x in enumerate((a1['n'], b0.get('correct', 0), b0.get('misread', 0), b0.get('unsupported', 0), a1['correct'], a1['misread'], a1['unsupported'])): st[k] += x
    print(f"| 合計 | {st[0]} | {st[1]} | {st[2]} | {st[3]} | {st[4]} | {st[5]} | {st[6]} |")
    for tag, fn in (('修正後', 'r3_review_check_after.txt'), ('dev', 'r3_review_check_dev.txt')):
        f = d / fn
        if f.exists():
            last = [l for l in f.read_text(encoding='utf-8').splitlines() if l.startswith('checks=')]
            print(f"- review.r2.md の反例の回帰確認(w1a2_review_r2_check.py、{tag}、出典: {fn}): {last[-1] if last else '-'}")
    r2c = d / 'soundness_round2code.json'
    if r2c.exists():
        r2 = load(r2c); r2_by = {r['id']: r['result'] for r in r2['sentences']}; now_by = {r['id']: r['result'] for r in aft['sentences']}
        moves = Counter((r2_by[i], now_by[i]) for i in now_by if i in r2_by and r2_by[i] != now_by[i])
        tot = {k: sum(1 for v in r2_by.values() if v == k) for k in ('correct', 'misread', 'unsupported')}
        print(f"- 第 2 ラウンドの終わりと同じ挙動の複製(`make_round2_copy.py`。出典: soundness_round2code.json)で同じ評価バンク({len(r2_by)} 文)を流した結果: 正読 {tot['correct']}、誤読 {tot['misread']}、未対応 {tot['unsupported']}。第 3 ラウンドの規則で結果が変わった文: {sum(moves.values())} 文({', '.join(f'{k[0]}→{k[1]} {v}' for k, v in sorted(moves.items()))})。変わった文はすべて ja_r6 の S1・S4 の文(`{', '.join(sorted({i for i in now_by if i in r2_by and r2_by[i] != now_by[i]})[:3])} …`)。ja_r6 以外の評価バンクの文の結果は 1 文も変わっていない: {sum(1 for i in now_by if i in r2_by and r2_by[i] != now_by[i] and not i.startswith('S'))} 文")
    lost = d / 'r3_lost_vs_round2.tsv'; ech = d / 'r3_entry_changes_vs_round2.tsv'
    if lost.exists():
        lr = [l.split('\t') for l in lost.read_text(encoding='utf-8').splitlines()[1:] if l.strip()]
        print(f"- 第 3 ラウンドの規則で、第 2 ラウンドの規則では supported だった (役割, 値) が supported でなくなったもの(出典: {lost.name}。第 2 ラウンドの規則は、第 3 ラウンドの変更だけを戻した複製で測った。対象は x3 と同じ 2144 文): {len(lr)} 組、{len({r[0] for r in lr})} 文。役割別: {dict(Counter(r[1] for r in lr))}")
    if ech.exists():
        er = [l.split('\t') for l in ech.read_text(encoding='utf-8').splitlines()[1:] if l.strip()]
        why = Counter((r[3].split(':')[0] if r[3] else '-') for r in er)
        print(f"- 入口が第 2 ラウンドでは `readable: true` で、第 3 ラウンドでは `readable: false` になった入力(出典: {ech.name}。対象は x3 の 2144 文と 3 つの B1 v2 の見本・英語の自作バンクの 2271 文): {len(er)} 件。棄権の理由の型: {dict(why)}。第 2 ラウンドで `false` で第 3 ラウンドで `true` になった入力: {sum(1 for r in er if r[1] != 'readable→false')} 件")
    cs = d / 'w1a2r3_s6_in_committed_copy.txt'
    if cs.exists():
        print(f"- 基線に無い失敗の s6(`test_s6_…`)を、W をコミットした複製(scratchpad)で `tests/bank_score`・`tests/test_semantic_read*.py` を流した結果(出典: w1a2r3_s6_in_committed_copy.txt): `{last_summary(cs)}`")


def w1a3(d):
    """W1-a3(review.r3.md の必須 1・2): 入口の態を正の証拠の向きに反転した。第 3 ラウンドの終わりの木との比較と、新しいテスト・検査の結果。"""
    from collections import Counter
    print('\n## W1-a3: 入口の態(`_voice_ja`)を正の証拠の向きにした変更の測定(出典: w1a3_*.txt / w1a3_*.tsv)\n')
    ech = d / 'w1a3_entry_changes_vs_r3end.tsv'
    if ech.exists():
        er = [l.split('\t') for l in ech.read_text(encoding='utf-8').splitlines()[1:] if l.strip()]
        kinds = Counter(r[1] for r in er)
        why = Counter(r[3] for r in er if r[1] == 'readable→false')
        summ = (d / 'w1a3_entry_changes_summary.txt').read_text(encoding='utf-8').splitlines()[0]
        print(f"- 入口の出力の比較(第 3 ラウンドの終わりの木と今の木。出典: {ech.name}、{summ}): 種類 {dict(kinds)}。`readable→false` の理由の内訳: {dict(why)}。`false→readable`・`changed`: {kinds.get('false→readable', 0)} 件・{kinds.get('changed', 0)} 件")
    cc = d / 'w1a3_bank_class_changes.tsv'
    if cc.exists():
        rows = [l.split('\t') for l in cc.read_text(encoding='utf-8').splitlines()[1:] if l.strip()]
        print(f"- 自作の 3 つの見本で分類が変わった問題(出典: {cc.name}。第 3 ラウンドの終わりの結果との比較): {len(rows)} 問、{dict(Counter((r[3], r[4]) for r in rows))}。id: {', '.join(r[1] for r in rows)}")
    for tag, fn in (('今の木', 'w1a3_review_r3_check_after.txt'), ('第 3 ラウンドの終わりの木', 'w1a3_review_r3_check_r3end.txt')):
        f = d / fn
        if f.exists():
            last = [l for l in f.read_text(encoding='utf-8').splitlines() if l.startswith(('checks=', 'exit='))]
            print(f"- review.r3.md の入口の反例の回帰確認(w1a3_review_r3_check.py、{tag}、出典: {fn}): {' '.join(last)}")
    fz = d / 'w1a3_tests_freeze.sha256'
    if fz.exists():
        import hashlib
        lines = fz.read_text(encoding='utf-8').splitlines()
        now = hashlib.sha256((d.parent.parent / 'tests' / 'test_semantic_read_r4.py').read_bytes()).hexdigest()
        print(f"- `tests/test_semantic_read_r4.py` の凍結(出典: w1a3_tests_freeze.sha256、w1a3_tests_freeze_time.txt): 凍結が {len(lines)} 回(2 回目は T4 の差し替え。H65)。最後の凍結 `{lines[-1].split()[0]}` / いま `{now}` / {'一致' if lines[-1].split()[0] == now else '不一致'}")
    for tag, fn in (('第 3 ラウンドの終わりの写しで流した結果(`r3end`。落ちるべきものが落ちる確認)', 'w1a3_r4_on_r3end.txt'), ('今の木', 'w1a3_pytest_semantic_read.txt')):
        f = d / fn
        if f.exists(): print(f"- テストの結果({tag}。出典: {fn}): `{last_summary(f)}`")
    if (d / 'w1a3_after_pytest.txt').exists():
        nf = [l for l in (d / 'w1a3_new_failures.txt').read_text(encoding='utf-8').splitlines() if l.strip()] if (d / 'w1a3_new_failures.txt').exists() else []
        print(f"- 全テスト(出典: w1a3_after_pytest.txt / w1a3_new_failures.txt): `{last_summary(d / 'w1a3_after_pytest.txt')}`。基線に無い失敗: {len(nf)} 件" + (' (' + '; '.join(nf) + ')' if nf else ''))
    cs = d / 'w1a3_s6_in_committed_copy.txt'
    if cs.exists():
        print(f"- 基線に無い失敗の s6 を、W をコミットした複製(scratchpad)で `tests/bank_score`・`tests/test_semantic_read*.py` を流した結果(出典: w1a3_s6_in_committed_copy.txt): `{last_summary(cs)}`")
    cv = d / 'w1a3_coverage_cmp.txt'
    if cv.exists(): print(f"- カバレッジの再測定(出典: {cv.name}): {cv.read_text(encoding='utf-8').strip()}")


if __name__ == '__main__':
    main()
