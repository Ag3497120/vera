"""r3: write tests/fusion/w10f04/fake_scripts.jsonl (r3) from artifacts/w10-f04/fake_scripts.r2.jsonl, BEFORE the (a4)/(b') code exists.
Expectations are derived from an independent oracle: the placement answers of r8 (`semantic_reader.placement_type`, `event_cross.PlaceResult`) and the reader's reading of the sentence with the hole word typed
(`_HoleProbe`): it does not import fill_candidates. Table (ii) of the plan: B/C rows become direct calls of the gate; ADOPT/D/A3R (and the two BACKEND rows that reach the closed ask) change by ruling A.
Run: VERA_PLACEMENT=<r8> python make_data_r3.py"""
import itertools, json, os, sys, collections
from verantyx import semantic_read as S, event_cross as EC, semantic_reader as R

W = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
r2_rows = [json.loads(l) for l in open(os.path.join(W, 'artifacts/w10-f04/fake_scripts.r2.jsonl'), encoding='utf-8')]
q = S._placement_query(S._UNSET)
_cache = {}


def hole_class(text, particle, head):
    """(class, own types, expected_types, role_by_type) of the hole (particle, head) of `text` -- None when it is not a hole."""
    if text not in _cache:
        _cache[text] = S.read_with_holes(text)
    ho = _cache[text]
    if ho['holes_status'] != 'HOLES_FOUND':
        return None
    for hi, h in enumerate(ho['holes']):
        if (h['particle'], h['head']) != (particle, head):
            continue
        others = [o for j, o in enumerate(ho['holes']) if j != hi]
        own = EC.PlaceResult.from_coarse_query(q.query(h['head'])).types
        roles = {}
        for t in own:
            rs = set()
            for combo in itertools.product(*[o['expected_types'] for o in others]):
                f = {o['head']: c for o, c in zip(others, combo)}
                f[h['head']] = t
                out = S.read(text, 'ja', placement=S._HoleProbe(q, f, {}))
                rs.add(S._hole_arm(out['clauses'][0], h['head'], t) if S._hole_probe_ok(out) else None)
            roles[t] = rs
        if h['placement_state'] in ('UNPLACED', 'UNKNOWN') or not own:
            return 'UNPLACED', own, h['expected_types'], roles
        allr = set(x for v in roles.values() for x in v)
        if len(allr) == 1 and None not in allr:
            return 'SAME', own, h['expected_types'], roles
        return ('SPLIT' if len(allr - {None}) >= 2 else 'UNDET'), own, h['expected_types'], roles
    return None


def ruling(cls):
    if cls == 'UNPLACED':
        return 'GATE_A_HOLE_WORD_UNPLACED', None
    return 'GATE_A_ROLE_SPLIT', ('ROLES_DIFFER' if cls == 'SPLIT' else 'TYPE_NOT_READ')


def decl(row):
    return json.loads(row['steps'][0]['raw'])


def op(type_, words, role):
    return {'raw': json.dumps({'type': type_, 'role': role, 'near_words': words}, ensure_ascii=False)}


def precheck(sentence, particle, head, declared, words, want):
    """The oracle checks the preconditions of a new row: the word is a hole of the wanted class and every candidate passes (a1)(a2)(a3)."""
    c = hole_class(sentence, particle, head)
    assert c is not None and c[0] == want, (sentence, particle, head, c and c[0], want)
    cls, own, expected, _ = c
    for w in words:
        t, why = R.placement_type(q.query(w))
        assert why is None and t == declared and t in expected, (sentence, w, t, why, declared, expected)
    assert not own or declared in own, (sentence, declared, own)
    return c


out = []
for r in r2_rows:
    r = dict(r)
    g = r['gate']
    if g == 'B':
        r['call'] = 'gate_b'
        r['r3'] = 'direct_call'
    elif g == 'C':
        r['call'] = 'gate_c'
        r['r3'] = 'direct_call'
    elif g in ('ADOPT', 'D', 'A3R') or (g == 'BACKEND' and len(r['steps']) > 1 and 'raw' in r['steps'][0] and r['steps'][0]['raw'].lstrip().startswith('{')):
        c = hole_class(r['sentence'], r['hole']['particle'], r['hole']['head'])
        assert c is not None and c[0] != 'SAME', (r['id'], c and c[0])
        reason, split = ruling(c[0])
        r['gate_r2'], r['expect_r2'] = g, r['expect']
        r['gate'] = 'A4'
        r['expect'] = {'status': 'NOT_ADOPTED', 'reason': reason, 'word': None}
        if split:
            r['expect']['split_kind'] = split
        r['r3'] = 'expect_changed_by_ruling_A'
        r['survey_class'] = c[0]
    out.append(r)


