from __future__ import annotations

import ast
import re
from dataclasses import replace
from pathlib import Path

import pytest

from verantyx.one import Vera
from verantyx.semantic_ir import Pattern, Span, View
from verantyx.semantic_reader import document_view
from verantyx.semantic_realize import (
    MAX_CHARS, MAX_CLAUSES, Realized, RealizedGroup, Refused,
    check_round_trip, check_term_lineage, realize_answer, realize_clause,
    realize_refusal, realize_variants, summarize_entity, summary_entity_from_request,
    verify_sentence,
)


def one_clause(text: str, source: str = "doc"):
    view = document_view({source: text})
    assert not view.unread
    assert len(view.clauses) == 1
    return view, view.clauses[0]


@pytest.mark.parametrize(
    "style,polarity,time,expected",
    [
        ("plain", "+", "past", "マキはリオに青鍵を渡した。"),
        ("plain", "-", "past", "マキはリオに青鍵を渡さなかった。"),
        ("plain", "+", "nonpast", "マキはリオに青鍵を渡す。"),
        ("plain", "-", "nonpast", "マキはリオに青鍵を渡さない。"),
        ("polite", "+", "past", "マキはリオに青鍵を渡しました。"),
        ("polite", "-", "past", "マキはリオに青鍵を渡しませんでした。"),
        ("polite", "+", "nonpast", "マキはリオに青鍵を渡します。"),
        ("polite", "-", "nonpast", "マキはリオに青鍵を渡しません。"),
    ],
)
def test_frame_style_polarity_tense_matrix_is_typed_and_verified(style, polarity, time, expected):
    _, base = one_clause("マキがリオに青鍵を渡した。")
    source = replace(base, polarity=polarity, time=time)
    result = realize_clause(source, style)
    assert isinstance(result, Realized), result
    assert result.text == expected
    assert result.derivation == "inverse-reader"
    assert result.clause_id == source.id
    assert result.checks["roundtrip"]["passed"]
    assert result.checks["term_lineage"]["passed"]
    assert result.spans and all(span.source == "doc" for span in result.spans)


@pytest.mark.parametrize("style,expected", [
    ("plain", "青鍵は道具である。"),
    ("polite", "青鍵は道具です。"),
])
def test_identity_copula_positive_style(style, expected):
    _, clause = one_clause("青鍵は道具である。")
    result = realize_clause(clause, style)
    assert isinstance(result, Realized), result
    assert result.text == expected


def test_identity_copula_negative_plain():
    _, clause = one_clause("青鍵は道具である。")
    result = realize_clause(replace(clause, polarity="-"), "plain")
    assert isinstance(result, Realized), result
    assert result.text == "青鍵は道具ではない。"
    assert result.checks["roundtrip"]["passed"] and result.checks["term_lineage"]["passed"]


def test_identity_copula_negative_polite_is_refused_by_reader_gate():
    _, clause = one_clause("青鍵は道具ではない。")
    result = realize_clause(clause, "polite")
    assert isinstance(result, Refused)
    assert result.reason == "ROUNDTRIP_MISMATCH"
    assert result.checks["roundtrip"]["passed"] is False


@pytest.mark.parametrize("style,expected", [
    ("plain", "木の種類は針葉樹である。"),
    ("polite", "木の種類は針葉樹です。"),
])
def test_property_copula_uses_attribute_source_surface(style, expected):
    _, clause = one_clause("木の種類は針葉樹である。")
    result = realize_clause(clause, style)
    assert isinstance(result, Realized), result
    assert result.text == expected
    assert all(check["passed"] for check in result.checks.values())


def test_property_attribute_nominal_surface_is_not_rederived():
    _, clause = one_clause("木の高さは高い。")
    attr = next(role for role in clause.roles if role.name == "attribute")
    assert attr.term == "nominal:高い"
    assert attr.span.text == "高さ"
    result = realize_clause(clause)
    assert isinstance(result, Realized), result
    assert result.text == "木の高さは高い。"


@pytest.mark.parametrize("style,expected", [
    ("plain", "木の高さは高い。"),
    ("polite", "木の高さは高いです。"),
])
def test_adjective_property_positive_styles(style, expected):
    _, clause = one_clause("木の高さは高い。")
    result = realize_clause(clause, style)
    assert isinstance(result, Realized), result
    assert result.text == expected


@pytest.mark.parametrize("style", ["plain", "polite"])
def test_adjective_property_negative_refuses_unrepresentable_surface(style):
    _, clause = one_clause("木の高さは高い。")
    result = realize_clause(replace(clause, polarity="-"), style)
    assert isinstance(result, Refused)
    assert result.reason == "ROLE_NOT_REALIZABLE"


