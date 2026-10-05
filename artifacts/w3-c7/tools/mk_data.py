#!/usr/bin/env python3
"""W3-c7 step 3: writes the frozen test data tests/reading_soundness/w3c7_{multi,te,quote,sharing,anaphora}.jsonl.

Nothing here calls the reader. Every expectation is written from the templates below (the clause table, the connective table of docs 10K, the rules K300-K307 and the
decisions H300-H308), before the stage C7 exists. The random choices use random.Random(SEED); hand-written rows have source 'hand'.
Usage: cd <tree> && python3 artifacts/w3-c7/tools/mk_data.py [--seed 300701]
"""
import argparse
import json
import random
from pathlib import Path

TREE = Path(__file__).resolve().parents[3]
OUT = TREE / 'tests' / 'reading_soundness'

# verb: (past, nonpast, te, continuative)
INTR = {'帰る': ('帰った', '帰る', '帰って', '帰り'), '残る': ('残った', '残る', '残って', '残り'), '寝る': ('寝た', '寝る', '寝て', '寝'), '座る': ('座った', '座る', '座って', '座り'),
        '立つ': ('立った', '立つ', '立って', '立ち'), '来る': ('来た', '来る', '来て', None), '起きる': ('起きた', '起きる', '起きて', '起き'), '落ちる': ('落ちた', '落ちる', '落ちて', '落ち')}
# verb: (object, past, nonpast, te, continuative)
TRANS = {'読む': ('本', '読んだ', '読む', '読んで', '読み'), '歌う': ('歌', '歌った', '歌う', '歌って', '歌い'), '描く': ('絵', '描いた', '描く', '描いて', '描き'),
         '飲む': ('薬', '飲んだ', '飲む', '飲んで', '飲み'), '開ける': ('窓', '開けた', '開ける', '開けて', '開け'), '閉める': ('戸', '閉めた', '閉める', '閉めて', '閉め'),
         '買う': ('本', '買った', '買う', '買って', '買い'), '食べる': ('飯', '食べた', '食べる', '食べて', '食べ')}
SAFE_AFTER_TO = ['帰る', '来る', '残る', '寝る', '座る', '立つ', '落ちる', '歌う', '飲む', '開ける', '閉める', '買う', '食べる']   # direct type, not a type of quotation
SUBJ = ['兄', '弟', '母', '姉', '妹', '先生', '生徒']
REL = {'ので': 'cause', 'から': 'cause', 'が': 'contrast', 'けれど': 'contrast', 'と': 'condition', 'なら': 'condition'}
TE_REL = ['sequence', 'manner', 'cause']


def verb_forms(v):
    if v in INTR:
        p, n, t, r = INTR[v]
        return None, p, n, t, r
    o, p, n, t, r = TRANS[v]
    return o, p, n, t, r


def clause_text(s, v, form):
    o, p, n, t, r = verb_forms(v)
    return s + 'が' + (o + 'を' if o else '') + {'past': p, 'nonpast': n, 'te': t, 'ren': r}[form]


def clause_expect(s, v, tense, extra=None):
    o = verb_forms(v)[0]
    roles = {'agent': s}
    if o: roles['patient'] = o
    if extra: roles.update(extra)
    return {'predicate': v, 'roles': roles, 'polarity': '+', 'tense': tense, 'modality': None, 'voice': 'active'}


def row(rid, behavior, text, readable_clauses, relations, entry_expect, w3c7, structure, rule, source, note, cut, construction, why=None):
    expect = {'readable': bool(readable_clauses), 'clauses': readable_clauses or [], 'relations': relations or [], 'must_not': []}
    return {'id': rid, 'lang': 'ja', 'behavior': behavior, 'input': text, 'text': text, 'expect': expect, 'cut': cut, 'construction': construction, 'entry_expect': entry_expect,
            'w3c7_expect': w3c7, 'structure_expect': structure, 'abstain_why': why, 'rule': rule, 'source': source, 'note': note}


def read_row(rid, text, clauses, relations, edges, rule, source, note, cut, construction):
    # `clauses` are the expected clauses of the output; the diagnosis holds the same clauses (the quote's quotation included)
    structure = {'clauses': clauses, 'edges': edges}
    return row(rid, 'read', text, clauses, relations, 'read', 'READ', structure, rule, source, note, cut, construction)


def abstain_row(rid, text, w3c7, rule, source, note, cut, construction, why):
    return row(rid, 'abstain', text, None, None, 'abstain', w3c7, None, rule, source, note, cut, construction, why)


