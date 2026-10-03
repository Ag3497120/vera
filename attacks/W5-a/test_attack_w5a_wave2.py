"""Adversarial probes for the integrated W5-a fixes; all sentences here were written for this wave."""
from __future__ import annotations

import copy
import itertools
import json

from verantyx.semantic_read import read
from verantyx.event_cross import build_crosses
from verantyx.llm_choice import ChoiceCandidate, ChoiceLedger, LLMChooser, ProviderReply


# K62: passive morphology without an agent phrase must not be asserted as passive.
JA_PASSIVE_NO_AGENT = (
    '議事録が読まれた。', '窓が開けられた。', '作品が褒められた。', '犬が追いかけられた。', '食事が運ばれた。',
    '箱が運ばれた。', '机が動かされた。', '駅が作られた。', '資料が提出された。', '橋が壊された。',
    '道路が整備された。', '記事が発表された。', '名前が呼ばれた。', '手紙が送られた。', '計画が決められた。',
    '扉が閉じられた。', '客が案内された。', '馬が運ばれた。', '病院が建てられた。', '会議が延期された。',
)

# K62: explicit agent evidence. The first half uses によって; the second uses the closed に/から predicate class.
JA_PASSIVE_WITH_AGENT = (
    '橋が作業員によって修理された。', '計画が政府によって承認された。', '候補者が政党によって指名された。',
    '小説が出版社によって採用された。', '地図が調査隊によって作成された。', '会場が実行委員会によって準備された。',
    '原稿が編集者によって訂正された。', '料理が料理人によって用意された。', '道路が市役所によって整備された。',
    '荷物が運送会社によって配達された。', '妹が母親に叱られた。', '生徒が教師に褒められた。',
    '子犬が熊に追いかけられた。', '弟が友人から殴られた。', '魚が猫に噛まれた。',
    '選手が監督に叱られた。', '子どもが祖父に褒められた。', '鼠が蛇に追いかけられた。',
    '新人が上司から叱られた。', '鶏が狐に噛まれた。',
)

# K62: active clauses must not acquire passive voice in the absence of passive morphology.
JA_ACTIVE = (
    '兄が本を読んだ。', '職人が棚を修理した。', '先生が地図を配った。', '母がパンを焼いた。', '店長が商品を並べた。',
    '生徒が答案を提出した。', '犬が骨を食べた。', '猫が魚を取った。', '猿が果物を運んだ。', '鷲が獲物を捕らえた。',
    '政府が資料を提出した。', '警察が容疑者を追いかけた。', '国会が法案を決めた。', '企業が新製品を発表した。',
    '電車が乗客を運んだ。', '船が食料を届けた。', '台風が屋根を壊した。', '地震が道路を損傷した。',
    '洪水が橋を流した。', '火山が灰を噴き出した。',
)

# K64: positive agent evidence and clear path/object contrasts. For readable gold cases only agent/patient are checked;
# all path and unlicensed natural-force cases must remain unread rather than assigning a false agent/patient.
JA_ROLE_CASES = (
    ('先生が生徒に資料を渡した。', 'read', '先生', '資料'),
    ('職員が住民に案内を送った。', 'read', '職員', '案内'),
    ('姉が弟に荷物を届けた。', 'read', '姉', '荷物'),
    ('医師が患者に薬を渡した。', 'read', '医師', '薬'),
    ('猫が魚を食べた。', 'read', '猫', '魚'),
    ('犬が骨をかじった。', 'read', '犬', '骨'),
    ('猿が果物を取った。', 'read', '猿', '果物'),
    ('鷲が魚を捕らえた。', 'read', '鷲', '魚'),
    ('政府が資料を提出した。', 'read', '政府', '資料'),
    ('警察が容疑者を追いかけた。', 'read', '警察', '容疑者'),
    ('国会が法案を決めた。', 'read', '国会', '法案'),
    ('企業が新製品を発表した。', 'read', '企業', '新製品'),
    ('トラックが荷物を運んだ。', 'read', 'トラック', '荷物'),
    ('船が食料を届けた。', 'read', '船', '食料'),
    ('列車が乗客を運んだ。', 'read', '列車', '乗客'),
    ('配送車が箱を届けた。', 'read', '配送車', '箱'),
    ('台風が屋根を壊した。', 'abstain', None, None),
    ('地震が道路を損傷した。', 'abstain', None, None),
    ('洪水が橋を流した。', 'abstain', None, None),
    ('火山が灰を噴き出した。', 'abstain', None, None),
    ('太郎が公園を走った。', 'abstain', None, None),
    ('先生が橋を渡った。', 'abstain', None, None),
    ('旅人が山を越えた。', 'abstain', None, None),
    ('兵士が広場を横切った。', 'abstain', None, None),
    ('犬が庭を走った。', 'abstain', None, None),
    ('馬が川を渡った。', 'abstain', None, None),
    ('鳥が空を飛んだ。', 'abstain', None, None),
    ('魚が川を泳いだ。', 'abstain', None, None),
    ('部隊が谷を進んだ。', 'abstain', None, None),
    ('探検隊が森を歩いた。', 'abstain', None, None),
    ('劇団が町を巡った。', 'abstain', None, None),
    ('軍隊が国境を越えた。', 'abstain', None, None),
    ('車がトンネルを通った。', 'abstain', None, None),
    ('列車が橋を渡った。', 'abstain', None, None),
    ('船が運河を進んだ。', 'abstain', None, None),
    ('飛行機が山脈を越えた。', 'abstain', None, None),
    ('洪水が町を流れた。', 'abstain', None, None),
    ('雪崩が谷を下った。', 'abstain', None, None),
    ('霧が湖面を這った。', 'abstain', None, None),
    ('溶岩が斜面を流れた。', 'abstain', None, None),
)

