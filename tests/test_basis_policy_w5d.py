"""W5-d (docs/BASIS_POLICY.md, W5-d): the two bindings of the basis policy.

A1  a ``family == "document"`` source is a human source only when its text is really in a document the caller handed over
    (``--document`` being non-empty proves nothing: the product reads the documents the way ``one.Vera.load_documents`` does and looks in them).
D1  a recorded "yes" lifts a generated answer only when the sentence now generated is, as a string and without any normalisation, the sentence that was
    confirmed; contradicting confirmations abstain before that comparison is made.
"""
import hashlib
import json

import pytest

from verantyx import basis_policy as bp
from verantyx import sovereign as sov

QUERY = "内容は何ですか？"


@pytest.fixture(autouse=True)
def _no_outside_environment(monkeypatch):
    for name in ("VERA_SOVEREIGN_ROOT", "VERA_SOVEREIGN_STORE", "VERA_P4_INDEX"):
        monkeypatch.delenv(name, raising=False)


# ------------------------------------------------------------------------------------------------ A1
BODY = "第一条 窓は午後に閉める。\n第二条 ＡＢＣ会議は月曜に開く。\n"
OTHER = "別の文書の本文。担当者は火曜に来る。\n"


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def _doc_answer(sources, text="答え。"):
    return {"kind": "answer", "verdict": "ANSWER", "text": text, "sources": sources, "evidence": [s.get("text", "") for s in sources], "door": "t"}


def _ask_docs(sources, documents):
    return bp.apply_to_ask(_doc_answer(sources), bp.AskPolicy(), query=QUERY, mode="round5", documents=documents)


def _basis(out):
    return out["basis_policy"]["basis_original"], out["basis_policy"]["outcome"]


def test_a1_a_sentence_that_is_in_the_handed_over_document_stays_human(tmp_path):
    doc = _write(tmp_path, "memo.txt", BODY)
    out, rc = _ask_docs([{"family": "document", "source": "memo.txt", "text": "窓は午後に閉める。"}], [doc])
    assert rc == 0 and _basis(out)[0] == "HUMAN" and out["basis_policy"]["outcome"].startswith("ANSWER")
    assert out["basis_policy"]["counts"]["unknown_origin"] == 0 and out["verdict"] == "ANSWER"


def test_a1_a_sentence_that_is_not_in_the_document_is_unknown_origin(tmp_path):
    doc = _write(tmp_path, "memo.txt", BODY)
    out, _ = _ask_docs([{"family": "document", "source": "memo.txt", "text": "渡された文書に無い文。"}], [doc])
    assert _basis(out) == ("UNKNOWN_ORIGIN", "ABSTAIN")
    assert out["verdict"] == "UNKNOWN_ORIGIN_SOURCE" and out["basis_policy"]["counts"]["unknown_origin"] == 1


def test_a1_a_document_that_does_not_exist_gives_no_body_and_nothing_is_found(tmp_path):
    out, _ = _ask_docs([{"family": "document", "source": "memo.txt", "text": "窓は午後に閉める。"}], [str(tmp_path / "nowhere.txt")])
    assert _basis(out) == ("UNKNOWN_ORIGIN", "ABSTAIN")


def test_a1_nfkc_difference_alone_does_not_hide_a_sentence_that_is_there(tmp_path):
    doc = _write(tmp_path, "memo.txt", BODY)                                 # the document has the full-width ＡＢＣ
    out, _ = _ask_docs([{"family": "document", "source": "memo.txt", "text": "ABC会議は月曜に開く。"}], [doc])
    assert _basis(out)[0] == "HUMAN"
    doc2 = _write(tmp_path, "memo2.txt", "ABC meeting is on Monday.\n")
    out, _ = _ask_docs([{"family": "document", "source": "memo2.txt", "text": "ＡＢＣ meeting is on Monday."}], [doc2])
    assert _basis(out)[0] == "HUMAN"


def test_a1_a_directory_of_documents_is_read_like_one_py_does(tmp_path):
    d = tmp_path / "docs"
    (d / "sub").mkdir(parents=True)
    (d / "a.txt").write_text(OTHER, encoding="utf-8")
    (d / "sub" / "b.txt").write_text(BODY, encoding="utf-8")
    out, _ = _ask_docs([{"family": "document", "source": "b.txt", "text": "窓は午後に閉める。"}], [str(d)])
    assert _basis(out)[0] == "HUMAN"
    out, _ = _ask_docs([{"family": "document", "source": "b.txt", "text": "どこにも無い文。"}], [str(d)])
    assert _basis(out)[0] == "UNKNOWN_ORIGIN"


def test_a1_the_sentence_may_be_in_any_of_several_documents(tmp_path):
    a, b = _write(tmp_path, "a.txt", OTHER), _write(tmp_path, "b.txt", BODY)
    out, _ = _ask_docs([{"family": "document", "source": "b.txt", "text": "窓は午後に閉める。"}], [a, b])
    assert _basis(out)[0] == "HUMAN"


