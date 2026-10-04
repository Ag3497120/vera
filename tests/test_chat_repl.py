from __future__ import annotations

import json
from json import JSONDecoder
from pathlib import Path

from verantyx.cli import _qc_records, main


DEMO_TEXT = (
    "先生が生徒に地図を渡した。\n"
    "校長が職員室で書類を確認した。\n"
    "母が弟に話した人を兄が呼んだ。\n"
    "係が荷物を倉庫に運んだ。\n"
)
R8_PLACEMENT = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2"
OBSERVE_PLACEMENT = Path(__file__).resolve().parent / "observe" / "data" / "placement.json"


def _document(tmp_path: Path) -> Path:
    path = tmp_path / "demo.txt"
    path.write_text(DEMO_TEXT, encoding="utf-8")
    return path


def _feed(monkeypatch, *lines: str) -> None:
    pending = iter([*lines, "/quit"])
    monkeypatch.setattr("verantyx.tui.read_input", lambda _prompt: next(pending, None))


def _json_in(text: str):
    decoder = JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        return value
    raise AssertionError("JSON object was not printed")


def _without_timing(value):
    if isinstance(value, dict):
        return {
            key: _without_timing(item)
            for key, item in value.items()
            if key not in {"ingest_ms", "elapsed_ms"}
        }
    if isinstance(value, list):
        return [_without_timing(item) for item in value]
    return value


def _chat(tmp_path: Path, monkeypatch, capsys, inputs, *, document=None, extra=()):
    _feed(monkeypatch, *inputs)
    argv = ["--store", str(tmp_path / "unused-store.json"), "chat", "--mode", "round5"]
    if document is not None:
        argv.extend(["--document", str(document)])
    argv.extend(extra)
    code = main(argv)
    return code, capsys.readouterr().out


def test_round5_chat_json_matches_ask_dict_including_later_stages(tmp_path, monkeypatch, capsys):
    doc = _document(tmp_path)
    monkeypatch.setenv("VERA_PLACEMENT", R8_PLACEMENT)
    query = "兄は誰を呼んだ？"

    assert main([
        "--store", str(tmp_path / "unused-store.json"), "ask", query,
        "--mode", "round5", "--document", str(doc),
        "--request-kind", "factual", "--human-present",
    ]) == 0
    ask = json.loads(capsys.readouterr().out)

    code, dialogue = _chat(
        tmp_path, monkeypatch, capsys, [query], document=doc,
        extra=("--request-kind", "factual", "--human-present", "--json"),
    )
    assert code == 0
    chat = _json_in(dialogue)
    assert _without_timing(chat) == _without_timing(ask)
    assert "question_cross" in chat
    assert "basis_policy" in chat and "outcome" in chat["basis_policy"]


def test_round5_chat_answers_map_question_with_source_and_line(tmp_path, monkeypatch, capsys):
    doc = _document(tmp_path)
    monkeypatch.setenv("VERA_PLACEMENT", R8_PLACEMENT)
    code, dialogue = _chat(tmp_path, monkeypatch, capsys,
                           ["誰が生徒に地図を渡した？"], document=doc)
    assert code == 0
    assert "\nANSWER\n" in dialogue
    assert "答え: " in dialogue and "先生" in dialogue
    assert "demo.txt:1:" in dialogue
    assert "先生が生徒に地図を渡した。" in dialogue
    assert "basis_policy.outcome:" in dialogue


def test_round5_chat_answers_brother_question_with_source_and_line(tmp_path, monkeypatch, capsys):
    doc = _document(tmp_path)
    monkeypatch.setenv("VERA_PLACEMENT", R8_PLACEMENT)
    query = "兄は誰を呼んだ？"
    code, dialogue = _chat(tmp_path, monkeypatch, capsys,
                           [query], document=doc, extra=("--json",))
    assert code == 0
    result = _json_in(dialogue)
    assert result["verdict"] == "UNKNOWN_UNREAD"
    assert isinstance(result.get("question_cross"), dict)
    assert result["basis_policy"]["outcome"] == "ABSTAIN"


def test_round5_chat_types_unread_destination_question(tmp_path, monkeypatch, capsys):
    doc = _document(tmp_path)
    monkeypatch.setenv("VERA_PLACEMENT", R8_PLACEMENT)
    query = "係は荷物をどこに運んだ？"
    code, dialogue = _chat(tmp_path, monkeypatch, capsys, [query], document=doc, extra=("--json",))
    assert code == 0
    result = _json_in(dialogue)
    assert result["verdict"] != "ANSWER"
    assert result["question_cross"]["state"] == "QUESTION_NOT_READ"
    assert "basis_policy" in result and "outcome" in result["basis_policy"]
    assert "QUESTION_NOT_READ" in dialogue


def test_round5_chat_keeps_other_unread_question_typed(tmp_path, monkeypatch, capsys):
    doc = _document(tmp_path)
    monkeypatch.setenv("VERA_PLACEMENT", R8_PLACEMENT)
    query = "校長はどこで書類を確認した？"
    code, dialogue = _chat(tmp_path, monkeypatch, capsys, [query], document=doc)
    assert code == 0
    assert "\nANSWER\n" in dialogue
    assert "答え: place: 職員室" in dialogue
    assert "demo.txt:2: 校長が職員室で書類を確認した。" in dialogue
    assert "basis_policy.outcome: ANSWER_HUMAN_BASIS" in dialogue


