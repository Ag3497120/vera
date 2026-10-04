"""P4: the real backend (Ollama, qwen3.5:4b) over the 30 holes of tests/fusion/w10f04/real_holes.jsonl, masked (K286 default). Writes one JSONL row per hole (decision, gate log, Vera/LLM time separately).
First line: holes=… adopted=… not_adopted_by_reason={…} backend_failed=… vera_ms(p50/p95/total) llm_ms(p50/p95/total). The adopted candidates are reviewed BY EYE afterwards (p4_visual_review.md): that is not ground truth."""
import argparse, collections, json, os, statistics, time
from verantyx import event_cross as EC, semantic_read as S, fill_candidates as F, llm_backend as LB, llm_choice as LC
from verantyx.testimony_ledger import TestimonyLedger

ap = argparse.ArgumentParser()
ap.add_argument('--data', required=True); ap.add_argument('--backend', default='ollama'); ap.add_argument('--model', required=True)
ap.add_argument('--ledger-file', required=True); ap.add_argument('--out', required=True); ap.add_argument('--require-realize', action='store_true'); ap.add_argument('--timeout', type=float, default=240.0)
a = ap.parse_args()
R8 = os.environ['VERA_PLACEMENT']
chat = LB.make_chat(a.backend, timeout=a.timeout)
led = TestimonyLedger(a.ledger_file)
rows = [json.loads(l) for l in open(a.data)]
out, reasons = [], collections.Counter()
vera_ms, llm_ms = [], []
for r in rows:
    t0 = time.perf_counter()
    ho = S.read_with_holes(r['text'], placement=R8)
    holes = ho['holes']
    for i in range(len(holes)):
        d = F.ask_and_gate(ho, text=r['text'], chat=chat, model=a.model, backend_name=a.backend, hole=i, placement=R8, ledger=led,
                           choice_ledger=LC.ChoiceLedger(a.ledger_file + '.choice.jsonl'), mask_user_text=True, require_realize=a.require_realize)
        reasons[d.reason.split(':')[0] if d.status != 'ADOPTED' else 'ADOPTED'] += 1
        vera_ms.append(d.timing['vera_ms']); llm_ms.append(d.timing['llm_ms'])
        wt = list(EC.PlaceResult.from_coarse_query(S._placement_query(R8).query(holes[i]['head'])).types)       # r2: the placement's own types of the hole word (M1 table)
        out.append({'id': r['id'], 'text': r['text'], 'hole': {k: holes[i][k] for k in ('particle', 'head', 'expected_types', 'role_candidates')}, 'status': d.status, 'reason': d.reason,
                    'candidate': d.candidate, 'declaration': d.declaration, 'hole_word_types': wt, 'declared_type_is_a_type_of_the_word': (None if not d.declaration or not wt else d.declaration['type'] in wt), 'gate_log': d.gate_log, 'timing': d.timing, 'fill_id': d.fill_id})
with open(a.out, 'w') as f:
    for x in out: f.write(json.dumps(x, ensure_ascii=False) + '\n')
def pct(v, p): return round(sorted(v)[min(len(v) - 1, int(len(v) * p))], 1) if v else None
adopted = sum(1 for x in out if x['status'] == 'ADOPTED')
print('holes=%d sentences=%d adopted=%d not_adopted_by_reason=%s backend_failed=%d' % (len(out), len(rows), adopted, json.dumps(dict(reasons), ensure_ascii=False), sum(1 for x in out if x['status'] == 'BACKEND_FAILED')))
print('vera_ms p50=%s p95=%s total=%s | llm_ms p50=%s p95=%s total=%s' % (pct(vera_ms, .5), pct(vera_ms, .95), round(sum(vera_ms), 1), pct(llm_ms, .5), pct(llm_ms, .95), round(sum(llm_ms), 1)))
print('declared_type_vs_word', dict(collections.Counter(str(x['declared_type_is_a_type_of_the_word']) for x in out)))
a4 = [g for x in out for g in x['gate_log'] if g['gate'] == 'a4']
print('r3 words_that_passed_a1_a3_and_failed_a4=%d (in %d holes; a4 reasons %s; split_kind %s)' % (len(a4), len({x['fill_id'] for x in out if any(g['gate'] == 'a4' for g in x['gate_log'])}), dict(collections.Counter(g['reason'] for g in a4)), dict(collections.Counter(g.get('split_kind') for g in a4 if g.get('split_kind')))))
print('r3 words_by_first_failed_gate', dict(collections.Counter(g['gate'] for x in out for g in x['gate_log'])), '| holes_with_b_prime_failure=%d' % sum(1 for x in out if any(g['gate'] == 'b_prime' for g in x['gate_log'])))
print('percentile: sorted(v)[min(n-1, int(n*p))] over the %d holes (one value per hole; vera_ms excludes the time in the backend)' % len(out))
print('realize_status_of_passed_words', dict(collections.Counter(g.get('realize') for x in out for g in x['gate_log'] if g['gate'] == 'passed')))
