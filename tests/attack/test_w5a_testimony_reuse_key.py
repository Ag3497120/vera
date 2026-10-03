"""W5-a (A-01): a recorded LLM testimony is reused only when the word, the candidates AND what was shown about each candidate
(the `used_in` lines: rule reasons, roles, kinds, lineage, model) are the same. The counts of asks are the evidence (a fake provider
counts every ask it receives)."""
import json
import re

from verantyx.agent_routing import RoutingRequest, route, table_from_dicts
from verantyx.llm_choice import (ChoiceCandidate, ChoiceLedger, LLMChooser, ProviderReply, choice_key, reuse_key, reuse_key_parts)

_LINE = re.compile(r'^(\d+): (\{.*\})$')


class ByContext:
    """Answers the number of the candidate whose shown context contains `marker`; counts every ask."""

    def __init__(self, marker='clear best fit'):
        self.marker = marker
        self.calls = 0

    def ask(self, prompt):
        self.calls += 1
        for line in prompt.splitlines():
            m = _LINE.match(line)
            if m and self.marker in m.group(2):
                return ProviderReply.success(json.dumps({'choice': int(m.group(1))}))
        return ProviderReply.success('{"choice": null}')


def _table(reason_a, reason_b, model_a=None):
    agent_a = {'id': 'A', 'adapter': 'codex', 'roles': ['implement'], 'kinds': ['feature'], 'lineage': 'one',
               'witness': 'A is an implementation agent.'}
    if model_a is not None: agent_a['model'] = model_a
    agents = [agent_a, {'id': 'B', 'adapter': 'claude', 'roles': ['implement'], 'kinds': ['feature'], 'lineage': 'two',
                        'witness': 'B is an implementation agent.'}]
    rules = [
        {'id': 'PICK_A', 'when': {'role': 'implement', 'kind': 'feature'}, 'prefer': ['A'], 'reason': reason_a, 'witness': 'The human\'s routing rule for A.'},
        {'id': 'PICK_B', 'when': {'role': 'implement', 'kind': 'feature'}, 'prefer': ['B'], 'reason': reason_b, 'witness': 'The human\'s routing rule for B.'},
        {'id': 'DEFAULT', 'when': {'role': 'implement'}, 'prefer': ['A'], 'fallback': True, 'reason': 'Use A otherwise.',
         'witness': 'The human\'s fallback rule.'},
    ]
    return table_from_dicts(agents, rules)


REQUEST = RoutingRequest('job', 'implement', 'feature', 'small')


def _chooser(provider, tmp_path):
    return LLMChooser(provider, ChoiceLedger(tmp_path / 'choice.jsonl'))


def test_the_same_table_twice_asks_twice_then_reuses(tmp_path):
    provider = ByContext()
    chooser = _chooser(provider, tmp_path)
    t = _table('A is the clear best fit.', 'B is less suitable.')
    first = route(t, REQUEST, chooser_factory=lambda: chooser)
    second = route(t, REQUEST, chooser_factory=lambda: chooser)
    assert (first.agent_id, first.testimony['cached']) == ('A', False)
    assert (second.agent_id, second.testimony['cached']) == ('A', True)
    assert provider.calls == 2            # one decision = two asks; the second route asked nothing


def test_changed_rule_reasons_ask_again_and_follow_the_new_context(tmp_path):
    provider = ByContext()
    chooser = _chooser(provider, tmp_path)
    first = route(_table('A is the clear best fit.', 'B is less suitable.'), REQUEST, chooser_factory=lambda: chooser)
    assert provider.calls == 2
    second = route(_table('A is less suitable.', 'B is the clear best fit.'), REQUEST, chooser_factory=lambda: chooser)
    assert provider.calls == 4            # asked again: the context changed
    assert (first.agent_id, second.agent_id) == ('A', 'B')
    assert second.testimony['cached'] is False


def test_a_changed_agent_model_alone_asks_again(tmp_path):
    provider = ByContext()
    chooser = _chooser(provider, tmp_path)
    route(_table('A is the clear best fit.', 'B is less suitable.', 'model-one'), REQUEST, chooser_factory=lambda: chooser)
    assert provider.calls == 2
    again = route(_table('A is the clear best fit.', 'B is less suitable.', 'model-two'), REQUEST, chooser_factory=lambda: chooser)
    assert provider.calls == 4 and again.testimony['cached'] is False
    same = route(_table('A is the clear best fit.', 'B is less suitable.', 'model-two'), REQUEST, chooser_factory=lambda: chooser)
    assert provider.calls == 4 and same.testimony['cached'] is True


