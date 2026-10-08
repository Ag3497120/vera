"""W3-e2 S3 (not a product file): writes the frozen test data tests/reading_soundness/w3e2_p{1,2,3}.jsonl and w3e2_fake_llm.jsonl.
The expectations (mode, assumptions, clauses, added_reason, source) are TYPED HERE, before any stage E2 exists. Only `abstain_reason` (the strict reader's own first reason) is read from
the strict `read()` (that is the thing the stage is conditioned on, not the thing under test). Run before verantyx/ is touched."""
import json, sys
from pathlib import Path
TREE = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(TREE))
from verantyx import semantic_read as SR, semantic_reader as R, constructions
constructions.discover()
PL = {'none': None, 'r8': '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2',
      'r9': '/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2'}
_q = {}
def strict_reason(text, pl):
    if pl not in _q: _q[pl] = None if PL[pl] is None else R.CoarseQuery(PL[pl])
    o = SR.read(text, placement=_q[pl])
    return None if o['readable'] else (o['abstain']['reasons'] or [None])[0]

def clause(pred, roles, pol='+', tense='past'):
    return [{'predicate': pred, 'roles': roles, 'polarity': pol, 'tense': tense, 'modality': None, 'voice': 'active'}]
def F(a, b): return {'answers': [a, b]}
def FE(): return {'error': 'CONNECT_FAILED'}
def src(layer=None, ledger=None, docs=None, llm='none'):
    return {'layer_rows': layer, 'ledger_rows': ledger, 'documents': docs, 'llm': llm}
def L(word, typ, origin='layer_human'): return {'word': word, 'type': typ, 'origin': origin}
def G(word, typ, promotable=True): return {'word': word, 'candidate': word, 'declared_type': typ, 'promotable': promotable}
def A_(word, kind, assumed, source): return [{'word': word, 'kind': kind, 'assumed': assumed, 'source': source}]

rows = {'P1': [], 'P2': [], 'P3': []}
def add(prem, text, pl, sources, mode, assumptions=None, clauses=None, added=None, note=''):
    n = len(rows[prem]) + 1
    rows[prem].append({'id': 'W3E2-%s-%03d' % (prem, n), 'premise': prem, 'input': text, 'placement': pl, 'sources': sources,
                       'expect': {'mode': mode, 'assumptions': assumptions or [], 'clauses': clauses, 'abstain_reason': strict_reason(text, pl), 'added_reason': added}, 'note': note})
FM = 'llm:fake-model'
# ---------------- P1 name type (assumed)
add('P1', 'ハルはミナに本を渡した。', 'r9', src(layer=[L('ミナ', 'PERSON')]), 'assumed', A_('ミナ', 'name_type', 'PERSON', 'layer'),
    clause('渡す', {'agent': 'ハル', 'patient': '本', 'recipient': 'ミナ'}), note='a: layer (direct)')
add('P1', 'ハルはナナに手紙を送った。', 'none', src(layer=[L('ナナ', 'GROUP_ORG')]), 'assumed', A_('ナナ', 'name_type', 'GROUP_ORG', 'layer'),
    clause('送る', {'agent': 'ハル', 'patient': '手紙', 'recipient': 'ナナ'}), note='a: layer; a group can receive')
add('P1', 'ハルはリクに本を渡した。', 'r9', src(ledger=[G('リク', 'PERSON')]), 'assumed', A_('リク', 'name_type', 'PERSON', 'ledger'),
    clause('渡す', {'agent': 'ハル', 'patient': '本', 'recipient': 'リク'}), note='b: ledger promotable')
add('P1', 'ミナが走った。', 'r9', src(), 'assumed', A_('ミナ', 'name_type', 'GROUP_ORG+PERSON', 'surface'),
    clause('走る', {'agent': 'ミナ'}), note='d: surface, が, both readable types give the same cross')
