import pytest

from verantyx.semantic_coord import coordination_ok, own_subject_phrase, phrase_bounded, tag, topic_phrase


def _token(surface, pos1, pos2, cform, start):
    return (surface, pos1, pos2, cform, start, start + len(surface))


def test_te_comma_chain_is_accepted():
    tagged = [
        _token("猫", "名詞", "一般", "", 0),
        _token("歩き", "動詞", "自立", "連用形", 1),
        _token("て", "助詞", "接続助詞", "", 3),
        _token("、", "補助記号", "読点", "", 4),
        _token("食べ", "動詞", "自立", "連用形", 5),
    ]

    assert coordination_ok(tagged, [1, 4])


def test_renyo_with_ideographic_comma_is_accepted():
    tagged = [
        _token("走り", "動詞", "自立", "連用形", 0),
        _token("、", "補助記号", "読点", "", 2),
        _token("笑い", "動詞", "自立", "連用形", 3),
    ]

    assert coordination_ok(tagged, [0, 2])


def test_bare_renyo_without_separator_is_refused():
    tagged = [
        _token("走り", "動詞", "自立", "連用形", 0),
        _token("笑い", "動詞", "自立", "連用形", 2),
    ]

    assert not coordination_ok(tagged, [0, 1])


def test_fullwidth_comma_is_not_the_coordination_comma():
    tagged = [
        _token("走り", "動詞", "自立", "連用形", 0),
        _token("，", "補助記号", "読点", "", 2),
        _token("笑い", "動詞", "自立", "連用形", 3),
    ]

    assert not coordination_ok(tagged, [0, 2])


def test_zero_width_noise_before_te_is_not_ignored():
    tagged = [
        _token("走り", "動詞", "自立", "連用形", 0),
        _token("\u200b", "補助記号", "", "", 2),
        _token("て", "助詞", "接続助詞", "", 3),
        _token("笑い", "動詞", "自立", "連用形", 4),
    ]

    assert not coordination_ok(tagged, [0, 3])


def test_halfwidth_katakana_te_is_not_a_te_particle():
    tagged = [
        _token("走り", "動詞", "自立", "連用形", 0),
        _token("ﾃ", "助詞", "接続助詞", "", 2),
        _token("笑い", "動詞", "自立", "連用形", 3),
    ]

    assert not coordination_ok(tagged, [0, 2])


def test_ascii_art_katakana_does_not_make_a_phrase_boundary():
    tagged = [
        _token("ノシ", "補助記号", "", "", 0),
        _token("猫", "名詞", "一般", "", 2),
        _token("見る", "動詞", "自立", "終止形", 3),
    ]

    assert not phrase_bounded(tagged, 2, 3)


def test_combining_mark_stays_inside_the_topic_span():
    tagged = [
        _token("e\u0301", "名詞", "一般", "", 0),
        _token("は", "助詞", "係助詞", "", 2),
        _token("行き", "動詞", "自立", "連用形", 3),
        _token("て", "助詞", "接続助詞", "", 5),
        _token("笑う", "動詞", "自立", "終止形", 6),
    ]

    assert topic_phrase(tagged, [2, 4]) == (0, 2)


def test_halfwidth_topic_particle_is_not_silently_treated_as_ha():
    tagged = [
        _token("猫", "名詞", "一般", "", 0),
        _token("ﾊ", "助詞", "係助詞", "", 1),
    ]

    assert not own_subject_phrase(tagged, 0, 2)


def test_tag_offsets_count_unicode_codepoints():
    class Feature:
        def __init__(self, pos1, pos2, cform):
            self.pos1 = pos1
            self.pos2 = pos2
            self.cForm = cform

    class Word:
        def __init__(self, surface, pos1, pos2, cform):
            self.surface = surface
            self.feature = Feature(pos1, pos2, cform)

    tagged = tag(
        [Word("e\u0301", "名詞", "一般", ""), Word("😀", "記号", "", "")],
        [10, 12],
    )

    assert tagged == [
        ("e\u0301", "名詞", "一般", "", 10, 12),
        ("😀", "記号", "", "", 12, 13),
    ]


@pytest.mark.parametrize(
    "noise",
    [
        pytest.param("🔥", id="emoji"),
        pytest.param("\u0301", id="combining-mark"),
        pytest.param("\u200b", id="zero-width"),
        pytest.param("<", id="markup-residue"),
    ],
)
@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: non-punctuation Unicode noise is accepted as phrase punctuation",
)
def test_non_punctuation_noise_does_not_make_a_phrase_boundary(noise):
    tagged = [
        _token(noise, "補助記号", "", "", 0),
        _token("猫", "名詞", "一般", "", len(noise)),
        _token("見る", "動詞", "自立", "終止形", len(noise) + 1),
    ]

    assert not phrase_bounded(tagged, len(noise), len(noise) + 1)
