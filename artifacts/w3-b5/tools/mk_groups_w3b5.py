def role_only(w):
    a = C.r8_answer(w)
    return bool(a.get('decided_by')) and all(x.startswith('role@') for x in a['decided_by'])


# The rows of the data, group by group (exec'd by mk_data_w3b5.py in its namespace: `add`, `C`, `ag`, `must_de`, `must_ni`, ... are defined there).
# Every `expect` and `w3b5_expect` below is the DESIGN of the row (the role the phrase has; the registered diagnosis), written before any run with a placement.

# ================================================================================================================================================
# DE (the particle で): place / instrument / cause
# ================================================================================================================================================
DE_LABEL = {'absent': 'frame_generated が無い（r8 に行の無い seed の語）', 'r8': 'r8 の枠（そのまま）'}

# --- DEPLACE-R: the predicate's r8 frame HOLDS で:PLACE; the filler is a PLACE word of r8 with evidence that is not role@ only (gate 5), the reader leaves で ambiguous (U3) ---
de_intr = [('校庭', 'あそぶ'), ('校庭', 'おどる'), ('校庭', '騒ぐ'), ('校庭', '昼寝する'), ('校庭', '活躍する'), ('ホテル', '勤務する'), ('ホテル', '仕事する'), ('ホテル', '生活する'),
           ('ホテル', '休憩する'), ('ホテル', '過ごす'), ('ホテル', '待ち合わせする'), ('神社', '修行する'), ('神社', '踊る'), ('神社', '待ち合わせする'), ('神社', '会合する'),
           ('交差点', '待ち合わせする'), ('交差点', '騒ぐ'), ('国道', 'ドライブする'), ('国道', '営業する'), ('歩道', '寝転がる'), ('歩道', '休憩する'), ('山頂', '乾杯する'),
           ('山頂', 'キャンプする'), ('山頂', '昼寝する'), ('校舎', '勤務する'), ('校舎', '修行する'), ('民宿', '過ごす'), ('民宿', '仕事する'), ('教会', '会合する'),
           ('教会', '乾杯する'), ('テニスコート', '活躍する'), ('テニスコート', '休憩する'), ('銭湯', '休憩する'), ('銭湯', '勤務する'), ('銭湯', '昼寝する'),
           ('老人ホーム', '勤務する'), ('老人ホーム', '生活する'), ('農道', 'ドライブする'), ('釣り堀', '過ごす')]
for i, (place, verb) in enumerate(de_intr):
    a_ = ag(i); p = C.past(verb)
    assert C.noun_check(place, ('PLACE',), adjunct=True), place
    add('DEPLACE', 'R', '%sが%sで%s。' % (a_, place, p), verb, 'P_ACT', 'r8', 'で', 'de_place', 'agent:が:PERSON + place:で:PLACE（述語の r8 の枠が で:PLACE を持つ）',
        {a_: 'r8', place: 'r8'}, C.expect_read(verb, {'agent': a_, 'place': place}, must_de(a_, place)), 'READ',
        'r8 では述語は estimated（ここでは direct の NOT_CONFIRMED として扱う）。充填物 %s は r8 の direct の PLACE（role@ だけでない）。' % place)

de_tr = [('教会', '演奏する', '曲', 'P_ACT'), ('老人ホーム', '演奏する', '楽器', 'P_ACT'), ('神社', '演奏する', '音楽', 'P_ACT'), ('校庭', '運転する', 'トラック', 'P_ACT'),
         ('農道', '運転する', 'トラック', 'P_ACT'), ('山頂', '放牧する', '牛', 'P_ACT'), ('校庭', '放牧する', '羊', 'P_ACT'), ('農道', '放牧する', '馬', 'P_ACT'),
         ('校庭', '撮影する', '映像', 'P_CREATE'), ('神社', '撮影する', '写真', 'P_CREATE'), ('教会', '撮影する', '動画', 'P_CREATE'), ('山頂', '撮影する', '写真', 'P_CREATE'),
         ('銭湯', '撮影する', '映像', 'P_CREATE'), ('民宿', '栽培する', '野菜', 'P_CREATE'), ('校庭', '栽培する', '花', 'P_CREATE'), ('農道', '栽培する', '苗', 'P_CREATE'),
         ('老人ホーム', '栽培する', '野菜', 'P_CREATE')]
for i, (place, verb, obj, pt) in enumerate(de_tr):
    a_ = ag(i + 3); p = C.past(verb)
    assert C.noun_check(place, ('PLACE',), adjunct=True) and C.noun_check(obj, tuple(t for t in C.CP.ct.NOUN_TYPES if t not in ('TIME', 'QUANTITY', 'PLACE'))), (place, obj)
    add('DEPLACE', 'R', '%sが%sで%sを%s。' % (a_, place, obj, p), verb, pt, 'r8', 'で', 'de_place', 'agent:が + place:で:PLACE + patient:を（述語の r8 の枠が で:PLACE を持つ）',
        {a_: 'r8', place: 'r8', obj: 'r8'}, C.expect_read(verb, {'agent': a_, 'patient': obj, 'place': place}, must_de(a_, place)), 'READ',
        'r8 では述語は estimated（direct の NOT_CONFIRMED として扱う）。')

# 搭乗口で係員が旅券の写しを確認した の型（場所が先頭・主語・「X の Y」の を）
de_gate = [('教会', '係員', '楽団', '曲', '演奏する', 'P_ACT'), ('神社', '店員', '町', '写真', '撮影する', 'P_CREATE'), ('ホテル', '先生', '旅券', '写真', '撮影する', 'P_CREATE'),
           ('国道', '係員', '会社', 'トラック', '運転する', 'P_ACT'), ('校庭', '職員', '町', '楽器', '演奏する', 'P_ACT'), ('山頂', '学生', '町', '動画', '撮影する', 'P_CREATE'),
           ('老人ホーム', '係員', '学校', '曲', '演奏する', 'P_ACT'), ('民宿', '社員', '工場', '野菜', '栽培する', 'P_CREATE')]
for place, a_, x, y, verb, pt in de_gate:
    p = C.past(verb)
    add('DEPLACE', 'R', '%sで%sが%sの%sを%s。' % (place, a_, x, y, p), verb, pt, 'r8', 'で', 'de_place', 'place:で:PLACE（文頭）+ agent:が + patient:を（X の Y）',
        {a_: 'r8', place: 'r8', y: 'r8'}, C.expect_read(verb, {'agent': a_, 'patient': '%sの%s' % (x, y), 'place': place}, must_de(a_, place)), 'READ',
        '搭乗口で係員が旅券の写しを確認した の型（別の述語・別の PLACE の語）。')

# --- DEPLACE-A: refused, the で phrase is a place that the frame / the gates do not license ---
P_PRED = lambda v: v   # (readability)
NIN = ('P_ACT', 'P_CREATE', 'P_EMOTION')

# (1) frame_generated absent (a seed verb with no row in r8): the registered reason is the one of the base commit
absent_tr = [('打つ', 'P_ACT', None), ('洗う', 'P_ACT', '皿'), ('拭く', 'P_ACT', '皿'), ('押す', 'P_ACT', None), ('引く', 'P_ACT', None), ('切る', 'P_ACT', '花'), ('並べる', 'P_ACT', '皿'),
             ('遊ぶ', 'P_ACT', None), ('働く', 'P_ACT', None), ('集める', 'P_ACT', '本'), ('守る', 'P_ACT', None), ('焼く', 'P_CREATE', '魚'), ('組み立てる', 'P_CREATE', '機械'),
             ('作る', 'P_CREATE', '皿'), ('描く', 'P_CREATE', '絵'), ('書く', 'P_CREATE', '記事'), ('縫う', 'P_CREATE', '服'), ('編む', 'P_CREATE', '帽子'),
             ('驚く', 'P_EMOTION', None), ('笑う', 'P_EMOTION', None), ('泣く', 'P_EMOTION', None), ('怒る', 'P_EMOTION', None), ('喜ぶ', 'P_EMOTION', None), ('慌てる', 'P_EMOTION', None)]
for i, (verb, pt, obj) in enumerate(absent_tr):
    a_ = ag(i + 5); p = C.past(verb); place = ['校庭', 'ホテル', '神社', '交差点', '国道', '歩道', '山頂', '校舎', '民宿', '教会'][i % 10]
    text = '%sが%sで%s%s。' % (a_, place, (obj + 'を') if obj else '', p)
    nouns = {a_: 'r8', place: 'r8'}
    roles = {'agent': a_, 'place': place}
    if obj: nouns[obj] = 'r8'
    add('DEPLACE', 'A', text, verb, pt, 'absent', 'で', 'de_place', '(c) frame_generated が無い（seed の語）。で の PLACE は表に行が無い（W3-b4 の第 3 ラウンド）',
        nouns, C.EXPECT_ABSTAIN, 'PLACEMENT_PARTICLE_NOT_IN_FRAME:%s:で' % pt, '述語 %s は r8 に枠の行が無い seed の語。基点でも棄権する理由と同じ。' % verb)

# (2) the r8 frame exists and does NOT hold で:PLACE (the frame says no) -> FRAME_GENERATED_DOES_NOT_LICENSE:で
dnl = [('ごねる', 'P_ACT'), ('じゃれる', 'P_ACT'), ('かみつく', 'P_ACT'), ('いじめる', 'P_ACT'), ('いどむ', 'P_ACT'), ('さわる', 'P_ACT'), ('すがる', 'P_ACT'),
       ('書き込む', 'P_CREATE'), ('記載する', 'P_CREATE'), ('縫いつける', 'P_CREATE'), ('敷設する', 'P_CREATE'), ('併設する', 'P_CREATE'), ('収める', 'P_CREATE'),
       ('あきれる', 'P_EMOTION'), ('じれる', 'P_EMOTION'), ('なやむ', 'P_EMOTION'), ('戸惑う', 'P_EMOTION'), ('感心する', 'P_EMOTION'), ('感謝する', 'P_EMOTION'),
       ('恐縮する', 'P_EMOTION'), ('退屈する', 'P_EMOTION'), ('おどろく', 'P_EMOTION'), ('おびえる', 'P_EMOTION')]
for i, (verb, pt) in enumerate(dnl):
    row = C.r8_frame_row(verb)
    assert row and row['ptype'] == pt and 'で' not in row['frame'], (verb, row and (row['ptype'], row['frame']))
    a_ = ag(i + 2); p = C.past(verb); place = ['校庭', 'ホテル', '神社', '交差点', '国道', '歩道', '山頂', '校舎', '民宿', '教会'][(i + 3) % 10]
    add('DEPLACE', 'A', '%sが%sで%s。' % (a_, place, p), verb, pt, 'r8', 'で', 'de_place', '(c) r8 の枠が で を持たない（DOES_NOT_LICENSE）',
        {a_: 'r8', place: 'r8'}, C.EXPECT_ABSTAIN, 'FRAME_GENERATED_DOES_NOT_LICENSE:で', 'r8 の枠 %s に で が無い。' % json.dumps(row['frame'], ensure_ascii=False))