add('P1', 'ナナが来た。', 'none', src(), 'assumed', A_('ナナ', 'name_type', 'GROUP_ORG+PERSON', 'surface'), clause('来る', {'agent': 'ナナ'}), note='d')
add('P1', 'リクが本を読んだ。', 'r8', src(), 'assumed', A_('リク', 'name_type', 'GROUP_ORG+PERSON', 'surface'),
    clause('読む', {'agent': 'リク', 'patient': '本'}), note='d: AGENT_EVIDENCE_MISSING')
add('P1', 'ミナは本を読んだ。', 'none', src(), 'assumed', A_('ミナ', 'name_type', 'GROUP_ORG+PERSON', 'surface'),
    clause('読む', {'agent': 'ミナ', 'patient': '本'}), note='d: は')
add('P1', 'ハルはミナへ荷物を運んだ。', 'r9', src(layer=[L('ミナ', 'PLACE')]), 'assumed', A_('ミナ', 'name_type', 'PLACE', 'layer'),
    clause('運ぶ', {'agent': 'ハル', 'patient': '荷物', 'goal': 'ミナ'}), note='a: へ splits person/place; layer decides')
add('P1', 'ハルはナナへ荷物を運んだ。', 'r9', src(llm=F('PLACE','PLACE')), 'assumed', A_('ナナ', 'name_type', 'PLACE', FM),
    clause('運ぶ', {'agent': 'ハル', 'patient': '荷物', 'goal': 'ナナ'}), note='e: fake llm answers PLACE twice')
add('P1', 'ハルはリクに手紙を送った。', 'r9', src(llm=F('PERSON','PERSON')), 'assumed', A_('リク', 'name_type', 'PERSON', FM),
    clause('送る', {'agent': 'ハル', 'patient': '手紙', 'recipient': 'リク'}), note='e: fake llm answers PERSON twice')
add('P1', 'ハルはミナに住んでいる。', 'none', src(layer=[L('ミナ', 'PLACE', 'layer_estimated')]), 'assumed', A_('ミナ', 'name_type', 'PLACE', 'layer'),
    clause('住む', {'agent': 'ハル', 'place': 'ミナ'}, tense='nonpast'), note='a: layer_estimated may be a source of an assumption')
add('P1', 'ハルはリクへ荷物を運んだ。', 'none', src(ledger=[G('リク', 'PLACE')]), 'assumed', A_('リク', 'name_type', 'PLACE', 'ledger'),
    clause('運ぶ', {'agent': 'ハル', 'patient': '荷物', 'goal': 'リク'}), note='b')
add('P1', 'ミナが走った。', 'none', src(layer=[L('ミナ', 'PERSON')]), 'assumed', A_('ミナ', 'name_type', 'PERSON', 'layer'),
    clause('走る', {'agent': 'ミナ'}), note='a beats d: a layer that knows decides before the surface')
add('P1', 'ハルはミナに本を渡した。', 'none', src(docs=['ミナはよく本を読んだ。', '先生がミナに本を渡した。']), 'assumed', A_('ミナ', 'name_type', 'PERSON', 'documents'),
    clause('渡す', {'agent': 'ハル', 'patient': '本', 'recipient': 'ミナ'}), note='c: documents (may be SOURCE_UNAVAILABLE:documents)')