def test_a1_a_source_with_only_a_sha256_is_checked_against_the_documents(tmp_path):
    doc = _write(tmp_path, "memo.txt", BODY)
    good = hashlib.sha256(BODY.encode("utf-8")).hexdigest()
    out, _ = _ask_docs([{"family": "document", "source": "memo.txt", "sha256": good}], [doc])
    assert _basis(out)[0] == "HUMAN"
    out, _ = _ask_docs([{"family": "document", "source": "memo.txt", "sha256": "0" * 64}], [doc])
    assert _basis(out) == ("UNKNOWN_ORIGIN", "ABSTAIN")
    out, _ = _ask_docs([{"family": "document", "source": "memo.txt"}], [doc])         # neither text nor sha256: nothing to check
    assert _basis(out) == ("UNKNOWN_ORIGIN", "ABSTAIN")


@pytest.mark.parametrize("text", ["", "   ", None, 5, ["窓は午後に閉める。"]])
def test_a1_an_empty_or_non_string_text_is_not_found_even_if_a_hash_would_match(tmp_path, text):
    doc = _write(tmp_path, "memo.txt", BODY)
    out, _ = _ask_docs([{"family": "document", "source": "memo.txt", "text": text, "sha256": hashlib.sha256(BODY.encode("utf-8")).hexdigest()}], [doc])
    assert _basis(out) == ("UNKNOWN_ORIGIN", "ABSTAIN")


def test_a1_a_generated_sentence_next_to_a_checked_document_sentence_stays_mixed(tmp_path):
    doc = _write(tmp_path, "memo.txt", BODY)
    gen = {"family": "local", "source": "local:f:1", "origin": "generated", "text": "生成された文。"}
    out, _ = _ask_docs([{"family": "document", "source": "memo.txt", "text": "窓は午後に閉める。"}, gen], [doc])
    assert out["basis_policy"]["basis_original"] == "MIXED"
    out, _ = _ask_docs([{"family": "document", "source": "memo.txt", "text": "文書に無い文。"}, gen], [doc])
    assert out["basis_policy"]["basis_original"] == "UNKNOWN_ORIGIN"


def test_a1_the_older_contract_without_the_bodies_is_unchanged_for_a_direct_caller():
    src = {"family": "document", "source": "memo.txt", "text": "どこにも無い"}
    assert bp.classify_sources([src], user_documents=True).counts["human"] == 1                    # the caller says he checked: kept (known hole)
    assert bp.classify_sources([src], user_documents=True, document_texts=["別の本文"]).unknown_origin == 1
    assert bp.classify_sources([src], user_documents=True, document_texts=["どこにも無い文"]).counts["human"] == 1
    assert bp.classify_sources([src]).unknown_origin == 1                                          # no documents handed over: unknown


def test_a1_a_sentence_across_a_line_break_is_not_found_a_loss_on_the_safe_side(tmp_path):
    doc = _write(tmp_path, "memo.txt", "窓は午後に\n閉める。\n")
    out, _ = _ask_docs([{"family": "document", "source": "memo.txt", "text": "窓は午後に閉める。"}], [doc])
    assert _basis(out) == ("UNKNOWN_ORIGIN", "ABSTAIN")                                              # known hole: documented


# ------------------------------------------------------------------------------------------------ D1
def _store(tmp_path, monkeypatch):
    root = str(tmp_path / "sov")
    assert sov.create(root, "s1", "owner", consent_promote=True)["verdict"] == "CREATED"
    monkeypatch.setenv("VERA_SOVEREIGN_ROOT", root)
    monkeypatch.setenv("VERA_SOVEREIGN_STORE", "s1")
    return root


def _result(claim):
    gen = {"family": "local", "source": "local:new:1", "source_file": "new.jsonl", "line": 1, "sha": "new", "origin": "generated", "text": claim}
    return {"kind": "answer", "verdict": "ANSWER", "text": claim, "sources": [gen], "evidence": [claim], "door": "t"}


def _confirm(claim):
    """The normal flow: ask (a human is present) -> --confirm ID yes."""
    q, rc = bp.apply_to_ask(_result(claim), bp.AskPolicy(human_present=True), query=QUERY, mode="legacy", documents=[])
    assert rc == 0 and q["verdict"] == "CONFIRM_REQUEST"
    got, rc = bp.apply_to_ask(_result(claim), bp.AskPolicy(confirm=(q["confirm"]["id"], "yes")), query=QUERY, mode="legacy", documents=[])
    assert rc == 0 and got["verdict"] == "CONFIRMED_HUMAN_RECORD" and got["wrote"] == 1


def _ask(claim, **policy):
    return bp.apply_to_ask(_result(claim), bp.AskPolicy(**policy), query=QUERY, mode="legacy", documents=[])[0]


