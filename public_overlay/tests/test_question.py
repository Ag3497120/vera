from __future__ import annotations

from pathlib import Path

from verantyx import question
from verantyx.bot import Bot
from verantyx.chat import Chat
from verantyx.lattice import build


def _small_typo_assets(monkeypatch):
    words = {"電荷密度", "電荷", "密度", "説明", "ファイル", "水銀"}
    monkeypatch.setattr(question, "_typo_assets", lambda: (build(words), words))


def test_typed_query_keeps_surface_and_candidates_separate(monkeypatch, tmp_path: Path):
    _small_typo_assets(monkeypatch)
    monkeypatch.setattr(question.meaning_assets, "BUILD", tmp_path)

    q = question.read(" 電荷密変は何ですか。 ")
    assert q.surface.value == "電荷密変は何ですか。"
    assert q.kind.value == "fact"
    assert q.asked_slot.value == "what"
    assert q.typo.value.verdict == "TYPO_CANDIDATE"
    assert any(c.term == "電荷密変" and c.word == "電荷密度"
               for c in q.typo.value.candidates)
    assert q.sense.value.verdict == "LACK_OF_ASSET"
    assert q.sense.value.missing_assets == ("jawiki_senses", "jawiki_aliases")
    assert q.sense.part == "question.assets"
    assert q.stages.part == "stage_split.split"
    assert q.polarity.part == "polarity.observe_negation"
    assert q.speech_act.part == "intent.act_by_form"


def test_only_genuine_instruction_reaches_operation_parser(monkeypatch):
    _small_typo_assets(monkeypatch)
    monkeypatch.setattr(question, "_sense_assets", lambda: None)
    calls = []
    original = question.intent_frames.parse

    def spy(text):
        calls.append(text)
        return original(text)

    monkeypatch.setattr(question.intent_frames, "parse", spy)
    for text in (
        "朝、時間に余裕を持って家を出る利点を2文で説明してください。",
        "「会議の資料を今日中に送ってください」を、依頼文に書き換えてください。",
        "「時間は川だ」という比喩を説明してください。",
    ):
        q = question.read(text)
        assert q.kind.value != "instruction"
        assert q.intent_op.value.verdict == "NOT_APPLICABLE"
        assert q.intent_op.part == "question.instruction_gate"
    instruction = question.read("ファイルを開いてください。")
    assert calls == ["ファイルを開いてください。"]
    assert instruction.kind.value == "instruction"
    assert instruction.intent_op.value.op == "OPEN"
    assert instruction.intent_op.part == "intent_frames.parse"


def test_named_sense_runs_only_with_assets(monkeypatch):
    _small_typo_assets(monkeypatch)
    monkeypatch.setattr(question, "_sense_assets", lambda: (
        {"水銀": [{"core": "水銀", "domain_tag": "", "lead_tokens": []}]}, {}))
    calls = []
    original = question.sense_split.resolve

    def spy(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(question.sense_split, "resolve", spy)
    q = question.read("水銀とは何ですか。")
    assert calls == ["水銀"]
    assert q.sense.value.verdict == "RESOLVED"
    assert q.sense.value.core == "水銀"
    assert q.sense.part == "sense_split.resolve"


def test_stage_chain_is_preserved_as_typed_handoff(monkeypatch):
    _small_typo_assets(monkeypatch)
    monkeypatch.setattr(question, "_sense_assets", lambda: None)
    q = question.read("背任罪の刑の上限を科された者の再審請求先")
    assert q.kind.value == "multi_hop"
    assert q.stages.value.verdict == "STAGED"
    assert len(q.stages.value.stages) > 1
    assert q.stages.value.cuts
    assert "→" in q.stages.value.chain


def test_bot_and_chat_path_runs_reader_parts_and_hands_query_downstream(monkeypatch, tmp_path: Path):
    _small_typo_assets(monkeypatch)
    monkeypatch.setattr(question, "_sense_assets", lambda: (
        {"電荷密変": [{"core": "電荷密変", "domain_tag": "", "lead_tokens": []}]}, {}))

    calls = {name: 0 for name in ("read", "stage", "typo", "sense", "polarity", "act", "intent")}
    def wrap(owner, name, key):
        original = getattr(owner, name)
        def spy(*args, **kwargs):
            calls[key] += 1
            return original(*args, **kwargs)
        monkeypatch.setattr(owner, name, spy)

    wrap(question, "read", "read")
    wrap(question.stage_split, "split", "stage")
    wrap(question.typo_recovery, "recover", "typo")
    wrap(question.sense_split, "resolve", "sense")
    wrap(question.polarity, "observe_negation", "polarity")
    wrap(question.intent, "act_by_form", "act")
    wrap(question.intent_frames, "parse", "intent")

    bot = Bot()
    chat = Chat([], general=tmp_path / "absent.db")
    bot._chat = chat
    handed = []
    original_find = bot.find
    original_reply = chat.reply

    def find_spy(q, *, query=None):
        handed.append(("find", query))
        return original_find(q, query=query)

    def reply_spy(u, context="", *, query=None):
        handed.append(("chat", query))
        return original_reply(u, context, query=query)

    monkeypatch.setattr(bot, "find", find_spy)
    monkeypatch.setattr(chat, "reply", reply_spy)

    result = bot.reply("電荷密変を2文で説明してください。")
    assert result["kind"] != "cannot"
    assert calls["read"] == 1  # Chat receives Bot's Query, with no second read.
    assert handed[0][0] == "find" and handed[0][1] is handed[1][1]
    assert handed[1][0] == "chat"

    direct = chat.reply("電荷密変を説明してください。")
    assert direct["kind"] != "cannot"
    operation = bot.reply("ファイルを開いてください。")
    assert operation["kind"] == "cannot"
    assert calls["read"] == 3
    for part in ("stage", "typo", "sense", "polarity", "act"):
        assert calls[part] >= 3, part
    assert calls["intent"] == 1


def test_engine_operation_gate_uses_typed_reader(monkeypatch):
    _small_typo_assets(monkeypatch)
    monkeypatch.setattr(question, "_sense_assets", lambda: None)
    from verantyx.engine import ask

    class VeraStub:
        def ask(self, *_args, **_kwargs):
            return {"verdict": "ANSWER", "text": "stub answer", "tokens": []}

    vera = VeraStub()
    explanation = ask("利点を2文で説明してください。", vera, observe=False)
    assert explanation["verdict"] != "INTENT"
    operation = ask("ファイルを開いてください。", vera, observe=False)
    assert operation["verdict"] == "INTENT"
    assert operation["op"] == "OPEN"