# English controls: 40 active clauses and 40 passives (20 with and 20 without an explicit by-phrase).
EN_ACTIVE = (
    'They reviewed the report.', 'They painted the fence.', 'They repaired the bridge.', 'They inspected the engine.',
    'They cleaned the kitchen.', 'They carried the boxes.', 'They checked the schedule.', 'They tested the device.',
    'They updated the manual.', 'They removed the label.', 'They replaced the battery.', 'They announced the result.',
    'They prepared the room.', 'They cancelled the meeting.', 'They confirmed the booking.', 'They notified the staff.',
    'They warned the driver.', 'They protected the village.', 'They rescued the child.', 'They discussed the proposal.',
    'They examined the sample.', 'They completed the form.', 'They submitted the application.', 'They published the article.',
    'They collected the papers.', 'They arranged the chairs.', 'They designed the poster.', 'They produced the film.',
    'They created the account.', 'They introduced the speaker.', 'They explained the rule.', 'They recommended the route.',
    'They offered the service.', 'They showed the photograph.', 'They served the meal.', 'They returned the book.',
    'They forwarded the message.', 'They assigned the task.', 'They provided the details.', 'They organized the event.',
)

EN_PASSIVE_BY = (
    'The report was reviewed by them.', 'The fence was painted by her.', 'The bridge was repaired by him.',
    'The engine was inspected by them.', 'The kitchen was cleaned by her.', 'The boxes were carried by them.',
    'The schedule was checked by him.', 'The device was tested by them.', 'The manual was updated by her.',
    'The label was removed by them.', 'The battery was replaced by him.', 'The result was announced by them.',
    'The room was prepared by her.', 'The meeting was cancelled by them.', 'The booking was confirmed by him.',
    'The staff were notified by them.', 'The driver was warned by her.', 'The village was protected by them.',
    'The child was rescued by him.', 'The proposal was discussed by them.',
)

EN_PASSIVE_NO_AGENT = (
    'The sample was examined.', 'The form was completed.', 'The application was submitted.', 'The article was published.',
    'The papers were collected.', 'The chairs were arranged.', 'The poster was designed.', 'The film was produced.',
    'The account was created.', 'The speaker was introduced.', 'The rule was explained.', 'The route was recommended.',
    'The service was offered.', 'The photograph was shown.', 'The meal was served.', 'The book was returned.',
    'The message was forwarded.', 'The task was assigned.', 'The details were provided.', 'The event was organized.',
)


def _read(text, lang):
    return read(text, lang=lang)


def _is_passive(c):
    return c.get('voice') == 'passive'


def test_fixture_has_at_least_eighty_unique_sentences_in_each_language():
    ja = JA_PASSIVE_NO_AGENT + JA_PASSIVE_WITH_AGENT + JA_ACTIVE + tuple(x[0] for x in JA_ROLE_CASES)
    en = EN_ACTIVE + EN_PASSIVE_BY + EN_PASSIVE_NO_AGENT
    assert len(ja) == 100 and len(set(ja)) == 100, (len(ja), len(set(ja)))
    assert len(en) == 80 and len(set(en)) == 80, (len(en), len(set(en)))


