"""G4-e / G4-f tests: the growth meter (experiments/line3/g4/meter.py) and the events (experiments/line3/g4/events.py).

T-G4-13 (the record schema: canonical bytes, no float in the hashed part, every 7.2 field present), T-G4-14 (the events on synthetic series: 直入 / 後から, 残る,
a loss with all-R = 置き換え, mixed R+U = 壊れる, A, 単独誤答化 with R = 壊れる, 戻る, unmeasured steps skipped, 未着 left out of the denominator), T-G4-15 (the 2x2 of
every verdict shape, present and absent, `gold_not_from_evidence`, the impossible pre-entry `from_evidence` raises), the determinism of the record bytes (hash seed,
workers), resume, and the dictionary-free arm B in a process that cannot import fugashi / unidic_lite.

Part 1  the 2x2 (pure)
Part 2  the events on synthetic series (pure)
Part 3  the arrangement oracles (ledger-based, dict-based)
Part 4  the meter on a toy stack: schema, evidence flags, determinism, resume, subsets
Part 5  the one-shot arm (C) on a toy: caches, the arrangement table
Part 6  the dictionary-free arm B in a fresh process
"""
import collections
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
G4 = os.path.join(ROOT, "experiments", "line3", "g4")
sys.path.insert(0, G4)

import events as EV                                           # noqa: E402
import meter as M                                             # noqa: E402

from verantyx.line3 import ask as A                           # noqa: E402
from verantyx.line3 import stack as st                        # noqa: E402
from test_stack import DOCS, SENTS, rows                      # noqa: E402

PY = sys.executable
ALL = ("RUN", "WORD", "CHAR")
LEVEL = "low"


# =============================================================================================================
# synthetic records
# =============================================================================================================
def gold_row(tier="WORD", seed="城", from_evidence=True, pre_entry_hit=False, pos=0, seats_after_entry=0, src_after_entry=False):
    return {"pos": pos, "tier": tier, "words": ["城"], "source_sids": [0], "from_evidence": from_evidence, "pre_entry_hit": pre_entry_hit,
            "src_after_entry": src_after_entry,
            "origins": [{"tier": tier, "seed": seed, "member": 0, "stability": "1/1", "unit": "x", "ratios": "AGREE", "agreed": "x", "arr": "aaaa", "opened_at": 1,
                         "closed_at": None, "closed": False, "seated": 2, "read": True, "seats_after_entry": seats_after_entry}]}


def rec(step, qid="Q1", kind="intra2", e=2, verdict="CHOICE", listed=3, gold=None, unarrived=False, read=None, site=None, arm="A", s=None):
    entered = kind == "intra2" and step >= e
    return {"format": EV.FORMAT, "arm": arm, "step": step, "qid": qid, "kind": kind, "e": e if kind == "intra2" else None, "s": s, "entered": entered,
            "verdict": verdict, "listed": listed, "gold": gold or [], "unarrived": unarrived, "unarrived_3tier": unarrived,
            "tiers": {"WORD": {"read": list(read if read is not None else ["城"]), "entries": listed, "unread": 0}}, "site": site}


def H(step, qid="Q1", e=2, seed="城", **kw):
    """A present-correct record whose gold came from the cross (WORD, seed)."""
    return rec(step, qid, e=e, verdict=kw.pop("verdict", "CHOICE"), listed=kw.pop("listed", 3), gold=[gold_row(seed=seed, **kw)])


def lost(step, qid="Q1", e=2, verdict="CHOICE", listed=3, read=("城",), gold=None):
    return rec(step, qid, e=e, verdict=verdict, listed=listed, read=read, gold=gold)


# =============================================================================================================
# Part 1: the 2x2
# =============================================================================================================
@pytest.mark.parametrize("r, want", [
    # present row
    (rec(2, verdict="ANSWER", listed=1, gold=[gold_row()]), ("present", "correct", None)),
    (rec(2, verdict="CHOICE", listed=5, gold=[gold_row()]), ("present", "correct", None)),
    (rec(2, verdict="UNKNOWN_NO_PATH", listed=0), ("present", "miss", "abstain")),
    (rec(2, verdict="UNKNOWN_NO_STATE", listed=0), ("present", "miss", "abstain")),
    (rec(2, verdict="CHOICE", listed=5), ("present", "miss", "list_without_gold")),
    (rec(2, verdict="CHOICE", listed=5, gold=[gold_row(from_evidence=False)]), ("present", "miss", "gold_not_from_evidence")),
    (rec(2, verdict="ANSWER", listed=1, gold=[gold_row(from_evidence=False)]), ("present", "miss", "gold_not_from_evidence")),
    (rec(2, verdict="ANSWER", listed=1), ("present", "wrong", None)),
    # absent row: intra2 before its article, unans at every step
    (rec(1, verdict="UNKNOWN_NO_PATH", listed=0), ("absent", "correct", None)),
    (rec(1, verdict="CHOICE", listed=4), ("absent", "miss", "false_presence")),
    (rec(1, verdict="ANSWER", listed=1, gold=[gold_row(from_evidence=False, pre_entry_hit=True)]), ("absent", "miss", "false_presence")),
    (rec(1, verdict="ANSWER", listed=1), ("absent", "wrong", None)),
    (rec(5, qid="U1", kind="unans", verdict="UNKNOWN_NO_PATH", listed=0, s=3), ("absent", "correct", None)),
    (rec(5, qid="U1", kind="unans", verdict="CHOICE", listed=9, s=3), ("absent", "miss", "false_presence")),
    (rec(5, qid="U1", kind="unans", verdict="ANSWER", listed=1, s=3), ("absent", "wrong", None)),
])
def test_2x2_classifies_every_verdict_shape(r, want):
    assert EV.classify(r) == want


def test_2x2_refuses_the_impossible_and_the_unknown():
    with pytest.raises(ValueError, match="before the article entered"):
        EV.classify(rec(1, verdict="CHOICE", listed=2, gold=[gold_row(from_evidence=True)]))            # from_evidence while the article has not entered
    with pytest.raises(ValueError, match="unknown verdict"):
        EV.classify(rec(2, verdict="MAYBE", listed=1))
    with pytest.raises(ValueError, match="ANSWER lists exactly one"):
        EV.classify(rec(2, verdict="ANSWER", listed=2))
    with pytest.raises(ValueError, match="abstention lists nothing"):
        EV.classify(rec(2, verdict="UNKNOWN_NO_PATH", listed=1))


def test_single_wrong_is_an_answer_of_one_entry_without_gold():
    assert EV.single_wrong(rec(2, verdict="ANSWER", listed=1))
    assert not EV.single_wrong(rec(2, verdict="ANSWER", listed=1, gold=[gold_row()]))
    assert not EV.single_wrong(rec(2, verdict="CHOICE", listed=3))
    assert EV.single_wrong(rec(3, qid="U1", kind="unans", verdict="ANSWER", listed=1))           # an unans question has no gold: every ANSWER is a single wrong


def test_the_table_counts_each_cell_once_and_puts_the_candidate_beside_it():
    recs = [rec(5, "Q1", e=2, verdict="CHOICE", listed=4, gold=[gold_row()]),                        # present correct
            rec(5, "Q2", e=2, verdict="CHOICE", listed=6, gold=[gold_row(from_evidence=False)], unarrived=False),     # present, gold in a candidate, not from evidence
            rec(5, "Q3", e=2, verdict="UNKNOWN_NO_PATH", listed=0, unarrived=True),                  # present abstain, 未着
            rec(5, "Q4", e=2, verdict="ANSWER", listed=1),                                          # present confident wrong
            rec(5, "Q5", e=9, verdict="CHOICE", listed=2),                                          # absent false presence (before entry)
            rec(5, "U1", kind="unans", verdict="UNKNOWN_NO_PATH", listed=0, s=1),                    # absent correct
            rec(5, "U2", kind="unans", verdict="ANSWER", listed=1, s=1)]                             # absent confident wrong
    t = EV.table_2x2(recs)
    assert t["present"] == {"n": 4, "correct": 1, "miss": 2, "wrong": 1}
    assert t["absent"] == {"n": 3, "miss": 1, "correct": 1, "wrong": 1}
    assert t["sub"] == {("present", "gold_not_from_evidence"): 1, ("present", "abstain"): 1, ("absent", "false_presence"): 1}
    assert t["gold_in_candidate"] == 2 and t["present_unarrived"] == 1 and t["single_wrong"] == 2
    assert t["listed_median"] == 1 and t["n"] == 7
    # the headline present row is WITHOUT the 未着 question (Q3), which is counted apart (owner): its cells add up to the denominator
    assert t["present_den"] == {"n": 3, "correct": 1, "miss": 1, "wrong": 1} and t["sub_den"] == {("present", "gold_not_from_evidence"): 1}
    assert t["present_unarrived"] == 1 and t["present_unarrived_own"] == 1 and t["present_unarrived_unknown"] == 0
    assert "denominator = present - 未着" in EV.render_step_table(recs)
    assert t["present"]["n"] + t["absent"]["n"] == t["n"]                                                  # every record in exactly one row
    assert sum(v for k, v in t["present"].items() if k != "n") == t["present"]["n"] and sum(v for k, v in t["absent"].items() if k != "n") == t["absent"]["n"]


