from __future__ import annotations

import json
import os
from pathlib import Path

from verantyx.cli import main
from verantyx.config import VeraConfig
from verantyx.one import Vera


RAW = "資料の出来事を一文で言い換えてください。"
SOURCE = "花子が太郎に資料を渡した。"
RAW_TWO_EVENT = "資料の出来事をすべて、二文でまとめてください。"
SOURCE_TWO_EVENT = "花子が太郎に資料を渡した。太郎が資料を読んだ。"
EXPECTED_TWO_EVENT = "花子が太郎に資料を渡した。また、太郎が資料を読んだ。"


# Integration (auditor, 2026-10-04): W7-chat (docs/CHAT.md) gives the round5 REPL a closed command set that ends with `/quit`;
# the legacy `:quit` of the lab/hybrid REPLs is no longer the round5 exit, so these tests exit with `/quit`.
def test_explicit_round5_chat_uses_raw_public_api_and_displays_partial_evidence(
        tmp_path, monkeypatch, capsys):
    source = tmp_path / "memo.txt"
    source.write_text(SOURCE, encoding="utf-8")
    inputs = iter([RAW, "/quit"])
    monkeypatch.setattr("verantyx.tui.read_input", lambda _prompt: next(inputs))

    seen = []
    original_ask = Vera.ask

    def recording_ask(self, raw_request, **kwargs):
        seen.append((self.mode, raw_request))
        return original_ask(self, raw_request, **kwargs)

    monkeypatch.setattr(Vera, "ask", recording_ask)
    result = main([
        "--store", str(tmp_path / "unused-store.json"),
        "chat", "--mode", "round5", "--document", str(source),
    ])
    dialogue = capsys.readouterr().out

    assert result == 0
    assert seen == [("round5", RAW)]
    assert "loaded 1 source document(s) for this session" in dialogue
    assert "PARTIAL_COMPLETENESS_UNVERIFIED" in dialogue
    assert "limited_projection_equivalent=True" in dialogue
    assert "full_semantic_equivalent=未確認" in dialogue
    assert "goal_satisfied=未確認" in dialogue
    assert "success_count_eligible=False" in dialogue
    assert "source_sha256=" in dialogue
    assert "source_event_sha256=" in dialogue
    assert "出典原文(source hash一致・真偽未確認): " + SOURCE in dialogue

    report_path = os.environ.get("VERA_CHAT_DIALOGUE_CAPTURE")
    if report_path:
        Path(report_path).write_text(dialogue, encoding="utf-8")


def test_round5_documents_require_explicit_mode_and_engine_route_is_rejected(
        tmp_path, capsys):
    source = tmp_path / "memo.txt"
    source.write_text(SOURCE, encoding="utf-8")

    result = main([
        "--store", str(tmp_path / "unused-store.json"),
        "chat", "--document", str(source),
    ])
    output = json.loads(capsys.readouterr().out)
    assert result == 2
    assert output["verdict"] == "UNKNOWN_ROUTE_CONFIGURATION"
    assert "requires --mode round5" in output["reason"]

    result = main([
        "--store", str(tmp_path / "unused-store.json"),
        "chat", "--mode", "round5", "--engine",
    ])
    output = json.loads(capsys.readouterr().out)
    assert result == 2
    assert output["verdict"] == "UNKNOWN_ROUTE_CONFIGURATION"
    assert "uses one.Vera.ask" in output["reason"]

    try:
        main(["chat", "--help"])
    except SystemExit as error:
        assert error.code == 0
    help_output = capsys.readouterr().out
    assert "--mode {lab,hybrid,round5}" in help_output
    assert "--document" in help_output


def test_chat_default_keeps_legacy_mode_and_raw_user_message(tmp_path, monkeypatch, capsys):
    inputs = iter(["ミオの居室を教えてください。", "/quit"])
    monkeypatch.setattr("verantyx.tui.read_input", lambda _prompt: next(inputs))
    monkeypatch.setattr(VeraConfig, "load",
                        classmethod(lambda _cls: VeraConfig(hf_store_repo="")))
    monkeypatch.setattr(Vera, "load_store", lambda self, _store: self)
    seen = []

    def fake_ask(self, raw_request):
        seen.append((self.mode, raw_request))
        return {"kind": "answer", "verdict": "ANSWER", "text": "legacy reply",
                "door": "legacy"}

    monkeypatch.setattr(Vera, "ask", fake_ask)
    result = main(["--store", str(tmp_path / "unused-store.json"), "chat"])
    output = capsys.readouterr().out

    assert result == 0
    assert seen == [("legacy", "ミオの居室を教えてください。")]
    assert "mode=lab" in output
    assert "legacy reply" in output


def test_round5_chat_same_two_event_request_remains_explicitly_partial(
        tmp_path, monkeypatch, capsys):
    source = tmp_path / "memo.txt"
    source.write_text(SOURCE_TWO_EVENT, encoding="utf-8")
    inputs = iter([RAW_TWO_EVENT, "/quit"])
    monkeypatch.setattr("verantyx.tui.read_input", lambda _prompt: next(inputs))

    seen = []
    results = []
    original_ask = Vera.ask

    def recording_ask(self, raw_request, **kwargs):
        seen.append((self.mode, raw_request))
        result = original_ask(self, raw_request, **kwargs)
        results.append(result)
        return result

    monkeypatch.setattr(Vera, "ask", recording_ask)
    result = main([
        "--store", str(tmp_path / "unused-store.json"),
        "chat", "--mode", "round5", "--document", str(source),
    ])
    dialogue = capsys.readouterr().out

    assert result == 0
    assert seen == [("round5", RAW_TWO_EVENT)]
    assert results[0]["verdict"] == "PARTIAL"
    assert results[0]["component_verdict"] == "ANSWER"
    assert results[0]["status"] == "PARTIAL_COMPLETENESS_UNVERIFIED"
    assert results[0]["goal_satisfied"] is None
    assert results[0]["success_count_eligible"] is False
    assert results[0]["text"] == EXPECTED_TWO_EVENT
    assert "PARTIAL_COMPLETENESS_UNVERIFIED" in dialogue
    assert "goal_satisfied=未確認" in dialogue
    assert "success_count_eligible=False" in dialogue
    assert "represented_projection_verified=True" in dialogue
    assert "full_goal_verified=False" in dialogue
    assert "source_truth_status=UNCLASSIFIED" in dialogue
    assert EXPECTED_TWO_EVENT in dialogue
    assert "出典主張の真偽未確認" in dialogue

    report_path = os.environ.get("VERA_CHAT_DIALOGUE_2EVENT_CAPTURE")
    if report_path:
        Path(report_path).write_text(dialogue, encoding="utf-8")