# ---------------- P1 abstain
add('P1', 'ハルはミナに本を渡した。', 'r9', src(), 'abstain', added='ASSUMPTION_UNDETERMINED:ミナ:に', note='に splits person/place; no source; no back end')
add('P1', 'ハルはナナへ荷物を運んだ。', 'none', src(), 'abstain', added='ASSUMPTION_UNDETERMINED:ナナ:へ', note='へ: no source')
add('P1', 'ハルはリクに住んでいる。', 'r9', src(), 'abstain', added='ASSUMPTION_UNDETERMINED:リク:に', note='に')
add('P1', 'ハルはミナに本を渡した。', 'r9', src(llm=F('PERSON','GROUP_ORG')), 'abstain', added='ASSUMPTION_UNDETERMINED:ミナ:に', note='e: the two answers split (PERSON / GROUP_ORG)')
add('P1', 'ハルはナナに手紙を送った。', 'none', src(llm=F('PLACE','PLACE')), 'abstain', added='ASSUMPTION_UNDETERMINED:ナナ:に', note='e: answer outside the readable candidates (PLACE)')
add('P1', 'ハルはリクに本を渡した。', 'none', src(llm=FE()), 'abstain', added='ASSUMPTION_BACKEND_FAILED:リク:GROUP_ORG+PERSON', note='e: back end failed')
add('P1', 'ハルはミナに本を渡した。', 'none', src(layer=[L('ミナ', 'PERSON'), L('ミナ', 'PLACE')]), 'abstain', added='ASSUMPTION_UNDETERMINED:ミナ:に', note='a: two direct types split; no lower source overrides')
add('P1', 'ハルはナナに本を渡した。', 'r9', src(layer=[L('ナナ', 'PLACE')]), 'abstain', added='ASSUMPTION_UNDETERMINED:ナナ:に', note='a: the layer type is not among the readable candidates')
add('P1', 'ハルはリクに本を渡した。', 'r9', src(ledger=[G('リク', 'PERSON', False)]), 'abstain', added='ASSUMPTION_UNDETERMINED:リク:に', note='b: not promotable = no information')
add('P1', 'ハルはミナにザクった。', 'none', src(), 'abstain', added=None, note='two premises / に before a nonce predicate: stage E2 does not act')
add('P1', 'ハルはミナに会った。', 'r9', src(layer=[L('ミナ', 'PERSON')]), 'abstain', added=None, note='the reason names the predicate, not a name: not a premise')
add('P1', 'ハルはナナへ走った。', 'r9', src(layer=[L('ナナ', 'PLACE')]), 'abstain', added=None, note='NO_SUPPORTED_CLAUSE: not a premise')
add('P1', 'ハルはミナで本を読んだ。', 'none', src(layer=[L('ミナ', 'PLACE')]), 'abstain', added=None, note='NO_SUPPORTED_CLAUSE: not a premise')
add('P1', 'ミナがナナに本を渡した。', 'none', src(), 'abstain', added=None, note='two unknown names: more than one premise (or no premise reason)')
# ---------------- P2 nonce predicate (assumed)
def p2(text, roles, pred, pol='+', tense='past', pl='none', note=''):
    add('P2', text, pl, src(), 'assumed', A_(pred[:-1], 'nonce_predicate', 'UNTYPED_VERB', 'surface'), clause(pred, roles, pol, tense), note=note)
