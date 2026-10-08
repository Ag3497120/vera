#!/usr/bin/env python3
"""W3-b5 round 2 (review.r1.md required fix 3): declare the frozen rows whose CORRECT ANSWER was written wrongly, and write the review of every `read` row of the group ni_goal.

The frozen data has rows whose `expect` says `goal` for a に phrase that the convention (docs/READING_CONVENTIONS.md section 2: goal = where a thing or a person is moved or set; place = where an
event or a state is) calls a place, or does not decide. Those rows were read through the row goal/に/PLACE and counted as `correct` (K207) although the answer in the data was wrong. The frozen
expectation is NOT rewritten: the row is declared in `expect_exceptions.json` with the kind `frozen_expectation_is_a_wrong_answer` or `goal_or_place_not_decided`, with what was observed with the table as registered (data_check_before_narrowing.json), before round 2 (data_check_before_round2.json) and now.
Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b5/tools/mk_round2_declarations.py --before-round2 J --registered J --exceptions-in F --narrowed F --out-exceptions F --out-review TSV
(reads the entry with the fake placement of the row through the test file's `query_of`: the same code as the tests)."""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[3]

# my judgment of each row (by the convention), written by hand after reading the sentence; every other `read` row of ni_goal is `kept`.
DECLARE = {
    'W3B5-NIGOAL-R-011': ('frozen_expectation_is_a_wrong_answer', 'place', '停泊する の に は船がとまっている場所（存在の場所）。到達点を言う動詞でない。規約 §2: place'),
    'W3B5-NIGOAL-R-031': ('frozen_expectation_is_a_wrong_answer', 'place', '停泊する の に は船がとまっている場所（存在の場所）。規約 §2: place'),
    'W3B5-NIGOAL-R-010': ('goal_or_place_not_decided', None, '停車する の に は止まる地点（到達点とも停車している場所とも決まらない）。同じ型（とまる・滞在）。正解は 1 つの読みに決まらない'),
    'W3B5-NIGOAL-R-036': ('goal_or_place_not_decided', None, '参列する に 場所 は 行き先（参列に行く）とも場所とも決まらない（行事には で を取る方が自然）。正解は 1 つの読みに決まらない'),
}
NOTES = {'W3B5-NIGOAL-R-007': 'kept: 入院する の に は入る先（病院）= goal', 'W3B5-NIGOAL-R-030': 'kept: goal（日本語として不自然な文。判定には影響しない。町に入院した）',
         'W3B5-NIGOAL-R-020': 'kept: 合流する の に は集まる先 = goal', 'W3B5-NIGOAL-R-034': 'kept: 参拝する の に は行く先（神社）= goal',
         'W3B5-NIGOAL-R-035': 'kept: 係留する は物を港に置く（設置の到達点）= goal', 'W3B5-NIGOAL-R-039': 'kept: 配備する は物を港に置く（設置の到達点）= goal',
         'W3B5-NIGOAL-R-040': 'kept: 保存する は物を倉庫に置く（設置の到達点）= goal', 'W3B5-NIGOAL-R-038': 'kept: 格納する は物を倉庫に置く（設置の到達点）= goal'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--before-round2', required=True); ap.add_argument('--registered', required=True); ap.add_argument('--exceptions-in', required=True); ap.add_argument('--narrowed', required=True)
    ap.add_argument('--out-exceptions', required=True); ap.add_argument('--out-review', required=True)
    a = ap.parse_args()
    sys.path.insert(0, str(TREE / 'tests'))
    spec = importlib.util.spec_from_file_location('tw5_decl', TREE / 'tests' / 'test_semantic_read_w3b5.py')
    tw = importlib.util.module_from_spec(spec); sys.modules['tw5_decl'] = tw; spec.loader.exec_module(tw)
    before = {x['id']: x for x in json.loads(Path(a.before_round2).read_text(encoding='utf-8'))}
    registered = {x['id']: x for x in json.loads(Path(a.registered).read_text(encoding='utf-8'))}
    narrowed = json.loads(Path(a.narrowed).read_text(encoding='utf-8'))['rows']
    exc = json.loads(Path(a.exceptions_in).read_text(encoding='utf-8'))
    exc['exceptions'] = [e for e in exc['exceptions'] if e['kind'] not in ('frozen_expectation_is_a_wrong_answer', 'goal_or_place_not_decided')]
    data = {r['id']: r for r in tw.DATA}
    tsv = ['id\tpred_type\tinput\tfrozen_roles\tdecision\treason']
    for rid, r in data.items():
        if r['role_group'] != 'ni_goal' or r['behavior'] != 'read': continue
        roles = json.dumps(r['expect']['clauses'][0]['roles'], ensure_ascii=False)
        if rid in DECLARE:
            kind, correct, why = DECLARE[rid]
            assert rid in narrowed and narrowed[rid]['observed_entry'] == 'abstain', rid
            b = before[rid]; g = registered[rid]
            assert g['entry'] == 'read' and g['verdict'] == 'correct', (rid, g['entry'], g['verdict'])          # with the table as registered: read and counted correct
            ex = tw.SR.typed_explain_ja(r['input'], tw.query_of(r))
            exc['exceptions'].append({'id': rid, 'input': r['input'], 'kind': kind, 'frozen_entry_expect': r['entry_expect'], 'frozen_w3b5_expect': r['w3b5_expect'],
                                      'frozen_roles': r['expect']['clauses'][0]['roles'], 'correct_by_convention': correct if correct else 'not one reading (readable false)', 'reason': why,
                                      'observed_with_the_table_as_registered': {'entry': g['entry'], 'verdict': g['verdict'], 'w3b2': g['w3b2'], 'role_license': g['role_license']},
                                      'observed_before_round2': {'entry': b['entry'], 'verdict': b['verdict'], 'w3b2': b['w3b2'], 'role_license': b['role_license']},
                                      'observed_entry': 'abstain', 'observed_explain': ex,
                                      'observed_verdict': tw.b1.judge(r['expect'], 'ja', tw.SR.read(r['input'], placement=tw.query_of(r)))['verdict']})
            tsv.append('\t'.join([rid, r['pred_type'], r['input'], roles, 'DECLARED:' + kind, why]))
        else:
            tsv.append('\t'.join([rid, r['pred_type'], r['input'], roles, 'kept', NOTES.get(rid, 'kept: goal（移動・設置の到達点）')]))
    exc['kinds'] = sorted({e['kind'] for e in exc['exceptions']})
    exc['note'] = ('frozen expectations that do not match what the entry does for a reason that is not a misread: a fact of the reader that the design had not seen, observation pinned; and (round 2, '
                   'review.r1.md required fix 3) frozen answers written wrongly (kind frozen_expectation_is_a_wrong_answer / goal_or_place_not_decided: the expectation is not rewritten)')
    Path(a.out_exceptions).write_text(json.dumps(exc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    Path(a.out_review).write_text('\n'.join(tsv) + '\n', encoding='utf-8')
    print('exceptions=%d kinds=%s review_rows=%d declared=%d' % (len(exc['exceptions']), exc['kinds'], len(tsv) - 1, sum(1 for l in tsv if 'DECLARED' in l)))


if __name__ == '__main__':
    main()
