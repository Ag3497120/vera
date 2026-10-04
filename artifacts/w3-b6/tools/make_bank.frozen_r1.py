#!/usr/bin/env python3
"""W3-b6 step 3: writes tests/reading_soundness/ja_r13.jsonl (the data, frozen before the implementation). The expectations are written here BY THE DESIGN (docs 10I K270-K277),
not from an output of the new code. What is measured is only the facts of the placement r8 (read only: the types and arms of the ordinary words are copied from it, so the
fakes do not contradict it) and the trigger of the reader as it is (`w3b1_trigger` / `w3b2_trigger` at the base commit), which is recorded in each row as `base_trigger`.
Usage: PYTHONPATH=<tree> python artifacts/w3-b6/tools/make_bank.py R8_PATH OUT.jsonl"""
import json
import sys
sys.path.insert(0, 'tests/reading_soundness')
import w3b6_fakes as W
from verantyx import coarse_place as CP, semantic_read as SR

R8 = sys.argv[1]
OUT = sys.argv[2]
ROWS = []
SEEN = set()


def noun_spec(word):
    q = CP.query(word, placement=R8)
    if q['state'] in ('DECIDED', 'MULTIPLE') and q['origin'] == 'direct': return {'top': list(q['top']), 'decided_by': list(q['decided_by'])}
    if q['state'] == 'DECIDED': return {'top': list(q['top']), 'origin': 'estimated', 'basis': q['estimate_basis']}
    return {'state': q['state']}


def pred_spec(word, ptype):
    """The answer of r8 for a predicate when it is DECIDED direct with that type; else a synthetic direct one (the caller notes it)."""
    q = CP.query(word, placement=R8)
    if q['state'] == 'DECIDED' and q['origin'] == 'direct' and q['top'] == [ptype]:
        return {'top': [ptype], 'namespace': 'P', 'decided_by': list(q['decided_by']), 'frame_status': 'NOT_CONFIRMED', 'frame': None}, False
    return {'top': [ptype], 'namespace': 'P', 'decided_by': ['seed'], 'frame_status': 'NOT_CONFIRMED', 'frame': None}, True


def frame(**kw):
    """{particle: [(role, [types]), ...]} -> the role_frame of the contract (sorted types)."""
    return {p: [{'role': r, 'types': sorted(t)} for r, t in entries] for p, entries in kw.items()}


def row(rid, text, *, rule, particle, pred, ptype, nouns, rf, path, w3b6, behavior, roles=None, must_not=(), construction='', note='', basis=None, keyless_same=False,
        over=None, status='CONFIRMED', unconf='default', plan_expect=None, tense='past'):
    assert rid not in SEEN, rid
    SEEN.add(rid)
    placement, synth = {}, []
    for w in nouns:
        if over and w in over:
            placement[w] = over[w]; synth.append(w)
        else:
            placement[w] = noun_spec(w)
    for w in (over or {}):
        if w not in placement and w != pred: placement[w] = over[w]; synth.append(w)
    spec, psynth = pred_spec(pred, ptype)
    if over and pred in over: spec = over[pred]
    if psynth: synth.append(pred)
    if rf != 'ABSENT':
        spec['role_frame_status'] = status
        spec['role_frame'] = rf if status == 'CONFIRMED' or rf is not None else None
        spec['role_frame_unconfirmed'] = ({'で': [{'role': 'place', 'reason': 'NOT_BACKED'}]} if unconf == 'default' else unconf) if status != 'NO_ROLE_FRAME' else None
    placement[pred] = spec
    if behavior == 'read':
        expect = {'readable': True, 'clauses': [{'predicate': pred, 'roles': roles, 'polarity': '+', 'tense': tense, 'modality': None, 'voice': 'active'}], 'relations': [],
                  'must_not': list(must_not)}
    else:
        expect = {'readable': False, 'clauses': [], 'relations': [], 'must_not': []}
    r = {'id': rid, 'lang': 'ja', 'input': text, 'text': text, 'behavior': behavior, 'expect': expect, 'pred_type': ptype, 'path': path, 'particle': particle, 'rule': rule,
         'construction': construction, 'placement': placement, 'placement_source': 'synthetic' if synth else 'r8', 'synthetic_words': synth, 'frame_source': 'synthetic_contract',
         'entry_expect': 'read' if behavior == 'read' else 'abstain', 'w3b6_expect': w3b6, 'plan_expect': plan_expect if plan_expect is not None else ('NOT_CALLED' if w3b6 == 'NOT_RUN' else w3b6), 'role_basis': basis, 'keyless_same': keyless_same,
         'note': (note + (' ' if note else '') + ('r8 では述語・語の一部が direct でない／型が違うので、作り物（synthetic_words）。r9 の状態は未知。' if synth else '')).strip()}
    ROWS.append(r)


PERSON = ['PERSON']
# ---------------------------------------------------------------------------------------------------------------------------------------
# the frames (all synthetic_contract: the roles of W3-a6 N2; 集める の に = goal, W3-a6 decision 2)
# ---------------------------------------------------------------------------------------------------------------------------------------
F_STAY = frame(が=[('agent', ['ARTIFACT', 'PERSON'])], に=[('place', ['PLACE'])])
F_REPORT = frame(が=[('agent', PERSON)], に=[('recipient', ['GROUP_ORG', 'PERSON'])])
F_HIT = frame(が=[('agent', ['ANIMAL', 'PERSON'])], を=[('patient', ['ARTIFACT', 'PLANT', 'SUBSTANCE_FOOD'])], で=[('instrument', ['ARTIFACT'])])
F_SURPRISE = frame(が=[('agent', ['ANIMAL', 'PERSON'])], で=[('cause', ['EVENT_ACT', 'NATURAL_PHENOMENON'])])
F_CHECK = frame(が=[('agent', ['GROUP_ORG', 'PERSON'])], を=[('patient', ['ABSTRACT', 'EVENT_ACT', 'INFO_LANGUAGE', 'WORK'])], で=[('place', ['PLACE'])],
                から=[('source', ['PLACE'])], へ=[('goal', ['PLACE'])])
