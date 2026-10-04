"""E7: the numbers of docs/EVENT_CROSS.md are the text between `<!-- recompute:begin -->` and `<!-- recompute:end -->`; this script builds that text
from the files of artifacts/w3-b/ alone.

  recompute.py --check   exit 0 when the text in the document equals the rebuilt text (prints a diff otherwise)
  recompute.py --write   put the rebuilt text into the document
  recompute.py --print   print the rebuilt text
  recompute.py --audit   list the lines of the document that hold a digit outside the block and name no source file (information only)
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parent.parent.parent
ART = TREE / 'artifacts' / 'w3-b'
DOC = TREE / 'docs' / 'EVENT_CROSS.md'
BEGIN, END = '<!-- recompute:begin -->', '<!-- recompute:end -->'
MISSING = '(未測定: %s が無い)'


def read(name):
    p = ART / name
    return p.read_text(encoding='utf-8') if p.exists() else None


def jread(name):
    t = read(name)
    return json.loads(t) if t is not None else None


def table(head, rows):
    out = ['| ' + ' | '.join(head) + ' |', '|' + '|'.join('---' for _ in head) + '|']
    out += ['| ' + ' | '.join(str(c) for c in r) + ' |' for r in rows]
    return out


def render():
    L = []
    cls, cls1, summ = jread('e2_classes.json'), jread('e2_classes_set1.json'), jread('e2_summary.json')
    if cls is None or summ is None:
        return MISSING % 'e2_classes.json / e2_summary.json'
    c = cls['counts']
    L += ['### 検査データと読解器の分類（出典: artifacts/w3-b/e2_classes.json, e2_summary.json）', '']
    L += ['検査データは日本語 %d 文・英語 %d 文、計 %d 文。' % (c['ja']['total'], c['en']['total'], c['all']['total']), '']
    L += table(['', '日本語', '英語', '計'], [
        ['(a) 読解器が棄権', c['ja']['a'], c['en']['a'], c['all']['a']],
        ['　うち期待も棄権（読めない文）', c['ja']['a_expected_abstain'], c['en']['a_expected_abstain'], c['all']['a_expected_abstain']],
        ['　うち期待は読める文（読解器の過剰棄権）', c['ja']['a_over_abstain'], c['en']['a_over_abstain'], c['all']['a_over_abstain']],
        ['(b) 読解器が読み、期待と一致', c['ja']['b'], c['en']['b'], c['all']['b']],
        ['(c) 読解器が読み、期待と食い違う', c['ja']['c'], c['en']['c'], c['all']['c']],
        ['読解器が読んだ文（(b)+(c)）', c['ja']['readable_by_reader'], c['en']['readable_by_reader'], c['all']['readable_by_reader']]])
    L.append('')
    if cls1 is not None:
        c1 = cls1['counts']['all']
        L.append('最初の %d 文（追記前。出典: artifacts/w3-b/e2_classes_set1.json）では、読解器が読んだ文は %d 文（(a) %d・(b) %d・(c) %d）。'
                 '読める文が全体の 4 分の 1 未満だったので、読める型の文を新しい id で追記した（変更記録を参照）。' % (
                     c1['total'], c1['readable_by_reader'], c1['a'], c1['b'], c1['c']))
        L.append('')
    L += ['### `--events` の出力の集計（出典: artifacts/w3-b/e2_summary.json）', '']
    st = summ['status']
    L.append('状態: CROSSED %d 文・ABSTAINED %d 文・INPUT_REJECTED %d 文。' % (st.get('CROSSED', 0), st.get('ABSTAINED', 0), st.get('INPUT_REJECTED', 0)))
    L.append('十字 %d 個・腕 %d 本・ARM_TIE %d 本・関係 %d 件。' % (summ['crosses'], summ['arms'], summ['arm_ties'], summ['relations']))
    L.append('関係の種類別: ' + (', '.join('%s %d' % kv for kv in summ['relation_types'].items()) if summ['relation_types'] else '(実際の入口からは 0 件)'))
    ag = summ['agreement']
    L.append('型一致（スタブの配置）: AGREE %d・DISAGREE %d・NOT_CHECKED %d。' % (ag['AGREE'], ag['DISAGREE'], ag['NOT_CHECKED']))
    L.append('NOT_CHECKED の理由別: ' + ', '.join('%s %d' % kv for kv in summ['not_checked_by_reason'].items()))
    L.append('棄権の種類: ' + ', '.join('%s %d' % kv for kv in summ['abstain_kind'].items()) + '。')
    L.append('棄権の最初の理由の上位: ' + ', '.join('%s %d' % kv for kv in sorted(summ['abstain_first_reason'].items(), key=lambda kv: (-kv[1], kv[0]))[:8]) + '。')
    L.append('')
    L += table(['タグ', '文の数', 'CROSSED', 'ABSTAINED'], [
        [t, v.get('CROSSED', 0) + v.get('ABSTAINED', 0), v.get('CROSSED', 0), v.get('ABSTAINED', 0)] for t, v in summ['status_by_tag'].items()])
    L += ['', '話題（topic）は %d 種。話題別の CROSSED / 文の数: ' % len(summ['status_by_topic']) + ', '.join(
        '%s %d/%d' % (t, v.get('CROSSED', 0), v.get('CROSSED', 0) + v.get('ABSTAINED', 0)) for t, v in summ['status_by_topic'].items()) + '。', '']
    L += ['### 「人が作業を説明する文」（タグ explain）で十字ができた数（出典: artifacts/w3-b/e2_summary.json）', '']
    ex = summ['explain']
    L += table(['', '文の数', '十字ができた', '棄権'], [[lang, ex[lang]['sentences'], ex[lang]['crossed'], ex[lang]['abstained']] for lang in ('ja', 'en')])
    L += ['', '十字ができた文の id: ' + ', '.join(ex['ja']['crossed_ids'] + ex['en']['crossed_ids']) + '。']
    first = [i for i in ex['ja']['crossed_ids'] + ex['en']['crossed_ids'] if not (int(i[3:]) <= (82 if i.startswith('ja') else 81))]
    L.append('そのうち最初に書いた文（追記前）の id: %d 件、追記した文の id: %d 件。' % (len(ex['ja']['crossed_ids'] + ex['en']['crossed_ids']) - len(first), len(first)))
    L.append('')
    L += ['### `--events` 無しの出力の一致（E1。出典: artifacts/w3-b/e1_cmp.txt）', '']
    e1 = read('e1_cmp.txt')
    L += ([('- ' + l) for l in e1.splitlines() if l.strip()] if e1 else [MISSING % 'e1_cmp.txt'])
    e5 = read('e5_selfmade_parity.txt')
    L += ['', '自作バンクでの `--events` の有無の一致（出典: artifacts/w3-b/e5_selfmade_parity.txt）: ' + (e5.strip() if e5 else MISSING % 'e5_selfmade_parity.txt'), '']
    L += ['### 所要時間（出典: artifacts/w3-b/timing.json）', '']
    tm = jread('timing.json')
    if tm is None: L.append(MISSING % 'timing.json')
    elif 'skipped' in tm: L.append('負荷が基準以上だったので測っていない（load %s）。' % tm['load'])
    else:
        L += ['1 分平均の負荷: 測定前 %s・測定後 %s。1 文あたり（ms、%d 文を 3 周し 1 周目は捨てた。%d 回の測定）。' % (tm['load_before'][0], tm['load_after'][0], tm['sentences'], tm['read']['n'])]
        L += ['']
        L += table(['関数', '中央値', '最大'], [[k, tm[k]['median'], tm[k]['max']] for k in ('read', 'build_crosses_stub', 'read_events')])
        if 'note' in tm: L.append('注: ' + tm['note'])
    L.append('')
    L += ['### 全体テストと決め打ち検査（E6。出典: artifacts/w3-b/pytest_full.txt, pytest_new_failures.txt, check_hardcode.txt, pytest_new_tests.txt）', '']
    nt = read('pytest_new_tests.txt')
    L.append('新しいテスト（tests/test_event_cross.py, test_event_cross_entry.py, test_event_cross_data.py）: ' + (nt.strip().splitlines()[-1] if nt else MISSING % 'pytest_new_tests.txt'))
    pf = read('pytest_full.txt')
    if pf is None: L.append(MISSING % 'pytest_full.txt')
    else: L.append('全体テストの最終行: `%s`' % pf.strip().splitlines()[-1])
    nf = read('pytest_new_failures.txt')
    L.append('基線にない失敗: %s 件。' % (len([l for l in nf.splitlines() if l.strip()]) if nf is not None else MISSING % 'pytest_new_failures.txt'))
    for l in (nf or '').splitlines():
        if l.strip(): L.append('- `%s`' % l.strip())
    for name, label in (('pytest_two_in_clean_clone_b471f5a.txt', '基線のコミットだけのクリーンなクローンで同じ 2 件を流した結果'),
                        ('pytest_two_in_scratch_clone.txt', '差分をコミットしたクローンで同じ 2 件を流した結果')):
        t = read(name)
        L.append('%s（出典: artifacts/w3-b/%s）: `%s`' % (label, name, t.strip().splitlines()[-1] if t else MISSING % name))
    hc = read('check_hardcode.txt')
    L.append('決め打ち検査の出力: ' + ('`' + ' / '.join(l.strip() for l in hc.strip().splitlines()[:3]) + '`' if hc else MISSING % 'check_hardcode.txt'))
    hn = read('check_hardcode_with_new_file.txt')
    L.append('新規ファイル verantyx/event_cross.py の行も追加行に含めて同じ検査を流した出力（出典: artifacts/w3-b/check_hardcode_with_new_file.txt。git の差分は未追跡のファイルを含まないため）: '
             + ('`' + ' / '.join(l.strip() for l in hn.strip().splitlines()[:3]) + '`' if hn else MISSING % 'check_hardcode_with_new_file.txt'))
    return '\n'.join(L).rstrip() + '\n'


EXAMPLE = re.compile(r'(<!-- example: (\S+) -->\n```text\n)(.*?)(\n```)', re.S)


def example_lines():
    ids, lines = read('events_all_ids.txt'), read('events_all.jsonl')
    if ids is None or lines is None: return {}
    return dict(zip(ids.split(), lines.splitlines()))


def block(doc):
    i, j = doc.index(BEGIN), doc.index(END)
    return i + len(BEGIN), j


def main(argv=None):
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    for f in ('check', 'write', 'print', 'audit'): g.add_argument('--' + f, action='store_true')
    args = ap.parse_args(argv)
    text = render()
    if args.print:
        print(text); return 0
    doc = DOC.read_text(encoding='utf-8')
    i, j = block(doc)
    ex = example_lines()
    if args.write:
        new = doc[:i] + '\n' + text + doc[j:]
        new = EXAMPLE.sub(lambda m: m.group(1) + ex[m.group(2)] + m.group(4), new)
        DOC.write_text(new, encoding='utf-8'); print('written'); return 0
    if args.audit:
        # identifiers that are not measured numbers are removed first: ticket / decision ids, section marks, list ordinals, dates, versions of a name
        ident = [r'W\d+-?[A-Za-z0-9]*', r'\bD\d\b', r'§[\d.]+', r'^\s*\d+\. ', r'\(\d+\)', r'\d{4}-\d\d-\d\d( \d\d:\d\d(:\d\d)?( \+\d{4})?)?',
                 r'/\d\b', r'VERSION = \d', r'\b[A-Z][A-Za-z_]*\d\b', r'\bB1\b', r'\b(ja|en)-\d+\b', r'<!-- example: \S+ -->', r'^[ -]*\{.*\}$']
        outside = doc[:i] + doc[j:]
        # the registered block is frozen text (its sha256 is in artifacts/w3-b/prereg.txt): its digits are dates, ordinals and the version
        k, l = outside.index('<!-- prereg:begin -->'), outside.index('<!-- prereg:end -->')
        for n, line in enumerate(outside.splitlines(), 1):
            if k <= sum(len(x) + 1 for x in outside.splitlines()[:n - 1]) <= l: continue
            rest = line
            for pat in ident: rest = re.sub(pat, '', rest)
            if re.search(r'[0-9]', rest) and not re.search(r'(artifacts/|\.jsonl|\.json|\.md|\.py|\.txt)', line): print('%d: %s' % (n, line))
        return 0
    have = doc[i:j].strip('\n') + '\n'
    bad_examples = [m.group(2) for m in EXAMPLE.finditer(doc) if ex.get(m.group(2)) != m.group(3)]
    found = [m.group(2) for m in EXAMPLE.finditer(doc)]
    if have == text and not bad_examples and found:
        print('recompute: OK (the document block equals the text rebuilt from artifacts/w3-b; %d output examples equal their lines of events_all.jsonl)' % len(found)); return 0
    sys.stdout.writelines(difflib.unified_diff(have.splitlines(True), text.splitlines(True), 'document', 'rebuilt'))
    if bad_examples or not found: print('examples that differ from events_all.jsonl (or none found): %s' % (bad_examples or 'none found'))
    return 1


if __name__ == '__main__':
    sys.exit(main())
