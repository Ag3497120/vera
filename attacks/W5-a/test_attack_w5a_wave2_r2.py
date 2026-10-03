"""Second, independently preregistered W5-a probes. See PRE_REGISTRATION_R2.md."""
from __future__ import annotations

import json
import re

from verantyx.semantic_read import read
from verantyx.llm_choice import ChoiceCandidate, ChoiceLedger, LLMChooser, ProviderReply


# Intentional cause/means, policy, and mechanism readings of によって, with no acting participant named.
JA_NON_AGENT_NIYOTTE = (
    '法律によって営業が制限された。', '制度によって支援が配分された。', '停電によって工場が止められた。',
    '規則によって入場が禁じられた。', '事故によって道路が閉鎖された。', '地震によって橋が壊された。',
    '台風によって屋根が飛ばされた。', '洪水によって家が流された。', '火災によって工場が破壊された。',
    '政策によって税率が変えられた。', '気温の上昇によって氷が溶かされた。', '薬によって痛みが抑えられた。',
)

# Explicit people/animals in the established passive-agent predicate class.
JA_CLEAR_PASSIVES = (
    '妹が母親に叱られた。', '子どもが教師に褒められた。', '鶏が狐に追いかけられた。',
    'ひよこが鶏に噛まれた。', '見習いが師匠に殴られた。', '旅人が山賊に追いかけられた。',
    '乗客が警察に叱られた。', '新人が上司から叱られた。', '小鹿が狼に追いかけられた。',
    '選手がコーチに褒められた。',
)

# Deliberately cover both the documented comparison exception and unsupported non-comparison alternatives.
K63_CASES = (
    'この建物は隣の建物より高い。', 'この道はあの道より短い。', '兄は弟より背が高い。',
    'この机はあの机より重い。', 'この川はあの川より長い。', 'この箱はその箱より小さい。',
    '彼女の鞄は私のより大きい。', '今年の売上は去年のより多い。', '兄は弟ほど早く走らない。',
    '猫は犬ほど大きくない。', 'その生徒は先生より詳しいとは限らない。', '彼の答えは私の答えくらい正確だ。',
)


def test_only_explicit_agent_by_phrases_can_license_passive_in_the_cause_means_probe():
    false_agents = []
    unsupported = []
    for text in JA_NON_AGENT_NIYOTTE:
        out = read(text, lang='ja')
        if not out['readable']:
            unsupported.append((text, out.get('abstain')))
        elif out['clauses'] and out['clauses'][0].get('voice') == 'passive' and 'agent' in out['clauses'][0]['roles']:
            false_agents.append((text, out))
    assert not false_agents, false_agents
    # Cases that are refused for a different unsupported predicate do not demonstrate this attack.
    assert len(unsupported) <= len(JA_NON_AGENT_NIYOTTE)


def test_positive_agent_evidence_on_known_predicates_does_not_over_abstain():
    failures = []
    for text in JA_CLEAR_PASSIVES:
        out = read(text, lang='ja')
        if not out['readable']:
            failures.append((text, 'over_abstention', out.get('abstain')))
        elif not out['clauses'] or out['clauses'][0].get('voice') != 'passive' or 'agent' not in out['clauses'][0]['roles']:
            failures.append((text, 'wrong_reading', out))
    assert not failures, failures


def test_k63_additional_comparison_and_noncomparison_inputs_hold_the_exception_boundary():
    violations = []
    for text in K63_CASES:
        out = read(text, lang='ja')
        if not out['readable'] or not out.get('unsupported'):
            continue
        allowed = (all(item.get('reasons') == ['copula value is a predicate phrase'] for item in out['unsupported'])
                   and any(c.get('comparison') for c in out.get('clauses', ())))
        if not allowed:
            violations.append((text, out))
    assert not violations, violations


class _PickNamedA:
    def __init__(self):
        self.calls = 0

    def ask(self, prompt):
        self.calls += 1
        for line in prompt.splitlines():
            match = re.match(r'^(\d+): (\{.*\})$', line)
            if match and json.loads(match.group(2)).get('term') == 'A':
                return ProviderReply.success(json.dumps({'choice': int(match.group(1))}))
        return ProviderReply.success('{"choice": null}')


def _chooser(path, provider):
    return LLMChooser(provider, ChoiceLedger(path), order_source=lambda n: list(range(n)), max_used_in=3)


def test_each_shown_context_fragment_changes_the_reuse_key(tmp_path):
    original_a = ('reason=clear', 'role=implement', 'kind=feature')
    original_b = ('reason=other', 'role=review', 'kind=bug')
    base = [ChoiceCandidate('A', original_a), ChoiceCandidate('B', original_b)]
    changed_contexts = []
    for candidate_i, rows in enumerate((original_a, original_b)):
        for row_i in range(3):
            replacement = rows[:row_i] + (rows[row_i] + '; changed',) + rows[row_i + 1:]
            changed_contexts.append((candidate_i, row_i, replacement))
    variants = []
    for candidate_i, _row_i, replacement in changed_contexts:
        changed = list(base)
        changed[candidate_i] = ChoiceCandidate(changed[candidate_i].term, replacement)
        variants.append(changed)
    variants += [
        [ChoiceCandidate('A', original_a + ('one new shown line',)), base[1]],
        [ChoiceCandidate('A', original_a[:-1]), base[1]],
        [ChoiceCandidate('A', tuple(reversed(original_a))), base[1]],
    ]
    failures = []
    for index, changed in enumerate(variants):
        provider = _PickNamedA()
        chooser = _chooser(tmp_path / ('partial-%02d.jsonl' % index), provider)
        first = chooser.choose('word', base)
        second = chooser.choose('word', changed)
        if first.status != 'ADOPTED' or second.status != 'ADOPTED' or second.cached or provider.calls != 4:
            failures.append((index, first.status, second.status, second.cached, provider.calls))
    assert not failures, failures


def test_an_unchanged_context_is_reused_when_only_candidate_order_changes(tmp_path):
    provider = _PickNamedA()
    chooser = _chooser(tmp_path / 'same.jsonl', provider)
    first = chooser.choose('word', [ChoiceCandidate('A', ('same',)), ChoiceCandidate('B', ('other',))])
    second = chooser.choose('word', [ChoiceCandidate('B', ('other',)), ChoiceCandidate('A', ('same',))])
    assert first.status == 'ADOPTED' and not first.cached
    assert second.status == 'ADOPTED' and second.cached and provider.calls == 2