def test_gen_json_is_byte_identical_to_observe_with_same_structure_and_placement(
    tmp_path, monkeypatch, capsys,
):
    doc = _document(tmp_path)
    monkeypatch.setenv("VERA_PLACEMENT", R8_PLACEMENT)
    records, _where, _loaded, _skipped = _qc_records([str(doc)])
    structure = tmp_path / "structure.jsonl"
    structure.write_text(
        "".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
                for record in records),
        encoding="utf-8",
    )
    anchor = "先生が生徒に地図を渡した。"
    direction = "FACE_SWAP:agent"
    assert main([
        "observe", "--anchor-text", anchor, "--direction", direction, "--range", "1",
        "--structure", str(structure), "--placement", str(OBSERVE_PLACEMENT),
    ]) == 0
    observe_line = capsys.readouterr().out.rstrip("\n")

    code, dialogue = _chat(
        tmp_path, monkeypatch, capsys, [f'/gen "{anchor}" {direction} 1'],
        document=doc, extra=("--placement", str(OBSERVE_PLACEMENT), "--json"),
    )
    assert code == 0
    gen_line = next(
        line for line in dialogue.splitlines()
        if line.startswith('{"schema":"verantyx.observe/1"')
    )
    assert gen_line == observe_line


def test_gen_without_json_placement_reports_no_move_license_and_observation(
    tmp_path, monkeypatch, capsys,
):
    monkeypatch.delenv("VERA_PLACEMENT", raising=False)
    code, dialogue = _chat(
        tmp_path, monkeypatch, capsys,
        ['/gen "先生が生徒に地図を渡した。" FACE_SWAP:agent 1'],
    )
    assert code == 0
    assert "NO_MOVE_LICENSED" in dialogue
    assert "UNKNOWN" in dialogue


def test_startup_reports_missing_placement_and_disabled_typed_question_path(
    tmp_path, monkeypatch, capsys,
):
    monkeypatch.delenv("VERA_PLACEMENT", raising=False)
    code, dialogue = _chat(tmp_path, monkeypatch, capsys, [])
    assert code == 0
    assert "配置: 配置無し" in dialogue
    assert "型の質問観測は動きません" in dialogue
    assert "読込文書数: 0" in dialogue


def test_read_uses_semantic_read_and_shows_event_cross(tmp_path, monkeypatch, capsys):
    code, dialogue = _chat(tmp_path, monkeypatch, capsys, ["/read 妹が本を読んだ。"])
    assert code == 0
    assert '"readable": true' in dialogue
    assert '"predicate": "読む"' in dialogue
    assert '"agent": "妹"' in dialogue
    assert '"patient": "本"' in dialogue


def test_doc_and_docs_load_source_for_later_questions(tmp_path, monkeypatch, capsys):
    doc = _document(tmp_path)
    monkeypatch.setenv("VERA_PLACEMENT", R8_PLACEMENT)
    code, dialogue = _chat(tmp_path, monkeypatch, capsys,
                           [f"/doc {doc}", "/docs", "誰が生徒に地図を渡した？"])
    assert code == 0
    assert "読み込み: " in dialogue
    assert "demo.txt" in dialogue
    assert "先生" in dialogue
    assert "先生が生徒に地図を渡した。" in dialogue


def test_unknown_slash_command_is_a_typed_unknown_command(tmp_path, monkeypatch, capsys):
    code, dialogue = _chat(tmp_path, monkeypatch, capsys, ["/x"])
    assert code == 0
    assert _json_in(dialogue) == {
        "kind": "unknown", "verdict": "UNKNOWN_COMMAND", "command": "/x",
    }


def test_json_command_enables_raw_result_dict(tmp_path, monkeypatch, capsys):
    doc = _document(tmp_path)
    monkeypatch.setenv("VERA_PLACEMENT", R8_PLACEMENT)
    code, dialogue = _chat(tmp_path, monkeypatch, capsys,
                           ["/json on", "誰が生徒に地図を渡した？"], document=doc)
    assert code == 0
    assert "JSON: on" in dialogue
    assert _json_in(dialogue)["verdict"] == "ANSWER"


def test_route_delegates_to_existing_cli_route_entry(tmp_path, monkeypatch, capsys):
    explanation = tmp_path / "agents.txt"
    explanation.write_text("説明", encoding="utf-8")
    seen = []

    def emit(path, task):
        seen.append((path, task))
        print('{"decision":"route"}')
        return 0

    monkeypatch.setattr("verantyx.routing_from_text.emit", emit)
    task = '{"role":"implement","kind":"feature","size":"small"}'
    code, dialogue = _chat(tmp_path, monkeypatch, capsys,
                           [f"/route {explanation} {task}"])
    assert code == 0
    assert seen == [(str(explanation), task)]
    assert '{"decision":"route"}' in dialogue