# =============================================================================================================
# Part 2: the events on synthetic series
# =============================================================================================================
def arr_of(**changed):
    """A DictArr in which the cross ('WORD', seed) has the id given for each step; kinds optional."""
    ids = {}
    for seed, per in changed.items():
        for step, ident in per.items():
            ids[("WORD", seed, step)] = ident
    return EV.DictArr(ids)


def test_a_direct_entry_that_stays():
    s = [rec(1), H(2), H(5), H(8)]                                                                    # step 1 is before the entry (e = 2) and is not part of the events
    ev = EV.question_events(s, arr_of(城={2: "a", 5: "a", 8: "a"}))
    assert ev["appear"] == 2 and ev["at_entry"] is True and ev["delay"] == 0
    assert ev["stay"] == (2, 2) and ev["losses"] == [] and ev["never"] is None and ev["steps"] == [2, 5, 8]
    assert ev["appear_G"] == 2 and ev["stay_G"] == (2, 2)


def test_a_late_appearance_and_whether_it_took_late_input():
    s = [lost(2), lost(5), H(8, seats_after_entry=3), H(13)]
    ev = EV.question_events(s, arr_of())
    assert ev["appear"] == 8 and ev["at_entry"] is False and ev["delay"] == 6 and ev["late_input"] is True
    assert ev["stay"] == (1, 1)
    ev2 = EV.question_events([lost(2), H(5, seats_after_entry=0, src_after_entry=False)], arr_of())
    assert ev2["at_entry"] is False and ev2["late_input"] is False                                    # later, but nothing seated or cited after the entry
    ev3 = EV.question_events([lost(2), H(5, src_after_entry=True)], arr_of())
    assert ev3["late_input"] is True                                                                  # the source of the gold entry came from after the entry


def test_direct_entry_is_delay_zero_and_a_missing_entry_record_is_a_later_appearance_not_a_direct_one():
    """D3: 直入 = appear == e(q).  When the e(q) record of the question is missing although e(q) is on the arm's schedule (a hole in the run), the later
    appearance is a 後から; the old `i == 0` called it 直入."""
    ev = EV.question_events([H(5, e=3), H(8, e=3)], arr_of(), schedule=[3, 5, 8])                     # step 3 is scheduled, this question has no record there
    assert ev["at_entry"] is False and ev["delay"] == 2 and ev["entry_measured"] is False and ev["entry_on_schedule"] is True
    ev = EV.question_events([H(3, e=3), H(5, e=3)], arr_of(), schedule=[3, 5])
    assert ev["at_entry"] is True and ev["delay"] == 0 and ev["entry_measured"] is True and ev["late_input"] is False
    # events_of takes the schedule from the steps that have a record of ANY question: here Q2 has the record at 3, Q1 does not
    recs = [H(5, "Q1", e=3), H(8, "Q1", e=3), H(3, "Q2", e=3), H(5, "Q2", e=3)]
    evs = EV.events_of(recs, arr_of())
    assert evs["Q1"]["at_entry"] is False and evs["Q2"]["at_entry"] is True
    sm = EV.summarize_events(evs)
    assert (sm["at_entry"], sm["later"], sm["appeared_entry_unmeasured"]) == (1, 1, 0)


def test_an_entry_step_off_the_arms_schedule_makes_the_label_unknowable_and_is_counted_apart():
    """Arm C measures the Fibonacci steps only: e(q) = 3 is not one of {1, 2, 5, 8}.  The first measured step after it is neither 直入 nor 後から."""
    recs = [H(5, "Q1", e=3), H(8, "Q1", e=3), rec(1, "Q0", e=1)] + [rec(2, "Q0", e=1)]
    ev = EV.question_events([r for r in recs if r["qid"] == "Q1"], arr_of(), schedule=[1, 2, 5, 8])
    assert ev["at_entry"] is None and ev["appear"] == 5 and ev["delay"] == 2 and ev["entry_measured"] is False and ev["entry_on_schedule"] is False
    sm = EV.summarize_events({"Q1": ev})
    assert (sm["appeared"], sm["at_entry"], sm["later"], sm["appeared_entry_unmeasured"]) == (1, 0, 0, 1)
    assert "NOT on the arm's schedule" in EV.render_events({"Q1": ev})[0]


def test_stay_is_the_share_of_the_later_measured_steps_that_still_hold():
    s = [H(2), H(5), lost(8), H(13), lost(21)]
    ev = EV.question_events(s, arr_of(城={2: "a", 5: "a", 8: "b", 13: "b", 21: "c"}))
    assert ev["stay"] == (2, 4) and ev["appear"] == 2


def test_a_loss_whose_every_cross_was_rearranged_is_growth_not_broken():
    """OP-G4-3: 並び替えによる消失は「成長」 -- every gold cross R; a recount 絞り is one too (owner decision)."""
    s = [H(2), lost(5)]
    arr = EV.DictArr({("WORD", "城", 2): "a", ("WORD", "城", 5): "b"}, kinds={("WORD", "城", 2, 5): ["narrow_recount"]})
    ev = EV.question_events(s, arr)
    (L,) = ev["losses"]
    assert (L["from"], L["to"], L["class"], L["reason"]) == (2, 5, EV.GROWTH, "rearranged")
    assert L["tags"] == {"R": 1} and L["rearrangement_kinds"] == ["narrow_recount"] and L["single_wrong"] is False
    sm = EV.summarize_events({"Q1": ev})
    assert sm["growth"] == 1 and sm["breaks"] == 0 and sm["rearrangement_kinds"] == {"narrow_recount": 1}


def test_a_mixed_loss_r_and_u_is_broken_and_keeps_its_tags():
    g = [gold_row(seed="城"), gold_row(seed="寺", pos=1)]
    s = [rec(2, gold=g), lost(5, read=("城",))]                                                       # 城 rearranged (R); 寺 unchanged and not read (U)
    arr = EV.DictArr({("WORD", "城", 2): "a", ("WORD", "城", 5): "b", ("WORD", "寺", 2): "x", ("WORD", "寺", 5): "x"})
    (L,) = EV.question_events(s, arr)["losses"]
    assert L["class"] == EV.BREAK and L["reason"] == "cause" and L["tags"] == {"R": 1, "U": 1}


def test_the_causes_u_and_a():
    arr = EV.DictArr({("WORD", "城", 2): "a", ("WORD", "城", 5): "a"})
    (u,) = EV.question_events([H(2), lost(5, read=())], arr)["losses"]                                # same arrangement, the cross was not read at step 5
    assert u["tags"] == {"U": 1} and u["class"] == EV.BREAK
    (a,) = EV.question_events([H(2), lost(5, read=("城",))], arr)["losses"]                           # same arrangement, read, no gold came out
    assert a["tags"] == {"A": 1} and a["class"] == EV.BREAK
    sm = EV.summarize_events({"Q1": EV.question_events([H(2), lost(5, read=("城",))], arr)})
    assert sm["tag_crosses"] == {"A": 1} and sm["breaks"] == 1


def test_a_single_wrong_answer_after_a_rearrangement_is_broken():
    """D-3: 単独誤答化 is 壊れる whatever the cause, even when the gold cross was rearranged."""
    s = [H(2), rec(5, verdict="ANSWER", listed=1)]
    arr = EV.DictArr({("WORD", "城", 2): "a", ("WORD", "城", 5): "b"})
    (L,) = EV.question_events(s, arr)["losses"]
    assert L["class"] == EV.BREAK and L["reason"] == "single_wrong" and L["single_wrong"] is True and L["tags"] == {"R": 1}
    sm = EV.summarize_events({"Q1": EV.question_events(s, arr)})
    assert sm["single_wrong_losses"] == 1 and sm["breaks"] == 1 and sm["growth"] == 0


def test_a_loss_into_an_abstention_or_a_list_without_gold_is_not_a_single_wrong():
    arr = EV.DictArr({("WORD", "城", 2): "a", ("WORD", "城", 5): "b"})
    for v, n in (("UNKNOWN_NO_PATH", 0), ("CHOICE", 4)):
        (L,) = EV.question_events([H(2), rec(5, verdict=v, listed=n)], arr)["losses"]
        assert L["single_wrong"] is False and L["class"] == EV.GROWTH


def test_a_cross_that_cannot_be_looked_up_is_broken_and_counted_apart():
    (L,) = EV.question_events([H(2), lost(5)], EV.DictArr({}))["losses"]
    assert L["tags"] == {"?": 1} and L["class"] == EV.BREAK
    assert EV.summarize_events({"Q1": EV.question_events([H(2), lost(5)], EV.DictArr({}))})["unknown_cause"] == 1


def test_return_after_a_loss_and_unmeasured_steps_are_skipped():
    arr = arr_of(城={2: "a", 5: "b", 13: "b"})
    s = [H(2), lost(5), H(13)]                          # the steps between 5 and 13 are not measured: the loss is between consecutive measured records 2 -> 5
    ev = EV.question_events(s, arr)
    (L,) = ev["losses"]
    assert (L["from"], L["to"]) == (2, 5) and L["returns"] == 13 and ev["returned"] is True