p2('ハルは本をザクった。', {'agent': 'ハル', 'patient': '本'}, 'ザクる')
p2('ハルは本をピロった。', {'agent': 'ハル', 'patient': '本'}, 'ピロる', pl='r8')
p2('ハルは本をクルった。', {'agent': 'ハル', 'patient': '本'}, 'クルる', pl='r9')
p2('ハルは本をザクる。', {'agent': 'ハル', 'patient': '本'}, 'ザクる', tense='nonpast')
p2('ハルは本をザクらない。', {'agent': 'ハル', 'patient': '本'}, 'ザクる', pol='-', tense='nonpast')
p2('ハルは本をザクらなかった。', {'agent': 'ハル', 'patient': '本'}, 'ザクる', pol='-')
p2('ハルは本をピロります。', {'agent': 'ハル', 'patient': '本'}, 'ピロる', tense='nonpast')
p2('ハルは本をヨモりました。', {'agent': 'ハル', 'patient': '本'}, 'ヨモる')
p2('ミナは本をザクった。', {'agent': 'ミナ', 'patient': '本'}, 'ザクる', note='a name as the agent needs no type here')
p2('ハルがザクった。', {'agent': 'ハル'}, 'ザクる')
p2('ハルは机をピロらない。', {'agent': 'ハル', 'patient': '机'}, 'ピロる', pol='-', tense='nonpast')
p2('ハルがヨモります。', {'agent': 'ハル'}, 'ヨモる', tense='nonpast')
p2('ハルはミナをザクった。', {'agent': 'ハル', 'patient': 'ミナ'}, 'ザクる', note='the example of the ticket')
# ---------------- P2 abstain
def p2n(text, note, pl='none', added=None): add('P2', text, pl, src(), 'abstain', added=added, note=note)
p2n('ハルは本をザクられた。', 'passive/potential/honorific split: not read')
p2n('ハルは本をザクられる。', 'られる: not read')
p2n('ハルは本にザクった。', 'に: a particle whose role splits')
p2n('ハルは本でザクった。', 'で')
p2n('ハルは本をそっとザクった。', 'an adverb besides the predicate: not read')
p2n('ハルは、本をザクった。', 'a comma: not read')
p2n('ハルは本をザクって、帰った。', 'two clauses: not read', pl='r9')
p2n('ハルも本をザクった。', 'も: another particle')
p2n('ハルとミナが本をザクった。', 'と: another particle')
p2n('ハルは本はザクった。', 'two は: two agents: not read')
p2n('ハルが本がザクった。', 'two が: not read')
p2n('ハルは本を机をザクった。', 'two を: not read')
p2n('ハルは本をピロれ。', 'imperative: not in the ending table')
# ---------------- P3 unknown noun type (assumed)
def p3(text, word, typ, sources, source, pred, roles, pl='r9', tense='past', note=''):
    add('P3', text, pl, sources, 'assumed', A_(word, 'noun_type', typ, source), clause(pred, roles, tense=tense), note=note)
