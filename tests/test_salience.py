"""W3-c: the salience field (verantyx/salience.py): ledger contract, stage values, ties, permutation, trace."""
from __future__ import annotations

import itertools
import json

import pytest

from verantyx import salience as S
from verantyx.salience import FLAT, Candidate, Ledger, MemoryLedger


def fixed_clock():
    return '2000-01-01T00:00:00+00:00'


def ledger(*events):
    led = MemoryLedger(clock=fixed_clock)
    for kind, payload in events:
        led.append({'kind': kind, 'payload': payload})
    return led


def cands(*specs):
    return [Candidate(k, d, tuple(ch)) for k, d, ch in specs]


# ------------------------------------------------------------------ the ledger contract
def test_protocol_conformance():
    assert isinstance(MemoryLedger(), Ledger)


def test_seq_id_since_count_last_seq():
    led = MemoryLedger(clock=fixed_clock)
    i1 = led.append({'kind': 'utterance', 'payload': {'text': 'a'}})
    i2 = led.append({'kind': 'observation', 'payload': {'observed_cell': 'X'}})
    i3 = led.append({'kind': 'observation', 'payload': {'observed_cell': 'X'}})
    i4 = led.append({'kind': 'decision', 'payload': {'decided_cell': 'Y'}})
    assert (i1, i2, i3, i4) == ('ev:1', 'ev:2', 'ev:3', 'ev:4')
    evs = list(led.events())
    assert [e['seq'] for e in evs] == [1, 2, 3, 4] and evs[0]['ts'] == fixed_clock()
    assert [e['seq'] for e in led.events(since='ev:2')] == [3, 4]
    assert list(led.events(since='ev:4')) == []
    assert led.count('observed_cell', 'X') == 2 and led.count('observed_cell', 'Z') == 0
    assert led.last_seq('observed_cell', 'X') == 3 and led.last_seq('observed_cell', 'Z') is None
    assert led.last_seq('decided_cell', 'Y') == 4
    with pytest.raises(ValueError, match='LEDGER_INVALID'):
        list(led.events(since='ev:99'))


def test_events_returned_are_copies():
    led = ledger(('utterance', {'text': 'a'}))
    list(led.events())[0]['payload']['text'] = 'changed'
    assert list(led.events())[0]['payload']['text'] == 'a'


@pytest.mark.parametrize('event', [
    {'kind': 'other', 'payload': {}},
    {'kind': 'utterance', 'payload': 'text'},
    {'kind': 'utterance'},
    {'payload': {}},
    {'kind': 'utterance', 'payload': {}, 'seq': 5},
    'utterance',
])
def test_broken_events_are_refused_and_nothing_is_appended(event):
    led = MemoryLedger(clock=fixed_clock)
    with pytest.raises(ValueError, match='LEDGER_INVALID'):
        led.append(event)
    assert len(led) == 0


def test_constructor_rejects_gaps_and_bad_kinds():
    ok = {'seq': 1, 'ts': 't', 'kind': 'utterance', 'payload': {}}
    MemoryLedger([ok])
    for bad in ({**ok, 'seq': 2}, {**ok, 'kind': 'x'}, {**ok, 'payload': []}, {**ok, 'id': 'ev:9'}, {k: v for k, v in ok.items() if k != 'ts'}):
        with pytest.raises(ValueError, match='LEDGER_INVALID'):
            MemoryLedger([bad])