F_GATHER = frame(が=[('agent', ['GROUP_ORG', 'PERSON'])], を=[('patient', ['ANIMAL', 'ARTIFACT', 'PERSON'])], に=[('goal', ['PLACE'])], から=[('source', ['PLACE'])], へ=[('goal', ['PLACE'])])
F_DIVIDE = frame(が=[('agent', PERSON)], を=[('patient', ['ARTIFACT', 'INFO_LANGUAGE', 'SUBSTANCE_FOOD'])], に=[('result', ['ARTIFACT'])])
F_WAIT = frame(が=[('agent', PERSON)], で=[('place', ['PLACE'])])
F_CARRY = frame(が=[('agent', ['GROUP_ORG', 'PERSON'])], を=[('patient', ['ARTIFACT'])], へ=[('goal', ['PLACE'])], から=[('source', ['PLACE'])])
F_RUN = frame(が=[('agent', ['ANIMAL', 'PERSON'])], に=[('goal', ['PLACE'])])
F_CUT = frame(が=[('agent', PERSON)], を=[('patient', ['PLANT', 'SUBSTANCE_FOOD'])], で=[('instrument', ['ARTIFACT'])])
F_WORK = frame(が=[('agent', PERSON)], で=[('place', ['PLACE'])])
F_PLACE_INSTR = frame(が=[('agent', PERSON)], を=[('patient', ['ARTIFACT', 'WORK', 'INFO_LANGUAGE'])], で=[('place', ['PLACE']), ('instrument', ['ARTIFACT'])])
F_PUSH = frame(が=[('agent', PERSON)], を=[('patient', ['ARTIFACT', 'PERSON'])], に=[('goal', ['PLACE'])], から=[('source', ['PLACE'])], へ=[('goal', ['PLACE'])])
F_CLIMB = frame(が=[('agent', PERSON)], に=[('goal', ['PLACE'])])

# ======================================================================================================================================
# N2: the 10 predicates, 11 lines of W3-a6
# ======================================================================================================================================
row('W3B6-N2-R-001', '船が港に停泊した。', rule='K273', particle='に', pred='停泊する', ptype='P_MOVE', nouns=['船', '港'], rf=F_STAY, path='R', w3b6='READ', behavior='read',
    roles={'agent': '船', 'place': '港'}, must_not=[{'clause': 0, 'role': 'goal', 'value': '港'}, {'clause': 0, 'role': 'recipient', 'value': '港'}],
    construction='停泊する の に=place（付加）。船 は ARTIFACT で、が の枠は ARTIFACT を宣言する（H271）', basis={'agent': 'role_frame:停泊する:が:ARTIFACT', 'place': 'role_frame:停泊する:に:PLACE'},
    note='N2 行 1: 停泊する に=place。基点では SUBJECT_TYPE_UNDETERMINED:船 で棄権する文。')
row('W3B6-N2-R-002', '住民が警察に通報した。', rule='K270', particle='に', pred='通報する', ptype='P_COMMUNICATE', nouns=['住民', '警察'], rf=F_REPORT, path='base', w3b6='NOT_RUN', behavior='read',
    roles={'agent': '住民', 'recipient': '警察'}, must_not=[{'clause': 0, 'role': 'goal', 'value': '警察'}], construction='通報する に=recipient。基点の読解器がそのまま読む（段 R に届かない）',
    keyless_same=True, note='N2 行 2。path は base（基点が読む）。枠を付けても出力は同じ。')
row('W3B6-N2-R-003', '社員が上司に連絡した。', rule='K270', particle='に', pred='連絡する', ptype='P_COMMUNICATE', nouns=['社員', '上司'], rf=F_REPORT, path='base', w3b6='NOT_RUN', behavior='read',
    roles={'agent': '社員', 'recipient': '上司'}, must_not=[{'clause': 0, 'role': 'goal', 'value': '上司'}], construction='連絡する に=recipient。基点が読む', keyless_same=True, note='N2 行 3。')
row('W3B6-N2-R-004', '大工が金槌で板を打った。', rule='K273', particle='で', pred='打つ', ptype='P_ACT', nouns=['大工', '金槌', '板'], rf=F_HIT, path='R', w3b6='READ', behavior='read',
    roles={'agent': '大工', 'patient': '板', 'instrument': '金槌'}, must_not=[{'clause': 0, 'role': 'place', 'value': '金槌'}, {'clause': 0, 'role': 'cause', 'value': '金槌'}],
    construction='打つ で=instrument（付加。金槌 は alias の腕で direct）', basis={'agent': 'placement_direct:PERSON', 'patient': 'placement_direct:ARTIFACT', 'instrument': 'role_frame:打つ:で:ARTIFACT'},
    note='N2 行 4: 打つ で=instrument。')
row('W3B6-N2-R-005', '妹が地震で驚いた。', rule='K273', particle='で', pred='驚く', ptype='P_EMOTION', nouns=['妹', '地震'], rf=F_SURPRISE, path='R', w3b6='READ', behavior='read',
    roles={'agent': '妹', 'cause': '地震'}, must_not=[{'clause': 0, 'role': 'place', 'value': '地震'}, {'clause': 0, 'role': 'instrument', 'value': '地震'}],
    construction='驚く で=cause（付加。地震 は seed で direct）', basis={'agent': 'placement_direct:PERSON', 'cause': 'role_frame:驚く:で:NATURAL_PHENOMENON'},
    note='N2 行 5: 驚く で=cause。原文の 物音 は r8 で UNPLACED（K272 の行 W3B6-K272-A-001）なので、r8 で direct の 地震 を使う。')
row('W3B6-N2-R-006', '係員が校庭で書類を確認した。', rule='K273', particle='で', pred='確認する', ptype='P_COGNITION', nouns=['係員', '校庭', '書類'], rf=F_CHECK, path='R', w3b6='READ', behavior='read',
    roles={'agent': '係員', 'patient': '書類', 'place': '校庭'}, must_not=[{'clause': 0, 'role': 'instrument', 'value': '校庭'}, {'clause': 0, 'role': 'cause', 'value': '校庭'}],
    construction='確認する（表が読まない型 P_COGNITION）で=place。が・を は枠が一意に宣言（H271）', basis={'agent': 'role_frame:確認する:が:PERSON', 'patient': 'role_frame:確認する:を:INFO_LANGUAGE', 'place': 'role_frame:確認する:で:PLACE'},
    note='N2 行 6: 確認する で=place。原文の 受付 は r8 で MULTIPLE（K272 の行）。校庭 は r8 で definition の腕を持つ direct PLACE で、読解器が で を曖昧と言う語。')
row('W3B6-N2-X-007', '先生が生徒を校庭に集めた。', rule='K273', particle='に', pred='集める', ptype='P_ACT', nouns=['先生', '生徒', '校庭'], rf=F_GATHER, path='R-blocked',
    w3b6='PLACEMENT_PREDICATE_POSSIBLY_DERIVED', plan_expect='READ', behavior='abstain',
    construction='集める に=goal（項）。段 R の計画は goal と読む（plan_expect=READ）が、入口の読み直しの K63 の門（head が派生動詞かもしれない: 下一段-マ行）が止める。この門は変えない',
    basis={'agent': 'placement_direct:PERSON', 'patient': 'placement_direct:PERSON', 'goal': 'role_frame:集める:に:PLACE'},
    note='N2 行 7: 計画では読めるが出力では NOT_READ:HEAD_DERIVED_GATE。同じ構成（に=goal、表の に の行が無い P_ACT）を 集める でない述語 押す で W3B6-N2-R-007b に置く。')
