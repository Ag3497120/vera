from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from verantyx.abilities import Abilities
from verantyx.ability_corpus import Corpus
from verantyx.chat import Chat
from verantyx.core_abilities import morae
from verantyx.cross_store import CrossStore
from verantyx.question import read as read_question
from verantyx.trace import Trace, _pick
from tools.build_p4_corpus_index import build


def _index(tmp_path: Path, family: str, rows: list[dict]) -> Corpus:
    src = tmp_path / (family + ".jsonl")
    src.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    build(src, tmp_path / "idx" / (family + ".db"), family)
    return Corpus(tmp_path / "idx")


def _chat(tmp_path: Path, corpus: Corpus | None = None) -> Chat:
    chat = Chat([], general=tmp_path / "absent_general.db")
    chat._abilities = Abilities(corpus or Corpus(tmp_path / "idx"), general=chat.general)
    return chat


def test_chat_typed_understanding_and_polite_rewrite_keep_sources(tmp_path: Path):
    chat = _chat(tmp_path)
    same = chat.reply("次の2文は同じ意味を表していますか。『窓を閉めてください。』／『窓を閉じてもらえますか。』")
    assert same["ability"] == "understanding"
    assert same["kind"] == "answer" and "はい" in same["text"]
    assert {s["text"] for s in same["sources"]} == {"窓を閉めてください。", "窓を閉じてもらえますか。"}
    assert any(t["part"] == "verdict.judge" for t in same["trace"])

    unknown = chat.reply("『美咲は傘を持たずに出かけた。雨が降った。』この文から、美咲はぬれたと分かりますか。")
    assert "分かりません" in unknown["text"]
    assert unknown["sources"][0]["family"] == "user"

    rewrite = chat.reply("「会議の資料を今日中に送ってください」を、ていねいな依頼文に書き換えてください。")
    assert rewrite["ability"] == "generation" and "いただけますか" in rewrite["text"]
    assert rewrite["lines"][0]["reread"]
    assert rewrite["sources"][0]["text"] == "会議の資料を今日中に送ってください"


def test_understanding_keeps_tense_and_realizes_role_answer(tmp_path: Path):
    chat = _chat(tmp_path)
    closed = chat.reply("『駅前のパン屋は月曜日が定休日だ。』今日は月曜日で、その店は休みだった。この情報は最初の文と一致しますか。")
    assert closed["ability"] == "understanding" and closed["text"].startswith("はい。")
    assert {s["source"] for s in closed["sources"]} == {"user:quote", "user:observation"}
    who = chat.reply("『直子はレシピを見ながら、鍋に塩をひとつまみ加えた。』誰が何を鍋に加えましたか。")
    assert "直子は鍋に塩を加えました" in who["text"]
    assert any(t["part"] == "realize.realize" and t["reread"] for t in who["trace"])
    future = chat.reply("『この地域では、春になると桜が咲く。』この文だけから、今年も桜が咲いたと分かりますか。")
    assert future["text"] == "この文だけでは分かりません。"


def test_conditional_examples_require_independent_sources_and_action_target(tmp_path: Path):
    _index(tmp_path, "local", [
        {"text": "雨の日に傘を持たずに出たら、髪が濡れた。", "source": "a", "scene": "雨", "sha": "a"},
        {"text": "雨の日に傘を持たずに出たら、服が濡れた。", "source": "b", "scene": "雨", "sha": "b"},
    ])
    out = _chat(tmp_path).reply("雨の日に傘を持たずに外出すると、どうなりますか？")
    assert out["ability"] == "commonsense" and "濡れた例" in out["text"]
    assert {s["source"] for s in out["sources"] if s["family"] == "local"} == {"a", "b"}
    assert any(t["part"] == "event_transition.conditional" and t.get("reread") for t in out["trace"])

    _index(tmp_path, "pro", [
        {"text": "雨が降り始めたので、窓を閉めた。", "source": "p1", "scene": "雨", "sha": "p1"},
        {"text": "雨が降り始めたので、窓を閉めた。", "source": "p2", "scene": "雨", "sha": "p2"},
    ])
    action = _chat(tmp_path).reply("窓を開けたまま雨が降り始めたことに気づいたら、何をするのがよいですか？")
    assert action["ability"] == "commonsense" and "窓を閉める" in action["text"]
    assert {s["source"] for s in action["sources"] if s["family"] == "pro"} == {"p1", "p2"}


