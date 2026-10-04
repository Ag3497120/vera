"""W3-c: `semantic_realize.realize_observed` / `observed_variants` / `check_observed_lineage` — an observed cross is said with words that
are already in it, checked by reading the sentence again, and anything else is a typed refusal."""
import importlib.util
from pathlib import Path

import pytest

from verantyx import event_cross as EC
from verantyx import observe as O
from verantyx import semantic_realize as SR

_spec = importlib.util.spec_from_file_location('w3c_observe_fakes', Path(__file__).resolve().parent / 'observe' / 'fakes.py')
fakes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fakes)


def cross_of(text, lang='ja'):
    out = EC.read_events(text, lang)
    assert out['events']['status'] == 'CROSSED', text
    return out['events']['crosses'][0]


def realize(cross, lang='ja'):
    return SR.realize_observed(cross['center'], cross['arms'], lang, cell_id='cell:x', rule=cross['provenance']['rule'])


def hand(clause_kwargs, rule='frame'):
    out = fakes.read_out([fakes.clause(**clause_kwargs)], metas=[{'rule': rule, 'span': [0, 1]}])
    c = EC.build_crosses(out).crosses[0].to_dict()
    return c


def content_key(text):
    return O.cell_key_of(EC.build_crosses(__import__('verantyx.semantic_read', fromlist=['read']).read(text, 'ja')).crosses[0])


SENTENCES = [
    '太郎は花子に本をあげた。',            # give: agent, patient, recipient
    '母は台所で料理を作った。',            # place (で)
    '先生は駅から学校へ行った。',          # source (から) and goal (へ)
    '太郎は花子に本をあげなかった。',      # negation
    '犬は庭で寝る。',                      # non-past
]


@pytest.mark.parametrize('text', SENTENCES)
def test_realized_sentence_is_read_again_to_the_same_cell(text):
    c = cross_of(text)
    got = realize(c)
    assert isinstance(got, SR.Realized), got
    assert got.derivation == 'observed-cross' and got.style == 'plain' and got.spans == () and got.clause_id == 'cell:x'
    assert got.checks['roundtrip']['passed'] and got.checks['term_lineage']['passed']
    assert content_key(got.text) == O.cell_key_of(EC.build_crosses(__import__('verantyx.semantic_read', fromlist=['read']).read(text, 'ja')).crosses[0])


def test_the_canonical_sentence_is_the_default_form():
    assert realize(cross_of('太郎は花子に本をあげた。')).text == '太郎は花子に本をあげた。'
    assert realize(cross_of('犬は庭で寝る。')).text == '犬は庭で寝る。'


def test_swapped_filler_is_said_with_the_new_word_only():
    c = cross_of('太郎は花子に本をあげた。')
    c['arms']['agent']['fillers'][0]['surface'] = '次郎'
    got = realize(c)
    assert isinstance(got, SR.Realized) and got.text == '次郎は花子に本をあげた。'


@pytest.mark.parametrize('text', SENTENCES)
def test_content_words_are_all_the_predicate_or_a_filler(text):
    c = cross_of(text)
    got = realize(c)
    surfaces = [f['surface'] for a in c['arms'].values() for f in a['fillers']]
    lineage = SR.check_observed_lineage(got.text, c['center']['predicate'], surfaces)
    assert lineage['passed'] and lineage['extra_lemmas'] == [] and lineage['unexpected_tokens'] == []


def test_lineage_check_names_a_word_that_is_not_in_the_observation():
    ok = SR.check_observed_lineage('太郎は花子に本をあげた。', 'あげる', ['太郎', '本', '花子'])
    assert ok['passed']
    bad = SR.check_observed_lineage('太郎は花子に新しい本をあげた。', 'あげる', ['太郎', '本', '花子'])
    assert not bad['passed'] and any(e['surface'] == '新しい' for e in bad['extra_lemmas'])
    missing_filler = SR.check_observed_lineage('太郎は花子に猫をあげた。', 'あげる', ['太郎', '本', '花子'])
    assert not missing_filler['passed']


def test_lineage_tags_each_filler_alone():
    # a filler that is tagged differently inside a longer string must still license its own lemma
    for text, surfaces in (('母は台所で料理を作った。', ['母', '台所', '料理']),):
        assert SR.check_observed_lineage(text, '作る', surfaces)['passed']


