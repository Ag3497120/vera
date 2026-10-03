"""W2-c2 (round 3): the trap rules of conduct_ask that were kept hand a question up only on POSITIVE evidence.

Round 3 (auditor's ruling of 2026-10-03 14:05): the inversion to "positive evidence" stays for two traps only, WIDER
(TERM_IN_WIDER_PHRASE) and BUILTIN (BUILTIN_PROTECTED).  NEGATED_QUESTION, INVERTED_QUESTION and NO_ALLOWLIST are put back to the
code of the base ``5cae978``; this file fixes that by comparing them with the RECORDED output of the base code
(artifacts/w2-c2/r3/sentences_base.jsonl, artifacts/w2-c2/base/results.jsonl), never by a weaker "may hand up or may route".

The data is tests/conduct_ask/w2c2/ (frozen before the rules were changed: artifacts/w2-c2/freeze.txt; the round-2 supplement
supp/: freeze_supp.txt; the round-3 sentences r3_sentences.jsonl and r3_scripts/: artifacts/w2-c2/r3/freeze_r3.txt).  Every trap has
three groups of sentences:
  raise     there is positive evidence: handed up, and (with the made-up record mapping) not even asked about
  route     the base code handed it up by form only: for the two kept traps it must now reach the record mapping
  transfer  right to hand up but no positive evidence: it must not be answered by the rules (the danger moves to the mapping)
No real provider is ever started (the mapping is made up: an empty script that never answers, or a scripted one).

C2 is read as D12 of docs/CONDUCT_ASK.md section 10 (judged here from the answers, not read from a report): C2-K for the kept traps
(raise: all; route: reaches the mapping, or is stopped by a REVERTED trap -- recorded), C2-R for the reverted traps (every row, both
modes, equal to the base code's).  ``tests/conduct_ask/w2c2/run_w2c2.py c2r3`` makes the same judgement as a tool."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "conduct_ask"))
import map_helpers as M  # noqa: E402
from verantyx import conduct_ask as ca  # noqa: E402
from verantyx.project_frame import load_conduct_frame  # noqa: E402

DATA = ROOT / "tests" / "conduct_ask" / "w2c2"
FRAMES = DATA / "frames"
MAP_EMPTY = str(DATA / "map_fake_empty.json")
TRAPS = ("WIDER", "NEGATED", "INVERTED", "BUILTIN", "NO_ALLOWLIST")
RULE = {"WIDER": ("FRAME_SILENT", "TERM_IN_WIDER_PHRASE"), "NEGATED": ("QUESTION_UNREADABLE", "NEGATED_QUESTION"),
        "INVERTED": ("QUESTION_UNREADABLE", "INVERTED_QUESTION"), "BUILTIN": ("HUMAN_APPROVAL_REQUIRED", "BUILTIN_PROTECTED"),
        "NO_ALLOWLIST": ("FRAME_SILENT", "NO_ALLOWLIST")}
TRAP_DETAILS = {d for _, d in RULE.values()}
ITEMS = [json.loads(ln) for ln in (DATA / "items.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]


@pytest.fixture(autouse=True)
def no_process(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("a real provider process must never be started")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)


def frame_path(frame_id: str) -> str:
    return str(FRAMES / f"{frame_id}.md")


def run(item: dict, mode: str) -> dict:
    kw = {"vocab_llm": "fake", "map_fake": MAP_EMPTY} if mode == "fakemap" else {}
    return ca.answer_question(frame_path(item["frame_id"]), item["question"], item["options"], **kw)


@pytest.fixture(scope="module")
def results() -> dict:
    return {it["id"]: {"off": run(it, "off"), "fakemap": run(it, "fakemap")} for it in ITEMS}


def truth_matches(res: dict, item: dict) -> bool:
    t = item["truth"]
    if res["decision"] != "answer" or t["decision"] != "answer":
        return False
    if t["answer_option_index"] is not None:
        return res["answer_option_index"] == t["answer_option_index"]
    return str(res["answer"]).strip() == str(t["answer"]).strip()


def not_asked(res: dict) -> bool:
    return str((res.get("mapping") or {}).get("outcome") or "").startswith("NOT_ASKED")


def by(trap: str, group: str) -> list[dict]:
    return [i for i in ITEMS if i["trap"] == trap and i["group"] == group]


# ---------------------------------------------------------------------------------------------
# the shape of the data
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("trap", TRAPS)
def test_each_trap_has_the_three_groups_in_both_languages(trap):
    need = {"raise": 10, "route": 10, "transfer": 3}
    for group, n in need.items():
        items = by(trap, group)
        assert len(items) >= n, (trap, group, len(items))
        for lang in ("ja", "en"):
            assert sum(1 for i in items if i["lang"] == lang) >= 3, (trap, group, lang)


def test_ids_are_unique_and_follow_the_pattern():
    ids = [i["id"] for i in ITEMS]
    assert len(ids) == len(set(ids))
    for i in ITEMS:
        assert i["id"].startswith(f"w2c2-{i['trap'].lower()}-{i['group']}-"), i["id"]
        assert i["id"].rsplit("-", 1)[1].isdigit()
        assert (FRAMES / f"{i['frame_id']}.md").exists()


def test_every_item_has_the_common_fields_and_a_well_formed_truth():
    for i in ITEMS:
        assert i["trap"] in TRAPS and i["group"] in ("raise", "route", "transfer") and i["lang"] in ("ja", "en")
        assert isinstance(i["question"], str) and i["question"].strip()
        assert i["options"] is None or (isinstance(i["options"], list) and len(i["options"]) >= 2)
        t = i["truth"]
        assert t["decision"] in ("answer", "escalate") and isinstance(t["records"], list)
        if t["decision"] == "answer":
            if i["options"] is not None:
                assert 0 <= t["answer_option_index"] < len(i["options"]) and t["answer"] == i["options"][t["answer_option_index"]]
            else:
                assert t["answer_option_index"] is None and isinstance(t["answer"], str) and t["answer"]
        else:
            assert t["answer"] is None and t["answer_option_index"] is None
        if i["group"] == "raise":
            assert (i["expect_rule"]["reason"], i["expect_rule"]["detail"]) == RULE[i["trap"]] and i["evidence"]
            assert t["decision"] == "escalate"
        elif i["group"] == "route":
            assert i["misfire"]
        else:
            assert i["danger"] and t["decision"] == "escalate"


@pytest.mark.parametrize("trap", TRAPS)
def test_at_least_eight_in_ten_route_sentences_have_an_answer_in_the_frame(trap):
    items = by(trap, "route")
    assert 10 * sum(1 for i in items if i["truth"]["decision"] == "answer") >= 8 * len(items)


def test_the_data_is_the_frozen_data():
    """artifacts/w2-c2/freeze.txt holds the hashes taken before any rule was changed (the data is not tuned afterwards)."""
    frozen = {}
    for ln in (ROOT / "artifacts" / "w2-c2" / "freeze.txt").read_text(encoding="utf-8").splitlines():
        parts = ln.split()
        if len(parts) == 2 and len(parts[0]) == 64:
            frozen[parts[1]] = parts[0]
    for rel in ["tests/conduct_ask/w2c2/items.jsonl"] + sorted(f"tests/conduct_ask/w2c2/frames/{p.name}" for p in FRAMES.glob("*.md")):
        assert frozen.get(rel) == hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), rel


# ---------------------------------------------------------------------------------------------
# C2: judged here from the answers themselves (not read from the report of the measuring tool)
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("item", [i for i in ITEMS if i["group"] == "raise"], ids=lambda i: i["id"])
def test_c2_raise_is_handed_up_in_the_type_and_the_mapping_is_not_asked(item, results):
    want = (item["expect_rule"]["reason"], item["expect_rule"]["detail"])
    for mode in ("off", "fakemap"):
        res = results[item["id"]][mode]
        assert res["decision"] == "escalate" and (res["escalate_reason"], res["escalate_detail"]) == want, (mode, res["escalate_reason"], res["escalate_detail"])
    assert not_asked(results[item["id"]]["fakemap"])


# RECORDED: the route sentences of the two KEPT traps (WIDER, BUILTIN) that do not reach the record mapping with the made-up mapping
# because a REVERTED trap (put back to the base code in round 3) hands them up.  Not a failure of the kept traps: D12 / ROUTE_STOPPED_BY_REVERTED_TRAP.
# w2c2-builtin-route-11 asks about "e.g." in a sentence of a frame without a write allowlist; the base's wide path test (NO_ALLOWLIST) hands it up.
KEPT = ("WIDER", "BUILTIN")
REVERTED = ("NEGATED", "INVERTED", "NO_ALLOWLIST")
REVERTED_DETAILS = {RULE[t][1] for t in REVERTED}
KEPT_DETAILS = {RULE[t][1] for t in KEPT}
ROUTE_STOPPED_BY_REVERTED_TRAP = {"w2c2-builtin-route-11"}
# B2 (auditor's ruling): the nine route sentences of the ORIGINAL data that a later W2-c rule hands up are a mistake of the data design;
# they are not judged as route (all of them belong to a reverted trap, whose rows are compared with the base code's instead)
B2_ITEMS = {"w2c2-negated-route-06", "w2c2-no_allowlist-route-01", "w2c2-no_allowlist-route-02", "w2c2-no_allowlist-route-03",
            "w2c2-no_allowlist-route-04", "w2c2-no_allowlist-route-05", "w2c2-no_allowlist-route-06", "w2c2-no_allowlist-route-07",
            "w2c2-no_allowlist-route-10"}
SIX = ("decision", "answer", "answer_option_index", "escalate_reason", "escalate_detail")


def six(res: dict) -> tuple:
    return tuple(res.get(k) for k in SIX) + ((res.get("mapping") or {}).get("outcome"),)


@pytest.fixture(scope="module")
def base_rows() -> dict:
    """The recorded results of the base code (5cae978) over all the data: (set, id, mode) -> six fields."""
    out = {}
    for ln in (ROOT / "artifacts" / "w2-c2" / "base" / "results.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(ln)
        out[(r["set"], r["id"], r["mode"])] = tuple(r.get(k) for k in SIX) + (r.get("mapping_outcome"),)
    return out


def test_b2_items_are_all_route_sentences_of_a_reverted_trap():
    by_id = {i["id"]: i for i in ITEMS}
    assert len(B2_ITEMS) == 9
    for iid in B2_ITEMS:
        assert by_id[iid]["group"] == "route" and by_id[iid]["trap"] in REVERTED, iid


@pytest.mark.parametrize("item", [i for i in ITEMS if i["id"] in B2_ITEMS], ids=lambda i: i["id"])
def test_a_b2_item_is_never_answered_wrongly_either(item, results):
    """(Was ``test_a_recorded_c2_failure_is_never_answered_wrongly_either``.)  The nine sentences that are not judged as route are still
    never answered wrongly, off or with the made-up mapping."""
    for mode in ("off", "fakemap"):
        res = results[item["id"]][mode]
        assert not (res["decision"] == "answer" and not truth_matches(res, item)), (mode, res["answer"])


@pytest.mark.parametrize("item", [i for i in ITEMS if i["trap"] in KEPT and i["group"] == "raise"], ids=lambda i: i["id"])
def test_c2k_raise_of_a_kept_trap_is_handed_up_in_the_type_and_the_mapping_is_not_asked(item, results):
    want = (item["expect_rule"]["reason"], item["expect_rule"]["detail"])
    for mode in ("off", "fakemap"):
        res = results[item["id"]][mode]
        assert res["decision"] == "escalate" and (res["escalate_reason"], res["escalate_detail"]) == want, (mode, res["escalate_reason"], res["escalate_detail"])
    assert not_asked(results[item["id"]]["fakemap"])
    assert results[item["id"]]["fakemap"]["mapping"]["rule"]["detail"] == want[1]


@pytest.mark.parametrize("item", [i for i in ITEMS if i["trap"] in KEPT and i["group"] == "route"], ids=lambda i: i["id"])
def test_c2k_route_of_a_kept_trap_reaches_the_mapping_or_is_stopped_by_a_reverted_trap(item, results):
    for mode in ("off", "fakemap"):
        res = results[item["id"]][mode]
        assert not (res["decision"] == "answer" and not truth_matches(res, item)), (mode, res["answer"])     # no wrong / other answer
    fm = results[item["id"]]["fakemap"]
    if not not_asked(fm):
        return
    assert item["id"] in ROUTE_STOPPED_BY_REVERTED_TRAP, (item["id"], fm["escalate_reason"], fm["escalate_detail"])
    assert fm["mapping"]["rule"]["detail"] in REVERTED_DETAILS, fm["mapping"]["rule"]


def test_route_stopped_by_reverted_trap_is_exactly_the_recorded_set(results):
    """Neither stale nor hiding a new failure: the live set of kept-trap route sentences whose made-up-mapping run is NOT_ASKED."""
    live = {i["id"] for i in ITEMS if i["trap"] in KEPT and i["group"] == "route" and not_asked(results[i["id"]]["fakemap"])}
    assert live == ROUTE_STOPPED_BY_REVERTED_TRAP, sorted(live ^ ROUTE_STOPPED_BY_REVERTED_TRAP)
    for iid in live:
        assert results[iid]["fakemap"]["mapping"]["rule"]["detail"] == "NO_ALLOWLIST"      # the base's wide path test, which is back


@pytest.mark.parametrize("item", [i for i in ITEMS if i["trap"] in REVERTED], ids=lambda i: i["id"])
def test_c2r_a_reverted_trap_gives_the_base_answer_in_both_modes(item, results, base_rows):
    """C2-R: every row (raise, route, transfer) of a reverted trap equals the recorded base output in the six fields, off and fakemap."""
    for mode in ("off", "fakemap"):
        assert six(results[item["id"]][mode]) == base_rows[("w2c2", item["id"], mode)], (mode, item["group"])


@pytest.mark.parametrize("item", [i for i in ITEMS if i["group"] == "transfer"], ids=lambda i: i["id"])
def test_c2_transfer_is_never_answered_by_the_rules(item, results):
    for mode in ("off", "fakemap"):
        assert results[item["id"]][mode]["decision"] == "escalate"


def test_c2_transfer_routing_count_is_the_measured_one(results):
    """The count that is reported next to (not inside) the pass/fail of C2: the transfer sentences that reach the mapping."""
    routed = {i["id"] for i in ITEMS if i["group"] == "transfer" and not not_asked(results[i["id"]]["fakemap"])}
    not_routed = {i["id"] for i in ITEMS if i["group"] == "transfer"} - routed
    assert len(routed) == 9 and len([i for i in ITEMS if i["group"] == "transfer"]) == 30
    # WIDER: 01-03 are not routed (reading the term narrowly hands up a type that the mapping may not retry: D10); 04-06 are.
    # BUILTIN: all six are routed (the danger moves to the mapping: docs 11).  NEGATED / INVERTED / NO_ALLOWLIST: none (the base code).
    assert not_routed == ({f"w2c2-wider-transfer-0{k}" for k in (1, 2, 3)} | {i["id"] for i in ITEMS if i["group"] == "transfer"
                                                                              and i["trap"] in REVERTED})
    assert {i for i in routed if "-wider-" in i} == {f"w2c2-wider-transfer-0{k}" for k in (4, 5, 6)}
    assert {i for i in routed if "-builtin-" in i} == {f"w2c2-builtin-transfer-0{k}" for k in range(1, 7)}


def test_the_two_kept_traps_hand_up_every_raise_sentence_and_no_route_sentence_in_the_rule_layer(results):
    for i in ITEMS:
        fm = results[i["id"]]["fakemap"]
        det = (fm["mapping"]["rule"] or {}).get("detail")
        fired = not_asked(fm) and det in KEPT_DETAILS
        if i["group"] == "raise" and i["trap"] in KEPT:
            assert fired, i["id"]
        elif i["group"] == "route":
            assert not fired, i["id"]


# ---------------------------------------------------------------------------------------------
# the frozen W2-c / W2-g data: the safety lines S1-S3 (against the answers of the base code, artifacts/w2-c2/base)
# ---------------------------------------------------------------------------------------------

FROZEN_SETS = ("fixtures", "w2g", "w2g2", "w2g3")


def frozen_items():
    for s in FROZEN_SETS:
        d = ROOT / "tests" / "conduct_ask" / s
        for ln in (d / "items.jsonl").read_text(encoding="utf-8").splitlines():
            if ln.strip():
                r = json.loads(ln)
                yield s, r, str(d / "frames" / (r["frame_id"] + ".md"))


@pytest.fixture(scope="module")
def frozen_now() -> dict:
    out = {}
    for s, r, fp in frozen_items():
        out[(s, r["id"])] = ca.answer_question(fp, r["question"], r.get("options"))
    return out


@pytest.fixture(scope="module")
def frozen_base() -> dict:
    out = {}
    for ln in (ROOT / "artifacts" / "w2-c2" / "base" / "results.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(ln)
        if r["mode"] == "off" and r["set"] in FROZEN_SETS:
            out[(r["set"], r["id"])] = r
    return out


def test_s1_s2_s3_no_new_answer_for_an_expected_escalation_and_no_wrong_answer_for_an_expected_answer(frozen_now, frozen_base):
    checked = 0
    for s, r, _ in frozen_items():
        now, base, exp = frozen_now[(s, r["id"])], frozen_base[(s, r["id"])], r["expect"]
        checked += 1
        if exp["decision"] == "escalate":
            assert not (now["decision"] == "answer" and base["decision"] != "answer"), r["id"]      # S1 (and S3 for off)
        elif now["decision"] == "answer":
            if exp.get("answer_option_index") is not None:
                assert now["answer_option_index"] == exp["answer_option_index"], r["id"]            # S2
            else:
                assert now["answer"] == exp.get("answer"), r["id"]
    assert checked == 349


# ---------------------------------------------------------------------------------------------
# the evidence functions, one by one
# ---------------------------------------------------------------------------------------------

def mentions_of(frame_id: str, question: str):
    view = ca.build_view(load_conduct_frame(frame_path(frame_id)))
    index = ca.TermIndex(view)
    ms, _ = ca.find_mentions(ca.nz(question), index)
    return ms


@pytest.mark.parametrize("frame_id,question,evidence", [
    ("z01_seedswap", "登録フォームのコピーは、今回の範囲に入りますか？", "E0:のコピー"),
    ("z02_photos", "撮影日の一覧の写しを、家族に渡す前に確かめる必要がありますか？", "E0:の写し"),
    ("z03_festival", "売り上げの記録欄の派生版は、今回の範囲に含めますか？", "E0:の派生"),
    ("z01_seedswap", "登録フォームの入力例は、今回の範囲に入りますか？", "OTHER_RECORD:C3"),
    ("z04_kiln", "Is the firing report archive in scope?", "OTHER_RECORD:C2"),
    ("z04_kiln", "Is the temperature reader log in scope?", "OTHER_RECORD:I2"),
    ("z04_kiln", "Must the reading format version be settled before the batch label printer is written?", "OTHER_RECORD:phase_order:P1->P3"),
])
def test_wider_phrase_with_evidence(frame_id, question, evidence):
    wide = [m for m in mentions_of(frame_id, question) if m.wider]
    assert wide and any(m.wider_evidence == evidence or (m.wider_evidence or "").startswith(evidence) for m in wide), [m.wider_evidence for m in wide]


@pytest.mark.parametrize("frame_id,question", [
    ("z01_seedswap", "登録フォームづくりに入るのは、品目の登録項目が決まったあとですか？"),
    ("z01_seedswap", "いまの登録フォームは、品目の登録項目が決まってから作りますか？"),
    ("z02_photos", "アルバムの形式の選択は、冊子と画面のどちらにしますか？"),
    ("z04_kiln", "Must the reading format be defined before the temperature reader work starts?"),
    ("z04_kiln", "Does the current temperature reader have to wait for the reading format?"),
    ("z05_tideclock", "Is the moon phase icon design in scope?"),
    ("z04_kiln", "Which backup label size should we use?"),
])
def test_wider_phrase_without_evidence_is_marked_wider_but_has_no_evidence(frame_id, question):
    wide = [m for m in mentions_of(frame_id, question) if m.wider]
    assert wide and all(m.wider_evidence is None for m in wide)


def test_a_wider_phrase_with_evidence_is_handed_up_as_frame_silent_and_says_what_was_not_checked():
    res = ca.answer_question(frame_path("z01_seedswap"), "登録フォームのコピーは、今回の範囲に入りますか？", ["はい", "いいえ"])
    assert (res["escalate_reason"], res["escalate_detail"]) == ("FRAME_SILENT", "TERM_IN_WIDER_PHRASE")
    assert res["trace"]["resolver_outcomes"]["wider_phrase"] == "ESCALATE:EVIDENCE:E0:のコピー"
    assert res["trace"]["resolver_outcomes"]["wider_phrase_head_type"] == "NOT_CHECKED:NO_PLACEMENT"


def ctx_of(frame_id: str, question: str, options=None) -> "ca.Ctx":
    view = ca.build_view(load_conduct_frame(frame_path(frame_id)))
    index = ca.TermIndex(view)
    q = ca.nz(question)
    ms, dropped = ca.find_mentions(q, index)
    opts = ca.read_options(list(options) if options is not None else None, view, index)
    return ca.Ctx(view, index, ca.Graph(view), question, q, opts, options is not None, ms, dropped, ca._sentences(q),
                  "ja" if ca.has_cjk(q) else "en", q_case=ca.nz(question, fold=False))


R3 = DATA / "r3_sentences.jsonl"
R3_SENTENCES = [json.loads(ln) for ln in R3.read_text(encoding="utf-8").splitlines() if ln.strip()]
R3_RECORDED = {}
for _ln in (ROOT / "artifacts" / "w2-c2" / "r3" / "sentences_base.jsonl").read_text(encoding="utf-8").splitlines():
    _r = json.loads(_ln)
    R3_RECORDED[(_r["id"], _r["mode"])] = _r
FIELDS7 = ("decision", "answer", "answer_option_index", "escalate_reason", "escalate_detail", "mapping_outcome", "mapping_exit_check")


def run_sentence(row: dict, mode: str) -> dict:
    """The same call as ``run_w2c2.py sentences``: off / an empty made-up mapping / a scripted made-up mapping (fixed order)."""
    fp = frame_path(row["frame_id"])
    if mode == "off":
        kw: dict = {}
    elif mode == "fakemap_empty":
        kw = {"vocab_llm": "fake", "map_fake": MAP_EMPTY}
    else:
        script = json.loads((DATA / "r3_scripts" / f"{row['script']}.json").read_text(encoding="utf-8"))
        kw = {"vocab_llm": "fake", "mapper": M.mapper_for(fp, row["options"], script)}
    res = ca.answer_question(fp, row["question"], row["options"], **kw)
    m = res.get("mapping") or {}
    return {"decision": res["decision"], "answer": res["answer"], "answer_option_index": res["answer_option_index"],
            "escalate_reason": res["escalate_reason"], "escalate_detail": res["escalate_detail"], "mapping_outcome": m.get("outcome"),
            "mapping_exit_check": m.get("exit_check")}


def modes_of(row: dict) -> tuple:
    return ("off", "fakemap_empty") + (("fakemap_script",) if row.get("script") else ())


def sentences_from(*origins: str) -> list:
    return [r for r in R3_SENTENCES if r["origin"] in origins]


FORM_TRAP_ORIGINS = ("test_form_trap_with_positive_evidence", "test_form_trap_without_positive_evidence_is_none")
WRITE_TARGET_ORIGIN = "test_a_path_is_a_write_target_only_right_after_or_before_a_write_verb"
GATE_PASS_ORIGIN = "test_the_gate_lets_a_mapped_answer_through_when_there_is_no_positive_evidence"
GATE_UP_ORIGIN = "test_the_gate_hands_up_a_mapped_answer_to_a_question_with_positive_evidence"


def test_the_r3_sentences_are_the_frozen_data():
    """artifacts/w2-c2/r3/freeze_r3.txt: the sentences, the script and the base code's recorded output (taken before this round's code)."""
    frozen = {}
    for ln in (ROOT / "artifacts" / "w2-c2" / "r3" / "freeze_r3.txt").read_text(encoding="utf-8").splitlines():
        parts = ln.split()
        if len(parts) == 2 and len(parts[0]) == 64:
            frozen[parts[1]] = parts[0]
    rels = ["tests/conduct_ask/w2c2/r3_sentences.jsonl", "artifacts/w2-c2/r3/sentences_base.jsonl"]
    rels += sorted(f"tests/conduct_ask/w2c2/r3_scripts/{p.name}" for p in (DATA / "r3_scripts").glob("*.json"))
    assert len(rels) == 3
    for rel in rels:
        assert frozen.get(rel) == hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), rel


def test_the_r3_sentences_are_the_ones_of_the_round_1_2_tables_and_every_one_has_a_recorded_base_output():
    """Mechanically moved (artifacts/w2-c2/r3/build_r3_sentences.py): the counts of the old parametrize tables."""
    counts = {}
    for r in R3_SENTENCES:
        counts[r["origin"]] = counts.get(r["origin"], 0) + 1
        for mode in modes_of(r):
            assert (r["id"], mode) in R3_RECORDED, (r["id"], mode)
    assert counts == {FORM_TRAP_ORIGINS[0]: 27, FORM_TRAP_ORIGINS[1]: 21, WRITE_TARGET_ORIGIN: 23, GATE_UP_ORIGIN: 4, GATE_PASS_ORIGIN: 3}
    assert len({r["id"] for r in R3_SENTENCES}) == len(R3_SENTENCES) == 78
    assert sum(len(modes_of(r)) for r in R3_SENTENCES) == len(R3_RECORDED) == 163


def assert_recorded(row: dict) -> None:
    for mode in modes_of(row):
        now, rec = run_sentence(row, mode), R3_RECORDED[(row["id"], mode)]
        assert tuple(now[k] for k in FIELDS7) == tuple(rec[k] for k in FIELDS7), (mode, now, rec)


@pytest.mark.parametrize("row", sentences_from(*FORM_TRAP_ORIGINS), ids=lambda r: r["id"])
def test_a_negation_or_inversion_sentence_gives_the_output_the_base_code_recorded(row):
    """Round 3 put NEGATED_QUESTION / INVERTED_QUESTION back to the base: the sentences that round 1/2 tested for the positive-evidence
    detectors (a form that is a trap, and a form that is not) now give EXACTLY the base's output in off and with the empty mapping."""
    assert_recorded(row)