def new(id_, gate, sentence, particle, head, steps, expect, note, **kw):
    row = {'id': id_, 'gate': gate, 'sentence': sentence, 'hole': {'particle': particle, 'head': head}, 'records': kw.pop('records', []), 'steps': steps, 'expect': expect, 'note': note, 'r3': 'new'}
    row.update(kw)
    out.append(row)


# --- A4U: the placement gives the hole word no type (UNPLACED / UNKNOWN). Candidates pass (a1)(a2)(a3).
A4U = [('父が税務署に申告した。', 'に', '税務署', 'TIME', ['夜'], 'time'), ('職員が望遠レンズに旅行した。', 'に', '望遠レンズ', 'TIME', ['夏'], 'time'), ('選手が搬出口に昇った。', 'に', '搬出口', 'TIME', ['冬'], 'time'),
       ('兄が土間で歩いた。', 'で', '土間', 'PLACE', ['駅'], 'place'), ('母が広間で名乗った。', 'で', '広間', 'PLACE', ['公園'], 'place'), ('祖父が座敷で断った。', 'で', '座敷', 'PLACE', ['港'], 'place'),
       ('妹が屋根裏で歩いた。', 'で', '屋根裏', 'PLACE', ['山'], 'place'), ('鳥が山の上へ飛んだ。', 'へ', '山の上', 'PLACE', ['川'], 'goal'), ('馬が橋の上へ走った。', 'へ', '橋の上', 'PLACE', ['駅'], 'goal'),
       ('兄が祖父の家へ走った。', 'へ', '祖父の家', 'PLACE', ['公園'], 'goal'), ('先生の夫婦が森へ歩いた。', 'が', '先生の夫婦', 'PERSON', ['兄'], 'agent'),
       ('母が荷物を後へ押した。', 'を', '荷物', 'INFO_LANGUAGE', ['本'], 'patient'), ('父が税務署に申告した。', 'に', '税務署', 'TIME', ['昼', '冬'], 'time')]
for i, (s, p, h, t, ws, role) in enumerate(A4U, 1):
    precheck(s, p, h, t, ws, 'UNPLACED')
    new('F-A4U-%02d' % i, 'A4U', s, p, h, [op(t, ws, role)], {'status': 'NOT_ADOPTED', 'reason': 'GATE_A_HOLE_WORD_UNPLACED' if len(ws) == 1 else 'GATE_A_HOLE_WORD_UNPLACED', 'word': None},
        'the placement gives the hole word no type: the candidate decides the structure, not only the word (ruling A); the declaration and the candidate stay in the ledger as testimony')

# --- A4S: the hole word has several types and they do not fall in ONE role in this sentence (some type is not read). TIME candidates pass (a1)(a2)(a3) because TIME is a type of the hole word.
A4S = [('妹が東京に旅行した。', 'に', '東京', 'TIME', ['夏'], 'time'), ('隊員が港へ走った。', 'が', '隊員', 'PERSON', ['兵士'], 'agent'), ('妹が左に旅行した。', 'に', '左', 'TIME', ['夜'], 'time'),
       ('妹があとに旅行した。', 'に', 'あと', 'TIME', ['冬'], 'time'), ('妹があいだに旅行した。', 'に', 'あいだ', 'TIME', ['夏'], 'time'), ('妹が前に旅行した。', 'に', '前', 'TIME', ['夜'], 'time'),
       ('妹が後に旅行した。', 'に', '後', 'TIME', ['冬'], 'time'), ('妹が下に旅行した。', 'に', '下', 'TIME', ['夏'], 'time'), ('妹がほかに旅行した。', 'に', 'ほか', 'TIME', ['夜'], 'time'),
       ('妹が先に旅行した。', 'に', '先', 'TIME', ['冬'], 'time'), ('妹が手前に旅行した。', 'に', '手前', 'TIME', ['夏'], 'time'), ('妹が外に旅行した。', 'に', '外', 'TIME', ['夜'], 'time'),
       ('妹が間に旅行した。', 'に', '間', 'TIME', ['冬'], 'time')]
for i, (s, p, h, t, ws, role) in enumerate(A4S, 1):
    c = precheck(s, p, h, t, ws, 'UNDET')
    new('F-A4S-%02d' % i, 'A4S', s, p, h, [op(t, ws, role)], {'status': 'NOT_ADOPTED', 'reason': 'GATE_A_ROLE_SPLIT', 'word': None, 'split_kind': 'TYPE_NOT_READ'},
        'the hole word has types %s; the reader reads some of them as the hole arm and not the others (ruling A: the structure would depend on which type is true)' % list(c[1]))