@pytest.mark.parametrize("style,expected", [("plain", "Aは12mだ。"), ("polite", "Aは12mです。")])
def test_measure_rule_styles(style, expected):
    _, clause = one_clause("Aは12mです。")
    result = realize_clause(clause, style)
    assert isinstance(result, Realized), result
    assert result.text == expected
    assert all(check["passed"] for check in result.checks.values())


@pytest.mark.parametrize("raw,role", [
    ("マキは学校で本を読んだ。", "location"),
    ("マキは学校から本を運んだ。", "origin"),
    ("マキは研究室へ行った。", "recipient"),
])
def test_reader_case_roles_are_preserved(raw, role):
    _, clause = one_clause(raw)
    assert role in {item.name for item in clause.roles}
    result = realize_clause(clause)
    assert isinstance(result, Realized), result
    assert result.checks["roundtrip"]["passed"] and result.checks["term_lineage"]["passed"]


def test_topic_subject_and_role_order_variants_are_all_verified():
    _, clause = one_clause("マキがリオに青鍵を渡した。")
    variants = [item for item in realize_variants(clause) if isinstance(item, Realized)]
    surfaces = {item.text for item in variants}
    assert len(surfaces) == 8
    assert "マキはリオに青鍵を渡した。" in surfaces
    assert "マキがリオに青鍵を渡した。" in surfaces
    assert "マキは青鍵をリオに渡した。" in surfaces
    assert "マキが青鍵をリオに渡した。" in surfaces
    assert all(item.checks["roundtrip"]["passed"] for item in variants)
    assert all(item.checks["term_lineage"]["passed"] for item in variants)


@pytest.mark.parametrize("field", ["conditions", "exceptions"])
def test_guarded_clause_is_typed_refusal(field):
    _, clause = one_clause("マキが本を読んだ。")
    guarded = replace(clause, **{field: (Pattern("来る", ()),)})
    result = realize_clause(guarded)
    assert isinstance(result, Refused)
    assert result.reason == "UNSUPPORTED_GUARDED"
    assert result.clause_ids == (clause.id,)


@pytest.mark.parametrize("modality", ["quote", "hedge", "permission"])
def test_nonasserted_modalities_refuse(modality):
    _, clause = one_clause("マキが本を読んだ。")
    result = realize_clause(replace(clause, modality=modality))
    assert isinstance(result, Refused)
    assert result.reason == "UNSUPPORTED_MODALITY"


def test_unknown_rule_and_unknown_conjugation_refuse():
    _, clause = one_clause("マキが本を読んだ。")
    unsupported = realize_clause(replace(clause, rule="other"))
    unknown = realize_clause(replace(clause, predicate="q"))
    assert isinstance(unsupported, Refused) and unsupported.reason == "UNSUPPORTED_RULE"
    assert isinstance(unknown, Refused) and unknown.reason == "CONJUGATION_UNKNOWN"


def test_wrong_tense_fails_roundtrip_only():
    _, clause = one_clause("マキがリオに青鍵を渡した。")
    checks = verify_sentence(clause, "マキはリオに青鍵を渡す。")
    assert not checks["roundtrip"]["passed"]
    assert checks["term_lineage"]["passed"]


def test_wrong_polarity_fails_roundtrip_only():
    _, clause = one_clause("マキがリオに青鍵を渡した。")
    checks = verify_sentence(clause, "マキはリオに青鍵を渡さなかった。")
    assert not checks["roundtrip"]["passed"]
    assert checks["term_lineage"]["passed"]


def test_swapped_role_terms_fail_roundtrip_but_keep_lineage():
    _, clause = one_clause("マキがリオに青鍵を渡した。")
    checks = verify_sentence(clause, "マキは青鍵にリオを渡した。")
    assert not checks["roundtrip"]["passed"]
    assert checks["term_lineage"]["passed"]


def test_fabricated_term_fails_both_independent_checks():
    _, clause = one_clause("マキがリオに青鍵を渡した。")
    checks = verify_sentence(clause, "マキはリオに宝石を渡した。")
    assert not checks["roundtrip"]["passed"]
    assert not checks["term_lineage"]["passed"]
    assert checks["term_lineage"]["extra_lemmas"]


def test_function_word_allowlist_is_closed():
    _, clause = one_clause("マキが本を読んだ。")
    assert not check_term_lineage(clause, "マキは本を読む。また。")["passed"]


