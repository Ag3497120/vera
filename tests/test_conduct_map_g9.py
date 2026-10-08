"""G9 (W2-g2, protocol conduct_map/v2): one decision per question, the second ask of an invalid reply, effort and the other settings,
with made-up providers only (a scripted reply is an assumption about a model, not a measurement of one).

Each case goes through the public entry (``answer_question`` or the CLI ``main``) and is checked down to the ledger rows."""
from __future__ import annotations

import inspect
import io
import json
import subprocess
import sys
import threading
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import map_helpers as M  # noqa: E402
from map_helpers import ask_map, w2g  # noqa: E402
from verantyx import conduct_ask  # noqa: E402
from verantyx import conduct_map as cm  # noqa: E402
from verantyx.llm_choice import ChoiceLedger, ProviderReply  # noqa: E402

F = w2g("w01_shelfcheck")
Q = "地元の歴史に関する資料も、確認する本に入りますか？"            # asks about D3 (scope: 郷土資料の点検 in scope)
YN = M.YN_JA
OPTS3 = ["はい", "いいえ", "どちらでもない"]
GOOD = {"records": ["D3"], "decides": "決まる", "relations": {"D3": ["一致", "矛盾"]}}
GOOD3 = {"records": ["D3"], "decides": "決まる", "relations": {"D3": ["一致", "矛盾", "無関係"]}}
X01 = str(Path(__file__).resolve().parent / "conduct_ask" / "w2g2" / "frames" / "x01_garden.md")     # chain P1 -> ... -> P5
X05 = str(Path(__file__).resolve().parent / "conduct_ask" / "w2g2" / "frames" / "x05_solar.md")     # diamond P2 || P3
CHAIN_Q = "お試し利用に進めるのは、区画のリストの用意が済んでからですか？"
CHAIN = {"phases": ["P1", "P5"], "relations": {"order:P1<P5": ["一致", "矛盾"]}, "records": ["order:ALL"], "decides": "決まる"}


@pytest.fixture(autouse=True)
def no_process(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("a real provider process must never be started")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)


def asks(mp, step=None):
    return [e for e in mp.ledger.entries() if e["type"] == "map_ask" and (step is None or e["step"] == step)]


def decisions(mp, step=None):
    return [e for e in mp.ledger.entries() if e["type"] == "map_decision" and (step is None or e["step"] == step)]


class Flaky:
    """A provider that wraps a scripted one and answers the first asks that ``when(prompt)`` selects with the given texts (an invalid
    reply, say), then delegates.  ``when`` picks the step by a line of the prompt."""

    name = "flaky"

    def __init__(self, inner, bad, when):
        self.inner, self.bad, self.when, self.n = inner, list(bad), when, 0
        self._lock = threading.Lock()

    @property
    def calls(self):
        return self.inner.calls

    def ask(self, prompt):
        if self.when(prompt):
            with self._lock:
                i = self.n
                self.n += 1
            if i < len(self.bad):
                return ProviderReply.success(self.bad[i], provider=self.inner.name)
        return self.inner.ask(prompt)


IS_RECORDS = lambda p: '0: {"kind"' in p          # noqa: E731
IS_DECIDES = lambda p: "対象:" in p               # noqa: E731
IS_RELATION = lambda p: "選択肢（この 1 つだけ）" in p      # noqa: E731


def flaky_mapper(options, script, slot, bad, when, **kw):
    pair = list(cm.fake_pair(script, M.view_of(F), options))
    pair[slot] = Flaky(pair[slot], bad, when)
    return M.mapper_for(F, options, providers=tuple(pair), **kw)


def run(mp, question=Q, options=YN):
    return conduct_ask.answer_question(F, question, options, vocab_llm="fake", mapper=mp)


# ---- 1-3: the pairs of the relation step are decided one by one ----------------------------------------------------------------------

def test_g9_1_three_options_make_three_pairs_each_agreed_on_its_own():
    res, mp = ask_map(F, Q, OPTS3, GOOD3)
    assert (res["decision"], res["answer"], res["answer_option_index"]) == ("answer", "はい", 0)
    rel = decisions(mp, "relation")
    assert len(rel) == 3 and all(d["status"] == "ADOPTED" for d in rel)
    assert [d["result"] for d in rel] == [{"relation": "一致"}, {"relation": "矛盾"}, {"relation": "無関係"}]
    assert len(asks(mp, "relation")) == 6 and all(len(d["ask_ids"]) == 2 for d in rel)
    assert res["mapping"]["asks_used"] == 2 + 2 + 6 and res["mapping"]["retries"] == 0
    assert [(x["option_index"], x["relation"], x["status"]) for x in res["mapping"]["step2"]] == [(0, "一致", "ADOPTED"), (1, "矛盾", "ADOPTED"),
                                                                                                  (2, "無関係", "ADOPTED")]


