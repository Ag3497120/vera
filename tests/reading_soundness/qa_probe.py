#!/usr/bin/env python3
"""補助測定(受入基準ではない): 読解の変更が質問応答の答えをどう動かしたかを、既存の gold probe(who_did_what, train のみ)で測る。

使い方: cd <木> && PYTHONPATH=<木> VERA_CORPUS_ROOT=/tmp/vera-empty-materials python qa_probe.py <seed> <out.json>
/Users/motonisihikoudai/vera-wiring/phase2/gold_probe.py(読み取り専用)の `sample`/`load` を使い、各現象 150 問を
Vera.from_texts(..., mode='semantic').ask に通して correct(完全一致)/wrong/abstain を文ごとに JSON に書く。
"""
import argparse, os, sys, collections, json
sys.path.insert(0,'.')
src=open('/Users/motonisihikoudai/vera-wiring/phase2/gold_probe.py').read().split("if __name__")[0]
exec(src)
a = argparse.Namespace(n=150, seed=int(sys.argv[1]), phenomenon='')
from verantyx.one import Vera
groups = sample(load('paraphrase_entail', 'who_did_what'), 'phenomenon', a.n, a.seed)
out=[]
for ph, items in sorted(groups.items()):
    for r in items:
        v = Vera.from_texts({'d': r['sentence']}, mode='semantic'); res = v.ask(r['question']); v.close()
        if res['verdict'] != 'ANSWER': st='abstain'; vals=[]
        else:
            vals = res.get('values') or []; gold = r['answer']
            st = 'correct' if vals == [gold] else 'wrong'
        out.append({'ph':ph,'s':r['sentence'],'q':r['question'],'gold':r['answer'],'st':st,'vals':vals})
json.dump(out, open(sys.argv[2],'w'), ensure_ascii=False)
