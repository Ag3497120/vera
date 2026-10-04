"""Writes the frozen test data of W10-f04 (tests/fusion/w10f04/{holes,fake_scripts,real_holes}.jsonl) BEFORE the product code exists.
The expectations are the author's (designed per row; see `note`), the rows of holes.jsonl come from the public copies (tests/reading_soundness) classified by the
independent oracle scripts mine_candidates.py / mine_pairs.py. Nothing here imports verantyx.fill_candidates or semantic_read.read_with_holes."""
import json, sys, collections, re
from verantyx import semantic_read as S
sys.path.insert(0, 'artifacts/w10-f04/scripts')
OUT = 'tests/fusion/w10f04/'
mined = [json.loads(l) for l in open(sys.argv[1])]
pairs = [json.loads(l) for l in open(sys.argv[2])]
P = '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2'
rows = []
# ---- positives: one hole
n = 0
for r in mined:
    if r.get('probe_types') and r.get('table_types'):
        n += 1
        rows.append({'id': 'H-POS-%03d' % n, 'text': r['text'], 'placement': 'r8', 'is_hole': True, 'n_holes': 1, 'particle': r['particle'], 'head': r['head'],
                     'table_types': r['table_types'], 'oracle_probe_types': r['probe_types'], 'expect_status': 'HOLES_FOUND',
                     'note': 'filler reason %s; one filler typed with one DECIDED direct type reads (oracle: mine_candidates.py)' % r['why']})
for i, r in enumerate(pairs, 1):
    rows.append({'id': 'H-POS2-%03d' % i, 'text': r['text'], 'placement': 'r8', 'is_hole': True, 'n_holes': 2,
                 'holes': [{'particle': h['particle'], 'head': h['head'], 'table_types': h['table_types'], 'oracle_probe_types': h['types']} for h in r['holes']],
                 'expect_status': 'HOLES_FOUND', 'note': 'two fillers: a pair of types reads (oracle: mine_pairs.py)'})
npos = len(rows)
# ---- negatives
n = 0
def neg(text, status, note, placement='r8', lang=None):
    global n
    n += 1
    if lang is None and S.detect_lang(text) == 'en': status = 'LANG_NOT_SUPPORTED'      # r1 (2026-10-04): the language of the text decides before any reason (K280 step 1)
    row = {'id': 'H-NEG-%03d' % n, 'text': text, 'placement': placement, 'is_hole': False, 'expect_status': status, 'note': note}
    if lang: row['lang'] = lang
    rows.append(row)
pairtexts = {p['text'] for p in pairs}
for r in mined:
    if r.get('particle') == 'part':
        neg(r['text'], 'NOT_A_FILLER_CAUSE', 'K63 left-over part (%s): not a hole' % r['why'])
for r in mined:
    if r.get('particle') and r['particle'] != 'part' and not r.get('probe_types') and r['text'] not in pairtexts:
        neg(r['text'], 'HOLE_NOT_PROBE_READABLE', 'filler reason %s but no typing of the filler(s) reads the sentence' % r['why'])
        if sum(1 for x in rows if x['expect_status'] == 'HOLE_NOT_PROBE_READABLE') >= 14: break
seen = collections.Counter()
for r in mined:
    if 'particle' in r: continue
    key = re.split(r'[:(]', r['reasons'][0])[0] if r['reasons'] else 'NONE'
    if seen[key] >= 3 or sum(seen.values()) >= 45: continue
    seen[key] += 1
    neg(r['text'], 'NOT_A_FILLER_CAUSE', 'no filler-placement reason; first reason %s' % r['reasons'][0])
for t in ['母が部屋で手紙を読んだ。', '兄が公園で犬を見た。', '先生が学校で本を読んだ。']:
    neg(t, 'READ', 'the reader reads it: no hole')
for t in ['兄が山田に催促した。', '母が図書館へ歩いた。', '客が庭へ走った。']:
    neg(t, 'NO_PLACEMENT', 'no placement given', placement='none')
for t in ['The mother walked to the library.', 'He read a book in the room.', 'Mother walked.']:
    neg(t, 'LANG_NOT_SUPPORTED', 'English is not supported', lang='en')
with open(OUT + 'holes.jsonl', 'w') as f:
    for r in rows: f.write(json.dumps(r, ensure_ascii=False) + '\n')
print('holes rows', len(rows), 'pos', npos, 'neg', len(rows) - npos, dict(collections.Counter(r['expect_status'] for r in rows)))

# ---- fake scripts
H = {'H1': ('母が図書館へ歩いた。', 'へ', '図書館'), 'H2': ('兄が窓口で名乗った。', 'で', '窓口'), 'H3': ('母が荷物を港へ押した。', 'を', '荷物'), 'H4': ('客が庭へ走った。', 'が', '客'),
     'H5': ('弟が役所へ走った。', 'へ', '役所'), 'H6': ('妹が本部へ歩いた。', 'へ', '本部'), 'H7': ('夫婦がホテルで名乗った。', 'が', '夫婦'), 'H8': ('母がホテルで勝利を願った。', 'を', '勝利')}
