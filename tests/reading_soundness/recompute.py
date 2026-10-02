#!/usr/bin/env python3
"""A7: docs/READING_SOUNDNESS.md の数値表を artifacts/w1-a/ の出力から再計算して Markdown で出す。

使い方: python tests/reading_soundness/recompute.py [--dir artifacts/w1-a]
入力: soundness_dev.json / soundness_after.json (harness.py の出力)、coverage_before.json / coverage_after.json、
      dropped.tsv / gained.tsv / changed.tsv と *_classified.tsv、before_pytest.txt / after_pytest.txt、bank_*.sha256。
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
    print('\n## 凍結ハッシュ(出典: bank_freeze.sha256 = 第 1 ラウンドの 4 ファイル、bank_freeze_r2.sha256 = 第 2 ラウンドの 3 ファイル、bank_freeze_r3.sha256 = 第 3 ラウンドの 2 ファイル)と、いまの評価ファイルの sha256\n')
    import hashlib
    here = Path(__file__).resolve().parent
    frozen = {}
    for name in ('bank_freeze.sha256', 'bank_freeze_r2.sha256', 'bank_freeze_r3.sha256'):
        for line in (d / name).read_text(encoding='utf-8').splitlines():
            if line.strip():
                digest, path = line.split(); frozen[Path(path).name] = digest
    print('| ファイル | 凍結時の sha256 | いまの sha256 | 一致 |\n|---|---|---|---|')
    for fname, digest in sorted(frozen.items()):
        now = hashlib.sha256((here / fname).read_bytes()).hexdigest()
        print(f'| {fname} | `{digest}` | `{now}` | {"一致" if now == digest else "不一致"} |')
    print('\n上申済みの既知の例外(harness.py の ESCALATED、id で列挙): ' + ', '.join(f'{k} ({v})' for k, v in aft['header'].get('escalated', {}).items()))


if __name__ == '__main__':
    main()