def test_two_losses_are_each_judged_between_their_own_consecutive_steps():
    arr = EV.DictArr({("WORD", "城", 2): "a", ("WORD", "城", 5): "b", ("WORD", "城", 8): "b", ("WORD", "城", 13): "b"})
    s = [H(2), lost(5), H(8), lost(13, read=())]
    ev = EV.question_events(s, arr)
    assert [(L["from"], L["to"], L["class"]) for L in ev["losses"]] == [(2, 5, EV.GROWTH), (8, 13, EV.BREAK)]


def test_never_appearing_gets_a_tag_and_未着_is_left_out_of_the_denominator():
    q1 = [rec(2, "Q1", unarrived=True), rec(5, "Q1", unarrived=True)]                                      # 未着
    q2 = [rec(2, "Q2", site={"tag": "未読"}), rec(5, "Q2", site={"tag": "未読"})]                           # never appears: 未読
    q3 = [rec(2, "Q3", gold=[gold_row(from_evidence=False)]), rec(5, "Q3", gold=[gold_row(from_evidence=False)])]    # gold in a candidate, not from the evidence
    q4 = [H(2, "Q4"), H(5, "Q4")]
    q5 = [rec(2, "Q5"), rec(5, "Q5")]                                                                    # no site recorded
    recs = [r for q in (q1, q2, q3, q4, q5) for r in q]
    evs = EV.events_of(recs, arr_of(城={2: "a", 5: "a"}))
    assert evs["Q1"]["unarrived_final"] and evs["Q1"]["never"] == "未着"
    assert evs["Q2"]["never"] == "未読" and evs["Q3"]["never"] == "非根拠" and evs["Q5"]["never"] == "未特定"
    sm = EV.summarize_events(evs)
    assert sm["intra2"] == 5 and sm["unarrived"] == 1 and sm["denominator"] == 4                          # Q1 is counted apart
    assert sm["appeared"] == 1 and sm["at_entry"] == 1 and sm["later"] == 0
    assert sm["never"] == {"未読": 1, "非根拠": 1, "未特定": 1}
    assert sm["gold_in_candidate_final"] == 2                                                           # Q3 and Q4


def test_the_3tier_flag_can_replace_the_arm_flag_for_the_denominator():
    a = rec(2, "Q1", unarrived=True)
    a["unarrived_3tier"] = False
    evs = EV.events_of([a], EV.DictArr({}))
    assert EV.summarize_events(evs)["denominator"] == 0
    evs3 = EV.events_of([a], EV.DictArr({}), "unarrived_3tier")
    assert EV.summarize_events(evs3)["denominator"] == 1 and evs3["Q1"]["never"] == "未特定"


def test_the_absent_row_series_finds_the_first_single_answer():
    recs = [rec(1, "Q1", e=3, verdict="UNKNOWN_NO_PATH", listed=0), rec(2, "Q1", e=3, verdict="ANSWER", listed=1), rec(3, "Q1", e=3, verdict="CHOICE", listed=2),
            rec(1, "U1", kind="unans", verdict="CHOICE", listed=5, s=1), rec(2, "U1", kind="unans", verdict="CHOICE", listed=5, s=1)]
    ab = EV.absent_series(recs)
    assert ab["Q1"]["first_single_wrong"] == 2 and ab["Q1"]["steps"] == 2          # step 3 is present (e = 3)
    assert ab["U1"]["first_single_wrong"] is None and ab["U1"]["classes"] == {"miss/false_presence": 2}


def test_the_markdown_renders_from_synthetic_records():
    recs = [rec(1, "Q1"), H(2), lost(5), rec(5, "U1", kind="unans", verdict="CHOICE", listed=4, s=1)]
    arr = EV.DictArr({("WORD", "城", 2): "a", ("WORD", "城", 5): "b"})
    md = EV.render_md("A", recs, arr)
    assert "## 2x2 per step" in md and "置き換え" in md and "| Q1 |" in md and "Absent row" in md


def _full_step(arm, h, g=0, ungot=0, step=300, answer_unans=0, abstain_unans=25):
    """A complete step: 69 intra2 (h present-correct, then g more with gold not from evidence, ungot unarrived, rest list-without-gold) + 25 unans."""
    out, n = [], 0
    for i in range(69):
        q = "I%02d" % i
        if n < h:
            out.append(dict(H(step, q, e=1), arm=arm))
        elif n < h + g:
            out.append(dict(rec(step, q, e=1, verdict="CHOICE", listed=3, gold=[gold_row(from_evidence=False)]), arm=arm))
        elif n < h + g + ungot:
            out.append(dict(rec(step, q, e=1, verdict="UNKNOWN_NO_PATH", listed=0, unarrived=True), arm=arm))
        else:
            out.append(dict(rec(step, q, e=1, verdict="CHOICE", listed=3), arm=arm))
        n += 1
    for i in range(25):
        v, ln = ("ANSWER", 1) if i < answer_unans else (("UNKNOWN_NO_PATH", 0) if i < answer_unans + abstain_unans else ("CHOICE", 4))
        out.append(dict(rec(step, "U%02d" % i, kind="unans", verdict=v, listed=ln, s=1), arm=arm))
    return out


def test_the_registered_predictions_are_judged_only_on_a_complete_step():
    arr = EV.DictArr({})
    partial = {"A": ([rec(5, "Q1")], EV.events_of([rec(5, "Q1")], arr))}
    assert {pid for pid, _t, _v, s in EV.judge(partial) if not s.startswith("not judged")} <= {"P-9"}      # P-9 is a property of the series, not of step 300
    a = _full_step("A", h=10, g=3, ungot=7, answer_unans=2, abstain_unans=3)
    c = _full_step("C", h=12, g=9, ungot=4, answer_unans=1, abstain_unans=4)
    b = _full_step("B", h=2, g=0, ungot=60)
    arms = {n: (r, EV.events_of(r, arr)) for n, r in (("A", a), ("B", b), ("C", c))}
    got = {pid: (status, value) for pid, _t, value, status in EV.judge(arms)}
    assert got["P-11"][0] == "held" and got["P-8"][0] == "held" and got["P-5"][0] == "held"                 # 10 <= 20; 7 in 5..25; B 2 <= 3
    assert got["P-3"][0].startswith("not judged") and got["P-10"][0].startswith("not judged")               # no loss, no appeared-with-a-later-step: unjudgeable, not failed
    assert got["P-4"][0] == "held" and "single ANSWER on the absent row: True" in got["P-4"][1]            # 3 and 4 abstain <= 5; an ANSWER on the absent row exists
    assert got["P-2"][0] == "held" and got["P-2"][1] == "A 13, C 21"                                         # 13 <= 21 - 3
    assert got["P-7"][0].startswith("not judged")
    md = EV.summary_md(arms)
    assert "## Registered predictions" in md and "| A |" in md and "| C |" in md
    # a prediction that fails says so
    a2 = _full_step("A", h=30)
    assert {p: s for p, _t, _v, s in EV.judge({"A": (a2, EV.events_of(a2, arr))})}["P-11"] == "failed"


# =============================================================================================================
# Part 3: the arrangement oracles
# =============================================================================================================
def ledger_line(step, opened=(), grown=()):
    return json.dumps({"step": step, "opened": list(opened), "grown": list(grown)})


def grown(seed, before, after, filled=(), narrowed=False, dropped_new=0, dropped_recount=0):
    return {"seed": seed, "arr": [before, after], "filled": list(filled), "narrowed": narrowed, "dropped_new": dropped_new, "dropped_recount": dropped_recount}


def test_the_ledger_oracle_sees_fill_narrow_and_recount_but_not_a_recount_free_regrowth_of_nothing():
    lines = [ledger_line(1, opened=["城", "寺"]),
             ledger_line(2, opened=["庭"], grown=[grown("城", "a", "b", filled=["庭"])]),                      # 充填
             ledger_line(3, grown=[grown("城", "b", "c", narrowed=True, dropped_new=1)]),                     # 絞り (a unit that left)
             ledger_line(4, grown=[grown("寺", "x", "y", narrowed=True, dropped_recount=2)]),                 # recount 絞り only
             ledger_line(5, grown=[grown("庭", "p", "p")])]                                                   # grown but the arrangement is the same
    o = EV.LedgerArr.from_ledgers({"WORD": lines})
    assert o.changed("WORD", "城", 1, 2) is True and o.kinds("WORD", "城", 1, 2) == ["fill"]
    assert o.changed("WORD", "城", 2, 3) is True and o.kinds("WORD", "城", 2, 3) == ["narrow_new"]
    assert o.changed("WORD", "城", 3, 5) is False                                                           # nothing in (3, 5]
    assert o.changed("WORD", "寺", 1, 5) is True and o.kinds("WORD", "寺", 1, 5) == ["narrow_recount"]
    assert o.changed("WORD", "庭", 2, 5) is False                                                           # born at 2, 'grown' at 5 with an equal arr
    assert o.changed("WORD", "無", 1, 5) is None and o.changed("WORD", "城", 1, 9) is None                  # unknown seed / beyond the ledger: unlookable


