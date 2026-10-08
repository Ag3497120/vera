"""P3 / P5: the frozen fake-backend scripts (tests/fusion/w10f04/fake_scripts.jsonl) through read_with_holes + fill_candidates.ask_and_gate. Deterministic (ids and order injected).
First lines: rows=… mismatch=0 adopted=… per-gate counts; --dump-sent writes every message sent at the backend boundary (for check_sent.py).
r3: a row with `call: gate_b|gate_c` calls that gate function directly (the word and the type are taken from the first step's declaration; nothing is sent to a backend); `record_roles` replaces the roles of the
record crosses made with decode_grammar.cross_of (a record made by hand); `gate_log_passed` / `split_kind` are checked in the gate log."""
import argparse, collections, json, os, sys
from types import SimpleNamespace
from verantyx import semantic_read as S, fill_candidates as F, llm_backend as LB, decode_grammar as G, llm_choice as LC

ap = argparse.ArgumentParser(); ap.add_argument('--data', required=True); ap.add_argument('--out', required=True); ap.add_argument('--dump-sent'); ap.add_argument('--no-mask', action='store_true')
ap.add_argument('--backend-name', default='fake'); a = ap.parse_args()
R8 = os.environ['VERA_PLACEMENT']
rows = [json.loads(l) for l in open(a.data)]
results, mism, sent_dump = [], [], []
counts = collections.Counter(); arms_ok = True

def records_of(r):
    out = {}
    for i, sent in enumerate(r['records']):
        c = G.cross_of(sent)[0]
        if r.get('record_roles'):
            c = dict(c, roles=dict(r['record_roles'][i]))
        out['rec%d' % i] = c
    return SimpleNamespace(crosses=out)


call_rows = 0
pipeline = collections.Counter(); all_b_prime = True
for r in rows:
    ho = S.read_with_holes(r['sentence'], placement=R8)
    idx = next((i for i, h in enumerate(ho['holes']) if (h['particle'], h['head']) == (r['hole']['particle'], r['hole']['head'])), None)
    e = r['expect']
    if r.get('call'):
        call_rows += 1
        q = S._placement_query(R8); decl0 = json.loads(r['steps'][0]['raw']); word, wtype = decl0['near_words'][0], decl0['type']
        if r['call'] == 'gate_b':
            reason, _ = F._gate_b(r['sentence'], ho, idx, word, wtype, q, None, {})
        else:
            reason, _n, _note = F._gate_c(r['sentence'], ho, idx, word, q, records_of(r), {})
        status = 'NOT_ADOPTED' if reason else 'PASSED'
        ok = idx is not None and status == e['status'] and (reason or '').startswith(e['reason']) and e['word'] is None
        if not ok: mism.append((r['id'], e, status, reason, None))
        counts[(r['gate'], status, (reason or '').split(':')[0])] += 1
        results.append({'id': r['id'], 'call': r['call'], 'status': status, 'reason': reason, 'candidate': None, 'gate_log': []})
        continue
    fb = LB.FakeBackend(r['steps'])
    chat = lambda model, msgs, fmt, fb=fb: LB.chat('fake', model, msgs, fmt, fake=fb)
    recs = records_of(r)
    n = [0]
    def ids():
        n[0] += 1; return 'id%03d' % n[0]
    d = F.ask_and_gate(ho, text=r['sentence'], chat=chat, model='fake-model', backend_name=a.backend_name, hole=idx if idx is not None else 0, placement=R8,
                       choice_ledger=LC.ChoiceLedger(None), records=recs if r['records'] else None, mask_user_text=not a.no_mask, id_source=ids,
                       order_source=lambda m: list(range(m)))
    ok = idx is not None and d.status == e['status'] and d.reason.startswith(e['reason']) and (d.candidate == e['word'])
    if ok and e.get('split_kind') is not None:
        ok = any(x.get('split_kind') == e['split_kind'] for x in d.gate_log if x['gate'] == 'a4')
    if ok and e.get('gate_log_passed'):
        passed = [x for x in d.gate_log if x['gate'] == 'passed']
        ok = len(passed) == 1 and all(passed[0].get(k) == v for k, v in e['gate_log_passed'].items())
    if not ok: mism.append((r['id'], e, d.status, d.reason, d.candidate))
    if d.status == 'ADOPTED':
        arms_ok &= d.origin == 'testimony' and d.basis.startswith('LLM_TESTIMONY_FILL:fake-model:')
        all_b_prime &= any(x['gate'] == 'passed' and x.get('b_prime') == 'PASSED' for x in d.gate_log)
    for x in d.gate_log:
        if x['gate'] == 'b_prime': pipeline['b_prime_failed'] += 1
        if x['gate'] == 'b': pipeline['b_failed'] += 1
        if x['gate'] == 'c': pipeline['c_failed'] += 1
    counts[(r['gate'], d.status, d.reason.split(':')[0])] += 1
    results.append({'id': r['id'], 'status': d.status, 'reason': d.reason, 'candidate': d.candidate, 'gate_log': d.gate_log})
    for s_ in fb.sent: sent_dump.append({'id': r['id'], 'messages': s_['messages'], 'fmt': s_['fmt']})
json.dump(results, open(a.out, 'w'), ensure_ascii=False, indent=1) if a.out != '/dev/null' else None
if a.dump_sent:
    with open(a.dump_sent, 'w') as f:
        for s in sent_dump: f.write(json.dumps(s, ensure_ascii=False) + '\n')
gate_rows = collections.Counter(r['gate'] for r in rows)
print('rows=%d mismatch=%d adopted=%d adopted_arms_all_testimony_fill_origin=%s' % (len(rows), len(mism), sum(1 for x in results if x['status'] == 'ADOPTED'), arms_ok))
print('rows_per_gate', dict(gate_rows))
print('outcomes', {'%s/%s/%s' % k: v for k, v in sorted(counts.items())})
print('rows_with_direct_call', call_rows)
print('pipeline_reached', {'b_prime_failed': pipeline['b_prime_failed'], 'b_failed': pipeline['b_failed'], 'c_failed': pipeline['c_failed']}, '(gate-log entries of the rows without a call)')
print('adopted_all_b_prime_passed=%s' % all_b_prime)
byid = {x['id']: x for x in results}
print('tokyo_natsu=%s zeimusho_yoru=%s taiin_heishi=%s' % (byid['F-A3R-01']['reason'], byid['F-A4U-01']['reason'], byid['F-A4S-02']['reason']))
for m in mism: print('  MISMATCH', m)