# (3) the state of the filler: role@ only (gate 5), split, wrong type, unplaced, unknown, estimated. The predicate holds で:PLACE in its r8 frame.
bad_fill = [('搭乗口', 'PLACEMENT_SLOT_EVIDENCE_ONLY'), ('宿', 'PLACEMENT_SLOT_EVIDENCE_ONLY'), ('林', 'PLACEMENT_SLOT_EVIDENCE_ONLY'), ('森', 'PLACEMENT_SLOT_EVIDENCE_ONLY'),
            ('橋', 'PLACEMENT_SLOT_EVIDENCE_ONLY'), ('池', 'PLACEMENT_SLOT_EVIDENCE_ONLY'), ('畑', 'PLACEMENT_SLOT_EVIDENCE_ONLY'), ('屋上', 'PLACEMENT_SLOT_EVIDENCE_ONLY'),
            ('廊下', 'PLACEMENT_SLOT_EVIDENCE_ONLY'), ('玄関', 'PLACEMENT_SLOT_EVIDENCE_ONLY'),
            ('左', 'PLACEMENT_MULTIPLE'), ('東京', 'PLACEMENT_MULTIPLE'), ('本社', 'PLACEMENT_MULTIPLE'), ('石畳', 'PLACEMENT_MULTIPLE'),
            ('稽古場', 'PLACEMENT_TYPE_MISMATCH:P_ACT:で:WORK'), ('多数決', 'PLACEMENT_TYPE_MISMATCH:P_ACT:で:ABSTRACT'), ('望遠レンズ', 'PLACEMENT_UNPLACED'), ('搬出口', 'PLACEMENT_UNKNOWN'),
            ('電話口', 'PLACEMENT_ESTIMATED_GENERATED')]
bad_verbs = ['あそぶ', '勤務する', '休憩する', '過ごす', '仕事する', '生活する', '待ち合わせする', '会合する', '乾杯する', '活躍する']
for i, (w, why) in enumerate(bad_fill):
    verb = bad_verbs[i % len(bad_verbs)]
    a_ = ag(i + 1); p = C.past(verb)
    if why == 'PLACEMENT_MULTIPLE' and role_only(w): why = 'PLACEMENT_SLOT_EVIDENCE_ONLY'      # a split filler whose arms are all role@: the gate of an adjunct (5) is asked first (placement_fit)
    reason = why if ':' in why else '%s:で:%s' % (why, w)
    add('DEPLACE', 'A', '%sが%sで%s。' % (a_, w, p), verb, 'P_ACT', 'r8', 'で', 'de_place', '(d) 充填物の配置（%s）' % why.split(':')[0],
        {a_: 'r8', w: 'r8'}, C.EXPECT_ABSTAIN, reason, '充填物 %s は r8 の実物の答え。述語の r8 の枠は で:PLACE を持つが、充填物の配置が門で止まる。' % w)

# (4) the state of the predicate: estimated (r8's real state), CONFIRMED whose frame has no で
est_pred = ['あそぶ', '勤務する', '休憩する', '過ごす', '仕事する', '生活する', '騒ぐ', '踊る']
for i, verb in enumerate(est_pred):
    row = C.r8_frame_row(verb); a_ = ag(i + 4); p = C.past(verb); place = ['校庭', 'ホテル', '神社', '交差点', '国道', '歩道', '山頂', '校舎'][i]
    spec = {'top': [row['ptype']], 'namespace': 'P', 'origin': 'estimated', 'basis': 'generated', 'frame_status': 'ESTIMATED', 'frame_generated': row}
    add('DEPLACE', 'A', '%sが%sで%s。' % (a_, place, p), verb, 'P_ACT', 'r8', 'で', 'de_place', '(e) 述語は推定（r8 の実物の状態。述語の型が生成の枠だけで決まった語）',
        {a_: 'r8', place: 'r8'}, C.EXPECT_ABSTAIN, 'PLACEMENT_ESTIMATED_GENERATED:predicate:%s' % verb, 'r8 の実物: 述語 %s は estimated(generated)。型の段が述語の段で止める（門 3）。' % verb, pred_override=spec)
conf = ['あそぶ', '勤務する', '休憩する', '過ごす']
for i, verb in enumerate(conf):
    row = C.r8_frame_row(verb); a_ = ag(i + 7); p = C.past(verb); place = ['校庭', 'ホテル', '神社', '山頂'][i]
    spec = {'top': [row['ptype']], 'namespace': 'P', 'decided_by': ['gen_frame', 'role_distribution@jawiki'], 'frame_status': 'CONFIRMED', 'frame': {'を': ['ARTIFACT']}, 'frame_generated': row}
    add('DEPLACE', 'A', '%sが%sで%s。' % (a_, place, p), verb, 'P_ACT', 'r8', 'で', 'de_place', '(e) 述語は CONFIRMED で、確認済みの frame に で が無い',
        {a_: 'r8', place: 'r8'}, C.EXPECT_ABSTAIN, 'PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:P_ACT:で', 'CONFIRMED の frame は偽（を だけ）。生成の枠は r8 の行。確認済みの frame が先に狭める（W3-b2）。', pred_override=spec)

# (5) the endings that the entry reads (終止形・連用形+た・未然形+ない・なかった): read rows, polarity and tense by the ending
for i, (verb, ending, pol, tense) in enumerate([('活躍する', 'する', '+', 'nonpast'), ('活躍する', 'しなかった', '-', 'past'), ('活躍する', 'しない', '-', 'nonpast'),
                                                ('休憩する', 'する', '+', 'nonpast'), ('休憩する', 'しなかった', '-', 'past'), ('休憩する', 'しない', '-', 'nonpast'),
                                                ('勤務する', 'する', '+', 'nonpast'), ('勤務する', 'しなかった', '-', 'past'), ('生活する', 'しない', '-', 'nonpast'),
                                                ('踊る', 'らなかった', '-', 'past'), ('騒ぐ', 'がない', '-', 'nonpast'), ('過ごす', 'さなかった', '-', 'past')]):
    a_ = ag(i + 6); place = ['校庭', 'ホテル', '神社', '山頂', '銭湯', '老人ホーム', '校舎', '民宿', '教会', '国道', 'テニスコート', '交差点'][i]
    stem = verb[:-2] if verb.endswith('する') else verb[:-1]
    text = '%sが%sで%s%s。' % (a_, place, stem, ending)
    add('DEPLACE', 'R', text, verb, 'P_ACT', 'r8', 'で', 'de_place', 'agent:が + place:で:PLACE、語尾は 終止形／未然形+ない／なかった（極性と時制は語尾で決まる）',
        {a_: 'r8', place: 'r8'}, C.expect_read(verb, {'agent': a_, 'place': place}, must_de(a_, place), polarity=pol, tense=tense), 'READ', 'r8 の枠が で:PLACE を持つ述語。語尾の形は W3-b1 の 4 つのうち。')

# (6) the gates that stay: a focus particle right after the case particle (K186), voice, the ending, a derived head
gate_rows = [('でも', 'PLACEMENT_FOCUS_PARTICLE_AFTER_CASE', 'K186 の係助詞・副助詞の門（格助詞の直後の も）'), ('さえ', 'PLACEMENT_FOCUS_PARTICLE_AFTER_CASE', 'K186 の副助詞の門（さえ）'),
             ('ばかり', 'PLACEMENT_FOCUS_PARTICLE_AFTER_CASE', 'K186 の副助詞の門（ばかり）')]
for i, (particle2, why, what) in enumerate(gate_rows):
    for verb, place in (('活躍する', '校庭'), ('休憩する', 'ホテル'), ('あそぶ', '神社')):
        a_ = ag(i + 2)
        text = '%sが%s%s%s。' % (a_, place, particle2 if False else 'で' + particle2[1:] if particle2.startswith('で') else 'で' + particle2, C.past(verb))
        add('DEPLACE', 'A', text, verb, 'P_ACT', 'r8', 'で', 'de_place', '(f) 既存の門: ' + what, {a_: 'r8', place: 'r8'}, C.EXPECT_ABSTAIN, why,
            'gate: r8 の枠が で:PLACE を持ち、充填物も direct の PLACE。係助詞・副助詞の門が読みを落とす（出力の欄が無い）。')
for verb, place, ending, why in [('活躍する', '校庭', 'している', 'PLACEMENT_PREDICATE_TAIL_UNINTERPRETED'), ('活躍する', 'ホテル', 'したい', 'PLACEMENT_PREDICATE_TAIL_UNINTERPRETED'),
                                 ('活躍する', '神社', 'します', 'PLACEMENT_PREDICATE_TAIL_UNINTERPRETED'), ('休憩する', '山頂', 'している', 'PLACEMENT_PREDICATE_TAIL_UNINTERPRETED'),
                                 ('勤務する', '校舎', 'したい', 'PLACEMENT_PREDICATE_TAIL_UNINTERPRETED'), ('生活する', '民宿', 'している', 'PLACEMENT_PREDICATE_TAIL_UNINTERPRETED')]:
    a_ = ag(len(ROWS)); stem = verb[:-2]
    add('DEPLACE', 'A', '%sが%sで%s%s。' % (a_, place, stem, ending), verb, 'P_ACT', 'r8', 'で', 'de_place', '(f) 既存の門: 語尾が 4 つの形の外（%s）' % ending, {a_: 'r8', place: 'r8'},
        C.EXPECT_ABSTAIN, why, 'gate: 語尾の門（W3-b1 の表の変更記録 2）は計画の後で掛かる。')
for verb, place, why in [('こける', '校庭', 'PLACEMENT_PREDICATE_POSSIBLY_DERIVED'), ('くらす', 'ホテル', 'PLACEMENT_PREDICATE_POSSIBLY_DERIVED'), ('ふかす', '神社', 'PLACEMENT_PREDICATE_POSSIBLY_DERIVED'),
                         ('待ち合わせる', '山頂', 'PLACEMENT_PREDICATE_POSSIBLY_DERIVED'), ('涼める', '校舎', 'PLACEMENT_PREDICATE_POSSIBLY_DERIVED')]:
    a_ = ag(len(ROWS))
    add('DEPLACE', 'A', '%sが%sで%s。' % (a_, place, C.past(verb)), verb, 'P_ACT', 'r8', 'で', 'de_place', '(f) 既存の門: 述語が派生（下一段・サ行五段）の疑い', {a_: 'r8', place: 'r8'},
        C.EXPECT_ABSTAIN, why, 'gate: 派生の門（W3-b1 の表の変更記録 3）。r8 の枠は で:PLACE を持つ。')
