"""入口 4,149 文の下一段の動詞の延べ数と型数を、3 つの判定の式で数える（K818 の式の選択の根拠）。
A: lemma != orthBase（表記の違いを拾う）、B: lForm != pronBase（長音・濁点を拾う）、C: len(pronBase) == len(lForm)+1（採用）。"""
import json, collections
from verantyx import semantic_reader as R
crit = {'A_lemma_ne_orth': lambda f: f.lemma != f.orthBase, 'B_lform_ne_pron': lambda f: f.lForm != f.pronBase, 'C_pron_len_plus1': lambda f: len(f.pronBase) == len(f.lForm) + 1}
tot = collections.Counter(); types = {k: collections.Counter() for k in crit}; n = 0
for l in open('artifacts/w3-b5/entry_inputs_r2.txt', encoding='utf-8'):
    if not l.strip(): continue
    t = json.loads(l)['text']
    for w, s, e in R._tokens(t):
        f = w.feature
        if f.pos1 == '動詞' and str(f.cType).startswith('下一段'):
            tot['all'] += 1
            for k, fn in crit.items():
                if fn(f): types[k][(f.lemma, f.orthBase)] += 1
for k in crit: print(k, 'tokens', sum(types[k].values()), 'types', len(types[k]), 'of all-tokens', tot['all'])
print('false-positive examples of A (same lForm/pronBase):', [x for x in types['A_lemma_ne_orth'] if x not in types['C_pron_len_plus1']][:8])
print('false-positive examples of B (long vowel / dakuten):', [x for x in types['B_lform_ne_pron'] if x not in types['C_pron_len_plus1']][:8])