@pytest.mark.parametrize("row", sentences_from(WRITE_TARGET_ORIGIN), ids=lambda r: r["id"])
def test_a_path_sentence_gives_the_output_the_base_code_recorded(row):
    """Round 3 put NO_ALLOWLIST back to the base: the path sentences of round 2 give EXACTLY the base's output."""
    assert_recorded(row)


@pytest.mark.parametrize("row", sentences_from(GATE_PASS_ORIGIN, GATE_UP_ORIGIN), ids=lambda r: r["id"])
def test_the_gate_gives_the_output_the_base_code_recorded_with_a_correct_script(row):
    """The mapping gate is the base's again (``_negated`` / ``_INVERT_CUE``): the same sentences with the script GOOD_D3 give the base's
    output down to ``mapping.exit_check`` -- the answer of the mapping is handed up by the gate, as before."""
    assert row["script"] == "good_d3"
    assert_recorded(row)
    rec = R3_RECORDED[(row["id"], "fakemap_script")]
    assert rec["decision"] == "escalate" and (rec["mapping_exit_check"] or "").startswith("QUESTION_UNREADABLE/")


def test_the_old_detectors_are_unchanged_because_the_stance_reader_uses_them():
    assert ca._negated("なければなりませんか") and ca._negated("yes or no") and ca._INVERT_CUE.search("at least")
    assert not ca._negated("問題ないですか") and ca._INVERT_CUE.search("drop-off")      # the old wide behaviour, kept on purpose


