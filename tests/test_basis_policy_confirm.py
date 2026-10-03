"""W6-a D and P4: a generated sentence is put to the user as a question; only a "yes" becomes a
human-written record in a consenting sovereign, and the same question is then answered from it.

Synthetic data only. The index is built in tmp_path; the sovereign memory is created in tmp_path.
Helpers are copied here on purpose: tests/ is not a package.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

from tools.build_p4_corpus_index import build
from verantyx import sovereign as sov
from verantyx.cli import main

Q = "雨の日に傘を持たずに外出すると、どうなりますか？"
ROWS = ["雨の日に傘を持たずに出たら、髪が濡れた。", "雨の日に傘を持たずに出たら、服が濡れた。"]
BODIES = ROWS


@pytest.fixture(autouse=True)
def _no_outside_environment(monkeypatch):
    for name in ("VERA_SOVEREIGN_ROOT", "VERA_SOVEREIGN_STORE", "VERA_P4_INDEX"):
        monkeypatch.delenv(name, raising=False)


def _world(tmp_path: Path, monkeypatch, *, consent: bool = True, sid: str = "s1", configure: bool = True):
    src = tmp_path / "local.jsonl"
    src.write_text("".join(json.dumps({"text": t, "source": f"g{i}", "scene": "雨", "sha": f"h{i}"},
                                      ensure_ascii=False) + "\n" for i, t in enumerate(ROWS)),
                   encoding="utf-8")
    build(src, tmp_path / "idx" / "local.db", "local")
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "idx"))
    root = tmp_path / "sov"
    assert sov.create(str(root), sid, "owner-a", consent_promote=consent)["verdict"] == "CREATED"
    if configure:
        monkeypatch.setenv("VERA_SOVEREIGN_ROOT", str(root))
        monkeypatch.setenv("VERA_SOVEREIGN_STORE", sid)
    return str(root), sid


def _ask(tmp_path, capsys, *args, query: str = Q):
    rc = main(["--store", str(tmp_path / "s.json"), "ask", query, *args])
    return rc, json.loads(capsys.readouterr().out)


def _events(root, sid):
    return sov.open_ledger(root, sid).events()


def _file_sha(root, sid):
    return sov.sovereign_file_sha256(os.path.join(root, "stores", f"{sid}.sqlite"))


def _payload(status="HUMAN_CONFIRMED", confirm_id="abc", query=Q, claim="C1"):
    p = {"record": "basis_confirmation", "status": status, "witness": "user_confirmation",
         "confirm_id": confirm_id, "query": query, "claim": claim,
         "generated_sources": [{"family": "local", "source_id": "local:f:1", "sha": "h0"}],
         "table_version": 1}
    if status == "HUMAN_CONFIRMED":
        p["origin"] = "human_confirmed"
    return p


# ------------------------------------------------------------- the sovereign's new mouth (S4)
def test_a_consenting_sovereign_takes_the_record_as_one_decision_event(tmp_path):
    root = str(tmp_path / "sov")
    sov.create(root, "s1", "o", consent_promote=True)
    before = len(_events(root, "s1"))
    out = sov.append_basis_confirmation(root, "s1", _payload())
    assert out["verdict"] == "APPENDED" and out["wrote"] == 1 and out["store_id"] == "s1"
    evs = _events(root, "s1")
    assert len(evs) == before + 1 and evs[-1]["kind"] == "decision"
    assert evs[-1]["payload"] == _payload() and evs[-1]["id"] == out["event_id"]


def test_without_consent_nothing_is_written_not_one_byte(tmp_path):
    root = str(tmp_path / "sov")
    sov.create(root, "s1", "o", consent_promote=False)
    file_before, events_before = _file_sha(root, "s1"), _events(root, "s1")
    out = sov.append_basis_confirmation(root, "s1", _payload())
    assert out["verdict"] == "NO_CONSENT" and out["wrote"] == 0
    assert _file_sha(root, "s1") == file_before and _events(root, "s1") == events_before


def test_after_consent_is_withdrawn_the_mouth_is_closed_again(tmp_path):
    root = str(tmp_path / "sov")
    sov.create(root, "s1", "o", consent_promote=True)
    sov.set_consent(root, "s1", False)
    before = _file_sha(root, "s1")
    assert sov.append_basis_confirmation(root, "s1", _payload())["verdict"] == "NO_CONSENT"
    assert _file_sha(root, "s1") == before


def test_unknown_and_detached_stores_are_typed(tmp_path):
    root = str(tmp_path / "sov")
    sov.create(root, "s1", "o", consent_promote=True)
    assert sov.append_basis_confirmation(root, "nope", _payload())["verdict"] == "UNKNOWN_STORE"
    sov.detach(root, "s1")
    out = sov.append_basis_confirmation(root, "s1", _payload())
    assert out["verdict"] == "DETACHED" and out.get("wrote", 0) == 0


@pytest.mark.parametrize("bad", [
    {"record": "other", "status": "HUMAN_CONFIRMED"},
    {"record": "basis_confirmation", "status": "MAYBE"},
    {"record": "basis_confirmation"},
    "not a mapping",
    None,
])
def test_a_payload_of_the_wrong_shape_is_refused_without_writing(tmp_path, bad):
    root = str(tmp_path / "sov")
    sov.create(root, "s1", "o", consent_promote=True)
    before = _file_sha(root, "s1")
    out = sov.append_basis_confirmation(root, "s1", bad)
    assert out["verdict"] == "BAD_PAYLOAD" and out["wrote"] == 0
    assert _file_sha(root, "s1") == before


def test_a_decision_event_never_becomes_a_promotion_candidate(tmp_path):
    root = str(tmp_path / "sov")
    sov.create(root, "s1", "o", consent_promote=True)
    for i in range(5):
        assert sov.append_basis_confirmation(root, "s1", _payload(confirm_id=f"id{i}"))["verdict"] == "APPENDED"
    out = sov.promote(root, "s1")
    cnt = out["counts"]
    assert out["verdict"] == "NOTHING_TO_PROMOTE" and out["promoted"] == []
    assert cnt["not_a_candidate"] == 5 == cnt["events_total"] and cnt["candidates"] == 0


# ---------------------------------------------------------------------------- D: the question
def test_a_human_present_gets_a_question_not_an_answer(tmp_path, monkeypatch, capsys):
    _world(tmp_path, monkeypatch)
    rc, out = _ask(tmp_path, capsys, "--human-present")
    assert rc == 0
    assert out["kind"] == "unknown" and out["verdict"] == "CONFIRM_REQUEST"
    assert out["basis_policy"]["outcome"] == "CONFIRM_REQUEST"
    conf = out["confirm"]
    assert conf["claim"] in conf["question"] and "生成" in conf["question"] and "正しい" in conf["question"]
    assert sorted(s["text"] for s in conf["generated_sentences"]) == sorted(ROWS)
    assert all(s["family"] == "local" and s["source_id"].startswith("local:") for s in conf["generated_sentences"])
    draft = conf["draft_record"]
    assert draft["kind"] == "decision"
    assert draft["payload"]["origin"] == "human_confirmed" and draft["payload"]["witness"] == "user_confirmation"
    assert draft["payload"]["status"] == "HUMAN_CONFIRMED" and draft["payload"]["query"] == Q
    assert out["sources"] == [] and out["evidence"] == [] and "basis_origin" not in out
    assert conf["destination"]["state"] == "ACTIVE_CONSENTED"
    assert conf["id"] in conf["how_to_answer"]


def test_the_question_id_is_deterministic_and_depends_on_the_query(tmp_path, monkeypatch, capsys):
    _world(tmp_path, monkeypatch)
    ids = [_ask(tmp_path, capsys, "--human-present")[1]["confirm"]["id"] for _ in range(2)]
    assert ids[0] == ids[1] and len(ids[0]) == 24
    other = _ask(tmp_path, capsys, "--human-present", query="雨の日に傘を持たずに歩くと、どうなりますか？")[1]
    assert other["verdict"] != "CONFIRM_REQUEST" or other["confirm"]["id"] != ids[0]


def test_asking_without_confirm_never_writes_to_the_sovereign(tmp_path, monkeypatch, capsys):
    root, sid = _world(tmp_path, monkeypatch)
    before, events = _file_sha(root, sid), _events(root, sid)
    for flags in ([], ["--human-present"], ["--show-generated-reference"],
                  ["--human-present", "--show-generated-reference"]):
        _ask(tmp_path, capsys, *flags)
    assert _file_sha(root, sid) == before and _events(root, sid) == events


def test_no_pending_question_is_stored_anywhere(tmp_path, monkeypatch, capsys):
    root, sid = _world(tmp_path, monkeypatch)
    def snap():
        return sorted((p.relative_to(tmp_path).as_posix(), p.stat().st_size)
                      for p in tmp_path.rglob("*") if p.is_file())
    before = snap()
    _ask(tmp_path, capsys, "--human-present")
    assert snap() == before


# --------------------------------------------------------------------------------- yes / no
def _id(tmp_path, capsys):
    return _ask(tmp_path, capsys, "--human-present")[1]["confirm"]["id"]


def test_yes_appends_one_human_record_and_the_same_question_is_then_answered(tmp_path, monkeypatch, capsys):
    root, sid = _world(tmp_path, monkeypatch)
    cid = _id(tmp_path, capsys)
    claim = _ask(tmp_path, capsys, "--human-present")[1]["confirm"]["claim"]
    n = len(_events(root, sid))
    rc, out = _ask(tmp_path, capsys, "--confirm", cid, "yes")
    assert rc == 0 and out["verdict"] == "CONFIRMED_HUMAN_RECORD" and out["wrote"] == 1
    assert out["confirm_id"] == cid and out["store_id"] == sid and out["event_id"]
    evs = _events(root, sid)
    assert len(evs) == n + 1 and evs[-1]["kind"] == "decision"
    p = evs[-1]["payload"]
    assert p["origin"] == "human_confirmed" and p["witness"] == "user_confirmation"
    assert p["status"] == "HUMAN_CONFIRMED" and p["claim"] == claim and p["query"] == Q
    assert p["confirm_id"] == cid and p["record"] == "basis_confirmation"
    assert not ({"phrase", "cell", "occupied", "corrects"} & set(p))
    for flags in ([], ["--human-present"], ["--show-generated-reference"]):
        rc, ans = _ask(tmp_path, capsys, *flags)
        assert rc == 0 and ans["verdict"] == "ANSWER" and ans["kind"] == "answer"
        assert ans["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS" and ans["text"] == claim
        assert ans["sources"][0]["origin"] == "human_confirmed" and ans["sources"][0]["text"] == claim
        assert "basis_origin" not in ans
        assert not any(s.get("origin") == "generated" for s in ans["sources"])
    # asking again never wrote anything more
    assert len(_events(root, sid)) == n + 1


def test_no_appends_a_rejection_never_deletes_and_the_next_ask_abstains(tmp_path, monkeypatch, capsys):
    root, sid = _world(tmp_path, monkeypatch)
    cid = _id(tmp_path, capsys)
    before = _events(root, sid)
    rc, out = _ask(tmp_path, capsys, "--confirm", cid, "no")
    assert rc == 0 and out["verdict"] == "REJECTED_GENERATED_RECORDED" and out["wrote"] == 1
    after = _events(root, sid)
    assert after[:len(before)] == before and len(after) == len(before) + 1     # nothing removed
    p = after[-1]["payload"]
    assert p["status"] == "REJECTED_GENERATED" and "origin" not in p
    rc, nxt = _ask(tmp_path, capsys, "--human-present")
    assert rc == 0 and nxt["kind"] == "unknown" and nxt["verdict"] == "UNKNOWN_GENERATED_REJECTED_BY_USER"
    assert nxt["basis_policy"]["outcome"] == "ABSTAIN"
    assert nxt["basis_policy"]["sovereign"]["rejected_by_user"] == 1


def test_the_last_record_for_an_id_is_the_one_that_counts(tmp_path, monkeypatch, capsys):
    root, sid = _world(tmp_path, monkeypatch)
    cid = _id(tmp_path, capsys)
    assert _ask(tmp_path, capsys, "--confirm", cid, "yes")[1]["verdict"] == "CONFIRMED_HUMAN_RECORD"
    assert _ask(tmp_path, capsys)[1]["verdict"] == "ANSWER"
    assert _ask(tmp_path, capsys, "--confirm", cid, "no")[1]["verdict"] == "REJECTED_GENERATED_RECORDED"
    nxt = _ask(tmp_path, capsys, "--human-present")[1]
    assert nxt["kind"] == "unknown" and nxt["verdict"] == "UNKNOWN_GENERATED_REJECTED_BY_USER"
    assert _ask(tmp_path, capsys, "--confirm", cid, "yes")[1]["verdict"] == "CONFIRMED_HUMAN_RECORD"
    assert _ask(tmp_path, capsys)[1]["verdict"] == "ANSWER"
    assert len(_events(root, sid)) == 3


def test_a_sovereign_without_consent_is_not_written_and_asks_again(tmp_path, monkeypatch, capsys):
    root, sid = _world(tmp_path, monkeypatch, consent=False)
    cid = _id(tmp_path, capsys)
    assert _ask(tmp_path, capsys, "--human-present")[1]["confirm"]["destination"]["state"] == "ACTIVE_NO_CONSENT"
    before_file, before_events = _file_sha(root, sid), _events(root, sid)
    rc, out = _ask(tmp_path, capsys, "--confirm", cid, "yes")
    assert rc == 1 and out["verdict"] == "NO_CONSENT" and out["wrote"] == 0
    assert _file_sha(root, sid) == before_file and _events(root, sid) == before_events
    assert _ask(tmp_path, capsys, "--human-present")[1]["verdict"] == "CONFIRM_REQUEST"


def test_no_sovereign_configured_keeps_the_question_and_says_there_is_nowhere_to_save(tmp_path, monkeypatch, capsys):
    _world(tmp_path, monkeypatch, configure=False)
    first = _ask(tmp_path, capsys, "--human-present")[1]
    assert first["confirm"]["destination"]["state"] == "UNKNOWN_NO_SOVEREIGN"
    rc, out = _ask(tmp_path, capsys, "--confirm", first["confirm"]["id"], "yes")
    assert rc == 1 and out["verdict"] == "CONFIRM_REQUEST" and out["wrote"] == 0
    assert out["confirm"]["destination"]["state"] == "UNKNOWN_NO_SOVEREIGN"


def test_half_configured_sovereign_is_a_typed_incomplete_state(tmp_path, monkeypatch, capsys):
    root, _sid = _world(tmp_path, monkeypatch, configure=False)
    monkeypatch.setenv("VERA_SOVEREIGN_ROOT", root)
    first = _ask(tmp_path, capsys, "--human-present")[1]
    assert first["confirm"]["destination"]["state"] == "UNKNOWN_SOVEREIGN_CONFIG_INCOMPLETE"
    rc, out = _ask(tmp_path, capsys, "--confirm", first["confirm"]["id"], "yes")
    assert rc == 1 and out["wrote"] == 0
    assert out["confirm"]["destination"]["state"] == "UNKNOWN_SOVEREIGN_CONFIG_INCOMPLETE"
    monkeypatch.delenv("VERA_SOVEREIGN_ROOT")
    monkeypatch.setenv("VERA_SOVEREIGN_STORE", "s1")
    assert _ask(tmp_path, capsys, "--human-present")[1]["confirm"]["destination"]["state"] \
        == "UNKNOWN_SOVEREIGN_CONFIG_INCOMPLETE"


def test_a_detached_sovereign_is_typed_and_its_records_are_not_used(tmp_path, monkeypatch, capsys):
    root, sid = _world(tmp_path, monkeypatch)
    cid = _id(tmp_path, capsys)
    assert _ask(tmp_path, capsys, "--confirm", cid, "yes")[0] == 0
    sov.detach(root, sid)
    nxt = _ask(tmp_path, capsys, "--human-present")[1]
    assert nxt["verdict"] == "CONFIRM_REQUEST" and nxt["confirm"]["destination"]["state"] == "DETACHED"
    rc, out = _ask(tmp_path, capsys, "--confirm", cid, "yes")
    assert rc == 1 and out["wrote"] == 0


def test_a_wrong_id_writes_nothing_and_is_typed(tmp_path, monkeypatch, capsys):
    root, sid = _world(tmp_path, monkeypatch)
    before_file = _file_sha(root, sid)
    for bad in ("000000000000000000000000", "x", _id(tmp_path, capsys)[::-1]):
        rc, out = _ask(tmp_path, capsys, "--confirm", bad, "yes")
        assert rc == 1 and out["kind"] == "unknown" and out["verdict"] == "UNKNOWN_CONFIRM_ID" and out["wrote"] == 0
    assert _file_sha(root, sid) == before_file


def test_an_id_for_another_question_is_not_accepted(tmp_path, monkeypatch, capsys):
    root, sid = _world(tmp_path, monkeypatch)
    cid = _id(tmp_path, capsys)
    rc, out = _ask(tmp_path, capsys, "--confirm", cid, "yes", query="雨の日に傘を持たずに歩くと、どうなりますか？")
    assert rc == 1 and out["verdict"] == "UNKNOWN_CONFIRM_ID" and out["wrote"] == 0
    assert _events(root, sid) == []


def test_two_confirmed_records_with_different_claims_abstain(tmp_path, monkeypatch, capsys):
    root, sid = _world(tmp_path, monkeypatch)
    sov.append_basis_confirmation(root, sid, _payload(confirm_id="aaa", claim="主張A"))
    sov.append_basis_confirmation(root, sid, _payload(confirm_id="bbb", claim="主張B"))
    rc, out = _ask(tmp_path, capsys, "--human-present")
    assert rc == 0 and out["kind"] == "unknown" and out["verdict"] == "AMBIGUOUS_CONFIRMED_RECORDS"
    assert out["basis_policy"]["outcome"] == "ABSTAIN"
    assert out["sources"] == [] and "text" in out


def test_two_confirmed_records_with_the_same_claim_are_not_a_split(tmp_path, monkeypatch, capsys):
    root, sid = _world(tmp_path, monkeypatch)
    sov.append_basis_confirmation(root, sid, _payload(confirm_id="aaa", claim="主張A"))
    sov.append_basis_confirmation(root, sid, _payload(confirm_id="bbb", claim="主張A"))
    rc, out = _ask(tmp_path, capsys)
    assert rc == 0 and out["verdict"] == "ANSWER" and out["text"] == "主張A"


def test_after_consent_is_withdrawn_the_records_are_not_used(tmp_path, monkeypatch, capsys):
    root, sid = _world(tmp_path, monkeypatch)
    cid = _id(tmp_path, capsys)
    assert _ask(tmp_path, capsys, "--confirm", cid, "yes")[0] == 0
    assert _ask(tmp_path, capsys)[1]["verdict"] == "ANSWER"
    sov.set_consent(root, sid, False)
    out = _ask(tmp_path, capsys)[1]
    assert out["kind"] == "unknown" and out["verdict"] == "UNKNOWN_GENERATED_BASIS_ONLY"
    assert _ask(tmp_path, capsys, "--human-present")[1]["verdict"] == "CONFIRM_REQUEST"


def test_a_record_for_another_query_is_not_used(tmp_path, monkeypatch, capsys):
    root, sid = _world(tmp_path, monkeypatch)
    sov.append_basis_confirmation(root, sid, _payload(query="全く別の問い", claim="主張A"))
    out = _ask(tmp_path, capsys, "--human-present")[1]
    assert out["verdict"] == "CONFIRM_REQUEST"


def test_reading_the_sovereign_does_not_change_its_bytes(tmp_path, monkeypatch, capsys):
    root, sid = _world(tmp_path, monkeypatch)
    sov.append_basis_confirmation(root, sid, _payload(confirm_id="aaa", claim="主張A"))
    before = sorted((p.relative_to(root).as_posix(), p.read_bytes()) for p in Path(root).rglob("*") if p.is_file())
    for flags in ([], ["--human-present"], ["--human-present", "--show-generated-reference"]):
        _ask(tmp_path, capsys, *flags)
    after = sorted((p.relative_to(root).as_posix(), p.read_bytes()) for p in Path(root).rglob("*") if p.is_file())
    assert after == before


def test_the_confirmation_never_leaks_outside_its_own_keys(tmp_path, monkeypatch, capsys):
    _world(tmp_path, monkeypatch)
    out = _ask(tmp_path, capsys, "--human-present")[1]
    rest = {k: v for k, v in out.items() if k != "confirm"}
    text = json.dumps(rest, ensure_ascii=False)
    for body in BODIES:
        assert body not in text


def test_an_unreadable_sovereign_file_is_a_typed_state_and_not_a_crash(tmp_path, monkeypatch, capsys):
    root, sid = _world(tmp_path, monkeypatch)
    Path(root, "stores", f"{sid}.sqlite").write_bytes(b"this is not a database" * 50)
    rc, out = _ask(tmp_path, capsys, "--human-present")
    assert rc == 0 and out["verdict"] == "CONFIRM_REQUEST"
    state = out["confirm"]["destination"]["state"]
    assert state not in ("ACTIVE_CONSENTED", "ACTIVE_NO_CONSENT") and state.startswith(("UNREADABLE", "UNKNOWN"))
    cid = out["confirm"]["id"]
    rc2, out2 = _ask(tmp_path, capsys, "--confirm", cid, "yes")
    assert rc2 == 1 and out2["wrote"] == 0