# ------------------------------------------------------------------ the stages
def test_each_stage_value():
    led = ledger(
        ('utterance', {'text': 'お母さんが先生と話した'}),
        ('observation', {'observed_cell': 'B'}),
        ('decision', {'decided_cell': 'C'}),
        ('decision', {'decided_cell': 'C'}),
    )
    ctx = S.build_context(led, lambda w: ('先生',) if w == '校長' else ())
    a = Candidate('A', 1, ('お母さん',))
    b = Candidate('B', 2, ('校長',))
    c = Candidate('C', 1, ('犬',))
    assert S.stage_distance(a, led, ctx) == (1, ())
    assert S.stage_utter_verbatim(a, led, ctx) == (1, (1,))        # the utterance is seq 1
    assert S.stage_utter_verbatim(c, led, ctx) == (0, ())
    assert S.stage_utter_neighbor(b, led, ctx) == (1, (1,))        # 校長's neighbour 先生 occurs
    assert S.stage_utter_neighbor(a, led, ctx) == (0, ())
    assert S.stage_recency(a, led, ctx) == (None, ())
    assert S.stage_recency(b, led, ctx) == (2, (2,))
    assert S.stage_decided(c, led, ctx) == (2, (3, 4))
    assert S.stage_decided(a, led, ctx) == (0, ())


def test_flat_field_stage_values():
    ctx = S.build_context(FLAT)
    c = Candidate('A', 1, ('x',))
    assert S.stage_utter_verbatim(c, FLAT, ctx) == (0, ())
    assert S.stage_utter_neighbor(c, FLAT, ctx) == (0, ())
    assert S.stage_recency(c, FLAT, ctx) == (None, ())
    assert S.stage_decided(c, FLAT, ctx) == (0, ())


def test_flat_field_is_a_tie():
    r = S.rank(cands(('A', 1, ('x',)), ('B', 1, ('y',))), FLAT)
    assert r.ranks == (('A', 'B'),) and r.trace['rank1'] == {'kind': 'TIE', 'size': 2}


def test_distance_orders_before_everything():
    led = ledger(('decision', {'decided_cell': 'Far'}), ('decision', {'decided_cell': 'Far'}))
    r = S.rank(cands(('Near', 1, ()), ('Far', 2, ())), led)
    assert r.ranks == (('Near',), ('Far',)) and r.trace['boundaries'] == [{'between': [1, 2], 'decided_by': 'distance'}]


def test_recency_none_is_top_then_older_first():
    led = ledger(('observation', {'observed_cell': 'Old'}), ('observation', {'observed_cell': 'New'}))
    r = S.rank(cands(('New', 1, ()), ('Old', 1, ()), ('Never', 1, ())), led)
    assert r.ranks == (('Never',), ('Old',), ('New',))
    assert [b['decided_by'] for b in r.trace['boundaries']] == ['recency', 'recency']


def test_recency_beats_decided_and_the_trace_names_the_stage():
    led = ledger(('decision', {'decided_cell': 'X'}), ('observation', {'observed_cell': 'X'}))
    r = S.rank(cands(('X', 1, ()), ('Y', 1, ())), led)
    assert r.ranks == (('Y',), ('X',))
    assert r.trace['boundaries'] == [{'between': [1, 2], 'decided_by': 'recency'}]


def test_decided_decides_when_the_earlier_stages_tie():
    led = ledger(('decision', {'decided_cell': 'X'}))
    r = S.rank(cands(('X', 1, ()), ('Y', 1, ())), led)
    assert r.ranks == (('X',), ('Y',)) and r.trace['rank1']['kind'] == 'SINGLE'
    by_cell = {c['cell_key']: c for c in r.trace['cells']}
    assert by_cell['X']['ledger_seqs']['decided'] == [1] and by_cell['Y']['ledger_seqs']['decided'] == []


def test_utterance_stages_come_before_recency():
    led = ledger(('utterance', {'text': 'Yを見た'}), ('observation', {'observed_cell': 'Y'}))
    r = S.rank(cands(('X', 1, ('Xw',)), ('Y', 1, ('Y',))), led)
    assert r.ranks == (('Y',), ('X',))
    assert r.trace['boundaries'] == [{'between': [1, 2], 'decided_by': 'utter_verbatim'}]


