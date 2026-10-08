"""Independent differential checks for the typed memory frame."""
import json
import random

import pytest

from verantyx.memory_frame import Memory, Resolver, WriteRejected, normalize_np, parse_choice


_SLOTS = {
    "FACT": ("subject", "attribute", "value"),
    "DECISION": ("subject", "choice"),
    "INVARIANT": ("subject", "rule"),
    "TASK": ("subject", "state"),
    "LESSON": ("situation", "fix"),
    "QUESTION": ("subject", "question"),
}
_TASK_STATES = ("未着手", "進行中", "完了", "停止", "保留")


def _reference_normalize(text):
    """Small contract model: trim and remove Japanese case/genitive particles."""
    particles = set("はがのをにでと")
    return "".join(char for char in text.strip() if char not in particles)


def _reference_shape_ok(kind, slots):
    return kind in _SLOTS and set(slots) == set(_SLOTS[kind])


def _reference_value_ok(value):
    text = str(value).strip()
    separators = "。！？!?\n\r「」『』"
    return bool(text) and not any(char in separators for char in text)


def _reference_choice(reply, count):
    """Strict model of the documented JSON-only, bounded-choice response."""
    try:
        data = json.loads(reply)
    except (TypeError, ValueError):
        return False
    if not isinstance(data, dict) or set(data) != {"choice"}:
        return False
    choice = data["choice"]
    if choice is None:
        return None
    if type(choice) is not int or not 0 <= choice < count:
        return False
    return choice


class _ReferenceStore:
    """Naive event projection, independent of the implementation's maps."""

    def __init__(self):
        self.rows = {}
        self.replaced = set()

    def append(self, row):
        old = row.get("supersedes")
        if old and old not in self.rows:
            raise ValueError("superseded row must already exist")
        self.rows[row["id"]] = dict(row)
        if old:
            self.replaced.add(old)

    def active(self):
        return [row for key, row in self.rows.items() if key not in self.replaced]


def _projection(rows):
    return [
        (row["kind"], tuple(sorted(row["slots"].items())), row["sentence"])
        for row in rows
    ]


def _memory_without_disk(path):
    memory = Memory(str(path), now=lambda: "2026-01-02T03:04:05")
    # Keep write-gate tests in memory; the separate log test exercises disk reload.
    memory._append = memory._apply
    return memory


def _base_slots(kind):
    return {name: f"値{index}" for index, name in enumerate(_SLOTS[kind])}


def test_generated_noun_normalization_matches_independent_reference():
    rng = random.Random(813)
    alphabet = "未読の上限はがをにでとルーターxyz 　"
    samples = ["未読の上限", "ルーターは未読の上限", "  値  "]
    samples.extend(
        "".join(rng.choice(alphabet) for _ in range(rng.randrange(1, 25)))
        for _ in range(128)
    )
    for sample in samples:
        assert normalize_np(sample) == _reference_normalize(sample)


def test_generated_slot_shapes_match_reference_gate(tmp_path):
    rng = random.Random(29)
    cases = []
    for kind, names in _SLOTS.items():
        base = _base_slots(kind)
        for name in names:
            missing = dict(base)
            del missing[name]
            cases.append((kind, missing))
        extra = dict(base)
        extra["unexpected"] = "value"
        cases.append((kind, extra))
    rng.shuffle(cases)

    for kind, slots in cases:
        expected = _reference_shape_ok(kind, slots)
        memory = _memory_without_disk(tmp_path / "unused.jsonl")
        try:
            memory.write(kind, "attacker", **slots)
            observed = True
        except WriteRejected:
            observed = False
        assert observed is expected
        assert memory.records == {}


@pytest.mark.parametrize("bad", ["", "   ", "a。b", "a\nb", "「値」"])
def test_generated_bad_slot_text_is_rejected_before_append(tmp_path, bad):
    expected = _reference_value_ok(bad)
    memory = _memory_without_disk(tmp_path / "unused.jsonl")
    try:
        memory.write("TASK", "attacker", subject=bad, state="完了")
        observed = True
    except WriteRejected:
        observed = False
    assert observed is expected
    assert memory.records == {}


