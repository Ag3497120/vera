"""W5-d G4: a synthetic probe of the basis policy, run on the inputs frozen in artifacts/w5-d/g4_inputs.json (sha256 in g4_inputs.sha256, checked here).
  (1) self-reported documents: a `family: document` source whose text is not in what was handed over -> no ANSWER_* outcome (counts ANSWER_*), and controls
      (sentences really in the handed-over documents) -> an answer (counts).
  (2) confirmation records of another wording: a yes for one sentence, then the same question with the sentence generated now differing -> no ANSWER_*;
      controls (exactly the same sentence) -> ANSWER_HUMAN_BASIS.
Writes artifacts/w5-d/g4_result.json. Uses its own temp dirs and a temp sovereign store (under the scratchpad given by --tmp or the system temp dir)."""
import hashlib, json, os, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
A = HERE.parent
TREE = A.parent.parent
sys.path.insert(0, str(TREE))
from verantyx import basis_policy as bp, sovereign as sov
assert bp.__file__.startswith(str(TREE)), bp.__file__
frozen = (A / 'g4_inputs.sha256').read_text().split()[0]
raw = (A / 'g4_inputs.json').read_bytes()
assert hashlib.sha256(raw).hexdigest() == frozen, 'g4_inputs.json changed after it was frozen'
spec = json.loads(raw.decode('utf-8'))
tmp = Path(tempfile.mkdtemp(prefix='g4_', dir=sys.argv[1] if len(sys.argv) > 1 else None))
for k in ('VERA_SOVEREIGN_ROOT', 'VERA_SOVEREIGN_STORE', 'VERA_P4_INDEX'): os.environ.pop(k, None)
files = {}
for name, body in spec['bodies'].items():
    p = tmp / name; p.write_text(body, encoding='utf-8'); files[name] = str(p)
def sha_of(name): return hashlib.sha256(spec['bodies'][name].encode('utf-8')).hexdigest()
def doc_arg(d):
    if d.startswith('MISSING:'): return str(tmp / d.split(':', 1)[1])
    if d.startswith('DIR:'):
        dd = tmp / ('dir_' + d.split(':', 1)[1].replace('.', '_')); dd.mkdir(exist_ok=True)
        (dd / d.split(':', 1)[1]).write_text(spec['bodies'][d.split(':', 1)[1]], encoding='utf-8'); return str(dd)
    return files[d]
def answer(sources, text='答え。'): return {'kind': 'answer', 'verdict': 'ANSWER', 'text': text, 'sources': sources, 'evidence': [], 'door': 'g4'}
def is_answer(out): return str(out['basis_policy']['outcome']).startswith('ANSWER') or out.get('verdict') == 'ANSWER'
res = {'self_reported': [], 'self_reported_controls': [], 'record_variants': [], 'record_controls': []}
for group in ('self_reported', 'self_reported_controls'):
    for c in spec[group]:
        src = dict(c['source'])
        if 'sha256_of_body' in src: src['sha256'] = sha_of(src.pop('sha256_of_body'))
        try:
            out, rc = bp.apply_to_ask(answer([src]), bp.AskPolicy(), query='内容は？', mode=c.get('mode', 'round5'), documents=[doc_arg(d) for d in c['documents']])
        except Exception as exc:      # recorded, never counted as an answer (the tree before W5-d raises on a blank text: borrow_form -> ReadError)
            res[group].append({'id': c['id'], 'exception': type(exc).__name__, 'answered': False})
            continue
        res[group].append({'id': c['id'], 'outcome': out['basis_policy']['outcome'], 'basis_original': out['basis_policy']['basis_original'], 'verdict': out.get('verdict'), 'answered': is_answer(out)})
Q = '何が起きましたか？'
def gen_result(claim): return answer([{'family': 'local', 'source': 'local:new:1', 'source_file': 'n.jsonl', 'line': 1, 'sha': 'n', 'origin': 'generated', 'text': claim}], claim)
def run_record(c, idx):
    root = str(tmp / ('sov%d' % idx)); sid = 's%d' % idx
    assert sov.create(root, sid, 'owner', consent_promote=True)['verdict'] == 'CREATED'
    os.environ['VERA_SOVEREIGN_ROOT'] = root; os.environ['VERA_SOVEREIGN_STORE'] = sid
    confirmed = c.get('confirmed', spec['confirmed_claim'])
    for n in range(c.get('records', 1)):
        if n == 0:
            q, _ = bp.apply_to_ask(gen_result(confirmed), bp.AskPolicy(human_present=True), query=Q, mode='legacy', documents=[])
            r, _ = bp.apply_to_ask(gen_result(confirmed), bp.AskPolicy(confirm=(q['confirm']['id'], 'yes')), query=Q, mode='legacy', documents=[])
            assert r['verdict'] == 'CONFIRMED_HUMAN_RECORD', r
        else:      # a second record of the same sentence under another id
            sov.append_basis_confirmation(root, sid, {'record': 'basis_confirmation', 'status': 'HUMAN_CONFIRMED', 'witness': 'user_confirmation', 'confirm_id': 'extra%d' % n, 'query': Q,
                                                      'claim': confirmed, 'origin': 'human_confirmed', 'generated_sources': [{'family': 'local', 'source_id': 'local:f:1', 'sha': 'h0'}], 'table_version': 1})
    out, rc = bp.apply_to_ask(gen_result(c['current']), bp.AskPolicy(), query=Q, mode='legacy', documents=[])
    return {'id': c['id'], 'outcome': out['basis_policy']['outcome'], 'verdict': out.get('verdict'), 'answered': is_answer(out),
            'text_is_the_confirmed_old_sentence': out.get('text') == confirmed and confirmed != c['current'],
            'claim_differs': out['basis_policy']['sovereign'].get('confirmed_records_claim_differs')}
i = 0
for group in ('record_variants', 'record_controls'):
    for c in spec[group]:
        i += 1; res[group].append(run_record(c, i))
summary = {
    'self_reported_cases': len(res['self_reported']), 'self_reported_exceptions': sum('exception' in r for r in res['self_reported']), 'self_reported_ANSWER': sum(r['answered'] for r in res['self_reported']),
    'self_reported_controls': len(res['self_reported_controls']), 'self_reported_controls_answered': sum(r['answered'] for r in res['self_reported_controls']),
    'record_variant_cases': len(res['record_variants']), 'record_variant_ANSWER': sum(r['answered'] for r in res['record_variants']),
    'record_variant_old_sentence_returned': sum(r['text_is_the_confirmed_old_sentence'] for r in res['record_variants']),
    'record_controls': len(res['record_controls']), 'record_controls_answered': sum(r['answered'] for r in res['record_controls'])}
(A / 'g4_result.json').write_text(json.dumps({'inputs_sha256': frozen, 'summary': summary, 'results': res}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False))
