from types import SimpleNamespace

import pytest

from verantyx.semantic_verify import Rejected, _native_guard_scope, _ranges, license_clause


def _span(text, start=0):
    return SimpleNamespace(start=start, end=start + len(text), text=text)


class _SourceSpan:
    def __init__(self, source, text, start=0):
        self.source = source
        self.text = text
        self.start = start
        self.end = start + len(text)

    def valid(self, sources):
        return (self.source in sources and 0 <= self.start <= self.end
                and sources[self.source][self.start:self.end] == self.text)


def _symbolic_source(actor_text, *, source_actor=None, predicate="owns"):
    source_actor = actor_text if source_actor is None else source_actor
    raw = f"{predicate}({source_actor})."
    key = "source-0"
    clause = SimpleNamespace(
        id="clause-0",
        sovereign="s0",
        span=_SourceSpan(key, raw),
        body_span=_SourceSpan(key, raw),
        predicate_span=_SourceSpan(key, predicate),
        roles=(SimpleNamespace(
            name="actor",
            term=actor_text,
            span=_SourceSpan(key, source_actor, len(predicate) + 1),
            rule="literal",
        ),),
        condition_spans=(),
        exception_spans=(),
        conditions=(),
        exceptions=(),
        event=SimpleNamespace(sort="event"),
        unsupported=False,
        rule="record",
        predicate=predicate,
        polarity="+",
        modality="assert",
        time="",
    )
    view = SimpleNamespace(by_id={clause.id: clause}, sources={key: raw})
    return clause, view


def _scope(raw, body_start=0, *, rule="frame", roles=(), conditions=(), condition_spans=()):
    return SimpleNamespace(
        span=_span(raw),
        body_span=_span(raw[body_start:], body_start),
        rule=rule,
        roles=roles,
        conditions=conditions,
        condition_spans=condition_spans,
    )


def test_symbolic_record_licenses_unicode_actor_without_normalization():
    actor = "Ａe\u0301👩\u200d💻אב"
    clause, view = _symbolic_source(actor)

    license_clause(clause, view)


def test_symbolic_record_rejects_confusable_source_value_mismatch():
    clause, view = _symbolic_source("Latin A", source_actor="Latin А")

    with pytest.raises(Rejected, match="role/value licensing"):
        license_clause(clause, view)


def test_symbolic_record_refuses_fullwidth_formula_delimiters():
    actor = "猫"
    raw = "owns（猫）。"
    key = "source-0"
    clause = SimpleNamespace(
        id="clause-0",
        sovereign="s0",
        span=_SourceSpan(key, raw),
        body_span=_SourceSpan(key, raw),
        predicate_span=_SourceSpan(key, "owns"),
        roles=(SimpleNamespace(
            name="actor", term=actor, span=_SourceSpan(key, actor, len("owns（")), rule="literal",
        ),),
        condition_spans=(), exception_spans=(), conditions=(), exceptions=(),
        event=SimpleNamespace(sort="event"), unsupported=False,
        rule="record", predicate="owns", polarity="+", modality="assert", time="",
    )
    view = SimpleNamespace(by_id={clause.id: clause}, sources={key: raw})

    with pytest.raises(Rejected, match="symbolic source formula"):
        license_clause(clause, view)


def test_fullwidth_sentence_marks_define_exact_source_ranges():
    raw = "猫は青い。犬は白い！鳥は黒い？"
    first = len("猫は青い。")
    second = first + len("犬は白い！")

    assert _ranges(raw) == {(0, first), (first, second), (second, len(raw))}


def test_japanese_quoted_punctuation_does_not_end_a_source_range():
    raw = "猫は「青い。丸い。」犬は白い。"

    assert _ranges(raw) == {(0, len(raw))}


def test_nested_japanese_quote_styles_keep_inner_punctuation_in_scope():
    raw = "猫は「『青い。丸い。』と言う。」犬は白い。"

    assert _ranges(raw) == {(0, len(raw))}


def test_unbalanced_japanese_quote_is_refused():
    with pytest.raises(Rejected, match="unclosed source quotation"):
        _ranges("猫は「青い。犬は白い。")


def test_halfwidth_punctuation_is_preserved_verbatim():
    raw = "猫｡犬､鳥。"

    assert _ranges(raw) == {(0, len(raw))}
    assert raw[slice(*next(iter(_ranges(raw))))] == raw


def test_combining_zero_width_and_emoji_sequences_are_preserved():
    raw = "ＡＢＣe\u0301\u200b👩\u200d💻אב"

    assert _ranges(raw) == {(0, len(raw))}
    start, end = next(iter(_ranges(raw)))
    assert raw[start:end] == "ＡＢＣe\u0301\u200b👩\u200d💻אב"


def test_mixed_scripts_and_fullwidth_colon_remain_in_their_original_range():
    raw = "Latin А：猫。犬"
    cut = len("Latin А：猫。")

    assert _ranges(raw) == {(0, cut), (cut, len(raw))}


def test_markup_and_ascii_punctuation_are_not_normalized_or_dropped():
    raw = "<!-- ?! -->\n<svg>☃</svg>。"
    cut = len("<!-- ?! -->\n")

    assert _ranges(raw) == {(0, cut), (cut, len(raw))}
    assert raw[:cut] == "<!-- ?! -->\n"


def test_ascii_art_noise_is_kept_as_source_text():
    noise = " /\\ ?! \\_/ ＼ _\\"
    raw = noise + "\n" + "猫"
    cut = len(noise) + 1

    assert _ranges(raw) == {(0, cut), (cut, len(raw))}
    assert raw[:cut] == noise + "\n"


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: curly quotation marks do not shield sentence punctuation",
)
def test_curly_quoted_sentence_mark_is_not_silently_treated_as_boundary():
    raw = "猫は“青い。犬は白い”と言う。"

    assert _ranges(raw) == {(0, len(raw))}


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: halfwidth corner brackets do not shield sentence punctuation",
)
def test_halfwidth_quoted_sentence_mark_is_not_silently_treated_as_boundary():
    raw = "猫は｢青い。犬は白い｣と言う。"

    assert _ranges(raw) == {(0, len(raw))}


def test_ascii_colon_prefix_is_rejected_as_uninterpreted_scope():
    raw = "注記:猫が走る"

    with pytest.raises(Rejected, match="uninterpreted colon scope"):
        _native_guard_scope(_scope(raw, len("注記:")), _span(raw[len("注記:"):], len("注記:")))


def test_fullwidth_colon_prefix_is_rejected_as_uninterpreted_scope():
    raw = "注記：猫が走る"

    with pytest.raises(Rejected, match="uninterpreted colon scope"):
        _native_guard_scope(_scope(raw, len("注記：")), _span(raw[len("注記："):], len("注記：")))


def test_unicode_prefix_guard_uses_exact_codepoint_offsets():
    raw = "e\u0301猫が来るならば、犬が走る"
    condition = "e\u0301猫が来る"
    body_start = len(condition + "ならば、")
    guard = SimpleNamespace(start=0, end=len(condition), text=condition)
    clause = _scope(
        raw,
        body_start,
        conditions=(object(),),
        condition_spans=(guard,),
    )

    _native_guard_scope(clause, clause.body_span)


def test_narrowing_body_past_unicode_antecedent_is_rejected():
    raw = "e\u0301猫が来るならば、犬が走る"
    body_start = len("e\u0301猫が来るならば、")

    with pytest.raises(Rejected, match="missing or duplicate source condition"):
        _native_guard_scope(_scope(raw, body_start), _span(raw[body_start:], body_start))