for verb, place, text_form, why in [('騒ぐ', '校庭', '%sが%sで叱られた。', 'PLACEMENT_VOICE_NOT_ACTIVE'), ('あそぶ', 'ホテル', '%sが弟を%sで騒がせた。', 'PLACEMENT_VOICE_NOT_ACTIVE'),
                                    ('あそぶ', '神社', '%sが%sで騒がされた。', 'PLACEMENT_VOICE_NOT_ACTIVE')]:
    a_ = ag(len(ROWS)); tx = text_form % (a_, place)
    pw = {'騒ぐ': '叱る'}.get(verb)
    # the predicate of the sentence is 叱る / 騒がせる / 騒がす: the data gives the fake answer of the written predicate (a seed verb without a frame)
    written = {'%sが%sで叱られた。': '叱る', '%sが弟を%sで騒がせた。': '騒がせる', '%sが%sで騒がされた。': '騒がす'}[text_form]
    _row = C.r8_frame_row(written)
    pt = _row['ptype'] if _row else 'P_ACT'
    add('DEPLACE', 'A', tx, written, pt, 'r8' if _row else 'absent', 'で', 'de_place', '(f) 既存の門: 受身・使役（voice）', {a_: 'r8', place: 'r8', '弟': 'r8'}, C.EXPECT_ABSTAIN, why,
        'voice: 受身・使役は計画の最初の行で止まる。述語の枠は %s。' % ('r8 の行そのまま' if _row else 'seed の語で r8 に行が無い'), pred_word=written)

# ================================================================================================================================================
# DEINSTR / DECAUSE (instrument / cause take PLACE words too: the frame says で:PLACE and does not say which role it is)
# `w3b5_expect` REFUSED (docs H205): the row is refused, and no reason is registered because nothing in the design refuses it (the frame HOLDS で:PLACE and the filler is PLACE):
# a reading is a misread. 'seed:PLACE' is the optimistic fake (the filler's real r8 answer is PLACE decided by role@ evidence only, which gate 5 refuses today; with another placement it may not).
# ================================================================================================================================================
# (a) the ten sentences of W3-b4 (bundles d and c), the base commit refuses them; the predicate has no row in r8
w3b4_ten = [('兄が右で打った。', '打つ', 'P_ACT', '右', 'de_instrument', 'で=右手（instrument）'), ('兄が右で皿を洗った。', '洗う', 'P_ACT', '右', 'de_instrument', 'で=右手（instrument）'),
            ('兄が右で皿を拭いた。', '拭く', 'P_ACT', '右', 'de_instrument', 'で=右手（instrument）'), ('兄が右で絵を描いた。', '描く', 'P_CREATE', '右', 'de_instrument', 'で=右手（instrument）'),
            ('弟が右で記事を書いた。', '書く', 'P_CREATE', '右', 'de_instrument', 'で=右手（instrument）'), ('兄が段差で驚いた。', '驚く', 'P_EMOTION', '段差', 'de_cause', 'で=原因（cause）'),
            ('兄が口で戦った。', '戦う', 'P_ACT', '口', 'de_instrument', 'で=口（instrument）。r8 の 口=PLACE は文の語義 くち でない（K173）'),
            ('兄が口で絵を描いた。', '描く', 'P_CREATE', '口', 'de_instrument', 'で=口（instrument）'), ('兄が口で手紙を書いた。', '書く', 'P_CREATE', '口', 'de_instrument', 'で=口（instrument）'),
            ('兄が口で笑った。', '笑う', 'P_EMOTION', '口', 'de_instrument', 'で=口（instrument）')]
for text, verb, pt, filler, rg, what in w3b4_ten:
    a_ = text[0] if text[0] in '兄弟' else '兄'
    nouns = {a_: 'r8', filler: 'seed:PLACE'}
    for w in ('皿', '絵', '記事', '手紙'):
        if w in text: nouns[w] = 'r8'
    add('DEINSTR' if rg == 'de_instrument' else 'DECAUSE', 'A', text, verb, pt, 'absent', 'で', rg, '(a) W3-b4 の束 d・c の文。%s。述語は seed の語で r8 に枠の行が無い' % what, nouns, C.EXPECT_ABSTAIN,
        'PLACEMENT_PARTICLE_NOT_IN_FRAME:%s:で' % pt, 'W3-b4 の第 3 ラウンドで外した誤読の文。充填物 %s は偽の配置で direct の PLACE（r8 の実物は role@ だけ）。枠が無いので棄権する（打つ・驚く の枠に で:PLACE が無い）。' % filler)

# (b) the worst case: the r8 frame HOLDS で:PLACE, the filler is PLACE (optimistic fake), the role is the instrument
ins_pairs = [('投球する', None), ('演奏する', '曲'), ('運転する', 'トラック'), ('撮影する', '写真'), ('踊る', None), ('騒ぐ', None), ('栽培する', '苗'), ('放牧する', '牛'), ('過ごす', None), ('活躍する', None)]
for j, filler in enumerate(('右', '口')):
    for i, (verb, obj) in enumerate(ins_pairs):
        pt = C.r8_frame_row(verb)['ptype']
        a_ = ag(i + j)
        text = '%sが%sで%s%s。' % (a_, filler, (obj + 'を') if obj else '', C.past(verb))
        nouns = {a_: 'r8', filler: 'seed:PLACE'}
        if obj: nouns[obj] = 'r8'
        add('DEINSTR', 'A', text, verb, pt, 'r8', 'で', 'de_instrument', '(b) 枠が許す最悪の場合: 述語の r8 の枠が で:PLACE を持つ。で=%s（手段）。充填物は PLACE の語' % ('右手' if filler == '右' else '口'),
            nouns, C.EXPECT_ABSTAIN, 'REFUSED', '充填物 %s は偽の配置で direct の PLACE（r8 の実物は role@ だけで、付加の門 5 が今は止める）。読めば誤読（手段を場所と読む）。' % filler)
# the same with the real r8 answer of the filler (gate 5 refuses it today)
for i, (verb, obj, filler) in enumerate([('投球する', None, '右'), ('演奏する', '曲', '口'), ('運転する', 'トラック', '右'), ('撮影する', '写真', '口')]):
    pt = C.r8_frame_row(verb)['ptype']; a_ = ag(i + 9)
    text = '%sが%sで%s%s。' % (a_, filler, (obj + 'を') if obj else '', C.past(verb))
    nouns = {a_: 'r8', filler: 'r8'}
    if obj: nouns[obj] = 'r8'
    add('DEINSTR', 'A', text, verb, pt, 'r8', 'で', 'de_instrument', '(b)+(d) 枠は で:PLACE を持つ。充填物は r8 の実物の答え（role@ だけ）', nouns, C.EXPECT_ABSTAIN,
        'PLACEMENT_SLOT_EVIDENCE_ONLY:で:%s' % filler, 'r8 の実物: %s の腕は role@ だけ。付加の門 5。' % filler)

cause_pairs = [('段差', 'もたつく'), ('段差', 'やすむ'), ('段差', '休憩する'), ('坂', 'もたつく'), ('坂', 'やすむ'), ('坂', '騒ぐ'), ('溝', 'もたつく'), ('溝', '休憩する'), ('ぬかるみ', 'もたつく'),
               ('ぬかるみ', 'やすむ'), ('ぬかるみ', '騒ぐ'), ('崖', 'やすむ'), ('崖', '騒ぐ'), ('暗闇', 'もたつく'), ('暗闇', '騒ぐ'), ('暗闇', '休憩する'), ('崖', '休憩する'), ('溝', 'やすむ')]
for i, (filler, verb) in enumerate(cause_pairs):
    row = C.r8_frame_row(verb); assert row and 'で' in row['frame'] and 'PLACE' in row['frame']['で'], verb
    a_ = ag(i)
    add('DECAUSE', 'A', '%sが%sで%s。' % (a_, filler, C.past(verb)), verb, row['ptype'], 'r8', 'で', 'de_cause', '(b) 枠が許す最悪の場合: で=原因（%s は PLACE の語）' % filler,
        {a_: 'r8', filler: 'seed:PLACE'}, C.EXPECT_ABSTAIN, 'REFUSED', '充填物 %s は偽の配置で direct の PLACE（r8 の実物は PLACE・role@ だけ）。原因を場所と読めば誤読。' % filler)
for i, (filler, verb) in enumerate([('雨', 'やすむ'), ('雪', '休憩する'), ('風', 'もたつく'), ('台風', 'やすむ'), ('地震', '騒ぐ'), ('雷', '休憩する'), ('雨', 'もたつく'), ('風', '騒ぐ')]):
    row = C.r8_frame_row(verb); a_ = ag(i + 3)
    add('DECAUSE', 'A', '%sが%sで%s。' % (a_, filler, C.past(verb)), verb, row['ptype'], 'r8', 'で', 'de_cause', '(b) で=原因。充填物は自然現象（型が PLACE でない）', {a_: 'r8', filler: 'r8'},
        C.EXPECT_ABSTAIN, 'PLACEMENT_TYPE_MISMATCH:%s:で:NATURAL_PHENOMENON' % row['ptype'], '充填物 %s は r8 で NATURAL_PHENOMENON（direct）。で の行の型 PLACE に入らない。' % filler)
for i, (filler, verb) in enumerate([('段差', 'やすむ'), ('坂', '休憩する'), ('溝', 'もたつく'), ('ぬかるみ', 'もたつく')]):
    row = C.r8_frame_row(verb); a_ = ag(i + 5)
    add('DECAUSE', 'A', '%sが%sで%s。' % (a_, filler, C.past(verb)), verb, row['ptype'], 'r8', 'で', 'de_cause', '(b)+(d) 原因。充填物は r8 の実物の答え（role@ だけ）', {a_: 'r8', filler: 'r8'},
        C.EXPECT_ABSTAIN, 'PLACEMENT_SLOT_EVIDENCE_ONLY:で:%s' % filler, 'r8 の実物: %s の腕は role@ だけ。' % filler)

# ================================================================================================================================================
# MECH (the contract of `frame_generated`: a made-up frame; only this group may use one)
# ================================================================================================================================================
def mech_gf(ptype, frame, **over):
    g = {'origin': 'generated', 'constructed': True, 'ptype': ptype, 'frame': frame, 'provenance': {'model': 'synthetic', 'effort': 'none', 'batch_id': 'synthetic', 'attempt': 0}}
    g.update(over)
    return g


# the ten sentences, with a frame that holds neither で nor PLACE: does not license (the reason of a frame that says no)
for text, verb, pt, filler, rg, what in w3b4_ten:
    a_ = {'兄': '妹', '弟': '姉'}[text[0]]; text = a_ + text[1:]            # another subject: the inputs of the data are all different
    nouns = {a_: 'r8', filler: 'seed:PLACE'}
    for w in ('皿', '絵', '記事', '手紙'):
        if w in text: nouns[w] = 'r8'
    add('MECH', 'A', text, verb, pt, 'synthetic', 'で', 'mechanism', '作った枠（で を持たない）: W3-b4 の束 d・c の文。DOES_NOT_LICENSE を確かめる', nouns, C.EXPECT_ABSTAIN,
        'FRAME_GENERATED_DOES_NOT_LICENSE:で', 'synthetic の枠 {を:ARTIFACT, に:PERSON}（mechanism だけに許す）。', frame_generated=mech_gf(pt, {'を': ['ARTIFACT'], 'に': ['PERSON']}))