def test_variants_are_listed_not_chosen_and_each_reads_back_to_the_same_cell():
    c = cross_of('太郎は花子に本をあげた。')
    canonical = realize(c).text
    variants = SR.observed_variants(c['center'], c['arms'], 'ja', cell_id='cell:x', rule='frame')
    texts = [v.text for v in variants if isinstance(v, SR.Realized)]
    assert texts and canonical not in texts and len(texts) == len(set(texts))
    assert '太郎が花子に本をあげた。' in texts and '太郎は花子に本をあげました。' in texts and '太郎は本を花子にあげた。' in texts
    key = O.cell_key_of(EC.build_crosses(__import__('verantyx.semantic_read', fromlist=['read']).read('太郎は花子に本をあげた。', 'ja')).crosses[0])
    for t in texts:
        assert content_key(t) == key
    for v in variants:
        if isinstance(v, SR.Realized):
            assert v.derivation == 'observed-cross-variant' and set(v.checks['variant']) == {'style', 'topic', 'role_order'}


@pytest.mark.parametrize('kwargs,reason', [
    ({'predicate': 'あげる', 'roles': {'agent': ['太郎', '次郎'], 'patient': '本'}}, 'ROLE_NOT_REALIZABLE'),      # ARM_TIE
    ({'predicate': 'あげる', 'roles': {'agent': '太郎', 'time': '昨日'}}, 'ROLE_NOT_REALIZABLE'),                 # time arm
    ({'predicate': 'あげる', 'roles': {'patient': '本'}}, 'ROLE_NOT_REALIZABLE'),                                  # no agent
    ({'predicate': 'あげる', 'roles': {'agent': '太郎', 'patient': '本'}, 'voice': 'passive'}, 'UNSUPPORTED_MODALITY'),
    ({'predicate': 'あげる', 'roles': {'agent': '太郎', 'patient': '本'}, 'modality': 'volition'}, 'UNSUPPORTED_MODALITY'),
    ({'predicate': 'あげる', 'roles': {'agent': '太郎', 'patient': '本'}, 'tense': None}, 'ROLE_NOT_REALIZABLE'),
    ({'predicate': 'あげる', 'roles': {'agent': '太郎', 'patient': '本'}, 'quantifiers': {'patient': {'n': 3}}}, 'ROLE_NOT_REALIZABLE'),
    ({'predicate': 'あげる', 'roles': {'agent': '太郎', 'instrument': '手'}}, 'ROLE_NOT_REALIZABLE'),
])
def test_out_of_scope_crosses_are_typed_refusals(kwargs, reason):
    c = hand(kwargs)
    got = realize(c)
    assert isinstance(got, SR.Refused) and got.reason == reason and got.reason in SR.REFUSAL_REASONS


def test_copula_rule_is_unsupported_rule_and_english_is_not_realizable():
    c = hand({'predicate': 'identity', 'roles': {'entity': '犬', 'value': '動物'}, 'tense': None}, rule='copula')
    assert realize(c).reason == 'UNSUPPORTED_RULE'
    en = cross_of('Taro gave Hanako a book.', 'en')
    assert realize(en, 'en').reason == 'NOT_REALIZABLE'
    assert SR.observed_variants(en['center'], en['arms'], 'en', cell_id='c', rule='en_frames')[0].reason == 'NOT_REALIZABLE'


def test_a_sentence_that_does_not_read_back_to_the_cell_is_refused_not_returned():
    # an unknown conjugation: the predicate is not a verb the closed conjugation table knows
    c = hand({'predicate': 'ぷぷぷ', 'roles': {'agent': '太郎', 'patient': '本'}})
    got = realize(c)
    assert isinstance(got, SR.Refused) and got.reason in ('CONJUGATION_UNKNOWN', 'ROUNDTRIP_MISMATCH', 'TERM_LINEAGE_MISMATCH')


def test_existing_names_and_the_refusal_vocabulary_are_not_changed():
    assert SR.REFUSAL_REASONS >= {'UNSUPPORTED_RULE', 'UNSUPPORTED_MODALITY', 'ROLE_NOT_REALIZABLE', 'ROUNDTRIP_MISMATCH', 'TERM_LINEAGE_MISMATCH', 'NOT_REALIZABLE'}
    for name in ('realize_observed', 'observed_variants', 'check_observed_lineage', 'realize_clause', 'realize_variants'):
        assert name in SR.__all__
