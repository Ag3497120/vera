# W5-a round 3: classification of the seven existing tests the auditor's decision B3 names, under variant C (written for this round).
# The predicate and the subject are written on each row (a sentence the reader does not read has no clause to take them from).
import json
from verantyx import semantic_read as SR, semantic_reader as R
from verantyx.frames import transitivity
ROWS = [('test_routing_from_text_entry.py::test_T1_...', 'モモがテストを書く。', '書く', 'モモ'),
        ('test_routing_from_text_entry.py::test_T1_...', 'セキがコードを確かめる。', '確かめる', 'セキ'),
        ('test_routing_from_text_entry.py::test_T1_...', 'モモは検証をやらない。', 'やる', 'モモ'),
        ('test_routing_from_text_regress.py::test_M1_...', 'セキがレビューをやる。', 'やる', 'セキ'),
        ('test_observe_data.py::...[S-J06]', '車掌は乗客に切符を渡した。', '渡す', '車掌'),
        ('test_observe_data.py::...[S-J07]', '受付は客に鍵を渡した。', '渡す', '受付'),
        ('test_observe_data.py::...[S-J13]', '農家は市場で果物を売った。', '売る', '農家'),
        ('test_observe_data.py::...[S-J21]', '会計係は領収書を発行しなかった。', '発行する', '会計係'),
        ('test_observe_data.py::...[M12-single-J05]', '駅員は乗客に切符を渡した。', '渡す', '駅員'),
        ('test_observe_data.py::...[M12-single-J05]', '車掌は乗客に切符を渡した。', '渡す', '車掌')]
CLASSES = ['_TRANSFER_PREDICATES', '_SHARING_PREDICATES', '_CHANGE_PREDICATES', '_SELECTION_PREDICATES', '_PROCESSING_PREDICATES', '_PRODUCT_PREDICATES',
           '_CONTAINMENT_PREDICATES', '_PLACEMENT_PREDICATES']
import verantyx.semantic_read as m
print('module', m.__file__)
for node, text, pred, subj in ROWS:
    o = SR.read(text)
    cls = [n for n in CLASSES if pred in getattr(R, n)]
    result = 'readable' if o['readable'] else 'abstain:%s' % o['abstain']['reasons']
    print(node, text, 'pred=%s' % pred, 'transitivity=%s' % transitivity(pred), 'classes=%s' % cls,
          'subject_is_person=%s' % R._is_person_phrase(subject := subj), 'object_frame_known=%s' % SR._object_frame_known(pred, R),
          'round3=%s' % result, sep=' | ')