p3('ハルはフレームへ荷物を運んだ。', 'フレーム', 'PLACE', src(layer=[L('フレーム', 'PLACE')]), 'layer', '運ぶ', {'agent': 'ハル', 'patient': '荷物', 'goal': 'フレーム'})
p3('ハルはホイールへ荷物を運んだ。', 'ホイール', 'PLACE', src(ledger=[G('ホイール', 'PLACE')]), 'ledger', '運ぶ', {'agent': 'ハル', 'patient': '荷物', 'goal': 'ホイール'})
p3('ハルはステムに本を渡した。', 'ステム', 'PERSON', src(llm=F('PERSON','PERSON')), FM, '渡す', {'agent': 'ハル', 'patient': '本', 'recipient': 'ステム'})
p3('フレームが走った。', 'フレーム', 'ANIMAL', src(layer=[L('フレーム', 'ANIMAL', 'layer_estimated')]), 'layer', '走る', {'agent': 'フレーム'})
p3('ブラケットが走った。', 'ブラケット', 'ANIMAL', src(llm=F('ANIMAL','ANIMAL')), FM, '走る', {'agent': 'ブラケット'})
p3('ハルはチューブへ荷物を運んだ。', 'チューブ', 'PLACE', src(layer=[L('チューブ', 'PLACE', 'layer_estimated')]), 'layer', '運ぶ', {'agent': 'ハル', 'patient': '荷物', 'goal': 'チューブ'})
p3('ハルはスプロケットに住んでいる。', 'スプロケット', 'PLACE', src(layer=[L('スプロケット', 'PLACE')]), 'layer', '住む', {'agent': 'ハル', 'place': 'スプロケット'}, tense='nonpast')
p3('ディレイラーが本を読んだ。', 'ディレイラー', 'PERSON', src(ledger=[G('ディレイラー', 'PERSON')]), 'ledger', '読む', {'agent': 'ディレイラー', 'patient': '本'})
p3('キャリパーが来た。', 'キャリパー', 'GROUP_ORG', src(layer=[L('キャリパー', 'GROUP_ORG')]), 'layer', '来る', {'agent': 'キャリパー'})
p3('ハルはシートポストへ荷物を運んだ。', 'シートポスト', 'PLACE', src(llm=F('PLACE','PLACE')), FM, '運ぶ', {'agent': 'ハル', 'patient': '荷物', 'goal': 'シートポスト'})
p3('ハルは歪みに住んでいる。', '歪み', 'PLACE', src(llm=F('PLACE','PLACE')), FM, '住む', {'agent': 'ハル', 'place': '歪み'}, tense='nonpast')
p3('ハルは消耗品に手紙を送った。', '消耗品', 'GROUP_ORG', src(docs=['店主が消耗品を発注した。', '消耗品は店にある。']), 'documents', '送る', {'agent': 'ハル', 'patient': '手紙', 'recipient': '消耗品'}, note='c (may be SOURCE_UNAVAILABLE:documents)')
p3('ハルは油圧ブレーキへ荷物を運んだ。', '油圧ブレーキ', 'PLACE', src(docs=['油圧ブレーキの工房がある。', '客が油圧ブレーキへ行った。']), 'documents', '運ぶ', {'agent': 'ハル', 'patient': '荷物', 'goal': '油圧ブレーキ'}, note='c')
# ---------------- P3 abstain
def p3n(text, sources, added, note, pl='r9'): add('P3', text, pl, sources, 'abstain', added=added, note=note)
p3n('ハルはフレームへ荷物を運んだ。', src(), 'ASSUMPTION_UNDETERMINED:フレーム:へ', 'no source')
p3n('フレームが走った。', src(), 'ASSUMPTION_UNDETERMINED:フレーム:が', 'no surface for P3 (D10): が alone does not decide')
p3n('ホイールが本を読んだ。', src(), 'ASSUMPTION_UNDETERMINED:ホイール:が', 'no surface for P3')
p3n('ハルはステムに本を渡した。', src(layer=[L('ステム', 'ARTIFACT')]), 'ASSUMPTION_UNDETERMINED:ステム:に', 'a: the layer type is not a readable candidate')
p3n('ハルはステムへ荷物を運んだ。', src(layer=[L('ステム', 'PLACE'), L('ステム', 'ANIMAL')]), 'ASSUMPTION_UNDETERMINED:ステム:へ', 'a: split')
p3n('ハルはブラケットに本を渡した。', src(llm=F('PERSON','ANIMAL')), 'ASSUMPTION_UNDETERMINED:ブラケット:に', 'e: split answers')
p3n('ハルはチューブに本を渡した。', src(llm=F('ARTIFACT','ARTIFACT')), 'ASSUMPTION_UNDETERMINED:チューブ:に', 'e: out of the readable candidates')
p3n('ハルはフレームへ荷物を運んだ。', src(llm=FE()), 'ASSUMPTION_BACKEND_FAILED:フレーム:PLACE', 'e: back end failed')
p3n('ハルはホイールへ荷物を運んだ。', src(ledger=[G('ホイール', 'PLACE', False)]), 'ASSUMPTION_UNDETERMINED:ホイール:へ', 'b: not promotable')
p3n('ハルはスプロケットへ荷物を運んだ。', src(ledger=[G('スプロケット', 'PLACE'), G('スプロケット', 'ANIMAL')]), 'ASSUMPTION_UNDETERMINED:スプロケット:へ', 'b: two promotable types split')
p3n('ハルはフレームへ荷物を運んだ。', src(layer=[L('フレーム', 'PLACE')]), None, 'no placement: a word is not UNPLACED without one, so P3 does not stand', pl='none')
p3n('ハルはフレームで走った。', src(layer=[L('フレーム', 'PLACE')]), None, 'not a premise reason')
p3n('ハルはディレイラーとステムに本を渡した。', src(layer=[L('ディレイラー', 'PERSON')]), None, 'not a premise reason (と)')
for prem in rows:
    with open(str(TREE) + '/tests/reading_soundness/w3e2_%s.jsonl' % prem.lower(), 'w', encoding='utf-8') as f:
        for r in rows[prem]: f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(prem, len(rows[prem]), sum(1 for r in rows[prem] if r['expect']['mode'] == 'assumed'))
