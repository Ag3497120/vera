#!/usr/bin/env python3
"""Scale of the document path: flat view vs leaf-routed view over N synthetic documents (own data, no fixtures)."""
import argparse, json, random, statistics, sys, time
sys.path.insert(0, '.')
from verantyx import semantic_route
from verantyx.one import Vera

SYL = ['カ','キ','ク','ケ','コ','サ','シ','ス','セ','ソ','タ','チ','ツ','テ','ト','ナ','ニ','ヌ','ネ','ノ','ハ','ヒ','フ','ヘ','ホ','マ','ミ','ム','メ','モ','ヤ','ユ','ヨ','ラ','リ','ル','レ','ロ','ワ']
def name(i, k):                      # unique katakana names, deterministic
    a, b, c = i % 39, (i // 39) % 39, (i // 1521) % 39
    return SYL[a] + SYL[b] + SYL[c] + ('ン' if k else 'ー'[:0] + 'ル')
OBJECTS = ['青鍵', '赤箱', '白紙', '黒鞄', '緑札', '銀鍵', '金箱', '灰紙']

def corpus(n, common=True, unread_every=7):
    docs, truth = {}, []
    for i in range(n):
        agent, recip, third = name(i, 0), name(i + 1, 1), name(i + 2, 0)
        obj = OBJECTS[i % len(OBJECTS)] + str(i)
        text = [f'{agent}は{obj}を{recip}に渡した。']
        if common: text.append(f'係員は{obj}を倉庫に置いた。')           # one entity shared by every document
        if i % unread_every == 0: text.append(f'{third}は{recip}に{obj}をそっと渡した。')   # unsupported sentence (adverb)
        docs[f'd{i}'] = ''.join(text)
        truth.append((f'{obj}を{recip}に渡したのは？', agent, i))
    return docs, truth

def run(n, k, routed, seed=1):
    docs, truth = corpus(n)
    semantic_route.ROUTE_MIN_LEAVES = 7 if routed else 10**9
    t = time.perf_counter(); v = Vera.from_texts(docs, mode='semantic'); build = (time.perf_counter() - t) * 1000
    rnd = random.Random(seed); sample = rnd.sample(truth, min(k, len(truth)))
    out = {'n': n, 'routed': routed, 'build_ms': round(build, 1), 'correct': 0, 'wrong': 0, 'abstain': 0, 'verdicts': {}, 'ms': []}
    first = None
    for q, want, i in sample:
        t = time.perf_counter(); a = v.ask(q); dt = (time.perf_counter() - t) * 1000
        out['ms'].append(dt); out['verdicts'][a['verdict']] = out['verdicts'].get(a['verdict'], 0) + 1
        if a['verdict'] == 'ANSWER': out['correct' if a['values'] == [want] else 'wrong'] += 1
        else: out['abstain'] += 1
        if first is None:
            first = [s for s in a.get('trace', []) if s.get('part') == 'semantic_route.LeafTree']
    v.close(); ms = sorted(out.pop('ms'))
    out.update(median_ms=round(statistics.median(ms), 2), p95_ms=round(ms[int(.95 * len(ms)) - 1], 2), max_ms=round(ms[-1], 2), route=first[0] if first else None)
    return out

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--sizes', default='10,50,200,1000'); ap.add_argument('--k', type=int, default=30)
    args = ap.parse_args()
    for n in map(int, args.sizes.split(',')):
        for routed in (False, True):
            print(json.dumps(run(n, args.k, routed), ensure_ascii=False), flush=True)
