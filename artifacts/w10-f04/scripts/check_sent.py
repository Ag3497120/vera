"""P5 (K286): what was SENT at the backend boundary (FakeBackend.sent, dumped by run_fake.py --dump-sent) must not hold the user's sentence, its sha256, or the surface of an arm that is not the hole
(a surface equal to the predicate, the hole's word, the particle or a candidate word is not counted). Needs VERA_PLACEMENT (reads the rows with read_with_holes to know the arms)."""
import argparse, collections, hashlib, json, os, unicodedata
from verantyx import semantic_read as S
ap = argparse.ArgumentParser(); ap.add_argument('--data', required=True); ap.add_argument('--sent', required=True); ap.add_argument('--expect-leak', action='store_true'); a = ap.parse_args()
R8 = os.environ['VERA_PLACEMENT']
rows = {r['id']: r for r in map(json.loads, open(a.data))}
sent = collections.defaultdict(list)
for l in open(a.sent):
    d = json.loads(l); sent[d['id']].append(d)
nfkc = lambda s: unicodedata.normalize('NFKC', s).strip()
leak_s = leak_sha = leak_arm = n_msgs = 0; detail = []; n_call = n_two_holes = n_other_hole_word_sent = 0
for rid, row in rows.items():
    text = row['sentence']
    ho = S.read_with_holes(text, placement=R8)
    hole = next(h for h in ho['holes'] if (h['particle'], h['head']) == (row['hole']['particle'], row['hole']['head']))
    allowed = {hole['head'], hole['particle'], ho['partial']['predicate']}
    if row.get('call'): n_call += 1                        # r3: a row that calls a gate directly sends nothing to a backend (counted here, not in the leaks)
    other_holes = [h['head'] for h in ho['holes'] if h is not hole]
    if other_holes: n_two_holes += 1
    for st in row['steps']:
        if 'raw' in st:
            try:
                for w in json.loads(st['raw']).get('near_words', []): allowed.add(w)
            except Exception: pass
        if st.get('pick'): allowed.add(st['pick'])
    others = [v for v in (ho['partial']['roles'] or {}).values() if isinstance(v, str)]
    blob = '\n'.join(m['content'] for d in sent[rid] for m in d['messages'])
    blob += '\n' + '\n'.join(json.dumps(d['fmt'], ensure_ascii=False) for d in sent[rid])
    n_msgs += sum(len(d['messages']) for d in sent[rid])
    if other_holes and any(w in blob for w in other_holes): n_other_hole_word_sent += 1
    if text in blob or text.rstrip('。') in blob: leak_s += 1; detail.append((rid, 'sentence'))
    if hashlib.sha256(text.encode()).hexdigest() in blob or hashlib.sha256(nfkc(text).encode()).hexdigest() in blob: leak_sha += 1; detail.append((rid, 'sha'))
    for o in others:
        if o in allowed or any(o in w for w in allowed): continue
        if o in blob: leak_arm += 1; detail.append((rid, 'arm:' + o))
print('rows=%d messages_checked=%d leaked_sentence=%d leaked_sentence_sha=%d leaked_other_arm=%d' % (len(rows), n_msgs, leak_s, leak_sha, leak_arm))
print('note: rows_with_direct_call=%d send nothing (their messages are 0); two_hole_rows=%d, of which %d sent the OTHER hole\'s word as a hole (J5: a hole\'s word is sent; `others` below = arms whose value is a string in partial.roles, so a hole is never counted as another arm)' % (n_call, n_two_holes, n_other_hole_word_sent))
for d in detail[:10]: print(' ', d)
if a.expect_leak: print('detector_sanity (unmasked dump must leak): leaks=%d' % (leak_s + leak_sha + leak_arm))