@pytest.mark.parametrize("frame_id,question,expected", [
    ("z04_kiln", "Can we delete last year's kiln logs?", True),
    ("z05_tideclock", "May I upload the tide table to the harbour website?", True),
    ("z06_choir", "Can we store the passwords in the sheet?", True),
    ("z04_kiln", "Are we allowed to erase the readings of the kiln door sensor?", True),
    ("z01_seedswap", "古い名簿を削除してもよいですか？", True),
    ("z03_festival", "出店料を支払ってもよいですか？", True),
    ("z01_seedswap", "参加者のパスワードを保存してもよいですか？", True),
    ("z01_seedswap", "古い名簿を削除することはできますか？", True),
    ("z05_tideclock", "Could a page with notes about the new release be added in this iteration?", False),
    ("z06_choir", "Could the page for resetting a forgotten password be part of this build?", False),
    ("z04_kiln", "May we use the small size for the stickers we pay for each month?", False),
    ("z01_seedswap", "公開される日をお知らせ画面に出すのは、今回の範囲に入れてよいですか？", False),
    ("z03_festival", "参加者へのお知らせは、公開の掲示板を使ってよいですか？", False),
    ("z04_kiln", "Can we ask someone to delete the old logs?", False),
])
def test_builtin_protected_is_asked_only_where_the_operation_is_asked(frame_id, question, expected):
    ctx = ctx_of(frame_id, question)
    assert ca._builtin_protected_asked(ctx) is expected
    if expected:
        assert ca._builtin_protected(ctx)          # the wide test (what the mapping gets) holds wherever the narrow one does


