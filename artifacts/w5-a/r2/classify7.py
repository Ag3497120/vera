# W5-a round 2: classification of the seven existing tests the auditor's decision B3 names (written for this round; not the prototype's script)
import json
from verantyx import semantic_read as SR, semantic_reader as R
from verantyx.frames import transitivity
ROWS = [('test_routing_from_text_entry.py::test_T1_...', ['モモがテストを書く。', 'セキがコードを確かめる。', 'モモは検証をやらない。']),
        ('test_routing_from_text_regress.py::test_M1_...', ['セキがレビューをやる。']),
        ('test_observe_data.py::...[S-J06]', ['車掌は乗客に切符を渡した。']),
        ('test_observe_data.py::...[S-J07]', ['受付は客に鍵を渡した。']),
        ('test_observe_data.py::...[S-J13]', ['農家は市場で果物を売った。']),
        ('test_observe_data.py::...[S-J21]', ['会計係は領収書を発行しなかった。']),
        ('test_observe_data.py::...[M12-single-J05]', ['駅員は乗客に切符を渡した。', '車掌は乗客に切符を渡した。'])]
CLASSES = ['_TRANSFER_PREDICATES', '_SHARING_PREDICATES', '_CHANGE_PREDICATES', '_SELECTION_PREDICATES', '_PROCESSING_PREDICATES', '_PRODUCT_PREDICATES',
           '_CONTAINMENT_PREDICATES', '_PLACEMENT_PREDICATES']
import verantyx.semantic_read as m
print('module', m.__file__)
for node, texts in ROWS:
    for t in texts:
        o = SR.read(t)
        pred = [c['predicate'] for c in o['clauses']]
        subj = [c['roles'].get('agent') for c in o['clauses']]
        p = pred[0] if pred else None
        tr = transitivity(p) if p else None
        cls = [n for n in CLASSES if p and p in getattr(R, n)]
        pers = [R._is_person_phrase(x) for x in subj if x]
        print(node, t, 'pred=%s' % p, 'transitivity=%s' % tr, 'classes=%s' % cls, 'subject_is_person=%s' % pers,
              'frame_known=%s' % (SR._object_frame_known(p, R, transitivity) if p else None),
              'readable=%s' % o['readable'], 'abstain=%s' % (o['abstain']['reasons'] if o['abstain'] else None), sep=' | ')
