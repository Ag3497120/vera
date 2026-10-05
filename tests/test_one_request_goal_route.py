from __future__ import annotations

import json

from verantyx.cli import main
from verantyx.one import Vera


RAW = "資料の出来事を一文で言い換えてください。"
SOURCE = "花子が太郎に資料を渡した。"


def test_public_python_ask_routes_request_and_original_document_through_verifier():
    vera = Vera.from_texts({"memo": SOURCE}, mode="round5")
    result = vera.ask(RAW)

    assert result["door"] == "round5_request_goal"
    assert result["runtime_mode"] == "round5"
    assert result["verdict"] == "PARTIAL"
    assert result["text"] == "花子は太郎に資料を渡した。"
    assert result["goal_route"] == "source_bound_candidate"
    assert result["source_binding_success"] is True
    assert result["source_binding_status"] == "BOUND"
    assert result["goal_satisfied"] is None
    assert result["success_count_eligible"] is False
    assert result["verified"] is False
    source = result["sources"][0]
    assert source == {
        "family": "document",
        "source": "memo",
        "sha256": result["evidence"][0]["source_sha256"],
        "original_document_sha256": result["evidence"][0]["source_sha256"],
        "original_sentence_span": {"start": 0, "end": len(SOURCE)},
    }
    assert result["trace"][0]["part"] == "one.round5_route"


def test_two_sentence_event_request_uses_target_projection_before_span_binding():
    raw = "資料の出来事を言い換えてください。"
    source = "午後、猫は庭で眠った。花子が太郎に資料を渡した。"
    vera = Vera.from_texts({"memo": source}, mode="round5")

    result = vera.ask(raw)
    navigation = result["multigrain_navigation"]
    binding = navigation["source_binding"]
    selection = navigation["request_goal_selection"]
    bound = binding["selections"][0]

    assert navigation["raw_question"] == raw
    assert navigation["selector_query"] == "資料"
    assert navigation["query_terms"] == ["資料"]
    assert navigation["resolution_verdict"] == "UNKNOWN_NOT_PRESENT"
    assert navigation["resolution_as_facet_only"] == ["資料"]
    assert navigation["resolution_as_core"] == []
    assert navigation["resolution_missing"] == []
    assert navigation["candidate_selection_mode"] == "exact_source_facet_owner"
    assert navigation["candidate_selection_verdict"] == "EXACT_FACET_OWNER_UNIQUE"
    assert selection["action"] == "restate"
    assert selection["target_kind"] == "source_event"
    assert binding["status"] == "BOUND"
    assert bound["source_id"] == "memo"
    assert bound["sentence_text"] == "花子が太郎に資料を渡した。"
    assert bound["sentence_span"] == {"source": "memo", "start": 11, "end": 24}
    assert bound["candidate"] == "花子"
    assert bound["candidate_spans"] == [[11, 13]]
    assert bound["candidate_role"] == "agent"
    assert bound["candidate_argument_span"] == [11, 13]
    assert bound["request_target_anchor"] == "資料"
    assert bound["target_role"] == "patient"
    assert bound["target_argument_span"] == [17, 19]
    assert bound["target_case_particle_span"] == [19, 20]
    assert bound["source_frame_id"]
    assert bound["source_frame_evidence_clause_id"]
    assert bound["source_assertion_status"] == "UNCLASSIFIED"
    assert binding["source_truth_status"] == "UNCLASSIFIED; no truth or authority claim"
    assert result["verdict"] == "PARTIAL"
    assert result["text"] == "花子は太郎に資料を渡した。"
    assert result["goal_satisfied"] is None
    assert result["success_count_eligible"] is False


def test_exact_facet_cooccurrence_cannot_borrow_a_patient_from_another_event():
    source = "資料は棚にある。花子が太郎に手紙を渡した。"
    vera = Vera.from_texts({"memo": source}, mode="round5")

    result = vera.ask("資料の出来事を言い換えてください。")

    assert result["verdict"] == "UNKNOWN_REQUEST_GOAL_HOLD"
    binding = result["multigrain_navigation"]["source_binding"]
    assert binding["status"] == "HOLD"
    assert "permitted explicit roles" in binding["reason"]
    assert result["goal_satisfied"] is None
    assert result["success_count_eligible"] is False