def test_ja_no_agent_passives_and_active_controls_do_not_gain_a_false_passive():
    violations = []
    for text in JA_PASSIVE_NO_AGENT:
        out = _read(text, 'ja')
        if out['readable']:
            violations.append(('K62-no-agent', text, out))
    for text in JA_ACTIVE:
        out = _read(text, 'ja')
        if out['readable'] and any(_is_passive(c) for c in out['clauses']):
            violations.append(('K62-active-as-passive', text, out))
    assert not violations, violations


def test_ja_positive_agent_cases_are_read_as_passive_or_counted_as_overabstention():
    over_abstentions = []
    wrong_voice = []
    for text in JA_PASSIVE_WITH_AGENT:
        out = _read(text, 'ja')
        if not out['readable']:
            over_abstentions.append((text, out.get('abstain')))
        elif not out['clauses'] or not _is_passive(out['clauses'][0]) or 'agent' not in out['clauses'][0]['roles']:
            wrong_voice.append((text, out))
    assert not wrong_voice, wrong_voice
    # This separate assertion makes any over-abstention executable and visible; it is never merged into a false-read hit.
    assert not over_abstentions, {'over_abstentions': over_abstentions}


def test_k64_wo_agent_patient_assignments_match_the_manual_cases():
    violations = []
    over_abstentions = []
    for text, expected, agent, patient in JA_ROLE_CASES:
        out = _read(text, 'ja')
        if expected == 'abstain':
            if out['readable']:
                violations.append((text, 'expected abstention; got roles', out['clauses']))
            continue
        if not out['readable']:
            over_abstentions.append((text, out.get('abstain')))
            continue
        roles = out['clauses'][0]['roles'] if out['clauses'] else {}
        if roles.get('agent') != agent or roles.get('patient') != patient:
            violations.append((text, {'agent': agent, 'patient': patient}, roles, out))
    assert not violations, violations
    assert not over_abstentions, {'positive_evidence_over_abstentions': over_abstentions}


def test_english_active_and_passive_controls_match_the_manual_voice_gold():
    expected = [(s, 'active') for s in EN_ACTIVE]
    expected += [(s, 'passive') for s in EN_PASSIVE_BY + EN_PASSIVE_NO_AGENT]
    violations = []
    over_abstentions = []
    for text, voice in expected:
        out = _read(text, 'en')
        if not out['readable']:
            if voice == 'passive':
                over_abstentions.append((text, out.get('abstain')))
            continue
        if not out['clauses'] or out['clauses'][0].get('voice') != voice:
            violations.append((text, voice, out))
    assert not violations, violations
    assert not over_abstentions, {'positive_passive_over_abstentions': over_abstentions}


def test_k63_readable_never_coexists_with_an_unsupported_clause_outside_the_written_comparison_exception():
    texts = (JA_PASSIVE_NO_AGENT + JA_PASSIVE_WITH_AGENT + JA_ACTIVE + tuple(x[0] for x in JA_ROLE_CASES)
             + EN_ACTIVE + EN_PASSIVE_BY + EN_PASSIVE_NO_AGENT)
    violations = []
    for text in texts:
        lang = 'en' if text in EN_ACTIVE + EN_PASSIVE_BY + EN_PASSIVE_NO_AGENT else 'ja'
        out = _read(text, lang)
        if not out['readable'] or not out.get('unsupported'):
            continue
        allowed = (all(item.get('reasons') == ['copula value is a predicate phrase'] for item in out['unsupported'])
                   and any(c.get('comparison') for c in out.get('clauses', ())))
        if not allowed:
            violations.append((text, out))
    # The explicit exception itself must still work, so it cannot be silently removed to satisfy this invariant.
    comparison = _read('この公園は隣の公園より広い。', 'ja')
    assert comparison['readable'] and comparison['unsupported']
    assert all(item['reasons'] == ['copula value is a predicate phrase'] for item in comparison['unsupported'])
    assert any(c.get('comparison') for c in comparison['clauses'])
    assert not violations, violations


def _mapping_paths(node, here=()):
    if isinstance(node, dict):
        yield here
        for key, value in node.items():
            yield from _mapping_paths(value, here + (key,))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _mapping_paths(value, here + (index,))


def _at(node, path):
    for part in path:
        node = node[part]
    return node


def _reorder_one(node, path, keys):
    out = copy.deepcopy(node)
    if not path:
        return {key: out[key] for key in keys}
    parent = _at(out, path[:-1])
    old = parent[path[-1]]
    parent[path[-1]] = {key: old[key] for key in keys}
    return out


