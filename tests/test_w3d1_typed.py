"""W3-d1 (K312, K314, K315): a typed cross (a reader clause dict with role_basis / predicate_basis, or an EventCross) is realized, and the sentence is read
again with the SAME placement. The placement r9 is read only; without it the tests skip (ENV_MISSING)."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from verantyx import event_cross, observe, semantic_read
from verantyx import semantic_realize as SR
from verantyx.semantic_reader import document_view

R9 = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2"


@pytest.fixture
def r9(monkeypatch):
    if not Path(R9).exists():
        pytest.skip("ENV_MISSING[coarse placement r9/run2 (wt/W3-a6-S)]")
    monkeypatch.delenv("VERA_PLACEMENT", raising=False)
    monkeypatch.delenv("VERA_REALIZE_FORMS", raising=False)
    return R9


def read(text, placement=R9):
    return semantic_read.read(text, "ja", placement=placement)


def clause_of(text):
    out = read(text)
    assert len(out["clauses"]) == 1
    return dict(out["clauses"][0], rule=out["clause_meta"][0]["rule"])     # the caller passes the reader rule (M1): a dict without one is not realized


def test_a_typed_clause_is_realized_and_the_topic_attempts_are_kept(r9):
    d = clause_of("母が駅へ歩いた。")
    assert d.get("role_basis")                                      # it was read with the placement
    r = SR.realize_clause(d, "plain", placement=R9)
    assert isinstance(r, SR.Realized) and r.text == "母が駅へ歩いた。" and r.derivation == "typed-cross"
    attempts = r.checks["topic_attempts"]
    assert [a["topic"] for a in attempts] == ["は", "が"]
    assert attempts[0]["passed"] is False and attempts[0]["text"] == "母は駅へ歩いた。" and attempts[0]["reason"].startswith("REREAD_MISMATCH:")
    assert attempts[1]["passed"] is True
    assert r.checks["reread"]["passed"] and r.checks["term_lineage"]["passed"]
    # the sentence that was emitted is the one that was checked (not a rewrite of the failed は sentence)
    again = read(r.text)
    assert again["clauses"][0]["roles"] == d["roles"] and again["clauses"][0]["predicate"] == d["predicate"]


def test_the_failed_topic_sentence_really_is_not_read_the_same(r9):
    assert read("母は駅へ歩いた。")["clauses"] == [] or SR._reread_check("母は駅へ歩いた。", {"predicate": "歩く", "polarity": "+", "tense": "past", "voice": "active", "modality": None},
                                                                   {"agent": {"fillers": [{"surface": "母"}]}, "goal": {"fillers": [{"surface": "駅"}]}}, R9)["passed"] is False


def test_the_same_dict_without_a_placement_is_refused_as_needing_one(r9, monkeypatch):
    d = clause_of("母が駅へ歩いた。")
    r = SR.realize_clause(d, "plain")
    assert isinstance(r, SR.Refused) and r.reason == "ROUNDTRIP_MISMATCH" and r.detail == "REREAD_MISMATCH:NEEDS_PLACEMENT"
    monkeypatch.setenv("VERA_PLACEMENT", R9)                        # the variable is not read on this path
    r = SR.realize_clause(d, "plain")
    assert isinstance(r, SR.Refused) and r.detail == "REREAD_MISMATCH:NEEDS_PLACEMENT"


def test_the_placement_information_does_not_change_the_sentence(r9):
    d = clause_of("母が駅へ歩いた。")
    bare = {k: v for k, v in d.items() if k not in ("role_basis", "predicate_basis", "role_flags")}
    a, b = SR.realize_clause(d, "plain", placement=R9), SR.realize_clause(bare, "plain", placement=R9)
    assert isinstance(a, SR.Realized) and isinstance(b, SR.Realized) and a.text == b.text and a.clause_id == b.clause_id


def test_without_a_placement_only_the_first_topic_is_tried_as_before(r9):
    d = {"predicate": "渡す", "roles": {"agent": "太郎", "recipient": "花子", "patient": "本"}, "polarity": "+", "tense": "past", "modality": None, "voice": "active", "rule": "frame"}
    r = SR.realize_clause(d, "plain")                                # a dict without a basis: the unplaced reread of the は sentence agrees
    assert isinstance(r, SR.Realized) and r.text == "太郎は花子に本を渡した。" and [a["topic"] for a in r.checks["topic_attempts"]] == ["は"]
    one = {"predicate": "走る", "roles": {"agent": "犬"}, "polarity": "+", "tense": "past", "modality": None, "voice": "active", "rule": "frame"}
    r = SR.realize_clause(one, "plain")                              # the unplaced reader abstains on 犬は走った。: no fall back to が without a placement (K313)
    assert isinstance(r, SR.Refused) and r.reason == "ROUNDTRIP_MISMATCH" and [a["topic"] for a in r.checks["topic_attempts"]] == ["は"]


def test_an_event_cross_is_accepted_and_its_cell_key_is_the_id(r9):
    out = read("弟がこの工場で働いた。")
    got = event_cross.build_crosses(out, event_cross.default_lookup(R9))
    assert got.status == "CROSSED" and len(got.crosses) == 1
    cross = got.crosses[0]
    r = SR.realize_clause(cross, "plain", placement=R9)
    assert isinstance(r, SR.Realized) and r.clause_id == observe.cell_key_of(cross)
    d = SR.realize_clause(dict(out["clauses"][0], rule=out["clause_meta"][0]["rule"]), "plain", placement=R9)
    assert isinstance(d, SR.Realized) and d.clause_id == r.clause_id and d.text == r.text
    assert isinstance(SR.realize_clause(cross, "plain"), SR.Refused)                  # typed by a placement, no placement given


def test_a_reread_that_differs_is_refused_with_the_difference(r9, monkeypatch):
    d = clause_of("兄が弟に本を渡した。")
    swapped = "弟が兄に本を渡した。"
    checks = SR.verify_sentence(d, swapped, placement=R9)
    assert checks["status"].startswith("REFUSED:REREAD_MISMATCH:roles:") and "-agent=兄" in checks["status"] and "+agent=弟" in checks["status"]
    nonpast = SR.verify_sentence(d, "兄が弟に本を渡す。", placement=R9)
    assert nonpast["status"] == "REFUSED:REREAD_MISMATCH:tense:past->nonpast"
    ok = SR.verify_sentence(d, "兄が弟に本を渡した。", placement=R9)
    assert ok["status"] == "REALIZED" and ok["reread"]["passed"]
    unread = SR.verify_sentence(d, "兄は弟に本を渡した。が", placement=R9)
    assert unread["status"].startswith("REFUSED:REREAD_MISMATCH:") and unread["reread"]["passed"] is False
    # the product path: a surface that reads back as another cross is a ROUNDTRIP_MISMATCH, whatever made it
    monkeypatch.setattr(SR, "_surface_text", lambda clause, style, **kw: (swapped, ""))
    r = SR.realize_clause(d, "plain", placement=R9)
    assert isinstance(r, SR.Refused) and r.reason == "ROUNDTRIP_MISMATCH" and r.detail.startswith("REREAD_MISMATCH:roles:")
    assert [a["topic"] for a in r.checks["topic_attempts"]] == ["は", "が"] and all(a["passed"] is False for a in r.checks["topic_attempts"])


def test_the_difference_text_is_deterministic(r9):
    d = clause_of("兄が弟に本を渡した。")
    first = SR.verify_sentence(d, "弟が兄に本を渡した。", placement=R9)["status"]
    assert all(SR.verify_sentence(d, "弟が兄に本を渡した。", placement=R9)["status"] == first for _ in range(3))
    assert SR._facts_diff(SR._cross_facts({"predicate": "渡す", "polarity": "+", "tense": "past"}, {"agent": {"fillers": [{"surface": "兄"}]}}),
                          SR._cross_facts({"predicate": "渡す", "polarity": "-", "tense": "past"}, {"agent": {"fillers": [{"surface": "兄"}]}})) == "polarity:+->-"


def test_fullwidth_forms_are_compared_after_nfkc():
    facts = SR._cross_facts({"predicate": "買う"}, {"patient": {"fillers": [{"surface": "ＡＢＣ"}]}})
    assert facts["roles"]["patient"] == ("ABC",)


def test_verify_sentence_without_a_placement_is_the_original_pair_of_checks():
    view = document_view({"doc": "マキがリオに青鍵を渡した。"})
    clause = view.clauses[0]
    sentence = "マキはリオに青鍵を渡した。"
    got = SR.verify_sentence(clause, sentence)
    assert got == {"roundtrip": SR.check_round_trip(clause, sentence), "term_lineage": SR.check_term_lineage(clause, sentence)}
    assert set(got) == {"roundtrip", "term_lineage"}


def test_a_source_clause_with_a_placement_gets_the_reread_too(r9):
    view = document_view({"doc": "太郎が花子に本を渡した。"})
    clause = view.clauses[0]
    got = SR.verify_sentence(clause, "太郎は花子に本を渡した。", placement=R9)
    assert set(got) == {"roundtrip", "term_lineage", "reread", "status"} and got["status"] == "REALIZED"
    r = SR.realize_clause(clause, "plain", placement=R9)
    assert isinstance(r, SR.Realized) and r.derivation == "inverse-reader" and r.text == "太郎は花子に本を渡した。"
    assert [a["topic"] for a in r.checks["topic_attempts"]] == ["は"] and r.checks["status"] == "REALIZED"
    swapped = SR.verify_sentence(clause, "花子は太郎に本を渡した。", placement=R9)
    assert swapped["status"].startswith("REFUSED:REREAD_MISMATCH:roles:") and swapped["roundtrip"]["passed"] is False
    copula = document_view({"doc": "青鍵は道具である。"}).clauses[0]
    c = SR.verify_sentence(copula, "青鍵は道具である。", placement=R9)
    assert c["status"] == "REFUSED:REREAD_MISMATCH:RULE_NOT_FRAME"


def test_what_the_realizer_cannot_say_stays_a_typed_refusal(r9):
    d = clause_of("兄が休日、手紙を書いた。")
    r = SR.realize_clause(d, "plain", placement=R9)
    assert isinstance(r, SR.Refused) and r.reason == "ROLE_NOT_REALIZABLE"
    bad = dict(clause_of("母が駅へ歩いた。"), surprise=1)
    assert SR.realize_clause(bad, "plain", placement=R9).reason == "ROLE_NOT_REALIZABLE"
    coll = copy.deepcopy(clause_of("母が駅へ歩いた。"))
    coll["roles"]["goal"] = ["駅", "港"]
    assert SR.realize_clause(coll, "plain", placement=R9).reason == "ROLE_NOT_REALIZABLE"
    assert SR.realize_clause("not a clause", "plain").reason == "INVALID_PROVENANCE"


def test_realize_observed_without_a_placement_reads_the_way_it_always_did(monkeypatch):
    seen = []
    real = semantic_read.read

    def spy(*args, **kwargs):
        seen.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(semantic_read, "read", spy)
    center = {"predicate": "走る", "polarity": "+", "tense": "past", "modality": None, "voice": "active"}
    arms = {"agent": {"kind": "FILLER", "fillers": [{"surface": "犬"}]}}
    SR.realize_observed(center, arms, "ja", cell_id="c1", rule="frame")
    assert seen and all(kwargs == {} and args[1:] == ("ja",) for args, kwargs in seen)


def test_the_polite_style_of_a_typed_cross_is_never_emitted_unless_it_reads_back(r9):
    d = clause_of("母が駅へ歩いた。")
    r = SR.realize_clause(d, "polite", placement=R9)
    if isinstance(r, SR.Realized):
        assert read(r.text)["clauses"][0]["roles"] == d["roles"] and read(r.text)["clauses"][0]["predicate"] == d["predicate"]
    else:
        assert r.reason in ("ROUNDTRIP_MISMATCH", "TERM_LINEAGE_MISMATCH")


def test_a_clause_of_another_rule_or_without_a_rule_is_not_realized_on_any_path(r9):
    """M1: the dict path and the EventCross path refuse what the frame rule does not cover, and a missing rule is a refusal."""
    import dataclasses

    out = read("先生は作文を直さなくはない。")
    d = out["clauses"][0]
    assert out["clause_meta"][0]["rule"] == "gold_double_neg"
    with_rule = dict(d, rule="gold_double_neg")
    assert SR.realize_clause(with_rule, "plain", placement=R9).reason == "UNSUPPORTED_RULE"
    assert SR.realize_clause(d, "plain", placement=R9).reason == "UNSUPPORTED_RULE"                 # no rule given
    assert "no reader rule" in SR.realize_clause(d, "plain", placement=R9).detail
    cross = event_cross.build_crosses(out, event_cross.default_lookup(R9)).crosses[0]
    assert cross.provenance.get("rule") == "gold_double_neg"
    assert SR.realize_clause(cross, "plain", placement=R9).reason == "UNSUPPORTED_RULE"
    bare = dataclasses.replace(cross, provenance={k: v for k, v in cross.provenance.items() if k != "rule"})
    assert SR.realize_clause(bare, "plain", placement=R9).reason == "UNSUPPORTED_RULE"
    assert SR.verify_sentence(with_rule, "先生は作文を直す。", placement=R9)["status"] == "REFUSED:REREAD_MISMATCH:RULE_NOT_FRAME"
    assert SR.verify_sentence(d, "先生は作文を直す。", placement=R9)["status"] == "REFUSED:REREAD_MISMATCH:RULE_UNKNOWN"
    ok = clause_of("母が駅へ歩いた。")                                                              # a frame dict with its rule is realized as before
    assert isinstance(SR.realize_clause(ok, "plain", placement=R9), SR.Realized)
    assert SR.verify_sentence(ok, "母が駅へ歩いた。", placement=R9)["status"] == "REALIZED"