# a made-up frame whose で holds other types / is empty / is broken (a reason of its own)
mech_cases = [
    ({}, 'FRAME_GENERATED_DOES_NOT_LICENSE:で', '空の frame {}（何も許さない）'),
    ({'で': ['ABSTRACT']}, 'FRAME_GENERATED_DOES_NOT_LICENSE:で', 'で が PLACE を含まない'),
    ({'で': ['ARTIFACT', 'ABSTRACT']}, 'FRAME_GENERATED_DOES_NOT_LICENSE:で', 'で が PLACE を含まない（2 型）'),
    ({'に': ['PLACE']}, 'FRAME_GENERATED_DOES_NOT_LICENSE:で', 'で が無い（に だけ）'),
]
for i, (fr, why, what) in enumerate(mech_cases):
    a_ = ag(i)
    add('MECH', 'A', '%sが校庭で%s。' % (a_, C.past('活躍する')), '活躍する', 'P_ACT', 'synthetic', 'で', 'mechanism', '作った枠: ' + what, {a_: 'r8', '校庭': 'r8'}, C.EXPECT_ABSTAIN, why,
        'synthetic の枠。', frame_generated=mech_gf('P_ACT', fr))
broken = [
    (mech_gf('P_ACT', {'で': ['PLACE']}, origin='estimated'), 'PLACEMENT_FRAME_GENERATED_INVALID:ORIGIN_NOT_GENERATED', 'origin が generated でない'),
    (mech_gf('P_ACT', ['で', 'PLACE']), 'PLACEMENT_FRAME_GENERATED_INVALID:FRAME_NOT_A_MAPPING', 'frame が写像でない'),
    (mech_gf('P_ACT', {'の': ['PLACE']}), 'PLACEMENT_FRAME_GENERATED_INVALID:PARTICLE_NOT_CASE:の', '格助詞 9 種の外の助詞'),
    (mech_gf('P_ACT', {'で': 'PLACE'}), 'PLACEMENT_FRAME_GENERATED_INVALID:TYPES_NOT_A_LIST:で', '型が並びでない'),
    (mech_gf('P_ACT', {'で': []}), 'PLACEMENT_FRAME_GENERATED_INVALID:TYPES_NOT_A_LIST:で', '型の並びが空'),
    (mech_gf('P_ACT', {'で': ['PLACE', 'SPACE']}), 'PLACEMENT_FRAME_GENERATED_INVALID:TYPE_NOT_NOUN:で:SPACE', '17 型の外の型'),
    ('a string', 'PLACEMENT_FRAME_GENERATED_INVALID:NOT_A_MAPPING', 'frame_generated が写像でない'),
]
for i, (gf, why, what) in enumerate(broken):
    a_ = ag(i + 2)
    add('MECH', 'A', '%sが神社で%s。' % (a_, C.past('活躍する')), '活躍する', 'P_ACT', 'synthetic', 'で', 'mechanism', '壊れた枠: ' + what, {a_: 'r8', '神社': 'r8'}, C.EXPECT_ABSTAIN, why,
        'synthetic の壊れた枠。枠を見る必要がある文（で の行が frame_required）。', frame_generated=gf)

# ================================================================================================================================================
# NI (the particle に): recipient / goal / time / purpose / other
# ================================================================================================================================================
OBJ_TYPES = tuple(t for t in C.CP.ct.NOUN_TYPES if t not in ('TIME', 'QUANTITY', 'PLACE'))


def real_status(word):
    """frame_status of the REAL r8 answer of a predicate (a CONFIRMED word is never used as a fake NOT_CONFIRMED read row: the real entry would refuse it)."""
    return C.r8_answer(word).get('frame_status')


def ni_pred(verb, particle, typ, ptype):
    row = C.r8_frame_row(verb)
    assert row and row['ptype'] == ptype and typ in row['frame'].get(particle, []), (verb, row and (row['ptype'], row['frame']))
    return row


# --- NIRECIP-R: P_COMMUNICATE, に:PERSON / に:GROUP_ORG in the r8 frame, the reader names the に phrase `recipient` (U) -------------------------------------------------------
comm_persons = ['部長', '課長', '先輩', '後輩', '上司', '同僚', '社長', '店長', '隣人', '弁護士', '管理人', '看護師', '母', '父', '祖母', '先生']
comm_pairs = [('催促する', '返事', 'p'), ('申告する', None, 'p'), ('披露する', '曲', 'p'), ('請求する', '請求書', 'p'), ('告白する', None, 'p'), ('告知する', None, 'p'), ('助言する', None, 'p'),
              ('謝罪する', None, 'p'), ('抗議する', None, 'p'), ('懇願する', None, 'p'), ('要望する', None, 'p'), ('電話する', None, 'p'), ('返答する', None, 'p'), ('宣伝する', None, 'p'),
              ('伝授する', None, 'p'), ('書き送る', '書類', 'p'), ('反論する', None, 'p'), ('応答する', None, 'p'), ('怒鳴る', None, 'p'), ('あやまる', None, 'p'), ('たのむ', None, 'p'),
              ('せがむ', None, 'p'), ('発注する', '部品', 'p'), ('声かけする', None, 'p'), ('メールする', '書類', 'p'), ('申し送る', '書類', 'p'), ('言い返す', None, 'p'), ('布教する', None, 'p'),
              ('確約する', None, 'p'), ('奏上する', None, 'p'), ('抗議する', None, 'o'), ('請求する', None, 'o'), ('要望する', None, 'o'), ('返答する', None, 'o'), ('発注する', None, 'o'),
              ('催促する', None, 'o'), ('申告する', None, 'o'), ('宣伝する', None, 'o'), ('反論する', None, 'o')]
comm_orgs = ['政府', '会社', '議会', '組合', '協会', '財団', '裁判所', '検察', '大学', '劇団']
pi = oi = 0
for i, (verb, obj, who) in enumerate(comm_pairs):
    row = ni_pred(verb, 'に', 'PERSON' if who == 'p' else 'GROUP_ORG', 'P_COMMUNICATE')
    assert real_status(verb) != 'CONFIRMED', verb
    if who == 'p': r_ = comm_persons[pi % len(comm_persons)]; pi += 1
    else: r_ = comm_orgs[oi % len(comm_orgs)]; oi += 1
    if not C.noun_check(r_, ('PERSON', 'GROUP_ORG')): PROBLEMS.append((r_, 'filler type')); continue
    a_ = ag(i)
    text = '%sが%sに%s%s。' % (a_, r_, (obj + 'を') if obj else '', C.past(verb))
    nouns = {a_: 'r8', r_: 'r8'}
    roles = {'agent': a_, 'recipient': r_}
    if obj:
        if not C.noun_check(obj, OBJ_TYPES): PROBLEMS.append((obj, 'filler type')); continue
        nouns[obj] = 'r8'; roles['patient'] = obj
    add('NIRECIP', 'R', text, verb, 'P_COMMUNICATE', 'r8', 'に', 'ni_recipient', 'agent:が + recipient:に:%s（述語の r8 の枠が に:%s を持つ）' % ('PERSON' if who == 'p' else 'GROUP_ORG', 'PERSON' if who == 'p' else 'GROUP_ORG'),
        nouns, C.expect_read(verb, roles, must_ni(a_, r_, ('goal', 'place', 'time'))), 'READ',
        'r8 では述語は %s（direct の NOT_CONFIRMED として扱う）。伝達の相手 = recipient（規約 4.3）。' % ('NOT_CONFIRMED' if real_status(verb) == 'NOT_CONFIRMED' else 'estimated'))

# --- NIGOAL-R: P_MOVE, に:PLACE in the r8 frame; the filler is a PLACE word (an argument: the gate for adjuncts does not apply) -------------------------------------------------------
goal_pairs = [('むかう', '駅'), ('もどる', '空港'), ('かけこむ', '駅'), ('とびこむ', '海'), ('たどり着く', '山頂'), ('いたる', '港'), ('入院する', '病院'), ('入店する', '店'), ('入港する', '港'),
              ('出向く', '倉庫'), ('到達する', '山頂'), ('停車する', '駅'), ('停泊する', '港'), ('出動する', '現場'), ('侵入する', '倉庫'), ('入場する', '球場'), ('遠征する', '北海道'),
              ('赴く', '沖縄'), ('赴任する', '京都'), ('転入する', '町'), ('転校する', '村'), ('合流する', '公園'), ('潜り込む', '倉庫'), ('逃げ込む', '山'), ('飛び込む', '海'),
              ('乗り込む', '港'), ('先回りする', '駅'), ('旅行する', '北海道'), ('旅行する', '沖縄'), ('旅行する', '京都'), ('昇る', '山'), ('昇る', '山頂'), ('出張する', '現場'),
              ('入室する', '現場'), ('到達する', '港'), ('入院する', '町'), ('停泊する', '島'), ('向かう', '島'), ('もどる', '町'), ('とびこむ', '川')]
for i, (verb, f_) in enumerate(goal_pairs):
    row = C.r8_frame_row(verb)
    if not row or row['ptype'] != 'P_MOVE' or 'PLACE' not in row['frame'].get('に', []) or real_status(verb) == 'CONFIRMED':
        PROBLEMS.append((verb, 'goal predicate not usable (no r8 row / not P_MOVE / no に:PLACE / CONFIRMED)')); continue
    if not C.noun_check(f_, ('PLACE',)): PROBLEMS.append((f_, 'filler type')); continue
    a_ = ag(i + 1)
    add('NIGOAL', 'R', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, 'P_MOVE', 'r8', 'に', 'ni_goal', 'agent:が + goal:に:PLACE（述語の r8 の枠が に:PLACE を持つ）',
        {a_: 'r8', f_: 'r8'}, C.expect_read(verb, {'agent': a_, 'goal': f_}, must_ni(a_, f_, ('recipient', 'place', 'time'))), 'READ',
        'r8 では述語は %s。移動の到達点 = goal。' % ('NOT_CONFIRMED（実物）' if real_status(verb) == 'NOT_CONFIRMED' else 'estimated（direct の NOT_CONFIRMED として扱う）'))

# --- NITIME-R: P_ACT, に:TIME in the r8 frame; the filler is a TIME word that the reader does not read as a time itself (U) and that has evidence other than role@ ----------------
time_pairs = [('遅刻する', f_) for f_ in ('命日', '祭日', '朔日', '満月', '新月', '乾季', '昭和', '大正', '平成', '令和', '戦間期', '氷河期')] + \
             [('起きる', f_) for f_ in ('満月', '新月', '朔日', '命日', '祭日', '乾季', '氷河期', '戦間期', '明治時代', '奈良時代')]
