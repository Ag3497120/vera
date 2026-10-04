#!/usr/bin/env python3
"""W3-b1 (A7): the rows of the measurement table of docs/READING_SOUNDNESS.md section 10 (K66), recomputed from the files of artifacts/w3-b1/.
Prints a markdown table; every line of it must be in the docs (the command of docs/READING_SOUNDNESS.md section 10 checks that). No number is typed in here.
Usage: python tests/reading_soundness/w3b1_recompute.py [ARTIFACT_DIR]     (standard library only)
"""
import collections, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
A = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent.parent / 'artifacts' / 'w3-b1'


def jl(p): return [json.loads(l) for l in Path(p).read_text(encoding='utf-8').splitlines() if l.strip()]
def js(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def txt(p): return Path(p).read_text(encoding='utf-8')


rows = []
def row(item, value, source): rows.append('| %s | %s | %s |' % (item, value, source))


# --- the new data
data = jl(HERE / 'ja_r8.jsonl') + jl(HERE / 'en_r4.jsonl')
c = collections.Counter((r['path'], r['entry_expect']) for r in data)
row('new data: rows (ja_r8 / en_r4)', '%d (%d / %d)' % (len(data), sum(r['lang'] == 'ja' for r in data), sum(r['lang'] == 'en' for r in data)), 'tests/reading_soundness/ja_r8.jsonl, en_r4.jsonl')
for path in ('U', 'S4', 'EN'):
    row('new data: path %s, read-expected / abstain-expected' % path, '%d / %d' % (c[(path, 'read')], c[(path, 'abstain')]), 'ja_r8.jsonl, en_r4.jsonl (r8_counts.txt)')
u = [r for r in data if r['path'] == 'U']
types = sorted({r['pred_type'] for r in u})
row('new data: path U, rows per predicate type (read-expected + abstain-expected)', ', '.join('%s %d+%d' % (t, sum(r['pred_type'] == t and r['entry_expect'] == 'read' for r in u), sum(r['pred_type'] == t and r['entry_expect'] == 'abstain' for r in u)) for t in types), 'ja_r8.jsonl')
# --- round 3: the data ja_r9 (endings of the predicate), before and after the gate on the ending
r9 = jl(HERE / 'ja_r9.jsonl')
c9 = collections.Counter((r['path'], r['entry_expect']) for r in r9)
row('round 3 data ja_r9: rows (path U / path S4)', '%d (%d / %d)' % (len(r9), sum(r['path'] == 'U' for r in r9), sum(r['path'] == 'S4' for r in r9)), 'tests/reading_soundness/ja_r9.jsonl, r9_counts.txt')
row('round 3 data ja_r9: read-expected / abstain-expected, path U and path S4', '%d / %d, %d / %d' % (c9[('U', 'read')], c9[('U', 'abstain')], c9[('S4', 'read')], c9[('S4', 'abstain')]), 'ja_r9.jsonl, r9_counts.txt')
b9 = js(A / 'r9_before_gate_live.json')['summary']; a9 = js(A / 'r9_entry_check.json')['summary']
row('ja_r9 through the entry with the placement, without the gate on the ending (written before the gate): verdicts', ', '.join('%s %d' % kv for kv in sorted(b9['verdicts'].items())), 'r9_before_gate_live.json')
row('ja_r9 without the gate: abstain-expected rows the entry reads', '%d' % b9['entry_expect_mismatch']['abstain_expected_but_read'], 'r9_before_gate_live.json')
row('ja_r9 through the entry with the placement, with the gate on the ending: verdicts', ', '.join('%s %d' % kv for kv in sorted(a9['verdicts'].items())), 'r9_entry_check.json')
row('ja_r9 with the gate: misread / incomplete / UNJUDGED', '%d / %d / %d' % (a9['misread'], a9['incomplete'], a9['unjudged']), 'r9_entry_check.json')
row('ja_r9 with the gate: bad verdicts identical to the output with no placement', '%d of %d' % (a9['bad_verdicts'].get('bad_verdict_identical_to_no_placement', 0), a9['bad_verdicts'].get('bad_verdict_total', 0)), 'r9_entry_check.json')
row('ja_r9 with the gate: read-expected rows the entry abstains on / abstain-expected rows the entry reads', '%d / %d' % (a9['entry_expect_mismatch']['read_expected_but_abstained'], a9['entry_expect_mismatch']['abstain_expected_but_read']), 'r9_entry_check.json')
row('ja_r9 with the gate: second reasons by prefix', ', '.join('%s %d' % kv for kv in sorted(a9['second_reason_prefixes'].items())), 'r9_entry_check.json')
# --- round 4: the data ja_r10 (derived verbs: potential, short causative; and the verbs to compare with), before and after the gate on a head that may be a derived verb
r10 = jl(HERE / 'ja_r10.jsonl'); by_id = {r['id']: r for r in r10}
c10 = collections.Counter((r['path'], r['entry_expect']) for r in r10)
row('round 4 data ja_r10: rows (path U / path S4)', '%d (%d / %d)' % (len(r10), sum(r['path'] == 'U' for r in r10), sum(r['path'] == 'S4' for r in r10)), 'tests/reading_soundness/ja_r10.jsonl, r10_counts.txt')
row('round 4 data ja_r10: read-expected / abstain-expected, path U and path S4', '%d / %d, %d / %d' % (c10[('U', 'read')], c10[('U', 'abstain')], c10[('S4', 'read')], c10[('S4', 'abstain')]), 'ja_r10.jsonl, r10_counts.txt')
kinds10 = collections.Counter(r['derived'] for r in r10)
row('round 4 data ja_r10: rows by kind', ', '.join('%s %d' % kv for kv in sorted(kinds10.items())), 'ja_r10.jsonl, r10_counts.txt')
b10 = js(A / 'r10_before_gate_live.json')['summary']; a10c = js(A / 'r10_entry_check.json'); a10 = a10c['summary']
row('ja_r10 through the entry with the placement, without the gate on a head that may be a derived verb (written before the gate): verdicts', ', '.join('%s %d' % kv for kv in sorted(b10['verdicts'].items())), 'r10_before_gate_live.json')
row('ja_r10 without the gate: misread / incomplete / UNJUDGED', '%d / %d / %d' % (b10['misread'], b10['incomplete'], b10['unjudged']), 'r10_before_gate_live.json')
row('ja_r10 through the entry with the placement, with the gate: verdicts', ', '.join('%s %d' % kv for kv in sorted(a10['verdicts'].items())), 'r10_entry_check.json')
row('ja_r10 with the gate: misread / incomplete / UNJUDGED', '%d / %d / %d' % (a10['misread'], a10['incomplete'], a10['unjudged']), 'r10_entry_check.json')
row('ja_r10 with the gate: read-expected rows the entry abstains on / abstain-expected rows the entry reads', '%d / %d' % (a10['entry_expect_mismatch']['read_expected_but_abstained'], a10['entry_expect_mismatch']['abstain_expected_but_read']), 'r10_entry_check.json')
row('ja_r10 with the gate: second reasons by prefix', ', '.join('%s %d' % kv for kv in sorted(a10['second_reason_prefixes'].items())), 'r10_entry_check.json')
gated10 = collections.Counter()
for rr in a10c['rows']:
    rs = rr['reasons'] or []
    if not rr['readable'] and len(rs) == 2 and rs[1].startswith('PLACEMENT_PREDICATE_POSSIBLY_DERIVED:'): gated10[(by_id[rr['id']]['path'], by_id[rr['id']]['derived'])] += 1
row('ja_r10 rows that the gate on a head that may be a derived verb stopped, by path and kind', ', '.join('%s %s %d' % (k[0], k[1], v) for k, v in sorted(gated10.items())) or 'none', 'r10_entry_check.json, ja_r10.jsonl')
read10 = collections.Counter((by_id[rr['id']]['path'], by_id[rr['id']]['derived']) for rr in a10c['rows'] if rr['readable'])
row('ja_r10 rows read by the entry with the gate, by path and kind', ', '.join('%s %s %d' % (k[0], k[1], v) for k, v in sorted(read10.items())), 'r10_entry_check.json, ja_r10.jsonl')
byk = collections.defaultdict(collections.Counter)
for rr in a10c['rows']:
    rs = rr['reasons'] or []
    byk[(by_id[rr['id']]['path'], by_id[rr['id']]['derived'])]['read' if rr['readable'] else (rs[1].split(':')[0] if len(rs) > 1 else 'one reason only')] += 1
for k in sorted(byk):
    row('ja_r10 with the gate, %s %s: read / second reasons by prefix' % k, ', '.join('%s %d' % kv for kv in sorted(byk[k].items())), 'r10_entry_check.json, ja_r10.jsonl')
r3live = {r['text']: r for r in jl(A / 'r3_entry_live.jsonl')}; r4live = {r['text']: r for r in jl(A / 'r4_entry_live.jsonl')}
ret = sorted((r4live[t]['source'], t) for t in r3live if t in r4live and r3live[t]['out'].get('readable') and not r4live[t]['out'].get('readable'))
row('round 3 -> round 4 (same inputs): read with the placement in round 3 and abstained in round 4, by the file the input comes from', ', '.join('%s %d' % kv for kv in sorted(collections.Counter(s for s, _ in ret).items())) or 'none', 'r3_entry_live.jsonl, r4_entry_live.jsonl')
row('round 3 -> round 4 (same inputs): read in both with a different output / abstained in round 3 and read in round 4 / abstained in both with a different output', '%d / %d / %d' % (
    sum(1 for t in r3live if t in r4live and r3live[t]['out'].get('readable') and r4live[t]['out'].get('readable') and r3live[t]['out'] != r4live[t]['out']),
    sum(1 for t in r3live if t in r4live and not r3live[t]['out'].get('readable') and r4live[t]['out'].get('readable')),
    sum(1 for t in r3live if t in r4live and not r3live[t]['out'].get('readable') and not r4live[t]['out'].get('readable') and r3live[t]['out'] != r4live[t]['out'])), 'r3_entry_live.jsonl, r4_entry_live.jsonl')
live2, live3 = jl(A / 'r2_entry_live.jsonl'), jl(A / 'r4_entry_live.jsonl')   # history rows are fixed to the round-4 output (W3-b1-5: the W5-a abstentions are not counted as the gate's)

t2 = {r['text']: r['out'] for r in live2}
back = sorted(r['text'] for r in live3 if r['source'] == 'ja_r8.jsonl' and t2.get(r['text'], {}).get('readable') and not r['out'].get('readable'))
row('ja_r8 rows read with the placement before the gate that the gate returned to abstention', '%d of %d' % (len(back), sum(1 for r in live3 if r['source'] == 'ja_r8.jsonl' and t2.get(r['text'], {}).get('readable'))), 'r2_entry_live.jsonl, r4_entry_live.jsonl')
changed_r2 = sum(1 for r in live3 if r['text'] in t2 and t2[r['text']].get('readable') and r['out'].get('readable') and t2[r['text']] != r['out'])
row('inputs read with the placement before the gate and after it with a different output', '%d' % changed_r2, 'r2_entry_live.jsonl, r4_entry_live.jsonl')
# --- the entry on the new data with the real placement
chk = js(A / 'r8_entry_check.json')['summary']
row('entry with the placement on the new data: verdicts', ', '.join('%s %d' % kv for kv in sorted(chk['verdicts'].items())), 'r8_entry_check.json')
row('entry with the placement on the new data: misread / incomplete / UNJUDGED', '%d / %d / %d' % (chk['misread'], chk['incomplete'], chk['unjudged']), 'r8_entry_check.json')
row('entry with the placement on the new data: bad verdicts identical to the output with no placement', '%d of %d' % (chk['bad_verdicts'].get('bad_verdict_identical_to_no_placement', 0), chk['bad_verdicts'].get('bad_verdict_total', 0)), 'r8_entry_check.json')
row('new data: read-expected rows the entry abstains on / abstain-expected rows the entry reads', '%d / %d' % (chk['entry_expect_mismatch']['read_expected_but_abstained'], chk['entry_expect_mismatch']['abstain_expected_but_read']), 'r8_entry_check.json')
row('new data: abstained rows whose second reason is not the registered prefix', '%d' % chk['reason_prefix_mismatch_among_abstained'], 'r8_entry_check.json')
exc = js(HERE / 'w3b1_expect_exceptions.json')['exceptions']
row('declared exceptions (w3b1_expect_exceptions.json) by kind', ', '.join('%s %d' % kv for kv in sorted(collections.Counter(e['kind'] for e in exc).items())), 'tests/reading_soundness/w3b1_expect_exceptions.json')
# --- against the base commit
dev, now = jl(A / 'entry_dev.jsonl'), jl(A / 'entry_live.jsonl')
k = collections.Counter(); newly_by_source = collections.Counter(); second = collections.Counter(); changed_stripped = changed_as_is = 0
def strip(o):
    o = json.loads(json.dumps(o))
    for cl in o.get('clauses') or []: cl.pop('predicate_basis', None); cl.pop('role_basis', None)
    return o
for d, n in zip(dev, now):
    do, no = d['out'], n['out']
    if do == no: k['same'] += 1; continue
    if 'error' in do or 'error' in no: k['error_changed'] += 1
    elif not do['readable'] and not no['readable']:
        k['reason_changed'] += 1
        for r in no['abstain']['reasons']:
            if r not in do['abstain']['reasons']: second[r.split(':')[0]] += 1
    elif not do['readable'] and no['readable']: k['false->readable'] += 1; newly_by_source[d['source']] += 1
    elif do['readable'] and not no['readable']: k['readable->false'] += 1
    else:
        changed_as_is += 1
        if (do['clauses'], do['relations']) != (strip(no)['clauses'], strip(no)['relations']): changed_stripped += 1
row('base-commit comparison: inputs (x3 + English + B1 samples + event cross sentences + new data)', len(dev), 'entry_dev.jsonl, entry_live.jsonl')
row('base-commit comparison: same / reason_changed', '%d / %d' % (k['same'], k['reason_changed']), 'entry_dev.jsonl, entry_live.jsonl, base_diff_summary.txt')
row('base-commit comparison: false->readable / readable->false', '%d / %d' % (k['false->readable'], k['readable->false']), 'entry_dev.jsonl, entry_live.jsonl, base_diff_summary.txt')
row('base-commit comparison: changed (source fields taken out) / changed (as they are) / error_changed', '%d / %d / %d' % (changed_stripped, changed_as_is, k['error_changed']), 'entry_dev.jsonl, entry_live.jsonl')
row('false->readable by the file the input comes from', ', '.join('%s %d' % kv for kv in sorted(newly_by_source.items())) or 'none', 'base_diff.jsonl')
labels = collections.Counter(json.loads(l)['verdict'] for l in txt(A / 'base_diff.jsonl').splitlines() if l.strip() and json.loads(l)['kind'] == 'false->readable')
row('false->readable verdicts', ', '.join('%s %d' % kv for kv in sorted(labels.items())) or 'none', 'base_diff.jsonl')
row('reason_changed: reasons added, by prefix', ', '.join('%s %d' % kv for kv in sorted(second.items())), 'entry_dev.jsonl, entry_live.jsonl')
x3 = [r for r in dev if r['source'] not in ('en.jsonl', 'en_r2.jsonl', 'B1_v2', 'B1_v2_r2', 'B1_v2_r3', 'ja_r8.jsonl', 'en_r4.jsonl', 'ja_r9.jsonl', 'ja_r10.jsonl') and not r['source'].startswith('sentences_')]
row('x3 sentences in the comparison: count / newly readable with the placement', '%d / %d' % (len(x3), sum(1 for d, n in zip(dev, now) if d['source'] in {r['source'] for r in x3} and not d['out'].get('readable') and n['out'].get('readable'))), 'entry_dev.jsonl, entry_live.jsonl')
# --- the reader itself
row('reader (document_view) on the x3 sentences: byte-for-byte as the base commit', 'yes (%d lines)' % len(jl(A / 'x3_after.jsonl')) if (A / 'x3_after.jsonl').read_bytes() == (A / 'x3_dev.jsonl').read_bytes() else 'NO', 'x3_after.jsonl, x3_dev.jsonl')
sc = txt(A / 'soundness_compare.txt').split()
row('frozen banks (harness): sentences / changed / misread', '%s / %s / %s' % (sc[1], sc[3], sc[5]), 'soundness_compare.txt')
row('a3_check output same as the base commit', 'yes' if [l for l in txt(A / 'a3_dev.txt').splitlines() if not l.startswith('tree=')] == [l for l in txt(A / 'a3_after.txt').splitlines() if not l.startswith('tree=')] else 'NO', 'a3_dev.txt, a3_after.txt')
# --- no placement
row('entry with no placement: output equal to the base commit on all inputs', 'yes' if (A / 'entry_none.jsonl').read_bytes() == (A / 'entry_dev.jsonl').read_bytes() else 'NO', 'entry_none.jsonl, entry_dev.jsonl')
# --- direct only
a3 = {m: re.search(r'newly_readable (\d+) readable_changed (\d+)', l) for l in txt(A / 'a3_direct_only.txt').splitlines() for m in ('estimated', 'multiple') if l.startswith(m)}
for m in ('estimated', 'multiple'):
    row('answers rewritten to %s only: newly readable / readable and changed' % m, '%s / %s' % a3[m].groups(), 'a3_direct_only.txt')
# --- the self-made B1 samples
for f in ('B1_v2', 'B1_v2_r2', 'B1_v2_r3'):
    s = js(A / ('bs_' + f) / 'summary.json')['classes']
    row('B1 sample %s through the scorer (no placement reaches the child process): correct / correct_abstain / over_abstain / misread / wrong' % f,
        ' / '.join(str(s[x]['count']) for x in ('correct', 'correct_abstain', 'over_abstain', 'misread', 'wrong')), 'bs_%s/summary.json' % f)
b1 = js(A / 'b1_fixtures_live.json')['summary']
row('B1 samples in-process with the placement: verdicts', ', '.join('%s %d' % kv for kv in sorted(b1['verdicts'].items())) + '; misread %d, incomplete %d' % (b1['misread'], b1['incomplete']), 'b1_fixtures_live.json')
# --- questions and time
q = js(A / 'queries_live.json')
row('placement questions over all inputs: total / most for one input / inputs with a question', '%d / %d / %d' % (q['questions_total'], q['questions_max_per_input'], q['inputs_with_a_question']), 'queries_live.json')
row('placement answers by state/origin/basis', ', '.join('%s %d' % kv for kv in sorted(q['answers_by_state_origin_basis'].items())), 'queries_live.json')
t = js(A / 'timing_live.json'); t0 = js(A / 'timing_none.json')
if 'skipped' in t or 'skipped' in t0:
    row('time per input', 'skipped (load)', 'timing_live.json')
else:
    row('time per input with the placement (median / mean / max, ms) at 1-min load %.2f' % t['load_1min_before'], '%s / %s / %s' % (t['median_ms_per_input'], t['mean_ms_per_input'], t['max_ms_per_input']), 'timing_live.json')
    row('time per input with no placement (median / mean / max, ms) at 1-min load %.2f' % t0['load_1min_before'], '%s / %s / %s' % (t0['median_ms_per_input'], t0['mean_ms_per_input'], t0['max_ms_per_input']), 'timing_none.json')
# --- the members of the two types in four frames (probe_members.txt)
pm = txt(A / 'probe_members.txt').splitlines()
m1 = re.match(r'frames_tried=(\d+) newly_readable=(\d+) members_of_the_two_types=(\d+)', pm[0]); m2 = re.match(r'placement predicates \(ns=P headwords\): (\d+), of them written with ASCII only: (\d+)', pm[1])
row('members of the two read types: members / frames tried / newly readable', '%s / %s / %s' % (m1.group(3), m1.group(1), m1.group(2)), 'probe_members.txt')
row('placement predicates (ns=P headwords): all / written with ASCII only', '%s / %s' % (m2.group(1), m2.group(2)), 'probe_members.txt')
# --- the event cross
ev = js(A / 'events_live.json')
for g in sorted(ev['groups']):
    v = ev['groups'][g]
    row('event cross with the placement, %s: sentences read / arms / AGREE / DISAGREE / NOT_CHECKED' % g, '%d / %d / %d / %d / %d' % (v['sentences_read'], v['arms'], v['AGREE'], v['DISAGREE'], v['NOT_CHECKED']), 'events_live.json')
row('event cross DISAGREE arms in all (and how many of them were typed by the entry)', '%d (%d)' % (len(ev['disagree']), sum(1 for d in ev['disagree'] if d['typed_by_the_entry'])), 'events_live.json')
# --- W3-b1-5: the merged tree (W3-b1 + W5-a, base commit 2732274). Every number is read from a file; nothing is typed in.
IG = 'integration (W3-b1 + W5-a, base 2732274): '
ic = {}
for l in txt(A / 'integ_combination.txt').splitlines():
    if '=' in l and not l.startswith('only_w3b1_input='):
        kk, vv = l.split('=', 1); ic[kk] = vv
only_w3b1_inputs = [l.split('=', 1)[1] for l in txt(A / 'integ_combination.txt').splitlines() if l.startswith('only_w3b1_input=')]
row(IG + 'inputs / the merged entry with no placement equals the base commit byte for byte (rows)', '%s / %s' % (ic['inputs'], ic['now_none_equals_base']), 'integ_combination.txt')
row(IG + 'inputs the commit before W5-a read and the base commit abstains on (W5-a): all / read by the merged entry with the placement / with a second reason (the typed path ran)', '%s / %s / %s' % (ic['w5a_new_abstain'], ic['now_readable'], ic['now_second_reason']), 'integ_combination.txt')
row(IG + 'those inputs by the type of the first reason', ic['w5a_new_abstain_first_reason_types'], 'integ_combination.txt')
row(IG + 'inputs abstained on both before and after W5-a with a different output (reason changed by W5-a)', ic['w5a_reason_changed'], 'integ_combination.txt')
row(IG + 'read by the typed path (read with the placement, abstained with none): merged entry / W3-b1 tree alone', '%s / %s' % (ic['typed_read_now'], ic['typed_read_w3b1']), 'integ_combination.txt')
row(IG + 'of those: identical output in both / different output / only the merged entry / only the W3-b1 tree alone (W5-a stopped it)', '%s / %s / %s / %s' % (ic['both_identical'], ic['both_different'], ic['only_now'], ic['only_w3b1']), 'integ_combination.txt')
row(IG + 'inputs read by the W3-b1 tree alone and stopped by W5-a (listed in full)', '; '.join(only_w3b1_inputs) or 'none', 'integ_combination.txt')
ex_now = js(HERE / 'w3b1_expect_exceptions.json')['exceptions']; ex_r4 = js(A / 'r4_w3b1_expect_exceptions.json')['exceptions']
ks = collections.Counter()
for e in ex_now:
    for kk in sorted(set(re.findall(r'section 10A (K\d+)', e['why']))): ks[kk] += 1
row(IG + 'declared exceptions whose why names section 10A, by K (all declared)', ', '.join('section 10A %s %d' % kv for kv in sorted(ks.items())) + ' (of %d)' % len(ex_now), 'tests/reading_soundness/w3b1_expect_exceptions.json')
assert [e['id'] for e in ex_now] == [e['id'] for e in ex_r4]
nchg = sum(1 for x, y in zip(ex_r4, ex_now) if x != y)
row(IG + 'declared exceptions: unchanged / rewritten compared with round 4', '%d / %d' % (len(ex_now) - nchg, nchg), 'w3b1_expect_exceptions.json, r4_w3b1_expect_exceptions.json')
d4, d5 = jl(A / 'r4_entry_dev.jsonl'), jl(A / 'entry_dev.jsonl')
r9_w5a = sum(1 for x, y in zip(d4, d5) if x['source'] == 'ja_r9.jsonl' and x['out'].get('readable') and not y['out'].get('readable'))
row(IG + 'ja_r9 rows the commit before W5-a reads and the base commit abstains on', '%d' % r9_w5a, 'r4_entry_dev.jsonl, entry_dev.jsonl')
W5 = HERE.parent.parent / 'artifacts' / 'w5-a'
def jt(p): return {r['text']: r for r in jl(p)}
w5b, w5r3, w5n, w5l = jt(W5 / 'entry_before.jsonl'), jt(W5 / 'r3' / 'entry_after.jsonl'), jt(A / 'w5a_entry_none.jsonl'), jt(A / 'w5a_entry_live.jsonl')
assert list(w5b) == list(w5n) == list(w5l) == list(w5r3)
def cmp5(x, y):
    cn = collections.Counter(); rf = {}
    for t in x:
        a_, b_ = x[t], y[t]
        if a_['readable'] and not b_['readable']: cn['readable->false'] += 1; rf[t] = b_['abstain']['reasons'][0]
        elif a_['readable'] and b_['readable'] and a_['clauses'] != b_['clauses']: cn['changed'] += 1
        elif not a_['readable'] and b_['readable']: cn['false->readable'] += 1
        elif not a_['readable'] and not b_['readable'] and a_['abstain'] != b_['abstain']: cn['reason_changed'] += 1
    return cn, rf
cn_n, rf_n = cmp5(w5b, w5n); cn_l, rf_l = cmp5(w5b, w5l); cn_3, rf_3 = cmp5(w5b, w5r3)
row(IG + 'W5-a measurement inputs (%d): merged entry with no placement equals W5-a round 3 byte for byte' % len(w5b), 'yes' if (A / 'w5a_entry_none.jsonl').read_bytes() == (W5 / 'r3' / 'entry_after.jsonl').read_bytes() else 'NO', 'w5a_entry_none.jsonl, artifacts/w5-a/r3/entry_after.jsonl')
row(IG + 'W5-a measurement inputs, merged entry with the placement against W5-a entry_before: readable->false / false->readable / changed / reason_changed', '%d / %d / %d / %d' % tuple(cn_l[x] for x in ('readable->false', 'false->readable', 'changed', 'reason_changed')), 'w5a_entry_live.jsonl, artifacts/w5-a/entry_before.jsonl')
row(IG + 'W5-a measurement inputs, with no placement (same comparison): readable->false / false->readable / changed / reason_changed', '%d / %d / %d / %d' % tuple(cn_n[x] for x in ('readable->false', 'false->readable', 'changed', 'reason_changed')), 'w5a_entry_none.jsonl, artifacts/w5-a/entry_before.jsonl')
row(IG + 'W5-a measurement inputs: the readable->false set and its first reasons with the placement are the same as W5-a round 3', 'yes (%d inputs)' % len(rf_l) if rf_l == rf_3 and rf_n == rf_3 else 'NO', 'w5a_entry_live.jsonl, w5a_entry_none.jsonl, artifacts/w5-a/r3/entry_after.jsonl')
row(IG + 'E1 (events parity) lines', ', '.join(l.strip() for l in txt(A / 'e1.txt').splitlines() if l.strip()), 'e1.txt')
print('| item | value | source (artifacts/w3-b1/) |')
print('|---|---|---|')
print('\n'.join(rows))
