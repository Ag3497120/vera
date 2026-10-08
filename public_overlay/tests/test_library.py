from __future__ import annotations

from verantyx import conduct_tree, surface
from verantyx.base import Base
from verantyx.library import Library
from verantyx.lang import ja_topic_match


def rows():
    return [
        {"scene": "庭（朝）", "text": "校庭で黒猫が跳ねた。"},
        {"scene": "庭（朝）", "text": "花壇で紫陽花が咲いた。"},
        {"scene": "港（夕方）", "text": "港で汽船が揺れた。"},
        {"scene": "港（夕方）", "text": "桟橋で漁師が休んだ。"},
    ]


def test_leaf_cap_and_names_survive_tokenizer():
    lib = Library.from_records(rows(), leaf_cap=1)
    assert len(lib.leaves) == 4
    assert all(len(lib.records[name]) <= 1 for name in lib.leaves)
    assert set(lib.leaves) == {"庭（朝）・一", "庭（朝）・二", "港（夕方）・一", "港（夕方）・二"}
    for name in lib.leaves:
        assert ja_topic_match(f"{name}は花壇である。")[0] == name


def test_own_content_words_reach_every_sentence():
    lib = Library.from_records(rows(), leaf_cap=1)
    for row in rows():
        result = lib.ask(row["text"])
        assert any(text == row["text"] for text, _, _ in result["sentences"]), result


def test_ask_never_scans_all_sentences():
    lib = Library.from_records(rows(), leaf_cap=1)
    before = lib.sentences_examined
    lib.ask("紫陽花はどこで咲いた？")
    assert lib.sentences_examined - before <= 3 * lib.leaf_cap


def test_frame_fallback_is_predicate_keyed_and_argument_narrowed():
    rows = [
        {"scene": f"庭（{i}）", "text": f"{noun}が跳ねた。"}
        for i, noun in enumerate(("黒猫", "白犬", "赤狐", "青鳥"))
    ] + [{"scene": "港（朝）", "text": "汽船が揺れた。"}]
    lib = Library.from_records(rows, leaf_cap=1, frame_cap=2)
    before = lib.frames_examined
    result = lib.ask("白犬が跳ねた。")
    assert result["sentences"][0][0] == "白犬が跳ねた。"
    # Force an ambiguous tree descent and inspect the predicate posting list.
    result = lib.ask("跳ねた。")
    assert result["path"] == "fallback_frames"
    assert result["frames_touched"] == 2
    assert result["frame_cap_hit"] is True
    assert lib.frames_examined - before <= 2
    assert all("揺れた" not in text for text, _, _ in result["sentences"])
    assert lib.ask("飛んだ。")["path"] == "refused"


def test_fallback_uses_read_records_roles_and_survives_save(tmp_path):
    lib = Library.from_records([
        {"scene": "連絡（朝）", "text": "花子が太郎に資料を渡した。"},
        {"scene": "連絡（夜）", "text": "佳子が次郎に手紙を渡した。"},
    ], leaf_cap=1)
    assert "渡す" in lib.frames_by_predicate
    assert len(lib.frames_by_argument["渡す"]["資料"]) == 1
    result = lib.ask("渡した。")
    assert result["path"] == "fallback_frames"
    assert result["frames_touched"] == 2
    lib.save(tmp_path)
    loaded = Library.load(tmp_path)
    answer = loaded.ask("渡した。")
    assert answer["sentences"] == result["sentences"]
    assert answer["frames_touched"] == result["frames_touched"]


def test_save_load_identical_answers(tmp_path):
    lib = Library.from_records(rows(), leaf_cap=1)
    expected = [{k: v for k, v in lib.ask(q).items() if k != "ms"}
                for q in ("黒猫が跳ねた。", "汽船が揺れた。", "宇宙船が飛ぶ。")]
    lib.save(tmp_path)
    loaded = Library.load(tmp_path)
    actual = [{k: v for k, v in loaded.ask(q).items() if k != "ms"}
              for q in ("黒猫が跳ねた。", "汽船が揺れた。", "宇宙船が飛ぶ。")]
    assert actual == expected