for i, (verb, f_) in enumerate(time_pairs):
    row = C.r8_frame_row(verb)
    if not row or 'TIME' not in row['frame'].get('に', []): PROBLEMS.append((verb, 'no に:TIME')); continue
    if not C.noun_check(f_, ('TIME',), adjunct=True): PROBLEMS.append((f_, 'filler fails the gates of an adjunct')); continue
    a_ = ag(i + 4)
    add('NITIME', 'R', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, 'P_ACT', 'r8', 'に', 'ni_time', 'agent:が + time:に:TIME（述語の r8 の枠が に:TIME を持つ）',
        {a_: 'r8', f_: 'r8'}, C.expect_read(verb, {'agent': a_, 'time': f_}, must_ni(a_, f_, ('place', 'recipient', 'goal'))), 'READ',
        'r8 では述語は estimated。時の語 %s は読解器が自分で time と読まず（U）、r8 の direct の TIME で role@ だけでない証拠を持つ。' % f_)


def conf_spec(verb, ptype):
    """The REAL r8 answer of a CONFIRMED predicate (state, frame as r8 has it), with the row of generated_frames."""
    a = C.r8_answer(verb)
    assert a.get('frame_status') == 'CONFIRMED' and a['top'][0] == ptype, (verb, a.get('frame_status'))
    return {'top': list(a['top']), 'namespace': 'P', 'decided_by': list(a['decided_by']), 'frame_status': 'CONFIRMED', 'frame': a['frame'], 'frame_generated': C.r8_frame_row(verb)}


def est_spec(verb):
    """The REAL r8 answer of an estimated predicate (the type comes from a generated frame only)."""
    row = C.r8_frame_row(verb); a = C.r8_answer(verb)
    assert a['origin'] == 'estimated', verb
    return {'top': list(a['top']), 'namespace': 'P', 'origin': 'estimated', 'basis': 'generated', 'frame_status': 'ESTIMATED', 'frame_generated': row}


def absent_spec(ptype):
    return {'top': [ptype], 'namespace': 'P', 'decided_by': ['seed'], 'frame_status': 'NOT_CONFIRMED', 'frame_generated': None}


def simple_A(group, text, verb, ptype, fsrc, particle, rg, cons, nouns, why, note, **kw):
    return add(group, 'A', text, verb, ptype, fsrc, particle, rg, cons, nouns, C.EXPECT_ABSTAIN, why, note, **kw)


# --- NIRECIP-A -----------------------------------------------------------------------------------------------------------------------------------
# (i) P_MOVE に:GROUP_ORG: the に phrase is the organization joined / reached, not a recipient (the type of W3-b1's table change record 1)
org_dest = [('入社する', '会社'), ('入団する', '劇団'), ('入会する', '協会'), ('入部する', 'チーム'), ('入局する', '事務局'), ('入隊する', '軍'), ('入閣する', '内閣'), ('入省する', '政府'),
            ('加わる', '組合'), ('合流する', 'チーム'), ('編入する', '大学'), ('出社する', '会社'), ('着任する', '会社'), ('赴任する', '会社'), ('就く', '企業'), ('入学する', '大学'), ('進学する', '大学')]
for i, (verb, o_) in enumerate(org_dest):
    row = C.r8_frame_row(verb)
    if not row or row['ptype'] != 'P_MOVE' or 'GROUP_ORG' not in row['frame'].get('に', []) or real_status(verb) == 'CONFIRMED': PROBLEMS.append((verb, 'org dest not usable')); continue
    if not C.noun_check(o_, ('GROUP_ORG',)): PROBLEMS.append((o_, 'filler type')); continue
    a_ = ag(i)
    simple_A('NIRECIP', '%sが%sに%s。' % (a_, o_, C.past(verb)), verb, 'P_MOVE', 'r8', 'に', 'ni_recipient', '(b) P_MOVE の に:GROUP_ORG は行き先の組織（recipient でない）。r8 の枠は に:GROUP_ORG を持つ',
             {a_: 'r8', o_: 'r8'}, 'REFUSED', '組織 %s は行き先（goal）。recipient と読めば誤読（W3-b1 の表の変更記録 1 の型）。' % o_)
# (ii) P_COMMUNICATE に:PERSON where the person is not the one who receives the message
not_recv = [('面接する', '部長'), ('交渉する', '課長'), ('合意する', '先輩'), ('通じる', '同僚'), ('呼応する', '後輩'), ('取り次ぐ', '社長'), ('応対する', '店長'), ('話し込む', '隣人'),
            ('面接する', '弁護士'), ('交渉する', '管理人'), ('合意する', '看護師'), ('呼応する', '上司')]
for i, (verb, r_) in enumerate(not_recv):
    row = C.r8_frame_row(verb)
    if not row or row['ptype'] != 'P_COMMUNICATE' or 'PERSON' not in row['frame'].get('に', []): PROBLEMS.append((verb, 'not usable')); continue
    a_ = ag(i + 3)
    simple_A('NIRECIP', '%sが%sに%s。' % (a_, r_, C.past(verb)), verb, 'P_COMMUNICATE', 'r8', 'に', 'ni_recipient', '(b) P_COMMUNICATE の に:PERSON が相手（交渉・合意・面接）で、情報を受け取る人でない。r8 の枠は に:PERSON を持つ',
             {a_: 'r8', r_: 'r8'}, 'REFUSED', '相手 %s は recipient でない（枠は役割を言わない）。' % r_)
# (iii) the frame has に but not PERSON / GROUP_ORG: it says no
for i, (verb, r_) in enumerate([('旅行する', '先生'), ('旅行する', '会社'), ('昇る', '部長'), ('昇る', '政府'), ('旅行する', '母'), ('昇る', '協会'), ('遠征する', '先輩'), ('赴く', '社長')]):
    row = C.r8_frame_row(verb)
    if not row or 'に' not in row['frame'] or {'PERSON', 'GROUP_ORG'} & set(row['frame']['に']): PROBLEMS.append((verb, 'frame に holds PERSON/GROUP_ORG or has no に')); continue
    a_ = ag(i)
    simple_A('NIRECIP', '%sが%sに%s。' % (a_, r_, C.past(verb)), verb, 'P_MOVE', 'r8', 'に', 'ni_recipient', '(c) r8 の枠の に が PERSON・GROUP_ORG を持たない（%s）' % json.dumps(row['frame']['に'], ensure_ascii=False),
             {a_: 'r8', r_: 'r8'}, 'FRAME_GENERATED_DOES_NOT_LICENSE:に', '旅行する の枠の に は PLACE だけ。W3-b1 の表の変更記録 1 の誤読の型（会社に旅行した）。')
# (iv) a seed verb with no frame: the table has the time/に row only
for i, (verb, pt, r_) in enumerate([('頼む', 'P_COMMUNICATE', '部長'), ('誘う', 'P_COMMUNICATE', '先輩'), ('断る', 'P_COMMUNICATE', '課長'), ('呼ぶ', 'P_COMMUNICATE', '同僚'),
                                    ('走る', 'P_MOVE', '先生'), ('歩く', 'P_MOVE', '母'), ('進む', 'P_MOVE', '父'), ('渡る', 'P_MOVE', '祖母'), ('通る', 'P_MOVE', '社長')]):
    a_ = ag(i + 5)
    simple_A('NIRECIP', '%sが%sに%s。' % (a_, r_, C.past(verb)), verb, pt, 'absent', 'に', 'ni_recipient', '(c) frame_generated が無い（seed の語）。表の に は time だけ',
             {a_: 'r8', r_: 'r8'}, ('PLACEMENT_SLOT_EVIDENCE_ONLY:に:%s' % r_) if role_only(r_) else ('PLACEMENT_TYPE_MISMATCH:%s:に:PERSON' % pt),
             '述語 %s は r8 に枠の行が無い seed の語。表の に は time（付加）だけなので、充填物の腕が role@ だけなら付加の門 5 が先に止める（基点と同じ理由）。' % verb)
# (v) the filler is split
for i, (verb, f_) in enumerate([('催促する', '山田'), ('抗議する', '本社'), ('請求する', '本社'), ('申告する', '山田')]):
    a_ = ag(i)
    simple_A('NIRECIP', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, 'P_COMMUNICATE', 'r8', 'に', 'ni_recipient', '(d) 充填物が割れる（r8 の実物: %s）' % json.dumps(C.r8_answer(f_)['top'], ensure_ascii=False),
             {a_: 'r8', f_: 'r8'}, 'PLACEMENT_MULTIPLE:に:%s' % f_, '%s は r8 で MULTIPLE。候補の 1 つが行の型の外。' % f_)
# (vi) the predicate is estimated (the real state in r8) / CONFIRMED (the real frame of r8 has no に)
for i, (verb, r_) in enumerate([('助言する', '部長'), ('謝罪する', '課長'), ('懇願する', '先輩')]):
    a_ = ag(i + 1)
    simple_A('NIRECIP', '%sが%sに%s。' % (a_, r_, C.past(verb)), verb, 'P_COMMUNICATE', 'r8', 'に', 'ni_recipient', '(e) 述語は推定（r8 の実物の状態）', {a_: 'r8', r_: 'r8'},
             'PLACEMENT_ESTIMATED_GENERATED:predicate:%s' % verb, 'r8 の実物: 述語は estimated(generated)。', pred_override=est_spec(verb))
for i, (verb, r_) in enumerate([('周知する', '部長'), ('指導する', '後輩'), ('発信する', '同僚'), ('講義する', '学生'), ('送信する', '課長'), ('配信する', '先輩'), ('詫びる', '上司'), ('説く', '弟')]):
    a_ = ag(i)
    if C.r8_answer(verb).get('frame_status') != 'CONFIRMED': PROBLEMS.append((verb, 'not CONFIRMED')); continue
    simple_A('NIRECIP', '%sが%sに%s。' % (a_, r_, C.past(verb)), verb, 'P_COMMUNICATE', 'r8', 'に', 'ni_recipient', '(e) 述語は CONFIRMED（r8 の実物）で、確認済みの frame に に が無い', {a_: 'r8', r_: 'r8'},
             'PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:P_COMMUNICATE:に', 'r8 の実物: CONFIRMED。frame は %s。' % json.dumps(C.r8_answer(verb)['frame'], ensure_ascii=False), pred_override=conf_spec(verb, 'P_COMMUNICATE'))

# --- NIGOAL-A ------------------------------------------------------------------------------------------------------------------------------------
# (i) P_ACT に:PLACE: the に phrase is the place of work / stay, or a contact surface (not the goal of a movement)
non_goal = [('勤める', '工場'), ('つとめる', '病院'), ('奉職する', '町'), ('業務する', '市'), ('涼む', '島'), ('雨宿りする', '駅'), ('ぶつかる', '駅'), ('激突する', '倉庫'), ('追突する', '港'),
            ('命中する', '島'), ('遭遇する', '町'), ('介入する', '市'), ('集中する', '工場'), ('入浴する', '町'), ('出演する', '町'), ('出場する', '町'), ('いつく', '村')]
