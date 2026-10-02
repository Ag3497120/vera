"""Independent library safety regressions, not a capability evaluation set."""
import json

import pytest

from verantyx.family_library import FamilyLibrary, _record_variants
from verantyx.question import read
from verantyx.round3 import GeneralRouter, route


def scene(sha="sample", **fields):
    return {"family": "paraphrase_entail", "split": "train", "source": "synthetic:scope-regression",
            "sha": sha, "kind": "who_did_what", "sentence": "ナオが午前九時に窓を開けた。",
            "question": "誰が窓を開けた？", "answer": "ナオ", **fields}


def build(tmp_path, rows):
    corpus = tmp_path / "corpus"
    path = corpus / "codex" / "paraphrase_entail" / "from_pro" / "records_test.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    target = tmp_path / "index" / "paraphrase_entail"
    info = FamilyLibrary.build(corpus, "paraphrase_entail", target)
    return FamilyLibrary(target, "paraphrase_entail"), info


@pytest.mark.parametrize("question, expected", [
    ("誰が窓を開けた？", "who"),
    ("ナオは誰から青鍵を受け取った？", "who"),
    ("ナオは何を受け取った？", "what"),
    ("ナオはいつ窓を開けた？", "when"),
    ("ナオは何時に窓を開けた？", "when"),
    ("ナオはどこで窓を開けた？", "where"),
    ("ナオはなぜ窓を開けた？", "why"),
    ("ナオは何のために窓を開けた？", "why"),
    ("ナオは窓を何枚開けた？", "how many"),
    ("ナオは代金を何円払った？", "how much"),
])
def test_original_question_types_its_own_slot(question, expected):
    row = scene(question=question)
    variants, answer, slot = _record_variants("paraphrase_entail", row)
    assert variants == [question] and answer == row["answer"] and slot == expected


@pytest.mark.parametrize("question", [
    "誰が何を受け取った？", "誰が誰に青鍵を渡した？", "ナオはいつどこで窓を開けた？",
    "ナオは何を受け取り、何を返した？", "ナオはどうやって窓を開けた？",
    "ナオはどのように窓を開けた？", "ナオは何日休んだ？", "ナオについて教えて。",
    "誰かが窓を開けた。", "窓を開けた？",
])
def test_unrepresented_questions_do_not_become_who_or_default_what(question):
    assert _record_variants("paraphrase_entail", scene(question=question)) == ([], "", "")


def test_build_reports_hold_without_rewriting_records(tmp_path):
    rows = [scene("valid"), scene("multi", question="誰が何を受け取った？"),
            scene("missing", sentence="")]
    before = json.loads(json.dumps(rows))
    lib, info = build(tmp_path, rows)
    assert info["rows"] == 1
    assert info["held_who_did_what"] == {"unsupported_question_slot": 1, "missing_scene": 1}
    assert rows == before
    assert json.loads(lib.con.execute("SELECT payload FROM records").fetchone()[0]) == rows[0]
    lib.close()


def test_scoped_answer_requires_original_scene_and_question(tmp_path):
    row = scene()
    lib, _ = build(tmp_path, [row])
    for query, context in [(row["question"], None), (row["question"], "リクが窓を開けた。"),
                           ("誰が窓を開けなかった？", row["sentence"]),
                           ("誰が窓を開けた？理由も答えて。", row["sentence"])]:
        result = lib.ask(query, context=context)
        assert result["verdict"] != "ANSWER"
    result = lib.ask(row["question"], context=row["sentence"])
    assert result["verdict"] == "ANSWER" and result["text"] == row["answer"]
    assert result["scope"] == {"kind": "attested_example", "sentence": row["sentence"],
                               "question": row["question"], "matching": "exact"}
    assert result["sources"][0]["source"].endswith(":" + row["sha"])
    assert result["sources"][0]["text"] == row["sentence"]
    assert result["evidence"] == [row["sentence"]]
    assert "verified" not in result
    lib.close()


@pytest.mark.parametrize("question, answer", [
    ("ナオはいつ窓を開けた？", "午前九時"), ("ナオは何を開けた？", "窓"),
])
def test_nonwho_single_slots_can_be_retrieved_in_their_scene(tmp_path, question, answer):
    row = scene(question=question, answer=answer)
    lib, _ = build(tmp_path, [row])
    assert lib.ask(question, context=row["sentence"])["text"] == answer
    assert lib.ask(question, slot="who", context=row["sentence"])["verdict"] != "ANSWER"
    lib.close()


def test_same_question_isolated_by_scene_and_conflict_abstains(tmp_path):
    a = scene("a")
    b = scene("b", sentence="リクが午後三時に窓を開けた。", answer="リク")
    c = scene("c", sentence=b["sentence"], answer="ミオ")
    lib, _ = build(tmp_path, [a, b, c])
    assert lib.ask(a["question"], context=a["sentence"])["text"] == "ナオ"
    assert lib.ask(b["question"], context=b["sentence"])["verdict"] == "TIED_ABSTAIN"
    assert lib.ask(a["question"])["verdict"] != "ANSWER"
    lib.close()


def test_stale_fixed_who_index_cannot_bypass_scope_or_slot_gate(tmp_path):
    row = scene(question="ナオはいつ窓を開けた？", answer="午前九時")
    lib, _ = build(tmp_path, [row])
    lib.con.execute("UPDATE records SET slot='who'")
    lib.con.commit()
    stale = lib.ask(row["question"], context=row["sentence"], slot="who")
    assert stale["verdict"] != "ANSWER"
    assert "UNKNOWN_INDEX_REBUILD_REQUIRED" in stale["scope_reasons"]
    forged = scene(question="誰が何を開けた？")
    lib.con.execute("UPDATE records SET payload=?", (json.dumps(forged, ensure_ascii=False),))
    lib.con.commit()
    assert lib.ask(row["question"], context=row["sentence"], slot="who")["verdict"] != "ANSWER"
    lib.close()


@pytest.mark.parametrize("sentence, question, family", [
    ("ナオが窓を掃除した。", "誰が窓を掃除した？", "paraphrase_entail"),
    ("ナオが窓を開けた。", "誰が窓を開けた？", "general_qa"),
])
def test_normal_router_does_not_promote_synthetic_scene_to_general_fact(tmp_path, sentence, question, family):
    row = scene(sentence=sentence, question=question)
    lib, _ = build(tmp_path, [row])
    root = lib.directory.parent
    lib.close()
    reading = read(row["question"])
    assert route(row["question"], reading)[0] == family
    result, trace = GeneralRouter(root).answer(row["question"], reading)
    assert result["verdict"] != "ANSWER"
    if family == "paraphrase_entail":
        assert not any(item.get("family") == "general_qa" for item in trace)
    assert not (root / "general_qa" / "evidence" / "evidence.db").exists()
