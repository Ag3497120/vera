#!/usr/bin/env python3
"""W3-b6 step 2 (before the prereg text of the measurements): where each sentence of the 11 lines (W3-a6 N2) goes in the reader as it is: with no placement (the output of
`read`), and with the answers of the placement r8 (read only) for every word of the sentence, the trigger of the typed paths (`typed_explain_ja`: w3b1_trigger / w3b2_trigger) and
the reason the typed step stopped. Written before any change of the reader. Usage: PYTHONPATH=<tree> python artifacts/w3-b6/tools/reach_base.py R8_PATH SENTENCES.txt
(each line: sentence<TAB>word word ...)"""
import sys
sys.path.insert(0, 'tests/reading_soundness')
import w3b2_fakes as F
from verantyx import coarse_place as CP, semantic_read as SR


def main():
    r8 = sys.argv[1]
    for line in open(sys.argv[2], encoding='utf-8'):
        line = line.rstrip('\n')
        if not line: continue
        text, words = line.split('\t')
        out = SR.read(text)
        none = ('READ ' + str([(c['predicate'], c['roles']) for c in out['clauses']])) if out['readable'] else ('ABSTAIN ' + str(out['abstain']['reasons']))
        ans = {w: CP.query(w, placement=r8) for w in words.split()}
        o2 = SR.read(text, placement=F.MapQuery(ans))
        ex = SR.typed_explain_ja(text, F.MapQuery(ans))
        r8s = ('READ ' + str([(c['predicate'], c['roles']) for c in o2['clauses']])) if o2['readable'] else ('ABSTAIN ' + str(o2['abstain']['reasons']))
        print('%s\n  none: %s\n  r8:   %s\n  trigger(w3b1,w3b2)=(%s,%s) w3b1=%s w3b2=%s' % (text, none, r8s, ex['w3b1_trigger'], ex['w3b2_trigger'], ex['w3b1'], ex['w3b2']))

main()