# =============================================================================================================
# the toy: 4 articles (A..D), one question per shape
# =============================================================================================================
TOY_BANK = [
    ["I-1", "intra2", "fulllead", "A", "東京の城は何ですか", "大きい", "A#1", "valid"],
    ["I-2", "intra2", "fulllead", "C", "京都の寺は何ですか", "寺と城", "C#5", "valid"],
    ["I-3", "intra2", "fulllead", "D", "京都の庭は何ですか", "静か", "D#7", "valid"],
    ["U-1", "unans", "fulllead", "B", "大阪の人口は何人ですか", "", "B#2", "valid"],
    ["U-2", "unans", "fulllead", "C", "京都の寺は何年にできましたか", "", "C#4", "valid"],
]
TOY_BANK_TSV = "#id\tkind\tcorpus\tsubject\tquestion\tgold\tevidence\taudit\n" + "".join("\t".join(r) + "\n" for r in TOY_BANK)
REQUIRED = ("format", "arm", "step", "article", "prefix_sha256", "structure_sha256", "seats_sha", "code_sha256", "qid", "kind", "e", "s", "entered", "evidence_sids",
            "verdict", "listed", "partial", "left_unread", "rebuild_refused", "tied_group_not_split", "tiers", "gold_in_candidate", "gold_entries", "first_gold_pos",
            "gold", "single_wrong", "unarrived", "answer_sha256", "answer_obj_sha256", "question_side", "n_standins", "cell", "site")


@pytest.fixture(scope="module", autouse=True)
def reader():
    M.import_reader(True)


@pytest.fixture(scope="module")
def toy_files(tmp_path_factory):
    d = tmp_path_factory.mktemp("g4meter")
    data = d / "toy.jsonl"
    data.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows(SENTS)), encoding="utf-8")
    bank = d / "bank.tsv"
    bank.write_text(TOY_BANK_TSV, encoding="utf-8")
    stack_root = d / "stack"
    docs = st.load_docs(str(data))
    state = st.empty_state("on", ALL, LEVEL)
    for doc in docs:
        state = st.extend(state, doc, 1)
        st.save(state, str(stack_root))
    return {"dir": d, "data": str(data), "bank": str(bank), "stack": str(stack_root), "docs": docs}


def toy_cfg(files, arm, out, workers=1, src=None, **kw):
    spec = dict(M.ARMS[arm])
    cfg = {"arm": arm, "spec": spec, "src": src or files["stack"], "level": LEVEL, "effort": "fast", "workers": workers, "out": str(out), "site": True,
           "started": "t", "code_sha": "c" * 64, "arrival": None}
    cfg.update(kw)
    return cfg


def toy_corpus(files, order="forward"):
    return M.Corpus(files["docs"], M.read_bank(files["bank"]), order)


def run_toy(files, arm, out, workers=1, steps=(1, 2, 3, 4), questions="all", **kw):
    cfg = toy_cfg(files, arm, out, workers, **kw)
    corpus = toy_corpus(files, cfg["spec"]["order"])
    qs = M.select_questions(corpus.questions, questions)
    rep = M.run(cfg, corpus, list(steps), qs, log=lambda m: None)
    return cfg, corpus, rep


def mfile(out, arm="A", kind="jsonl"):
    """The one result file of an arm in a directory: results are keyed meter_<arm>.<config key>.<kind>."""
    names = [f for f in os.listdir(str(out)) if f.startswith("meter_%s." % arm) and f.endswith("." + kind) and (kind != "jsonl" or EV.parse_stem(f))]
    assert len(names) == 1, (arm, kind, names)
    return os.path.join(str(out), names[0])


def records_of(out, arm="A"):
    return EV.load_records(mfile(out, arm))


def shas_of(out, arm="A"):
    d = {}
    for line in open(mfile(out, arm), encoding="utf-8"):
        try:
            o = json.loads(line)
        except ValueError:                                                                              # a line cut by a kill
            continue
        if "record" in o:
            d[(o["record"]["step"], o["record"]["qid"])] = o["record_sha256"]
    return d


# =============================================================================================================
# Part 4: the meter on the toy stack
# =============================================================================================================
def test_the_corpus_gives_entry_steps_and_the_sids_of_the_evidence_article(toy_files):
    c = toy_corpus(toy_files)
    pos = {q["qid"]: q["pos"] for q in c.questions}
    assert pos == {"I-1": 1, "I-2": 3, "I-3": 4, "U-1": 2, "U-2": 3}
    assert c.article_sids(1, 4) == [0, 1] and c.article_sids(3, 4) == [4, 5] and c.article_sids(3, 2) == []        # not entered: nothing
    assert c.entry_sid("C#5", 4, 3) == 5 and c.entry_sid("C#5", 2, 3) is None and c.entry_sid("C#9", 4, 3) is None
    r = toy_corpus(toy_files, "reverse")
    assert r.titles == ["D", "C", "B", "A"] and r.article_sids(1, 4) == [0, 1]                                    # the first article is D, its own sentences kept
    with pytest.raises(ValueError, match="distinct"):
        M.Corpus([toy_files["docs"][0], toy_files["docs"][0]], [])


def test_subsets_of_questions_and_steps(toy_files):
    c = toy_corpus(toy_files)
    ids = lambda spec: [q["qid"] for q in M.select_questions(c.questions, spec)]            # noqa: E731
    assert ids("all") == ["I-1", "I-2", "I-3", "U-1", "U-2"]
    assert ids("intra2") == ["I-1", "I-2", "I-3"] and ids("unans") == ["U-1", "U-2"]
    assert ids("e<=3,s<=2") == ["I-1", "I-2", "U-1"] and ids("e<=1,unans:1") == ["I-1", "U-1"] and ids("U-2,I-3") == ["I-3", "U-2"]
    with pytest.raises(ValueError, match="unknown question ids"):
        ids("Z-9")
    sj = {"measured_steps": [1, 2, 4], "fibonacci_steps": [1, 2, 3]}
    assert M.parse_steps(None, "measured", sj, 4) == [1, 2, 4] and M.parse_steps("fib", "measured", sj, 4) == [1, 2, 3]
    assert M.parse_steps("last", "measured", sj, 4) == [4] and M.parse_steps("2-3,1", "measured", sj, 4) == [1, 2, 3]
    with pytest.raises(ValueError):
        M.parse_steps("9", "measured", sj, 4)


def test_every_record_has_the_schema_canonical_bytes_and_no_float(toy_files, tmp_path):
    cfg, corpus, rep = run_toy(toy_files, "A", tmp_path / "a")
    assert rep["errors"] == 0 and rep["done"] == 4 * 5
    recs = records_of(tmp_path / "a")
    assert len(recs) == 20
    for r in recs:
        assert set(REQUIRED) <= set(r), set(REQUIRED) - set(r)
        M.assert_no_float(r)
        assert r["format"] == EV.FORMAT and r["arm"] == "A" and len(r["answer_sha256"]) == 64 and len(r["prefix_sha256"]) == 64
        assert set(r["structure_sha256"]) == set(ALL) and r["seats_sha"]
        assert r["verdict"] in ("ANSWER", "CHOICE") or r["verdict"].startswith("UNKNOWN")
        assert r["entered"] == (r["kind"] == "intra2" and r["step"] >= r["e"])
        assert r["article"] == corpus.titles[r["step"] - 1]
    for line in open(mfile(tmp_path / "a", "A"), encoding="utf-8"):
        o = json.loads(line)
        assert o["record_sha256"] == hashlib.sha256(M.cj(o["record"]).encode("utf-8")).hexdigest()
        assert line.rstrip("\n") == M.cj(o)                                                           # the line IS the canonical form
        assert set(o["cost"]) == {"cpu_ms", "wall_ms", "load1", "host", "pid"}                         # time and load are outside the hashed record
    with pytest.raises(TypeError, match="float"):
        M.assert_no_float({"a": [1, {"b": 0.5}]})


def test_evidence_flags_follow_the_article_and_the_step(toy_files, tmp_path):
    run_toy(toy_files, "A", tmp_path / "a")
    by = {(r["step"], r["qid"]): r for r in records_of(tmp_path / "a")}
    assert by[(1, "I-1")]["entered"] and by[(1, "I-1")]["evidence_sids"] == [0, 1] and by[(1, "I-1")]["e"] == 1
    assert not by[(2, "I-2")]["entered"] and by[(2, "I-2")]["evidence_sids"] == [] and by[(3, "I-2")]["evidence_sids"] == [4, 5]
    assert by[(3, "I-2")]["evidence_sid"] == 5 and by[(2, "U-1")]["evidence_sids"] == [] and by[(2, "U-1")]["s"] == 2 and by[(2, "U-1")]["e"] is None
    assert by[(4, "I-3")]["unarrived"] is False and by[(1, "I-1")]["unarrived"] in (True, False)
    assert by[(1, "U-1")]["unarrived"] is None and by[(1, "U-1")]["gold_in_candidate"] is None            # an unans question has no gold
    # nothing before its article can be from the evidence (the impossible case is refused at record time)
    for r in by.values():
        if not r["entered"]:
            assert all(not g["from_evidence"] for g in r["gold"])