for i, (verb, f_) in enumerate(non_goal):
    row = C.r8_frame_row(verb)
    if not row or row['ptype'] != 'P_ACT' or 'PLACE' not in row['frame'].get('に', []): PROBLEMS.append((verb, 'P_ACT に:PLACE not usable')); continue
    if not C.noun_check(f_, ('PLACE',)): PROBLEMS.append((f_, 'filler type')); continue
    a_ = ag(i + 2)
    simple_A('NIGOAL', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, 'P_ACT', 'r8', 'に', 'ni_goal', '(b) P_ACT の に:PLACE が勤務先・滞在先・接触面で、移動の到達点でない。r8 の枠は に:PLACE を持つ',
             {a_: 'r8', f_: 'r8'}, 'REFUSED', '枠は役割を言わない（に:PLACE は goal・place・接触面）。goal と読めば誤読。')
for i, (verb, f_) in enumerate([('併設する', '町'), ('敷設する', '市'), ('分村する', '村'), ('記載する', '町')]):
    row = C.r8_frame_row(verb)
    if not row or row['ptype'] != 'P_CREATE' or 'PLACE' not in row['frame'].get('に', []): PROBLEMS.append((verb, 'P_CREATE に:PLACE not usable')); continue
    a_ = ag(i)
    simple_A('NIGOAL', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, 'P_CREATE', 'r8', 'に', 'ni_goal', '(b) P_CREATE の に:PLACE は作った物の置き場（place）か到達点か決まらない',
             {a_: 'r8', f_: 'r8'}, 'REFUSED', '枠は役割を言わない。')
# (ii) the filler of a goal: split, wrong type, unplaced, unknown, estimated; the predicate holds に:PLACE
for i, (verb, f_, why) in enumerate([('旅行する', '東京', 'PLACEMENT_MULTIPLE'), ('旅行する', '本社', 'PLACEMENT_MULTIPLE'), ('昇る', '左', 'PLACEMENT_MULTIPLE'), ('旅行する', '山田', 'PLACEMENT_MULTIPLE'),
                                     ('昇る', '稽古場', 'PLACEMENT_TYPE_MISMATCH:P_MOVE:に:WORK'), ('旅行する', '多数決', 'PLACEMENT_TYPE_MISMATCH:P_MOVE:に:ABSTRACT'),
                                     ('旅行する', '望遠レンズ', 'PLACEMENT_UNPLACED'), ('昇る', '搬出口', 'PLACEMENT_UNKNOWN'), ('旅行する', '電話口', 'PLACEMENT_ESTIMATED_GENERATED'),
                                     ('遠征する', '東京', 'PLACEMENT_MULTIPLE'), ('赴く', '本社', 'PLACEMENT_MULTIPLE'), ('赴任する', '稽古場', 'PLACEMENT_TYPE_MISMATCH:P_MOVE:に:WORK')]):
    row = C.r8_frame_row(verb)
    if not row or 'PLACE' not in row['frame'].get('に', []): PROBLEMS.append((verb, 'no に:PLACE')); continue
    a_ = ag(i + 3)
    reason = why if ':' in why else '%s:に:%s' % (why, f_)
    simple_A('NIGOAL', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, 'P_MOVE', 'r8', 'に', 'ni_goal', '(d) 充填物の配置（%s）。r8 の枠は に:PLACE を持つ' % why.split(':')[0], {a_: 'r8', f_: 'r8'}, reason,
             '充填物 %s は r8 の実物の答え。' % f_)
# (iii) seed verbs of movement (no frame): the table has the time/に row only
for i, (verb, f_) in enumerate([('走る', '駅'), ('歩く', '空港'), ('進む', '港'), ('戻る', '町'), ('帰る', '村'), ('入る', '倉庫'), ('出る', '島'), ('渡る', '山'), ('通る', '海'), ('向かう', '川'),
                                ('飛ぶ', '公園'), ('降りる', '現場')]):
    a_ = ag(i + 1)
    simple_A('NIGOAL', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, 'P_MOVE', 'absent', 'に', 'ni_goal', '(c) frame_generated が無い（seed の語）。表の に は time だけ', {a_: 'r8', f_: 'r8'},
             ('PLACEMENT_SLOT_EVIDENCE_ONLY:に:%s' % f_) if role_only(f_) else 'PLACEMENT_TYPE_MISMATCH:P_MOVE:に:PLACE',
             '述語 %s は r8 に枠の行が無い seed の語。表の に は time（付加）だけなので、充填物の腕が role@ だけなら付加の門 5 が先に止める（基点と同じ理由）。' % verb)
# (iv) the frame of the predicate has に but not PLACE
for i, (verb, f_) in enumerate([('催促する', '駅'), ('申告する', '空港'), ('請求する', '港'), ('披露する', '町'), ('抗議する', '村'), ('要望する', '島')]):
    row = C.r8_frame_row(verb)
    if not row or 'PLACE' in row['frame'].get('に', []): PROBLEMS.append((verb, 'frame に holds PLACE')); continue
    a_ = ag(i)
    simple_A('NIGOAL', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, 'P_COMMUNICATE', 'r8', 'に', 'ni_goal', '(c) r8 の枠の に が PLACE を持たない（%s）' % json.dumps(row['frame']['に'], ensure_ascii=False), {a_: 'r8', f_: 'r8'},
             'FRAME_GENERATED_DOES_NOT_LICENSE:に', '枠が に:PLACE を許さない。')
# (v) the predicate is estimated / CONFIRMED (real r8 states)
for i, (verb, f_) in enumerate([('入院する', '病院'), ('入港する', '港'), ('到達する', '山頂')]):
    a_ = ag(i + 2)
    simple_A('NIGOAL', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, 'P_MOVE', 'r8', 'に', 'ni_goal', '(e) 述語は推定（r8 の実物の状態）', {a_: 'r8', f_: 'r8'},
             'PLACEMENT_ESTIMATED_GENERATED:predicate:%s' % verb, 'r8 の実物: 述語は estimated(generated)。', pred_override=est_spec(verb))
for i, (verb, f_) in enumerate([('通う', '病院'), ('避難する', '町'), ('日帰りする', '町'), ('移動する', '町'), ('進出する', '町'), ('潜る', '海'), ('戻れる', '町'), ('行ける', '港'), ('浸透する', '町')]):
    a_ = ag(i)
    if C.r8_answer(verb).get('frame_status') != 'CONFIRMED': PROBLEMS.append((verb, 'not CONFIRMED')); continue
    simple_A('NIGOAL', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, 'P_MOVE', 'r8', 'に', 'ni_goal', '(e) 述語は CONFIRMED（r8 の実物）で、確認済みの frame に に が無い', {a_: 'r8', f_: 'r8'},
             'PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:P_MOVE:に', 'r8 の実物: CONFIRMED。frame は %s。' % json.dumps(C.r8_answer(verb)['frame'], ensure_ascii=False), pred_override=conf_spec(verb, 'P_MOVE'))

# --- NITIME-A ------------------------------------------------------------------------------------------------------------------------------------
tv = ['遅刻する', '起きる']
# (i) role@ only (gate 5, an adjunct) / decided by a generated definition (gate 4)
for i, f_ in enumerate(['七夕', '節分', '日没', '室町時代', '幕末', '平安時代', '弥生時代', '鎌倉時代']):
    verb = tv[i % 2]; a_ = ag(i)
    simple_A('NITIME', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, 'P_ACT', 'r8', 'に', 'ni_time', '(d) 充填物の腕が role@ だけ（付加の門 5）。r8 の枠は に:TIME を持つ', {a_: 'r8', f_: 'r8'},
             'PLACEMENT_SLOT_EVIDENCE_ONLY:に:%s' % f_, '充填物 %s は r8 の direct の TIME だが腕は role@ だけ。' % f_)
for i, f_ in enumerate(['全盛期', '収穫期', '旧暦', '昭和初期', '立春', '繁忙期', '飛鳥時代']):
    verb = tv[(i + 1) % 2]; a_ = ag(i + 2)
    simple_A('NITIME', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, 'P_ACT', 'r8', 'に', 'ni_time', '(d) 充填物が生成の定義で決まった（門 4）。r8 の枠は に:TIME を持つ', {a_: 'r8', f_: 'r8'},
             'PLACEMENT_DIRECT_VIA_GENERATED:に:%s' % f_, '充填物 %s は r8 で gen_definition が決め手。' % f_)
# (ii) the に phrase is the target of a stare / the cause of a feeling (the frame says に:TIME)
for i, (verb, pt, f_) in enumerate([('臨む', 'P_ACT', '命日'), ('臨む', 'P_ACT', '祭日'), ('臨む', 'P_ACT', '満月'), ('臨む', 'P_ACT', '乾季'), ('臨む', 'P_ACT', '昭和'), ('臨む', 'P_ACT', '令和'),
                                    ('臨む', 'P_ACT', '大正'), ('退屈する', 'P_EMOTION', '満月'), ('退屈する', 'P_EMOTION', '新月'), ('退屈する', 'P_EMOTION', '命日'), ('退屈する', 'P_EMOTION', '祭日'),
                                    ('退屈する', 'P_EMOTION', '乾季')]):
    row = C.r8_frame_row(verb)
    if not row or 'TIME' not in row['frame'].get('に', []): PROBLEMS.append((verb, 'no に:TIME')); continue
    a_ = ag(i + 5)
    simple_A('NITIME', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, pt, 'r8', 'に', 'ni_time', '(b) r8 の枠が に:TIME を持つが、に の句は対象・原因（%s に%s）で time でない' % (f_, verb), {a_: 'r8', f_: 'r8'}, 'REFUSED',
             '枠は役割を言わない。時と読めば誤読（W3-b4 の P_CONSUME の型）。')
# (iii) the frame has に but not TIME
for i, (verb, pt, f_) in enumerate([('参拝する', 'P_ACT', '満月'), ('会う', 'P_ACT', '命日'), ('勝つ', 'P_ACT', '祭日'), ('逆らう', 'P_ACT', '乾季'), ('挑む', 'P_ACT', '朔日'), ('勤める', 'P_ACT', '昭和'),
                                    ('反抗する', 'P_ACT', '大正'), ('感心する', 'P_EMOTION', '命日'), ('共感する', 'P_EMOTION', '祭日'), ('戸惑う', 'P_EMOTION', '満月'), ('書き込む', 'P_CREATE', '朔日'),
                                    ('記載する', 'P_CREATE', '命日')]):
    row = C.r8_frame_row(verb)
    if not row or row['ptype'] != pt or 'TIME' in row['frame'].get('に', []) or 'に' not in row['frame']: PROBLEMS.append((verb, 'frame に holds TIME / no に')); continue
    a_ = ag(i + 1)
    simple_A('NITIME', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, pt, 'r8', 'に', 'ni_time', '(c) r8 の枠の に が TIME を持たない（%s）' % json.dumps(row['frame']['に'], ensure_ascii=False), {a_: 'r8', f_: 'r8'},
             'FRAME_GENERATED_DOES_NOT_LICENSE:に', '枠が に:TIME を許さない。')