def test_g9_2_one_pair_that_disagrees_leaves_the_other_pairs_adopted_and_nothing_is_answered():
    script = {**GOOD3, "relations": {"D3": ["一致", "矛盾", "矛盾"]}, "relations2": {"D3": ["一致", "矛盾", "無関係"]}}
    res, mp = ask_map(F, Q, OPTS3, script)
    assert (res["decision"], res["answer"], res["escalate_reason"], res["escalate_detail"]) == ("escalate", None, "MAPPING_UNSETTLED", "STEP2_DISAGREE")
    assert [d["status"] for d in decisions(mp, "relation")] == ["ADOPTED", "ADOPTED", "ABSTAINED"]
    assert [x["status"] for x in res["mapping"]["step2"]] == ["ADOPTED", "ADOPTED", "ABSTAINED"]
    assert [x["relation"] for x in res["mapping"]["step2"]] == ["一致", "矛盾", None]            # no answer is made from two pairs of three
    assert res["mapping"]["asks_used"] == 10 and len(asks(mp, "relation")) == 6


def test_g9_3_two_records_by_two_options_all_agreeing_give_a_combined_answer_with_both_original_lines():
    script = {"records": ["D2", "D3"], "decides": "決まる", "relations": {"D2": ["一致", "矛盾"], "D3": ["一致", "矛盾"]}}
    res, mp = ask_map(F, Q, YN, script)
    assert (res["decision"], res["answer"], res["derivation"]) == ("answer", "はい", "COMBINED")
    assert [b["id"] for b in res["basis"]] == ["D2", "D3"]
    assert [b["text"] for b in res["basis"]] == [M.frame_line(F, b["line"]) for b in res["basis"]]
    assert len(decisions(mp, "relation")) == 4 and res["mapping"]["asks_used"] == 2 + 2 + 8
    assert [(x["record"], x["option_index"]) for x in res["mapping"]["step2"]] == [("D2", 0), ("D2", 1), ("D3", 0), ("D3", 1)]


# ---- 4-6: the second ask of an invalid reply (records, decides, relation) ----------------------------------------------------------

def test_g9_4_an_invalid_first_reply_of_the_records_step_is_asked_again_in_a_new_order_and_then_adopted():
    mp = flaky_mapper(YN, GOOD, 0, ["records: D3 です"], IS_RECORDS)
    res = run(mp)
    assert (res["decision"], res["answer"]) == ("answer", "はい")
    rows = asks(mp, "records")
    assert len(rows) == 3 and [(r["ask_index"], r["attempt"]) for r in rows] == [(0, 0), (1, 0), (0, 1)]
    retry = rows[2]
    assert retry["retry_of"] == rows[0]["id"] and retry["id"] == rows[0]["decision_id"] + ".0.r1"
    assert retry["order"] != rows[0]["order"] and sorted(retry["order"]) == sorted(rows[0]["order"])          # a new order, though the source is fixed
    assert retry["variant"] == rows[0]["variant"] == 0 and retry["provider"] == rows[0]["provider"]          # the same provider and wording
    assert retry["prompt"] != rows[0]["prompt"] and retry["prompt"].split("記録（1行に")[0] == rows[0]["prompt"].split("記録（1行に")[0]
    assert rows[0]["verdict"] == "INVALID" and rows[0]["invalid_reason"] == "NOT_MINIMAL_FORM" and retry["verdict"] == "PICK"
    d = decisions(mp, "records")[0]
    assert d["status"] == "ADOPTED" and d["ask_ids"] == [r["id"] for r in rows] and d["result"] == {"records": ["D3"]}
    assert res["mapping"]["asks_used"] == 3 + 2 + 4 and res["mapping"]["retries"] == 1
    assert res["mapping"]["step1"]["retries"] == 1