NEG = {'H1': '母が{w}へ歩かなかった。', 'H2': '兄が{w}で名乗らなかった。', 'H3': '母が{w}を港へ押さなかった。', 'H4': '{w}が庭へ走らなかった。', 'H5': '弟が{w}へ走らなかった。',
       'H6': '妹が{w}へ歩かなかった。', 'H7': '{w}がホテルで名乗らなかった。', 'H8': '母がホテルで{w}を願わなかった。'}
ROLE = {'H1': 'goal', 'H2': 'place', 'H3': 'patient', 'H4': 'agent', 'H5': 'goal', 'H6': 'goal', 'H7': 'agent', 'H8': 'patient'}
fr = []
def op(type_, near, role=None):
    return {'raw': json.dumps({'type': type_, 'role': role, 'near_words': near}, ensure_ascii=False)}
def add(gate, h, near, decl, expect_status, expect_reason, word=None, pick=None, records=None, open_step=None, closed_steps=None, note=''):
    i = sum(1 for x in fr if x['gate'] == gate) + 1
    text, part, head = H[h]
    step0 = open_step if open_step is not None else op(decl, near, ROLE[h])
    if closed_steps is None:
        closed_steps = [{'pick': pick}, {'pick': pick}] if pick is not None else []
    row = {'id': 'F-%s-%02d' % (gate, i), 'gate': gate, 'sentence': text, 'hole': {'particle': part, 'head': head}, 'records': records or [], 'steps': [step0] + closed_steps,
           'expect': {'status': expect_status, 'reason': expect_reason, 'word': word}, 'note': note}
    fr.append(row)
def A(h, w, decl, near=None, **kw): add('ADOPT', h, near or [w], decl, 'ADOPTED', 'ADOPTED', word=w, pick=w, **kw)
A('H1', '駅', 'PLACE'); A('H1', '公園', 'PLACE', near=['公園', '市役所']); A('H3', '皿', 'ARTIFACT'); A('H3', '本', 'INFO_LANGUAGE'); A('H3', '絵', 'WORK')
A('H4', '犬', 'ANIMAL'); A('H4', '先生', 'PERSON'); A('H4', '学校', 'GROUP_ORG'); A('H5', '港', 'PLACE'); A('H6', '駅', 'PLACE', near=['駅', '午後'])
A('H7', '会社', 'GROUP_ORG'); A('H8', '小説', 'WORK'); A('H2', '公園', 'PLACE'); A('H3', '論文', 'WORK'); A('H4', '猫', 'ANIMAL', near=['猫', '山田'])
def N(gate, h, near, decl, reason, **kw): add(gate, h, near, decl, 'NOT_ADOPTED', reason, **kw)
for h, w, reason in [('H1', '市役所', 'GATE_A_NOT_PLACED:PLACEMENT_ESTIMATED_NEAR'), ('H3', '切符', 'GATE_A_NOT_PLACED:PLACEMENT_UNPLACED'), ('H3', '手紙', 'GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE'),
                     ('H3', '傘', 'GATE_A_NOT_PLACED:PLACEMENT_DIRECT_VIA_GENERATED'), ('H1', '母', 'GATE_A_TYPE_NOT_EXPECTED'), ('H4', '駅', 'GATE_A_TYPE_NOT_EXPECTED'),
                     ('H2', '先生', 'GATE_A_TYPE_NOT_EXPECTED'), ('H5', '昨日', 'GATE_A_NOT_PLACED:PLACEMENT_ESTIMATED_GENERATED'), ('H6', '山田', 'GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE'),
                     ('H7', '公園', 'GATE_A_TYPE_NOT_EXPECTED'), ('H1', '午後', 'GATE_A_NOT_PLACED:PLACEMENT_UNPLACED'), ('H8', '荷物', 'GATE_A_NOT_PLACED:PLACEMENT_UNPLACED')]:
    T = {'GATE_A_TYPE_NOT_EXPECTED': {'母': 'PERSON', '駅': 'PLACE', '先生': 'PERSON', '公園': 'PLACE'}.get(w, 'PLACE')}.get(reason, 'PLACE')
    N('A1', h, [w], T, reason)