row('W3B6-N2-R-007b', '兄が箱を工場に押した。', rule='K273', particle='に', pred='押す', ptype='P_ACT', nouns=['兄', '箱', '工場'], rf=F_PUSH, path='R', w3b6='READ', behavior='read',
    roles={'agent': '兄', 'patient': '箱', 'goal': '工場'}, must_not=[{'clause': 0, 'role': 'place', 'value': '工場'}, {'clause': 0, 'role': 'time', 'value': '工場'}],
    construction='押す に=goal（項）。N2 行 7 と同じ構成（表の に の行が無い P_ACT）を、head の派生の門に掛からない述語で', basis={'agent': 'placement_direct:PERSON', 'patient': 'placement_direct:ARTIFACT', 'goal': 'role_frame:押す:に:PLACE'},
    note='N2 行 7 の代わりに、集める の門を避けた同じ構成。')
row('W3B6-N2-A-008', '店員が商品を箱に分けた。', rule='K270', particle='に', pred='分ける', ptype='P_CHANGE', nouns=['店員', '商品', '箱'], rf=F_DIVIDE, path='none', w3b6='PLACEMENT_W3B2_NOT_TRIGGERED', behavior='abstain',
    construction='分ける に=result。基点では に が result|beneficiary で、計画の引き金（U・U3）が掛からない（NOT_REACHED:TRIGGER_NONE）。K270 は入口を足さない',
    note='N2 行 8: NOT_REACHED:TRIGGER_NONE。未達として報告する（読めたとは書かない）。')
row('W3B6-N2-R-009', '友人が駅で待った。', rule='K270', particle='で', pred='待つ', ptype='P_EXIST', nouns=['友人', '駅'], rf=F_WAIT, path='base', w3b6='NOT_RUN', behavior='read',
    roles={'agent': '友人', 'place': '駅'}, must_not=[{'clause': 0, 'role': 'instrument', 'value': '駅'}], construction='待つ で=place。基点が読む', keyless_same=True, note='N2 行 9。')
row('W3B6-N2-R-010', '業者が倉庫から工場へ荷物を運んだ。', rule='K270', particle='へ', pred='運ぶ', ptype='P_MOVE', nouns=['業者', '倉庫', '工場', '荷物'], rf=F_CARRY, path='base', w3b6='NOT_RUN',
    behavior='read', roles={'agent': '業者', 'patient': '荷物', 'goal': '工場', 'source': '倉庫'}, must_not=[{'clause': 0, 'role': 'place', 'value': '工場'}],
    construction='運ぶ へ=goal・から=source（N2 行 10・11）。基点が読む', keyless_same=True, over={'荷物': {'top': ['ARTIFACT'], 'decided_by': ['seed']}},
    note='N2 行 10・11。荷物 は r8 で UNPLACED だが、基点の読解器は型を使わずに読む（枠を付けても同じ出力であることを見る行）。')

# ======================================================================================================================================
# K270: the entrance and the status
# ======================================================================================================================================
row('W3B6-K270-A-001', '大工が金槌で板を打った。', rule='K270', particle='で', pred='打つ', ptype='P_ACT', nouns=['大工', '金槌', '板'], rf=None, status='ESTIMATED', unconf='default', path='U3',
    w3b6='ROLE_FRAME_NOT_CONFIRMED:ESTIMATED', behavior='abstain', keyless_same=True, construction='role_frame_status=ESTIMATED（role_frame=null）。段 R は動かない', note='N2 行 4 の ESTIMATED 版。')
row('W3B6-K270-A-002', '妹が地震で驚いた。', rule='K270', particle='で', pred='驚く', ptype='P_EMOTION', nouns=['妹', '地震'], rf=None, status='NO_ROLE_FRAME', path='U3',
    w3b6='ROLE_FRAME_NOT_CONFIRMED:NO_ROLE_FRAME', behavior='abstain', keyless_same=True, construction='role_frame_status=NO_ROLE_FRAME。段 R は動かない', note='N2 行 5 の NO_ROLE_FRAME 版。')
row('W3B6-K270-A-003', '先生が生徒を校庭に集めた。', rule='K270', particle='に', pred='集める', ptype='P_ACT', nouns=['先生', '生徒', '校庭'], rf='ABSENT', path='U',
    w3b6='PLACEMENT_PARTICLE_NOT_IN_FRAME:P_ACT:に', behavior='abstain', keyless_same=True, construction='3 鍵なし（r8 の答え）。基点と同じ理由・同じ出力', note='N2 行 7 の鍵なし版。')
row('W3B6-K270-A-004', '板が大工に金槌で打たれた。', rule='K270', particle='で', pred='打つ', ptype='P_ACT', nouns=['大工', '金槌', '板'], rf=F_HIT, path='none',
    w3b6='PLACEMENT_W3B2_NOT_TRIGGERED', behavior='abstain', construction='受身（入口の外）。CONFIRMED の枠があっても読まない')
row('W3B6-K270-A-005', '大工が金槌でも板を打った。', rule='K270', particle='で', pred='打つ', ptype='P_ACT', nouns=['大工', '金槌', '板'], rf=F_HIT, path='U3',
    w3b6='PLACEMENT_FOCUS_PARTICLE_AFTER_CASE:で:も', behavior='abstain', construction='K186 の係助詞の門（段 R が読んだ後ろの門が止める）')
row('W3B6-K270-A-006', '大工が金槌とハンマーで板を打った。', rule='K270', particle='で', pred='打つ', ptype='P_ACT', nouns=['大工', '金槌', 'ハンマー', '板'], rf=F_HIT, path='none',
    w3b6='PLACEMENT_W3B2_NOT_TRIGGERED', behavior='abstain', construction='並立（入口の外）')
row('W3B6-K270-A-007', '大工が金槌で板を打つと言った。', rule='K270', particle='で', pred='打つ', ptype='P_ACT', nouns=['大工', '金槌', '板', '言う'], rf=F_HIT, path='none',
    w3b6='PLACEMENT_W3B2_NOT_TRIGGERED', behavior='abstain', construction='引用（入口の外）', over={'言う': {'top': ['P_COMMUNICATE'], 'namespace': 'P', 'decided_by': ['seed']}})
row('W3B6-K270-R-008', '兄が箱を工場に押した。', rule='K270', particle='に', pred='押す', ptype='P_ACT', nouns=['兄', '箱', '工場'], rf=F_PUSH, unconf='junk', path='R', w3b6='READ',
    behavior='read', roles={'agent': '兄', 'patient': '箱', 'goal': '工場'}, must_not=[{'clause': 0, 'role': 'place', 'value': '工場'}], construction='role_frame_unconfirmed が壊れた値（文字列）でも読みは変わらない（読まない）',
    basis={'agent': 'placement_direct:PERSON', 'patient': 'placement_direct:ARTIFACT', 'goal': 'role_frame:押す:に:PLACE'}, note='N2 行 7 b の role_frame_unconfirmed を壊した版。')