def test_the_allowlist_checks_are_not_loosened():
    # a frame WITH an allowlist keeps handing up a path outside it (OUTSIDE_ALLOWLIST is not one of the five traps)
    res = ca.answer_question(frame_path("z05_tideclock"), "Can I edit tools/check.sh?", ["Yes", "No"])
    assert (res["escalate_reason"], res["escalate_detail"]) == ("FRAME_SILENT", "OUTSIDE_ALLOWLIST")
    res = ca.answer_question(frame_path("z05_tideclock"), "Can I edit src/main.py?", ["Yes", "No"])
    assert res["decision"] == "answer" and res["answer"] == "Yes"
    # and a write to a path of a frame without an allowlist is still NO_ALLOWLIST
    res = ca.answer_question(frame_path("z04_kiln"), "Can I edit logs/firing.csv?", ["Yes", "No"])
    assert (res["escalate_reason"], res["escalate_detail"]) == ("FRAME_SILENT", "NO_ALLOWLIST")


# ---------------------------------------------------------------------------------------------
# mapping_gate: the same detectors, applied to an answer that comes out of the record mapping
# ---------------------------------------------------------------------------------------------

F1 = frame_path("z01_seedswap")
F4 = frame_path("z04_kiln")
YN_JA = ["はい", "いいえ"]
YN_EN = ["Yes", "No"]
GOOD_D3 = {"records": ["D3"], "decides": "決まる", "relations": {"D3": ["一致", "矛盾"]}}    # z01 D3: 当日の来場者の人数集計 in scope; z04 D3: kiln door sensor in scope
# paraphrases of D3 that have no frame term and none of the cue words of a vocabulary role: off hands them up as VOCAB_UNMAPPED
# (NO_ROLE) and only the record mapping can decide them; the gate looks at the form of the question afterwards