def test_determinism_for_clause_and_variants():
    _, clause = one_clause("マキがリオに青鍵を渡した。")
    assert realize_clause(clause) == realize_clause(clause)
    assert realize_variants(clause) == realize_variants(clause)


def test_no_sentence_is_emitted_without_valid_source_provenance():
    _, clause = one_clause("マキが本を読んだ。")
    invalid = replace(clause, id="", span=Span("", 0, 0, ""))
    result = realize_clause(invalid)
    assert isinstance(result, Refused)
    assert result.reason == "INVALID_PROVENANCE"
    assert result.text is None
    assert not result.clause_ids


def test_generated_text_is_bounded():
    _, clause = one_clause("マキが本を読んだ。")
    too_many = summarize_entity(document_view({"d": "マキは本を読む。"}), "マキ", limit=MAX_CLAUSES + 1)
    assert isinstance(too_many, Refused) and too_many.reason == "BUDGET"
    assert MAX_CHARS == 2048 and MAX_CLAUSES == 64


def test_summary_conflict_lists_both_clause_ids():
    view = document_view({"d": "マキが本を読んだ。マキが本を読まなかった。"})
    assert len(view.clauses) == 2
    result = summarize_entity(view, "マキ")
    assert isinstance(result, Refused)
    assert result.reason == "CONFLICT"
    assert result.clause_ids == tuple(clause.id for clause in view.clauses)


def test_summary_deduplicates_projection_and_cites_every_span():
    view = document_view({"a": "マキは学生である。", "b": "マキは学生である。"})
    result = summarize_entity(view, "マキ")
    assert isinstance(result, Realized)
    assert result.clause_ids == tuple(clause.id for clause in view.clauses)
    assert {span.source for span in result.spans} == {"a", "b"}


def test_summary_preserves_document_order_and_keeps_unverified_merge_separate():
    view = document_view({"d": "マキは学生である。マキは研究者である。"})
    result = summarize_entity(view, "マキ")
    assert isinstance(result, RealizedGroup)
    assert result.text == "マキは学生である。マキは研究者である。"
    assert len(result.sentences) == 2
    assert all(s.checks["roundtrip"]["passed"] and s.checks["term_lineage"]["passed"]
               for s in result.sentences)
    assert "また" not in result.text


def test_summary_selects_exact_subject_only():
    view = document_view({"d": "マキは学生である。マキコは研究者である。"})
    result = summarize_entity(view, "マキ")
    assert isinstance(result, Realized)
    assert result.text == "マキは学生である。"


def test_summary_refuses_clause_spans_not_licensed_by_view_sources():
    base = document_view({"d": "マキは学生である。"})
    forged = View({"d": "別の文章。"}, base.clauses)
    result = summarize_entity(forged, "マキ")
    assert isinstance(result, Refused)
    assert result.reason == "INVALID_PROVENANCE"
    assert result.text is None


@pytest.mark.parametrize("text,entity", [
    ("青鍵について教えて", "青鍵"),
    ("青鍵をまとめて。", "青鍵"),
])
def test_summary_request_closed_patterns(text, entity):
    assert summary_entity_from_request(text) == entity


@pytest.mark.parametrize("text", ["青鍵を詳しく説明して", "青鍵は何？", "まとめて"])
def test_summary_request_rejects_other_shapes(text):
    assert summary_entity_from_request(text) is None


def test_unread_refusal_quotes_verbatim_source_offsets():
    source = "資料には未解釈の条件がある。"
    raw_span = {"source": "doc", "start": 4, "end": 9, "text": source[4:9]}
    result = {
        "verdict": "UNKNOWN_UNSUPPORTED_EVIDENCE", "reason": "source unread",
        "semantic": {"source_unread": [{"span": raw_span, "reason": "unread"}]},
    }
    refusal = realize_refusal(result)
    assert refusal.text == "UNKNOWN_UNSUPPORTED_EVIDENCE：「未解釈の条」。"
    assert refusal.spans[0].text == source[refusal.spans[0].start:refusal.spans[0].end]
    assert refusal.clause_ids == ("unread:doc:4:9",)


def test_conflict_refusal_quotes_both_conflicting_source_clauses():
    view = document_view({"d": "マキが本を読んだ。マキが本を読まなかった。"})
    result = {
        "verdict": "CONFLICT", "reason": "opposing evidence",
        "semantic": {"request": {"plans": [{"nodes": [{"pattern": {"predicate": "読む"}}]}]}},
    }
    refusal = realize_refusal(result, view)
    assert isinstance(refusal, Refused)
    assert refusal.text is not None and "CONFLICT" in refusal.text
    assert len(refusal.spans) == 2
    assert refusal.clause_ids == tuple(c.id for c in view.clauses)
    assert all(span.text == view.sources[span.source][span.start:span.end] for span in refusal.spans)