row('W3B6-K270-R-009', '大工が金槌で板を打った。', rule='K270', particle='で', pred='打つ', ptype='P_ACT', nouns=['大工', '金槌', '板'], rf=F_HIT, unconf={'で': 'garbage', '': [1, 2]}, path='R', w3b6='READ',
    behavior='read', roles={'agent': '大工', 'patient': '板', 'instrument': '金槌'}, must_not=[{'clause': 0, 'role': 'place', 'value': '金槌'}], construction='role_frame_unconfirmed の中身が契約外でも読まない',
    basis={'agent': 'placement_direct:PERSON', 'patient': 'placement_direct:ARTIFACT', 'instrument': 'role_frame:打つ:で:ARTIFACT'})
row('W3B6-K270-A-010', '先生が生徒を校庭に集めた。', rule='K270', particle='に', pred='集める', ptype='P_ACT', nouns=['先生', '生徒', '校庭'], rf=None, status='ESTIMATED', unconf={'に': [{'role': 'goal', 'reason': 'SPLIT'}]},
    path='U', w3b6='ROLE_FRAME_NOT_CONFIRMED:ESTIMATED', behavior='abstain', keyless_same=True, construction='ESTIMATED（role_frame_unconfirmed は付くが読まない）')

# ======================================================================================================================================
# K271: the particles (に で へ から と まで より; が・を は読まない)
# ======================================================================================================================================
row('W3B6-K271-R-001', '係員が病院から校庭で書類を確認した。', rule='K271', particle='から', pred='確認する', ptype='P_COGNITION', nouns=['係員', '病院', '校庭', '書類'], rf=F_CHECK, path='R', w3b6='READ',
    behavior='read', roles={'agent': '係員', 'patient': '書類', 'source': '病院', 'place': '校庭'}, must_not=[{'clause': 0, 'role': 'goal', 'value': '病院'}],
    construction='から（読解器が source と名づけた）を枠が source と一意に宣言。表は読まない型', basis={'agent': 'role_frame:確認する:が:PERSON', 'patient': 'role_frame:確認する:を:INFO_LANGUAGE',
    'source': 'role_frame:確認する:から:PLACE', 'place': 'role_frame:確認する:で:PLACE'})
row('W3B6-K271-R-002', '係員が病院へ校庭で書類を確認した。', rule='K271', particle='へ', pred='確認する', ptype='P_COGNITION', nouns=['係員', '病院', '校庭', '書類'], rf=F_CHECK, path='R', w3b6='READ',
    behavior='read', roles={'agent': '係員', 'patient': '書類', 'goal': '病院', 'place': '校庭'}, must_not=[{'clause': 0, 'role': 'recipient', 'value': '病院'}],
    construction='へ（読解器は recipient とした未対応の充填物）を枠が goal と宣言', basis={'agent': 'role_frame:確認する:が:PERSON', 'patient': 'role_frame:確認する:を:INFO_LANGUAGE',
    'goal': 'role_frame:確認する:へ:PLACE', 'place': 'role_frame:確認する:で:PLACE'})
row('W3B6-K271-R-003', '兄が箱を教室に押した。', rule='K271', particle='に', pred='押す', ptype='P_ACT', nouns=['兄', '箱', '教室'], rf=F_PUSH, path='R', w3b6='READ', behavior='read',
    roles={'agent': '兄', 'patient': '箱', 'goal': '教室'}, must_not=[{'clause': 0, 'role': 'place', 'value': '教室'}], construction='に。教室 は role@ の腕だけの direct PLACE だが goal は項（K275）なので読める',
    basis={'agent': 'placement_direct:PERSON', 'patient': 'placement_direct:ARTIFACT', 'goal': 'role_frame:押す:に:PLACE'})
row('W3B6-K271-R-004', '兄が公園に走った。', rule='K271', particle='に', pred='走る', ptype='P_MOVE', nouns=['兄', '公園'], rf=F_RUN, path='R', w3b6='READ', behavior='read',
    roles={'agent': '兄', 'goal': '公園'}, must_not=[{'clause': 0, 'role': 'time', 'value': '公園'}, {'clause': 0, 'role': 'recipient', 'value': '公園'}],
    construction='P_MOVE の に の行は time（TIME）だけ。表は PLACE を読まない（NO_OPINION）→ 枠 goal', basis={'agent': 'placement_direct:PERSON', 'goal': 'role_frame:走る:に:PLACE'})
row('W3B6-K271-A-005', '船が港に停泊した。', rule='K271', particle='が', pred='停泊する', ptype='P_MOVE', nouns=['船', '港'], rf=frame(に=[('place', ['PLACE'])]), path='U',
    w3b6='ROLE_FRAME_PARTICLE_NOT_DECLARED:が', behavior='abstain', construction='が は枠に無い。表が確かめていない名前（agent）は枠の一意の確認なしに残さない（H271）')
row('W3B6-K271-A-006', '船が港に停泊した。', rule='K271', particle='が', pred='停泊する', ptype='P_MOVE', nouns=['船', '港'], rf=frame(が=[('agent', ['PERSON'])], に=[('place', ['PLACE'])]), path='U',
    w3b6='ROLE_FRAME_TYPE_NOT_DECLARED:が:ARTIFACT', behavior='abstain', construction='が の枠は PERSON だけで、船 は ARTIFACT（0 件）')
row('W3B6-K271-A-007', '船が港に停泊した。', rule='K271', particle='が', pred='停泊する', ptype='P_MOVE', nouns=['船', '港'], rf=frame(が=[('patient', ['ARTIFACT', 'PERSON'])], に=[('place', ['PLACE'])]), path='U',
    w3b6='ROLE_FRAME_TABLE_CONFLICT:が:agent:patient', behavior='abstain', construction='枠が が に別の役割（patient）を一意に宣言: 読解器の名前 agent と食い違い（K274）。枠は表を上書きしない')
row('W3B6-K271-A-008', '係員が病院から校庭で書類を確認した。', rule='K271', particle='を', pred='確認する', ptype='P_COGNITION', nouns=['係員', '病院', '校庭', '書類'],
    rf=frame(が=[('agent', ['PERSON'])], で=[('place', ['PLACE'])], から=[('source', ['PLACE'])]), path='U3', w3b6='ROLE_FRAME_PARTICLE_NOT_DECLARED:を', behavior='abstain',
    construction='を は枠に無い（読解器の名前 patient は枠の確認が無ければ残さない）')