@pytest.mark.parametrize("frame,question,options,detail", [
    (F1, "会場に来た人の数を数えるのは、今回やらないのですか？", YN_JA, "NEGATED_QUESTION"),
    (F1, "会場に来た人の数を数えるのをやめるのは、今回の方針として正しいですか？", YN_JA, "INVERTED_QUESTION"),
    (F4, "Isn't the sensor on the oven door among the things we build?", YN_EN, "NEGATED_QUESTION"),
    (F4, "Do we skip the sensor on the oven door?", YN_EN, "INVERTED_QUESTION"),
])
def test_the_gate_hands_up_a_mapped_answer_to_a_question_with_positive_evidence(frame, question, options, detail):
    off = ca.answer_question(frame, question, options)
    assert (off["escalate_reason"], off["escalate_detail"]) == ("VOCAB_UNMAPPED", "NO_ROLE")
    res, _ = M.ask_map(frame, question, options, GOOD_D3)
    assert (res["decision"], res["escalate_reason"], res["escalate_detail"]) == ("escalate", "QUESTION_UNREADABLE", detail)
    assert res["mapping"]["exit_check"] == f"QUESTION_UNREADABLE/{detail}"
    assert res["trace"]["resolver_outcomes"]["mapping_gate"] == detail


@pytest.mark.parametrize("frame,question,options", [
    (F1, "会場に来た人の数を数えることは、今回やっておかなければなりませんか？", YN_JA),
    (F4, "Is the sensor on the oven door among the things we build, yes or no?", YN_EN),
    (F4, "Is the sensor on the oven door among the things we build, whether or not it is cheap?", YN_EN),
])
def test_the_gate_is_the_base_gate_again_a_negation_word_hands_a_mapped_answer_up(frame, question, options):
    """Round 3 (D9): the three sentences that round 2 let through ("なければならない", "yes or no", "whether or not") are handed up again
    by the base's ``_negated`` test.  Not "may pass or may be handed up": the exact type, the exit check and the gate's trace."""
    off = ca.answer_question(frame, question, options)
    assert (off["escalate_reason"], off["escalate_detail"]) == ("VOCAB_UNMAPPED", "NO_ROLE")
    res, _ = M.ask_map(frame, question, options, GOOD_D3)
    assert (res["decision"], res["escalate_reason"], res["escalate_detail"]) == ("escalate", "QUESTION_UNREADABLE", "NEGATED_QUESTION")
    assert res["mapping"]["exit_check"] == "QUESTION_UNREADABLE/NEGATED_QUESTION"
    assert res["trace"]["resolver_outcomes"]["mapping_gate"] == "NEGATED_QUESTION"