CONFIRMED = "窓が光った。"
VARIANTS = {"half-width space": "窓が 光った。", "ideographic space": "窓が　光った。", "nbsp": "窓が 光った。", "trailing space": "窓が光った。 ",
            "trailing newline": "窓が光った。\n", "punctuation": "窓が光った!", "no stop": "窓が光った", "nfkc": "コードはＡＢＣです。"}


@pytest.mark.parametrize("name", sorted(VARIANTS))
def test_d1_a_yes_for_another_wording_does_not_lift_the_answer(tmp_path, monkeypatch, name):
    _store(tmp_path, monkeypatch)
    confirmed = "コードはABCです。" if name == "nfkc" else CONFIRMED
    _confirm(confirmed)
    out = _ask(VARIANTS[name])
    assert out["basis_policy"]["outcome"] == "ABSTAIN" and out["kind"] == "unknown" and out["verdict"] == "UNKNOWN_GENERATED_BASIS_ONLY"
    sv = out["basis_policy"]["sovereign"]
    assert sv["confirmed_records_claim_differs"] == 1 and sv["confirmed_records_not_used"] == 1 and sv["confirmed_records_used"] == 0
    assert out["basis_policy"]["basis"] == "GENERATED" and out["basis_policy"]["basis_original"] == "GENERATED"
    assert "text" in out and out["text"] != VARIANTS[name]                                           # the old sentence is not answered


def test_d1_with_a_human_present_a_different_wording_is_asked_again(tmp_path, monkeypatch):
    _store(tmp_path, monkeypatch)
    _confirm(CONFIRMED)
    out = _ask("窓が 光った。", human_present=True)
    assert out["verdict"] == "CONFIRM_REQUEST" and out["confirm"]["claim"] == "窓が 光った。"


def test_d1_the_same_sentence_is_answered_from_the_record(tmp_path, monkeypatch):
    _store(tmp_path, monkeypatch)
    _confirm(CONFIRMED)
    out = _ask(CONFIRMED)
    assert out["verdict"] == "ANSWER" and out["text"] == CONFIRMED and out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"
    assert out["basis_policy"]["sovereign"]["confirmed_records_used"] == 1
    assert "confirmed_records_claim_differs" not in out["basis_policy"]["sovereign"]                 # the key only appears when it applies


def test_d1_contradicting_confirmations_abstain_even_when_one_equals_the_present_sentence(tmp_path, monkeypatch):
    root = _store(tmp_path, monkeypatch)

    def payload(cid, claim):
        return {"record": "basis_confirmation", "status": "HUMAN_CONFIRMED", "witness": "user_confirmation", "confirm_id": cid, "query": QUERY,
                "claim": claim, "origin": "human_confirmed", "generated_sources": [{"family": "local", "source_id": "local:f:1", "sha": "h0"}], "table_version": 1}
    sov.append_basis_confirmation(root, "s1", payload("aaa", CONFIRMED))
    sov.append_basis_confirmation(root, "s1", payload("bbb", "窓が割れた。"))
    out = _ask(CONFIRMED, human_present=True)                                                           # the present sentence equals the first record
    assert out["verdict"] == "AMBIGUOUS_CONFIRMED_RECORDS" and out["basis_policy"]["outcome"] == "ABSTAIN"
    assert out["basis_policy"]["sovereign"]["ambiguous"] is True
    assert "confirmed_records_claim_differs" not in out["basis_policy"]["sovereign"]


def test_d1_two_records_of_the_same_sentence_that_is_not_the_present_one_do_not_lift(tmp_path, monkeypatch):
    root = _store(tmp_path, monkeypatch)
    for cid in ("aaa", "bbb"):
        sov.append_basis_confirmation(root, "s1", {"record": "basis_confirmation", "status": "HUMAN_CONFIRMED", "witness": "user_confirmation", "confirm_id": cid,
                                                   "query": QUERY, "claim": CONFIRMED, "origin": "human_confirmed",
                                                   "generated_sources": [{"family": "local", "source_id": "local:f:1", "sha": "h0"}], "table_version": 1})
    out = _ask("窓が光った！")
    sv = out["basis_policy"]["sovereign"]
    assert out["basis_policy"]["outcome"] == "ABSTAIN" and sv["confirmed_records_claim_differs"] == 2 and sv["confirmed_records_not_used"] == 2


def test_d1_no_variant_produces_an_answer_basis(tmp_path, monkeypatch):
    _store(tmp_path, monkeypatch)
    _confirm(CONFIRMED)
    for name, claim in sorted(VARIANTS.items()):
        if name == "nfkc": continue
        out = _ask(claim)
        assert not out["basis_policy"]["outcome"].startswith("ANSWER"), name
        out = json.loads(json.dumps(out))
        assert out.get("verdict") != "ANSWER", name