# ======================================================================================================================================
# K272: the filler (direct, one type)
# ======================================================================================================================================
row('W3B6-K272-A-001', '妹が物音で驚いた。', rule='K272', particle='で', pred='驚く', ptype='P_EMOTION', nouns=['妹', '物音'], rf=F_SURPRISE, path='U3',
    w3b6='ROLE_FRAME_FILLER_NOT_DIRECT:で:PLACEMENT_UNPLACED', behavior='abstain', construction='物音 は r8 で UNPLACED', note='N2 行 5 の原文（物音）。')
row('W3B6-K272-A-002', '係員が受付で書類を確認した。', rule='K272', particle='で', pred='確認する', ptype='P_COGNITION', nouns=['係員', '受付', '書類'], rf=F_CHECK, path='U3',
    w3b6='ROLE_FRAME_FILLER_NOT_DIRECT:で:PLACEMENT_MULTIPLE', behavior='abstain', construction='受付 は r8 で MULTIPLE [IDENTIFIER, PLACE]', note='N2 行 6 の原文（受付）。')
row('W3B6-K272-A-003', '大工が釘で板を打った。', rule='K272', particle='で', pred='打つ', ptype='P_ACT', nouns=['大工', '釘', '板'], rf=F_HIT, path='U3',
    w3b6='ROLE_FRAME_FILLER_NOT_DIRECT:で:PLACEMENT_ESTIMATED_GENERATED', behavior='abstain', construction='釘 は r8 で estimated（generated）')
row('W3B6-K272-A-004', '大工が金槌で板を打った。', rule='K272', particle='で', pred='打つ', ptype='P_ACT', nouns=['大工', '板'], rf=F_HIT, path='U3',
    w3b6='ROLE_FRAME_FILLER_NOT_DIRECT:で:PLACEMENT_UNKNOWN', behavior='abstain', construction='金槌 の答えが UNKNOWN（問い合わせの答えが無い語）。r8 では direct の語を UNKNOWN にした作り物',
    over={'金槌': {'state': 'UNKNOWN'}})
row('W3B6-K272-A-005', '大工が金槌で板を打った。', rule='K272', particle='で', pred='打つ', ptype='P_ACT', nouns=['大工', '板'], rf=F_HIT, path='U3',
    w3b6='ROLE_FRAME_FILLER_NOT_DIRECT:で:PLACEMENT_MULTIPLE', behavior='abstain', construction='金槌 が MULTIPLE [ARTIFACT, PLACE]（枠の で が ARTIFACT を宣言しても候補は決まらない）。r8 では direct の語を割った作り物',
    over={'金槌': {'top': ['ARTIFACT', 'PLACE'], 'decided_by': ['alias']}})
row('W3B6-K272-A-006', '大工が金槌で板を打った。', rule='K272', particle='で', pred='打つ', ptype='P_ACT', nouns=['大工', '板'], rf=F_HIT, path='U3',
    w3b6='ROLE_FRAME_FILLER_NOT_DIRECT:で:PLACEMENT_NO_PLACEMENT', behavior='abstain', construction='金槌 が NO_PLACEMENT（配置なしの答え）。作り物',
    over={'金槌': {'state': 'NO_PLACEMENT'}})

# ======================================================================================================================================
# K272 + 4(c): a word of relative position (右 左): RELATIVE_POSITION direct, and MULTIPLE [PLACE, RELATIVE_POSITION]
# ======================================================================================================================================
RELP_DIRECT = {'top': ['RELATIVE_POSITION'], 'decided_by': ['role@codex:narrative', 'role@jawiki']}
RELP_MULTI = {'top': ['PLACE', 'RELATIVE_POSITION'], 'decided_by': ['role@codex:narrative', 'role@jawiki']}
rel_sources = [('W3B4-ACT-A-901', '兄が右で打った。', ['兄'], '打つ', 'P_ACT'), ('W3B4-ACT-A-902', '兄が右で皿を洗った。', ['兄', '皿'], '洗う', 'P_ACT'),
               ('W3B4-ACT-A-903', '兄が右で皿を拭いた。', ['兄', '皿'], '拭く', 'P_ACT'), ('W3B4-CREATE-A-901', '兄が右で絵を描いた。', ['兄', '絵'], '描く', 'P_CREATE'),
               ('W3B4-CREATE-A-902', '弟が右で記事を書いた。', ['弟', '記事'], '書く', 'P_CREATE')]
for n, (src, text, ns, pred, pt) in enumerate(rel_sources, 1):
    for kind, spec, why in (('D', RELP_DIRECT, 'ROLE_FRAME_FILLER_RELATIVE_POSITION:で'), ('M', RELP_MULTI, 'ROLE_FRAME_FILLER_NOT_DIRECT:で:PLACEMENT_MULTIPLE')):
        row('W3B6-K272-A-1%s%02d' % (kind, n), text, rule='K272', particle='で', pred=pred, ptype=pt, nouns=ns + ['右'], rf=F_PLACE_INSTR, path='U3', w3b6=why, behavior='abstain',
            construction='右 = %s（枠は で に PLACE を宣言する: 枠が寛容でも棄権する）。出典 %s（W3-b4 の束 d）' % ('RELATIVE_POSITION direct' if kind == 'D' else 'MULTIPLE [PLACE, RELATIVE_POSITION]', src),
            over={'右': spec}, note='4(c)。r9 では 右 が RELATIVE_POSITION か MULTIPLE になる見込みの形を偽の答えで与える（r8 では direct の PLACE）。')
row('W3B6-K272-A-2D01', '監督が左で騒いだ。', rule='K272', particle='で', pred='騒ぐ', ptype='P_ACT', nouns=['監督', '左'], rf=F_PLACE_INSTR, path='U3',
    w3b6='ROLE_FRAME_FILLER_RELATIVE_POSITION:で', behavior='abstain', construction='左 = RELATIVE_POSITION direct。出典 W3-b5 の反例の型（W3B5-DEPLACE-A-045 の 左 で）',
    over={'左': RELP_DIRECT, '騒ぐ': {'top': ['P_ACT'], 'namespace': 'P', 'decided_by': ['seed']}}, note='4(c)。')
row('W3B6-K272-A-2D02', '店員が左に昇った。', rule='K272', particle='に', pred='昇る', ptype='P_MOVE', nouns=['店員', '左'], rf=F_CLIMB, path='U', w3b6='ROLE_FRAME_FILLER_RELATIVE_POSITION:に',
    behavior='abstain', construction='左 = RELATIVE_POSITION direct の に（goal を宣言する枠）。出典 W3B5-NIGOAL-A-021', over={'左': RELP_DIRECT}, note='4(c)。')
row('W3B6-K272-A-2M03', '店員が左に昇った。', rule='K272', particle='に', pred='昇る', ptype='P_MOVE', nouns=['店員', '左'], rf=F_CLIMB, path='U', w3b6='PLACEMENT_MULTIPLE:に:左',
    behavior='abstain', construction='左 = MULTIPLE [PLACE, RELATIVE_POSITION] の に。表が に の行（time）を持つ型なので、計画の理由 PLACEMENT_MULTIPLE で止まる（H273: 段 R は上書きしない）',
    over={'左': RELP_MULTI}, note='4(c)。')