# --- ADOPT (two-hole sentences; the hole is the agent, every type of the hole word reads agent, the other hole is typed PLACE by the probe)
AD = [('ウサギが図書館へ走った。', 'ウサギ', 'ANIMAL', '犬'), ('ウサギが図書館へ走った。', 'ウサギ', 'PERSON', '兄'), ('エリートが銀行へ歩いた。', 'エリート', 'PERSON', '姉'), ('ライオンが銀行へ歩いた。', 'ライオン', 'ANIMAL', '猫'),
      ('家族が図書館へ走った。', '家族', 'PERSON', '弟'), ('警察が家へ歩いた。', '警察', 'PERSON', '先生'), ('パンダが本部へ走った。', 'パンダ', 'ANIMAL', '鳥'), ('ヒツジが家へ歩いた。', 'ヒツジ', 'PERSON', '妹'),
      ('リスが図書館へ歩いた。', 'リス', 'ANIMAL', '犬'), ('スズメが銀行へ走った。', 'スズメ', 'ANIMAL', '猫'), ('ヤギが本部へ走った。', 'ヤギ', 'PERSON', '母'), ('カラスが図書館へ走った。', 'カラス', 'ANIMAL', '鳥')]
for i, (s, h, t, w) in enumerate(AD, 1):
    precheck(s, 'が', h, t, [w], 'SAME')
    new('F-ADOPT-N%02d' % i, 'ADOPT', s, 'が', h, [op(t, [w], 'agent'), {'pick': w}, {'pick': w}], {'status': 'ADOPTED', 'reason': 'ADOPTED', 'word': w},
        'two-hole sentence; every type of the hole word reads agent in this sentence, so the candidate decides the word only; (b\') (type injection) must come back to the same cross')
BP = [('ウサギが図書館へ走った。', 'ウサギ', 'ANIMAL', '鳥'), ('ウサギが図書館へ走った。', 'ウサギ', 'PERSON', '先生'), ('エリートが銀行へ歩いた。', 'エリート', 'PERSON', '母'), ('ライオンが銀行へ歩いた。', 'ライオン', 'ANIMAL', '犬'),
      ('家族が図書館へ走った。', '家族', 'PERSON', '兄'), ('警察が家へ歩いた。', '警察', 'PERSON', '弟'), ('パンダが本部へ走った。', 'パンダ', 'ANIMAL', '猫'), ('ヒツジが家へ歩いた。', 'ヒツジ', 'PERSON', '姉'),
      ('リスが図書館へ歩いた。', 'リス', 'ANIMAL', '鳥'), ('スズメが銀行へ走った。', 'スズメ', 'ANIMAL', '犬'), ('ヤギが本部へ走った。', 'ヤギ', 'PERSON', '兵士')]
for i, (s, h, t, w) in enumerate(BP, 1):
    precheck(s, 'が', h, t, [w], 'SAME')
    new('F-BP-%02d' % i, 'BP', s, 'が', h, [op(t, [w], 'agent'), {'pick': w}, {'pick': w}], {'status': 'ADOPTED', 'reason': 'ADOPTED', 'word': w, 'gate_log_passed': {'a4_role': 'agent', 'b_prime': 'PASSED'}},
        'an adoption: the gate log of the adopted word says (a4) gave the role agent and (b\') passed')

# --- D (two-hole sentences)
TIE = [('ウサギが図書館へ走った。', 'ウサギ', 'ANIMAL', ['犬', '猫']), ('エリートが銀行へ歩いた。', 'エリート', 'PERSON', ['兄', '姉']), ('ライオンが銀行へ歩いた。', 'ライオン', 'ANIMAL', ['鳥', '犬']),
       ('家族が図書館へ走った。', '家族', 'PERSON', ['弟', '妹'])]
for i, (s, h, t, ws) in enumerate(TIE, 1):
    precheck(s, 'が', h, t, ws, 'SAME')
    new('F-D-N%02d' % i, 'D', s, 'が', h, [op(t, ws, 'agent')], {'status': 'NOT_ADOPTED', 'reason': 'GATE_D_TIE', 'word': None}, 'two words pass every gate: abstain, no winner by order')