def test_a_gold_entry_carries_its_provenance(toy_files, tmp_path):
    run_toy(toy_files, "A", tmp_path / "a", questions="I-1")
    got = [r for r in records_of(tmp_path / "a") if r["gold"]]
    assert got, "the toy question I-1 should list the gold 大きい in some entry"
    g = got[0]["gold"][0]
    assert {"pos", "tier", "words", "source_sids", "from_evidence", "pre_entry_hit", "origins"} <= set(g)
    o = g["origins"][0]
    assert {"tier", "seed", "member", "stability", "arr", "opened_at", "closed_at", "seated", "read", "seats_after_entry", "r2", "r3", "ratios_eval"} <= set(o)
    assert o["ratios"] == o["ratios_eval"]                                          # r2 / r3 come from the reader that adopted the state: its status is the end state's
    assert all(x is None or isinstance(x, str) for x in (o["r2"], o["r3"]))        # units or None, never a float
    assert got[0]["first_gold_pos"] == got[0]["gold_entries"][0] and got[0]["gold_in_candidate"] is True
    assert all(isinstance(x["read"], bool) for x in g["origins"])
    assert got[0]["cell"].startswith("present/") or got[0]["cell"].startswith("absent/")


def test_the_record_bytes_are_deterministic_across_workers_and_hash_seeds(toy_files, tmp_path):
    run_toy(toy_files, "A", tmp_path / "w1", workers=1)
    run_toy(toy_files, "A", tmp_path / "w2", workers=2)
    assert shas_of(tmp_path / "w1") == shas_of(tmp_path / "w2") and len(shas_of(tmp_path / "w1")) == 20
    # another hash seed, in a fresh process
    prog = ("import sys, json; sys.path.insert(0, %r); sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
            "import meter as M\nM.import_reader(True)\n"
            "from test_g4_meter import *\n"
            "files = {'data': %r, 'bank': %r, 'stack': %r, 'docs': M.st.load_docs(%r)}\n"
            "run_toy(files, 'A', %r, 1)\n") % (G4, HERE, ROOT, toy_files["data"], toy_files["bank"], toy_files["stack"], toy_files["data"], str(tmp_path / "s7"))
    out = subprocess.run([PY, "-c", prog], capture_output=True, text=True, env=dict(os.environ, PYTHONHASHSEED="7", PYTHONPATH=ROOT))
    assert out.returncode == 0, out.stderr[-2000:]
    assert shas_of(tmp_path / "s7") == shas_of(tmp_path / "w1")


def test_resume_skips_what_is_recorded_and_retries_errors_and_cut_lines(toy_files, tmp_path):
    out = tmp_path / "r"
    run_toy(toy_files, "A", out, steps=(1, 2))
    path = __import__("pathlib").Path(mfile(out, "A"))
    before = shas_of(out)
    assert len(before) == 10
    size = path.stat().st_size
    cfg, corpus, rep = run_toy(toy_files, "A", out, steps=(1, 2))                                      # nothing to do
    assert rep["done"] == 0 and path.stat().st_size == size
    cfg, corpus, rep = run_toy(toy_files, "A", out, steps=(1, 2, 3))                                   # only step 3
    assert rep["done"] == 5 and len(shas_of(out)) == 15 and {k: v for k, v in shas_of(out).items() if k[0] < 3} == before
    # a kill: one record is replaced by an error line, the last line is cut in half
    all_before = shas_of(out)
    lines = path.read_text(encoding="utf-8").splitlines()
    victim = next(i for i, l in enumerate(lines) if '"qid":"I-2"' in l and '"step":3' in l and i != len(lines) - 1)
    lost_keys = {(3, "I-2"), (json.loads(lines[-1])["record"]["step"], json.loads(lines[-1])["record"]["qid"])}
    path.write_text("\n".join(lines[:victim] + ['{"arm":"A","step":3,"qid":"I-2","error":"boom"}'] + lines[victim + 1:-1]) + "\n" + lines[-1][:40], encoding="utf-8")
    assert len(EV.load_errors(str(path))) == 1 and set(all_before) - set(shas_of(out)) == lost_keys
    cfg, corpus, rep = run_toy(toy_files, "A", out, steps=(1, 2, 3))
    assert rep["done"] == len(lost_keys) and shas_of(out) == all_before                                  # the retried records equal the first run, byte for byte
    run_toy(toy_files, "A", tmp_path / "uninterrupted", steps=(1, 2, 3))
    assert shas_of(tmp_path / "uninterrupted") == shas_of(out)                                          # and an uninterrupted run elsewhere


def test_questions_and_steps_subsets_write_only_those(toy_files, tmp_path):
    run_toy(toy_files, "A", tmp_path / "s", steps=(2, 4), questions="I-1,U-1")
    assert sorted(shas_of(tmp_path / "s")) == [(2, "I-1"), (2, "U-1"), (4, "I-1"), (4, "U-1")]


def test_a_failing_step_is_recorded_not_fatal(toy_files, tmp_path):
    cfg = toy_cfg(toy_files, "A", tmp_path / "f")
    cfg["src"] = str(tmp_path / "nowhere")
    rep = M.run(cfg, toy_corpus(toy_files), [1], M.select_questions(toy_corpus(toy_files).questions, "I-1"), log=lambda m: None)
    assert rep["errors"] == 1 and rep["done"] == 0
    errs = EV.load_errors(mfile(tmp_path / "f", "A"))
    assert errs[0]["step"] == 1 and "stack" in errs[0]["error"]


def test_the_markdown_and_the_events_from_the_toy_records(toy_files, tmp_path):
    cfg, corpus, rep = run_toy(toy_files, "A", tmp_path / "m")
    md = M.render(cfg)
    assert md and "## 2x2 per step" in md and "## Events" in md
    arr = EV.stack_arr(toy_files["stack"], "on", LEVEL)
    evs = EV.events_of(records_of(tmp_path / "m"), arr)
    assert sorted(evs) == ["I-1", "I-2", "I-3"]
    for q, e in evs.items():
        assert e["steps"][0] == e["e"] and e["appear"] in (None,) + tuple(e["steps"])
    assert os.path.exists(mfile(tmp_path / "m", "A", "md"))
    # the ledger oracle agrees with the snapshots: arr_sha of a cross changed between two steps exactly when the oracle says so
    s1 = st.load(toy_files["stack"], st.prefix_sha256(toy_files["docs"][:1]), "on", ALL, LEVEL)
    s4 = st.load(toy_files["stack"], st.prefix_sha256(toy_files["docs"][:4]), "on", ALL, LEVEL)
    n = 0
    for t in ALL:
        for seed, c1 in s1.crosses[t].items():
            same = st.arr_sha(c1) == st.arr_sha(s4.crosses[t][seed])
            assert arr.changed(t, seed, 1, 4) is (not same)
            n += 1
    assert n > 10


def test_the_meta_names_the_arm_and_the_code(toy_files, tmp_path):
    cfg, corpus, rep = run_toy(toy_files, "A", tmp_path / "meta", steps=(1,), questions="I-1")
    M.write_meta(cfg, ["--arm", "A"], rep, [1], corpus.questions[:1])
    meta = json.load(open(mfile(tmp_path / "meta", "A", "meta.json"), encoding="utf-8"))
    r = meta["runs"][0]
    assert r["argv"] == ["--arm", "A"] and r["effort"] == "fast" and isinstance(r["dictionary_modules_blocked_at_exit"], bool) and r["arm_spec"]["grammar"] == "on"
    shas = M.code_shas()
    assert {"ask", "stack", "meter", "events", "scorer"} <= set(shas) and all(len(v) == 64 for v in shas.values())


# =============================================================================================================
# Part 5: the one-shot arm (C) on the toy
# =============================================================================================================
@pytest.fixture(scope="module")
def oneshot(toy_files, tmp_path_factory):
    d = tmp_path_factory.mktemp("oneshot")
    for k in (1, 2, 3, 4):
        p = d / ("prefix_%d.jsonl" % k)
        p.write_bytes(st.prefix_bytes(toy_files["docs"][:k]))
        ix = A.Index.from_jsonl(str(p), None, LEVEL, ALL, group_insert="ordered", on_collapse="stop")
        ix.precompute(str(d / "cache"))
        assert A.file_sha256(str(p)) == st.prefix_sha256(toy_files["docs"][:k])
    return str(d / "cache")


def test_arm_c_reads_the_one_shot_caches_and_writes_the_arrangement_table(toy_files, oneshot, tmp_path):
    cfg, corpus, rep = run_toy(toy_files, "C", tmp_path / "c", src=oneshot)
    assert rep["errors"] == 0 and rep["done"] == 20
    recs = records_of(tmp_path / "c", "C")
    assert all(r["seats_sha"] is None and set(r["structure_sha256"]) == set(ALL) for r in recs)
    assert all(g["origins"][0]["opened_at"] is None for r in recs for g in r["gold"])               # a one-shot cross has no stack history
    tab = [json.loads(l) for l in open(mfile(tmp_path / "c", "C", "arr.jsonl"), encoding="utf-8")]
    assert sorted((o["step"], o["tier"]) for o in tab) == sorted((k, t) for k in (1, 2, 3, 4) for t in ALL)
    arr = EV.sha_arr(mfile(tmp_path / "c", "C", "arr.jsonl"))
    seed = sorted(tab[0]["arr"])[0]
    assert arr.changed(tab[0]["tier"], seed, 1, 1) is False and arr.changed(tab[0]["tier"], "無い", 1, 2) is None
    md = M.render(cfg)
    assert "arm C" in md
    run_toy(toy_files, "C", tmp_path / "c", src=oneshot)                                            # resume: the table is not written twice
    assert len([1 for _ in open(mfile(tmp_path / "c", "C", "arr.jsonl"), encoding="utf-8")]) == 12


