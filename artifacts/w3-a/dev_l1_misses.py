import sys, json, re
from collections import Counter
sys.path.insert(0, '/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S/artifacts/w3-a')
import measure_w3a as m
from verantyx import coarse_place as cp
pl_path = sys.argv[1]
pl, why = cp._open(pl_path)
for kv in sys.argv[2:]:
    k, v = kv.split('=', 1); pl.cfg[k] = json.loads(v)
import fugashi
tg = fugashi.Tagger()
H = m.load(m.A + '/dev_l1_1000.jsonl')
miss = Counter(); cat = Counter(); tot = 0
for h in H:
    for term, role, pred, p1 in m.content_tokens(tg, h['sentence']):
        tot += 1
        r = m.query(term, context_role=role, context_predicate=pred, placement=pl_path)
        if not r['top']:
            miss[(term, p1, r['state'])] += 1
            if re.fullmatch(r'[A-Za-z0-9 ._\-]+', term): c = 'ascii'
            elif re.fullmatch(r'[぀-ゟ]+', term): c = 'hiragana'
            elif re.fullmatch(r'[゠-ヿー]+', term): c = 'katakana'
            elif p1 != '名詞': c = 'pred:' + p1
            elif len(term) <= 2: c = 'kanji<=2'
            else: c = 'kanji>2'
            cat[(c, r['state'])] += 1
print('tokens', tot, 'misses', sum(miss.values()))
for k, v in sorted(cat.items(), key=lambda x: -x[1]): print(k, v)
print([(k[0], v) for k, v in miss.most_common(90)])