def test_conductive_wiring_trace_routes_and_abstains(monkeypatch):
    calls = {"faces": 0, "descend": 0, "surface": 0}
    original_faces = conduct_tree.distinct_faces
    original_descend = conduct_tree.descend
    original_surface = surface.route

    def faces(*args, **kwargs):
        calls["faces"] += 1
        return original_faces(*args, **kwargs)

    def descend(*args, **kwargs):
        calls["descend"] += 1
        return original_descend(*args, **kwargs)

    def route(*args, **kwargs):
        calls["surface"] += 1
        return original_surface(*args, **kwargs)

    monkeypatch.setattr(conduct_tree, "distinct_faces", faces)
    monkeypatch.setattr(conduct_tree, "descend", descend)
    monkeypatch.setattr(surface, "route", route)

    lib = Library.from_records(rows(), leaf_cap=1)
    before_route = calls["surface"]
    routed = lib.ask("校庭で黒猫が跳ねた。")
    assert calls["surface"] > before_route
    before_abstention = calls["surface"]
    abstained = lib.ask("宇宙船が飛んだ。")
    assert calls["surface"] > before_abstention
    assert routed["path"] == "conduct"
    assert routed["route_trace"]["verdict"] == "ROUTED"
    assert abstained["route_trace"]["verdict"] == "UNKNOWN_NO_ROUTE"
    assert abstained["verdict"] == "UNKNOWN_NO_ROUTE"
    assert abstained["how_to_resolve"]
    unseen_subject = lib.ask("宇宙船が跳ねた。")
    assert unseen_subject["route_trace"]["verdict"] == "UNKNOWN_NO_ROUTE"
    assert unseen_subject["route_trace"]["anchor"] == "宇宙船"

    base = Base()
    base.add("庭", "校庭で黒猫が跳ねた。")
    base.add("港", "港で汽船が揺れた。")
    base.build()
    assert base.lower("黒猫が跳ねた。") == "庭"
    assert base.last_route["verdict"] == "ROUTED"
    assert base.lower("宇宙船が飛んだ。") is None
    assert base.last_route["verdict"] == "UNKNOWN_NO_ROUTE"
    assert calls["faces"] >= 2
    assert calls["descend"] >= 5
    assert calls["surface"] >= 5


def test_conductive_equal_top_abstains():
    tree = conduct_tree.build({
        "a": {"共有": {"同じ": 1}, "甲": {"甲面": 1}},
        "b": {"共有": {"同じ": 1}, "乙": {"乙面": 1}},
    })
    outcome = conduct_tree.descend(tree, ["共有"])
    assert outcome["verdict"] == "UNKNOWN_NO_ROUTE"
    assert outcome["stopped_at"] == "root"


def test_base_english_question_words_do_not_become_subjects():
    base = Base()
    base.add("garden", "The black cat jumped in the garden.")
    base.add("harbor", "The boat rocked in the harbor.")
    base.build()
    assert base.lower("Where did the black cat jump?") == "garden"
    assert base.lower("Which boat rocked in the harbor?") == "harbor"


def test_compact_surface_tie_refuses_to_choose_a_document():
    base = Base()
    base.add("first", "黒猫が跳ねた。")
    base.add("second", "黒猫が跳ねた。")
    base.build()
    assert base.lower("黒猫が跳ねた。") is None
    assert base.last_route["verdict"] == "UNKNOWN_NO_ROUTE"


def test_version_two_checkpoint_without_conductive_tree_loads(tmp_path):
    lib = Library.from_records(rows(), leaf_cap=1)
    del lib.routing_root
    lib.save(tmp_path)
    loaded = Library.load(tmp_path)
    assert loaded.ask("校庭で黒猫が跳ねた。")['path'] == "conduct"
