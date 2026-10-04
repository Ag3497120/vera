#!/usr/bin/env python3
"""W3-b6 (docs 10I H276): can a sentence with to / made / yori reach stage R through the entrance of the plan (the triggers of W3-b1 / W3-b2)? Each sentence is run with a CONFIRMED frame
that declares every particle, and the trigger and the diagnosis are printed. Usage: PYTHONPATH=<tree> python artifacts/w3-b6/tools/reach_particles.py"""
import sys
sys.path.insert(0, 'tests/reading_soundness')
import w3b6_fakes as W
from verantyx import semantic_read as SR
FRAME = {p: [{'role': r, 'types': t}] for p, r, t in (('が', 'agent', ['PERSON']), ('を', 'patient', ['ARTIFACT', 'INFO_LANGUAGE']), ('で', 'place', ['PLACE']), ('に', 'goal', ['PLACE']), ('へ', 'goal', ['PLACE']),
                                                       ('から', 'source', ['PLACE']), ('と', 'companion', ['PERSON']), ('まで', 'goal', ['PLACE']), ('より', 'standard', ['PLACE']))}
NOUNS = {'係員': ['PERSON'], '上司': ['PERSON'], '駅': ['PLACE'], '校庭': ['PLACE'], '書類': ['INFO_LANGUAGE'], '箱': ['ARTIFACT'], '兄': ['PERSON'], '倉庫': ['PLACE'], '前年': ['TIME']}
SENTENCES = [('係員が上司と校庭で書類を確認した。', '確認する', 'P_COGNITION'), ('係員が駅まで校庭で書類を確認した。', '確認する', 'P_COGNITION'), ('係員が倉庫より校庭で書類を確認した。', '確認する', 'P_COGNITION'),
             ('兄が駅まで箱を押した。', '押す', 'P_ACT'), ('兄が上司と箱を押した。', '押す', 'P_ACT'), ('兄が倉庫より箱を押した。', '押す', 'P_ACT'), ('兄が駅まで校庭に箱を押した。', '押す', 'P_ACT'),
             ('兄が上司と校庭に箱を押した。', '押す', 'P_ACT')]
for text, pred, ptype in SENTENCES:
    ans = {w: {'top': t, 'decided_by': ['seed']} for w, t in NOUNS.items()}
    ans[pred] = {'top': [ptype], 'namespace': 'P', 'decided_by': ['seed'], 'role_frame_status': 'CONFIRMED', 'role_frame': FRAME, 'role_frame_unconfirmed': None}
    row = {'placement': ans}
    ex = SR.typed_explain_ja(text, W.query_of(row))
    out = SR.read(text, placement=W.query_of(row))
    print('%s trigger=%s/%s w3b2=%s entry=%s' % (text, ex['w3b1_trigger'], ex['w3b2_trigger'], ex['w3b2'], 'READ' if out['readable'] else 'ABSTAIN ' + str(out['abstain']['reasons'])))