def test_multiple_exact_facet_owners_hold_before_goal_realization():
    source = "花子が太郎に資料を渡した。次郎が資料を受け取った。"
    vera = Vera.from_texts({"memo": source}, mode="round5")

    result = vera.ask("資料の出来事を言い換えてください。")

    navigation = result["multigrain_navigation"]
    assert navigation["candidate_selection_mode"] == "exact_source_facet_owner"
    assert navigation["verdict"] == "UNKNOWN_REQUEST_GOAL_SELECTION_HOLD"
    assert navigation["selected_candidate"] is None
    assert navigation["candidate_selection_verdict"] == "HOLD"
    assert result["verdict"] == "UNKNOWN_REQUEST_GOAL_HOLD"
    assert result["text"] == ""
    assert result["goal_satisfied"] is None
    assert result["success_count_eligible"] is False


def test_source_facet_with_wrong_argument_role_does_not_bind_as_goal_patient():
    source = "花子が資料に手紙を渡した。"
    vera = Vera.from_texts({"memo": source}, mode="round5")

    result = vera.ask("資料の出来事を言い換えてください。")

    assert result["verdict"] == "UNKNOWN_REQUEST_GOAL_HOLD"
    assert result["source_binding_success"] is False
    assert result["goal_route"] == "source_candidate_rejected_by_local_frame_binding"
    assert result["text"] == ""
    assert result["goal_satisfied"] is None


def test_quoted_source_event_candidate_is_not_rebound_as_asserted_source():
    source = "「花子が太郎に資料を渡した。」"
    vera = Vera.from_texts({"memo": source}, mode="round5")

    result = vera.ask("資料の出来事を言い換えてください。")

    assert result["verdict"] == "UNKNOWN_REQUEST_GOAL_HOLD"
    assert result["source_binding_success"] is False
    assert result["text"] == ""
    assert result["goal_satisfied"] is None


def test_source_content_target_stays_held_instead_of_using_legacy_partial_fallback():
    vera = Vera.from_texts({"memo": SOURCE}, mode="round5")

    result = vera.ask("資料の内容を一文で言い換えてください。")

    assert result["verdict"] == "UNKNOWN_REQUEST_GOAL_HOLD"
    assert result["goal_route"] == "raw_request_projection_hold"
    assert result["source_binding_success"] is False
    assert result["text"] == ""
    assert result["goal_satisfied"] is None
    assert result["success_count_eligible"] is False


def test_negative_source_event_is_not_rebound_as_a_positive_target():
    source = "花子が太郎に資料を渡さなかった。"
    vera = Vera.from_texts({"memo": source}, mode="round5")

    result = vera.ask("資料の出来事を言い換えてください。")

    assert result["verdict"] == "UNKNOWN_REQUEST_GOAL_HOLD"
    assert result["multigrain_navigation"]["source_binding"]["status"] == "HOLD"
    assert result["goal_satisfied"] is None
    assert result["success_count_eligible"] is False


def test_round5_request_without_an_original_source_holds_without_semantic_fallback():
    result = Vera(mode="round5").ask(RAW)

    assert result["door"] == "round5_request_goal"
    assert result["verdict"] == "UNKNOWN_REQUEST_GOAL_HOLD"
    assert result["status"] == "HOLD"
    assert result["text"] == ""
    assert result["candidate_text"] is None
    assert "exactly one original source document" in result["reason"]


def test_polite_fact_request_continues_to_semantic_qa(monkeypatch):
    vera = Vera(mode="round5")
    seen = []

    def semantic(text, *, candidate_views=()):
        seen.append(text)
        return {"kind": "answer", "verdict": "ANSWER", "text": "room 204",
                "trace": [], "door": "semantic_qa"}

    monkeypatch.setattr(vera, "_ask_semantic", semantic)
    raw = "ミオの居室を教えてください。"
    result = vera.ask(raw)

    assert seen == [raw]
    assert result["door"] != "round5_request_goal"
    assert result["text"] == "room 204"