for h, w, decl, reason in [('H3', '皿', 'WORK', 'GATE_A_DECLARED_TYPE_MISMATCH'), ('H3', '本', 'ARTIFACT', 'GATE_A_DECLARED_TYPE_MISMATCH'), ('H4', '犬', 'PERSON', 'GATE_A_DECLARED_TYPE_MISMATCH'),
                           ('H4', '先生', 'ANIMAL', 'GATE_A_DECLARED_TYPE_MISMATCH'), ('H1', '駅', 'GROUP_ORG', 'GATE_A_DECLARED_TYPE_MISMATCH'), ('H5', '港', 'PERSON', 'GATE_A_DECLARED_TYPE_MISMATCH'),
                           ('H3', '絵', 'ARTIFACT', 'GATE_A_DECLARED_TYPE_MISMATCH'), ('H7', '会社', 'PERSON', 'GATE_A_DECLARED_TYPE_MISMATCH'), ('H8', '小説', 'INFO_LANGUAGE', 'GATE_A_DECLARED_TYPE_MISMATCH'),
                           ('H6', '駅', 'TIME', 'GATE_A_DECLARED_TYPE_MISMATCH'), ('H2', '公園', 'GROUP_ORG', 'GATE_A_DECLARED_TYPE_MISMATCH')]:
    N('A2', h, [w], decl, reason)
for w in ['玄関', '窓辺', '校門', '中庭', '入口', '壁', '台', '隅', '渓谷', '近く', '隣']:
    N('B', 'H2', [w], 'PLACE', 'GATE_B_REREAD', note='placement says PLACE (direct) but the reader does not read the slot with it')
for h, w, decl in [('H1', '駅', 'PLACE'), ('H3', '皿', 'ARTIFACT'), ('H4', '犬', 'ANIMAL'), ('H5', '港', 'PLACE'), ('H6', '駅', 'PLACE'), ('H7', '会社', 'GROUP_ORG'), ('H8', '小説', 'WORK'),
                   ('H2', '公園', 'PLACE'), ('H3', '本', 'INFO_LANGUAGE'), ('H4', '先生', 'PERSON')]:
    N('C', h, [w], decl, 'GATE_C_CONTRADICTS_RECORD', records=[NEG[h].format(w=w)], note='the record says the same cross with the opposite polarity')
for h, ws, decl in [('H1', ['駅', '公園'], 'PLACE'), ('H1', ['港', '山'], 'PLACE'), ('H3', ['皿', '箱'], 'ARTIFACT'), ('H4', ['犬', '猫'], 'ANIMAL'), ('H5', ['駅', '港'], 'PLACE'), ('H6', ['公園', '川'], 'PLACE')]:
    # the declared type must match both: the tie is decided before the closed ask, so the declared type is the first word's type; the second word's type is checked on its own
    N('D', h, ws, decl, 'GATE_D_TIE', note='two words pass every gate: abstain, no winner by order')

# choice not passing: the (a)-list is {pass word, b-failing word}; the closed ask picks the b-failing word (twice)
for w in ['玄関', '窓辺', '校門']:
    add('D', 'H2', ['公園', w], 'PLACE', 'NOT_ADOPTED', 'GATE_D_CHOICE_NOT_PASSING', pick=w, note='the closed ask picked a word that did not pass (b)')
# closed ask abstains: first ask null / the two asks disagree
add('D', 'H1', ['駅'], 'PLACE', 'NOT_ADOPTED', 'GATE_D_CHOICE_ABSTAINED', closed_steps=[{'pick': None}], note='first closed ask answers null')
add('D', 'H4', ['犬'], 'ANIMAL', 'NOT_ADOPTED', 'GATE_D_CHOICE_ABSTAINED', closed_steps=[{'raw': '{"choice": 0}'}, {'pick': None}], note='the two closed asks disagree (pick / null)')
# backend failures (K285): typed, never "no candidate"
for kind in ['TIMEOUT', 'CONNECT_FAILED', 'HTTP_ERROR', 'BAD_RESPONSE']:
    for h in ['H1', 'H4']:
        add('BACKEND', h, [], 'PLACE', 'BACKEND_FAILED', 'BACKEND_FAILED:' + kind, open_step={'fail': kind}, note='open declaration call fails: %s' % kind)
for h in ['H1', 'H3']:
    add('BACKEND', h, [], 'PLACE', 'BACKEND_FAILED', 'BACKEND_FAILED:EMPTY_CONTENT', open_step={'raw': ''}, note='empty content')