def _reverse_mappings(node):
    if isinstance(node, dict):
        return {key: _reverse_mappings(value) for key, value in reversed(list(node.items()))}
    if isinstance(node, list):
        return [_reverse_mappings(value) for value in node]
    return copy.deepcopy(node)


def _event_input():
    return {
        'schema': 'verantyx.semantic_read/1', 'lang': 'ja', 'readable': True,
        'clauses': [{'predicate': '渡す', 'roles': {'patient': '本', 'agent': '太郎', 'recipient': '花子'},
                     'polarity': '+', 'tense': 'past', 'modality': None, 'voice': 'active',
                     'quantifiers': {'patient': {'kind': 'universal', 'word': '各', 'detail': {'x': 1, 'y': 2}}},
                     'scope': {'basis': {'wide': 'agent', 'narrow': 'patient'}, 'wide': 'agent', 'narrow': 'patient'}}],
        'relations': [{'to': 1, 'extra_z': {'b': 2, 'a': 1}, 'from': 0, 'type': 'relative'}],
        'abstain': None, 'unsupported': [],
        'clause_meta': [{'span': [0, 5], 'rule': 'frame', 'detail': {'z': 0, 'a': 1}}],
    }


def _dump_event(value):
    return json.dumps(build_crosses(value).to_dict(), ensure_ascii=False).encode('utf-8')


def test_event_cross_serialization_is_invariant_under_each_input_mapping_key_order():
    base = _event_input()
    want = _dump_event(base)
    for path in _mapping_paths(base):
        mapping = _at(base, path)
        reversed_keys = list(reversed(list(mapping)))
        assert _dump_event(_reorder_one(base, path, reversed_keys)) == want, path
    assert _dump_event(_reverse_mappings(base)) == want
    for order in itertools.permutations(base):
        changed = {key: base[key] for key in order}
        assert _dump_event(changed) == want


class _PickZero:
    def __init__(self):
        self.calls = 0

    def ask(self, prompt):
        self.calls += 1
        return ProviderReply.success('{"choice": 0}')


def _context_chooser(tmp_path, provider):
    return LLMChooser(provider, ChoiceLedger(tmp_path / 'ledger.jsonl'), order_source=lambda n: list(range(n)))


def test_reuse_key_changes_when_any_individual_context_line_or_its_order_changes(tmp_path):
    base = [ChoiceCandidate('A', ('reason=clear', 'roles=implement', 'kind=feature', 'lineage=one', 'model=first')),
            ChoiceCandidate('B', ('reason=other', 'roles=implement', 'kind=feature', 'lineage=two', 'model=second'))]
    variants = [
        [ChoiceCandidate('A', ('reason=changed',) + base[0].used_in[1:]), base[1]],
        [ChoiceCandidate('A', (base[0].used_in[0], 'roles=review') + base[0].used_in[2:]), base[1]],
        [ChoiceCandidate('A', base[0].used_in[:2] + ('kind=other',) + base[0].used_in[3:]), base[1]],
        [ChoiceCandidate('A', base[0].used_in[:3] + ('lineage=two',) + base[0].used_in[4:]), base[1]],
        [ChoiceCandidate('A', base[0].used_in[:4] + ('model=second',)), base[1]],
        [ChoiceCandidate('A', base[0].used_in + ('new-context=shown',)), base[1]],
        [ChoiceCandidate('A', base[0].used_in[:-1]), base[1]],
        [ChoiceCandidate('A', tuple(reversed(base[0].used_in)),), base[1]],
        [base[0], ChoiceCandidate('B', base[1].used_in + ('one extra line',))],
    ]
    misses = []
    for index, changed in enumerate(variants):
        provider = _PickZero()
        chooser = _context_chooser(tmp_path / ('variant-%02d' % index), provider)
        first = chooser.choose('term', base)
        second = chooser.choose('term', changed)
        if first.status != 'ADOPTED' or second.status != 'ADOPTED' or second.cached or provider.calls != 4:
            misses.append((index, first.status, second.status, second.cached, provider.calls))
    assert not misses, misses


def test_same_context_reuses_after_candidate_order_changes(tmp_path):
    provider = _PickZero()
    chooser = _context_chooser(tmp_path, provider)
    first = chooser.choose('term', [ChoiceCandidate('A', ('same',)), ChoiceCandidate('B', ('other',))])
    second = chooser.choose('term', [ChoiceCandidate('B', ('other',)), ChoiceCandidate('A', ('same',))])
    assert first.status == 'ADOPTED' and first.cached is False
    assert second.status == 'ADOPTED' and second.cached is True and provider.calls == 2