# --- a chain of 3-4 clauses (path M) --------------------------------------------------------------------------------------------------
def chain(rng, n, require_intr=False, allow_cuts=('ので', 'から', 'が', 'けれど', 'と', 'なら')):
    for _ in range(1000):
        subs = rng.sample(SUBJ, n)
        pool = list(INTR) + list(TRANS)
        verbs = rng.sample(pool, n)
        if require_intr and not any(v in INTR for v in verbs): continue
        cuts = [rng.choice(allow_cuts) for _ in range(n - 1)]
        ok = True
        forms = [None] * n
        for i, c in enumerate(cuts):
            if c in ('と', 'なら'):
                forms[i] = 'nonpast'
                if forms[i + 1] not in (None, 'nonpast'): ok = False
                forms[i + 1] = 'nonpast'
                if c == 'と' and verbs[i + 1] not in SAFE_AFTER_TO: ok = False
        if not ok: continue
        forms = [f or rng.choice(['past', 'nonpast']) for f in forms]
        return subs, verbs, cuts, forms
    raise RuntimeError('no chain')


def chain_row(rid, subs, verbs, cuts, forms, rule, source, note):
    n = len(subs)
    text = ''
    clauses, rels, edges = [], [], []
    for i in range(n):
        text += clause_text(subs[i], verbs[i], forms[i])
        tense = forms[i]
        if i < n - 1:
            text += cuts[i] + '、'
            if cuts[i] == 'なら': tense = None
        clauses.append(clause_expect(subs[i], verbs[i], tense))
        if i < n - 1:
            rels.append({'type': REL[cuts[i]], 'from': i, 'to': i + 1})
            edges.append({'kind': 'finite', 'type': REL[cuts[i]], 'from': i, 'to': i + 1})
    text += '。'
    return read_row(rid, text, clauses, rels, edges, rule, source, note, '+'.join(cuts), '%d 節の連鎖（%s）' % (n, '・'.join(cuts)))


def make_multi(rng):
    rows, k = [], 0
    rid = lambda: 'W3C7-MULTI-%03d' % (len(rows) + 1)
    for n in (3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4):
        subs, verbs, cuts, forms = chain(rng, n)
        rows.append(chain_row(rid(), subs, verbs, cuts, forms, '1', 'generated seed', '定形の切れ目だけの %d 節。隣り合う節の間に辺を 1 本ずつ。' % n))
    # relative at the head of the chain: the last clause has an object so that the head's phrase cannot belong to it (K116 generalised)
    text = '母が弟に話した人を兄が呼んだので、姉が窓を開けた。'
    c = [{'predicate': '話す', 'roles': {'agent': '母', 'recipient': '弟', 'patient': '人'}, 'polarity': '+', 'tense': 'past', 'modality': None, 'voice': 'active'},
         {'predicate': '呼ぶ', 'roles': {'agent': '兄', 'patient': '人'}, 'polarity': '+', 'tense': 'past', 'modality': None, 'voice': 'active'},
         clause_expect('姉', '開ける', 'past')]
    rows.append(read_row(rid(), text, c, [{'type': 'relative', 'from': 0, 'to': 1}, {'type': 'cause', 'from': 1, 'to': 2}],
                         [{'kind': 'relative', 'type': 'relative', 'from': 0, 'to': 1}, {'kind': 'finite', 'type': 'cause', 'from': 1, 'to': 2}], '1', 'hand',
                         '連体の切れ目と定形の切れ目。最後の節の を が、主辞の句の を の移し先を壊す。', 'relative+ので', '3 節（連体・ので）'))
    # abstentions
    A = lambda text, w3c7, note, cut, why: rows.append(abstain_row(rid(), text, w3c7, '1', 'hand', note, cut, '3 節以上の棄権', why))
    A('兄が本を読んで、弟が帰ったので、妹が座った。', 'CUT_KIND_NOT_READ', '非定形（て）を含む 3 節は棄権。', 'て+ので', 'nonfinite_cut')
    A('兄が本を読み、弟が帰ったので、妹が座った。', 'CUT_KIND_NOT_READ', '非定形（連用中止）を含む 3 節は棄権。', '並列+ので', 'nonfinite_cut')
    A('兄が帰れば、弟が来たので、母が座った。', 'CUT_KIND_NOT_READ', '非定形（ば）を含む 3 節は棄権。', 'ば+ので', 'nonfinite_cut')
    A('兄が帰ったら、弟が来たが、母が座った。', 'CUT_KIND_NOT_READ', '非定形（たら）を含む 3 節は棄権。', 'たら+が', 'nonfinite_cut')
    A('兄が帰っても、弟が来たので、母が座った。', 'CUT_KIND_NOT_READ', '非定形（ても）を含む 3 節は棄権。', 'ても+ので', 'nonfinite_cut')
    A('兄が本を読みながら、弟が来たが、母が座った。', 'CUT_KIND_NOT_READ', '非定形（ながら）を含む 3 節は棄権。', 'ながら+が', 'nonfinite_cut')
    A('兄が帰ったので、弟が来たが、母が座ったけれど、姉が立ったから、妹が寝た。', 'CLAUSES_OVER_LIMIT', '5 節は上限（4 節）を超える。', 'ので+が+けれど+から', 'over_limit')
    A('兄が帰ったので、弟は来たが、母が座った。', 'CLAUSE_SCOPE_AMBIGUOUS', '主題が先頭の節以外にある。', 'ので+が', 'topic_position')
    A('本を兄が読んだので、弟が帰ったが、母が座った。', 'CLAUSE_SCOPE_AMBIGUOUS', '先頭の句（本を）が 2 番目の節の側にも付きうる（切り方の別解）。', 'ので+が', 'alternative_cut')
    A('兄が帰ると、母が言うので、姉が座った。', 'RELATION_TYPE_UNDETERMINED', 'と の主節の述語が伝達の型（引用の可能性）。', 'と+ので', 'quote_possible')
    A('兄が帰ると、弟が来たので、母が座った。', 'RELATION_TYPE_UNDETERMINED', 'と の主節が過去（条件の主節が過去は決まらない）。', 'と+ので', 'condition_past_main')
    A('兄が帰ったので、弟が来たが、母が座ったか。', 'CLAUSE_FORM_NOT_READ', '疑問の終助詞。', 'ので+が', 'question')
    A('兄が帰ったのに、弟が来たので、母が座った。', 'CLAUSE_SCOPE_NOT_LISTED', '一覧外の形（のに）。', 'のに+ので', 'not_listed')
    return rows