def test_fact_and_invariant_require_a_witness(tmp_path):
    for kind in ("FACT", "INVARIANT"):
        memory = _memory_without_disk(tmp_path / "unused.jsonl")
        with pytest.raises(WriteRejected):
            memory.write(kind, "attacker", **_base_slots(kind))
        assert memory.records == {}


def test_unknown_witness_kind_is_rejected_before_append(tmp_path):
    memory = _memory_without_disk(tmp_path / "unused.jsonl")
    with pytest.raises(WriteRejected):
        memory.write(
            "DECISION",
            "attacker",
            witness={"kind": "invented"},
            subject="機能",
            choice="採用",
        )
    assert memory.records == {}


def test_task_state_is_a_closed_choice_without_a_resolver(tmp_path):
    for state in ("queued", "未分類", "完了予定"):
        memory = _memory_without_disk(tmp_path / "unused.jsonl")
        expected = state in _TASK_STATES
        try:
            memory.write("TASK", "attacker", subject="機能", state=state)
            observed = True
        except WriteRejected:
            observed = False
        assert observed is expected
        assert memory.records == {}


def test_resolver_adopts_only_the_shared_canonical_candidate():
    class TargetAsker:
        def __init__(self, target):
            self.target = target

        def __call__(self, prompt):
            block = prompt.split("候補:\n", 1)[1].split("\n答えは", 1)[0]
            candidates = [line.split(": ", 1)[1] for line in block.splitlines()]
            return json.dumps({"choice": candidates.index(self.target)})

    for size in range(2, 6):
        options = [f"候補{i}" for i in range(size)]
        target = options[-1]
        result = Resolver(TargetAsker(target), seed=size).resolve("別表現", options)
        assert result["status"] == "ADOPT"
        assert result["choice"] == target
        assert [ask["picked"] for ask in result["asks"]] == [size - 1, size - 1]


def test_generated_json_choices_match_independent_reference():
    for count in range(1, 7):
        replies = [json.dumps({"choice": None})]
        replies.extend(json.dumps({"choice": index}) for index in range(count))
        replies.extend(
            [
                json.dumps({"choice": -1}),
                json.dumps({"choice": count}),
                "not json",
                '{"other": 0}',
                '{"choice": "0"}',
            ]
        )
        for reply in replies:
            expected = _reference_choice(reply, count)
            observed = parse_choice(reply, count)
            assert observed == expected
            assert (observed is False) == (expected is False)


def test_append_reload_and_supersession_match_reference_projection(tmp_path):
    path = tmp_path / "events.jsonl"
    memory = Memory(str(path), now=lambda: "2026-01-02T03:04:05")
    reference = _ReferenceStore()

    first = memory.write("TASK", "tester", subject="機能甲", state="進行中")
    reference.append(first)
    second = memory.write(
        "TASK", "tester", subject="機能乙", state="完了", supersedes=first["id"]
    )
    reference.append(second)

    reopened = Memory(str(path), now=lambda: "2026-01-02T03:04:05")
    assert _projection(reopened.active()) == _projection(reference.active())
    assert _projection(reopened.active()) == [
        ("TASK", (("state", "完了"), ("subject", "機能乙")), "機能乙の状態は完了である。")
    ]


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: a rejected missing supersession target is appended before validation",
)
def test_rejected_missing_supersession_target_does_not_append(tmp_path):
    path = tmp_path / "rejected.jsonl"
    memory = Memory(str(path), now=lambda: "2026-01-02T03:04:05")
    with pytest.raises(WriteRejected):
        memory.write(
            "FACT",
            "tester",
            witness={"kind": "testimony"},
            supersedes="missing-id",
            subject="ルーター",
            attribute="未読上限",
            value="10",
        )
    reopened = Memory(str(path), now=lambda: "2026-01-02T03:04:05")
    assert reopened.active() == []


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: parser accepts a bounded choice embedded in non-JSON prose",
)
def test_choice_parser_rejects_prose_wrapped_json():
    reply = '説明文のあとに {"choice": 1}'
    expected = _reference_choice(reply, 2)
    assert expected is False
    assert parse_choice(reply, 2) is expected