def test_two_sentence_benefit_explanation_reads_causal_outcome_clauses(tmp_path: Path):
    corpus = _index(tmp_path, "local", [
        {"text": "余裕を持って家を出るので、不安が減った。", "source": "a", "scene": "通勤", "sha": "a"},
        {"text": "余裕を持って家を出たので、心にゆとりがある。", "source": "b", "scene": "通勤", "sha": "b"},
    ])
    out = _chat(tmp_path, corpus).reply("朝、余裕を持って家を出る利点を2文で説明してください。")
    assert out["ability"] == "generation" and out["kind"] == "compose"
    assert len(out["lines"]) == 2 and all(line["reread"] for line in out["lines"])
    assert {s["source"] for s in out["sources"]} == {"a", "b"}


def test_event_graph_requires_two_sources_in_one_family_and_wires_chat(tmp_path: Path):
    row = "猫が箱を押したら、箱が倒れた。"
    local = [
        {"text": row, "source": "batch-a", "scene": "猫の遊び", "sha": "a"},
        {"text": row, "source": "batch-b", "scene": "猫の遊び", "sha": "b"},
    ]
    corpus = _index(tmp_path, "local", local)
    chat = _chat(tmp_path, corpus)
    out = chat.reply("猫が箱を押したら、どうなりますか？")
    assert out["ability"] == "commonsense" and out["kind"] == "answer"
    assert "倒れ" in out["text"]
    assert {s["source"] for s in out["sources"] if s["family"] == "local"} == {"batch-a", "batch-b"}
    assert any(t["part"].startswith("event_transition") for t in out["trace"])
    assert out["lines"][0]["reread"]

    # A pro witness cannot combine with a local witness to create quorum.
    _index(tmp_path, "local", local[:1])
    _index(tmp_path, "pro", [{"text": row, "source": "pro-a", "scene": "猫の遊び", "sha": "c"}])
    alone = _chat(tmp_path).reply("猫が箱を押したら、どうなりますか？")
    assert alone["kind"] == "unknown"


def test_corpus_keeps_consecutive_narrative_order_and_creation_rereads(tmp_path: Path, monkeypatch):
    from verantyx import abilities, compose_ja, hub_edges, realize, surface
    calls = {"word_center": 0, "seats": 0, "realize": 0, "compose_ja": 0}
    for module, name, key in ((surface, "word_center", "word_center"),
                              (hub_edges, "seats", "seats"),
                              (realize, "realize", "realize"),
                              (compose_ja, "compose", "compose_ja")):
        original = getattr(module, name)
        def spy(*args, _original=original, _key=key, **kwargs):
            calls[_key] += 1
            return _original(*args, **kwargs)
        monkeypatch.setattr(module, name, spy)
    (tmp_path / "writer.json").write_text("{}")
    monkeypatch.setattr(abilities, "_writer", lambda _path: type("WriterStub", (),
                                                                 {"forms": {}, "vocab": set()})())
    corpus = _index(tmp_path, "local", [
        {"text": "猫が窓を見た。", "source": "scene-a", "scene": "猫の朝", "sha": "a"},
        {"text": "猫が庭に出た。", "source": "scene-a", "scene": "猫の朝", "sha": "b"},
        {"text": "猫が鳥を見つけた。", "source": "scene-a", "scene": "猫の朝", "sha": "c"},
        {"text": "犬が走った。", "source": "scene-b", "scene": "犬の朝", "sha": "d"},
    ])
    rows = corpus.search("猫", "local")
    assert [r.sha for r in corpus.neighbors(rows[0], after=3)] == ["a", "b", "c"]
    out = _chat(tmp_path, corpus).reply("「猫」を題材に、短い物語を書いてください。")
    assert out["ability"] == "creation" and out["kind"] == "compose"
    assert out["text"].startswith("創作")
    assert len(out["lines"]) == 3
    assert all(line["sources"] and line["reread"] for line in out["lines"])
    assert any(t["part"] == "event_graph.walk" for t in out["trace"])
    assert all(n > 0 for n in calls.values())
    assert {"surface.word_center", "hub_edges.seats", "trace.walk", "compose_ja.compose",
            "realize.realize", "connective_render"} <= {t["part"] for t in out["trace"]}


