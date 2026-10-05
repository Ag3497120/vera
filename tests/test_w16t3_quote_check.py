"""W16-t3 (K651, docs/FUSION.md §9): 引用の照合 `verantyx.quote_check.check`。LLM も読解器も使わない純粋な関数。No test is skipped."""
import json
from pathlib import Path

import pytest

from verantyx import answer as ANS
from verantyx import answer_slots as SLOTS
from verantyx import decode_grammar as G
from verantyx import quote_check as QC

D1 = "D1.txt"
D1_TEXT = ("備品の責任者は久保田澄江さんである。貸出は70日以内とする。\n"
           "会議は2026年4月1日の午前10時に開く。参加費は3,000円である。\n"
           "次の会議は日曜日に開く。\n"
           "ＡＢＣ商事の担当は三十人である。\n"
           "予備の行である。\n"
           "予備の行である。\n")
D2 = "D2.txt"
D2_TEXT = "備品の責任者は久保田澄子さんである。貸出は30日以内とする。\n予備の行である。\n"


@pytest.fixture
def records(tmp_path):
    a = Path(tmp_path) / D1
    b = Path(tmp_path) / D2
    a.write_text(D1_TEXT, encoding="utf-8")
    b.write_text(D2_TEXT, encoding="utf-8")
    return G.load_records([str(a), str(b)])


def q(source, line, text):
    return {"source": source, "line": line, "text": text}


def first(rec, answer, quotes):
    return QC.check(answer, quotes, rec)


# --- 引用の実在 ------------------------------------------------------------------------------------------------------------------------------

def test_exact_quote_in_the_named_line_is_anchored(records):
    r = first(records, "久保田澄江", [q(D1, 1, "備品の責任者は久保田澄江さんである。")])
    assert r.quotes[0]["found"] == "exact"
    assert r.verdict == "anchored"
    assert r.elements == [{"kind": "name", "value": "久保田澄江", "found_in": ["D1.txt:1"]}]
    assert r.to_dict().keys() == {"verdict", "quotes", "elements", "conflicts"}


def test_a_quote_spanning_two_sentences_of_one_line_is_found(records):
    r = first(records, "70日", [q(D1, 1, "久保田澄江さんである。貸出は70日以内とする。")])
    assert r.quotes[0]["found"] == "exact"


def test_wrong_line_number_is_relocated(records):
    r = first(records, "70日", [q(D1, 4, "貸出は70日以内とする。")])
    assert r.quotes[0]["found"] == "relocated"
    assert r.quotes[0]["relocated_to"] == ["D1.txt:1"]
    assert r.elements[0]["found_in"] == ["D1.txt:1"]
    assert r.verdict == "anchored"


def test_a_line_that_matches_in_two_places_keeps_both_and_picks_no_winner(records):
    r = first(records, "", [q(D1, 3, "予備の行である。")])
    assert r.quotes[0]["found"] == "relocated"
    assert set(r.quotes[0]["relocated_to"]) == {"D1.txt:5", "D1.txt:6", "D2.txt:2"}


def test_fabricated_quote_makes_unanchored_even_if_the_answer_is_in_the_record(records):
    r = first(records, "久保田澄江", [q(D1, 1, "備品の責任者は久保田澄江さんである。"), q(D1, 1, "どこにも無い文。")])
    assert [x["found"] for x in r.quotes] == ["exact", "fabricated"]
    assert r.verdict == "unanchored"


def test_empty_text_is_fabricated(records):
    assert first(records, "x", [q(D1, 1, "  ")]).quotes[0]["found"] == "fabricated"


def test_wrong_typed_quotes_are_kept_as_fabricated_with_a_typed_reason(records):
    bad = [q(D1, True, "貸出は70日以内とする。"), {"source": 3, "line": 1, "text": "x"}, "text only", {"source": D1, "line": 1, "text": None}, q(D1, "1", "x")]
    r = first(records, "", bad)
    assert len(r.quotes) == 5 and all(x["found"] == "fabricated" for x in r.quotes)
    assert r.reason == "BAD_QUOTE_TYPE" and r.verdict == "unanchored"
    json.dumps(r.to_dict())


def test_quotes_not_a_list_and_answer_not_a_string_are_typed(records):
    r = QC.check("x", {"a": 1}, records)
    assert r.verdict == "unanchored" and r.reason == "QUOTES_NOT_A_LIST" and r.quotes == []
    r = QC.check(["x"], [q(D1, 1, "貸出は70日以内とする。")], records)
    assert r.reason == "ANSWER_NOT_A_STRING" and r.verdict == "unanchored"    # 答えが読めない -> 錨ありにしない（型で残る）


def test_no_quotes_is_unanchored(records):
    r = first(records, "文書に記載がありません", [])
    assert r.verdict == "unanchored" and r.quotes == []


def test_source_is_matched_by_basename_and_nfkc(records):
    r = first(records, "", [q("docs/D1.txt", 1, "貸出は70日以内とする。")])
    assert r.quotes[0]["found"] == "exact"
    r = first(records, "", [q(D1, 4, "ＡＢＣ商事の担当は三十人である。")])        # 全角英字は NFKC で同じ
    assert r.quotes[0]["found"] == "exact"
    r = first(records, "", [q(D1, 4, "ABC商事の担当は三十人である。")])
    assert r.quotes[0]["found"] == "exact"


# --- 答えの要素 ------------------------------------------------------------------------------------------------------------------------------

def kinds(text):
    els, _ = QC.extract(text)
    return [(e["kind"], e["value"]) for e in els]