def test_g9_5_a_second_invalid_reply_hands_the_question_up_after_exactly_one_second_ask_per_slot():
    mp = M.mapper_for(F, YN, providers=(M.TextProvider("D3 です"), M.TextProvider("答え: 2")))
    res = run(mp)
    assert (res["decision"], res["escalate_reason"], res["escalate_detail"]) == ("escalate", "MAPPING_UNSETTLED", "STEP1_INVALID_ANSWER")
    rows = asks(mp, "records")
    assert [(r["ask_index"], r["attempt"], r["verdict"]) for r in rows] == [(0, 0, "INVALID"), (1, 0, "INVALID"), (0, 1, "INVALID"), (1, 1, "INVALID")]
    assert res["mapping"]["asks_used"] == 4 and res["mapping"]["retries"] == 2 and decisions(mp, "records")[0]["status"] == "ABSTAINED"
    assert [p.calls for p in mp.providers] == [2, 2]


def test_g9_6a_the_decides_step_asks_an_invalid_reply_again_and_adopts_the_valid_one():
    mp = flaky_mapper(YN, GOOD, 1, ["決まる。答えは A"], IS_DECIDES)
    res = run(mp)
    assert (res["decision"], res["answer"]) == ("answer", "はい")
    rows = asks(mp, "decides")
    assert [(r["ask_index"], r["attempt"], r["verdict"]) for r in rows] == [(0, 0, "PICK"), (1, 0, "INVALID"), (1, 1, "PICK")]
    assert rows[2]["retry_of"] == rows[1]["id"] and rows[2]["labels_shown"] != rows[1]["labels_shown"] and rows[2]["order"] != rows[1]["order"]
    assert decisions(mp, "decides")[0]["status"] == "ADOPTED" and res["mapping"]["retries"] == 1


def test_g9_6b_the_decides_step_with_a_second_invalid_reply_is_handed_up():
    pair = cm.fake_pair(GOOD, M.view_of(F), YN)
    mp = M.mapper_for(F, YN, providers=(Flaky(pair[0], ["決まる。"] * 2, IS_DECIDES), pair[1]))
    res = run(mp)
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "DECIDES_INVALID_ANSWER")
    assert [(r["ask_index"], r["attempt"]) for r in asks(mp, "decides")] == [(0, 0), (1, 0), (0, 1)] and asks(mp, "relation") == []


def test_g9_6c_a_relation_pair_asks_its_invalid_slot_again_and_the_answer_is_still_made():
    mp = flaky_mapper(YN, GOOD, 0, ["一致。"], IS_RELATION)
    res = run(mp)
    assert (res["decision"], res["answer"]) == ("answer", "はい")
    rel = asks(mp, "relation")
    assert len(rel) == 5 and sum(1 for r in rel if r["attempt"] == 1) == 1 and res["mapping"]["retries"] == 1
    first_invalid = next(r for r in rel if r["verdict"] == "INVALID")
    retry = next(r for r in rel if r["attempt"] == 1)
    assert retry["retry_of"] == first_invalid["id"] and (retry["option_index"], retry["option"]) == (first_invalid["option_index"], first_invalid["option"])
    assert res["mapping"]["asks_used"] == 2 + 2 + 5


def test_g9_6d_a_relation_pair_that_stays_invalid_hands_the_question_up_and_the_other_pairs_are_kept():
    pair = cm.fake_pair(GOOD, M.view_of(F), YN)
    mp = M.mapper_for(F, YN, providers=(Flaky(pair[0], ["一致。"] * 4, IS_RELATION), pair[1]))
    res = run(mp)
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "STEP2_INVALID_ANSWER") and res["answer"] is None
    assert [x["status"] for x in res["mapping"]["step2"]] == ["ABSTAINED", "ABSTAINED"] and res["mapping"]["retries"] == 2
    assert sum(1 for r in asks(mp, "relation") if r["attempt"] == 1) == 2


# ---- 7: failures are typed and are not asked again ---------------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["TIMEOUT", "LIMIT_REACHED"])
def test_g9_7_a_failure_is_not_asked_again_in_any_step(kind):
    res, mp = ask_map(F, Q, YN, {**GOOD, "fail2": kind})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", f"STEP1_FAILED:{kind}")
    assert len(asks(mp)) == 2 and all(r["attempt"] == 0 for r in asks(mp)) and res["mapping"]["retries"] == 0
    res, mp = ask_map(F, Q, YN, {**GOOD, "fail_decides": kind})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", f"DECIDES_FAILED:{kind}")
    assert len(asks(mp, "decides")) == 2 and res["mapping"]["asks_used"] == 4
    res, mp = ask_map(F, Q, YN, {**GOOD, "fail_relations2": kind})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", f"STEP2_FAILED:{kind}")
    assert len(asks(mp, "relation")) == 4 and res["mapping"]["retries"] == 0