def test_refusal_without_any_source_blocker_emits_no_sentence():
    refusal = realize_refusal({"verdict": "UNKNOWN_NO_EVIDENCE", "reason": "none"})
    assert refusal.text is None
    assert not refusal.clause_ids and not refusal.spans


def test_refusal_clause_budget_is_typed():
    source = "x" * (MAX_CLAUSES + 1)
    unread = [{"span": {"source": "doc", "start": i, "end": i + 1, "text": "x"},
               "reason": "unread"} for i in range(MAX_CLAUSES + 1)]
    refusal = realize_refusal({"verdict": "UNKNOWN_UNREAD", "semantic": {"source_unread": unread}})
    assert refusal.reason == "BUDGET"
    assert refusal.text is None


def test_realize_answer_uses_only_verified_proof_clause():
    vera = Vera.from_texts({"doc": "青鍵は道具である。"}, mode="semantic")
    asked = vera.ask("青鍵は何？")
    assert asked["verdict"] == "ANSWER"
    answer = realize_answer(vera._semantic_view, asked)
    assert isinstance(answer, Realized)
    assert answer.text == "青鍵は道具である。"
    assert answer.clause_id == asked["sources"][0]["clause"]
    detached = realize_answer(None, asked)
    assert isinstance(detached, Realized) and detached.text == answer.text
    vera.close()


def test_role_wh_answer_realizes_the_licensing_clause():
    vera = Vera.from_texts({"doc": "マキがリオに青鍵を渡した。"}, mode="semantic")
    asked = vera.ask("誰がリオに青鍵を渡した？")
    assert asked["verdict"] == "ANSWER" and asked["values"] == ["マキ"]
    answer = realize_answer(vera._semantic_view, asked)
    assert isinstance(answer, Realized)
    assert answer.text == "マキはリオに青鍵を渡した。"
    assert answer.clause_id == asked["sources"][0]["clause"]
    vera.close()


def test_sum_answer_is_not_invented_as_comparative_or_measure_prose():
    result = {
        "verdict": "ANSWER", "text": "計算結果: 3m", "values": ["3m"],
        "semantic": {"verified": True, "plan": {"nodes": [{"op": "Sum"}]},
                     "proof": {"nodes": []}},
    }
    refused = realize_answer(None, result)
    assert isinstance(refused, Refused)
    assert refused.reason == "NOT_REALIZABLE"
    assert "計算結果: 3m" in refused.detail
    assert refused.text == "計算結果: 3m"


def test_say_keeps_ask_result_shape_and_returns_generated_provenance():
    vera = Vera.from_texts({"doc": "青鍵は道具である。"}, mode="semantic")
    before = vera.ask("青鍵は何？")
    said = vera.say("青鍵は何？")
    assert said["ask"] == before
    assert set(said) == {"verdict", "text", "generated", "provenance", "refusals", "ask"}
    assert said["generated"] is True
    assert said["verdict"] == "ANSWER"
    assert said["text"] == "青鍵は道具である。"
    assert said["provenance"] and not said["refusals"]
    vera.close()


def test_say_summary_uses_the_closed_entity_summary_path():
    vera = Vera.from_texts({"doc": "青鍵は道具である。"}, mode="semantic")
    said = vera.say("青鍵について教えて")
    assert said["verdict"] == "ANSWER"
    assert said["text"] == "青鍵は道具である。"
    assert said["generated"] is True and said["provenance"]
    assert said["ask"]["verdict"] == "UNKNOWN_UNREAD"
    vera.close()


def test_say_abstention_returns_typed_quoted_refusal_when_unread_exists():
    vera = Vera.from_texts({"doc": "青鍵は道具である。"}, mode="semantic")
    said = vera.say("青鍵について教えて")
    # Summary succeeds for this closed request; an ordinary unsupported query
    # instead follows ask's unread result and quotes that exact request span.
    refused = vera.say("青鍵について詳しく説明して")
    assert refused["ask"]["verdict"] != "ANSWER"
    assert refused["text"] is not None
    assert refused["refusals"]
    assert refused["provenance"]
    assert said["text"] is not None
    vera.close()


def test_literal_overlap_guard_has_only_closed_long_grammar_literals():
    module = Path(__file__).parents[1] / "verantyx" / "semantic_realize.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))
    allowed_long_cjk = {"ではありません"}
    cjk = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff]{7,}")
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.update(cjk.findall(node.value))
    assert found <= allowed_long_cjk