# (iv) no frame (a seed verb): P_ACT / P_EMOTION / P_CREATE have no row with に
for i, (verb, pt, f_) in enumerate([('遊ぶ', 'P_ACT', '満月'), ('働く', 'P_ACT', '命日'), ('守る', 'P_ACT', '祭日'), ('打つ', 'P_ACT', '乾季'), ('驚く', 'P_EMOTION', '満月'), ('喜ぶ', 'P_EMOTION', '命日'),
                                    ('怒る', 'P_EMOTION', '祭日'), ('作る', 'P_CREATE', '満月'), ('書く', 'P_CREATE', '命日'), ('描く', 'P_CREATE', '祭日')]):
    a_ = ag(i + 7)
    simple_A('NITIME', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, pt, 'absent', 'に', 'ni_time', '(c) frame_generated が無い（seed の語）。表に に の行が無い', {a_: 'r8', f_: 'r8'},
             'PLACEMENT_PARTICLE_NOT_IN_FRAME:%s:に' % pt, '述語 %s は r8 に枠の行が無い seed の語。基点と同じ理由。' % verb)
# (v) split filler
for i, (verb, f_) in enumerate([('遅刻する', '東京'), ('起きる', '左'), ('遅刻する', '石畳')]):
    a_ = ag(i)
    simple_A('NITIME', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, 'P_ACT', 'r8', 'に', 'ni_time', '(d) 充填物が割れる（%s）' % json.dumps(C.r8_answer(f_)['top'], ensure_ascii=False), {a_: 'r8', f_: 'r8'},
             ('PLACEMENT_SLOT_EVIDENCE_ONLY:に:%s' % f_) if role_only(f_) else ('PLACEMENT_MULTIPLE:に:%s' % f_), '%s は r8 で MULTIPLE。時の行は付加なので、腕が role@ だけなら門 5 が先に止める。' % f_)

# --- NIPURP-A: に = purpose ------------------------------------------------------------------------------------------------------------------------
purposes = ['取材', '見学', '買い物', '散歩', '見物', '面会', '勉強', '運動']
for i, f_ in enumerate(purposes):
    if C.r8_answer(f_)['top'][0] != 'EVENT_ACT' or C.r8_answer(f_)['state'] != 'DECIDED': PROBLEMS.append((f_, 'not EVENT_ACT')); continue
    for j, verb in enumerate(['出向く', '赴く', '遠征する', '出動する']):
        row = C.r8_frame_row(verb)
        if not row or row['ptype'] != 'P_MOVE' or real_status(verb) == 'CONFIRMED' or not {'PLACE', 'PERSON', 'GROUP_ORG'} & set(row['frame'].get('に', [])): PROBLEMS.append((verb, 'purpose verb not usable')); continue
        a_ = ag(i + j)
        simple_A('NIPURP', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, 'P_MOVE', 'r8', 'に', 'ni_purpose', '(b) に の句は目的（%s に%s）。型は EVENT_ACT で行の型の外' % (f_, verb), {a_: 'r8', f_: 'r8'},
                 'PLACEMENT_TYPE_MISMATCH:P_MOVE:に:EVENT_ACT', '目的の充填物の型は EVENT_ACT（r8 の direct）。どの行の型にも入らない。')
# a use of money ("休みに金を使った"): P_CONSUME is a type that stays unread (W3-b4 table change record 2)
for i, f_ in enumerate(['休み', '夏休み', '祭日', '朔日', '命日', '乾季']):
    a_ = ag(i + 2)
    if not C.noun_check(f_, ('TIME',), adjunct=True) and f_ not in ('休み', '夏休み'): PROBLEMS.append((f_, 'time filler')); continue
    add('NIPURP', 'A', '%sが%sに金を使った。' % (a_, f_), '使う', 'P_CONSUME', 'absent', 'に', 'ni_purpose', '(b) に+TIME が使い道（P_CONSUME は読まない型）', {a_: 'r8', f_: 'r8', '金': 'r8'},
        C.EXPECT_ABSTAIN, 'PLACEMENT_FRAME_NOT_READ:P_CONSUME', 'W3-b4 の表の変更記録 2 の型。述語 使う は seed。', pred_word='使う')

# --- NIOTHER-A: stimulus / opponent / source of a feeling or an act ------------------------------------------------------------------------------
stim = [('共感する', '先生'), ('執着する', '先輩'), ('帰依する', '上司'), ('恋する', '母'), ('恐縮する', '部長'), ('感心する', '父'), ('戸惑う', '隣人'), ('満足する', '後輩'), ('親しむ', '祖母'),
        ('配慮する', '課長'), ('いら立つ', '同僚'), ('おどろく', '店長'), ('なやむ', '弁護士'), ('びびる', '管理人'), ('恐れ入る', '社長'), ('共感する', '看護師')]
for i, (verb, r_) in enumerate(stim):
    row = C.r8_frame_row(verb)
    if not row or row['ptype'] != 'P_EMOTION' or 'PERSON' not in row['frame'].get('に', []): PROBLEMS.append((verb, 'P_EMOTION に:PERSON not usable')); continue
    a_ = ag(i + 1)
    simple_A('NIOTHER', '%sが%sに%s。' % (a_, r_, C.past(verb)), verb, 'P_EMOTION', 'r8', 'に', 'ni_other', '(b) P_EMOTION の に:PERSON は感情の対象・刺激（recipient でない）。r8 の枠は に:PERSON を持つ',
             {a_: 'r8', r_: 'r8'}, 'REFUSED', '対象 %s は recipient でない（枠は役割を言わない）。' % r_)
opp = [('かみつく', '先生'), ('さわる', '先輩'), ('すがる', '上司'), ('つきまとう', '母'), ('ぶつかる', '部長'), ('反抗する', '父'), ('反発する', '隣人'), ('逆らう', '後輩'), ('挑む', '祖母'),
       ('立ち向かう', '課長'), ('勝つ', '同僚'), ('会う', '店長'), ('再会する', '弁護士'), ('遭遇する', '管理人'), ('激突する', '社長'), ('倣う', '看護師'), ('拝む', '先生'), ('屈する', '先輩')]
for i, (verb, r_) in enumerate(opp):
    row = C.r8_frame_row(verb)
    if not row or row['ptype'] != 'P_ACT' or 'PERSON' not in row['frame'].get('に', []): PROBLEMS.append((verb, 'P_ACT に:PERSON not usable')); continue
    a_ = ag(i + 3)
    simple_A('NIOTHER', '%sが%sに%s。' % (a_, r_, C.past(verb)), verb, 'P_ACT', 'r8', 'に', 'ni_other', '(b) P_ACT の に:PERSON は対戦・接触・手本の相手（recipient でない）。r8 の枠は に:PERSON を持つ',
             {a_: 'r8', r_: 'r8'}, 'REFUSED', '相手 %s は recipient でない。' % r_)
for i, (verb, r_) in enumerate([('打つ', '先生'), ('守る', '母'), ('遊ぶ', '弟'), ('洗う', '妹')]):
    a_ = ag(i + 6)
    if r_ == a_: continue
    simple_A('NIOTHER', '%sが%sに%s。' % (a_, r_, C.past(verb)), verb, 'P_ACT', 'absent', 'に', 'ni_other', '(c) frame_generated が無い（seed の語）。P_ACT の表に に の行が無い', {a_: 'r8', r_: 'r8'},
             'PLACEMENT_PARTICLE_NOT_IN_FRAME:P_ACT:に', '述語 %s は seed の語。基点と同じ理由。' % verb)

# ================================================================================================================================================
# more rows: all candidates inside the row (a split filler that is read), goals of P_ACT with a patient, the gates that stay on に
# ================================================================================================================================================
# a MULTIPLE direct filler whose every candidate is in the expected types of the row (the entry reads it: the reading is the same whichever candidate it is)
for i, (verb, f_) in enumerate([('抗議する', '警察'), ('告白する', '家族'), ('要望する', '警察'), ('申告する', '警察'), ('請求する', '顧客'), ('宣伝する', '顧客'), ('伝授する', '家族')]):
    row = C.r8_frame_row(verb)
    if not row or not {'PERSON', 'GROUP_ORG'} & set(row['frame'].get('に', [])) or real_status(verb) == 'CONFIRMED': PROBLEMS.append((verb, 'not usable')); continue
    a_ = ag(i + 4)
    add('NIRECIP', 'R', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, 'P_COMMUNICATE', 'r8', 'に', 'ni_recipient', 'agent:が + recipient:に（MULTIPLE{GROUP_ORG,PERSON}: 全候補が行の型に入る）',
        {a_: 'r8', f_: 'r8'}, C.expect_read(verb, {'agent': a_, 'recipient': f_}, must_ni(a_, f_, ('goal', 'place', 'time'))), 'READ',
        '充填物 %s は r8 で MULTIPLE direct {GROUP_ORG, PERSON}（decided_by に gen_definition が無い）。全候補が行の型の中（どちらでも recipient）。' % f_)
for i, (verb, f_) in enumerate([('催促する', '友人'), ('請求する', '隊員'), ('抗議する', '住民'), ('申告する', '相手')]):
    a_ = ag(i + 8)
    simple_A('NIRECIP', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, 'P_COMMUNICATE', 'r8', 'に', 'ni_recipient', '(d) 充填物が割れ、候補の 1 つが行の型の外（r8 の実物: %s）' % json.dumps(C.r8_answer(f_)['top'], ensure_ascii=False),
             {a_: 'r8', f_: 'r8'}, 'PLACEMENT_MULTIPLE:に:%s' % f_, '%s は r8 で MULTIPLE。' % f_)
# goals of P_ACT with a patient: moving or setting a thing to a place
for i, (verb, obj, f_) in enumerate([('参拝する', None, '神社'), ('登山する', None, '山'), ('係留する', '船', '港'), ('参列する', None, '教会'), ('植え込む', '苗', '畑'), ('供える', '花', '神社'),
                                      ('格納する', '機械', '倉庫'), ('設置する', '装置', '駅'), ('配備する', '船', '港'), ('保存する', '書類', '倉庫'), ('積み込む', '部品', '港'), ('据える', '装置', '現場')]):
    row = C.r8_frame_row(verb)
    if not row or row['ptype'] != 'P_ACT' or 'PLACE' not in row['frame'].get('に', []) or real_status(verb) == 'CONFIRMED': PROBLEMS.append((verb, 'P_ACT goal not usable')); continue
    if not C.noun_check(f_, ('PLACE',)) or (obj and not C.noun_check(obj, OBJ_TYPES)): PROBLEMS.append((verb, 'filler type')); continue
    a_ = ag(i + 2)
    text = ('%sが%sを%sに%s。' % (a_, obj, f_, C.past(verb))) if obj else ('%sが%sに%s。' % (a_, f_, C.past(verb)))
    nouns = {a_: 'r8', f_: 'r8'}; roles = {'agent': a_, 'goal': f_}
    if obj: nouns[obj] = 'r8'; roles['patient'] = obj
    add('NIGOAL', 'R', text, verb, 'P_ACT', 'r8', 'に', 'ni_goal', 'agent:が %s+ goal:に:PLACE（P_ACT。述語の r8 の枠が に:PLACE を持つ）' % ('+ patient:を ' if obj else ''), nouns,
        C.expect_read(verb, roles, must_ni(a_, f_, ('recipient', 'place', 'time'))), 'READ', 'r8 では述語は estimated（direct の NOT_CONFIRMED として扱う）。置き場所・参拝先 = goal。')