def test_g9_7b_an_invalid_reply_next_to_a_failed_one_is_not_asked_again():
    res, mp = ask_map(F, Q, YN, {**GOOD, "fail": "TIMEOUT", "fail2": None, "raw2": "xx"})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "STEP1_FAILED:TIMEOUT")
    assert len(asks(mp)) == 2 and decisions(mp, "records")[0]["detail"] == "RETRY_SKIPPED_PAIR_FAILED"


# ---- 8: the cap of a question's asks -------------------------------------------------------------------------------------------------

def test_g9_8a_a_second_ask_that_would_pass_the_cap_is_not_made_and_is_not_reused_later():
    mp = flaky_mapper(YN, GOOD, 1, ["xx"], IS_RECORDS, max_asks=2)
    res = run(mp)
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "STEP1_INVALID_ANSWER")
    assert len(asks(mp, "records")) == 2 and res["mapping"]["asks_used"] == 2 and res["mapping"]["retries"] == 0
    d = decisions(mp, "records")[0]
    assert d["status"] == "ABSTAINED" and d["detail"] == "RETRY_NO_BUDGET"
    # with room for it, the same question is asked afresh: a decision that only the lack of budget caused is not reused
    pair = cm.fake_pair(GOOD, M.view_of(F), YN)
    mp2 = M.mapper_for(F, YN, providers=pair, ledger=mp.ledger)
    res2 = run(mp2)
    assert res2["decision"] == "answer" and not any(e["type"] == "map_reuse" and e["step"] == "records" for e in mp.ledger.entries())


def test_g9_8b_the_pairs_that_do_not_all_fit_are_not_asked_at_all():
    res, mp = ask_map(F, Q, YN, GOOD, max_asks=2 + 2 + 3)           # the 2 pairs need 4 asks, 3 are left
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "ASK_BUDGET")
    assert asks(mp, "relation") == [] and res["mapping"]["asks_used"] == 4
    assert [(d["status"], d["reason"]) for d in decisions(mp, "relation")] == [("REFUSED", "ASK_BUDGET")] * 2
    res, mp = ask_map(F, Q, YN, GOOD, max_asks=2 + 2 + 4)           # exactly enough
    assert res["decision"] == "answer" and res["mapping"]["asks_used"] == 8


def test_g9_8c_the_default_cap_covers_a_second_ask_in_every_step_of_one_record_and_three_options():
    # records 2+1, decides 2+1, 3 pairs x (2+1) = 15 <= 24
    pair = cm.fake_pair(GOOD3, M.view_of(F), OPTS3)
    p0 = Flaky(Flaky(Flaky(pair[0], ["x"], IS_RECORDS), ["x"] * 3, IS_RELATION), [], IS_DECIDES)
    p1 = Flaky(pair[1], ["x"], IS_DECIDES)
    mp = M.mapper_for(F, OPTS3, providers=(p0, p1))
    res = run(mp, Q, OPTS3)
    assert (res["decision"], res["answer"]) == ("answer", "はい")
    assert res["mapping"]["asks_used"] == 15 <= cm.DEFAULT_MAX_ASKS and res["mapping"]["retries"] == 5 and res["mapping"]["asks_cap"] == 24


# ---- 9: what the decides question shows ---------------------------------------------------------------------------------------------

def test_g9_9a_the_decides_prompt_shows_the_question_and_the_original_lines_and_no_option():
    res, mp = ask_map(F, Q, ["郷土資料を含める", "郷土資料を含めない"], {**GOOD, "relations": {"D3": ["一致", "矛盾"]}})
    prompts = [r["prompt"] for r in asks(mp, "decides")]
    assert len(prompts) == 2 and prompts[0] != prompts[1]
    d3 = M.frame_line(F, next(b["line"] for b in res["basis"] if b["id"] == "D3"))
    for p in prompts:
        assert json.dumps(Q, ensure_ascii=False) in p and json.dumps(d3, ensure_ascii=False) in p
        assert "郷土資料を含め" not in p and "選択肢" not in p and "記録: " not in p
    rel = [r["prompt"] for r in asks(mp, "relation")]
    assert any("郷土資料を含める" in p for p in rel) and all("選択肢（この 1 つだけ）" in p for p in rel)         # an option is shown to the relation question only