def test_verbatim_and_neighbor_are_separate_stages_not_one_vote():
    led = ledger(('utterance', {'text': '近い語と別の語'}))
    ctx = S.build_context(led, lambda w: ('別の語',) if w == 'N' else ())
    r = S.rank(cands(('V', 1, ('近い語',)), ('N', 1, ('N',))), led, ctx)
    # V has s2=1, N has s2=0 and s3=1: the verbatim stage is compared first; the two signals are never added
    assert r.ranks == (('V',), ('N',))
    assert r.trace['boundaries'] == [{'between': [1, 2], 'decided_by': 'utter_verbatim'}]
    by_cell = {c['cell_key']: c for c in r.trace['cells']}
    assert by_cell['N']['values']['utter_verbatim'] == 0 and by_cell['N']['values']['utter_neighbor'] == 1


def test_an_utterance_equal_to_the_anchor_sentence_does_not_act_on_stage_ii_and_the_one_before_it_does():
    # D17 (docs change record 3): U = the latest utterance whose text is NOT the anchor sentence of this turn
    led = ledger(('utterance', {'text': 'Yを見た'}), ('utterance', {'text': '問いの文'}))
    cs = cands(('X', 1, ('Xw',)), ('Y', 1, ('Y',)))
    # without the anchor sentence the latest utterance (seq 2) is U and says nothing about Y: the two are tied
    assert S.rank(cs, led).ranks == (('X', 'Y'),)
    # with it, seq 2 is skipped (and counted), U is seq 1, and the trace points to seq 1, not seq 2
    ctx = S.build_context(led, anchor_text='問いの文')
    assert (ctx.utterance_seq, ctx.utterance_text, ctx.skipped_as_anchor) == (1, 'Yを見た', (2,))
    r = S.rank(cs, led, ctx)
    assert r.ranks == (('Y',), ('X',))
    by_cell = {c['cell_key']: c for c in r.trace['cells']}
    assert by_cell['Y']['ledger_seqs']['utter_verbatim'] == [1] and by_cell['X']['ledger_seqs']['utter_verbatim'] == []
    assert r.trace['utterance'] == {'used_seq': 1, 'skipped_same_as_anchor': [2]}


def test_when_every_utterance_is_the_anchor_sentence_stage_ii_has_no_utterance():
    led = ledger(('utterance', {'text': '問いの文'}), ('utterance', {'text': '問いの文'}))
    ctx = S.build_context(led, anchor_text='問いの文')
    assert (ctx.utterance_seq, ctx.utterance_text, ctx.skipped_as_anchor) == (None, '', (1, 2))
    r = S.rank(cands(('X', 1, ('問い',)), ('Y', 1, ('Y',))), led, ctx)
    assert r.ranks == (('X', 'Y'),) and r.trace['utterance'] == {'used_seq': None, 'skipped_same_as_anchor': [1, 2]}


def test_only_an_exactly_equal_text_is_skipped_and_the_default_skips_nothing():
    led = ledger(('utterance', {'text': '問いの文。'}))
    assert S.build_context(led, anchor_text='問いの文').utterance_seq == 1          # not equal as a string: it counts
    assert S.build_context(led).utterance_seq == 1 and S.build_context(led).skipped_as_anchor == ()


# ------------------------------------------------------------------ permutation: O3
def test_permutation_of_equal_candidates_keeps_the_tie():
    specs = [('A', 1, ('a',)), ('B', 1, ('b',)), ('C', 1, ('c',))]
    led = ledger(('utterance', {'text': 'zzz'}))
    results = set()
    for perm in itertools.permutations(specs):
        r = S.rank(cands(*perm), led)
        assert len(r.ranks) == 1 and r.trace['rank1'] == {'kind': 'TIE', 'size': 3}
        results.add(json.dumps([list(g) for g in r.ranks]))
    assert len(results) == 1