def test_numbers_and_dates_are_extracted_without_confusing_3_and_30():
    assert ("number", "3個") in kinds("3個ではなく")
    assert ("number", "30人") in kinds("30人が来た")
    assert ("number", "3人") not in kinds("30人が来た")
    assert ("number", "3000円") in kinds("参加費は3,000円")
    assert ("number", "3万円") in kinds("3万円")
    assert ("number", "300円") in kinds("三百円")
    assert ("number", "30人") in kinds("３０人")                        # 全角
    d = kinds("2026年4月1日の午前10時、日曜日")
    assert [("date", "2026年"), ("date", "4月"), ("date", "1日"), ("date", "午前10時"), ("date", "日曜日")] == d


def test_relative_words_are_not_dates():
    assert kinds("明日と来週と翌日と前日") == []


def test_names_are_proper_nouns_katakana_and_honorific_runs():
    assert ("name", "久保田澄江") in kinds("責任者は久保田澄江です")
    assert ("name", "トヨタ") in kinds("トヨタが来た")
    assert ("name", "田中") in kinds("田中さんが来た")
    assert kinds("文書に記載がありません") == []


def test_unreadable_kanji_numerals_are_counted_as_skipped_not_dropped():
    els, sk = QC.extract("十十人")
    assert sk >= 1 and all(e["value"] != "十十人" for e in els)


def test_the_unit_list_is_the_existing_one():
    assert QC._NUM == ANS._NUMBER
    assert SLOTS._VALUE.pattern == QC._NUM + r"\s*" + QC._UNIT_PAT


# --- 照合・食い違い・印 ----------------------------------------------------------------------------------------------------------------------

def test_wrong_name_with_the_real_quote_is_a_conflict_with_both_values(records):
    r = first(records, "久保田澄子", [q(D1, 1, "備品の責任者は久保田澄江さんである。")])
    assert r.verdict == "conflict"
    c = r.conflicts[0]
    assert c["answer_value"] == "久保田澄子" and {"value": "久保田澄江", "source": "D1.txt", "line": 1} in c["values"]
    assert r.elements[0]["found_in"] is None


def test_tagger_down_is_typed_and_never_anchored(records, monkeypatch):
    from verantyx import typed_edges

    def boom():
        raise RuntimeError("tagger down")
    ok = first(records, "久保田澄子", [q(D1, 1, "備品の責任者は久保田澄江さんである。")])
    assert ok.verdict == "conflict" and ok.reason is None                      # 動いているときは従来どおり
    monkeypatch.setattr(typed_edges, "_tagger", boom)
    r = first(records, "久保田澄子", [q(D1, 1, "備品の責任者は久保田澄江さんである。")])
    assert r.verdict == "unanchored" and r.reason == "NAME_TAGGER_UNAVAILABLE"
    assert r.verdict != "anchored"


def test_wrong_number_with_the_real_quote_is_a_conflict(records):
    r = first(records, "30日", [q(D1, 1, "貸出は70日以内とする。")])
    assert r.verdict == "conflict"
    assert {"value": "70日", "source": "D1.txt", "line": 1} in r.conflicts[0]["values"]


def test_element_missing_from_quotes_without_a_same_kind_value_is_unanchored(records):
    r = first(records, "久保田澄江", [q(D1, 3, "次の会議は日曜日に開く。")])
    assert r.verdict == "unanchored" and r.conflicts == []


def test_two_documents_with_different_values_conflict_whatever_the_answer_says(records):
    r = first(records, "70日", [q(D1, 1, "貸出は70日以内とする。"), q(D2, 1, "貸出は30日以内とする。")])
    assert r.verdict == "conflict"
    kinds_ = [c for c in r.conflicts if c["answer_value"] is None]
    assert kinds_ and {v["source"] for v in kinds_[0]["values"]} == {"D1.txt", "D2.txt"}


def test_two_documents_with_the_same_values_do_not_conflict(records):
    r = first(records, "", [q(D1, 5, "予備の行である。"), q(D2, 2, "予備の行である。")])
    assert r.conflicts == []


def test_verdict_order_unanchored_before_conflict_before_missing_element(records):
    fab = q(D1, 1, "無い文です。")
    ok = q(D1, 1, "備品の責任者は久保田澄江さんである。")
    assert first(records, "久保田澄子", [ok, fab]).verdict == "unanchored"      # 捏造があれば衝突より先
    assert first(records, "久保田澄子", [ok]).verdict == "conflict"
    assert first(records, "久保田澄江と70日", [ok]).verdict == "unanchored"
    assert first(records, "久保田澄江", [ok]).verdict == "anchored"


def test_no_elements_with_a_real_quote_is_not_anchored(records):
    """旧い期待: anchored（第 1 ラウンド。要素が無ければ確かめる物が無いので錨あり）。
    監査役の裁定 第 5 ラウンド 3 で改めた: 要素も確かめる内容語も無い答えは「確かめた」と言えないので unanchored（NO_CONTENT_TO_CHECK）。"""
    r = first(records, "そうです", [q(D1, 5, "予備の行である。")])
    assert r.elements == [] and r.verdict == "unanchored" and r.reason == "NO_CONTENT_TO_CHECK"


def test_year_month_day_components_are_matched_one_by_one(records):
    r = first(records, "4月1日", [q(D1, 2, "会議は2026年4月1日の午前10時に開く。")])
    assert r.verdict == "anchored"
    r = first(records, "5月1日", [q(D1, 2, "会議は2026年4月1日の午前10時に開く。")])
    assert r.verdict == "conflict"


def test_check_does_not_use_a_reader_or_a_llm():
    src = Path(QC.__file__).read_text(encoding="utf-8")
    assert "semantic_read" not in src and "llm_backend" not in src and "_ollama" not in src
