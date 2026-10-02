from __future__ import annotations

import json
from pathlib import Path

from verantyx.family_library import FamilyLibrary
from verantyx.one import Vera
from verantyx.round3 import GeneralRouter


def _row(family: str, sha: str, **fields) -> dict:
    return {"family": family, "split": "train", "source": "test:source", "sha": sha, **fields}


def _write(corpus: Path, family: str, rows: list[dict], *, complete: bool = True) -> Path:
    source = corpus / "codex" / family / "from_pro" / "records_one.jsonl"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) +
                      ("\n" if complete else ""), encoding="utf-8")
    return source


def test_family_build_reads_complete_train_lines_and_appends(tmp_path: Path):
    corpus = tmp_path / "corpus"
    first = _row("general_qa", "one", kind="fact", domain="食べ物", q_variants=["あんこは何から作られますか？"],
                 answer="小豆と砂糖から作ります。")
    second = _row("general_qa", "two", kind="fact", domain="食べ物", q_variants=["味噌は何から作られますか？"],
                  answer="大豆から作ります。")
    source = _write(corpus, "general_qa", [first, second], complete=False)
    hidden = _row("general_qa", "hidden", kind="fact", domain="x",
                  q_variants=["秘密は何ですか？"], answer="秘密") | {"split": "heldout"}
    (source.parent / "records_two.jsonl").write_text(json.dumps(hidden, ensure_ascii=False) + "\n")
    target = tmp_path / "build" / "general_qa"
    initial = FamilyLibrary.build(corpus, "general_qa", target, leaf_cap=1)
    assert initial["rows"] == 1
    opened = FamilyLibrary(target, "general_qa")
    with source.open("ab") as stream:
        stream.write(b"\n")
    final = FamilyLibrary.build(corpus, "general_qa", target, leaf_cap=1)
    assert final["rows"] == 2 and final["new_rows"] == 1
    assert opened.ask("味噌は何から作られますか？")["verdict"] == "ANSWER"
    opened.close()
    lib = FamilyLibrary(target, "general_qa")
    answer = lib.ask("味噌は何から作られますか？")
    assert answer["verdict"] == "ANSWER"
    assert answer["source"].endswith(":two")
    assert answer["route_trace"]
    lib.close()


def test_strict_tie_slot_and_code_example(tmp_path: Path):
    corpus = tmp_path / "corpus"
    question = "あんこは何から作られますか？"
    rows = [_row("general_qa", str(i), kind="fact", domain="食べ物", q_variants=[question],
                 answer=answer) for i, answer in enumerate(("小豆です。", "別の材料です。"))]
    _write(corpus, "general_qa", rows)
    target = tmp_path / "build" / "general_qa"
    FamilyLibrary.build(corpus, "general_qa", target)
    lib = FamilyLibrary(target, "general_qa")
    assert lib.ask(question)["verdict"] == "TIED_ABSTAIN"
    assert lib.ask(question, slot="when")["verdict"] != "ANSWER"
    lib.close()
    code = _row("code_qa", "code-one", question="余分な空白をまとめるPythonの関数を書いてください。",
                answer_text="空白で分割し結合します。", code='def clean(text):\n    return " ".join(text.split())',
                usage="clean('a  b')", lang="Python", task_kind="write_function", context="文字列処理")
    _write(corpus, "code_qa", [code])
    target = tmp_path / "build" / "code_qa"
    FamilyLibrary.build(corpus, "code_qa", target)
    lib = FamilyLibrary(target, "code_qa")
    result = lib.ask(code["question"], slot="code")
    assert "def clean" in result["text"] and "そのまま示す例" in result["text"]
    assert result["sources"][0]["source"].endswith(":code-one")
    changed = lib.ask(code["question"] + "関数名はstrip_spacesにしてください。", slot="code")
    assert "def strip_spaces" in changed["text"] and "指定された関数名" in changed["text"]
    literal = lib.ask(code["question"] + "文字列「 」を「_」に変更してください。", slot="code")
    assert "'_'.join" in literal["text"] and "指定された文字列" in literal["text"]
    lib.close()


def test_one_vera_routes_live_and_document_scope(tmp_path: Path, monkeypatch):
    corpus = tmp_path / "corpus"
    _write(corpus, "general_qa", [
        _row("general_qa", "weather", kind="fact", domain="天候",
             q_variants=["雨はなぜ降りますか？"], answer="水蒸気が冷えて水滴になります。"),
        _row("general_qa", "box", kind="fact", domain="道具",
             q_variants=["青い箱は何でできていますか？"], answer="紙でできています。")])
    root = tmp_path / "build" / "round3"
    FamilyLibrary.build(corpus, "general_qa", root / "general_qa")
    vera = Vera(round3_root=root)
    hello = vera.ask("こんにちは。")
    assert hello["kind"] == "social" and hello["sources"] and hello["evidence"]
    assert {"round3.family.conversation", "round3.family.general_qa"} <= {
        s["part"] for s in hello["trace"]}
    live = vera.ask("今日の天気は？")
    assert live["verdict"] == "UNKNOWN_LIVE_DATA"
    assert live["how_to_resolve"] and live["remedy"]
    assert any(s["part"] == "round3.family.live" for s in live["trace"])
    assert vera.ask("現在の首相は誰ですか？")["verdict"] == "UNKNOWN_LIVE_DATA"
    fact = vera.ask("雨はなぜ降りますか？")
    assert fact["sources"] and fact["evidence"]
    monkeypatch.setenv("VERA_CORPUS_ROOT", str(tmp_path))
    from verantyx.chat import Chat
    chatted = Chat([]).reply("青い箱は何でできていますか？")
    assert chatted["verdict"] == "ANSWER" and chatted["sources"]
    from_docs = Vera.from_texts({"guide": "図書館は九時に開きます。"}, round3_root=root)
    missing = from_docs.ask("雨はなぜ降りますか？")
    assert missing["door"] == "document" and missing["verdict"] == "NOT_IN_DOCS"


