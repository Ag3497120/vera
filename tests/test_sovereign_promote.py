"""W4-m S4 / S5 / S6: consented promotion, retirement on release, and "the same ledger gives the same output".

Thresholds are the pre-registered policy values (artifacts/w4-m/PREREG_W4m_promotion.md): n = 3, d = 2.
They are not measured values; the boundary tests below are what pins them.
Time is always injected (`now`), never read from the machine.
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'sovereign'))

from verantyx import sovereign as sov    # noqa: E402
import sov_memory_ledger as M    # noqa: E402
import sov_protocol_reader as P    # noqa: E402

N, D = 3, 2     # PREREG_W4m_promotion.md section 1


class Conv:
    """A conversation with an injectable clock: `add(day, kind, payload)` appends at that UTC day."""

    def __init__(self, root, sid="s1", consent=True, owner="owner-a"):
        self.root, self.sid = root, sid
        self.t = [M.day(0)]
        out = sov.create(root, sid, owner, consent_promote=consent, now=lambda: M.day(0))
        assert out["verdict"] == "CREATED"
        self.led = sov.open_ledger(root, sid, now=lambda: self.t[0])

    def add(self, day, kind, payload, hour=0):
        self.t[0] = M.day(day, hour)
        return self.led.append({"kind": kind, "payload": payload})

    def say(self, day, phrase, hour=0):
        return self.add(day, "utterance", {"phrase": phrase}, hour)

    def see(self, day, cell, occupied="UNOCCUPIED", hour=0):
        payload = {"cell": cell}
        if occupied is not None:
            payload["occupied"] = occupied
        return self.add(day, "observation", payload, hour)

    def promote(self, **kw):
        return sov.promote(self.root, self.sid, now=lambda: M.day(10), **kw)


def rows(path, table):
    c = sqlite3.connect(str(path))
    try:
        return c.execute(f"SELECT * FROM {table} ORDER BY seq").fetchall()
    finally:
        c.close()


def struct_rows(root, table):
    return rows(Path(root) / "structure.sqlite", table)


def sov_rows(root, sid, table):
    return rows(Path(root) / "stores" / f"{sid}.sqlite", table)


def class_sum(res):
    c = res["counts"]
    return sum(c[k] for k in ("outside_consent_window", "superseded_by_correction", "not_a_candidate",
                              "below_count", "below_days", "conflicting_occupancy",
                              "unknown_occupancy", "already_promoted", "promoted_events"))


# ================================================================ S4: consent
def test_prereg_values_are_the_registered_ones():
    assert (sov.PREREG_MIN_COUNT, sov.PREREG_MIN_DAYS) == (N, D)


def test_without_consent_promote_writes_nothing_on_either_side(tmp_path):
    c = Conv(tmp_path, consent=False)
    for day in (0, 1, 2):
        c.say(day, "repeated phrase")
    before = (struct_rows(tmp_path, "promotion_log"), sov_rows(tmp_path, "s1", "promotion_log"),
              struct_rows(tmp_path, "registry_log"), sov_rows(tmp_path, "s1", "event_log"),
              sov_rows(tmp_path, "s1", "consent_log"))
    out = c.promote()
    assert out["verdict"] == "NO_CONSENT" and out["wrote"] == 0 and out["consent"]["promote"] is False
    assert before == (struct_rows(tmp_path, "promotion_log"), sov_rows(tmp_path, "s1", "promotion_log"),
                      struct_rows(tmp_path, "registry_log"), sov_rows(tmp_path, "s1", "event_log"),
                      sov_rows(tmp_path, "s1", "consent_log"))
    assert sov.active_promotions(tmp_path) == []


def test_consent_withdrawn_stops_promotion_but_keeps_what_was_promoted(tmp_path):
    c = Conv(tmp_path)
    for day in (0, 1, 1):
        c.say(day, "kept")
    assert c.promote()["verdict"] == "PROMOTED"
    sov.set_consent(tmp_path, "s1", False, now=lambda: M.day(11))
    for day in (2, 3, 4):
        c.say(day, "after withdrawal")
    assert c.promote()["verdict"] == "NO_CONSENT"
    assert [p["payload"]["key"] for p in sov.active_promotions(tmp_path)] == ["kept"]   # still there


# ====================================================== S4: thresholds (n, d)
def test_boundaries_under_exact_and_over_for_both_n_and_d(tmp_path):
    c = Conv(tmp_path)
    c.say(0, "n_under"); c.say(1, "n_under")                                       # 2 events, 2 days
    c.say(0, "d_under"); c.say(0, "d_under", hour=5); c.say(0, "d_under", hour=9)   # 3 events, 1 day
    c.say(0, "exact"); c.say(1, "exact"); c.say(1, "exact", hour=3)                 # 3 events, 2 days
    for day in (0, 1, 2, 3, 3):
        c.say(day, "over")                                                           # 5 events, 4 days
    out = c.promote()
    assert out["verdict"] == "PROMOTED"
    assert sorted(p["key"] for p in out["promoted"]) == ["exact", "over"]
    cnt = out["counts"]
    assert cnt["below_count"] == 2 and cnt["below_days"] == 3
    assert cnt["promoted"] == 2 and cnt["promoted_events"] == 8 and cnt["candidates"] == 4
    assert out["thresholds"] == {"n": N, "d": D, "source": "prereg"}
    assert class_sum(out) == cnt["events_total"] == 13
    by = {p["key"]: p for p in out["promoted"]}
    assert (by["exact"]["count"], by["exact"]["days"]) == (3, 2)
    assert (by["over"]["count"], by["over"]["days"]) == (5, 4)


def test_a_day_is_a_utc_date_not_24_hours(tmp_path):
    c = Conv(tmp_path)
    c.say(0, "late", hour=23)
    c.say(1, "late", hour=0)       # 1 hour later, but the next UTC date
    c.say(1, "late", hour=1)
    assert [p["key"] for p in c.promote()["promoted"]] == ["late"]
    c2 = Conv(tmp_path / "r2")
    for h in (0, 12, 23):          # 23 hours apart, one UTC date
        c2.say(0, "same day", hour=h)
    out = c2.promote()
    assert out["promoted"] == [] and out["counts"]["below_days"] == 3


def test_override_thresholds_are_recorded_as_override(tmp_path):
    c = Conv(tmp_path)
    c.say(0, "two"); c.say(1, "two")
    assert c.promote()["promoted"] == []
    out = c.promote(min_count=2, min_days=2)
    assert [p["key"] for p in out["promoted"]] == ["two"]
    assert out["thresholds"] == {"n": 2, "d": 2, "source": "override"}
    assert json.loads(struct_rows(tmp_path, "promotion_log")[0][7]) == {"n": 2, "d": 2, "source": "override"}


@pytest.mark.parametrize("kw", [{"min_count": 0}, {"min_days": 0}, {"min_count": -1}, {"min_count": 2.5},
                                {"min_days": True}, {"min_count": "3"}])
def test_bad_thresholds_are_refused_and_write_nothing(tmp_path, kw):
    c = Conv(tmp_path)
    c.say(0, "x"); c.say(1, "x"); c.say(1, "x")
    out = c.promote(**kw)
    assert out["verdict"] == "REFUSED_BAD_THRESHOLDS"
    assert struct_rows(tmp_path, "promotion_log") == []


# ============================================================ S4: the window
def test_events_before_the_consent_are_not_counted(tmp_path):
    c = Conv(tmp_path, consent=False)
    for day in (0, 1, 1):
        c.say(day, "said before consent")
    sov.set_consent(tmp_path, "s1", True, now=lambda: M.day(2))
    out = c.promote()
    assert out["verdict"] == "NOTHING_TO_PROMOTE"
    assert out["counts"]["outside_consent_window"] == 3 and out["consent"]["since_seq"] == 3
    after = [c.say(day, "said before consent") for day in (3, 4, 4)]
    out = c.promote()
    assert out["verdict"] == "PROMOTED"
    ev = json.loads(sov_rows(tmp_path, "s1", "promotion_log")[0][6])
    assert ev == after                         # evidence is the post-consent events only
    assert class_sum(out) == out["counts"]["events_total"] == 6


def test_the_latest_consent_row_sets_the_window(tmp_path):
    c = Conv(tmp_path)
    for day in (0, 1, 1):
        c.say(day, "early")
    sov.set_consent(tmp_path, "s1", False, now=lambda: M.day(2))
    sov.set_consent(tmp_path, "s1", True, now=lambda: M.day(2, 1))   # re-granted: the window restarts here
    out = c.promote()
    assert out["promoted"] == [] and out["counts"]["outside_consent_window"] == 3


# ================================================== S4: shapes of candidates
def test_placement_evidence_needs_unoccupied_and_keys_cells_canonically(tmp_path):
    c = Conv(tmp_path)
    cell = {"b": 1, "a": 2}
    for day in (0, 1, 1):
        c.see(day, cell)
    out = c.promote()
    assert out["verdict"] == "PROMOTED"
    p = out["promoted"][0]
    assert p["kind"] == "placement_evidence" and p["key"] == '{"a":2,"b":1}'
    c.see(2, {"a": 2, "b": 1})        # the same cell written in another key order is the same key
    again = c.promote()
    assert again["promoted"] == [] and again["counts"]["already_promoted"] == 4


def test_a_cell_with_split_occupancy_is_not_promoted_and_is_counted(tmp_path):
    c = Conv(tmp_path)
    for day in (0, 1, 1):
        c.see(day, "cellA")
    c.see(2, "cellA", occupied="ATTESTED")        # one disagreeing event poisons the cell
    for day in (0, 1, 1):
        c.see(day, "cellB")
    c.see(2, "cellB", occupied="UNKNOWN_NO_INDEX")
    out = c.promote()
    assert out["promoted"] == []
    assert out["counts"]["conflicting_occupancy"] == 8
    assert class_sum(out) == out["counts"]["events_total"] == 8


def test_unknown_or_missing_occupancy_is_counted_and_never_promoted(tmp_path):
    c = Conv(tmp_path)
    for day in (0, 1, 1):
        c.see(day, "cellK", occupied="UNKNOWN_NO_INDEX")
    for day in (0, 1, 1):
        c.see(day, "cellM", occupied=None)           # no `occupied` at all
    for day in (0, 1, 1):
        c.see(day, "cellX", occupied="ATTESTED")     # attested only: not a candidate
    out = c.promote()
    assert out["promoted"] == []
    assert out["counts"]["unknown_occupancy"] == 6 and out["counts"]["not_a_candidate"] == 3
    assert class_sum(out) == out["counts"]["events_total"] == 9


def test_construction_evidence_is_kept_exactly_without_normalising(tmp_path):
    c = Conv(tmp_path)
    c.say(0, "Phrase"); c.say(1, "phrase"); c.say(1, "phrase ")      # three different keys
    out = c.promote()
    assert out["promoted"] == [] and out["counts"]["below_count"] == 3 and out["counts"]["candidates"] == 3


def test_utterance_and_observation_shapes_do_not_cross(tmp_path):
    c = Conv(tmp_path)
    for day in (0, 1, 1):
        c.add(day, "observation", {"phrase": "obs with phrase"})     # an observation is not a phrase
        c.add(day, "utterance", {"cell": "u", "occupied": "UNOCCUPIED"})   # an utterance is not a placement
        c.add(day, "decision", {"phrase": "decided"})
    out = c.promote()
    assert out["promoted"] == [] and out["counts"]["not_a_candidate"] == 9
    assert class_sum(out) == out["counts"]["events_total"] == 9


def test_corrected_events_are_not_counted_and_the_count_is_reported(tmp_path):
    c = Conv(tmp_path)
    c.say(0, "p"); c.say(0, "p", hour=1)
    third = c.say(1, "p")
    c.add(1, "utterance", {"phrase": "q", "corrects": third}, hour=1)
    out = c.promote()
    assert out["promoted"] == []                                 # "p" has 2 live events, not 3
    assert out["counts"]["superseded_by_correction"] == 1 and out["counts"]["below_count"] == 3
    assert class_sum(out) == out["counts"]["events_total"] == 4
    # the raw ledger still counts the corrected event (Protocol numbers are raw)
    assert c.led.count("phrase", "p") == 3


# ============================================================ the sum equation
def test_every_event_lands_in_exactly_one_class_on_a_messy_ledger(tmp_path):
    c = Conv(tmp_path, consent=False)
    c.say(0, "pre1"); c.say(1, "pre1"); c.say(2, "pre1")                  # before consent
    sov.set_consent(tmp_path, "s1", True, now=lambda: M.day(3))
    for day in (3, 4, 4):
        c.say(day, "good")
    c.say(3, "n_under")
    c.say(3, "d_under"); c.say(3, "d_under", hour=2); c.say(3, "d_under", hour=4)
    for day in (3, 4, 4):
        c.see(day, "split")
    c.see(5, "split", occupied="ATTESTED")
    for day in (3, 4, 4):
        c.see(day, "unk", occupied="UNKNOWN_X")
    c.add(3, "decision", {"choice": "x"})
    c.add(3, "utterance", {"no_phrase": 1})
    c.add(3, "utterance", {"phrase": ""})
    c.add(3, "observation", {"occupied": "UNOCCUPIED"})                   # no cell
    wrong = c.say(4, "typo")
    c.add(5, "utterance", {"phrase": "typo fixed", "corrects": wrong})
    out = c.promote()
    cnt = out["counts"]
    assert cnt["events_total"] == len(sov.open_ledger(tmp_path, "s1").events())
    assert class_sum(out) == cnt["events_total"]
    assert [p["key"] for p in out["promoted"]] == ["good"]
    assert cnt["outside_consent_window"] == 3 and cnt["superseded_by_correction"] == 1
    # after promoting, the second pass moves "good" from promoted to already_promoted and still sums
    out2 = c.promote()
    assert out2["counts"]["already_promoted"] == 3 and out2["counts"]["promoted_events"] == 0
    assert class_sum(out2) == out2["counts"]["events_total"]


# ================================================ S4: idempotence and both-way trace
def test_second_promote_adds_nothing(tmp_path):
    c = Conv(tmp_path)
    for day in (0, 1, 1):
        c.say(day, "again")
    first = c.promote()
    sizes = (len(struct_rows(tmp_path, "promotion_log")), len(sov_rows(tmp_path, "s1", "promotion_log")))
    second = c.promote()
    assert first["verdict"] == "PROMOTED" and second["verdict"] == "NOTHING_TO_PROMOTE"
    assert second["counts"]["already_promoted"] == 3 and second["promoted"] == []
    assert sizes == (1, 1) == (len(struct_rows(tmp_path, "promotion_log")),
                               len(sov_rows(tmp_path, "s1", "promotion_log")))


def test_promotion_is_traceable_in_both_directions_and_basis_is_the_store(tmp_path):
    c = Conv(tmp_path)
    ids = [c.say(day, "traced") for day in (0, 1, 1)]
    out = c.promote()
    pr = out["promoted"][0]
    srow = struct_rows(tmp_path, "promotion_log")[0]
    brow = sov_rows(tmp_path, "s1", "promotion_log")[0]
    # structure side: (seq, ts, promotion_id, store_id, kind, basis, payload, thresholds)
    assert srow[2] == pr["promotion_id"] and srow[3] == "s1" and srow[5] == "conversation:s1"
    assert srow[4] == "construction_evidence"
    assert json.loads(srow[6]) == {"count": 3, "days": 2, "evidence": ids, "key": "traced"}
    # sovereign side: (seq, ts, promotion_id, kind, cand_key, structure_seq, evidence)
    assert brow[2] == srow[2] and brow[5] == srow[0] and json.loads(brow[6]) == ids
    tr = sov.trace_promotion(tmp_path, pr["promotion_id"])
    assert tr["verdict"] == "ANSWER" and tr["store_id"] == "s1"
    assert tr["structure"][0]["basis"] == "conversation:s1" and tr["retired"] == []
    assert tr["sovereign"]["verdict"] == "ANSWER"
    assert tr["sovereign"]["rows"][0]["structure_seq"] == tr["structure"][0]["seq"]
    live = {e["id"] for e in sov.open_ledger(tmp_path, "s1").events()}
    assert set(tr["sovereign"]["rows"][0]["evidence"]) <= live        # the evidence is really in the log
    assert sov.trace_promotion(tmp_path, "0" * 24)["verdict"] == "UNKNOWN_PROMOTION"
    assert [p["promotion_id"] for p in sov.active_promotions(tmp_path)] == [pr["promotion_id"]]


def test_promotion_id_is_deterministic_in_store_kind_key(tmp_path):
    a, b = Conv(tmp_path / "a"), Conv(tmp_path / "b")
    for c in (a, b):
        for day in (0, 1, 1):
            c.say(day, "same key")
    ia = a.promote()["promoted"][0]["promotion_id"]
    ib = b.promote()["promoted"][0]["promotion_id"]
    assert ia == ib == sov._sov_promotion_id("s1", "construction_evidence", "same key")
    c2 = Conv(tmp_path / "c", sid="s2")
    for day in (0, 1, 1):
        c2.say(day, "same key")
    assert c2.promote()["promoted"][0]["promotion_id"] != ia


def test_promotion_record_type_pins_the_basis():
    ok = sov.PromotionRecord("s1", "placement_evidence", {"key": "k"}, "conversation:s1")
    assert ok.basis == "conversation:s1"
    with pytest.raises(ValueError):
        sov.PromotionRecord("s1", "placement_evidence", {}, "conversation:s2")
    with pytest.raises(ValueError):
        sov.PromotionRecord("s1", "fact", {}, "conversation:s1")
    with pytest.raises(Exception):
        ok.basis = "other"


def test_no_winner_is_picked_among_equal_candidates(tmp_path):
    c = Conv(tmp_path)
    for key in ("tie_b", "tie_a", "tie_c"):
        for day in (0, 1, 1):
            c.say(day, key)
    out = c.promote()
    assert sorted(p["key"] for p in out["promoted"]) == ["tie_a", "tie_b", "tie_c"]   # all of them
    assert [p["key"] for p in out["promoted"]] == ["tie_b", "tie_a", "tie_c"]         # display order = first seq


# =========================================================== crash recovery
def test_a_crash_between_the_two_writes_is_repaired_on_the_next_run(tmp_path, monkeypatch):
    c = Conv(tmp_path)
    for key in ("first", "second"):
        for day in (0, 1, 1):
            c.say(day, key)
    real = sov._sov_append_backlink
    calls = []

    def flaky(*a, **kw):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("simulated crash after the structure write")
        return real(*a, **kw)

    monkeypatch.setattr(sov, "_sov_append_backlink", flaky)
    with pytest.raises(RuntimeError):
        c.promote()
    assert len(struct_rows(tmp_path, "promotion_log")) == 2 and len(sov_rows(tmp_path, "s1", "promotion_log")) == 1
    monkeypatch.setattr(sov, "_sov_append_backlink", real)
    out = c.promote()
    assert out["counts"]["repaired_backlink"] == 1 and out["promoted"] == []
    assert len(struct_rows(tmp_path, "promotion_log")) == 2 and len(sov_rows(tmp_path, "s1", "promotion_log")) == 2
    ids_s = {r[2] for r in struct_rows(tmp_path, "promotion_log")}
    ids_b = {r[2] for r in sov_rows(tmp_path, "s1", "promotion_log")}
    assert ids_s == ids_b
    assert c.promote()["counts"]["repaired_backlink"] == 0          # nothing left to repair


def test_a_crash_before_any_write_leaves_nothing_half_done(tmp_path, monkeypatch):
    c = Conv(tmp_path)
    for day in (0, 1, 1):
        c.say(day, "x")

    def boom(*a, **kw):
        raise RuntimeError("down")

    monkeypatch.setattr(sov, "_sov_append_structure_promotion", boom)
    with pytest.raises(RuntimeError):
        c.promote()
    assert struct_rows(tmp_path, "promotion_log") == [] and sov_rows(tmp_path, "s1", "promotion_log") == []


# ======================================================== not-ACTIVE sovereigns
def test_promote_on_a_store_that_is_not_active_is_typed(tmp_path):
    c = Conv(tmp_path)
    for day in (0, 1, 1):
        c.say(day, "x")
    assert sov.promote(tmp_path, "zz")["verdict"] == "UNKNOWN_STORE"
    sov.detach(tmp_path, "s1")
    assert c.promote()["verdict"] == "DETACHED"
    sov.attach(tmp_path, store_id="s1")
    sov.release(tmp_path, "s1", "s1")
    assert c.promote()["verdict"] == "RELEASED"
    assert struct_rows(tmp_path, "promotion_log") == []


# ================================================================== S5: retire
def two_sovereigns(root):
    a, b = Conv(root, "sa", owner="owner-a"), Conv(root, "sb", owner="owner-b")
    for c in (a, b):
        for key in ("k1", "k2"):
            for day in (0, 1, 1):
                c.say(day, key)
        c.see(0, "cell"); c.see(1, "cell"); c.see(1, "cell")
    return a, b


def test_release_retires_the_promotions_by_appending_and_deletes_nothing(tmp_path):
    a, b = two_sovereigns(tmp_path)
    assert a.promote()["counts"]["promoted"] == 3 and b.promote()["counts"]["promoted"] == 3
    before_struct = struct_rows(tmp_path, "promotion_log")
    assert len(before_struct) == 6 and len(sov.active_promotions(tmp_path)) == 6
    out = sov.release(tmp_path, "sa", "sa")
    assert out["verdict"] == "RELEASED" and out["retired"] == 3 and out["retired_this_run"] == 3
    # nothing deleted: the structure-side promotion rows are byte-for-byte the same, retire rows were added
    assert struct_rows(tmp_path, "promotion_log") == before_struct
    ret = struct_rows(tmp_path, "retire_log")
    assert len(ret) == 3 and {r[4] for r in ret} == {"sa"} and {r[5] for r in ret} == {"RELEASED"}
    # out of the candidates, but still in the full list with its retire row
    active = sov.active_promotions(tmp_path)
    assert len(active) == 3 and {p["store_id"] for p in active} == {"sb"}
    allp = sov.all_promotions(tmp_path)
    assert len(allp) == 6
    retired = [p for p in allp if p["retired"] is not None]
    assert len(retired) == 3 and {p["store_id"] for p in retired} == {"sa"}
    assert all(p["retired"]["reason"] == "RELEASED" for p in retired)
    assert sov.active_promotions(tmp_path, "sa") == [] and len(sov.all_promotions(tmp_path, "sa")) == 3
    # the retire row points at the RELEASE row of the registry
    rel_seq = [r[0] for r in struct_rows(tmp_path, "registry_log") if r[3] == "RELEASE"][0]
    assert {r[6] for r in ret} == {rel_seq} == {out["registry_seq"]}
    st = {s["store_id"]: s for s in sov.status(tmp_path)["stores"]}
    assert st["sa"]["promotions_active"] == 0 and st["sa"]["promotions_retired"] == 3
    assert st["sb"]["promotions_active"] == 3 and st["sb"]["promotions_retired"] == 0


def test_trace_of_a_retired_promotion_still_resolves_the_structure_side(tmp_path):
    a, _b = two_sovereigns(tmp_path)
    pid = a.promote()["promoted"][0]["promotion_id"]
    sov.release(tmp_path, "sa", "sa")
    tr = sov.trace_promotion(tmp_path, pid)
    assert tr["verdict"] == "ANSWER" and len(tr["structure"]) == 1
    assert tr["retired"][0]["reason"] == "RELEASED"
    assert tr["sovereign"]["verdict"] == "RELEASED"            # typed: the sovereign side was let go


def test_detach_does_not_retire_and_the_promotions_stay_active(tmp_path):
    a, _b = two_sovereigns(tmp_path)
    a.promote()
    sov.detach(tmp_path, "sa")
    assert len(sov.active_promotions(tmp_path, "sa")) == 3 and struct_rows(tmp_path, "retire_log") == []
    tr = sov.trace_promotion(tmp_path, sov.active_promotions(tmp_path, "sa")[0]["promotion_id"])
    assert tr["sovereign"]["verdict"] == "DETACHED"
    sov.attach(tmp_path, store_id="sa")
    assert len(sov.active_promotions(tmp_path, "sa")) == 3


def test_release_with_no_promotions_retires_zero(tmp_path):
    Conv(tmp_path)
    out = sov.release(tmp_path, "s1", "s1")
    assert out["retired"] == 0 and struct_rows(tmp_path, "retire_log") == []


def test_release_failing_after_the_retire_is_finished_by_the_rerun(tmp_path, monkeypatch):
    a, _b = two_sovereigns(tmp_path)
    a.promote()
    real = sov._sov_registry_append

    def fail_release(root, **kw):
        if kw.get("op") == "RELEASE":
            raise RuntimeError("simulated crash before the RELEASE row")
        return real(root, **kw)

    monkeypatch.setattr(sov, "_sov_registry_append", fail_release)
    with pytest.raises(RuntimeError):
        sov.release(tmp_path, "sa", "sa")
    assert sov.describe(tmp_path, "sa").status == "ACTIVE"          # the reference was not cut yet
    assert len(struct_rows(tmp_path, "retire_log")) == 3            # but the retirement is already appended
    monkeypatch.setattr(sov, "_sov_registry_append", real)
    out = sov.release(tmp_path, "sa", "sa")
    assert out["verdict"] == "RELEASED" and out["retired"] == 3 and out["retired_this_run"] == 0
    assert len(struct_rows(tmp_path, "retire_log")) == 3            # nothing retired twice
    assert sov.describe(tmp_path, "sa").status == "RELEASED"


def test_leftover_promotions_found_after_release_are_retired_on_rerun(tmp_path):
    a, _b = two_sovereigns(tmp_path)
    a.promote()
    sov.release(tmp_path, "sa", "sa")
    # a stray promotion row for the released store appears (a legal append made from outside)
    c = sqlite3.connect(str(tmp_path / "structure.sqlite"), isolation_level=None)
    n = c.execute("SELECT MAX(seq) FROM promotion_log").fetchone()[0]
    c.execute("INSERT INTO promotion_log (seq, ts, promotion_id, store_id, kind, basis, payload, thresholds) "
              "VALUES (?, 't', 'stray', 'sa', 'construction_evidence', 'conversation:sa', '{}', '{}')", (n + 1,))
    c.close()
    out = sov.release(tmp_path, "sa", "sa")
    assert out["verdict"] == "ALREADY_RELEASED" and out["retired_on_rerun"] == 1
    assert sov.active_promotions(tmp_path, "sa") == []
    assert sov.release(tmp_path, "sa", "sa")["retired_on_rerun"] == 0


def test_the_other_stores_candidates_are_untouched_by_a_release(tmp_path):
    a, b = two_sovereigns(tmp_path)
    a.promote(); b.promote()
    before = [p for p in sov.active_promotions(tmp_path, "sb")]
    sov.release(tmp_path, "sa", "sa")
    assert sov.active_promotions(tmp_path, "sb") == before


# ========================================================= S6: same ledger, same output
def run_script(root, with_ops):
    """The same conversation script, optionally with unit operations woven through it."""
    c = Conv(root)
    c.say(0, "alpha"); c.see(0, "c1"); c.add(0, "decision", {"choice": "x"})
    if with_ops:
        sov.set_consent(root, "s1", False, now=lambda: M.day(0, 1))
        sov.set_consent(root, "s1", True, now=lambda: M.day(0, 2))
    c.say(1, "alpha"); c.see(1, "c1")
    if with_ops:
        sov.detach(root, "s1")
        sov.attach(root, store_id="s1")
    c.say(1, "alpha", hour=5); c.see(1, "c1", hour=5)
    if with_ops:
        sov.export(root, "s1", str(Path(root).parent / (Path(root).name + "-export.sqlite")))
        c.promote()
        sov.create(root, "other", "owner-b")
        sov.release(root, "other", "other")
    return c


def test_the_same_script_in_two_roots_gives_byte_equal_digests(tmp_path):
    a = run_script(tmp_path / "A", False)
    b = run_script(tmp_path / "B", False)
    assert P.digest(a.led) == P.digest(b.led) and len(P.digest(a.led)) > 300


def test_unit_operations_do_not_change_what_the_ledger_says(tmp_path):
    plain = run_script(tmp_path / "plain", False)
    busy = run_script(tmp_path / "busy", True)
    # consent switches add rows to consent_log, not to the event log, so the conversation is the same bytes
    assert P.digest(plain.led) == P.digest(sov.open_ledger(tmp_path / "busy", "s1"))


def test_each_operation_leaves_the_target_digest_unchanged(tmp_path):
    root = tmp_path / "R"
    c = Conv(root)
    for day in (0, 1, 1):
        c.say(day, "alpha")
        c.see(day, "c1")
    base = P.digest(sov.open_ledger(root, "s1"))
    steps = [
        lambda: sov.set_consent(root, "s1", False, now=lambda: M.day(5)),
        lambda: sov.set_consent(root, "s1", True, now=lambda: M.day(5, 1)),
        lambda: c.promote(),
        lambda: sov.export(root, "s1", str(tmp_path / "exp.sqlite")),
        lambda: sov.attach(tmp_path / "R2", file=str(tmp_path / "exp.sqlite")),
        lambda: sov.detach(root, "s1"),
        lambda: sov.attach(root, store_id="s1"),
        lambda: (sov.create(root, "zz", "o"), sov.release(root, "zz", "zz")),
        lambda: sov.status(root),
    ]
    for step in steps:
        step()
        if sov.describe(root, "s1").status == "ACTIVE":
            assert P.digest(sov.open_ledger(root, "s1")) == base
    # the copy attached in another root says the same, byte for byte
    assert P.digest(sov.open_ledger(tmp_path / "R2", "s1")) == base


def test_digest_through_the_protocol_matches_the_reference_after_promotion_and_release(tmp_path):
    c = Conv(tmp_path)
    ref = M.MemoryLedger("s1", now=M.FakeClock())
    for day in (0, 1, 1):
        c.say(day, "alpha")
        ref.append({"kind": "utterance", "payload": {"phrase": "alpha"}})
    c.promote()
    persistent = P.digest(sov.open_ledger(tmp_path, "s1"))
    # reference ts values come from its own clock, so compare the Protocol answers that do not carry ts
    pe = [(e["id"], e["kind"], e["payload"]) for e in sov.open_ledger(tmp_path, "s1").events()]
    re_ = [(e["id"], e["kind"], e["payload"]) for e in ref.events()]
    assert pe == re_
    assert P.candidates(sov.open_ledger(tmp_path, "s1"), "phrase") == P.candidates(ref, "phrase")
    assert len(persistent) > 100



# ============================== review r1, must 1: a back-link names the ledger it points into
def _three_day_phrases(conv, *phrases):
    for ph in phrases:
        for day in (0, 1, 1):
            conv.say(day, ph)


def _two_roots_with_a_moved_store(tmp_path, with_other_store=True):
    """Root A promotes s1 (and, by default, another store s0 first); s1 is exported and attached in
    root B. With s0, A's structure_seq values for s1 name rows in B that belong to another store (the
    situation the first review reproduced). Without s0 they COINCIDE with B's own seq values, so only
    the `structure_ref` tells A's links from B's."""
    A, B = tmp_path / "A", tmp_path / "B"
    if with_other_store:
        s0 = Conv(A, "s0")
        _three_day_phrases(s0, "a0", "a1")
        s0.promote()
    s1 = Conv(A, "s1")
    _three_day_phrases(s1, "k1", "k2")
    s1.promote()
    (tmp_path / "out").mkdir()
    out = tmp_path / "out" / "s1.sqlite"
    assert sov.export(A, "s1", str(out))["verdict"] == "EXPORTED"
    assert sov.attach(B, file=str(out))["verdict"] == "ATTACHED"
    return A, B, out


def _all_backlinks(out):
    """The moved file stays where it was exported to (attach registers it in place, no copy)."""
    return rows(out, "promotion_log")


def test_structure_ref_is_deterministic_and_differs_between_roots(tmp_path):
    import hashlib
    A, B, _out = _two_roots_with_a_moved_store(tmp_path)
    refs = []
    for root in (A, B):
        conn = sov._sov_struct_open(root)
        try:
            first = conn.execute("SELECT * FROM registry_log WHERE seq = 1").fetchone()
            ref = sov._sov_struct_ref(conn)
            assert ref == sov._sov_struct_ref(conn)                       # same value every time
            assert ref == hashlib.sha256(sov._sov_dump(list(first)).encode("utf-8")).hexdigest()
            # the first row carries the absolute path of the root that wrote it (review r2, must 1)
            assert json.loads(first[-1])["root"] == os.path.abspath(str(root))
        finally:
            conn.close()
        refs.append(ref)
    assert refs[0] != refs[1]
    # a ref does not move when the ledger grows (the first row is append-only history)
    sov.create(A, "late", "owner-a")
    conn = sov._sov_struct_open(A)
    try:
        assert sov._sov_struct_ref(conn) == refs[0]
    finally:
        conn.close()


def test_a_moved_store_promoted_in_another_root_is_traced_only_to_that_roots_rows(tmp_path):
    A, B, _out = _two_roots_with_a_moved_store(tmp_path)
    res = sov.promote(B, "s1", now=lambda: M.day(10))
    assert res["verdict"] == "PROMOTED" and len(res["promoted"]) == 2
    other = Conv(B, "t9")                       # B now has other-store rows after s1's
    _three_day_phrases(other, "x", "y")
    assert other.promote()["verdict"] == "PROMOTED"
    by_seq = {p["seq"]: p for p in sov.all_promotions(B)}
    # the file now carries A's back-links as well as B's: 2 + 2 rows for the 2 keys
    assert len(_all_backlinks(_out)) == 4
    cur = None
    for p in sov.active_promotions(B, "s1"):
        tr = sov.trace_promotion(B, p["promotion_id"])
        cur = tr["structure_ref"]
        rows = tr["sovereign"]["rows"]
        assert len(rows) == 1
        for r in rows:
            assert r["structure_ref"] == cur
            assert by_seq[r["structure_seq"]]["promotion_id"] == p["promotion_id"]   # the SAME promotion
            assert by_seq[r["structure_seq"]]["store_id"] == "s1"
        # A's link is not dropped and not mixed in: typed, separate, and it names another ledger
        assert len(tr["sovereign"]["other_structures"]) == 1
        assert tr["sovereign"]["other_structures"][0]["structure_ref"] != cur
        assert tr["sovereign"]["mismatched"] == []
    # the other store's rows in B are traced to their own back-links only
    for p in sov.active_promotions(B, "t9"):
        tr = sov.trace_promotion(B, p["promotion_id"])
        assert [r["structure_seq"] for r in tr["sovereign"]["rows"]] == [p["seq"]]
        assert tr["sovereign"]["other_structures"] == []
    # root A still traces to its own rows (A's links were never touched)
    for p in sov.active_promotions(A, "s1"):
        tr = sov.trace_promotion(A, p["promotion_id"])
        assert [r["structure_seq"] for r in tr["sovereign"]["rows"]] == [p["seq"]]


def test_a_back_link_pointing_at_a_row_of_another_promotion_is_reported_as_mismatched(tmp_path):
    c = Conv(tmp_path)
    _three_day_phrases(c, "p", "q")
    c.promote()
    ps = sov.active_promotions(tmp_path, "s1")
    pid_p = ps[0]["promotion_id"]
    # a legal append made from outside: a link with this ledger's ref but pointing at the other row
    conn = sov._sov_struct_open(tmp_path)
    try:
        ref = sov._sov_struct_ref(conn)
    finally:
        conn.close()
    path = tmp_path / "stores" / "s1.sqlite"
    db = sqlite3.connect(str(path), isolation_level=None)
    n = db.execute("SELECT MAX(seq) FROM promotion_log").fetchone()[0]
    db.execute("INSERT INTO promotion_log (seq, ts, promotion_id, kind, cand_key, structure_seq, evidence, structure_ref) "
               "VALUES (?, 't', ?, 'construction_evidence', 'p', ?, '[]', ?)", (n + 1, pid_p, ps[1]["seq"], ref))
    db.close()
    tr = sov.trace_promotion(tmp_path, pid_p)
    assert len(tr["sovereign"]["rows"]) == 1 and len(tr["sovereign"]["mismatched"]) == 1
    assert tr["sovereign"]["mismatched"][0]["structure_seq"] == ps[1]["seq"]


def test_repair_in_a_second_root_is_not_hidden_by_the_first_roots_links(tmp_path, monkeypatch):
    # A has only s1, so A's (promotion_id, structure_seq) pairs are identical to B's: only the ref differs
    A, B, _out = _two_roots_with_a_moved_store(tmp_path, with_other_store=False)
    real = sov._sov_append_backlink
    calls = []

    def flaky(*a, **kw):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("simulated crash after the structure write")
        return real(*a, **kw)

    monkeypatch.setattr(sov, "_sov_append_backlink", flaky)
    with pytest.raises(RuntimeError):
        sov.promote(B, "s1", now=lambda: M.day(10))
    assert len(struct_rows(B, "promotion_log")) == 2
    monkeypatch.setattr(sov, "_sov_append_backlink", real)
    out = sov.promote(B, "s1", now=lambda: M.day(10))
    assert out["counts"]["repaired_backlink"] == 1 and out["promoted"] == []
    assert len(struct_rows(B, "promotion_log")) == 2
    for p in sov.active_promotions(B, "s1"):
        tr = sov.trace_promotion(B, p["promotion_id"])
        assert [r["structure_seq"] for r in tr["sovereign"]["rows"]] == [p["seq"]]
        assert len(tr["sovereign"]["other_structures"]) == 1          # A's identical-looking link, kept apart
        assert tr["sovereign"]["other_structures"][0]["structure_ref"] != tr["structure_ref"]
    assert sov.promote(B, "s1", now=lambda: M.day(10))["counts"]["repaired_backlink"] == 0


# ============================== review r2, must 1: the ref tells apart roots that attach the same file
def _same_file_attached_in_two_new_roots(tmp_path):
    """A creates s1 and promotes it; the exported file is attached in new roots B and C at the SAME
    instant. Both registries then start with an ATTACH row whose path is the exported file (it holds
    no root), so without a root in the row the two first rows would be byte for byte equal."""
    A, B, C = tmp_path / "A", tmp_path / "B", tmp_path / "C"
    s1 = Conv(A, "s1")
    _three_day_phrases(s1, "k")
    s1.promote()
    (tmp_path / "out").mkdir()
    out = tmp_path / "out" / "s1.sqlite"
    assert sov.export(A, "s1", str(out), now=lambda: M.day(2))["verdict"] == "EXPORTED"
    for root in (B, C):
        assert sov.attach(root, file=str(out), now=lambda: M.day(3))["verdict"] == "ATTACHED"
    return A, B, C, out


def _ref_of(root):
    conn = sov._sov_struct_open(root)
    try:
        return sov._sov_struct_ref(conn)
    finally:
        conn.close()


def test_structure_ref_differs_for_the_same_file_attached_in_two_new_roots_at_the_same_time(tmp_path):
    A, B, C, _out = _same_file_attached_in_two_new_roots(tmp_path)
    firsts = []
    for root in (B, C):
        conn = sov._sov_struct_open(root)
        try:
            row = conn.execute("SELECT ts, store_id, op, path, file_sha256, content_sha256 "
                               "FROM registry_log WHERE seq = 1").fetchone()
        finally:
            conn.close()
        firsts.append(row)
    # the situation the review reproduced: everything but the root is identical in the two first rows
    assert firsts[0] == firsts[1] and firsts[0][2] == "ATTACH"
    refs = {r.name: _ref_of(r) for r in (A, B, C)}
    assert len(set(refs.values())) == 3
    assert refs["B"] == _ref_of(B)                     # deterministic: asked again, same value
    sov.create(B, "late", "owner-b")
    assert _ref_of(B) == refs["B"]                     # does not move when the ledger grows


def test_two_roots_that_attached_the_same_file_keep_their_back_links_and_repairs_apart(tmp_path, monkeypatch):
    A, B, C, out = _same_file_attached_in_two_new_roots(tmp_path)
    real = sov._sov_append_backlink
    calls = []

    def flaky(*a, **kw):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("simulated crash after the structure write")
        return real(*a, **kw)

    monkeypatch.setattr(sov, "_sov_append_backlink", flaky)
    with pytest.raises(RuntimeError):
        sov.promote(B, "s1", now=lambda: M.day(5))
    monkeypatch.setattr(sov, "_sov_append_backlink", real)
    assert sov.promote(C, "s1", now=lambda: M.day(5))["verdict"] == "PROMOTED"
    again = sov.promote(B, "s1", now=lambda: M.day(5))
    assert again["counts"]["repaired_backlink"] == 1               # C's link did not hide B's missing one
    pid = sov.active_promotions(B, "s1")[0]["promotion_id"]
    tr = sov.trace_promotion(B, pid)
    mine = tr["sovereign"]["rows"]
    assert len(mine) == 1 and mine[0]["structure_ref"] == _ref_of(B)
    refs_elsewhere = {r["structure_ref"] for r in tr["sovereign"]["other_structures"]}
    assert refs_elsewhere == {_ref_of(A), _ref_of(C)}             # A's and C's links, kept apart
    assert tr["sovereign"]["mismatched"] == []
    assert len(_all_backlinks(out)) == 3                           # one per root, none lost
    assert sov.promote(B, "s1", now=lambda: M.day(5))["counts"]["repaired_backlink"] == 0


# ====================================== review r1, optional 1: promote refuses mid-release
def test_promote_stops_while_a_release_is_half_done(tmp_path, monkeypatch):
    c = Conv(tmp_path)
    _three_day_phrases(c, "p")
    c.promote()
    real = sov._sov_registry_append

    def fail_release(root, **kw):
        if kw.get("op") == "RELEASE":
            raise RuntimeError("simulated crash before the RELEASE row")
        return real(root, **kw)

    monkeypatch.setattr(sov, "_sov_registry_append", fail_release)
    with pytest.raises(RuntimeError):
        sov.release(tmp_path, "s1", "s1")
    monkeypatch.setattr(sov, "_sov_registry_append", real)
    before = (struct_rows(tmp_path, "promotion_log"), struct_rows(tmp_path, "retire_log"),
              sov_rows(tmp_path, "s1", "promotion_log"))
    out = c.promote()
    assert out["verdict"] == "RELEASE_IN_PROGRESS" and out["wrote"] == 0
    assert (struct_rows(tmp_path, "promotion_log"), struct_rows(tmp_path, "retire_log"),
            sov_rows(tmp_path, "s1", "promotion_log")) == before
    assert sov.release(tmp_path, "s1", "s1")["verdict"] == "RELEASED"
    assert len(struct_rows(tmp_path, "promotion_log")) == 1          # never promoted twice
    assert sov.active_promotions(tmp_path, "s1") == []