# ======================================================================================================================================
# K273: how it is decided (0 / 2+ / not declared / invalid)
# ======================================================================================================================================
row('W3B6-K273-A-001', '大工が壁で板を打った。', rule='K273', particle='で', pred='打つ', ptype='P_ACT', nouns=['大工', '壁', '板'], rf=F_HIT, path='U3', w3b6='ROLE_FRAME_TYPE_NOT_DECLARED:で:PLACE',
    behavior='abstain', construction='で の枠は instrument [ARTIFACT] だけで、壁 は PLACE（0 件）')
row('W3B6-K273-A-002', '大工が金槌で板を打った。', rule='K273', particle='で', pred='打つ', ptype='P_ACT', nouns=['大工', '金槌', '板'],
    rf=frame(が=[('agent', PERSON)], を=[('patient', ['ARTIFACT'])], で=[('instrument', ['ARTIFACT']), ('cause', ['ARTIFACT'])]), path='U3', w3b6='ROLE_FRAME_SPLIT:で:ARTIFACT', behavior='abstain',
    construction='で の枠が instrument と cause の両方に ARTIFACT を宣言（2 件）')
row('W3B6-K273-A-003', '大工が金槌で板を打った。', rule='K273', particle='で', pred='打つ', ptype='P_ACT', nouns=['大工', '金槌', '板'], rf=frame(が=[('agent', PERSON)], を=[('patient', ['ARTIFACT'])]), path='U3',
    w3b6='ROLE_FRAME_PARTICLE_NOT_DECLARED:で', behavior='abstain', construction='で が枠に無い')
row('W3B6-K273-A-004', '先生が生徒を校庭に集めた。', rule='K273', particle='に', pred='集める', ptype='P_ACT', nouns=['先生', '生徒', '校庭'], rf=frame(が=[('agent', PERSON)], を=[('patient', ['PERSON'])], で=[('place', ['PLACE'])]),
    path='U', w3b6='ROLE_FRAME_PARTICLE_NOT_DECLARED:に', behavior='abstain', construction='に が枠に無い（で だけ宣言）')
row('W3B6-K273-A-005', '先生が生徒を校庭に集めた。', rule='K273', particle='に', pred='集める', ptype='P_ACT', nouns=['先生', '生徒', '校庭'],
    rf=frame(が=[('agent', PERSON)], を=[('patient', ['PERSON'])], に=[('goal', ['PLACE']), ('place', ['PLACE'])]), path='U', w3b6='ROLE_FRAME_SPLIT:に:PLACE', behavior='abstain',
    construction='に の枠が goal と place の両方に PLACE を宣言（同じ型の別の役割を枠で分けられない: K220 の形）')
INV = [  # (suffix, status, role_frame value, expected problem)
    ('01', 'CONFIRMED', [], 'NOT_A_MAPPING'),
    ('02', 'CONFIRMED', None, 'NOT_A_MAPPING'),
    ('03', 'CONFIRMED', {'は': [{'role': 'agent', 'types': ['PERSON']}]}, 'PARTICLE_NOT_CASE:は'),
    ('04', 'CONFIRMED', {'で': [{'role': 'tool', 'types': ['ARTIFACT']}]}, 'ROLE_NOT_IN_CONVENTION:で:tool'),
    ('05', 'CONFIRMED', {'で': [{'role': 'instrument', 'types': ['RELATIVE_POSITION']}]}, 'TYPE_NOT_NOUN:で:RELATIVE_POSITION'),
    ('06', 'CONFIRMED', {'で': [{'role': 'instrument', 'types': []}]}, 'TYPES_NOT_A_LIST:で'),
    ('07', 'CONFIRMED', {'で': ['instrument']}, 'ENTRY_NOT_A_MAPPING:で'),
    ('08', 'CONFIRMED', {'で': [{'role': 'instrument', 'types': ['ARTIFACT']}, {'role': 'instrument', 'types': ['PLACE']}]}, 'ROLE_DUPLICATED:で:instrument'),
    ('09', 'MAYBE', {'で': [{'role': 'instrument', 'types': ['ARTIFACT']}]}, 'STATUS_UNKNOWN'),
    ('10', 'CONFIRMED', {'で': [{'role': 'instrument', 'types': ['ARTIFACT'], 'extra': 1}]}, 'ENTRY_KEYS:で'),
    ('11', 'CONFIRMED', {'で': {'role': 'instrument', 'types': ['ARTIFACT']}}, 'ENTRIES_NOT_A_LIST:で'),
    ('12', 'ESTIMATED', {'で': [{'role': 'instrument', 'types': ['ARTIFACT']}]}, 'FRAME_WITHOUT_CONFIRMED'),
    ('13', 'CONFIRMED', {'で': [{'role': 'instrument', 'types': 'ARTIFACT'}]}, 'TYPES_NOT_A_LIST:で'),
]
for suf, st, val, prob in INV:
    row('W3B6-K273-A-9' + suf, '大工が金槌で板を打った。', rule='K273', particle='で', pred='打つ', ptype='P_ACT', nouns=['大工', '金槌', '板'], rf=val, status=st, path='U3',
        w3b6='ROLE_FRAME_INVALID:' + prob, behavior='abstain', construction='契約外の形（4(d)）: %s' % prob, note='文全体を棄権（黙って読まない）。')
row('W3B6-K273-A-914', '大工が金槌で板を打った。', rule='K273', particle='で', pred='打つ', ptype='P_ACT', nouns=['大工', '金槌', '板'], rf='ABSENT', path='U3', w3b6='PLACEMENT_PARTICLE_NOT_IN_FRAME:P_ACT:で',
    behavior='abstain', construction='MISSING_ROLE_FRAME の対照: 3 鍵なしは基点と同じ（問題にならない）。MISSING は答えを直接作る単体テストで見る', keyless_same=True)

# ======================================================================================================================================
# K274: the table is not overwritten (agree: the reading of the table stays; conflict: the sentence is refused)
# ======================================================================================================================================
row('W3B6-K274-R-001', '兄が箱を倉庫から工場に押した。', rule='K274', particle='から', pred='押す', ptype='P_ACT', nouns=['兄', '箱', '倉庫', '工場'], rf=F_PUSH, path='R', w3b6='READ',
    behavior='read', roles={'agent': '兄', 'patient': '箱', 'source': '倉庫', 'goal': '工場'}, must_not=[{'clause': 0, 'role': 'place', 'value': '工場'}],
    construction='から は表が source と読み（P_ACT の から の行）、に は枠が goal。表の読みと枠が一致', basis={'agent': 'placement_direct:PERSON', 'patient': 'placement_direct:ARTIFACT',
    'source': 'placement_direct:PLACE', 'goal': 'role_frame:押す:に:PLACE'})