def test_humor_explanation_and_metaphor_transfer_are_sourced(tmp_path: Path):
    chat = _chat(tmp_path)
    pun = chat.reply("次のダジャレの仕掛けを説明してください：「校長先生、絶好調！」")
    assert pun["ability"] == "humor" and pun["kind"] == "answer"
    assert "音" in pun["text"] and pun["sources"][0]["family"] == "user"

    chat._abilities._simile_properties = lambda _v: [("冷たい", 3, [{"family": "local", "source": "a", "text": "氷のように冷たい。"}])]
    chat._abilities._predicable = lambda _t, _p: [
        {"family": "general", "source": "b", "text": "心は冷たい。"},
        {"family": "general", "source": "c", "text": "冷たい心。"},
    ]
    meta = chat.reply("「彼女の心は氷だ」はどういう意味ですか？")
    assert meta["ability"] == "metaphor" and "冷たい" in meta["text"]
    assert {s["family"] for s in meta["sources"]} == {"user", "local", "general"}


def test_homophone_pair_uses_both_readings_and_attested_roles(tmp_path: Path):
    db = tmp_path / "general.db"
    con = sqlite3.connect(db)
    con.executescript("CREATE TABLE tedges(head TEXT,dep TEXT,rel TEXT,pol TEXT,src TEXT,sha TEXT);"
                      "CREATE TABLE tsent(sha TEXT,text TEXT);")
    for i, (verb, noun) in enumerate([("渡る", "橋"), ("渡る", "橋"),
                                      ("渡す", "箸"), ("渡す", "箸")]):
        con.execute("INSERT INTO tedges VALUES (?,?,?,?,?,?)",
                    (verb, noun, "を", "+", f"source-{i}", f"sha-{i}"))
        con.execute("INSERT INTO tsent VALUES (?,?)", (f"sha-{i}", f"{noun}を{verb}。"))
    con.commit()
    con.close()
    chat = Chat([], general=db)
    chat._abilities = Abilities(Corpus(tmp_path / "idx"), general=db)
    out = chat.reply("「橋」と「箸」を使ってダジャレを作ってください。")
    assert out["ability"] == "humor" and out["kind"] == "compose"
    assert "橋を渡る、箸を渡す" in out["text"]
    assert {s["source"] for s in out["sources"] if s["family"] == "general"} == {
        "source-0", "source-1", "source-2", "source-3"}
    assert any(t["part"] == "homophone_pair" and t.get("reread") for t in out["trace"])


def test_trace_walk_selection_abstains_on_equal_top():
    store = CrossStore()
    store.crosses = {"始": {"甲": 1, "乙": 1}, "甲": {"始": 1}, "乙": {"始": 1}}
    t = Trace(seed="始", mode="path", horizon={"始"})
    assert _pick(store, ["甲", "乙"], t) is None
    assert _pick(store, ["甲"], t) == "甲"