# ---------------------------------------------------------------------------------------------
# round 3, D10: a longer phrase without evidence goes to the record mapping; with the mapping off, or when it does not decide, the
# outcome is the base hand-up FRAME_SILENT/TERM_IN_WIDER_PHRASE
# ---------------------------------------------------------------------------------------------

WIDER_TERM = ("FRAME_SILENT", "TERM_IN_WIDER_PHRASE")
SET_FRAMES = {"fixtures": "fixtures", "w2g": "w2g", "w2g2": "w2g2", "w2g3": "w2g3"}


def every_item():
    """(set, id, frame path, question, options) of the frozen W2-c / W2-g data, the new data and the supplement: 349 + 159 + 46."""
    for s, r, fp in frozen_items():
        yield s, r["id"], fp, r["question"], r.get("options")
    for i in ITEMS:
        yield "w2c2", i["id"], frame_path(i["frame_id"]), i["question"], i["options"]
    for i in SUPP_ITEMS:
        yield "supp", i["id"], str(SUPP_FRAMES / f"{i['frame_id']}.md"), i["question"], i["options"]


@pytest.fixture(scope="module")
def every_row() -> dict:
    out = {}
    for s, iid, fp, q, o in every_item():
        out[(s, iid)] = {"off": ca.answer_question(fp, q, o), "fakemap": ca.answer_question(fp, q, o, vocab_llm="fake", map_fake=MAP_EMPTY)}
    return out


def wider_step(res: dict):
    return (res.get("trace") or {}).get("resolver_outcomes", {}).get("wider_phrase")


def test_every_row_of_the_data_is_run_and_the_wider_phrase_step_is_seen(every_row):
    assert len(every_row) == 349 + 159 + 46
    assert sum(1 for r in every_row.values() if wider_step(r["off"]) is not None) > 0


def test_a_wider_phrase_with_evidence_is_never_asked_of_the_mapping(every_row):
    """(b) With evidence (E0 / OTHER_RECORD) the hand-up stands in the rule layer: with the made-up mapping the run is NOT_ASKED."""
    rows = [r for r in every_row.values() if str(wider_step(r["off"]) or "").startswith("ESCALATE:EVIDENCE:")]
    assert len(rows) >= 10
    handed_up = 0
    for r in rows:
        if (r["off"]["escalate_reason"], r["off"]["escalate_detail"]) != WIDER_TERM:
            # the step stands before the request / status check: that one is a state-or-request question, not a hand-up of the phrase
            assert (r["off"]["escalate_reason"], r["off"]["escalate_detail"]) == ("OUT_OF_RANGE", "STATE_OR_REQUEST_QUESTION")
            continue
        handed_up += 1
        assert not_asked(r["fakemap"]) and r["fakemap"]["mapping"]["rule"]["detail"] == "TERM_IN_WIDER_PHRASE"
        assert (r["fakemap"]["escalate_reason"], r["fakemap"]["escalate_detail"]) == WIDER_TERM
    assert handed_up >= 10


@pytest.mark.parametrize("item", [i for i in ITEMS if i["trap"] == "WIDER" and i["group"] == "route"], ids=lambda i: i["id"])
def test_a_wider_route_sentence_is_off_the_base_hand_up_and_with_the_mapping_goes_to_it_and_comes_back_the_same(item, results):
    """(a) off: FRAME_SILENT/TERM_IN_WIDER_PHRASE.  With the empty made-up mapping: it IS asked (outcome not NOT_ASKED), the rule's type
    is VOCAB_UNMAPPED/TERM_IN_WIDER_PHRASE (only in ``mapping.rule``), and the mapping does not decide, so the final output is again
    FRAME_SILENT/TERM_IN_WIDER_PHRASE.  What the mapping said stays in ``mapping.outcome``."""
    off, fm = results[item["id"]]["off"], results[item["id"]]["fakemap"]
    assert (off["decision"], off["escalate_reason"], off["escalate_detail"]) == ("escalate",) + WIDER_TERM
    assert wider_step(off) == "ESCALATE:UNDECIDED:MAPPING_OFF"
    assert (fm["decision"], fm["escalate_reason"], fm["escalate_detail"]) == ("escalate",) + WIDER_TERM
    assert (fm["mapping"]["rule"]["reason"], fm["mapping"]["rule"]["detail"]) == ("VOCAB_UNMAPPED", "TERM_IN_WIDER_PHRASE")
    assert not not_asked(fm) and fm["mapping"]["outcome"].startswith("ESCALATED:")
    assert wider_step(fm).startswith("ESCALATE:UNDECIDED:MAPPING_DID_NOT_DECIDE:"), wider_step(fm)