row('W3B6-K274-R-002', '兄が箱を倉庫から工場へ押した。', rule='K274', particle='へ', pred='押す', ptype='P_ACT', nouns=['兄', '箱', '倉庫', '工場'], rf=F_PUSH, path='W3-b4', w3b6='READ',
    behavior='read', roles={'agent': '兄', 'patient': '箱', 'source': '倉庫', 'goal': '工場'}, must_not=[{'clause': 0, 'role': 'place', 'value': '工場'}],
    construction='表が全部読む（W3-b4）。枠は一致するので読みはそのまま（role_basis も表のまま）', keyless_same=True, basis={'agent': 'placement_direct:PERSON', 'patient': 'placement_direct:ARTIFACT',
    'source': 'placement_direct:PLACE', 'goal': 'placement_direct:PLACE'})
row('W3B6-K274-A-003', '兄が箱を倉庫から工場へ押した。', rule='K274', particle='から', pred='押す', ptype='P_ACT', nouns=['兄', '箱', '倉庫', '工場'],
    rf=frame(が=[('agent', PERSON)], を=[('patient', ['ARTIFACT'])], から=[('goal', ['PLACE'])], へ=[('goal', ['PLACE'])]), path='W3-b4', w3b6='ROLE_FRAME_TABLE_CONFLICT:から:source:goal',
    behavior='abstain', construction='表が source と読んだ から を、枠が goal と一意に宣言（場合 A）: 黙って上書きしない・黙って通さない。基点では読める文')
row('W3B6-K274-A-004', '兄が箱を倉庫から工場へ押した。', rule='K274', particle='が', pred='押す', ptype='P_ACT', nouns=['兄', '箱', '倉庫', '工場'],
    rf=frame(が=[('patient', PERSON)], を=[('patient', ['ARTIFACT'])], から=[('source', ['PLACE'])], へ=[('goal', ['PLACE'])]), path='W3-b4', w3b6='ROLE_FRAME_TABLE_CONFLICT:が:agent:patient',
    behavior='abstain', construction='表が agent と読んだ が を、枠が patient と宣言（が は読まないが検査には使う: K271 の但し書き）')
row('W3B6-K274-A-005', '兄が箱を倉庫から工場に押した。', rule='K274', particle='から', pred='押す', ptype='P_ACT', nouns=['兄', '箱', '倉庫', '工場'],
    rf=frame(が=[('agent', PERSON)], を=[('patient', ['ARTIFACT'])], に=[('goal', ['PLACE'])], から=[('goal', ['PLACE'])]), path='U', w3b6='ROLE_FRAME_TABLE_CONFLICT:から:source:goal',
    behavior='abstain', construction='場合 B の中の表の読み（から source）と枠（から goal）の食い違い')
row('W3B6-K274-A-006', '兄が箱を倉庫から工場に押した。', rule='K274', particle='を', pred='押す', ptype='P_ACT', nouns=['兄', '箱', '倉庫', '工場'],
    rf=frame(が=[('agent', PERSON)], を=[('goal', ['ARTIFACT'])], に=[('goal', ['PLACE'])], から=[('source', ['PLACE'])]), path='U', w3b6='ROLE_FRAME_TABLE_CONFLICT:を:patient:goal',
    behavior='abstain', construction='場合 B で、表が patient と読んだ を を枠が goal と宣言')

# ======================================================================================================================================
# K275: kind (arg / adjunct): an adjunct whose arms are all role@ is not used; an argument is
# ======================================================================================================================================
row('W3B6-K275-A-001', '大工が帽子で板を打った。', rule='K275', particle='で', pred='打つ', ptype='P_ACT', nouns=['大工', '帽子', '板'], rf=F_HIT, path='U3',
    w3b6='ROLE_FRAME_FILLER_NOT_DIRECT:で:PLACEMENT_SLOT_EVIDENCE_ONLY', behavior='abstain', construction='instrument は付加（H274）。帽子 は role@ の腕だけの direct ARTIFACT')
row('W3B6-K275-A-002', '係員が廊下で書類を確認した。', rule='K275', particle='で', pred='確認する', ptype='P_COGNITION', nouns=['係員', '廊下', '書類'], rf=F_CHECK, path='U3',
    w3b6='ROLE_FRAME_FILLER_NOT_DIRECT:で:PLACEMENT_SLOT_EVIDENCE_ONLY', behavior='abstain', construction='place は付加（表の値）。廊下 は role@ の腕だけの direct PLACE')
row('W3B6-K275-A-003', '弟が試験で泣いた。', rule='K275', particle='で', pred='泣く', ptype='P_EMOTION', nouns=['弟', '試験'], rf=F_SURPRISE, path='U3',
    w3b6='ROLE_FRAME_FILLER_NOT_DIRECT:で:PLACEMENT_SLOT_EVIDENCE_ONLY', behavior='abstain', construction='cause は付加（H274）。試験 は role@ の腕だけの direct EVENT_ACT')
row('W3B6-K275-R-004', '弟が洪水で泣いた。', rule='K275', particle='で', pred='泣く', ptype='P_EMOTION', nouns=['弟', '洪水'], rf=F_SURPRISE, path='R', w3b6='READ', behavior='read',
    roles={'agent': '弟', 'cause': '洪水'}, must_not=[{'clause': 0, 'role': 'place', 'value': '洪水'}, {'clause': 0, 'role': 'instrument', 'value': '洪水'}], construction='cause（付加）。洪水 は seed の腕で direct',
    basis={'agent': 'placement_direct:PERSON', 'cause': 'role_frame:泣く:で:NATURAL_PHENOMENON'})
row('W3B6-K275-R-005', '兄が地震で驚いた。', rule='K275', particle='で', pred='驚く', ptype='P_EMOTION', nouns=['兄', '地震'], rf=F_SURPRISE, path='R', w3b6='READ', behavior='read',
    roles={'agent': '兄', 'cause': '地震'}, must_not=[{'clause': 0, 'role': 'place', 'value': '地震'}], construction='cause（付加）。地震 は seed',
    basis={'agent': 'placement_direct:PERSON', 'cause': 'role_frame:驚く:で:NATURAL_PHENOMENON'})

# ======================================================================================================================================
# K276: two fillers of the same particle
# ======================================================================================================================================
row('W3B6-K276-A-001', '船が港に岸に停泊した。', rule='K276', particle='に', pred='停泊する', ptype='P_MOVE', nouns=['船', '港', '岸'], rf=F_STAY, path='U', w3b6='ROLE_FRAME_MULTIPLE_FILLERS:に',
    behavior='abstain', construction='に の充填物が 2 つ（港・岸）。どちらも place と宣言されるが、1 つの役割に 2 つは読まない')
