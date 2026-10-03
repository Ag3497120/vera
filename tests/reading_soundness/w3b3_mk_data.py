#!/usr/bin/env python3
"""W3-b3 step 3: writes the frozen test data w3b3_relative.jsonl, w3b3_connective.jsonl, w3b3_parallel.jsonl, w3b3_w1a4.jsonl.

The expectations are written HERE, before any of these sentences goes through the new path (docs/READING_SOUNDNESS.md section 10C was registered first).
  expect          the reading by the convention (docs/READING_CONVENTIONS.md), whatever the implementation can produce. An `abstain` row has readable: false, meaning
                  "this path does not decide a unique reading" (it is NOT the convention's 'unreadable input' of section 7).
  entry_expect    what the entry (`semantic_read.read`, with the placement) is expected to return: read | abstain
  w3b3_expect     what the diagnosis (`semantic_read.clause_scope_explain_ja`) is expected to say: READ, or the beginning of a reason of K122 (checked with startswith); ABSTAIN = any
  structure_expect  for the て / 連用中止 rows only: the two clauses and the edge the diagnosis writes
No word list is used by the path; the sentences here are the only place the words are.
Usage: cd <tree> && python tests/reading_soundness/w3b3_mk_data.py [--out DIR]
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def cl(pred, roles, tense='past', pol='+', voice='active'):
    return {'predicate': pred, 'roles': roles, 'polarity': pol, 'tense': tense, 'modality': None, 'voice': voice}


def exp_read(clauses, relations):
    return {'readable': True, 'clauses': clauses, 'relations': relations, 'must_not': []}


EXP_NO = {'readable': False, 'clauses': [], 'relations': [], 'must_not': []}


def row(prefix, n, behavior, text, expect, cut, construction, entry, w3, source, note, structure=None, why=None):
    return {'id': '%s-%03d' % (prefix, n), 'lang': 'ja', 'behavior': behavior, 'input': text, 'text': text, 'expect': expect, 'cut': cut, 'construction': construction,
            'entry_expect': entry, 'w3b3_expect': w3, 'structure_expect': structure, 'abstain_why': why, 'source': source, 'note': note}


# ---------------------------------------------------------------------------------------------------------------------------------
# relative clauses (60): 30 read (convention reading), 30 abstain
# ---------------------------------------------------------------------------------------------------------------------------------
def relative_rows():
    rows = []
    P = 'W3B3-REL'

    def add(behavior, text, expect, construction, entry, w3, note, why=None):
        rows.append(row(P, len(rows) + 1, behavior, text, expect, 'relative', construction, entry, w3, 'w3b3_relative', note, None, why))

    def read(text, c0, c1, head, construction, entry, w3, note, arm=None):
        add('read', text, exp_read([c0, c1], [{'type': 'relative', 'from': 0, 'to': 1}]), construction, entry, w3, note)

    # --- read, P_COMMUNICATE, the head is the patient (the relative clause starts with a が phrase): predicted READ
    for A, B, vp, v, H, C, v2p, v2 in (
            ('母', '弟', '話した', '話す', '人', '兄', '呼んだ', '呼ぶ'),
            ('姉', '妹', '頼んだ', '頼む', '友達', '先生', '呼んだ', '呼ぶ'),
            ('兄', '先生', '言った', '言う', '生徒', '母', '待った', '待つ'),
            ('父', '祖母', '話した', '話す', '犬', '兄', '見た', '見る'),
            ('母', '姉', '話した', '話す', '本', '弟', '読んだ', '読む'),
            ('兄', '弟', '頼んだ', '頼む', '花', '母', '買った', '買う'),
            ('姉', '母', '頼んだ', '頼む', '薬', '弟', '飲んだ', '飲む'),
            ('祖父', '兄', '話した', '話す', '絵', '姉', '描いた', '描く'),
            ('先生', '生徒', '言った', '言う', '歌', '弟', '歌った', '歌う'),
            ('母', '弟', '話した', '話す', '客', '兄', '呼んだ', '呼ぶ')):
        text = '%sが%sに%s%sを%sが%s。' % (A, B, vp, H, C, v2p)
        read(text, cl(v, {'agent': A, 'recipient': B, 'patient': H}), cl(v2, {'agent': C, 'patient': H}), H,
             'P_COMMUNICATE: 空いている腕は patient（agent と に の腕が埋まる）', 'read', 'READ', '関係節の先頭は が の句。空いている腕は patient だけ（に の腕は埋まっている）。主辞の型は patient の期待に合う。')
    # --- read, P_COMMUNICATE, the head is the agent (the relative clause starts with an を phrase): predicted READ
    for O, B, vp, v, H, C, v2p, v2 in (
            ('歌', '弟', '頼んだ', '頼む', '人', '兄', '呼んだ', '呼ぶ'),
            ('本', '妹', '話した', '話す', '先生', '母', '待った', '待つ'),
            ('絵', '先生', '言った', '言う', '生徒', '弟', '呼んだ', '呼ぶ')):
        text = '%sを%sに%s%sを%sが%s。' % (O, B, vp, H, C, v2p)
        read(text, cl(v, {'agent': H, 'patient': O, 'recipient': B}), cl(v2, {'agent': C, 'patient': H}), H,
             'P_COMMUNICATE: 空いている腕は agent', 'read', 'READ', '関係節の先頭は を の句。空いている腕は agent だけ。主辞は人で agent の期待に合う。')
    # --- read by the convention, predicted abstain: the predicate type is not one of the two the table reads
    for A, v, vp, O, C, v2, v2p, why in (
            ('兄', '書く', '書いた', '手紙', '母', '読む', '読んだ', 'P_CREATE'),
            ('母', '作る', '作った', '料理', '姉', '持つ', '持った', 'P_CREATE'),
            ('姉', '描く', '描いた', '絵', '弟', '見る', '見た', 'P_CREATE'),
            ('母', '買う', '買った', '花', '姉', '見る', '見た', 'P_GIVE'),
            ('兄', '歌う', '歌った', '歌', '姉', '聞く', '聞いた', 'WORK（述語の型でない）'),
            ('先生', '読む', '読んだ', '本', '弟', '持つ', '持った', '推定（生成）の述語'),
            ('弟', '飲む', '飲んだ', '薬', '母', '買う', '買った', 'P_CONSUME')):
        text = '%sが%s%sを%sが%s。' % (A, vp, O, C, v2p)
        read(text, cl(v, {'agent': A, 'patient': O}), cl(v2, {'agent': C, 'patient': O}), O, '関係節の述語が表の外の型: ' + why, 'abstain', 'HEAD_ROLE_UNDETERMINED:frame_not_read',
             '規約どおりの読みは一意だが、型の表は P_MOVE と P_COMMUNICATE だけを読む。')
    # --- read by the convention, predicted abstain: a derived-verb suspect (the shimo-ichidan gate of K63) in a clause
    for A, B, v, vp, H, C, v2, v2p in (
            ('先生', '生徒', '教える', '教えた', '歌', '弟', '歌う', '歌った'),
            ('母', '弟', '伝える', '伝えた', '人', '兄', '呼ぶ', '呼んだ'),
            ('兄', None, '褒める', '褒めた', '生徒', '母', '待つ', '待った'),
            ('母', None, '開ける', '開けた', '窓', '弟', '見る', '見た')):
        text = ('%sが%sに%s%sを%sが%s。' % (A, B, vp, H, C, v2p)) if B else ('%sが%s%sを%sが%s。' % (A, vp, H, C, v2p))
        c0 = cl(v, {'agent': A, 'recipient': B, 'patient': H}) if B else cl(v, {'agent': A, 'patient': H})
        read(text, c0, cl(v2, {'agent': C, 'patient': H}), H, '下一段の述語（派生の疑いの門）', 'abstain', 'CLAUSE_FORM_NOT_READ',
             '規約どおりの読みは一意。下一段の動詞は 派生（可能・自発）の疑いの門で全部止まる。')
    # --- read by the convention, predicted abstain: the head's type
    for A, B, vp, v, H, C, v2p, v2, why in (
            ('母', '弟', '話した', '話す', '部屋', '兄', '見た', '見る', 'PLACE は patient の期待の外（mismatch）'),
            ('父', '兄', '話した', '話す', '医者', '母', '呼んだ', '呼ぶ', '割れた型に PLACE がある'),
            ('兄', '弟', '頼んだ', '頼む', '荷物', '母', '持った', '持つ', '型が UNPLACED'),
            ('母', '弟', '話した', '話す', '知らせ', '兄', '聞いた', '聞く', '型が推定（生成）'),
            ('兄', '弟', '話した', '話す', '家', '母', '見た', '見る', '割れた型に PLACE がある')):
        text = '%sが%sに%s%sを%sが%s。' % (A, B, vp, H, C, v2p)
        read(text, cl(v, {'agent': A, 'recipient': B, 'patient': H}), cl(v2, {'agent': C, 'patient': H}), H, '主辞の型: ' + why, 'abstain', 'HEAD_ROLE_UNDETERMINED:type',
             '規約どおりの読みは一意。主辞の型が腕の期待に合わない・決まらないので、型だけでは腕を決めない。')
    # --- read by the convention, predicted abstain: a path with two phrases that are not anchored (alternative cut)
    read('東京から大阪へ行った兄を母が呼んだ。', cl('行く', {'agent': '兄', 'source': '東京', 'goal': '大阪'}), cl('呼ぶ', {'agent': '母', 'patient': '兄'}), '兄',
         'P_MOVE: source と goal が埋まり agent が空', 'abstain', 'CLAUSE_SCOPE_AMBIGUOUS:alternative_cut',
         '規約どおりの読みは一意だが、東京から を主節の側に付ける切り方が構造の上で成り立つ（が・を の重なりで壊れない）ので棄権する。')
    assert len(rows) == 30, len(rows)

    # --- abstain: the path does not decide
    def no(text, why, w3, construction, note):
        add('abstain', text, EXP_NO, construction, 'abstain', w3, note, why)
    for text in ('駅で母が弟に話した人を兄が呼んだ。', '庭で兄が先生に言った生徒を母が待った。', '三時に父が祖母に話した犬を兄が見た。', '学校で姉が母に頼んだ薬を弟が飲んだ。',
                 '弟に歌を頼んだ人を兄が呼んだ。'):
        no(text, 'alternative_cut', 'CLAUSE_SCOPE_AMBIGUOUS:alternative_cut', '別の切り方: 関係節の先頭が が・を の句でない', '先頭の句（駅で・庭で・三時に・弟に）を主節の側に付ける切り方が成り立つ。')
    for text in ('母は弟に話した人を兄が呼んだ。', '兄は先生に言った生徒を母が待った。', '姉は妹に頼んだ友達を先生が呼んだ。'):
        no(text, 'topic_in_relative', 'CLAUSE_SCOPE_AMBIGUOUS:topic_in_relative', '主題が関係節の区間にある', 'X は が関係節の主題か主節の主題か決まらない。')
    for text in ('母が弟に話した問題を兄が聞いた。', '兄が先生に言った約束を母が待った。', '姉が妹に頼んだ質問を先生が待った。', '父が兄に話した手紙を母が読んだ。',
                 '母が弟に話した理由を兄が聞いた。'):
        no(text, 'outer_relation_type', 'HEAD_ROLE_UNDETERMINED:outer_relation_type', '外の関係の型（ABSTRACT・EVENT_ACT・STATE_PROPERTY）', '内容節・外の関係（〜という問題）と、欠けた腕に入る名詞の区別がつかない。')
    for text in ('母が話した人を兄が呼んだ。', '兄が言った生徒を母が待った。', '姉が頼んだ友達を先生が呼んだ。'):
        no(text, 'empty_arms=2', 'HEAD_ROLE_UNDETERMINED:empty_arms=2', '空いている腕が 2 つ（patient と に の腕）', '主辞がどちらの腕か型では決まらない。')
    for text in ('母が人を弟に話した部屋を兄が見た。', '兄が本を先生に言った場所を母が見た。'):
        no(text, 'empty_arms=0', 'HEAD_ROLE_UNDETERMINED:empty_arms=0', '空いている腕が 0（agent・patient・に が全部埋まっている）', '主辞を入れる腕が無い（外の関係）。')
    for text in ('母が薬を頼んだ人を兄が呼んだ。', '姉が本を頼んだ友達を先生が呼んだ。'):
        no(text, 'undecided_arm', 'HEAD_ROLE_UNDETERMINED:undecided_arm', '空いている腕が に の腕（決まっていない腕）だけ', 'に の腕の役割（recipient か source か）は表が決めない。')
    for text in ('兄が東京から歩いた町を弟が見た。', '母が大阪から走った村を弟が見た。'):
        no(text, 'adjunct_tie', 'HEAD_ROLE_UNDETERMINED:adjunct_tie', '付加の腕（place）との同点', '主辞が goal か 場所の付加（で の腕）か型では決まらない。')
    for text in ('母が弟に話した兄の友達を先生が呼んだ。', '母が弟に話した三人の客を兄が呼んだ。'):
        no(text, 'head_not_simple', 'HEAD_ROLE_UNDETERMINED:head_not_simple', '主辞が単純な名詞句でない（の・数詞を含む）', '主辞の句の型が主辞の 1 語で決まらない。')
    for text in ('兄が先生に言った後に母が来た。', '母が弟に話した時に兄が来た。'):
        no(text, 'not_listed', 'CLAUSE_SCOPE_NOT_LISTED', '一覧外の形（後・時 の型）', '時間の名詞が主辞の連体修飾は関係節ではない。')
    no('母が弟に話した人を呼べ。', 'imperative', 'CLAUSE_FORM_NOT_READ:imperative', '形の門: 命令形', '命令形の節を含む文は読まない。')
    no('母が弟に話した人を兄が呼んだか。', 'question', 'CLAUSE_FORM_NOT_READ:question', '形の門: 疑問', '疑問の文は読まない。')
    for text in ('母が弟に話した人が歩いた。', '兄が先生に言った生徒が走った。'):
        no(text, 'object', 'ELLIPSIS_UNDETERMINED:object', '主節の目的語の省略', '主節の 歩く・走る に目的語が無く、ほかの節に別の名詞がある（先行詞の候補）。')
    assert len(rows) == 60, len(rows)
    return rows


# ---------------------------------------------------------------------------------------------------------------------------------
# connective sentences (60): 10 forms x (3 read + 3 abstain)
# ---------------------------------------------------------------------------------------------------------------------------------
def connective_rows():
    rows = []
    P = 'W3B3-CON'

    def add(behavior, text, expect, cut, construction, entry, w3, note, why=None):
        rows.append(row(P, len(rows) + 1, behavior, text, expect, cut, construction, entry, w3, 'w3b3_connective', note, None, why))

    def read(text, cut, rel, c0, c1, entry='read', w3='READ', note='', construction=None):
        add('read', text, exp_read([c0, c1], [{'type': rel, 'from': 0, 'to': 1}]), cut, construction or ('接続: ' + cut), entry, w3, note or '節ごとに入口が読み、閉じた接続語から関係の型が決まる。')

    def no(text, cut, why, w3, note):
        add('abstain', text, EXP_NO, cut, '棄権: ' + why, 'abstain', w3, note, why)
    T = lambda pred, roles, tense='past': cl(pred, roles, tense)
    # ので (cause)
    read('兄が本を読んだので、弟が歌を歌った。', 'ので', 'cause', T('読む', {'agent': '兄', 'patient': '本'}), T('歌う', {'agent': '弟', 'patient': '歌'}))
    read('母が兄を叱ったので、兄が帰った。', 'ので', 'cause', T('叱る', {'agent': '母', 'patient': '兄'}), T('帰る', {'agent': '兄'}))
    read('姉が窓を開けたので、母が戸を閉めた。', 'ので', 'cause', T('開ける', {'agent': '姉', 'patient': '窓'}), T('閉める', {'agent': '母', 'patient': '戸'}),
         'abstain', 'CLAUSE_FORM_NOT_READ', '規約どおりの読みは一意。下一段の動詞は派生の疑いの門で止まる。')
    no('駅で兄が本を読んだので、弟が歌を歌った。', 'ので', 'alternative_cut', 'CLAUSE_SCOPE_AMBIGUOUS:alternative_cut', '文頭の駅でが どちらの節に付くか構造で決まらない。')
    no('妹が転んだので、姉が起こした。', 'ので', 'object', 'ELLIPSIS_UNDETERMINED:object', '起こす の目的語が省略されていて、先行詞の候補（妹）が入力にある。')
    no('弟が帰ったので、姉が手紙を書け。', 'ので', 'imperative', 'CLAUSE_FORM_NOT_READ:imperative', '命令形の節。')
    # から (cause)
    read('弟が薬を飲んだから、兄が来た。', 'から', 'cause', T('飲む', {'agent': '弟', 'patient': '薬'}), T('来る', {'agent': '兄'}))
    read('母が絵を描いたから、父が起きた。', 'から', 'cause', T('描く', {'agent': '母', 'patient': '絵'}), T('起きる', {'agent': '父'}))
    read('兄が弟を叩いたから、母が兄を叱った。', 'から', 'cause', T('叩く', {'agent': '兄', 'patient': '弟'}), T('叱る', {'agent': '母', 'patient': '兄'}))
    no('兄が来たから、弟は帰った。', 'から', 'topic_position', 'CLAUSE_SCOPE_AMBIGUOUS:topic_position', '主節の側に は の句がある。')
    no('兄が来たから、弟が帰りましたか。', 'から', 'question', 'CLAUSE_FORM_NOT_READ:question', '疑問の文。')
    no('兄が来たから、しかし弟が帰った。', 'から', 'connective_outside_cut', 'CLAUSE_FORM_NOT_READ:connective_outside_cut', '切れ目の外に接続詞がある。')
    # が (contrast)
    read('兄が本を読んだが、弟が歌を歌った。', 'が', 'contrast', T('読む', {'agent': '兄', 'patient': '本'}), T('歌う', {'agent': '弟', 'patient': '歌'}))
    read('先生が生徒を許したが、母が兄を叱った。', 'が', 'contrast', T('許す', {'agent': '先生', 'patient': '生徒'}), T('叱る', {'agent': '母', 'patient': '兄'}))
    read('姉が来たが、弟が帰った。', 'が', 'contrast', T('来る', {'agent': '姉'}), T('帰る', {'agent': '弟'}))
    no('兄が駅に着いたが、弟が帰った。', 'が', 'goal', 'ELLIPSIS_UNDETERMINED:goal', '帰る の行き先が省略されていて、先行詞の候補（駅）が入力にある。')
    no('兄が来たが、帰った。', 'が', 'alternative_cut', 'CLAUSE_SCOPE_AMBIGUOUS:alternative_cut', '主節に主語が無い。兄が を主節の側に付ける切り方が成り立つ。')
    no('兄が静かに来たが、弟が帰らなかった。', 'が', 'unread_clause', 'CLAUSE_UNREAD', '節の中の副詞（静かに）を入口が読まない。')
    # けれど (contrast)
    read('兄が弟を呼んだけれど、弟が来た。', 'けれど', 'contrast', T('呼ぶ', {'agent': '兄', 'patient': '弟'}), T('来る', {'agent': '弟'}))
    read('母が花を買ったけど、姉が絵を描いた。', 'けれど', 'contrast', T('買う', {'agent': '母', 'patient': '花'}), T('描く', {'agent': '姉', 'patient': '絵'}))
    read('父が起きたけれども、祖父が座った。', 'けれど', 'contrast', T('起きる', {'agent': '父'}), T('座る', {'agent': '祖父'}))
    no('庭で母が絵を描いたけれど、姉が歌を歌った。', 'けれど', 'alternative_cut', 'CLAUSE_SCOPE_AMBIGUOUS:alternative_cut', '文頭の庭でが どちらの節に付くか構造で決まらない。')
    no('母が弟に話したけれど、兄が帰った。', 'けれど', 'object', 'ELLIPSIS_UNDETERMINED:object', '話す の目的語が省略されていて、先行詞の候補（兄）が入力にある。')
    no('兄が本を読んでいるけれど、弟が歌を歌った。', 'けれど', 'aspect', 'CLAUSE_FORM_NOT_READ', 'ている の節。入口の単独の読みは語尾の門が止める。')
    # と (condition; the quotation と is a separate gate)
    read('兄が来ると、弟が帰る。', 'と', 'condition', T('来る', {'agent': '兄'}, 'nonpast'), T('帰る', {'agent': '弟'}, 'nonpast'))
    read('姉が着くと、母が座る。', 'と', 'condition', T('着く', {'agent': '姉'}, 'nonpast'), T('座る', {'agent': '母'}, 'nonpast'))
    read('先生が入ると、生徒が立つ。', 'と', 'condition', T('入る', {'agent': '先生'}, 'nonpast'), T('立つ', {'agent': '生徒'}, 'nonpast'))
    no('兄が来ると、弟が帰った。', 'と', 'condition_past_main', 'RELATION_TYPE_UNDETERMINED:condition_past_main', '主節が過去: 条件でなく発見・継起とも読める。')
    no('弟が帰ると、先生が話す。', 'と', 'quote_possible', 'RELATION_TYPE_UNDETERMINED:quote_possible', '主節の述語が伝達の動詞: 引用の と と区別できない。')
    no('姉が戻ると、母が見る。', 'と', 'quote_possible', 'RELATION_TYPE_UNDETERMINED:quote_possible', '主節の述語の型が知覚（P_PERCEIVE）: 引用の と と区別できない。')
    # なら (condition, tense null)
    read('兄が来るなら、弟が帰る。', 'なら', 'condition', T('来る', {'agent': '兄'}, None), T('帰る', {'agent': '弟'}, 'nonpast'))
    read('姉が戻るなら、母が着く。', 'なら', 'condition', T('戻る', {'agent': '姉'}, None), T('着く', {'agent': '母'}, 'nonpast'))
    read('父が起きるなら、祖父が座る。', 'なら', 'condition', T('起きる', {'agent': '父'}, None), T('座る', {'agent': '祖父'}, 'nonpast'))
    no('兄が来るなら、弟が帰った。', 'なら', 'condition_past_main', 'RELATION_TYPE_UNDETERMINED:condition_past_main', '主節が過去。')
    no('兄が来るなら、母が見る。', 'なら', 'object', 'ELLIPSIS_UNDETERMINED:object', '見る の目的語が省略されていて、先行詞の候補（兄）が入力にある。')
    no('兄が来るなら、弟は帰る。', 'なら', 'topic_position', 'CLAUSE_SCOPE_AMBIGUOUS:topic_position', '主節の側に は の句がある。')
    # ば (condition, non-finite)
    read('兄が来れば、弟が帰る。', 'ば', 'condition', T('来る', {'agent': '兄'}, None), T('帰る', {'agent': '弟'}, 'nonpast'))
    read('母が戻れば、姉が着く。', 'ば', 'condition', T('戻る', {'agent': '母'}, None), T('着く', {'agent': '姉'}, 'nonpast'))
    read('弟が入れば、兄が立つ。', 'ば', 'condition', T('入る', {'agent': '弟'}, None), T('立つ', {'agent': '兄'}, 'nonpast'))
    no('兄が来なければ、弟が帰る。', 'ば', 'aux_in_nonfinite', 'CLAUSE_FORM_NOT_READ:aux_in_nonfinite', '切れ目の直前が助動詞（なけれ）: 非定形の節を書き直さない。')
    no('兄が来れば、弟が帰った。', 'ば', 'condition_past_main', 'RELATION_TYPE_UNDETERMINED:condition_past_main', '主節が過去。')
    no('駅で兄が来れば、弟が帰る。', 'ば', 'alternative_cut', 'CLAUSE_SCOPE_AMBIGUOUS:alternative_cut', '文頭の駅でが どちらの節に付くか構造で決まらない。')
    # たら (condition, non-finite)
    read('兄が着いたら、弟が帰る。', 'たら', 'condition', T('着く', {'agent': '兄'}, None), T('帰る', {'agent': '弟'}, 'nonpast'))
    read('姉が戻ったら、母が来る。', 'たら', 'condition', T('戻る', {'agent': '姉'}, None), T('来る', {'agent': '母'}, 'nonpast'))
    read('弟が転んだら、兄が起きる。', 'たら', 'condition', T('転ぶ', {'agent': '弟'}, None), T('起きる', {'agent': '兄'}, 'nonpast'))
    no('兄が着いたら、弟が帰った。', 'たら', 'condition_past_main', 'RELATION_TYPE_UNDETERMINED:condition_past_main', '主節が過去: 条件でなく発見・継起。')
    no('兄が着いたら、窓を閉めろ。', 'たら', 'imperative', 'CLAUSE_FORM_NOT_READ:imperative', '命令形の節。')
    no('兄が着いたら、弟が帰るか。', 'たら', 'question', 'CLAUSE_FORM_NOT_READ:question', '疑問の文。')
    # ても (concession, non-finite)
    read('兄が来ても、弟が帰る。', 'ても', 'concession', T('来る', {'agent': '兄'}, None), T('帰る', {'agent': '弟'}, 'nonpast'))
    read('姉が戻っても、母が座る。', 'ても', 'concession', T('戻る', {'agent': '姉'}, None), T('座る', {'agent': '母'}, 'nonpast'))
    read('先生が入っても、生徒が立った。', 'ても', 'concession', T('入る', {'agent': '先生'}, None), T('立つ', {'agent': '生徒'}, 'past'))
    no('兄が褒められても、弟が帰る。', 'ても', 'aux_in_nonfinite', 'CLAUSE_FORM_NOT_READ:aux_in_nonfinite', '切れ目の直前が助動詞（られ）。')
    no('兄が歌っても、弟が歩いた。', 'ても', 'object', 'ELLIPSIS_UNDETERMINED:object', '歌う の目的語が省略されていて、先行詞の候補（弟）が入力にある。')
    no('兄が来てもいい。', 'ても', 'permission', 'W3B3_NOT_TRIGGERED', 'ても いい は許可で切れ目にしない（述語のまとまりは 1 つ）。')
    # ながら (simultaneous, non-finite)
    read('兄が本を読みながら、弟が歌を歌った。', 'ながら', 'simultaneous', T('読む', {'agent': '兄', 'patient': '本'}, None), T('歌う', {'agent': '弟', 'patient': '歌'}))
    read('母が絵を描きながら、姉が歌を歌った。', 'ながら', 'simultaneous', T('描く', {'agent': '母', 'patient': '絵'}, None), T('歌う', {'agent': '姉', 'patient': '歌'}))
    read('先生が本を読みながら、生徒が薬を飲んだ。', 'ながら', 'simultaneous', T('読む', {'agent': '先生', 'patient': '本'}, None), T('飲む', {'agent': '生徒', 'patient': '薬'}))
    no('兄が歌いながら、弟は歩いた。', 'ながら', 'topic_position', 'CLAUSE_SCOPE_AMBIGUOUS:topic_position', '主節の側に は の句がある。')
    no('母が歌いながら、姉が帰った。', 'ながら', 'object', 'ELLIPSIS_UNDETERMINED:object', '歌う の目的語が省略されていて、先行詞の候補（姉）が入力にある。')
    no('兄が静かに歌いながら、弟が歌を歌った。', 'ながら', 'unread_clause', 'CLAUSE_UNREAD', '節の中の副詞（静かに）を入口が読まない。')
    assert len(rows) == 60, len(rows)
    return rows


# ---------------------------------------------------------------------------------------------------------------------------------
# て / 連用中止 (30): the edge is TE_UNDETERMINED / PARALLEL_UNDETERMINED in the diagnosis only; the entry abstains
# ---------------------------------------------------------------------------------------------------------------------------------
def parallel_rows():
    rows = []
    P = 'W3B3-PAR'
    TE_TYPES = ['sequence', 'manner', 'cause']

    def read(text, cut, c0, c1, types, edge, note):
        structure = {'clauses': [c0, c1], 'edges': [{'type': edge, 'from': 0, 'to': 1}]}
        rows.append(row(P, len(rows) + 1, 'read', text, exp_read([c0, c1], [{'type': types, 'from': 0, 'to': 1}]), cut, '%s: 2 節と辺 %s' % (cut, edge), 'abstain',
                        'RELATION_TYPE_UNDETERMINED:' + edge, 'w3b3_parallel', note, structure, None))

    def no(text, cut, why, w3, note):
        rows.append(row(P, len(rows) + 1, 'abstain', text, EXP_NO, cut, '棄権: ' + why, 'abstain', w3, 'w3b3_parallel', note, None, why))
    N = lambda pred, roles: cl(pred, roles, None)
    P2 = lambda pred, roles: cl(pred, roles, 'past')
    te = '継起・手段・付帯（原因）の区別がつかない（TE_UNDETERMINED）。入口では棄権し、辺は診断にだけ書く。'
    for text, a, b in (
            ('兄が本を読んで、弟が歌を歌った。', N('読む', {'agent': '兄', 'patient': '本'}), P2('歌う', {'agent': '弟', 'patient': '歌'})),
            ('母が絵を描いて、姉が手紙を書いた。', N('描く', {'agent': '母', 'patient': '絵'}), P2('書く', {'agent': '姉', 'patient': '手紙'})),
            ('先生が本を読んで、生徒が薬を飲んだ。', N('読む', {'agent': '先生', 'patient': '本'}), P2('飲む', {'agent': '生徒', 'patient': '薬'})),
            ('兄が来て弟が帰った。', N('来る', {'agent': '兄'}), P2('帰る', {'agent': '弟'})),
            ('姉が着いて母が座った。', N('着く', {'agent': '姉'}), P2('座る', {'agent': '母'})),
            ('父が起きて、祖父が立った。', N('起きる', {'agent': '父'}), P2('立つ', {'agent': '祖父'})),
            ('弟が転んで、兄が来た。', N('転ぶ', {'agent': '弟'}), P2('来る', {'agent': '兄'})),
            ('母が戻って、姉が着いた。', N('戻る', {'agent': '母'}), P2('着く', {'agent': '姉'}))):
        read(text, 'て', a, b, TE_TYPES, 'TE_UNDETERMINED', te)
    no('兄が読みたくて、弟が歌った。', 'て', 'aux_in_nonfinite', 'CLAUSE_FORM_NOT_READ:aux_in_nonfinite', '切れ目の直前が助動詞（たく）。')
    no('兄が来てから、弟が帰った。', 'て', 'not_listed', 'CLAUSE_SCOPE_NOT_LISTED', 'てから は一覧外の形。')
    no('兄が本を読んでいて、弟が歌った。', 'て', 'aspect', 'CLAUSE_FORM_NOT_READ', 'ている の節。')
    no('兄が来て、弟が帰って、母が座った。', 'て', 'three_clauses', 'W3B3_NOT_TRIGGERED:groups=3', '述語のまとまりが 3 つ。')
    no('駅で兄が来て、弟が帰った。', 'て', 'alternative_cut', 'CLAUSE_SCOPE_AMBIGUOUS:alternative_cut', '文頭の駅でが どちらの節に付くか構造で決まらない。')
    no('兄が来て、弟が帰れ。', 'て', 'imperative', 'CLAUSE_FORM_NOT_READ:imperative', '命令形の節。')
    no('兄が来て、弟は帰った。', 'て', 'topic_position', 'CLAUSE_SCOPE_AMBIGUOUS:topic_position', '主節の側に は の句がある。')
    cont = '連用中止（PARALLEL_UNDETERMINED）。継起・並列・原因の区別がつかない。入口では棄権し、辺は診断にだけ書く。'
    for text, a, b in (
            ('兄が本を読み、弟が歌を歌った。', N('読む', {'agent': '兄', 'patient': '本'}), P2('歌う', {'agent': '弟', 'patient': '歌'})),
            ('母が絵を描き、姉が手紙を書いた。', N('描く', {'agent': '母', 'patient': '絵'}), P2('書く', {'agent': '姉', 'patient': '手紙'})),
            ('先生が本を読み、生徒が薬を飲んだ。', N('読む', {'agent': '先生', 'patient': '本'}), P2('飲む', {'agent': '生徒', 'patient': '薬'})),
            ('兄が着き、弟が帰った。', N('着く', {'agent': '兄'}), P2('帰る', {'agent': '弟'})),
            ('姉が戻り、母が座った。', N('戻る', {'agent': '姉'}), P2('座る', {'agent': '母'})),
            ('父が起き、祖父が立った。', N('起きる', {'agent': '父'}), P2('立つ', {'agent': '祖父'})),
            ('弟が転び、兄が来た。', N('転ぶ', {'agent': '弟'}), P2('来る', {'agent': '兄'}))):
        read(text, '並列', a, b, ['sequence'], 'PARALLEL_UNDETERMINED', cont)
    no('駅で兄が本を読み、弟が歌を歌った。', '並列', 'alternative_cut', 'CLAUSE_SCOPE_AMBIGUOUS:alternative_cut', '文頭の駅でが どちらの節に付くか構造で決まらない。')
    no('兄が来、弟が帰り、母が座った。', '並列', 'three_clauses', 'W3B3_NOT_TRIGGERED:groups=3', '述語のまとまりが 3 つ。')
    no('兄が本を読み、弟は歌を歌った。', '並列', 'topic_position', 'CLAUSE_SCOPE_AMBIGUOUS:topic_position', '主節の側に は の句がある。')
    no('兄が本を読み、弟が歌を歌え。', '並列', 'imperative', 'CLAUSE_FORM_NOT_READ:imperative', '命令形の節。')
    no('兄が静かに本を読み、弟が歌を歌った。', '並列', 'unread_clause', 'CLAUSE_UNREAD', '節の中の副詞（静かに）を入口が読まない。')
    no('兄が本を読み、しかし弟が歌を歌った。', '並列', 'connective_outside_cut', 'CLAUSE_FORM_NOT_READ:connective_outside_cut', '切れ目の外に接続詞がある。')
    no('兄が本を読み、弟が歌を歌いましたか。', '並列', 'question', 'CLAUSE_FORM_NOT_READ:question', '疑問の文。')
    no('兄がすぐ近くの店に行き、弟が帰った。', '並列', 'unread_clause', 'CLAUSE_UNREAD', '節の中の名詞句にかかる副詞（すぐ近くの）を入口が読まない。')
    assert len(rows) == 30, len(rows)
    return rows


# ---------------------------------------------------------------------------------------------------------------------------------
# W1-a4's misreads (review rounds 1-3): every sentence is one the new path must not read
# ---------------------------------------------------------------------------------------------------------------------------------
W1A4 = (
    ('r1 必須 1（否定の中の副詞）', ('兄は静かに本を読まなかった。', '兄がゆっくり歩かなかった。', '弟は丁寧に字を書かなかった。', '母はそっと窓を閉めなかった。', '兄がすぐ帰らなかった。',
                              '兄が慎重にドアを開けなかった。', '兄がとても喜ばなかった。', '兄が来ないので、母がすぐ帰らなかった。', '母が簡単に窓を開けなかった。')),
    ('r1 必須 2（名詞句にかかる副詞）', ('兄がすぐ近くの店に行った。', '兄がすぐ隣の部屋に入った。', '母がすぐ前の店で本を買った。', '兄がとても近くの店に行った。')),
    ('r1 必須 3（意志動詞＋ように）', ('手紙を書くように、本を読んだ。', '先生が教えるように、生徒が練習した。', '兄が歩くように、弟が歩いた。')),
    ('r1 必須 4（命令形）', ('窓を開けたら、戸を閉めろ。', '窓を開けるなら、戸を閉めよ。', '窓を開けたので、戸を閉めろ。', '兄が来たので、母が料理を作れ。')),
    ('r1 必須 6・8（類の外し・主題の埋め）', ('兄がとても喜んだ。', '本は兄が買ったので、読んだ。', '客は店員が案内したので、席に座った。')),
    ('r2 必須 3（共有された斜格の脱落）', ('兄は駅に行ったが、弟は行かなかった。', '兄は駅に行ったが、弟は着かなかった。', '兄は東京から来たが、弟は来なかった。', '兄が公園で遊んだが、弟は遊ばなかった。',
                              '兄は駅に着いたが、弟は着かなかった。')),
    ('r3 必須 1（と の引用）', ('兄は来ると、母に言う。', '兄は行くと、先生に話す。', '弟は帰ると、姉に伝える。', '兄は来ると、母に答える。', '兄は勝つと、弟に言う。', '兄が来ると、母が言う。',
                        '兄は来ると母に言う。', '兄が来ると、母が書く。')),
    ('r3 必須 2（目的語の省略）', ('姉が泣いたから、兄が慰めた。', '弟が転んだので、兄が助けた。', '先生が来たので、生徒が迎えた。', '犬が吠えたので、兄が叱った。', '兄が歌ったので、弟が褒めた。',
                          '母が呼んだので、兄が答えた。', '母が兄を呼んだので、兄が答えた。')),
    ('r3 必須 3（部分の外の接続詞）', ('兄が大胆に、しかし慎重に進んだ。', '兄が静かに、そして丁寧に皿を洗った。', '兄が静かに、または丁寧に皿を洗った。', '兄が静かに、でも丁寧に皿を洗った。')),
    ('r3 必須 2 の変種（正しく棄権した文として挙がったもの）', ('兄は東京の駅に行ったが、弟は行かなかった。', '兄は駅へ行ったが、弟は行かなかった。', '兄はゆっくり駅に行ったが、弟は行かなかった。',
                                                    '兄は弟と公園に行ったが、姉は行かなかった。')),
    ('r3 必須 1 の探りの文（レビュー本文に挙がるが付録 A に無かったもの。手順 1 で足した）', ('兄は来ると、母は思う。', '兄がゆっくり、また静かに歩いた。')),
)


def w1a4_rows():
    rows = []
    for source, texts in W1A4:
        for t in texts:
            rows.append(row('W3B3-W1A4', len(rows) + 1, 'abstain', t, EXP_NO, 'w1a4', 'W1-a4 のレビューの誤読の文', 'abstain', 'ABSTAIN', 'review-impl/W1-a4 %s' % source,
                            'W1-a4 の新しい経路が読んで誤読・不完全になった文。W3-b3 の新しい経路は読まない（基点でも棄権）。', None, 'w1a4_misread'))
    return rows


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=str(HERE))
    a = ap.parse_args()
    out = Path(a.out)
    for name, rows in (('relative', relative_rows()), ('connective', connective_rows()), ('parallel', parallel_rows()), ('w1a4', w1a4_rows())):
        (out / ('w3b3_%s.jsonl' % name)).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        print(name, len(rows), 'read=%d abstain=%d' % (sum(r['behavior'] == 'read' for r in rows), sum(r['behavior'] == 'abstain' for r in rows)))


if __name__ == '__main__':
    main()