def test_a_wider_phrase_that_hands_up_a_type_the_mapping_may_not_retry_is_not_routed(every_row):
    """(c) ALL rows of the data whose narrow reading hands up such a type: with the made-up mapping NOT_ASKED, final the base hand-up."""
    rows = {k: r for k, r in every_row.items() if wider_step(r["off"]) == "ESCALATE:UNDECIDED:NARROW_READING_HANDS_UP"}
    assert len(rows) >= 1
    for k, r in rows.items():
        assert wider_step(r["fakemap"]) == "ESCALATE:UNDECIDED:NARROW_READING_HANDS_UP", k
        assert not_asked(r["fakemap"]), k
        for mode in ("off", "fakemap"):
            assert (r[mode]["escalate_reason"], r[mode]["escalate_detail"]) == WIDER_TERM, (k, mode)


def test_vocab_unmapped_wider_phrase_is_never_the_final_output(every_row):
    """(d) VOCAB_UNMAPPED/TERM_IN_WIDER_PHRASE is the rule's internal type: it appears in ``mapping.rule`` only."""
    seen_rule = 0
    for k, r in every_row.items():
        for mode in ("off", "fakemap"):
            assert (r[mode]["escalate_reason"], r[mode]["escalate_detail"]) != ("VOCAB_UNMAPPED", "TERM_IN_WIDER_PHRASE"), (k, mode)
        rule = (r["fakemap"].get("mapping") or {}).get("rule") or {}
        seen_rule += (rule.get("reason"), rule.get("detail")) == ("VOCAB_UNMAPPED", "TERM_IN_WIDER_PHRASE")
    assert seen_rule >= 10


def test_a_wider_phrase_without_evidence_whose_narrow_reading_is_also_silent_goes_to_the_mapping_and_comes_back_frame_silent():
    """Round 2 (M2) returned the narrow reading's silence (NO_RECORD_DECIDES); round 3 hands the sentence to the mapping, and when the
    mapping does not decide the base hand-up is the final output (md and jsonl then give the same type)."""
    q = "Should the temperature reader work be finished by Friday?"
    off = ca.answer_question(frame_path("z04_kiln"), q, ["Yes", "No"])
    assert (off["escalate_reason"], off["escalate_detail"]) == WIDER_TERM and wider_step(off) == "ESCALATE:UNDECIDED:MAPPING_OFF"
    res = ca.answer_question(frame_path("z04_kiln"), q, ["Yes", "No"], vocab_llm="fake", map_fake=MAP_EMPTY)
    assert (res["escalate_reason"], res["escalate_detail"]) == WIDER_TERM
    assert not not_asked(res) and (res["mapping"]["rule"]["reason"], res["mapping"]["rule"]["detail"]) == ("VOCAB_UNMAPPED", "TERM_IN_WIDER_PHRASE")
    assert wider_step(res).startswith("ESCALATE:UNDECIDED:MAPPING_DID_NOT_DECIDE:")


@pytest.mark.parametrize("q", ["Is the kiln door sensor module in scope?", "Should the kiln door sensor module use the 10 minutes report interval?"])
def test_a_wider_phrase_without_evidence_is_not_answered_from_the_narrow_reading_by_the_rules(q):
    """The narrow reading's ANSWER is not taken by the rules (it only makes the sentence a candidate for the mapping): off and with
    the made-up mapping the output is the base hand-up; the mapping, with a script that answers, is what can answer it."""
    for kw in ({}, {"vocab_llm": "fake", "map_fake": MAP_EMPTY}):
        res = ca.answer_question(frame_path("z04_kiln"), q, ["Yes", "No"], **kw)
        assert res["decision"] == "escalate" and (res["escalate_reason"], res["escalate_detail"]) == WIDER_TERM, (q, kw)


# D10 step 3 (a): a sentence handed to the mapping IS answered when the (made-up) mapping gives a record and a relation.  Scripts follow
# the data's own ``truth.records``: a record that holds a value (D3 / D5: yes-no and choice records).
def wider_route_with_a_value_record():
    return [i for i in ITEMS if i["trap"] == "WIDER" and i["group"] == "route" and i["options"] is not None
            and not i["truth"]["records"][0].startswith("P")]


def script_for(item: dict, relations: list) -> dict:
    rid = item["truth"]["records"][0]
    return {"records": [rid], "decides": "決まる", "relations": {rid: relations}}


def ask_item(item: dict, script: dict) -> dict:
    res, _ = M.ask_map(frame_path(item["frame_id"]), item["question"], item["options"], script)
    return res


def test_a_wider_route_sentence_is_answered_by_the_mapping_when_the_script_names_the_right_record():
    items = wider_route_with_a_value_record()
    assert len(items) >= 3
    answered = 0
    for it in items:
        rel = ["一致" if k == it["truth"]["answer_option_index"] else "矛盾" for k in range(len(it["options"]))]
        res = ask_item(it, script_for(it, rel))
        assert res["decision"] == "answer" and truth_matches(res, it), (it["id"], res["decision"], res["escalate_reason"], res["escalate_detail"])
        assert res["mapping"]["outcome"] == "ANSWERED" and res["mapping"]["exit_check"] is None
        answered += 1
    assert answered >= 3


def test_a_conflict_or_no_allowed_option_of_the_mapping_stays_as_its_own_type():
    """The mapping's more specific hand-ups are not squashed into FRAME_SILENT/TERM_IN_WIDER_PHRASE."""
    it = next(i for i in ITEMS if i["id"] == "w2c2-wider-route-12")
    res = ask_item(it, script_for(it, ["矛盾", "矛盾"]))
    assert (res["escalate_reason"], res["escalate_detail"]) == ("NO_OPTION_ALLOWED", "MAPPED_NO_OPTION_AGREES")
    assert (res["mapping"]["rule"]["reason"], res["mapping"]["rule"]["detail"]) == ("VOCAB_UNMAPPED", "TERM_IN_WIDER_PHRASE")
    rid = it["truth"]["records"][0]
    res = ask_item(it, {"records": [rid, "D1"], "decides": "決まる", "relations": {rid: ["一致", "矛盾"], "D1": ["矛盾", "一致"]}})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("FRAME_CONFLICT", "MAPPED_RECORDS_DISAGREE")
    assert res["mapping"]["outcome"] == "ESCALATED:FRAME_CONFLICT/MAPPED_RECORDS_DISAGREE"