row('W3B6-K276-A-002', '兄が公園に駅に走った。', rule='K276', particle='に', pred='走る', ptype='P_MOVE', nouns=['兄', '公園', '駅'], rf=F_RUN, path='U', w3b6='ROLE_FRAME_MULTIPLE_FILLERS:に',
    behavior='abstain', construction='に の充填物が 2 つ（公園・駅）。どちらも goal と宣言されるが 1 つの役割に 2 つは読まない')
row('W3B6-K276-A-003', '鳥が山に川に飛んだ。', rule='K276', particle='に', pred='飛ぶ', ptype='P_MOVE', nouns=['鳥', '山', '川'], rf=F_RUN, path='U', w3b6='ROLE_FRAME_MULTIPLE_FILLERS:に',
    behavior='abstain', construction='に の充填物が 2 つ（山・川）')
row('W3B6-K276-A-004', '弟が公園に庭に走った。', rule='K276', particle='に', pred='走る', ptype='P_MOVE', nouns=['弟', '公園', '庭'], rf=F_RUN, path='U', w3b6='ROLE_FRAME_MULTIPLE_FILLERS:に',
    behavior='abstain', construction='に の充填物が 2 つ（公園・庭）')

# ======================================================================================================================================
# more rows that stage R reads (the same constructions, other words)
# ======================================================================================================================================
def more(rid, text, pred, ptype, nouns, rf, roles, basis, particle, must_not):
    row(rid, text, rule='K273', particle=particle, pred=pred, ptype=ptype, nouns=nouns, rf=rf, path='R', w3b6='READ', behavior='read', roles=roles, basis=basis, must_not=must_not,
        construction='段 R が読む（枠が役割を一意に宣言。充填物は direct の 1 型）')
more('W3B6-K273-R-001', '船が湖に停泊した。', '停泊する', 'P_MOVE', ['船', '湖'], F_STAY, {'agent': '船', 'place': '湖'}, {'agent': 'role_frame:停泊する:が:ARTIFACT', 'place': 'role_frame:停泊する:に:PLACE'}, 'に',
     [{'clause': 0, 'role': 'goal', 'value': '湖'}])
more('W3B6-K273-R-002', '兄が箱を体育館に押した。', '押す', 'P_ACT', ['兄', '箱', '体育館'], F_PUSH, {'agent': '兄', 'patient': '箱', 'goal': '体育館'},
     {'agent': 'placement_direct:PERSON', 'patient': 'placement_direct:ARTIFACT', 'goal': 'role_frame:押す:に:PLACE'}, 'に', [{'clause': 0, 'role': 'place', 'value': '体育館'}])
more('W3B6-K273-R-003', '母が金槌で板を打った。', '打つ', 'P_ACT', ['母', '金槌', '板'], F_HIT, {'agent': '母', 'patient': '板', 'instrument': '金槌'},
     {'agent': 'placement_direct:PERSON', 'patient': 'placement_direct:ARTIFACT', 'instrument': 'role_frame:打つ:で:ARTIFACT'}, 'で', [{'clause': 0, 'role': 'place', 'value': '金槌'}])
more('W3B6-K273-R-004', '大工がタガネで板を打った。', '打つ', 'P_ACT', ['大工', 'タガネ', '板'], F_HIT, {'agent': '大工', 'patient': '板', 'instrument': 'タガネ'},
     {'agent': 'placement_direct:PERSON', 'patient': 'placement_direct:ARTIFACT', 'instrument': 'role_frame:打つ:で:ARTIFACT'}, 'で', [{'clause': 0, 'role': 'cause', 'value': 'タガネ'}])
more('W3B6-K273-R-005', '職員が校庭で書類を確認した。', '確認する', 'P_COGNITION', ['職員', '校庭', '書類'], F_CHECK, {'agent': '職員', 'patient': '書類', 'place': '校庭'},
     {'agent': 'role_frame:確認する:が:PERSON', 'patient': 'role_frame:確認する:を:INFO_LANGUAGE', 'place': 'role_frame:確認する:で:PLACE'}, 'で', [{'clause': 0, 'role': 'instrument', 'value': '校庭'}])
more('W3B6-K273-R-006', '弟が事故で泣いた。', '泣く', 'P_EMOTION', ['弟', '事故'], F_SURPRISE, {'agent': '弟', 'cause': '事故'},
     {'agent': 'placement_direct:PERSON', 'cause': 'role_frame:泣く:で:EVENT_ACT'}, 'で', [{'clause': 0, 'role': 'place', 'value': '事故'}])
more('W3B6-K273-R-007', '妹が雷で驚いた。', '驚く', 'P_EMOTION', ['妹', '雷'], F_SURPRISE, {'agent': '妹', 'cause': '雷'},
     {'agent': 'placement_direct:PERSON', 'cause': 'role_frame:驚く:で:NATURAL_PHENOMENON'}, 'で', [{'clause': 0, 'role': 'instrument', 'value': '雷'}])
more('W3B6-K273-R-008', '弟が公園に走った。', '走る', 'P_MOVE', ['弟', '公園'], F_RUN, {'agent': '弟', 'goal': '公園'},
     {'agent': 'placement_direct:PERSON', 'goal': 'role_frame:走る:に:PLACE'}, 'に', [{'clause': 0, 'role': 'time', 'value': '公園'}])
more('W3B6-K273-R-009', '兄が箱を倉庫に押した。', '押す', 'P_ACT', ['兄', '箱', '倉庫'], F_PUSH, {'agent': '兄', 'patient': '箱', 'goal': '倉庫'},
     {'agent': 'placement_direct:PERSON', 'patient': 'placement_direct:ARTIFACT', 'goal': 'role_frame:押す:に:PLACE'}, 'に', [{'clause': 0, 'role': 'place', 'value': '倉庫'}])

with open(OUT, 'w', encoding='utf-8') as f:
    for r in ROWS: f.write(json.dumps(r, ensure_ascii=False) + '\n')
print('rows', len(ROWS), 'read', sum(1 for r in ROWS if r['behavior'] == 'read'), 'abstain', sum(1 for r in ROWS if r['behavior'] == 'abstain'))

# the trigger of the reader as it is (recorded; nothing of it is used to decide an expectation)
import collections
bad = []
for r in ROWS:
    ex = SR.typed_explain_ja(r['input'], W.query_of(r))
    trig = ex['w3b1_trigger'] or ex['w3b2_trigger']
    r['base_trigger'] = trig
    if r['behavior'] == 'abstain' and r['path'] in ('U', 'U3', 'none'):
        want = None if r['path'] == 'none' else r['path']
        if trig != want: bad.append((r['id'], 'path', r['path'], 'trigger', trig))
with open(OUT, 'w', encoding='utf-8') as f:
    for r in ROWS: f.write(json.dumps(r, ensure_ascii=False) + '\n')
print('trigger mismatches', bad)