ABST = [('警察が家へ歩いた。', '警察', 'PERSON', '先生'), ('パンダが本部へ走った。', 'パンダ', 'ANIMAL', '鳥'), ('ヒツジが家へ歩いた。', 'ヒツジ', 'PERSON', '妹')]
for i, (s, h, t, w) in enumerate(ABST, 1):
    precheck(s, 'が', h, t, [w], 'SAME')
    new('F-D-N%02d' % (4 + i), 'D', s, 'が', h, [op(t, [w], 'agent'), {'pick': None}], {'status': 'NOT_ADOPTED', 'reason': 'GATE_D_CHOICE_ABSTAINED', 'word': None}, 'the closed ask abstains (two asks that do not agree)')
NP = [('ウサギが図書館へ走った。', 'ウサギ', 'ANIMAL', ['犬', '猫'], '犬'), ('エリートが銀行へ歩いた。', 'エリート', 'PERSON', ['兄', '姉'], '兄'), ('リスが図書館へ歩いた。', 'リス', 'ANIMAL', ['鳥', '犬'], '鳥')]
for i, (s, h, t, ws, bad) in enumerate(NP, 1):
    precheck(s, 'が', h, t, ws, 'SAME')
    verb = s.split('へ')[1][:-1]
    dest = s.split('が')[1].split('へ')[0]
    neg = {'走った': '走らなかった', '歩いた': '歩かなかった'}[verb]
    new('F-D-N%02d' % (7 + i), 'D', s, 'が', h, [op(t, ws, 'agent'), {'pick': bad}, {'pick': bad}], {'status': 'NOT_ADOPTED', 'reason': 'GATE_D_CHOICE_NOT_PASSING', 'word': None},
        'the closed ask picks the word that gate (c) refused (a record with the opposite polarity says "%s"): only the word that passed every gate may be chosen' % bad,
        records=['母が駅へ%s。' % neg], record_roles=[{'agent': bad, 'goal': dest}])

# --- C through the mouth (a record made by hand: no reader types the hole's word in a record; see the report: r8 gives no readable real record for these)
CM = [('ウサギが図書館へ走った。', 'ウサギ', 'ANIMAL', '犬', '図書館', '走らなかった'), ('エリートが銀行へ歩いた。', 'エリート', 'PERSON', '姉', '銀行', '歩かなかった'),
      ('ライオンが銀行へ歩いた。', 'ライオン', 'ANIMAL', '猫', '銀行', '歩かなかった'), ('パンダが本部へ走った。', 'パンダ', 'ANIMAL', '鳥', '本部', '走らなかった')]
for i, (s, h, t, w, dest, neg) in enumerate(CM, 1):
    precheck(s, 'が', h, t, [w], 'SAME')
    new('F-C-N%02d' % i, 'C', s, 'が', h, [op(t, [w], 'agent')], {'status': 'NOT_ADOPTED', 'reason': 'GATE_C_CONTRADICTS_RECORD', 'word': None},
        'two-hole sentence through the whole pipeline; the record (made by hand with record_roles from a readable sentence of the same predicate) has the same arms and the opposite polarity',
        records=['母が駅へ%s。' % neg], record_roles=[{'agent': w, 'goal': dest}])

# --- BACKEND: the closed ask fails (two-hole sentences: a one-hole sentence no longer reaches the closed ask)
new('F-BACKEND-N01', 'BACKEND', 'ウサギが図書館へ走った。', 'が', 'ウサギ', [op('ANIMAL', ['犬'], 'agent'), {'fail': 'TIMEOUT'}], {'status': 'BACKEND_FAILED', 'reason': 'BACKEND_FAILED:TIMEOUT', 'word': None}, 'the closed ask fails: typed, not "no candidate"')
new('F-BACKEND-N02', 'BACKEND', 'エリートが銀行へ歩いた。', 'が', 'エリート', [op('PERSON', ['姉'], 'agent'), {'fail': 'CONNECT_FAILED'}], {'status': 'BACKEND_FAILED', 'reason': 'BACKEND_FAILED:CONNECT_FAILED', 'word': None}, 'the closed ask fails: typed, not "no candidate"')

ids = [r['id'] for r in out]
assert len(ids) == len(set(ids))
path = os.path.join(W, 'tests/fusion/w10f04/fake_scripts.jsonl')
with open(path, 'w', encoding='utf-8') as f:
    for r in out:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')
print('rows=%d' % len(out), dict(collections.Counter(r['gate'] for r in out)))
print('changed_by_ruling_A', sum(1 for r in out if r.get('r3') == 'expect_changed_by_ruling_A'), 'direct_call', sum(1 for r in out if r.get('r3') == 'direct_call'), 'new', sum(1 for r in out if r.get('r3') == 'new'))
print('reasons_of_changed', dict(collections.Counter(r['expect']['reason'] for r in out if r.get('r3') == 'expect_changed_by_ruling_A')))