@pytest.mark.parametrize("q,detail", [
    ("Could we have included the moon phase icon design in scope?", "PAST_TENSE_PERMISSION"),
    ("Was it ok to include the moon phase icon design in scope?", "PAST_TENSE_PERMISSION"),
    ("Should we include the moon phase icon design in scope?", "ADVICE_NOT_PERMISSION"),
])
def test_the_gate_still_stands_after_a_wider_phrase_was_routed_and_its_exit_check_is_not_replaced(q, detail):
    """A routed wider-phrase question is answered by the mapping only through the gate: past tense / advice are handed up with an
    ``exit_check`` and the base hand-up does NOT replace them (an exit check is a more specific type than 'the frame is silent')."""
    res = ask_item({"frame_id": "z05_tideclock", "question": q, "options": ["Yes", "No"]}, GOOD_D3)
    assert res["decision"] == "escalate" and res["escalate_detail"] == detail
    assert res["mapping"]["exit_check"] and res["mapping"]["exit_check"].endswith(detail)
    assert (res["mapping"]["rule"]["reason"], res["mapping"]["rule"]["detail"]) == ("VOCAB_UNMAPPED", "TERM_IN_WIDER_PHRASE")


def test_a_negation_word_in_a_wider_phrase_question_is_handed_up_by_the_rule_layer_before_the_mapping_is_asked():
    """Measured: ``layer_negation`` stands before the wider-phrase step, so a sentence with a negation word never reaches the gate; with a
    script that would answer, the final output is the base's QUESTION_UNREADABLE/NEGATED_QUESTION and the mapping is NOT_ASKED."""
    res = ask_item({"frame_id": "z05_tideclock", "question": "Isn't the moon phase icon design in scope?", "options": ["Yes", "No"]}, GOOD_D3)
    assert (res["escalate_reason"], res["escalate_detail"]) == ("QUESTION_UNREADABLE", "NEGATED_QUESTION")
    assert not_asked(res) and res["mapping"]["exit_check"] is None


def test_the_narrow_reading_leaves_the_context_as_it_was():
    ctx = ctx_of("z04_kiln", "Should the temperature reader work be finished by Friday?", ["Yes", "No"])
    wide = [m for m in ctx.mentions if m.wider]
    assert wide
    before = (list(ctx.trace_tried), dict(ctx.trace_out), list(ctx.premise_sents))
    ca._narrow_reading(ctx, wide)
    assert (ctx.trace_tried, ctx.trace_out, ctx.premise_sents) == before and all(m.wider for m in wide)


# ---------------------------------------------------------------------------------------------
# round 2, M3: the supplement (tests/conduct_ask/w2c2/supp/), frozen BEFORE the round-2 rule changes
# ---------------------------------------------------------------------------------------------

SUPP = DATA / "supp"
SUPP_FRAMES = SUPP / "frames"
SUPP_ITEMS = [json.loads(ln) for ln in (SUPP / "items.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]


def supp_run(item: dict, mode: str) -> dict:
    kw = {"vocab_llm": "fake", "map_fake": MAP_EMPTY} if mode == "fakemap" else {}
    return ca.answer_question(str(SUPP_FRAMES / f"{item['frame_id']}.md"), item["question"], item["options"], **kw)


@pytest.fixture(scope="module")
def supp_results() -> dict:
    return {it["id"]: {"off": supp_run(it, "off"), "fakemap": supp_run(it, "fakemap")} for it in SUPP_ITEMS}


def supp_by(trap: str, group: str) -> list[dict]:
    return [i for i in SUPP_ITEMS if i["trap"] == trap and i["group"] == group]


def test_the_supplement_is_the_frozen_supplement():
    """artifacts/w2-c2/freeze_supp.txt holds the hashes taken before the round-2 rule changes (nothing is tuned afterwards)."""
    frozen = {}
    for ln in (ROOT / "artifacts" / "w2-c2" / "freeze_supp.txt").read_text(encoding="utf-8").splitlines():
        parts = ln.split()
        if len(parts) == 2 and len(parts[0]) == 64:
            frozen[parts[1]] = parts[0]
    for rel in ["tests/conduct_ask/w2c2/supp/items.jsonl"] + sorted(f"tests/conduct_ask/w2c2/supp/frames/{p.name}" for p in SUPP_FRAMES.glob("*.md")):
        assert frozen.get(rel) == hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), rel


def test_the_supplement_has_what_review_1_asked_for():
    assert len(supp_by("NO_ALLOWLIST", "route")) >= 10 and len(supp_by("NEGATED", "route")) >= 1
    ids = [i["id"] for i in SUPP_ITEMS]
    assert len(ids) == len(set(ids)) and all(i.startswith("supp-") for i in ids)
    for i in SUPP_ITEMS:
        assert (SUPP_FRAMES / f"{i['frame_id']}.md").exists() and i["trap"] in ("NEGATED", "NO_ALLOWLIST") and i["group"] in ("raise", "route")
        t = i["truth"]
        if i["group"] == "route":
            assert t["decision"] == "answer" and t["answer"] in ("Yes", "No", "はい", "いいえ") and t["records"]    # the frame has the answer
        else:
            assert t["decision"] == "escalate" and i["evidence"] and i["expect_rule"]
    for trap in ("NO_ALLOWLIST", "NEGATED"):
        for group in ("raise", "route"):
            for lang in ("ja", "en"):
                assert any(i["lang"] == lang for i in supp_by(trap, group)), (trap, group, lang)


@pytest.mark.parametrize("item", [i for i in SUPP_ITEMS if i["group"] == "raise"], ids=lambda i: i["id"])
def test_supp_c2_raise_is_handed_up_in_the_type_and_the_mapping_is_not_asked(item, supp_results):
    want = (item["expect_rule"]["reason"], item["expect_rule"]["detail"])
    for mode in ("off", "fakemap"):
        res = supp_results[item["id"]][mode]
        assert res["decision"] == "escalate" and (res["escalate_reason"], res["escalate_detail"]) == want, (mode, res["escalate_reason"], res["escalate_detail"])
    assert not_asked(supp_results[item["id"]]["fakemap"])


@pytest.mark.parametrize("item", [i for i in SUPP_ITEMS if i["group"] == "route"], ids=lambda i: i["id"])
def test_supp_route_rows_give_the_base_answer_in_both_modes(item, supp_results, base_rows):
    """C2-R on the supplement: it is made of NEGATED and NO_ALLOWLIST sentences only (both reverted), so after the revert every
    ``route`` row is handed up exactly as the base code does (round 2 had routed them; the auditor's ruling put them back)."""
    for mode in ("off", "fakemap"):
        assert six(supp_results[item["id"]][mode]) == base_rows[("supp", item["id"], mode)], mode


@pytest.mark.parametrize("item", [i for i in SUPP_ITEMS if i["group"] == "raise"], ids=lambda i: i["id"])
def test_supp_raise_rows_give_the_base_answer_in_both_modes(item, supp_results, base_rows):
    for mode in ("off", "fakemap"):
        assert six(supp_results[item["id"]][mode]) == base_rows[("supp", item["id"], mode)], mode