def test_haiku_counts_cut_and_two_images_from_distinct_sentences(tmp_path: Path):
    corpus = _index(tmp_path, "local", [
        {"text": "梅雨明けが近づいた。", "source": "a", "scene": "梅雨（晴天）", "sha": "a"},
        {"text": "夏の青空が広がった。", "source": "b", "scene": "梅雨（晴天）", "sha": "b"},
        {"text": "虹の道が見えた。", "source": "c", "scene": "梅雨（晴天）", "sha": "c"},
    ])
    out = _chat(tmp_path, corpus).reply("「梅雨明け」を題材に、季語を含む五七五の俳句を作ってください。")
    assert out["kind"] == "compose"
    poem = out["text"].split(": ", 1)[1].split("／")
    assert [morae(part) for part in poem] == [5, 7, 5]
    assert poem[0].endswith("や")
    assert len({s["sha"] for line in out["lines"] for s in line["sources"]}) == 3


def test_poem_splits_attested_coordination_and_rereads_each_line(tmp_path: Path):
    sentences = ["湯気が喫茶店の窓に広がった。",
                 "コーヒーの香りと暖房の熱が頬を包んだ。",
                 "湯気が上がった。", "時計が鳴った。", "扉が開いた。"]
    corpus = _index(tmp_path, "local", [
        {"text": sentence, "source": "cafe-a", "scene": "喫茶店（午後）", "sha": str(i)}
        for i, sentence in enumerate(sentences)])
    out = _chat(tmp_path, corpus).reply("「喫茶店」を題材に五行の詩を書いてください。音や匂いを入れてください。")
    assert out["kind"] == "compose" and len(out["lines"]) == 5
    assert any("コーヒーの香り" in line["text"] for line in out["lines"])
    assert all(line["sources"] and line["reread"] for line in out["lines"])


def test_story_keeps_received_gift_and_smile_in_sourced_ending(tmp_path: Path):
    sentences = ["日差しが花屋に差し込んだ。", "花びらが揺れた。",
                 "友人も笑顔で花を受け取った。"]
    corpus = _index(tmp_path, "local", [
        {"text": sentence, "source": "florist-a", "scene": "買い物（昼）", "sha": str(i)}
        for i, sentence in enumerate(sentences)])
    out = _chat(tmp_path, corpus).reply(
        "「小さな花屋」を題材に、短い物語を書いてください。誰かを元気づける展開にしてください。")
    assert out["kind"] == "compose" and len(out["lines"]) == 3
    assert "花を受け取った友人が笑った" in out["text"]
    assert out["lines"][-1]["sources"][0]["source"] == "florist-a"
    assert len(out["lines"][-1]["reread"]) == 2


def test_code_and_conversation_are_separate_supply_layers(tmp_path: Path):
    _index(tmp_path, "code", [{"text": "変数が値を保持する。", "source": "code-a",
                               "topic": "変数と型", "sha": "code"}])
    corpus = _index(tmp_path, "conversation", [{"text": "会議は午後三時からです。",
                                               "source": "conv-a", "dialogue_id": "d1",
                                               "scene": "予定の相談", "sha": "conv"}])
    assert corpus.search("変数", "code")[0].family == "code"
    assert corpus.search("変数", "conversation") == []
    assert corpus.search("会議", "conversation")[0].group == "d1"
    assert corpus.search("会議", "code") == []


def test_generation_calls_frame_composer_and_say_fallback(tmp_path: Path, monkeypatch):
    corpus = _index(tmp_path, "local", [{"text": "窓が光った。", "source": "scene-a",
                                         "scene": "窓の朝", "sha": "w"}])
    chat = _chat(tmp_path, corpus)
    made = chat.reply("窓の様子を一文で描写してください。")
    assert made["ability"] == "generation" and made["kind"] == "compose"
    assert made["lines"][0]["reread"]
    assert any(t["part"] == "compose_frame.compose" for t in made["trace"])

    (tmp_path / "absent_general.db").touch()
    chat = _chat(tmp_path, Corpus(tmp_path / "empty_index"))
    from verantyx import say
    called = []
    def fake_say(topic, **_kwargs):
        called.append(topic)
        return {"verdict": "GROUNDED", "lines": [{"sentence": "星が光る。",
                "witnesses": [{"source": "general-a", "text": "星が光った。"}]}]}
    monkeypatch.setattr(say, "say", fake_say)
    fallback = chat.reply("星の様子を一文で描写してください。")
    assert called and fallback["lines"][0]["sources"][0]["source"] == "general-a"
    assert any(t["part"] == "say.say" for t in fallback["trace"])