def test_arm_c_without_a_cache_for_the_step_is_an_error_record_not_a_silent_build(toy_files, oneshot, tmp_path):
    cfg = toy_cfg(toy_files, "C", tmp_path / "c2", src=str(tmp_path / "empty"))
    rep = M.run(cfg, toy_corpus(toy_files), [2], M.select_questions(toy_corpus(toy_files).questions, "I-1"), log=lambda m: None)
    assert rep["errors"] == 1 and "no one-shot placement cache" in EV.load_errors(mfile(tmp_path / "c2", "C"))[0]["error"]


# =============================================================================================================
# Part 6: the dictionary-free arm B
# =============================================================================================================
def test_a_dictionary_free_arm_refuses_a_process_that_already_imported_the_dictionary():
    prog = ("import sys; sys.path.insert(0, %r); sys.path.insert(0, %r)\nimport fugashi\nimport meter as M\n"
            "try:\n    M.import_reader(False)\nexcept RuntimeError as e:\n    print('refused', e)\n") % (G4, ROOT)
    out = subprocess.run([PY, "-c", prog], capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=ROOT))
    assert out.returncode == 0 and "refused" in out.stdout, out.stderr[-1500:]


def test_arm_b_runs_without_fugashi_and_reads_the_char_tier_of_arms_stack(toy_files, tmp_path):
    out = tmp_path / "b"
    argv = [PY, os.path.join(G4, "meter.py"), "--arm", "B", "--stack", toy_files["stack"], "--data", toy_files["data"], "--bank", toy_files["bank"], "--level", LEVEL,
            "--steps", "1-4", "--questions", "all", "--workers", "1", "--out", str(out), "--units-from", toy_files["stack"]]
    res = subprocess.run(argv, capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED="0"))
    assert res.returncode == 0, res.stderr[-3000:] + res.stdout[-1000:]
    recs = records_of(out, "B")
    assert len(recs) == 20 and all(set(r["tiers"]) == {"CHAR"} and r["n_standins"] == 0 for r in recs)
    meta = json.load(open(mfile(out, "B", "meta.json"), encoding="utf-8"))
    assert meta["runs"][0]["dictionary_modules_blocked_at_exit"] is True
    # B's structure is A's CHAR stack: the same state sha at the same step
    run_toy(toy_files, "A", tmp_path / "a4", steps=(1, 4), questions="I-1")
    a = {r["step"]: r["structure_sha256"]["CHAR"] for r in records_of(tmp_path / "a4")}
    assert all(r["structure_sha256"]["CHAR"] == a[r["step"]] for r in recs if r["step"] in a)
    # the 3-tier 未着 flag is available (from A's ledgers), the arm flag is CHAR only
    assert all(r["unarrived_3tier"] is not None for r in recs if r["kind"] == "intra2")
    # a CHAR-only arm cannot have been given the dictionary
    prog = ("import sys; sys.modules['fugashi']=None; sys.modules['unidic_lite']=None\ntry:\n    import fugashi\n    print('imported')\nexcept ImportError:\n    print('blocked')\n")
    assert subprocess.run([PY, "-c", prog], capture_output=True, text=True).stdout.strip() == "blocked"


def test_arm_c_b_reads_the_one_shot_char_caches_without_fugashi(toy_files, oneshot, tmp_path):
    """One-shot + a blocked dictionary + unpickling the placements: the one combination that only this arm exercises."""
    out = tmp_path / "cb"
    argv = [PY, os.path.join(G4, "meter.py"), "--arm", "C_B", "--cache", oneshot, "--data", toy_files["data"], "--bank", toy_files["bank"], "--level", LEVEL,
            "--steps", "1-4", "--questions", "all", "--workers", "1", "--out", str(out), "--units-from", toy_files["stack"]]
    res = subprocess.run(argv, capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED="0"))
    assert res.returncode == 0, res.stderr[-3000:] + res.stdout[-1000:]
    recs = records_of(out, "C_B")
    assert len(recs) == 20 and all(set(r["tiers"]) == {"CHAR"} and r["seats_sha"] is None and set(r["structure_sha256"]) == {"CHAR"} for r in recs)
    assert json.load(open(mfile(out, "C_B", "meta.json"), encoding="utf-8"))["runs"][0]["dictionary_modules_blocked_at_exit"] is True
    tab = [json.loads(l) for l in open(mfile(out, "C_B", "arr.jsonl"), encoding="utf-8")]
    assert sorted((o["step"], o["tier"]) for o in tab) == [(k, "CHAR") for k in (1, 2, 3, 4)]
    # the same CHAR caches read in-process by the reader that has the dictionary give the same verdicts (the dictionary changes nothing for a CHAR-only read)
    run_toy(toy_files, "C_B", tmp_path / "cb_in", src=oneshot)
    a = {k: v["verdict"] for k, v in {(r["step"], r["qid"]): r for r in records_of(tmp_path / "cb_in", "C_B")}.items()}
    b = {(r["step"], r["qid"]): r["verdict"] for r in recs}
    assert a == b


# =============================================================================================================
# Part 7: the review fixes (D2..D14)
# =============================================================================================================
def b_rec(step, qid="Q1", own=True, tier3=False, **kw):
    """A record of arm B: the arm's own (CHAR-only) 未着 flag and the 3-tier flag differ."""
    r = rec(step, qid, arm="B", **kw)
    r["unarrived"], r["unarrived_3tier"] = own, tier3
    return r


def test_the_primary_unarrived_flag_is_the_3tier_one_for_b_and_c_b_with_the_arms_own_count_beside_it():
    assert EV.primary_key("A") == "unarrived" and EV.primary_key("B") == "unarrived_3tier" and EV.primary_key("C_B") == "unarrived_3tier" and EV.primary_key("C") == "unarrived"
    # B: the CHAR-only flag calls Q1 and Q2 未着, the 3-tier flag only Q2
    recs = [b_rec(2, "Q1", own=True, tier3=False, verdict="CHOICE", listed=3), b_rec(2, "Q2", own=True, tier3=True, verdict="UNKNOWN_NO_PATH", listed=0),
            b_rec(5, "Q1", own=True, tier3=False, verdict="CHOICE", listed=3), b_rec(5, "Q2", own=True, tier3=True, verdict="UNKNOWN_NO_PATH", listed=0)]
    t = EV.table_2x2([r for r in recs if r["step"] == 5])
    assert t["key"] == "unarrived_3tier" and t["present_unarrived"] == 1 and t["present_unarrived_own"] == 2 and t["present_den"]["n"] == 1
    evs = EV.events_of(recs, EV.DictArr({}))
    assert EV.summarize_events(evs)["unarrived"] == 1 and EV.summarize_events(evs)["denominator"] == 1 and evs["Q1"]["key"] == "unarrived_3tier"
    own = EV.events_of(recs, EV.DictArr({}), "unarrived")
    assert EV.summarize_events(own)["unarrived"] == 2
    md = EV.render_md("B", recs, EV.DictArr({}))
    assert "the arm's own tiers" in md and "| 未着 at the last step, flag `unarrived_3tier`" in md and "the arm's own flag `unarrived`" in md
    assert "WARNING" not in md


def test_an_unknown_3tier_flag_is_shown_not_read_as_arrived():
    """D8: the arrival oracle did not load -> unarrived_3tier is None.  It must not fall in the denominator as 'arrived' unnoticed, and the markdown says so."""
    recs = [b_rec(2, "Q1", own=True, tier3=None, verdict="CHOICE", listed=3), b_rec(5, "Q1", own=True, tier3=None, verdict="CHOICE", listed=3)]
    assert EV.flag_unknown(recs[0], "unarrived_3tier") and EV.is_unarrived(recs[0], "unarrived_3tier") is None
    sm = EV.summarize_events(EV.events_of(recs, EV.DictArr({}), "unarrived_3tier"))
    assert sm["unarrived_unknown"] == 1 and sm["denominator"] == 0 and sm["unarrived"] == 0                      # in neither, and counted
    t = EV.table_2x2(recs[1:])
    assert t["present_unarrived_unknown"] == 1
    md = EV.render_md("B", recs, EV.DictArr({}))
    assert "WARNING" in md and "arrival oracle" in md and "did not load" in md
    assert "use the arm's own flag `unarrived`" in md.replace("The tables below use the arm's own flag", "use the arm's own flag") or "arm's own flag" in md   # the fallback is announced


def _sched_arm(steps, h=1, arm="A"):
    out = []
    for k in steps:
        out += _full_step(arm, h=h, step=k)
    return out


def test_a_prediction_is_judged_only_when_every_scheduled_step_is_complete():
    """D3/judge: a hole in a step before 300 makes the arm unjudgeable, not only a hole at 300."""
    arr = EV.DictArr({})
    ok = _sched_arm([100, 300])
    holes = [r for r in ok if not (r["step"] == 100 and r["qid"] == "I05")]                                       # step 100 lacks one question
    pick = lambda recs, **kw: {pid: st for pid, _t, _v, st in EV.judge({"A": (recs, EV.events_of(recs, arr))}, 300, **kw)}      # noqa: E731
    assert pick(ok)["P-11"] == "held"
    got = pick(holes)
    assert got["P-11"].startswith("not judged") and "incomplete" in got["P-11"] and "100" in got["P-11"]
    # a scheduled step with no record at all is a hole too
    got = pick(ok, schedules={"A": [100, 200, 300]})
    assert got["P-11"].startswith("not judged") and "200" in got["P-11"]
    assert pick(ok, schedules={"A": [100, 300]})["P-11"] == "held"
    md = EV.render_md("A", holes, arr, schedule=[100, 300])
    assert "not judged: arm A has 1 of 2 scheduled steps incomplete" in md