def test_g9_9b_the_order_decides_prompt_shows_the_edge_lines_and_the_phases_at_their_ends():
    res, mp = ask_map(X01, CHAIN_Q, YN, CHAIN)
    order_decides = [r for r in asks(mp, "decides") if "対象: 工程の順序" in r["prompt"]]
    assert len(order_decides) == 2
    text = Path(X01).read_text(encoding="utf-8").splitlines()
    edge_lines = [ln.strip() for ln in text if "->" in ln and ln.strip().startswith("P")]
    phase_lines = [ln.strip() for ln in text if ln.strip()[:2] in ("P1", "P2", "P3", "P4", "P5") and "->" not in ln]
    assert len(edge_lines) >= 4 and len(phase_lines) == 5
    for r in order_decides:
        for ln in edge_lines[:4] + phase_lines:
            assert json.dumps(ln, ensure_ascii=False) in r["prompt"], ln
        assert "選択肢" not in r["prompt"]
    # the records question of the same run asked about the whole family: its decides shows the family's lines too
    records_decides = [r for r in asks(mp, "decides") if "対象: 記録" in r["prompt"]]
    assert len(records_decides) == 2


# ---- 10-11: records that do not decide, phases that are not ordered ---------------------------------------------------------------

def test_g9_10_records_that_do_not_decide_by_two_agreeing_readings_stop_before_the_options():
    res, mp = ask_map(F, Q, YN, {**GOOD, "decides": "決まらない"})
    assert (res["decision"], res["escalate_reason"], res["escalate_detail"]) == ("escalate", "FRAME_SILENT", "MAP_RECORD_DOES_NOT_DECIDE")
    assert res["mapping"]["asks_used"] == 4 and asks(mp, "relation") == [] and [b["id"] for b in res["basis"]] == ["D3"]
    assert res["mapping"]["decides"]["decides"] == "決まらない"


def test_g9_11_two_parallel_phases_are_handed_up_before_the_decides_question_is_asked():
    q = "Which gets built first, the daily chart or the fault alert?"
    res, mp = ask_map(X05, q, ["Build the fault alert", "Build the daily chart"], {"phases": ["P2", "P3"]})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("FRAME_SILENT", "UNORDERED")
    assert [r["step"] for r in asks(mp)] == ["phases", "phases"] and res["mapping"]["asks_used"] == 2


# ---- 12: effort and timeout ---------------------------------------------------------------------------------------------------------

