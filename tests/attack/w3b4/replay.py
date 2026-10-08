"""Print the reproducible W3-b4 attack outputs (fake and requested r8/run2 placement)."""
import json
import os
from collections import Counter

from test_attack_w3b4 import PROMPT_CASES, R8, _base_entry, entry_result, focus_result, is_lossy, probes, query_for, role_overlap_probes, SR, R


def clean(out):
    return {'readable': out.get('readable'),
            'roles': (out.get('clauses') or [{}])[0].get('roles'),
            'abstain': out.get('abstain')}


all_probes = probes()
fake_hits = []
for p in all_probes:
    out = entry_result(p)
    roles = (out.get('clauses') or [{}])[0].get('roles') or {}
    if out.get('readable') and is_lossy(p, roles):
        fake_hits.append({'id': p.case_id, 'input': p.text, 'roles': roles})

gate_ids = {'A004', 'A026', 'A027', 'A028', 'A029', 'A030', 'A039', 'A046', 'A054', 'A059',
            'C002', 'C006', 'C016', 'C020', 'C026', 'C030', 'C036', 'C038'}
gate_misses = []
for p in all_probes:
    if p.case_id in gate_ids and focus_result(p.text) is None:
        gate_misses.append({'id': p.case_id, 'input': p.text,
                            'tokens': [[w.surface, w.feature.pos1, w.feature.pos2] for w, _, _ in R._tokens(p.text)]})

false_probe = next(p for p in all_probes if p.case_id == 'D10')
false_direct = entry_result(false_probe)
no_answer = entry_result(false_probe, {'右': None})

real_ids = {'A026', 'A054', 'A059', 'D01', 'D03', 'D06', 'D08', 'D10'}
k188_texts = ('兄が倉庫へさえ行った。', '兄が駅からさえ走った。', '兄が弟にさえ話した。',
              '兄が絵をさえ描いた。', '去年、兄が東京にさえ行った。')
real_rows = []
real_answers = {}
k188_rows = []
if os.path.isdir(R8):
    query = R.CoarseQuery(R8)
    for p in all_probes:
        if p.case_id in real_ids:
            real_rows.append({'id': p.case_id, 'input': p.text, 'output': clean(SR.read(p.text, 'ja', placement=query)),
                              'diagnosis': SR.typed_explain_ja(p.text, query)})
    for term in ('右', '東', '荷車', '倉庫', '押す', '運ぶ', '打つ'):
        real_answers[term] = query.query(term)
    for text in k188_texts:
        ex = SR.typed_explain_ja(text, query)
        k188_rows.append({'input': text, 'output': clean(SR.read(text, 'ja', placement=query)), 'diagnosis': ex})

diagnostics = []
for p in all_probes:
    if p.case_id.startswith('D'):
        diagnostics.append({'id': p.case_id, 'input': p.text, 'entry': clean(entry_result(p)),
                            'w3b2': SR.typed_explain_ja(p.text, query_for(p)).get('w3b2')})

overlap_diagnostics = []
for p in role_overlap_probes():
    overlap_diagnostics.append({'id': p.case_id, 'input': p.text, 'entry': clean(entry_result(p)),
                                'w3b2': SR.typed_explain_ja(p.text, query_for(p)).get('w3b2')})

prompt_rows = []
reader_only_baseline = []
if os.path.isdir(R8):
    query = R.CoarseQuery(R8)
    base_entry = _base_entry()
    for case_id, text, category in PROMPT_CASES:
        out = SR.read(text, 'ja', placement=query)
        prompt_rows.append({'id': case_id, 'category': category, 'input': text, 'output': clean(out),
                            'diagnosis': SR.typed_explain_ja(text, query)})
        if case_id in ('P02', 'P03', 'P10', 'P11'):
            before = base_entry.read(text, 'ja', placement=query)
            reader_only_baseline.append({'id': case_id, 'input': text, 'base_entry': clean(before),
                                         'current_entry': clean(out), 'same': before == out})

pair_counts = Counter((ptype, particle) for ptype, rows in R.typed_frames_v2().items()
                      for _, particles, _, _ in rows for particle in particles)
duplicate_keys = {str(key): count for key, count in pair_counts.items() if count > 1}

print(json.dumps({'preregistered_cases': len(all_probes), 'fake_misreads': fake_hits,
                  'focus_gate_misses': gate_misses, 'false_direct_case': {'id': 'D10', 'direct': clean(false_direct), 'without_right_answer': clean(no_answer)},
                  'r8_run2_available': os.path.isdir(R8), 'r8_run2': real_rows, 'r8_answers': real_answers,
                  'k188_published_examples_r8': k188_rows,
                  'table_duplicate_type_particle_keys': duplicate_keys, 'role_overlap_probes': diagnostics,
                  'extra_role_overlap_probes': overlap_diagnostics, 'prompt_examples_r8': prompt_rows,
                  'reader_only_baseline': reader_only_baseline}, ensure_ascii=False, indent=2))