def test_permutation_of_a_mixed_set_gives_the_same_ranks_and_trace():
    led = ledger(('decision', {'decided_cell': 'B'}), ('observation', {'observed_cell': 'C'}))
    specs = [('A', 1, ()), ('B', 1, ()), ('C', 1, ()), ('D', 2, ())]
    outs = set()
    for perm in itertools.permutations(specs):
        r = S.rank(cands(*perm), led)
        outs.add(json.dumps([[list(g) for g in r.ranks], r.trace], sort_keys=True))
    assert len(outs) == 1


def test_one_line_of_the_ledger_changes_the_rank_and_the_trace_points_to_its_seq():
    base = [('utterance', {'text': 'q'}), ('observation', {'observed_cell': 'P'})]
    r1 = S.rank(cands(('P', 1, ()), ('Q', 1, ())), ledger(*base))
    r2 = S.rank(cands(('P', 1, ()), ('Q', 1, ())), ledger(*base, ('observation', {'observed_cell': 'Q'})))
    assert r1.ranks == (('Q',), ('P',)) and r2.ranks == (('P',), ('Q',))
    cells2 = {c['cell_key']: c for c in r2.trace['cells']}
    assert cells2['Q']['ledger_seqs']['recency'] == [3] and cells2['P']['ledger_seqs']['recency'] == [2]


def test_duplicate_cell_keys_are_refused():
    with pytest.raises(ValueError):
        S.rank(cands(('A', 1, ()), ('A', 1, ())), FLAT)


def test_empty_candidate_list_has_no_rank():
    r = S.rank([], FLAT)
    assert r.ranks == () and r.trace['rank1']['kind'] == 'EMPTY'


# ------------------------------------------------------------------ a tie event never writes observed_cell (shape contract of D9)
def test_a_tie_event_carries_candidates_and_no_observed_cell():
    led = MemoryLedger(clock=fixed_clock)
    led.append({'kind': 'observation', 'payload': {'outcome': 'TIE', 'tie_cells': ['A', 'B']}})
    assert led.last_seq('observed_cell', 'A') is None and led.last_seq('observed_cell', 'B') is None
    r = S.rank(cands(('A', 1, ()), ('B', 1, ())), led)
    assert r.trace['rank1']['kind'] == 'TIE'


# ------------------------------------------------------------------ files
def test_load_and_append_roundtrip(tmp_path):
    p = tmp_path / 'l.jsonl'
    led = ledger(('utterance', {'text': 'こんにちは'}), ('observation', {'observed_cell': 'X'}))
    assert S.append_jsonl(p, led.events()) == 2
    loaded = S.load_jsonl(p)
    assert list(loaded.events()) == list(led.events())
    loaded.append({'kind': 'decision', 'payload': {'decided_cell': 'X'}})
    assert S.append_jsonl(p, loaded.events(since='ev:2')) == 1
    assert [e['seq'] for e in S.load_jsonl(p).events()] == [1, 2, 3]
    assert S.append_jsonl(p, []) == 0


def test_load_empty_file_is_an_empty_ledger(tmp_path):
    p = tmp_path / 'e.jsonl'
    p.write_bytes(b'')
    assert len(S.load_jsonl(p)) == 0


@pytest.mark.parametrize('content', [
    b'{broken\n',
    b'{"seq":2,"ts":"t","kind":"utterance","payload":{}}\n',
    b'{"seq":1,"ts":"t","kind":"nope","payload":{}}\n',
    b'{"seq":1,"ts":"t","kind":"utterance","payload":{}}',
    b'{"seq":1,"ts":"t","kind":"utterance","payload":{}}\n\n',
    b'\xff\xfe\n',
])
def test_broken_files_are_ledger_invalid(tmp_path, content):
    p = tmp_path / 'b.jsonl'
    p.write_bytes(content)
    with pytest.raises(ValueError, match='LEDGER_INVALID'):
        S.load_jsonl(p)


def test_missing_file_is_ledger_invalid(tmp_path):
    with pytest.raises(ValueError, match='LEDGER_INVALID:FILE_NOT_FOUND'):
        S.load_jsonl(tmp_path / 'nope.jsonl')