def _main(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = conduct_ask.main(argv)
    return code, json.loads(out.getvalue())


def _base(*extra):
    return ["--frame", F, "--question", Q, "--option", "はい", "--option", "いいえ", *extra]


@pytest.fixture
def built(monkeypatch):
    """Replace the real builder by one that records its arguments, builds the real (idle) providers and hands out a scripted mapper."""
    seen = []
    real = cm.build_real_mapper

    def spy(mode, second, ledger, max_asks, effort="low", timeout=None):
        idle = real(mode, second, ledger, max_asks, effort=effort, timeout=timeout)        # no process is started by building
        seen.append((mode, second, max_asks, effort, timeout, idle))
        return M.mapper_for(F, YN, GOOD)
    monkeypatch.setattr(cm, "build_real_mapper", spy)
    return seen


def test_g9_12a_the_cli_effort_reaches_the_codex_provider_and_its_command_line(built):
    code, res = _main(_base("--vocab-llm", "codex", "--map-effort", "xhigh", "--map-timeout", "600"))
    assert code == 0 and res["decision"] == "answer" and res["mapping"]["asks_cap"] == 24
    mode, second, max_asks, effort, timeout, idle = built[-1]
    assert (mode, second, max_asks, effort, timeout) == ("codex", None, 24, "xhigh", 600.0)
    assert [type(p).__name__ for p in idle.providers] == ["CodexProvider", "CodexProvider"]
    assert [p.effort for p in idle.providers] == ["xhigh", "xhigh"] and [p.timeout for p in idle.providers] == [600.0, 600.0]
    spec = idle.providers[0].build_command("p", "/nonexistent-workdir")           # only builds the argument list; nothing is started
    assert 'model_reasoning_effort="xhigh"' in spec.argv and "gpt-6-luna" in spec.argv


def test_g9_12b_without_the_argument_the_effort_is_low_and_the_time_limit_is_the_providers_own(built):
    code, res = _main(_base("--vocab-llm", "codex"))
    assert code == 0
    mode, second, max_asks, effort, timeout, idle = built[-1]
    assert (effort, timeout) == ("low", None) and [p.effort for p in idle.providers] == ["low", "low"] and idle.providers[0].timeout == 240.0
    assert 'model_reasoning_effort="low"' in idle.providers[0].build_command("p", "/nonexistent-workdir").argv


def test_g9_12c_the_claude_provider_gets_the_same_effort(built):
    _main(_base("--vocab-llm", "codex", "--map-second", "claude", "--map-effort", "high"))
    idle = built[-1][-1]
    assert [type(p).__name__ for p in idle.providers] == ["CodexProvider", "ClaudeProvider"] and [p.effort for p in idle.providers] == ["high", "high"]


@pytest.mark.parametrize("argv,detail", [
    (["--vocab-llm", "codex", "--map-effort", "max"], "BAD_MAP_EFFORT"),
    (["--vocab-llm", "codex", "--map-effort", ""], "BAD_MAP_EFFORT"),
    (["--vocab-llm", "codex", "--map-effort", "LOW"], "BAD_MAP_EFFORT"),
    (["--map-effort", "low"], "MAP_EFFORT_WITHOUT_REAL_MODE"),                           # off
    (["--vocab-llm", "fake", "--map-effort", "low"], "MAP_EFFORT_WITHOUT_REAL_MODE"),
    (["--vocab-llm", "codex", "--map-timeout", "0"], "BAD_MAP_TIMEOUT"),
    (["--vocab-llm", "codex", "--map-timeout", "-5"], "BAD_MAP_TIMEOUT"),
    (["--vocab-llm", "codex", "--map-timeout", "nan"], "BAD_MAP_TIMEOUT"),
    (["--vocab-llm", "codex", "--map-timeout", "inf"], "BAD_MAP_TIMEOUT"),
    (["--map-timeout", "600"], "MAP_TIMEOUT_WITHOUT_REAL_MODE"),
    (["--vocab-llm", "fake", "--map-timeout", "600"], "MAP_TIMEOUT_WITHOUT_REAL_MODE"),
    (["--vocab-llm", "codex", "--map-timeout", "abc"], "BAD_ARGUMENTS"),
])
def test_g9_12d_a_bad_effort_or_timeout_is_a_typed_refusal_with_exit_code_2(argv, detail, built):
    code, res = _main(_base(*argv))
    assert code == 2 and res["decision"] == "escalate" and res["escalate_detail"] == detail and built == []
    assert detail in conduct_ask.INPUT_REFUSALS or detail == "BAD_ARGUMENTS"


def test_g9_12e_the_api_refuses_the_same_values(built):
    for kw, detail in (({"vocab_llm": "codex", "map_effort": "max"}, "BAD_MAP_EFFORT"),
                       ({"vocab_llm": "off", "map_effort": "xhigh"}, "MAP_EFFORT_WITHOUT_REAL_MODE"),
                       ({"vocab_llm": "codex", "map_timeout": True}, "BAD_MAP_TIMEOUT"),
                       ({"vocab_llm": "codex", "map_timeout": "5"}, "BAD_MAP_TIMEOUT"),
                       ({"vocab_llm": "codex", "map_timeout": 0}, "BAD_MAP_TIMEOUT"),
                       ({"vocab_llm": "off", "map_timeout": 5}, "MAP_TIMEOUT_WITHOUT_REAL_MODE")):
        res = conduct_ask.answer_question(F, Q, YN, **kw)
        assert (res["escalate_reason"], res["escalate_detail"]) == ("QUESTION_UNREADABLE", detail), kw
    assert built == []
    res = conduct_ask.answer_question(F, Q, YN, vocab_llm="codex", map_effort="medium", map_timeout=90)
    assert res["decision"] == "answer" and built[-1][3:5] == ("medium", 90)


def test_g9_12f_the_real_builder_refuses_an_unknown_effort_and_builds_each_known_one():
    for effort in cm.MAP_EFFORTS:
        mp = cm.build_real_mapper("codex", None, None, 24, effort=effort, timeout=30)
        assert [p.effort for p in mp.providers] == [effort, effort] and [p.timeout for p in mp.providers] == [30.0, 30.0]
    with pytest.raises(ValueError):
        cm.build_real_mapper("codex", None, None, 24, effort="max")
    assert conduct_ask.MAP_EFFORTS == cm.MAP_EFFORTS == ("low", "medium", "high", "xhigh")


# ---- 13: effort in the ledger and in the reuse key ---------------------------------------------------------------------------------

class WithEffort:
    """A scripted provider that reports a model and an effort the way a real one does."""

    def __init__(self, inner, effort, model="m1"):
        self.inner, self.effort, self.model, self.name = inner, effort, model, "withfort"

    @property
    def calls(self):
        return self.inner.calls

    def ask(self, prompt):
        r = self.inner.ask(prompt)
        return ProviderReply(r.text, r.failure, self.name, self.model, self.effort)


def _effort_mapper(effort, ledger, model="m1"):
    pair = cm.fake_pair(GOOD, M.view_of(F), YN)
    return M.mapper_for(F, YN, providers=tuple(WithEffort(p, effort, model) for p in pair), ledger=ledger)


def test_g9_13_the_effort_is_in_every_ledger_row_and_an_ask_of_another_effort_or_model_is_not_reused():
    ledger = ChoiceLedger(None)
    a = _effort_mapper("low", ledger)
    r1 = run(a)
    assert r1["decision"] == "answer" and {r["effort"] for r in asks(a)} == {"low"} and {r["model"] for r in asks(a)} == {"m1"}
    n = len(asks(a))
    b = _effort_mapper("low", ledger)                                     # the same providers' description: reused, nothing asked
    r2 = run(b)
    assert r2["decision"] == "answer" and len(asks(a)) == n and b.providers[0].calls == 0 and r2["mapping"]["asks_used"] == 0
    assert sum(1 for e in ledger.entries() if e["type"] == "map_reuse") == 4
    c = _effort_mapper("xhigh", ledger)                                   # another effort: a different ask
    r3 = run(c)
    assert r3["decision"] == "answer" and len(asks(a)) == 2 * n and {r["effort"] for r in asks(a)} == {"low", "xhigh"} and r3["mapping"]["asks_used"] == 8
    d = _effort_mapper("low", ledger, model="m2")                          # another model: a different ask
    run(d)
    assert len(asks(a)) == 3 * n and sum(1 for e in ledger.entries() if e["type"] == "map_reuse") == 4
    assert r3["mapping"]["effort"] == "xhigh" and r1["mapping"]["effort"] == "low"


def test_g9_13b_a_decision_of_the_earlier_protocol_is_not_reused():
    ledger = ChoiceLedger(None)
    mp = M.mapper_for(F, YN, GOOD, ledger=ledger)
    cands = cm.all_candidates(M.view_of(F))
    sess = mp.session("0" * 64, Q, YN)
    key = json.loads(mp._key("records", sess, [[c.id, c.text] for c in cands], None))
    assert key["protocol"] == "conduct_map/v2" and key["providers"] == [["scripted-map", "", ""]] * 2
    v1 = dict(key, protocol="conduct_map/v1")
    v1.pop("providers")
    ledger.append({"type": "map_decision", "decision_id": "old1", "key": json.dumps(v1, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                   "step": "records", "record_id": None, "status": "ADOPTED", "reason": "ADOPTED", "detail": "",
                   "result": {"records": ["D3"], "decides": "決まる"}, "ask_ids": [], "question": Q, "candidates": [], "ts": "x"})
    assert mp._cached(mp._key("records", sess, [[c.id, c.text] for c in cands], None)) is None


# ---- 14: the number of asks in flight --------------------------------------------------------------------------------------------------

class Counting:
    def __init__(self, inner):
        self.inner, self.now, self.peak, self.name = inner, 0, 0, "counting"
        self._lock = threading.Lock()

    def ask(self, prompt):
        with self._lock:
            self.now += 1
            self.peak = max(self.peak, self.now)
        try:
            time.sleep(0.03)
            return self.inner.ask(prompt)
        finally:
            with self._lock:
                self.now -= 1


@pytest.mark.parametrize("limit", [1, 2, 3])
def test_g9_14_no_more_asks_than_max_parallel_are_in_flight_at_once(limit):
    lock, state = threading.Lock(), {"now": 0, "peak": 0}

    class Joint:
        """The two providers of a mapper are separate objects: count the asks in flight over both."""
        def __init__(self, inner):
            self.inner, self.name = inner, "joint"

        def ask(self, prompt):
            with lock:
                state["now"] += 1
                state["peak"] = max(state["peak"], state["now"])
            try:
                time.sleep(0.03)
                return self.inner.ask(prompt)
            finally:
                with lock:
                    state["now"] -= 1
    pair = cm.fake_pair(GOOD3, M.view_of(F), OPTS3)
    mp = M.mapper_for(F, OPTS3, providers=(Joint(pair[0]), Joint(pair[1])), max_parallel=limit)
    res = run(mp, Q, OPTS3)
    assert res["decision"] == "answer" and res["mapping"]["asks_used"] == 10
    assert state["peak"] == limit            # 6 asks of the three pairs are ready at once: the limit, and never more, is in flight


def test_g9_14b_the_default_is_a_configured_number_and_a_mapper_never_runs_with_zero():
    assert cm.DEFAULT_MAX_PARALLEL == 6 and M.mapper_for(F, YN, GOOD).max_parallel == 6
    assert M.mapper_for(F, YN, GOOD, max_parallel=0).max_parallel == 1


# ---- 15: nothing of a reply but a closed choice is ever used -----------------------------------------------------------------------------

@pytest.mark.parametrize("raw", ["2\n答え: はい", '{"records": [0], "answer": "はい"}', "はい", "答え: いいえ", "2 / はい"])
def test_g9_15a_a_records_reply_with_an_answer_in_it_is_invalid_and_no_answer_is_made_from_it(raw):
    res, mp = ask_map(F, Q, YN, {**GOOD, "raw": raw})
    assert res["decision"] == "escalate" and res["answer"] is None and res["answer_option_index"] is None
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "STEP1_INVALID_ANSWER")
    assert [r["verdict"] for r in asks(mp, "records") if r["ask_index"] == 0] == ["INVALID", "INVALID"]


@pytest.mark.parametrize("raw", ["一致（肢1）", "一致。", '{"relation": "一致", "answer": "はい"}', "はい", "1"])
def test_g9_15b_a_relation_reply_that_is_not_one_word_of_the_set_is_invalid(raw):
    res, mp = ask_map(F, Q, YN, {**GOOD, "raw_relations": raw})
    assert res["decision"] == "escalate" and res["answer"] is None
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "STEP2_INVALID_ANSWER")
    assert all(r["parsed"] is None for r in asks(mp, "relation") if r["ask_index"] == 0)