def test_scheduled_steps_follow_the_arm_table_of_the_meter():
    assert EV.ARM_STEPS == {a: spec["steps"] for a, spec in M.ARMS.items()}
    sj = json.load(open(os.path.join(G4, "steps.json"), encoding="utf-8"))
    assert len(EV.scheduled_steps("A", sj)) == 66 and EV.scheduled_steps("C", sj) == sj["fibonacci_steps"] and EV.scheduled_steps("C_F", sj) == [300]


def test_p4_is_judged_on_both_arms_or_not_at_all_and_p1_checks_the_direct_share():
    arr = EV.DictArr({})
    a = _full_step("A", h=3, answer_unans=2, abstain_unans=3)
    only_a = {pid: st for pid, _t, _v, st in EV.judge({"A": (a, EV.events_of(a, arr))})}
    assert only_a["P-4"].startswith("not judged") and "arm C" in only_a["P-4"]
    c = _full_step("C", h=3, answer_unans=0, abstain_unans=20)                                                    # C abstains 20 > 5: P-4 fails on C
    both = {pid: st for pid, _t, _v, st in EV.judge({"A": (a, EV.events_of(a, arr)), "C": (c, EV.events_of(c, arr))})}
    assert both["P-4"] == "failed"
    # P-1: direct entries must be more than half of the appeared AND 後から <= 5.  _full_step has e = 1 and H at 300 only, so every appeared question is 後から (the
    # schedule is {300}, e = 1 is off it -> unknowable) ...
    unk = {pid: st for pid, _t, _v, st in EV.judge({"A": (a, EV.events_of(a, arr))})}
    assert unk["P-1"].startswith("not judged") and "unmeasured entry" in unk["P-1"]
    # ... a schedule that holds step 1 turns them into 後から: 3 <= 5 but 0 direct of 3 is not 'most' -> failed
    recs = _sched_arm([1], h=0) + _full_step("A", h=3, step=300)
    got = {pid: (st, v) for pid, _t, v, st in EV.judge({"A": (recs, EV.events_of(recs, arr))}, 300, schedules={"A": [1, 300]})}
    assert got["P-1"][0] == "failed" and "直入 0, 後から 3" in got["P-1"][1]
    # direct entries: H at step 1 for 3 questions (their e is 1 and step 1 is scheduled) -> 直入 3 of 3: held
    direct = [dict(H(1, "I%02d" % i, e=1), arm="A") for i in range(3)]
    recs = _sched_arm([1, 300], h=0)
    recs = [r for r in recs if not (r["step"] == 1 and r["qid"] in ("I00", "I01", "I02"))] + direct
    recs = [r for r in recs if not (r["step"] == 300 and r["qid"] in ("I00", "I01", "I02"))] + [dict(H(300, "I%02d" % i, e=1), arm="A") for i in range(3)]
    got = {pid: (st, v) for pid, _t, v, st in EV.judge({"A": (recs, EV.events_of(recs, arr))}, 300, schedules={"A": [1, 300]})}
    assert got["P-1"][0] == "held" and "直入 3, 後から 0" in got["P-1"][1]


def test_p12_leaves_out_one_character_golds_and_needs_the_gold_lengths():
    arr = EV.DictArr({})
    a = _full_step("A", h=0, g=3)                                                                                  # A has no present-correct, 3 golds in a candidate
    b = _full_step("B", h=2, g=0)                                                                                  # B has I00 and I01 correct
    arms = {"A": (a, EV.events_of(a, arr)), "B": (b, EV.events_of(b, arr))}
    unknown = {pid: (st, v) for pid, _t, v, st in EV.judge(arms)}
    assert unknown["P-12"][0].startswith("not judged") and "gold lengths" in unknown["P-12"][0]
    failed = {pid: (st, v) for pid, _t, v, st in EV.judge(arms, one_char=set())}
    assert failed["P-12"][0] == "failed" and "B-only ['I00', 'I01']" in failed["P-12"][1]
    held = {pid: (st, v) for pid, _t, v, st in EV.judge(arms, one_char={"I00", "I01"})}
    assert held["P-12"][0] == "held" and "left out: ['I00', 'I01']" in held["P-12"][1]


def test_one_character_golds_come_from_the_bank_with_the_scorers_normalisation(tmp_path):
    bank = tmp_path / "b.tsv"
    bank.write_text("#id\tkind\tcorpus\tsubject\tquestion\tgold\tevidence\taudit\n"
                    "Q1\tintra2\tfulllead\tS\tq\tY17|Y18\tS#1\tvalid\n"
                    "Q2\tintra2\tfulllead\tS\tq\t5\tS#1\tvalid\n"
                    "Q3\tintra2\tfulllead\tS\tq\t五|五十\tS#1\tvalid\n"
                    "Q4\tintra2\tother\tS\tq\t7\tS#1\tvalid\n"
                    "U1\tunans\tfulllead\tS\tq\t\tS#1\tvalid\n", encoding="utf-8")
    assert EV.one_char_qids(str(bank)) == {"Q2", "Q3"}                                                              # '五' normalises to the digit '5'; Q4 is another corpus


def test_the_result_files_are_keyed_by_the_run_settings_and_the_config_is_in_every_record(toy_files, tmp_path):
    out = tmp_path / "k"
    cfg, corpus, rep = run_toy(toy_files, "A", out, steps=(1,), questions="I-1")
    (r,) = records_of(out)
    conf = r["config"]
    assert conf == {"grammar": "on", "effort": "fast", "site": "on", "level": LEVEL, "code_sha256": "c" * 64} and r["code_sha256"] == conf["code_sha256"]
    key = EV.config_key(conf)
    assert os.path.basename(mfile(out, "A")) == "meter_A.%s.jsonl" % key and EV.parse_stem("meter_A.%s.jsonl" % key) == ("A", key)
    assert EV.parse_stem("meter_C_B.%s.jsonl" % key) == ("C_B", key) and EV.parse_stem("meter_C.%s.arr.jsonl" % key) is None and EV.parse_stem("meter_C_t10check.json") is None
    # the key does not move with the code sha (else a changed file could never be refused) but does with every other setting
    assert EV.config_key(dict(conf, code_sha256="d" * 64)) == key
    assert all(EV.config_key(dict(conf, **{k: v})) != key for k, v in (("grammar", "off"), ("effort", "standard"), ("site", "off"), ("level", "mid")))
    # another setting writes another file in the same directory, and neither is read as the other
    run_toy(toy_files, "A", out, steps=(1,), questions="I-1", site=False)
    assert len([f for f in os.listdir(out) if EV.parse_stem(f)]) == 2


def test_a_resume_with_another_config_or_other_code_is_refused(toy_files, tmp_path):
    out = tmp_path / "rc"
    run_toy(toy_files, "A", out, steps=(1,), questions="I-1")
    path = mfile(out, "A")
    before = open(path, "rb").read()
    with pytest.raises(EV.ConfigMismatch, match="code_sha256"):                                                    # same settings, other code: same file name, refused
        run_toy(toy_files, "A", out, steps=(1, 2), questions="I-1", code_sha="d" * 64)
    assert open(path, "rb").read() == before                                                                        # nothing was appended
    EV.check_resume(path, json.loads(open(path, encoding="utf-8").readline())["record"]["config"])                  # the same config passes
    # records that carry no config (an old file) or a hand-edited one are refused too
    lines = open(path, encoding="utf-8").read().splitlines()
    o = json.loads(lines[0])
    del o["record"]["config"]
    open(path, "w", encoding="utf-8").write(json.dumps(o) + "\n")
    with pytest.raises(EV.ConfigMismatch, match="absent"):
        run_toy(toy_files, "A", out, steps=(1,), questions="I-1")
    # the CLI turns it into a message and exit status 3, not a traceback and not a silent mix
    argv = [PY, os.path.join(G4, "meter.py"), "--arm", "A", "--stack", toy_files["stack"], "--data", toy_files["data"], "--bank", toy_files["bank"], "--level", LEVEL,
            "--steps", "1", "--questions", "I-1", "--workers", "1", "--out", str(tmp_path / "rc2")]
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED="0")
    assert subprocess.run(argv, capture_output=True, text=True, env=env).returncode == 0
    cut = mfile(tmp_path / "rc2", "A")
    o = json.loads(open(cut, encoding="utf-8").readline())
    o["record"]["config"]["code_sha256"] = "0" * 64
    open(cut, "w", encoding="utf-8").write(json.dumps(o) + "\n")
    res = subprocess.run(argv, capture_output=True, text=True, env=env)
    assert res.returncode == 3 and "resume refused" in res.stderr and "Traceback" not in res.stderr


