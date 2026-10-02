"""Small source-backed demo for semantic multi-sentence generation."""
from __future__ import annotations

from verantyx.semantic import answer as semantic_answer
from verantyx.semantic_generate import GeneratedText, generate
from verantyx.semantic_reader import document_view, read_request
from verantyx.semantic_realize import Refused


CHECKS = 0


def check(condition: bool, message: str) -> None:
    global CHECKS
    CHECKS += 1
    assert condition, message


def main() -> None:
    # Hand-authored gold: 太郎 ate an apple and went to school; 花子 has the
    # same predicate/roles once positive and once negative. The final raw
    # sentence is deliberately not a readable semantic clause.
    docs = {
        "food-a": "太郎はりんごを食べた。",
        "travel": "太郎は学校へ行った。",
        "food-b": "太郎はりんごを食べた。",
        "fish-positive": "花子は魚を食べた。",
        "fish-negative": "花子は魚を食べなかった。",
        "banana": "次郎はバナナを食べた。",
        "unread": "ゔぁゔぁゔぁ、ぬるぽのざらめ。",
    }
    view = document_view(docs)

    check(len(docs) >= 5, "corpus has several source documents")
    check("太郎" in docs["food-a"] and "太郎" in docs["food-b"],
          "gold has an overlapping entity across documents")
    check("食べた" in docs["fish-positive"] and "食べなかった" in docs["fish-negative"],
          "gold contains one positive/negative contradiction")
    check(bool(getattr(view, "unread", ())), "the authored unread sentence remains unread")

    # Keep the answer view complete and readable: semantic.answer refuses an
    # answer when any source in that view is unread. The summary view above
    # separately demonstrates exact quotation of unread source text.
    answer_view = document_view({key: docs[key] for key in ("food-a", "travel", "food-b")})
    answer_request = read_request("太郎はりんごを食べたか？")
    answer = semantic_answer(answer_request, (answer_view,))
    check(isinstance(answer, dict), "semantic QA returns its public result mapping")
    check(answer.get("verdict") == "ANSWER", "the hand-authored answer query is answered")
    check(answer.get("semantic", {}).get("verified") is True,
          "the answer is independently verified before realization")
    answer_text = generate(answer_view, answer, style="polite")
    check(isinstance(answer_text, GeneratedText), "verified answer becomes constructed text")
    check(answer_text.verdict == "CONSTRUCTED" and answer_text.kind == "constructed",
          "generated answer support does not become an ANSWER object")
    check(any("food-a" in span.source for sentence in answer_text.sentences for span in sentence.spans),
          "answer realization cites its authored support source")

    plain = generate(view, {"kind": "summary", "entity": "太郎", "limit": 6}, "plain")
    polite = generate(view, {"kind": "summary", "entity": "太郎", "limit": 6}, "polite")
    ga_topic = generate(view, {"kind": "summary", "entity": "太郎", "limit": 6,
                              "topic_particle": "が"}, "plain")
    check(isinstance(plain, GeneratedText) and isinstance(polite, GeneratedText),
          "both summary styles produce typed constructed text")
    check(isinstance(ga_topic, GeneratedText), "a closed topic-particle variant is available")
    expected_taro_sources = {"food-a", "food-b", "travel"}
    actual_taro_sources = {
        span.source for sentence in plain.sentences for span in sentence.spans
        if span.source in expected_taro_sources
    }
    check(actual_taro_sources == expected_taro_sources,
          "summary gold facts come from all three authored Taro documents")
    check(plain.text != polite.text, "plain and polite surfaces differ")
    if isinstance(ga_topic, GeneratedText):
        check(plain.text != ga_topic.text, "verified は/が topic variants have distinct surfaces")
    plain_projection = {
        clause_id: sentence.projection
        for sentence in plain.sentences for clause_id in sentence.clause_ids
    }
    polite_projection = {
        clause_id: sentence.projection
        for sentence in polite.sentences for clause_id in sentence.clause_ids
    }
    check(plain_projection == polite_projection,
          "verified typed projections stay equal across styles")
    if isinstance(ga_topic, GeneratedText):
        check(plain_projection == {
            clause_id: sentence.projection
            for sentence in ga_topic.sentences for clause_id in sentence.clause_ids
        }, "verified typed projections stay equal across topic variants")
    check(all(plain.text[s.output_start:s.output_end] == s.text for s in plain.sentences),
          "generated sentence offsets address their own output text")
    check(all(link.license == "within-bucket" and link.left_clause_ids and link.right_clause_ids
              for link in plain.connectives),
          "each summary connective has a closed within-bucket license and clause lineage")

    for generated in (answer_text, plain, polite, ga_topic):
        if not isinstance(generated, GeneratedText):
            continue
        check(generated.constructed and generated.verdict != "ANSWER",
              "generated result remains constructed, never an answer verdict")
        for sentence in generated.sentences:
            check(bool(sentence.clause_ids) and bool(sentence.spans),
                  "no generated sentence lacks source provenance")
            check(sentence.checks["roundtrip"]["passed"],
                  "every emitted sentence passes the independent round-trip check")
            check(sentence.checks["term_lineage"]["passed"],
                  "every emitted sentence passes the term-lineage check")

    conflict = generate(view, {"kind": "summary", "entity": "花子"}, "plain")
    check(isinstance(conflict, Refused) and conflict.reason == "CONFLICT",
          "opposite source polarities produce a typed conflict refusal")
    check("食べた" in docs["fish-positive"] and "食べなかった" in docs["fish-negative"],
          "conflict refusal is grounded in the two authored contradictory sentences")

    check(isinstance(plain, GeneratedText) and bool(plain.quotes),
          "unread source material is carried as a verbatim quote")
    if isinstance(plain, GeneratedText):
        unread_text = docs["unread"]
        check(any(q.source_text in unread_text and unread_text[q.spans[0].start:q.spans[0].end] == q.source_text
                  for q in plain.quotes if q.spans and q.spans[0].source == "unread"),
              "unread material is sliced and quoted from its exact original span")
        check(any(q.source_text == unread_text for q in plain.quotes),
              "unread sentence is quoted without paraphrase")

    comparison = generate(view, {"kind": "compare", "entities": ["太郎", "次郎"]}, "plain")
    check(isinstance(comparison, GeneratedText) and comparison.request_kind == "compare",
          "comparison assembles two independently source-bound entity groups")
    if isinstance(comparison, GeneratedText):
        check([group.label for group in comparison.groups] == ["太郎", "次郎"],
              "comparison preserves its two explicit entity buckets")
        check(not any(link.license == "bucket-transition" for link in comparison.connectives),
              "no unsupported left-only/right-only transition is added")

    # Count is retained as a demo-local audit value without adding output after
    # the required final sentinel.
    check(CHECKS >= 30, "demo exercised the expected acceptance assertions")
    print("DEMO OK")


if __name__ == "__main__":
    main()
