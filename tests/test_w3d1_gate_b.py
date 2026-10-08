"""W3-d1 (T4, J10): the gate (b) step "realize -> read again with the same placement" works on the frozen script of one-hole sentences.
The expectations of the table were written and frozen (sha256 in artifacts/w3-d1/data_freeze.sha256) BEFORE the realizer was changed.
The placement r8 is read only; without it the tests skip (the same pattern as tests/test_w10f04_fill.py)."""
import inspect
from pathlib import Path

import pytest

from verantyx import fill_candidates as F
from verantyx import semantic_read as S

R8 = '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2'

# (sentence, word, word type) -> the realize status the step must give
PASSING = [
    ('母が図書館へ歩いた。', '駅', 'PLACE'),
    ('兄が窓口で名乗った。', '駅', 'PLACE'),
    ('母がホールで断った。', '駅', 'PLACE'),
    ('弟が交番で走った。', '駅', 'PLACE'),
    ('兄が土間で歩いた。', '駅', 'PLACE'),
    ('手紙が駅へ飛んだ。', '犬', 'ANIMAL'),
    ('夫婦がホテルで名乗った。', '犬', 'ANIMAL'),
]
FAILING = [
    ('兄が山田に催促した。', '朝', 'TIME'),
    ('姉が本社に請求した。', '朝', 'TIME'),
    ('妹が山田に申告した。', '朝', 'TIME'),
    ('妹が東京に旅行した。', '朝', 'TIME'),
    ('学生が友人に催促した。', '朝', 'TIME'),
    ('母がホテルで勝利を願った。', '先生', 'PERSON'),
]


@pytest.fixture
def r8(monkeypatch):
    if not Path(R8).exists():
        pytest.skip('ENV_MISSING[coarse placement r8/run2]')
    monkeypatch.setenv('VERA_PLACEMENT', R8)
    return R8


def gate(sentence, word, wtype, require):
    ho = S.read_with_holes(sentence, placement=R8)
    return F._gate_b(sentence, ho, 0, word, wtype, S._placement_query(R8), R8, {}, require)


@pytest.mark.parametrize('sentence,word,wtype', PASSING)
def test_a_realizable_typed_cross_passes_gate_b_when_required(r8, sentence, word, wtype):
    assert gate(sentence, word, wtype, True) == (None, 'REALIZED')
    assert gate(sentence, word, wtype, False) == (None, 'REALIZED')            # the default does not make it a gate, and the record says what happened


@pytest.mark.parametrize('sentence,word,wtype', FAILING)
def test_an_unrealizable_cross_falls_at_the_realize_step_when_required(r8, sentence, word, wtype):
    assert gate(sentence, word, wtype, True) == ('GATE_B_REALIZE_REFUSED', 'REFUSED')
    assert gate(sentence, word, wtype, False) == (None, 'REFUSED')             # not required: recorded, not a gate


def test_the_default_of_require_realize_is_unchanged():
    assert inspect.signature(F.ask_and_gate).parameters['require_realize'].default is False
    assert inspect.signature(F._gate_b).parameters['require_realize'].default is False
    assert F.FillConfig.__dataclass_fields__['require_realize'].default is False


def test_the_j10_sentence_of_test_w10f04_fill_is_now_realized(r8):
    """The case that tests/test_w10f04_fill.py::test_realize_is_recorded_and_can_be_required pins as REFUSED (J10): the same call now gives REALIZED."""
    q = S._placement_query(R8)
    ho = S.read_with_holes('母が図書館へ歩いた。', placement=R8)
    assert F._gate_b('母が図書館へ歩いた。', ho, 0, '駅', 'PLACE', q, R8, {}) == (None, 'REALIZED')
    assert F._gate_b('母が図書館へ歩いた。', ho, 0, '駅', 'PLACE', q, R8, {}, True) == (None, 'REALIZED')