# --- te / continuative (path T) ----------------------------------------------------------------------------------------------------------
def pair_clauses(rng):
    s0, s1 = rng.sample(SUBJ, 2)
    pool = list(INTR) + list(TRANS)
    while True:
        v0, v1 = rng.sample(pool, 2)
        return s0, v0, s1, v1


def te_row(rid, s0, v0, s1, v1, f1, comma, kind, rule, source, note):
    form0 = 'te' if kind == 'te' else 'ren'
    t0 = clause_text(s0, v0, form0)
    t1 = clause_text(s1, v1, f1)
    text = t0 + ('、' if comma or kind == 'parallel' else '') + t1 + '。'
    c = [clause_expect(s0, v0, None), clause_expect(s1, v1, f1)]
    types = TE_REL if kind == 'te' else ['sequence']
    edge = {'kind': 'te' if kind == 'te' else 'parallel', 'type': 'sequence', 'from': 0, 'to': 1}
    return read_row(rid, text, c, [{'type': types, 'from': 0, 'to': 1}], [edge], rule, source, note, 'て' if kind == 'te' else '並列',
                    '2 節の て（両節に主語）' if kind == 'te' else '2 節の連用中止（両節に主語）')


def make_te(rng):
    rows = []
    rid = lambda: 'W3C7-TE-%03d' % (len(rows) + 1)
    kinds = ['te'] * 7 + ['parallel'] * 6
    for kind in kinds:
        while True:
            s0, v0, s1, v1 = pair_clauses(rng)
            if kind == 'parallel' and verb_forms(v0)[4] is None: continue
            break
        rows.append(te_row(rid(), s0, v0, s1, v1, rng.choice(['past', 'nonpast']), rng.random() < 0.7, kind, '2', 'generated seed',
                           '両方の節が自分の主語（が）を持つ。て は sequence・manner・cause のどれか、連用中止は sequence。'))
    A = lambda text, w3c7, note, cut, why: rows.append(abstain_row(rid(), text, w3c7, '2', 'hand', note, cut, '2 節の て・連用中止の棄権', why))
    A('兄は本を読んで、歌を歌った。', 'SUBJECT_SHARING_NOT_READ', '後ろの節に主語が無い（兄は の主題は共有しない）。', 'て', 'subject_missing_right')
    A('弟は絵を描いて、薬を飲んだ。', 'SUBJECT_SHARING_NOT_READ', '後ろの節に主語が無い。', 'て', 'subject_missing_right')
    A('母は窓を開け、戸を閉めた。', 'SUBJECT_SHARING_NOT_READ', '連用中止。後ろの節に主語が無い。', '並列', 'subject_missing_right')
    A('本を読んで、弟が歌を歌った。', 'SUBJECT_SHARING_NOT_READ', '前の節に主語が無い。', 'て', 'subject_missing_left')
    A('絵を描き、姉が薬を飲んだ。', 'SUBJECT_SHARING_NOT_READ', '連用中止。前の節に主語が無い。', '並列', 'subject_missing_left')
    A('兄が本を読んで、弟は歌を歌った。', 'CLAUSE_SCOPE_AMBIGUOUS', '主題が後ろの節にある。', 'て', 'topic_position')
    A('姉が絵を描き、母は薬を飲んだ。', 'CLAUSE_SCOPE_AMBIGUOUS', '連用中止。主題が後ろの節にある。', '並列', 'topic_position')
    A('妹が飯を食べて、先生は窓を開けた。', 'CLAUSE_SCOPE_AMBIGUOUS', '主題が後ろの節にある。', 'て', 'topic_position')
    A('兄が読んで、弟が歌を歌った。', 'ROLE_SHARING_NOT_READ', '前の節は他動詞で目的語が無く、後ろの節に目的語がある（共有の疑い）。', 'て', 'role_sharing')
    A('姉が描き、母が薬を飲んだ。', 'ROLE_SHARING_NOT_READ', '連用中止。前の節は他動詞で目的語が無い。', '並列', 'role_sharing')
    A('先生が食べて、生徒が窓を開けた。', 'ROLE_SHARING_NOT_READ', '前の節は他動詞で目的語が無い。', 'て', 'role_sharing')
    A('本を兄が読んで、弟が帰った。', 'CLAUSE_SCOPE_AMBIGUOUS', '先頭の句（本を）が後ろの節にも付きうる。', 'て', 'alternative_cut')
    A('兄が本を読んで、弟が歌を歌ったか。', 'CLAUSE_FORM_NOT_READ', '疑問の終助詞。', 'て', 'question')
    return rows