def test_the_meta_records_the_code_sha_per_module_and_the_combined_one(toy_files, tmp_path):
    cfg, corpus, rep = run_toy(toy_files, "A", tmp_path / "meta2", steps=(1,), questions="I-1")
    cfg["code_modules"] = M.code_shas()
    cfg["code_sha"] = M.sha(M.cj(cfg["code_modules"]).encode("utf-8"))
    M.write_meta(cfg, ["--arm", "A"], rep, [1], corpus.questions[:1])
    r = json.load(open(mfile(tmp_path / "meta2", "A", "meta.json"), encoding="utf-8"))["runs"][0]
    assert r["code_modules"] == M.code_shas() and {"ask", "stack", "meter", "events", "scorer", "cycle"} <= set(r["code_modules"])
    assert r["code_sha256"] == M.sha(M.cj(r["code_modules"]).encode("utf-8")) and r["config"]["code_sha256"] == r["code_sha256"]
    assert r["arrival_oracle"] is None or isinstance(r["arrival_oracle"], dict)


def test_the_dictionary_block_is_present_as_none_not_merely_absent(monkeypatch):
    for m in ("fugashi", "unidic_lite"):
        monkeypatch.delitem(sys.modules, m, raising=False)
    assert M.dictionary_blocked() is False                                                                         # never imported is NOT blocked
    monkeypatch.setitem(sys.modules, "fugashi", None)
    assert M.dictionary_blocked() is False                                                                         # one of the two
    monkeypatch.setitem(sys.modules, "unidic_lite", None)
    assert M.dictionary_blocked() is True
    monkeypatch.setitem(sys.modules, "unidic_lite", object())                                                       # imported for real
    assert M.dictionary_blocked() is False


def test_no_absolute_path_of_one_machine_is_in_the_code():
    for f in ("meter.py", "events.py"):
        text = open(os.path.join(G4, f), encoding="utf-8").read()
        assert "/Users/" not in text.replace("/Users/.../", ""), f
    assert EV.VERA_IMPL == os.path.normpath(os.path.join(ROOT, "..", "..")) or os.environ.get("VERA_IMPL_DIR")
    assert M.rel(os.path.join(EV.VERA_IMPL, "cache", "g4_stack_A")) == os.path.join("cache", "g4_stack_A") and M.rel("/elsewhere/x") == "/elsewhere/x" and M.rel(None) is None
    assert M.CACHE_A == os.path.join(EV.VERA_IMPL, "cache", "g4_stack_A") and EV.DEFAULT_STACK == M.CACHE_A and M.T10_FAST.startswith(os.path.join(EV.VERA_IMPL, "wt", "line3"))


def test_a_char_only_arm_without_the_arrival_oracle_has_an_unknown_3tier_flag_not_the_arms_flag(toy_files, tmp_path):
    """D8 on the meter: B with no arrival oracle -> unarrived_3tier None on every intra2 record; with it -> a bool.  A reads three tiers, so its two flags are one."""
    run_toy(toy_files, "B", tmp_path / "b0", steps=(1, 4))                                                           # toy_cfg has arrival None
    recs = records_of(tmp_path / "b0", "B")
    intra = [r for r in recs if r["kind"] == "intra2"]
    assert intra and all(r["unarrived_3tier"] is None and isinstance(r["unarrived"], bool) for r in intra)
    assert all(r["unarrived_3tier"] is None and r["unarrived"] is None for r in recs if r["kind"] == "unans")
    arr = EV.stack_arr(toy_files["stack"], "on", LEVEL)
    md = EV.render_md("B", recs, arr)
    assert "WARNING" in md and "arrival oracle" in md
    run_toy(toy_files, "B", tmp_path / "b1", steps=(1, 4), arrival=M.Arrival.from_stack(toy_files["stack"], "on", LEVEL, "forward"))
    assert all(isinstance(r["unarrived_3tier"], bool) for r in records_of(tmp_path / "b1", "B") if r["kind"] == "intra2")
    run_toy(toy_files, "A", tmp_path / "a0", steps=(1, 4))
    assert all(r["unarrived_3tier"] == r["unarrived"] for r in records_of(tmp_path / "a0", "A"))


def test_a_cut_arrangement_table_is_survived_by_the_writer_and_the_reader(toy_files, oneshot, tmp_path):
    """D11: write_arr_table starts its append on a line of its own; sha_arr skips a line that does not parse."""
    cfg, corpus, rep = run_toy(toy_files, "C", tmp_path / "ca", src=oneshot, steps=(1, 2, 3), questions="I-1")
    path = mfile(tmp_path / "ca", "C", "arr.jsonl")
    raw = open(path, "rb").read()
    open(path, "wb").write(raw[:-15])                                                                               # a kill in the middle of the last line: no newline
    assert not open(path, "rb").read().endswith(b"\n")
    arr = EV.sha_arr(path)                                                                                          # the reader does not crash on the cut line
    assert arr.ids and len(arr.ids) < sum(len(json.loads(l)["arr"]) for l in raw.decode("utf-8").splitlines())
    g = M.open_step(dict(cfg, site=False), corpus, 3)
    M.write_arr_table(cfg, g)                                                                                       # the cut (step, tier) is written again, on its own line
    lines = open(path, encoding="utf-8").read().splitlines()
    parsed = []
    for l in lines:
        try:
            parsed.append(json.loads(l))
        except ValueError:
            pass
    assert len(lines) == len(parsed) + 1                                                                            # exactly the cut line does not parse
    assert sorted((o["step"], o["tier"]) for o in parsed) == sorted((k, t) for k in (1, 2, 3) for t in ALL)
    assert len(EV.sha_arr(path).ids) == sum(len(o["arr"]) for o in parsed)


def _fake_t10(toy_files, oneshot, tmp_path, mutate=None, errors=False):
    """A T10-format flat/fast file made from the toy arm C at the last step (what t10_check re-asks and compares)."""
    cfg = toy_cfg(toy_files, "C", tmp_path / "t10out", src=oneshot)
    cfg["spec"] = dict(cfg["spec"], grammar="off")
    corpus = toy_corpus(toy_files)
    g = M.open_step(dict(cfg, site=False), corpus, 4)
    rows = []
    for q in corpus.questions:
        c = A.ask(g.ix, q["question"], view="all", effort="fast")
        l0 = {o.tier: {"entries": [{"words": list(e.words), "centres": list(e.centres), "count": e.count, "stability": A._fs(e.stability)} for e in o.entries],
                       "verdict": o.verdict, "read": dict(o.read_counts), "ms": 1} for o in c.outcomes}
        rows.append({"id": q["qid"], "verdict0": c.verdict, "layer0": l0})
    if mutate:
        mutate(rows)
    if errors:
        rows.append({"id": "ZZZ", "error": "boom"})
    path = tmp_path / "t10.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return cfg, corpus, str(path)


def test_t10_check_compares_verdicts_tier_verdicts_entries_and_read_counts(toy_files, oneshot, tmp_path):
    cfg, corpus, path = _fake_t10(toy_files, oneshot, tmp_path)
    res = M.t10_check(cfg, corpus, path, n=5)
    assert res["all_equal"] is True and res["n"] == 5 and res["arm"] == "C" and res["config"]["grammar"] == "off" and res["source"].endswith("t10.jsonl")
    assert all(r["verdict_equal"] and r["tier_verdicts_equal"] and r["entries_equal"] and r["read_counts_equal"] for r in res["results"])

    def tier_verdict(rows):
        rows[0]["layer0"]["WORD"]["verdict"] = "UNKNOWN_NO_PATH_X"
    cfg, corpus, path = _fake_t10(toy_files, oneshot, tmp_path, mutate=tier_verdict)
    res = M.t10_check(cfg, corpus, path, n=5)
    bad = [r for r in res["results"] if not r["tier_verdicts_equal"]]
    assert res["all_equal"] is False and len(bad) == 1 and all(r["entries_equal"] and r["read_counts_equal"] and r["verdict_equal"] for r in bad)

    def read_counts(rows):
        rows[1]["layer0"]["CHAR"]["read"]["crosses_read"] += 1
    cfg, corpus, path = _fake_t10(toy_files, oneshot, tmp_path, mutate=read_counts)
    res = M.t10_check(cfg, corpus, path, n=5)
    bad = [r for r in res["results"] if not r["read_counts_equal"]]
    assert res["all_equal"] is False and len(bad) == 1 and all(r["entries_equal"] and r["tier_verdicts_equal"] for r in bad)


def test_t10_check_raises_on_an_error_record_instead_of_leaving_it_out(toy_files, oneshot, tmp_path):
    cfg, corpus, path = _fake_t10(toy_files, oneshot, tmp_path, errors=True)
    with pytest.raises(ValueError, match="error records"):
        M.t10_check(cfg, corpus, path, n=5)


def test_a_results_directory_with_two_configs_of_one_arm_is_ambiguous(toy_files, tmp_path):
    out = tmp_path / "amb"
    run_toy(toy_files, "A", out, steps=(1,), questions="I-1")
    run_toy(toy_files, "A", out, steps=(1,), questions="I-1", site=False)
    with pytest.raises(ValueError, match="several configs"):
        EV._discover(str(out))
    keys = sorted(EV.parse_stem(f)[1] for f in os.listdir(out) if EV.parse_stem(f))
    assert EV._discover(str(out), keys[0])["A"][0] == keys[0]
