"""W5-b / W2-g2: a replay from the ledger is a typed replay and it is checked against the run's manifest.

The attack file (tests/attack/test_attack_w2g2_mapping.py) rewrote one ``map_decision`` row, re-sealed the chain and got a changed
answer with no ask. These tests use another frame, other questions and other steps (``records`` and ``decides`` rows, the manifest
alone, a cut-off tail, a ledger shared with the word chooser), and they pin the limit the documentation states: a rewrite of the
ledger AND the manifest that agree with each other is not detected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))

import map_helpers as M  # noqa: E402
from verantyx import llm_choice as lc  # noqa: E402
from verantyx.llm_choice import ChoiceCandidate, ChoiceLedger, LLMChooser, ProviderReply  # noqa: E402

FRAME = M.w2g("w02_absence")
QUESTION = "授業料の請求の処理も今回の開発に入りますか？"          # the frame says: 月謝の請求 is out of scope (D3)
YN = M.YN_JA
SCRIPT = {"records": ["D3"], "decides": "決まる", "relations": {"D3": ["矛盾", "一致"]}}     # はい contradicts D3, いいえ agrees
QUESTION_2 = "お休みの理由は、いくつかの項目から選んでもらう形にしますか？"                    # D5: 選択式
SCRIPT_2 = {"records": ["D5"], "decides": "決まる", "relations": {"D5": ["一致", "矛盾"]}}


def _run(ledger, script=SCRIPT, question=QUESTION):
    return M.ask_map(FRAME, question, YN, script, ledger=ledger)


def _calls(mapper):
    return [p.calls for p in mapper.providers]


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def _write(path, rows):
    Path(path).write_text("".join(lc._canonical(r) + "\n" for r in rows), encoding="utf-8")


def _reseal(rows, start):
    """Make the chain valid again from row ``start`` on (what an editor of the file can always do: there is no secret key)."""
    prev = rows[start - 1]["hash"] if start else lc.GENESIS
    for r in rows[start:]:
        r["prev"] = prev
        r["hash"] = lc._chain_hash(prev, {k: v for k, v in r.items() if k != "hash"})
        prev = r["hash"]


def _decision(rows, step):
    return next(i for i, r in enumerate(rows) if r.get("type") == "map_decision" and r.get("step") == step)


def _first_run(tmp_path, script=SCRIPT, question=QUESTION):
    path = tmp_path / "ledger.jsonl"
    res, mapper = _run(ChoiceLedger(path), script, question)
    assert res["decision"] == "answer", res
    return path, res, mapper


def _manifest(path):
    return json.loads(Path(str(path) + ".manifest.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ a first run writes the manifest, a second run replays by type
def test_a_first_run_writes_a_manifest_and_a_second_run_is_a_typed_replay_with_no_ask(tmp_path):
    path, first, m1 = _first_run(tmp_path)
    assert first["mapping"]["ledger_replay"] is None
    assert all("replay" not in s for s in (first["mapping"]["step1"], first["mapping"]["decides"], *first["mapping"]["step2"]))
    man = _manifest(path)
    rows = _rows(path)
    assert man["schema"] == "conduct_map.manifest/1" and man["root"] == rows[0]["hash"]
    assert sorted(int(k) for k in man["rows"]) == [r["seq"] for r in rows if r["type"].startswith("map_")]
    assert man["rows"]["0"] == lc.row_content_sha256(rows[0])
    second, m2 = _run(ChoiceLedger(path))
    assert (second["decision"], second["answer"]) == (first["decision"], first["answer"]) and _calls(m2) == [0, 0]
    assert second["mapping"]["ledger_replay"] == {"type": "LEDGER_REPLAY", "steps": 4}          # records, decides, two pairs
    assert second["mapping"]["step1"]["replay"] == {"type": "LEDGER_REPLAY", "manifest": "MATCHED"}
    assert all(s["replay"]["manifest"] == "MATCHED" for s in second["mapping"]["step2"])


def test_the_chain_hash_and_the_row_content_hash_are_two_different_things(tmp_path):
    path, _first, _m = _first_run(tmp_path)
    row = _rows(path)[1]
    assert lc.row_content_sha256(row) != row["hash"]
    assert lc.row_content_sha256(dict(row, hash="x", prev="y")) == lc.row_content_sha256(row)      # hash and prev are not content
    assert lc.row_content_sha256(dict(row, seq=row["seq"] + 1)) != lc.row_content_sha256(row)        # seq is


# ------------------------------------------------------------------ a rewrite of the ledger alone
@pytest.mark.parametrize("step,change", [
    ("records", lambda r: r["result"].update(records=["D5"])),
    ("decides", lambda r: r["result"].update(decides="決まらない")),
])
def test_a_resealed_rewrite_of_one_decision_row_is_refused_with_no_ask(tmp_path, step, change):
    path, _first, _m = _first_run(tmp_path)
    rows = _rows(path)
    i = _decision(rows, step)
    change(rows[i])
    _reseal(rows, i)
    _write(path, rows)
    assert ChoiceLedger(path).verify()["lines"] == len(rows)           # the chain is intact: that is the point
    res, mapper = _run(ChoiceLedger(path))
    assert _calls(mapper) == [0, 0]
    assert (res["decision"], res["escalate_reason"], res["escalate_detail"]) == ("escalate", "MAPPING_UNSETTLED", "LEDGER_INTEGRITY")
    assert res["mapping"]["outcome"] == "ESCALATED:MAPPING_UNSETTLED/LEDGER_INTEGRITY"
    detail = res["mapping"]["step1"]["detail"] if res["mapping"]["step1"] else None
    assert detail == f"LEDGER_MISMATCH:ROW {rows[i]['seq']}", res["mapping"]
    assert res["answer"] is None and res["mapping"]["ledger_replay"] is None


def test_a_rewrite_of_the_first_row_is_a_root_mismatch(tmp_path):
    path, _first, _m = _first_run(tmp_path)
    rows = _rows(path)
    rows[0]["ts"] = "2000-01-01T00:00:00Z"                              # the first row is a map row: its content changes too
    _reseal(rows, 0)
    _write(path, rows)
    mapper = M.mapper_for(FRAME, YN, SCRIPT, ledger=ChoiceLedger(path))
    assert mapper.ledger.manifest_mismatch("map_") == "ROOT"
    res, mapper = _run(ChoiceLedger(path))
    assert res["decision"] == "escalate" and res["escalate_detail"] == "LEDGER_INTEGRITY" and _calls(mapper) == [0, 0]
    assert res["mapping"]["step1"]["detail"] == "LEDGER_MISMATCH:ROOT"


# ------------------------------------------------------------------ a rewrite of the manifest alone, a cut-off tail
def test_a_rewritten_manifest_with_an_intact_ledger_is_refused(tmp_path):
    path, _first, _m = _first_run(tmp_path, SCRIPT_2, QUESTION_2)
    mp = Path(str(path) + ".manifest.json")
    man = json.loads(mp.read_text(encoding="utf-8"))
    seq = sorted(int(k) for k in man["rows"])[2]
    man["rows"][str(seq)] = "0" * 64
    mp.write_text(lc._canonical(man) + "\n", encoding="utf-8")
    res, mapper = _run(ChoiceLedger(path), SCRIPT_2, QUESTION_2)
    assert _calls(mapper) == [0, 0] and res["decision"] == "escalate"
    assert res["mapping"]["step1"]["detail"] == f"LEDGER_MISMATCH:ROW {seq}"


def test_a_cut_off_tail_keeps_the_chain_valid_and_is_found_by_the_manifest(tmp_path):
    path, _first, _m = _first_run(tmp_path)
    rows = _rows(path)
    last = rows[-1]
    _write(path, rows[:-1])
    assert ChoiceLedger(path).verify()["lines"] == len(rows) - 1        # a shorter chain is still a chain
    res, mapper = _run(ChoiceLedger(path))
    assert _calls(mapper) == [0, 0] and res["decision"] == "escalate" and res["escalate_detail"] == "LEDGER_INTEGRITY"
    assert res["mapping"]["step1"]["detail"] == f"LEDGER_MISMATCH:MISSING_ROW {last['seq']}"


def test_a_manifest_that_is_not_a_manifest_is_named(tmp_path):
    path, _first, _m = _first_run(tmp_path)
    Path(str(path) + ".manifest.json").write_text("{not json", encoding="utf-8")
    res, mapper = _run(ChoiceLedger(path))
    assert _calls(mapper) == [0, 0] and res["mapping"]["step1"]["detail"] == "LEDGER_MISMATCH:MANIFEST_UNREADABLE"


def test_a_ledger_with_map_rows_and_no_manifest_is_refused_not_replayed(tmp_path):
    path, _first, _m = _first_run(tmp_path)
    old = tmp_path / "old.jsonl"
    old.write_bytes(path.read_bytes())                                   # the same rows, no manifest next to them
    res, mapper = _run(ChoiceLedger(old))
    assert _calls(mapper) == [0, 0] and res["decision"] == "escalate" and res["escalate_detail"] == "LEDGER_INTEGRITY"
    assert res["mapping"]["step1"]["detail"] == "LEDGER_MISMATCH:NO_MANIFEST"
    assert not Path(str(old) + ".manifest.json").exists()               # nothing was written behind the refusal


# ------------------------------------------------------------------ the documented limit
def test_documented_limit_a_rewrite_of_the_ledger_and_the_manifest_together_is_replayed(tmp_path):
    """docs/CONDUCT_ASK.md 14.5: the manifest is a file too. Whoever can rewrite the ledger can rewrite the manifest to agree with it;
    what the manifest protects against is a rewrite of ONE of the two. This test pins what is NOT protected."""
    path, first, _m = _first_run(tmp_path)
    assert first["answer"] == "いいえ"
    rows = _rows(path)
    for r in rows:
        if r.get("type") == "map_decision" and r.get("step") == "relation":
            r["result"]["relation"] = {"矛盾": "一致", "一致": "矛盾"}[r["result"]["relation"]]       # swap the two answers
    _reseal(rows, 1)
    _write(path, rows)
    man = _manifest(path)
    man["root"] = rows[0]["hash"]
    for r in rows:
        if str(r["seq"]) in man["rows"]:
            man["rows"][str(r["seq"])] = lc.row_content_sha256(r)
    Path(str(path) + ".manifest.json").write_text(lc._canonical(man) + "\n", encoding="utf-8")
    res, mapper = _run(ChoiceLedger(path))
    assert _calls(mapper) == [0, 0] and res["mapping"]["ledger_replay"] is not None
    assert (res["decision"], res["answer"]) == ("answer", "はい")           # the forged answer is replayed: not detected


# ------------------------------------------------------------------ the same ledger as the word chooser; an in-memory ledger
CANDS = [ChoiceCandidate("保管"), ChoiceCandidate("廃棄")]


def _chooser(ledger):
    def pick(term):
        def reply(prompt):
            shown = [json.loads(line.split(": ", 1)[1])["term"] for line in prompt.split("\n")
                     if line[:1].isdigit() and ": {" in line]
            return json.dumps({"choice": shown.index(term)})
        return reply

    class Fake:
        name, model, effort = "fake", "fake-model", "none"

        def __init__(self):
            self.n = 0

        def ask(self, prompt):
            self.n += 1
            return ProviderReply.success(pick("保管")(prompt), self.name, self.model, self.effort)

    return LLMChooser(Fake(), ledger, order_source=lambda n: list(range(n)))


def test_a_ledger_shared_with_the_word_chooser_still_replays_and_still_checks(tmp_path):
    path = tmp_path / "shared.jsonl"
    ledger = ChoiceLedger(path)
    assert _chooser(ledger).choose("収納", CANDS, "どれを選びますか？").status == "ADOPTED"      # word rows first
    first, _m1 = _run(ledger)
    assert first["decision"] == "answer"
    assert _chooser(ledger).choose("片付け", CANDS, "どれを選びますか？").status == "ADOPTED"   # word rows in the middle
    second, m2 = _run(ChoiceLedger(path))
    assert _calls(m2) == [0, 0] and second["mapping"]["ledger_replay"] is not None
    assert (second["decision"], second["answer"]) == (first["decision"], first["answer"])
    assert {e["type"] for e in ChoiceLedger(path).entries()} >= {"ask", "decision", "map_ask", "map_decision"}
    man = _manifest(path)                                                # the manifest names the map rows and nothing else
    entries = ChoiceLedger(path).entries()
    assert {int(k) for k in man["rows"]} == {e["seq"] for e in entries if e["type"].startswith("map_")}
    assert man["root"] == entries[0]["hash"]


def test_the_word_chooser_alone_never_writes_a_manifest(tmp_path):
    path = tmp_path / "words.jsonl"
    assert _chooser(ChoiceLedger(path)).choose("収納", CANDS, "どれを選びますか？").status == "ADOPTED"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["words.jsonl"]


def test_an_in_memory_ledger_shared_by_two_mappers_replays_for_the_second():
    shared = ChoiceLedger(None)
    first, m1 = _run(shared)
    assert first["decision"] == "answer" and sum(_calls(m1)) > 0
    second, m2 = _run(shared)
    assert _calls(m2) == [0, 0] and second["mapping"]["ledger_replay"] == {"type": "LEDGER_REPLAY", "steps": 4}
    assert shared.read_manifest()["root"] == shared.entries()[0]["hash"]
    assert (second["decision"], second["answer"]) == (first["decision"], first["answer"])


def test_an_in_memory_ledger_with_map_rows_and_no_manifest_is_refused():
    shared = ChoiceLedger(None)
    _run(shared)
    shared._memory_manifest = None                                       # the object lost its manifest
    res, mapper = _run(shared)
    assert _calls(mapper) == [0, 0] and res["mapping"]["step1"]["detail"] == "LEDGER_MISMATCH:NO_MANIFEST"


def test_append_alone_does_not_touch_the_manifest(tmp_path):
    ledger = ChoiceLedger(tmp_path / "plain.jsonl")
    ledger.append({"type": "ask", "x": 1})
    assert ledger.read_manifest() is None and ledger.manifest_mismatch("map_") is None
    ledger.append_manifested({"type": "map_reuse", "x": 2})
    assert ledger.read_manifest()["rows"].keys() == {"1"} and ledger.manifest_mismatch("map_") is None