# --- quotation (path Q) ------------------------------------------------------------------------------------------------------------------
COMM = {'言った': ('言う', 'past'), '思った': ('思う', 'past'), '伝えた': ('伝える', 'past'), '叫んだ': ('叫ぶ', 'past'), '話した': ('話す', 'past'), '考えた': ('考える', 'past'),
        '知った': ('知る', 'past'), '書いた': ('書く', 'past'), '言う': ('言う', 'nonpast'), '思う': ('思う', 'nonpast'), '答えた': ('答える', 'past')}


def quote_row(rid, s1, comm, s2, v2, f2, topic, rule, source, note):
    content = clause_text(s2, v2, f2)
    text = s1 + ('は' if topic else 'が') + content + 'と' + comm + '。'
    pred, tense = COMM[comm]
    c = [clause_expect(s2, v2, f2), {'predicate': pred, 'roles': {'agent': s1, 'quotation': content}, 'polarity': '+', 'tense': tense, 'modality': None, 'voice': 'active'}]
    return read_row(rid, text, c, [{'type': 'quote', 'from': 1, 'to': 0}], [{'kind': 'quote', 'type': 'quote', 'from': 1, 'to': 0}], rule, source, note, 'と(引用)', '引用: と＋伝達・思考の述語')


def make_quote(rng):
    rows = []
    rid = lambda: 'W3C7-QUOTE-%03d' % (len(rows) + 1)
    comms = ['言った', '思った', '伝えた', '叫んだ', '話した', '考えた', '知った', '書いた']
    for comm in comms:
        s1, s2 = rng.sample(SUBJ, 2)
        v2 = rng.choice(list(INTR) + list(TRANS))
        rows.append(quote_row(rid(), s1, comm, s2, v2, 'past', False, '3', 'generated seed', '伝達・思考の述語（配置の型）。内容を埋め込みの十字として読み、伝達の節に quotation。'))
    for comm, v2 in (('言う', '帰る'), ('思う', '座る')):
        s1, s2 = rng.sample(SUBJ, 2)
        rows.append(quote_row(rid(), s1, comm, s2, v2, 'nonpast', False, '3', 'generated seed', '内容が非過去。'))
    for s1, s2, v2 in (('母', '兄', '帰る'), ('先生', '生徒', '読む'), ('姉', '妹', '歌う')):
        rows.append(quote_row(rid(), s1, '答えた', s2, v2, 'past', True, '3', 'hand', '主題（は）の伝達の節。答える は は の主題でも単独で読める。'))
    A = lambda text, w3c7, note, why: rows.append(abstain_row(rid(), text, w3c7, '3', 'hand', note, 'と(引用)', '引用の棄権', why))
    A('兄が本を読んだと言った。', 'QUOTE_CONTENT_NOT_READ', '中身に主語が無い（誰が読んだのか決まらない）。', 'content_no_subject')
    A('母が手紙を書いたと思った。', 'QUOTE_CONTENT_NOT_READ', '中身に主語が無い。', 'content_no_subject')
    A('姉が絵を描いたと伝えた。', 'QUOTE_CONTENT_NOT_READ', '中身に主語が無い。', 'content_no_subject')
    A('先生が薬を飲んだと話した。', 'QUOTE_CONTENT_NOT_READ', '中身に主語が無い。', 'content_no_subject')
    A('兄は母に弟が来たと言った。', 'QUOTE_CONTENT_NOT_READ', '分け方が 2 通り（母に が伝達の側か中身の側か）。', 'split_two')
    A('姉は先生に妹が帰ったと伝えた。', 'QUOTE_CONTENT_NOT_READ', '分け方が 2 通り。', 'split_two')
    A('母は兄に姉が残ったと話した。', 'QUOTE_CONTENT_NOT_READ', '分け方が 2 通り。', 'split_two')
    A('兄が弟が来たと喜んだ。', 'QUOTE_PREDICATE_NOT_READ', '述語の型が伝達・思考の型でない（感情）。', 'predicate_not_quote_type')
    A('姉が妹が帰ったと喜んだ。', 'QUOTE_PREDICATE_NOT_READ', '述語の型が伝達・思考の型でない（感情）。', 'predicate_not_quote_type')
    A('兄が、弟が来たと言った。', 'QUOTE_CONTENT_NOT_READ', '読点がある。', 'comma')
    A('母が、姉が帰ったと思った。', 'QUOTE_CONTENT_NOT_READ', '読点がある。', 'comma')
    A('兄が弟が来たと言ったか。', 'CLAUSE_FORM_NOT_READ', '疑問の終助詞。', 'question')
    A('兄が弟が来たと言ったので、母が座った。', 'CLAUSE_SCOPE_AMBIGUOUS', '引用に別の節が付く 3 節（切れ目の数が合わない）は読まない。', 'quote_in_multi')
    return rows