def test_haiku_and_story_recombine_attested_lines(tmp_path: Path):
    corpus = tmp_path / "corpus"
    haiku = [
        _row("figurative_commonsense", "h1", kind="haiku", theme="台所", kigo="朝", season="春",
             lines=["朝の鍋", "湯気にあくびが", "まじってる"], haiku="朝の鍋／湯気にあくびが／まじってる"),
        _row("figurative_commonsense", "h2", kind="haiku", theme="台所", kigo="朝", season="春",
             lines=["朝の窓", "朝日がひかる", "皿の上"], haiku="朝の窓／朝日がひかる／皿の上"),
    ]
    _write(corpus, "figurative_commonsense", haiku)
    root = tmp_path / "build" / "round3"
    FamilyLibrary.build(corpus, "figurative_commonsense", root / "figurative_commonsense")
    router = GeneralRouter(root)
    made = router._compose_haiku(router.library("figurative_commonsense"), "台所の俳句を作って")
    assert made and made["text"] == "創作: 朝の鍋／湯気にあくびが／皿の上"
    assert made["reread"]["morae"] == [5, 7, 5] and len(made["sources"]) == 2

    def story(sha: str, verbs: list[str]) -> dict:
        return _row("narrative", sha, kind="story", setting="台所", tone="静か", title=sha,
                    sentences=[{"shape": shape, "text": f"太郎は台所で鍋を{verb}。"}
                               for shape, verb in zip(("start", "development", "turn", "ending"), verbs)])
    _write(corpus, "narrative", [story("s1", ["見た", "洗った", "運んだ", "置いた"]),
                                 story("s2", ["触った", "磨いた", "見た", "片付けた"])])
    FamilyLibrary.build(corpus, "narrative", root / "narrative")
    made = router._compose_story(router.library("narrative"), "台所の物語を書いて")
    assert made and made["path"] == "labelled_story_walk"
    assert len(made["evidence"]) == 4 and len(made["sources"]) == 2


def test_relation_lexicon_uses_predicates_with_same_roles(tmp_path: Path):
    corpus = tmp_path / "corpus"
    pair = _row("paraphrase_entail", "p1", kind="pair", label="paraphrase",
                s1="姉は父に電話した。", s2="姉は父に電話をかけた。", reason="同じ行為", phenomenon="表現", topic="家族")
    _write(corpus, "paraphrase_entail", [pair])
    target = tmp_path / "build" / "paraphrase_entail"
    FamilyLibrary.build(corpus, "paraphrase_entail", target)
    lib = FamilyLibrary(target, "paraphrase_entail")
    same = lib.relation_answer("『母は父に電話した。』『母は父に電話をかけた。』は同じ意味ですか？")
    assert same and same["verdict"] == "ANSWER" and same["sources"]
    assert lib.relation_answer("『母は父に電話した。』『兄は父に電話をかけた。』は同じ意味ですか？") is None
    lib.close()


def test_metaphor_and_pun_use_attested_mechanisms(tmp_path: Path):
    corpus = tmp_path / "corpus"
    rows = [
        _row("figurative_commonsense", "m1", kind="simile_metaphor", theme="動物",
             vehicle="子猫", target="人", property="体を小さく丸める",
             expression="子猫のように丸くなる", plain_meaning="人が体を丸める"),
        _row("figurative_commonsense", "p1", kind="pun", theme="台所",
             word_a="あじ", word_b="味", reading="あじ",
             pun="あじがいい！", mechanism="同じ読み"),
    ]
    _write(corpus, "figurative_commonsense", rows)
    root = tmp_path / "build" / "round3"
    FamilyLibrary.build(corpus, "figurative_commonsense", root / "figurative_commonsense")
    router = GeneralRouter(root)
    lib = router.library("figurative_commonsense")
    metaphor = router._compose_metaphor(lib, "「太郎」を「子猫」にたとえて")
    assert metaphor and metaphor["reread"]["agent"] == "太郎"
    assert metaphor["sources"][0]["source"].endswith(":m1")
    pun = router._compose_pun(lib, "「鯵」でダジャレを作って")
    assert pun and "鯵" in pun["text"] and pun["sources"][0]["source"].endswith(":p1")