def test_round5_attaches_multigrain_candidates_as_navigation_only_to_qa_and_goal(monkeypatch):
    vera = Vera.from_texts({"memo": SOURCE}, mode="round5")
    seen = []
    goal_raw = "資料の出来事を言い換えてください。"

    def navigation(raw):
        seen.append(raw)
        if raw == goal_raw:
            return {
                "kind": "multigrain_candidates",
                "verdict": "UNKNOWN_NO_CANDIDATE",
                "raw_question": raw,
                "selected_candidate": None,
                "source_identity_status": "UNKNOWN_NO_SOURCE_MATCH",
                "independent_source_count": None,
                "trace": {"calls": {"FullConstellation.ask": 1}},
                "used_for_answer": False,
                "used_for_goal_realization": False,
                "authority": "navigation_only_unverified",
            }
        return {
            "kind": "multigrain_candidates",
            "verdict": "CANDIDATE_SOURCE_LEAF_MATCHED",
            "selected_candidate": "fixture-only",
            "source_identity_status": "identity_unverified",
            "independent_source_count": None,
            "trace": {"calls": {"FullConstellation.ask": 1}},
            "used_for_answer": False,
            "used_for_goal_realization": False,
            "authority": "navigation_only_unverified",
        }

    monkeypatch.setattr(vera, "_round5_multigrain_navigation", navigation)
    monkeypatch.setattr(vera, "_ask_semantic", lambda _raw, **_kwargs: {
        "kind": "answer", "verdict": "ANSWER", "text": "document QA result", "trace": []
    })
    qa_raw = "ミオの居室を教えてください。"
    qa = vera.ask(qa_raw)
    goal = vera.ask(goal_raw)

    assert seen == [qa_raw, goal_raw]
    assert qa["text"] == "document QA result"
    assert qa["multigrain_navigation"]["authority"] == "navigation_only_unverified"
    assert qa["multigrain_navigation"]["used_for_answer"] is False
    assert goal["candidate_text"] == "花子は太郎に資料を渡した。"
    assert goal["goal_route"] == "unbound_original_source_fallback"
    assert goal["source_binding_success"] is False
    assert goal["source_binding_status"] == "HOLD"
    assert goal["multigrain_navigation"]["used_for_goal_realization"] is False
    route_steps = [step for step in goal["trace"]
                   if step["part"] == "multigrain_adapter.retrieve_multigrain_candidates"]
    assert len(route_steps) == 1
    assert route_steps[0]["licenses_goal_realization"] is False


def test_cli_explicit_round5_document_entry_uses_same_python_route(tmp_path, capsys):
    source = tmp_path / "memo.txt"
    source.write_text(SOURCE, encoding="utf-8")
    result = main([
        "--store", str(tmp_path / "unused-store.json"),
        "ask", RAW,
        "--mode", "round5",
        "--document", str(source),
    ])
    output = json.loads(capsys.readouterr().out)

    assert result == 0
    assert output["door"] == "round5_request_goal"
    assert output["verdict"] == "PARTIAL"
    assert output["candidate_text"] == "花子は太郎に資料を渡した。"
    assert output["goal_satisfied"] is None
    assert output["success_count_eligible"] is False


def test_cli_rejects_source_documents_when_default_legacy_mode_was_selected(tmp_path, capsys):
    source = tmp_path / "memo.txt"
    source.write_text(SOURCE, encoding="utf-8")
    result = main([
        "--store", str(tmp_path / "unused-store.json"),
        "ask", RAW, "--mode", "legacy",
        "--document", str(source),
    ])
    output = json.loads(capsys.readouterr().out)

    assert result == 2
    assert output["verdict"] == "UNKNOWN_ROUTE_CONFIGURATION"
    assert "requires --mode round5" in output["reason"]