# --- sharing across clauses (K304, H304) ----------------------------------------------------------------------------------------------------
def make_sharing(rng):
    rows = []
    rid = lambda: 'W3C7-SHARE-%03d' % (len(rows) + 1)
    # read: an intransitive clause among clauses that have objects: its object arm stays empty (nothing to share)
    for _ in range(6):
        subs, verbs, cuts, forms = chain(rng, 3, require_intr=True, allow_cuts=('ので', 'から', 'が', 'けれど'))
        rows.append(chain_row(rid(), subs, verbs, cuts, forms, '4', 'generated seed', '自動詞の節の目的語の腕は空のまま（共有する先行詞は無い）。'))
    for _ in range(5):
        while True:
            s0, v0, s1, v1 = pair_clauses(rng)
            if (v0 in INTR) or (v1 in INTR):
                if verb_forms(v0)[3] is None: continue
                break
        rows.append(te_row(rid(), s0, v0, s1, v1, 'past', True, 'te', '4', 'generated seed', '自動詞の節の腕は空のまま。'))
    for s1, s2, v2 in (('生徒', '先生', '座る'), ('妹', '母', '帰る')):
        rows.append(quote_row(rid(), s1, '言った', s2, v2, 'past', False, '4', 'hand', '中身が自動詞（腕は空のまま）。'))
    A = lambda text, w3c7, note, cut, why: rows.append(abstain_row(rid(), text, w3c7, '4', 'hand', note, cut, '節をまたぐ共有の棄権', why))
    A('兄は本を読んだので、歌を歌ったが、弟が窓を開けた。', 'SUBJECT_SHARING_NOT_READ', '真ん中の節に主語が無い（兄は は先頭の節だけに属する）。', 'ので+が', 'subject_missing_middle')
    A('母は薬を飲んだから、戸を閉めたけれど、姉が飯を食べた。', 'SUBJECT_SHARING_NOT_READ', '真ん中の節に主語が無い。', 'から+けれど', 'subject_missing_middle')
    A('先生は絵を描いたが、本を買ったので、生徒が窓を開けた。', 'SUBJECT_SHARING_NOT_READ', '真ん中の節に主語が無い。', 'が+ので', 'subject_missing_middle')
    A('姉は飯を食べて、薬を飲んだ。', 'SUBJECT_SHARING_NOT_READ', '後ろの節に主語が無い（て）。', 'て', 'subject_missing_right')
    A('妹は戸を閉めて、窓を開けた。', 'SUBJECT_SHARING_NOT_READ', '後ろの節に主語が無い（て）。', 'て', 'subject_missing_right')
    A('歌を歌って、母が飯を食べた。', 'SUBJECT_SHARING_NOT_READ', '前の節に主語が無い（て）。', 'て', 'subject_missing_left')
    A('兄が泣いたので、弟が帰ったが、母が座った。', 'ROLE_SHARING_NOT_READ', '先頭の節は目的語の取れる述語で目的語が無く、ほかの節に値がある。', 'ので+が', 'role_sharing')
    A('姉が帰ったので、母が笑ったが、妹が座った。', 'ROLE_SHARING_NOT_READ', '真ん中の節が目的語の取れる述語で目的語が無い。', 'ので+が', 'role_sharing')
    A('先生が喜んだから、弟が来たけれど、母が立った。', 'ROLE_SHARING_NOT_READ', '先頭の節が目的語の取れる述語で目的語が無い。', 'から+けれど', 'role_sharing')
    A('兄が笑って、弟が本を読んだ。', 'ROLE_SHARING_NOT_READ', '前の節が目的語の取れる述語で目的語が無く、後ろの節に値がある（て）。', 'て', 'role_sharing')
    A('母が泣き、姉が歌を歌った。', 'ROLE_SHARING_NOT_READ', '連用中止。前の節に目的語が無い。', '並列', 'role_sharing')
    A('生徒が窓を開けたので、妹が帰ったが、母が喜んだ。', 'ROLE_SHARING_NOT_READ', '最後の節が目的語の取れる述語で目的語が無い。', 'ので+が', 'role_sharing')
    A('兄が弟が笑ったと言った。', 'ROLE_SHARING_NOT_READ', '中身が目的語の取れる述語で目的語が無く、伝達の節に値がある。', 'と(引用)', 'role_sharing')
    return rows


