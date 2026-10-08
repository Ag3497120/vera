#!/usr/bin/env python3
"""W3-b5 round 2 (docs 10F, "変更 2 の事前登録"): the rows APPENDED to tests/reading_soundness/ja_r11.jsonl after review round 1 (review.r1.md, required fix 2).

The review named four TYPES of sentence that the two remaining rows (P_MOVE goal/に/PLACE, P_COMMUNICATE goal/に/PLACE) misread, without giving the sentences (they are unpublished). This writes
sentences of those four types with predicates and fillers of my own, with the REAL r8 row of `generated_frames` for the predicate (frame_source `r8`) and the REAL r8 answer for each noun:
  (1) a verb of staying / remaining whose r8 frame holds に:PLACE, with the に phrase the PLACE where the subject stays (convention docs/READING_CONVENTIONS.md section 2: `place`, not `goal`)   -> NIGOAL-A-951..
  (2) a purpose / event noun that r8 types PLACE, with に the purpose of going (there is no goal)                                                                                              -> NIPURP-A-951..
  (3) P_COMMUNICATE with に:PLACE in the r8 frame and a に phrase that is an organization receiving information (convention section 4.1: recipient side) that r8 types PLACE             -> NIRECIP-A-951..
  (4) a sentence whose に is a destination or a place and nothing in it says which (the correct answer is not one reading: `readable: false`)                                                -> NIGOAL-A-961..
Every row is an abstain row (`expect` = readable false): with the registered table the entry reads them as `goal` (the misread), and the rows are the reason the two rows are taken out (K206).
The expectations are written from the design of each row before any run with a placement. A row whose trigger path or gates are not the intended ones is REPORTED and not written.
Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b5/tools/mk_round2_rows.py --out FILE --report FILE
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mk_core as C            # noqa: E402
import mk_data_w3b5 as D       # noqa: E402

AGENTS = D.AGENTS
OLD = {json.loads(l)['input'] for l in open(os.path.join(D.C.TREE, 'tests', 'reading_soundness', 'ja_r11.jsonl'), encoding='utf-8')}


def status(word):
    return C.r8_answer(word).get('frame_status')


def row(group, rg, idn, text, verb, ptype, filler, ftype, cons, note, nouns_extra=None):
    """One abstain row: agent が + filler に + verb. The predicate frame is the real r8 row (it must hold に:ftype); the filler must be the real r8 DECIDED direct answer of type ftype."""
    fr = C.r8_frame_row(verb)
    if not fr or fr['ptype'] != ptype or ftype not in fr['frame'].get('に', []) or status(verb) == 'CONFIRMED':
        D.PROBLEMS.append((text, 'predicate not usable: %s %s' % (verb, fr and (fr['ptype'], fr['frame'])))); return
    if not C.noun_check(filler, (ftype,)):
        D.PROBLEMS.append((text, 'filler %s is not a DECIDED direct %s in r8: %s' % (filler, ftype, C.r8_answer(filler)['top']))); return
    if text in OLD:
        D.PROBLEMS.append((text, 'in the old data')); return
    agent = text[:text.index('が')]
    nouns = {agent: 'r8', filler: 'r8'}
    if nouns_extra: nouns.update(nouns_extra)
    D.add(group, 'A', text, verb, ptype, 'r8', 'に', rg, cons, nouns, C.EXPECT_ABSTAIN, 'REFUSED', note, idnum=idn)


# (1) staying / remaining: the に phrase is the place where the subject stays
STAY = [('兄が教室に居残った。', '居残る', '教室'), ('弟が体育館に居残った。', '居残る', '体育館'), ('姉が旅館に宿泊した。', '宿泊する', '旅館'), ('妹がホテルに宿泊した。', '宿泊する', 'ホテル'),
        ('先生が寺に宿泊した。', '宿泊する', '寺'), ('店員が工場に居残った。', '居残る', '工場'), ('係員が校舎に居残った。', '居残る', '校舎'), ('社員が公民館に宿泊した。', '宿泊する', '公民館')]
for i, (t, v, f) in enumerate(STAY):
    row('NIGOAL', 'ni_goal', 951 + i, t, v, 'P_MOVE', f, 'PLACE', '(b) 滞在・残留の動詞（r8 の枠が に:PLACE を持つ）。に は存在の場所（規約 §2: place）',
        '枠は役割を言わない。goal と読めば誤読（存在の場所）。')

# (2) a purpose / event noun typed PLACE by r8: に is what the subject goes for
PURP = [('弟が遠足に集まった。', '集まる', '遠足'), ('姉が花火大会に集まった。', '集まる', '花火大会'), ('妹がお祭りに殺到した。', '殺到する', 'お祭り'), ('先生が展覧会に来場した。', '来場する', '展覧会'),
        ('店員が花火大会に殺到した。', '殺到する', '花火大会'), ('係員が遠足に立ち寄った。', '立ち寄る', '遠足'), ('選手が展覧会に出張した。', '出張する', '展覧会'), ('学生が神社参拝に殺到した。', '殺到する', '神社参拝'),
        ('職員が展覧会に立ち寄った。', '立ち寄る', '展覧会')]
for i, (t, v, f) in enumerate(PURP):
    row('NIPURP', 'ni_purpose', 951 + i, t, v, 'P_MOVE', f, 'PLACE', '(b) 目的・行事の名詞が r8 で PLACE（に は行く目的・催しで、到達点の場所でない）。述語の枠は に:PLACE を持つ',
        '目的の名詞を goal と読めば誤読。r8 の型（PLACE）が文の語義（行事）と合わない。')

# (3) P_COMMUNICATE with に:PLACE: the に phrase is an organization that receives the information (typed PLACE by r8)
ORG = [('兄が警察署にアップロードした。', 'アップロードする', '警察署', None), ('弟が区役所にアップロードした。', 'アップロードする', '区役所', None),
       ('姉が営業所にアップロードした。', 'アップロードする', '営業所', None), ('妹が支社にアップロードした。', 'アップロードする', '支社', None),
       ('先生が写真を警察署にアップロードした。', 'アップロードする', '警察署', '写真'), ('店員が書類を区役所にアップロードした。', 'アップロードする', '区役所', '書類'),
       ('係員が記録を営業所にアップロードした。', 'アップロードする', '営業所', '記録'), ('社員が資料を支社にアップロードした。', 'アップロードする', '支社', '資料')]
for i, (t, v, f, obj) in enumerate(ORG):
    row('NIRECIP', 'ni_recipient', 951 + i, t, v, 'P_COMMUNICATE', f, 'PLACE', '(b) P_COMMUNICATE の に が情報を受け取る組織（規約 §4.1: recipient 側）で、r8 では PLACE。述語の枠は に:PLACE を持つ',
        '枠は役割を言わない。組織を goal と読めば誤読。', {obj: 'r8'} if obj else None)

# (4) に is a destination or a place and the sentence does not say which: not one reading
UNDEC = [('兄が玄関に座り込んだ。', '座り込む', '玄関'), ('弟が広場にしゃがみこんだ。', 'しゃがみこむ', '広場'), ('姉が入口に倒れ込んだ。', '倒れ込む', '入口'), ('妹が庭に座り込んだ。', '座り込む', '庭'),
         ('先生が舞台に倒れ込んだ。', '倒れ込む', '舞台'), ('店員がベンチに座り込んだ。', '座り込む', 'ベンチ'), ('学生が庭に倒れ込んだ。', '倒れ込む', '庭'), ('係員が広場に座り込んだ。', '座り込む', '広場')]
for i, (t, v, f) in enumerate(UNDEC):
    row('NIGOAL', 'ni_goal', 961 + i, t, v, 'P_MOVE', f, 'PLACE', '(c) に が行き先とも存在の場所とも決まらない（動作の着地点か動作の場所か）。正解は 1 つの読みに決まらない',
        '決まらない文。goal と読めば誤読（棄権が正しい）。')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--report', default=None)
    a = ap.parse_args()
    ids = [r['id'] for r in D.ROWS]; assert len(set(ids)) == len(ids)
    with open(a.out, 'w', encoding='utf-8') as fh:
        for r in D.ROWS:
            assert list(r) == C.KEYS, r['id']
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    rep = ['rows=%d problems=%d' % (len(D.ROWS), len(D.PROBLEMS))] + ['PROBLEM\t%s\t%s' % p for p in D.PROBLEMS]
    rep += ['ROW\t%s\t%s\t%s\t%s' % (r['id'], r['input'], r['path'], r['pred_type']) for r in D.ROWS]
    if a.report: open(a.report, 'w', encoding='utf-8').write('\n'.join(rep) + '\n')
    print('\n'.join(rep))


if __name__ == '__main__':
    main()