add('BACKEND', 'H1', ['駅'], 'PLACE', 'BACKEND_FAILED', 'BACKEND_FAILED:TIMEOUT', closed_steps=[{'fail': 'TIMEOUT'}], note='closed ask fails')
add('BACKEND', 'H4', ['犬'], 'ANIMAL', 'BACKEND_FAILED', 'BACKEND_FAILED:CONNECT_FAILED', closed_steps=[{'fail': 'CONNECT_FAILED'}], note='closed ask fails')
# invalid open declarations (not a backend failure)
add('OPEN', 'H1', [], 'PLACE', 'NOT_ADOPTED', 'OPEN_DECLARATION_INVALID', open_step={'raw': '駅です'}, note='not JSON')
add('OPEN', 'H1', [], 'PLACE', 'NOT_ADOPTED', 'OPEN_DECLARATION_INVALID', open_step={'raw': json.dumps({'type': 'STATION', 'role': None, 'near_words': ['駅']}, ensure_ascii=False)}, note='type outside the 17')
add('OPEN', 'H1', [], 'PLACE', 'NOT_ADOPTED', 'OPEN_DECLARATION_INVALID', open_step={'raw': json.dumps({'type': 'PLACE', 'role': 'patient', 'near_words': ['駅']}, ensure_ascii=False)}, note='role outside the hole role_candidates')
add('OPEN', 'H1', [], 'PLACE', 'NOT_ADOPTED', 'OPEN_DECLARATION_INVALID', open_step={'raw': json.dumps({'type': 'PLACE', 'role': None, 'near_words': ['駅', '公園', '港', '山', '川', '庭']}, ensure_ascii=False)}, note='more than K=5 words')
add('OPEN', 'H1', [], 'PLACE', 'NOT_ADOPTED', 'OPEN_DECLARATION_INVALID', open_step={'raw': json.dumps({'type': 'PLACE', 'role': None, 'near_words': ['駅'], 'why': 'x'}, ensure_ascii=False)}, note='extra key')
add('OPEN', 'H4', [], 'ANIMAL', 'NOT_ADOPTED', 'OPEN_DECLARATION_INVALID', open_step={'raw': json.dumps({'type': 'ANIMAL', 'near_words': ['犬']}, ensure_ascii=False)}, note='missing key role')
# no near words
add('NONE', 'H1', [], 'PLACE', 'NOT_ADOPTED', 'NO_CANDIDATE_WORDS', note='the declaration holds no near word')
add('NONE', 'H3', [], 'ARTIFACT', 'NOT_ADOPTED', 'NO_CANDIDATE_WORDS', note='the declaration holds no near word')
with open(OUT + 'fake_scripts.jsonl', 'w') as f:
    for r in fr: f.write(json.dumps(r, ensure_ascii=False) + '\n')
print('fake rows', len(fr), dict(collections.Counter(r['gate'] for r in fr)))

# ---- real holes: 30 from the positives (hole rows), stratified by particle; the expectation is by eye (none written)
byp = collections.defaultdict(list)
for r in rows:
    if r['is_hole']: byp[(r.get('particle') or 'pair')].append(r)
pick = []
for part, k in [('へ', 6), ('で', 5), ('が', 6), ('を', 9), ('に', 3), ('pair', 2)]:
    pick += byp[part][:k]
for r in rows:
    if r['is_hole'] and r not in pick and len(pick) < 30: pick.append(r)
with open(OUT + 'real_holes.jsonl', 'w') as f:
    for i, r in enumerate(pick, 1):
        f.write(json.dumps({'id': 'R-%02d' % i, 'text': r['text'], 'source_row': r['id']}, ensure_ascii=False) + '\n')
print('real rows', len(pick))

# ---- self-check of the designed rows with the reader alone (the oracle, not the product code)
from verantyx import semantic_reader as R
base = R.CoarseQuery(P)
bad = []
for r in fr:
    text, part, head = r['sentence'], r['hole']['particle'], r['hole']['head']
    if r['gate'] == 'ADOPT':
        w = r['expect']['word']; o = S.read(text.replace(head, w), placement=P)
        a = base.query(w)
        if not (o['readable'] and len(o['clauses']) == 1 and w in o['clauses'][0]['roles'].values() and R.placement_type(a)[1] is None): bad.append((r['id'], 'adopt row does not read'))
    if r['gate'] == 'B':
        w = r['steps'][0] and json.loads(r['steps'][0]['raw'])['near_words'][0]; o = S.read(text.replace(head, w), placement=P)
        if o['readable']: bad.append((r['id'], 'b row reads'))
    if r['gate'] == 'C':
        w = json.loads(r['steps'][0]['raw'])['near_words'][0]
        o1 = S.read(text.replace(head, w), placement=P); o2 = S.read(r['records'][0], placement=P)
        if not (o1['readable'] and o2['readable'] and o2['clauses'][0]['polarity'] == '-' and o1['clauses'][0]['polarity'] == '+'
                and {k: v for k, v in o1['clauses'][0].items() if k != 'polarity'} == {k: v for k, v in o2['clauses'][0].items() if k != 'polarity'}): bad.append((r['id'], 'c record not the opposite polarity'))
    if r['gate'] == 'D' and r['expect']['reason'] == 'GATE_D_TIE':
        for w in json.loads(r['steps'][0]['raw'])['near_words']:
            o = S.read(text.replace(head, w), placement=P)
            if not o['readable']: bad.append((r['id'], 'tie word %s does not read' % w))
print('self-check problems:', bad)
