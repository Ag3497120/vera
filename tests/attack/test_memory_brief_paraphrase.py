import pytest

from verantyx.memory_brief import compile_brief


class Memory:
    def __init__(self, records=(), superseded=()):
        self.records = list(records)
        self.superseded = dict.fromkeys(superseded)

    def active(self):
        return list(self.records)

    def ask_about(self, subject, attribute, *, kind, require_fresh):
        assert require_fresh is True
        matches = []
        for record in self.records:
            slots = record.get("slots", {})
            if record.get("kind") != kind or slots.get("subject") != subject:
                continue
            if attribute is not None and slots.get("attribute") != attribute:
                continue
            matches.append(record["id"])
        return {"records": matches}


def fact(rid, sentence, *, subject="会議", attribute="場所", value="東京", ts="2024-01-01"):
    return {
        "id": rid,
        "kind": "FACT",
        "sentence": sentence,
        "slots": {"subject": subject, "attribute": attribute, "value": value},
        "ts": ts,
    }


def task(rid, state, sentence):
    return {
        "id": rid,
        "kind": "TASK",
        "sentence": sentence,
        "slots": {"subject": "準備", "state": state},
        "ts": "2024-01-01",
    }


def constrained_focus_records(target_sentence):
    target = fact("r1", target_sentence)
    other = fact(
        "r2",
        "旅行の日程は来週です。参加者が迷わないよう、事前に詳細な予定と移動案内を共有します。",
        subject="旅行",
        attribute="日程",
        value="来週",
        ts="2023-01-01",
    )
    records = [target, other]
    single_briefs = [
        f"[id:{chosen['id']}] {chosen['sentence']}\nDropped record ids: {omitted['id']}"
        for chosen, omitted in ((target, other), (other, target))
    ]
    budget = max(map(len, single_briefs))
    both = f"[id:r1] {target_sentence}\n[id:r2] {other['sentence']}"
    assert len(both) > budget
    return Memory(records), budget


def test_empty_memory_returns_empty_string():
    assert compile_brief(Memory(), 0) == ""


@pytest.mark.parametrize("budget", [True, -1, 1.5, "10"])
def test_invalid_budget_is_rejected(budget):
    with pytest.raises(ValueError):
        compile_brief(Memory(), budget)


def test_focus_normalizes_width_and_case():
    memory = Memory([
        fact("r1", "識別子 ABC の記録です。", subject="識別子", attribute="値", value="ABC"),
        fact("r2", "別の記録です。", subject="別項目", attribute="値", value="xyz", ts="2023-01-01"),
    ])

    brief = compile_brief(memory, 500, focus="ａｂｃ")

    assert brief.startswith("[id:r1]")


def test_focus_precedes_kind_priority():
    focused_fact = fact("fact", "会議の場所は東京です。")
    other_invariant = {
        "id": "invariant",
        "kind": "INVARIANT",
        "sentence": "毎朝は水を飲みます。",
        "slots": {"subject": "朝", "value": "水"},
        "ts": "2020-01-01",
    }

    brief = compile_brief(Memory([other_invariant, focused_fact]), 500, focus="会議の場所")

    assert brief.startswith("[id:fact]")


def test_polite_and_plain_wording_keep_the_same_focused_record():
    polite, budget = constrained_focus_records(
        "会議の場所は東京です。参加者が迷わないよう、事前に会場案内を共有します。"
    )
    plain, _ = constrained_focus_records(
        "会議の場所は東京だ。参加者が迷わないよう、事前に会場案内を共有する。"
    )

    polite_brief = compile_brief(polite, budget, focus="会議の場所")
    plain_brief = compile_brief(plain, budget, focus="会議の場所")

    assert polite_brief.startswith("[id:r1]")
    assert plain_brief.startswith("[id:r1]")


@pytest.mark.xfail(strict=False, reason="DEFECT: synonymous word order can lose literal focus ranking and change the budgeted selection")
def test_word_order_paraphrase_keeps_the_same_budget_verdict():
    direct, budget = constrained_focus_records(
        "会議の場所は東京です。参加者が迷わないよう、事前に会場案内を共有します。"
    )
    reordered, _ = constrained_focus_records(
        "東京で会議を開きます。参加者が迷わないよう、事前に会場案内を共有します。"
    )

    direct_brief = compile_brief(direct, budget, focus="会議の場所")
    reordered_brief = compile_brief(reordered, budget, focus="会議の場所")

    assert direct_brief.startswith("[id:r1]")
    assert reordered_brief.startswith("[id:r1]")


def test_entity_swap_is_reflected_in_the_rendered_record():
    tokyo = Memory([fact("place", "会議の場所は東京です。", value="東京")])
    osaka = Memory([fact("place", "会議の場所は大阪です。", value="大阪")])

    tokyo_brief = compile_brief(tokyo, 200)
    osaka_brief = compile_brief(osaka, 200)

    assert tokyo_brief == "[id:place] 会議の場所は東京です。"
    assert osaka_brief == "[id:place] 会議の場所は大阪です。"
    assert tokyo_brief != osaka_brief


def test_number_swap_is_reflected_in_the_rendered_record():
    two = Memory([fact("floor", "会議は2階です。", attribute="階", value="2階")])
    three = Memory([fact("floor", "会議は3階です。", attribute="階", value="3階")])

    assert compile_brief(two, 100) == "[id:floor] 会議は2階です。"
    assert compile_brief(three, 100) == "[id:floor] 会議は3階です。"


def test_closed_task_is_omitted_and_accounted_for():
    memory = Memory([
        task("done", "完了", "準備は完了しました。"),
        task("open", "進行中", "準備を進めています。"),
    ])

    brief = compile_brief(memory, 200)

    assert brief == "[id:open] 準備を進めています。\nDropped record ids: done"


def test_unaskable_record_is_accounted_for_as_dropped():
    unaskable = {
        "id": "unaskable",
        "kind": "FACT",
        "sentence": "根拠レコードではありません。",
        "slots": {"attribute": "状態", "value": "不明"},
    }

    assert compile_brief(Memory([unaskable]), 100) == "Dropped record ids: unaskable"


def test_superseded_record_is_removed_before_dropped_accounting():
    old = fact("old", "会議の場所は東京です。")
    current = fact("current", "会議の場所は大阪です。", value="大阪")

    brief = compile_brief(Memory([old, current], superseded=["old"]), 200)

    assert brief == "[id:current] 会議の場所は大阪です。"


def test_too_small_budget_raises_instead_of_hiding_dropped_ids():
    with pytest.raises(ValueError, match="too small"):
        compile_brief(Memory([fact("r1", "会議の場所は東京です。")]), 0)