# the gates that stay on に: a focus particle after に (K186), voice, a derived head
for i, (text_f, verb, f_, why, what) in enumerate([
        ('%sが%sにも%s。', '旅行する', '北海道', 'PLACEMENT_FOCUS_PARTICLE_AFTER_CASE', 'K186（に の直後の も）'), ('%sが%sにさえ%s。', '旅行する', '沖縄', 'PLACEMENT_FOCUS_PARTICLE_AFTER_CASE', 'K186（に の直後の さえ）'),
        ('%sが%sにも%s。', '催促する', '部長', 'PLACEMENT_FOCUS_PARTICLE_AFTER_CASE', 'K186（に の直後の も）'), ('%sが%sにばかり%s。', '申告する', '課長', 'PLACEMENT_FOCUS_PARTICLE_AFTER_CASE', 'K186（に の直後の ばかり）'),
        ('%sが%sにも%s。', '遅刻する', '満月', 'PLACEMENT_FOCUS_PARTICLE_AFTER_CASE', 'K186（に の直後の も）')]):
    a_ = ag(i)
    pt = C.r8_frame_row(verb)['ptype']
    text = text_f % (a_, f_, C.past(verb))
    add('NIGOAL' if verb == '旅行する' else ('NIRECIP' if pt == 'P_COMMUNICATE' else 'NITIME'), 'A', text, verb, pt, 'r8', 'に', 'ni_goal' if verb == '旅行する' else ('ni_recipient' if pt == 'P_COMMUNICATE' else 'ni_time'),
        '(f) 既存の門: ' + what, {a_: 'r8', f_: 'r8'}, C.EXPECT_ABSTAIN, why, 'gate: 枠が許し、充填物も direct。係助詞・副助詞の門が読みを落とす。')
for i, (verb, f_, ptx) in enumerate([('催促する', '部長', 'した'), ('申告する', '課長', 'したい')]):
    a_ = ag(i + 3); stem = verb[:-2]
    add('NIRECIP', 'A', '%sが%sに%s%s。' % (a_, f_, stem, ptx), verb, 'P_COMMUNICATE', 'r8', 'に', 'ni_recipient', '(f) 既存の門: 語尾' if ptx == 'したい' else '(f) 既存の門（語尾は読む形）', {a_: 'r8', f_: 'r8'},
        C.EXPECT_ABSTAIN, 'PLACEMENT_PREDICATE_TAIL_UNINTERPRETED', 'gate: 語尾の門。') if ptx == 'したい' else None
for i, (verb, f_, ptype_) in enumerate([('つたえる', '部長', 'P_COMMUNICATE'), ('おしえる', '先輩', 'P_COMMUNICATE'), ('ひろめる', '課長', 'P_COMMUNICATE'), ('例える', '後輩', 'P_COMMUNICATE')]):
    a_ = ag(i + 5)
    row = C.r8_frame_row(verb)
    if not row: PROBLEMS.append((verb, 'no row')); continue
    add('NIRECIP', 'A', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, 'P_COMMUNICATE', 'r8', 'に', 'ni_recipient', '(f) 既存の門: 派生の疑い（下一段）', {a_: 'r8', f_: 'r8'}, C.EXPECT_ABSTAIN,
        'PLACEMENT_PREDICATE_POSSIBLY_DERIVED', 'gate: 派生の門（W3-b1 の表の変更記録 3）。r8 の枠は に:PERSON を持つ。')

# ================================================================================================================================================
# sentences the typed step is not asked about (the reader alone reads them, or abstains for a reason that is not a case split): no trigger
# ================================================================================================================================================
for i, (place, verb) in enumerate([('温室', '活躍する'), ('広場', '休憩する'), ('倉庫', '勤務する'), ('球場', '活躍する'), ('温室', '昼寝する'), ('広場', '乾杯する')]):
    a_ = ag(i)
    add('DEPLACE', 'R', '%sが%sで%s。' % (a_, place, C.past(verb)), verb, 'P_ACT', 'r8', 'で', 'de_place', 'agent:が + place:で:PLACE（読解器が で を自分で place と読む語。型の段は呼ばれない）',
        {a_: 'r8', place: 'r8'}, C.expect_read(verb, {'agent': a_, 'place': place}, must_de(a_, place)), 'PLACEMENT_W3B2_NOT_TRIGGERED',
        '読解器だけで読める（配置なしの入口と同じ）。型の段は引き金に当たらない。', want_path=('none',))
for i, (text_f, verb) in enumerate([('%sが校庭で活躍して休んだ。', '活躍する'), ('%sがホテルで休憩し、弟が休んだ。', '休憩する'), ('%sが神社で踊ったが、弟は帰った。', '踊る')]):
    a_ = ag(i + 3)
    add('DEPLACE', 'A', text_f % a_, verb, 'P_ACT', 'r8', 'で', 'de_place', '(f) 既存の門: 節が 2 つ（型の段の引き金に当たらない）', {a_: 'r8', '校庭': 'r8', 'ホテル': 'r8', '神社': 'r8'},
        C.EXPECT_ABSTAIN, 'PLACEMENT_W3B2_NOT_TRIGGERED', '複数の節は引き金に当たらない（読解器が節の範囲を決められない）。', want_path=('none',))

# ================================================================================================================================================
# APPENDED AFTER THE FREEZE OF THE FIRST 604 ROWS (docs 10F, judgement record H206): the rows of the table that the first 604 rows could not exercise with a real r8 frame
# (P_COMMUNICATE goal/に, P_EMOTION place/で and goal/に, P_CREATE recipient/に). Written before they were run (the expectations are the design of each row); ids 901-.
# A row that is read although it is a worst case is a misread (K206: its row of the table goes). The made-up frames are the mechanism group's.
# ================================================================================================================================================
_n = 900
for verb, f_ in [('案内する', '駅'), ('案内する', '空港'), ('案内する', '港'), ('登壇する', '舞台'), ('掲示する', '校舎')]:
    row = C.r8_frame_row(verb)
    if not row or row['ptype'] != 'P_COMMUNICATE' or 'PLACE' not in row['frame'].get('に', []) or real_status(verb) == 'CONFIRMED': PROBLEMS.append((verb, 'comm goal not usable')); continue
    if not C.noun_check(f_, ('PLACE',)): PROBLEMS.append((f_, 'filler type')); continue
    _n += 1; a_ = ag(_n)
    add('NIGOAL', 'R', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, 'P_COMMUNICATE', 'r8', 'に', 'ni_goal', 'agent:が + goal:に:PLACE（P_COMMUNICATE。r8 の枠が に:PLACE を持つ）',
        {a_: 'r8', f_: 'r8'}, C.expect_read(verb, {'agent': a_, 'goal': f_}, must_ni(a_, f_, ('recipient', 'place', 'time'))), 'READ', 'r8 では述語は estimated。案内・掲示・登壇の行き先 = goal。', idnum=_n)
_n = 900
for verb, f_ in [('通じる', '町'), ('通じる', '村'), ('通じる', '島'), ('通じる', '山'), ('送付する', '町'), ('送付する', '村')]:
    row = C.r8_frame_row(verb)
    if not row or row['ptype'] != 'P_COMMUNICATE' or 'PLACE' not in row['frame'].get('に', []): PROBLEMS.append((verb, 'comm goal worst case not usable')); continue
    if not C.noun_check(f_, ('PLACE',)): PROBLEMS.append((f_, 'filler type')); continue
    _n += 1; a_ = ag(_n)
    simple_A('NIGOAL', '%sが%sに%s。' % (a_, f_, C.past(verb)), verb, 'P_COMMUNICATE', 'r8', 'に', 'ni_goal', '(b) P_COMMUNICATE の に:PLACE が行き先でなく、通じる相手・送り先（recipient）の場所。r8 の枠は に:PLACE を持つ',
             {a_: 'r8', f_: 'r8'}, 'REFUSED', '枠は役割を言わない。goal と読めば誤読。', idnum=_n)
_n = 900
for text, verb, pt, filler, particle, ftype, what in [
        ('弟が段差で驚いた。', '驚く', 'P_EMOTION', '段差', 'で', 'PLACE', 'で=原因'), ('姉が坂でおどろいた。', 'おどろく', 'P_EMOTION', '坂', 'で', 'PLACE', 'で=原因'),
        ('妹が溝で戸惑った。', '戸惑う', 'P_EMOTION', '溝', 'で', 'PLACE', 'で=原因'), ('弟が崖でおびえた。', 'おびえる', 'P_EMOTION', '崖', 'で', 'PLACE', 'で=原因'),
        ('姉が現場におどろいた。', 'おどろく', 'P_EMOTION', '現場', 'に', 'PLACE', 'に=原因（驚きの対象）'), ('妹が駅に戸惑った。', '戸惑う', 'P_EMOTION', '駅', 'に', 'PLACE', 'に=原因'),
        ('弟が港に感心した。', '感心する', 'P_EMOTION', '港', 'に', 'PLACE', 'に=対象')]:
    _n += 1
    a_ = text[0]
    if C.past(verb) is None or (verb in ('おどろく',) and False): continue
    gf_ = mech_gf(pt, {particle: [ftype]})
    nouns = {a_: 'r8', filler: 'seed:PLACE' if particle == 'で' else 'r8'}
    add('MECH', 'A', text, verb, pt, 'synthetic', particle, 'mechanism', '作った枠が %s:[PLACE] を持つ P_EMOTION の述語（%s）。r8 にはこの形の枠が無い' % (particle, what), nouns, C.EXPECT_ABSTAIN, 'REFUSED',
        'synthetic の枠。P_EMOTION の place/で と goal/に の行を働かせる最悪の場合（枠は役割を言わない）。', frame_generated=gf_, idnum=_n)
for text, verb, pt, filler in [('兄が先生に作った。', '作る', 'P_CREATE', '先生'), ('弟が先輩に縫った。', '縫う', 'P_CREATE', '先輩'), ('姉が母に編んだ。', '編む', 'P_CREATE', '母'),
                               ('妹が祖母に焼いた。', '焼く', 'P_CREATE', '祖母'), ('兄が上司に書いた。', '書く', 'P_CREATE', '上司')]:
    _n += 1
    a_ = text[0]
    gf_ = mech_gf(pt, {'に': ['PERSON']})
    add('MECH', 'A', text, verb, pt, 'synthetic', 'に', 'mechanism', '作った枠が に:[PERSON] を持つ P_CREATE の述語。に の人は受益者・宛先（recipient か beneficiary か決まらない）', {a_: 'r8', filler: 'r8'},
        C.EXPECT_ABSTAIN, 'REFUSED', 'synthetic の枠。P_CREATE の recipient/に の行を働かせる最悪の場合（r8 で に:PERSON を持つ P_CREATE の語は かなえる・分泌する の 2 語）。', frame_generated=gf_, idnum=_n)