@pytest.mark.parametrize("raw", ["決まる。答えは A", "決まる\nはい", '{"decides": "決まる"}', "はい", "yes"])
def test_g9_15c_a_decides_reply_that_is_not_one_word_of_the_set_is_invalid(raw):
    res, mp = ask_map(F, Q, YN, {**GOOD, "raw_decides": raw})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "DECIDES_INVALID_ANSWER") and res["answer"] is None


def test_g9_15d_the_answer_text_is_always_the_callers_option_and_never_a_word_of_a_reply():
    res, mp = ask_map(F, Q, ["はい（推奨）", "いいえ"], GOOD)
    assert res["answer"] == "はい（推奨）"
    replies = {r["raw_reply"] for r in asks(mp)}
    assert res["answer"] not in replies and all(len(x) <= 4 for x in replies)
    assert "決まる" not in json.dumps({k: res[k] for k in ("answer", "basis", "derivation")}, ensure_ascii=False)


# ---- 16: the configured defaults agree ------------------------------------------------------------------------------------------------------

def test_g9_16_the_default_cap_of_one_questions_asks_is_24_everywhere():
    assert cm.DEFAULT_MAX_ASKS == conduct_ask.DEFAULT_MAP_MAX_ASKS == 24
    assert inspect.signature(conduct_ask.answer_question).parameters["map_max_asks"].default == 24
    assert conduct_ask.build_parser().get_default("map_max_asks") == 24
    assert inspect.signature(M.mapper_for).parameters["max_asks"].default == cm.DEFAULT_MAX_ASKS
    assert cm.DEFAULT_MAX_CANDIDATES == 24 and cm.DEFAULT_MAX_RECORDS == 3
    assert cm.RecordMapper(M.cm.fake_pair({}, M.view_of(F), None), ChoiceLedger(None)).max_asks == 24


def test_g9_16b_the_protocol_name_is_in_the_output_and_the_ledger():
    res, mp = ask_map(F, Q, YN, GOOD)
    assert res["mapping"]["protocol"] == cm.PROTOCOL == "conduct_map/v2"
    assert all(tuple(k for k in ("protocol",) if k in e) == () for e in asks(mp))                  # a row names its step; the key of a decision names the protocol
    assert all(json.loads(d["key"])["protocol"] == "conduct_map/v2" for d in decisions(mp))