def test_speech_act_drafts_fill_new_roles_and_reread(tmp_path: Path):
    chat = _chat(tmp_path)
    cases = [
        ("同僚に資料を確認してもらう依頼文を書いてください。",
         "request", ("資料", "いただけますか")),
        ("私が資料をなくしたことを謝る文を書いてください。",
         "apology", ("資料", "申し訳ありません")),
        ("同僚に、来週の研修の集合時刻が変わったことを知らせるメッセージを書いてください。"
         "新しい集合時刻は午前9時です。", "report-change", ("研修", "午前9時")),
        ("友人から借りた傘を返すときのお礼のメッセージを書いてください。",
         "thanks", ("傘", "ありがとうございます")),
        ("公園で花を見つけたときの感想を一文で書いてください。",
         "impression", ("公園", "花")),
        ("街角に新しい図書館ができたと聞いたときの期待を一文で書いてください。",
         "impression", ("図書館", "楽しみ")),
        ("職場で資料の確認に間に合わない可能性に気づいたとき、先輩に状況を相談する"
         "メッセージを書いてください。記録と、必要なら確認の調整を相談したいことを含めてください。",
         "consult", ("資料の確認", "記録")),
    ]
    for prompt, act, content in cases:
        assert read_question(prompt).requested_speech_act.value == act
        out = chat.reply(prompt)
        assert out["ability"] == "generation" and out["kind"] == "answer"
        assert all(word in out["text"] for word in content)
        assert all(line["reread"] and line["sources"][0]["family"] == "user"
                   for line in out["lines"])
        assert any(step["part"] == "generation.speech_act_form" and
                   step["verdict"] == "REREAD" for step in out["trace"])


def test_catchphrase_uses_brief_slots_and_abstains_on_tied_collocations(tmp_path: Path):
    chat = _chat(tmp_path)
    copy = chat.reply("「昼食を素早く用意したい人」に向けて、サンドイッチの新商品を"
                      "紹介するキャッチコピーを作ってください。")
    assert copy["kind"] == "compose"
    assert "サンドイッチ一つで、昼食を素早く" in copy["text"]
    assert copy["lines"][0]["sources"][0]["source"] == "user:brief"

    corpus = _index(tmp_path, "local", [
        {"text": "散歩で安心が増えた。", "source": "a", "sha": "a"},
        {"text": "散歩で快適さが増えた。", "source": "b", "sha": "b"},
    ])
    tied = _chat(tmp_path, corpus).reply(
        "「散歩を始める人」に向けたキャッチコピーを作ってください。"
        "安心と快適さのどちらかが伝わる表現にしてください。")
    assert tied["kind"] == "unknown" and tied["verdict"] == "TIED_ABSTAIN"


def test_action_from_examples_generalizes_to_another_condition(tmp_path: Path):
    corpus = _index(tmp_path, "pro", [
        {"text": "水をこぼしたので、床を拭いた。", "source": "a", "sha": "a"},
        {"text": "水をこぼしたので、床を拭いた。", "source": "b", "sha": "b"},
    ])
    out = _chat(tmp_path, corpus).reply("机に水をこぼしたことに気づいたら、何をするのがよいですか？")
    assert out["ability"] == "commonsense" and out["kind"] == "answer"
    assert "床を拭く" in out["text"]
    assert {s["source"] for s in out["sources"] if s["family"] == "pro"} == {"a", "b"}
    assert out["lines"][0]["reread"]