# --- anaphora (K305) ---------------------------------------------------------------------------------------------------------------------
def make_anaphora(rng):
    rows = []
    rid = lambda: 'W3C7-ANA-%03d' % (len(rows) + 1)
    # pairs: the same shape with a noun (read) and with a word of the part of speech pronoun / adnominal (abstain)
    # (c0, c1, c2) with the connectives; the twin puts `word` where `where` says: ('subj', i) the subject of clause i, ('obj', i) its object
    pairs = [
        (('兄', '帰る', 'ので'), ('弟', '来る', 'が'), ('母', '座る', None), '彼', ('subj', 0)),
        (('姉', '読む', 'から'), ('妹', '寝る', 'けれど'), ('先生', '立つ', None), 'それ', ('obj', 0)),
        (('弟', '帰る', 'ので'), ('母', '飲む', 'が'), ('生徒', '残る', None), 'あれ', ('obj', 1)),
        (('先生', '来る', 'が'), ('兄', '買う', 'ので'), ('姉', '座る', None), 'これ', ('obj', 1)),
        (('妹', '立つ', 'から'), ('弟', '食べる', 'ので'), ('兄', '寝る', None), '彼女', ('subj', 1)),
    ]
    for c0, c1, c2, word, (kind, pos) in pairs:
        cs = [c0, c1, c2]
        subs, verbs, cuts = [c[0] for c in cs], [c[1] for c in cs], [c0[2], c1[2]]
        forms = ['past'] * 3
        rows.append(chain_row(rid(), subs, verbs, cuts, forms, '5', 'hand', '照応の無い最小対（同じ形で読む）。'))
        parts = []
        for i in range(3):
            o = verb_forms(verbs[i])[0]
            subj = word if (kind == 'subj' and pos == i) else subs[i]
            obj = word if (kind == 'obj' and pos == i) else o
            parts.append(subj + 'が' + (obj + 'を' if obj else '') + verb_forms(verbs[i])[1])
        text = parts[0] + cuts[0] + '、' + parts[1] + cuts[1] + '、' + parts[2] + '。'
        rows.append(abstain_row(rid(), text, 'ANAPHORA_NOT_READ', '5', 'hand', '主辞が代名詞（品詞）。', cuts[0] + '+' + cuts[1], '3 節の照応の棄権', 'anaphora'))
    # te / quote shapes
    te_pairs = [('兄', '読む', '弟', '歌う', '彼'), ('姉', '描く', '母', '飲む', 'それ'), ('先生', '帰る', '生徒', '食べる', '彼女')]
    for s0, v0, s1, v1, word in te_pairs:
        rows.append(te_row(rid(), s0, v0, s1, v1, 'past', True, 'te', '5', 'hand', '照応の無い最小対。'))
        t = clause_text(s0, v0, 'te')
        if word in ('それ',):
            t = s0 + 'が' + word + 'を' + verb_forms(v0)[3]
        else:
            t = word + 'が' + (verb_forms(v0)[0] + 'を' if verb_forms(v0)[0] else '') + verb_forms(v0)[3]
        rows.append(abstain_row(rid(), t + '、' + clause_text(s1, v1, 'past') + '。', 'ANAPHORA_NOT_READ', '5', 'hand', '主辞が代名詞。', 'て', 'て の照応の棄権', 'anaphora'))
    for s1, comm, s2, v2, word in (('兄', '言った', '弟', '帰る', '彼'), ('母', '思った', '姉', '座る', 'この')):
        rows.append(quote_row(rid(), s1, comm, s2, v2, 'past', False, '5', 'hand', '照応の無い最小対。'))
        if word == '彼':
            text = s1 + 'が' + word + 'が' + verb_forms(v2)[1] + 'と' + comm + '。'
        else:
            text = s1 + 'が' + 'この' + '姉' + 'が' + verb_forms(v2)[1] + 'と' + comm + '。'
        rows.append(abstain_row(rid(), text, 'ANAPHORA_NOT_READ', '5', 'hand', '主辞が代名詞か連体詞（指示）。', 'と(引用)', '引用の照応の棄権', 'anaphora'))
    # the adnominal class: every word of the class is refused (the price of deciding by the part of speech)
    for text in ('兄が大きな本を読んだので、弟が帰ったが、母が座った。', '姉が同じ薬を飲んで、妹が歌を歌った。', '先生がその窓を開けたから、生徒が帰ったが、母が座った。'):
        rows.append(abstain_row(rid(), text, 'ANAPHORA_NOT_READ', '5', 'hand', '連体詞は品詞で全部棄権する（大きな・同じ も。代価）。', '連体詞', '連体詞の棄権', 'rentaishi'))
    for subs, verbs, cuts in ((['兄', '弟', '母'], ['描く', '帰る', '座る'], ['ので', 'が']), (['先生', '生徒', '母'], ['開ける', '帰る', '立つ'], ['から', 'が'])):
        rows.append(chain_row(rid(), subs, verbs, cuts, ['past'] * 3, '5', 'hand', '連体詞の無い最小対（同じ形で読む）。'))
    rows.append(te_row(rid(), '姉', '飲む', '妹', '歌う', 'past', True, 'te', '5', 'hand', '連体詞の無い最小対（同じ形で読む）。'))
    return rows