def test_the_chooser_reuses_only_for_the_same_context_whatever_the_candidate_order(tmp_path):
    provider = ByContext(marker='MARK')
    chooser = _chooser(provider, tmp_path)
    a1, b1 = ChoiceCandidate('A', ('A is the one MARK',)), ChoiceCandidate('B', ('B is other',))
    first = chooser.choose('w', [a1, b1])
    assert first.status == 'ADOPTED' and first.choice == 'A' and first.cached is False and provider.calls == 2
    # the same word and candidates, the order of the candidates reversed, the same context: reused
    reordered = chooser.choose('w', [b1, a1])
    assert reordered.cached is True and reordered.choice == 'A' and provider.calls == 2
    # the same word and the same terms, one candidate's context differs: asked again
    changed = chooser.choose('w', [ChoiceCandidate('A', ('A is something else',)), ChoiceCandidate('B', ('B is other MARK',))])
    assert changed.cached is False and provider.calls == 4 and changed.choice == 'B'
    # a context line that is only added also changes the key
    added = chooser.choose('w', [a1, ChoiceCandidate('B', ('B is other', 'B has one more line'))])
    assert added.cached is False and provider.calls == 6
    # the question is not part of the key (the existing promise): the same word, candidates and contexts are reused
    asked_differently = chooser.choose('w', [a1, b1], 'a different question')
    assert asked_differently.cached is True and provider.calls == 6


def test_the_order_of_the_context_lines_of_one_candidate_is_part_of_the_key(tmp_path):
    provider = ByContext(marker='MARK')
    chooser = _chooser(provider, tmp_path)
    chooser.choose('w', [ChoiceCandidate('A', ('x MARK', 'y')), ChoiceCandidate('B', ('z',))])
    assert provider.calls == 2
    chooser.choose('w', [ChoiceCandidate('A', ('y', 'x MARK')), ChoiceCandidate('B', ('z',))])
    assert provider.calls == 4


def test_the_decision_line_keeps_the_parts_of_its_reuse_key_and_the_old_key_is_unchanged(tmp_path):
    provider = ByContext(marker='MARK')
    chooser = _chooser(provider, tmp_path)
    cands = [ChoiceCandidate('A', ('a MARK',)), ChoiceCandidate('B', ('b',))]
    chooser.choose('word', cands)
    decision = next(e for e in chooser.ledger.entries() if e['type'] == 'decision')
    assert decision['key'] == choice_key('word', ['A', 'B'])                 # the key that verify_adoption checks is not changed
    assert decision['reuse_key'] == reuse_key('word', cands)
    parts = decision['reuse_key_parts']
    assert parts == reuse_key_parts('word', cands)
    assert parts['word'] == 'word' and [p[0] for p in parts['candidates']] == ['A', 'B']
    assert all(re.fullmatch(r'[0-9a-f]{64}', p[1]) for p in parts['candidates'])
    assert parts['candidates'][0][1] != parts['candidates'][1][1]
    assert chooser.ledger.summary()['decisions_without_reuse_key'] == 0


def test_a_decision_without_a_reuse_key_is_not_reused_and_is_counted(tmp_path):
    ledger = ChoiceLedger(tmp_path / 'choice.jsonl')
    provider = ByContext(marker='MARK')
    chooser = LLMChooser(provider, ledger)
    # an old ledger line: it has the old key (word + terms) and no context
    ledger.append({'type': 'decision', 'decision_id': 'old1', 'key': choice_key('w', ['A', 'B']), 'word': 'w', 'candidates': ['A', 'B'],
                   'merged_duplicates': [], 'status': 'ADOPTED', 'reason': 'ADOPTED', 'choice': 'B', 'ask_ids': [], 'failure': None,
                   'detail': '', 'mapping_type': 'x', 'counts_as_evidence': False, 'ts': 't'})
    assert ledger.summary()['decisions_without_reuse_key'] == 1
    got = chooser.choose('w', [ChoiceCandidate('A', ('a MARK',)), ChoiceCandidate('B', ('b',))])
    assert got.cached is False and got.choice == 'A' and provider.calls == 2      # asked, not the old 'B'
    assert ledger.summary()['decisions_without_reuse_key'] == 1                    # the old line is still counted, never rewritten