# --- supplementary rows (POST-HOC: written after the first run of the stage, not part of the frozen data) ------------------------------------------
# The first run showed that the gate of W3-b3 for a derived verb (typed_head_derived_ja) stops every verb of the lower one-step conjugation (taberu, akeru, shimeru, neru, kangaeru,
# kotaeru, tsutaeru ...): 41 rows of the frozen data expect a reading that this older gate forbids. The frozen rows stay as they are (their mismatch is reported). These rows keep to
# the verbs that the gate lets through, to show the stage itself on the same shapes. They were written after the first run: they are not evidence of a prediction.
GOOD_INTR = ['帰る', '残る', '座る', '立つ', '来る', '起きる', '落ちる']
GOOD_TRANS = ['読む', '歌う', '描く', '飲む', '買う']
GOOD_COMM = ['言った', '思った', '叫んだ', '話した', '知った', '書いた', '言う', '思う']


def make_sup(rng):
    global INTR, TRANS, SAFE_AFTER_TO
    saved = (INTR, TRANS, SAFE_AFTER_TO)
    INTR = {k: v for k, v in INTR.items() if k in GOOD_INTR}
    TRANS = {k: v for k, v in TRANS.items() if k in GOOD_TRANS}
    SAFE_AFTER_TO = [v for v in SAFE_AFTER_TO if v in INTR or v in TRANS]
    rows = []
    rid = lambda: 'W3C7-SUP-%03d' % (len(rows) + 1)
    try:
        for n in (3, 3, 3, 3, 3, 3, 4, 4, 4, 4):
            subs, verbs, cuts, forms = chain(rng, n)
            rows.append(chain_row(rid(), subs, verbs, cuts, forms, '1', 'generated seed 300702 (post-hoc)', '定形の切れ目だけの %d 節（派生の疑いの門を通る動詞だけ）。' % n))
        for kind in ['te'] * 3 + ['parallel'] * 3:
            while True:
                s0, v0, s1, v1 = pair_clauses(rng)
                if kind == 'parallel' and verb_forms(v0)[4] is None: continue
                break
            rows.append(te_row(rid(), s0, v0, s1, v1, rng.choice(['past', 'nonpast']), rng.random() < 0.7, kind, '2', 'generated seed 300702 (post-hoc)', '両節に主語のある て・連用中止。'))
        for comm in ('言った', '思った', '叫んだ', '話した', '知った', '書いた', '言う', '思う'):
            s1, s2 = rng.sample(SUBJ, 2)
            v2 = rng.choice(list(INTR) + list(TRANS))
            rows.append(quote_row(rid(), s1, comm, s2, v2, 'nonpast' if comm in ('言う', '思う') else 'past', False, '3', 'generated seed 300702 (post-hoc)', '引用（派生の疑いの門を通る動詞だけ）。'))
        for text, tail in (('母が弟に話した人を兄が呼んだので、姉が絵を描いた。', None), ('兄が帰ったので、母が弟に話した人を姉が呼んだが、妹が絵を描いた。', 'lead')):
            rel0 = {'predicate': '話す', 'roles': {'agent': '母', 'recipient': '弟', 'patient': '人'}, 'polarity': '+', 'tense': 'past', 'modality': None, 'voice': 'active'}
            if tail is None:
                cl = [rel0, {'predicate': '呼ぶ', 'roles': {'agent': '兄', 'patient': '人'}, 'polarity': '+', 'tense': 'past', 'modality': None, 'voice': 'active'}, clause_expect('姉', '描く', 'past')]
                rels = [{'type': 'relative', 'from': 0, 'to': 1}, {'type': 'cause', 'from': 1, 'to': 2}]
                edges = [{'kind': 'relative', 'type': 'relative', 'from': 0, 'to': 1}, {'kind': 'finite', 'type': 'cause', 'from': 1, 'to': 2}]
            else:
                # H309 (round 2, review M1): a finite cut followed by a relative cut: the attachment of the finite clause is split, so the sentence is refused
                rows.append(abstain_row(rid(), text, 'RELATIVE_NESTED_NOT_READ', '1', 'hand (post-hoc, round 2: was a read row until review M1)', '定形の切れ目の直後に連体の切れ目。定形の節の掛かり先（関係節か主節か）が割れる。', 'ので+連体+が', '連体を含む 3〜4 節', 'attachment'))
                continue
            rows.append(read_row(rid(), text, cl, rels, edges, '1', 'hand (post-hoc)', '連体の切れ目を含む連鎖。最後の節の を が主辞の句の移し先を壊す。', 'relative', '連体を含む 3〜4 節'))
        A = lambda text, w3c7, note, cut, why: rows.append(abstain_row(rid(), text, w3c7, '4', 'hand (post-hoc)', note, cut, '節をまたぐ共有の棄権', why))
        A('兄は本を読んだので、歌を歌ったが、弟が絵を描いた。', 'SUBJECT_SHARING_NOT_READ', '真ん中の節に主語が無い。', 'ので+が', 'subject_missing_middle')
        A('母は薬を飲んだから、本を買ったけれど、姉が歌を歌った。', 'SUBJECT_SHARING_NOT_READ', '真ん中の節に主語が無い。', 'から+けれど', 'subject_missing_middle')
        A('姉は本を読んで、薬を飲んだ。', 'SUBJECT_SHARING_NOT_READ', '後ろの節に主語が無い（て）。', 'て', 'subject_missing_right')
        A('歌を歌って、母が本を読んだ。', 'SUBJECT_SHARING_NOT_READ', '前の節に主語が無い（て）。', 'て', 'subject_missing_left')
        A('兄が笑ったので、弟が帰ったが、母が座った。', 'ROLE_SHARING_NOT_READ', '先頭の節に目的語が無く、ほかの節に値がある。', 'ので+が', 'role_sharing')
        A('兄が読んで、弟が歌を歌った。', 'ROLE_SHARING_NOT_READ', '前の節は他動詞で目的語が無い（て）。', 'て', 'role_sharing')
        A('母が飲み、姉が歌を歌った。', 'ROLE_SHARING_NOT_READ', '連用中止。前の節は他動詞で目的語が無い。', '並列', 'role_sharing')
        A('兄が弟が笑ったと言った。', 'ROLE_SHARING_NOT_READ', '中身が目的語の取れる述語で目的語が無い。', 'と(引用)', 'role_sharing')
        for text, cut in (('兄が帰ったので、母が弟に話した人を姉が呼んだ。', 'ので+連体'), ('兄が来たが、母が弟に話した人を姉が呼んだ。', 'が+連体')):
            rows.append(abstain_row(rid(), text, 'RELATIVE_NESTED_NOT_READ', '1', 'hand (post-hoc, round 2: review M1)', '定形の切れ目の直後に連体の切れ目。定形の節の掛かり先が割れる。', cut, '連体を含む 3〜4 節', 'attachment'))
    finally:
        INTR, TRANS, SAFE_AFTER_TO = saved
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=300701)
    ap.add_argument('--sup', action='store_true', help='write only the post-hoc supplementary file (seed 300702)')
    a = ap.parse_args()
    if a.sup:
        taken = set()
        for name in ('multi', 'te', 'quote', 'sharing', 'anaphora'):
            for l in (OUT / ('w3c7_%s.jsonl' % name)).read_text(encoding='utf-8').splitlines(): taken.add(json.loads(l)['input'])
        rows = make_sup(random.Random(300702))
        seen_here = set()
        rows = [r for r in rows if r['input'] not in taken and not (r['input'] in seen_here or seen_here.add(r['input']))]
        for i, r in enumerate(rows): r['id'] = 'W3C7-SUP-%03d' % (i + 1)
        (OUT / 'w3c7_sup.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        print('sup', len(rows), sum(1 for r in rows if r['entry_expect'] == 'read'), sum(1 for r in rows if r['entry_expect'] == 'abstain'))
        return
    rng = random.Random(a.seed)
    files = {'multi': make_multi(rng), 'te': make_te(rng), 'quote': make_quote(rng), 'sharing': make_sharing(rng), 'anaphora': make_anaphora(rng)}
    seen = {}
    for name, rows in files.items():
        for r in rows:
            if r['input'] in seen:
                raise SystemExit('DUPLICATE INPUT %s in %s and %s' % (r['input'], seen[r['input']], r['id']))
            seen[r['input']] = r['id']
        (OUT / ('w3c7_%s.jsonl' % name)).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        print(name, len(rows), sum(1 for r in rows if r['entry_expect'] == 'read'), sum(1 for r in rows if r['entry_expect'] == 'abstain'))


if __name__ == '__main__':
    main()
