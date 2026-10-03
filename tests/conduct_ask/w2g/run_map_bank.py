"""Measure ``python -m verantyx.conduct_ask`` with the record mapping on the paraphrased self-made fixtures (not a test).

  run_map_bank.py --mode off|fake|codex [--second codex|claude] [--subset IDFILE] --out DIR
                  [--items ITEMS] [--frames DIR] [--ledger PATH] [--workers 4] [--run-budget N] [--total-budget 1300]
                  [--budget-root DIR] [--map-max-asks 24] [--map-effort low|medium|high|xhigh] [--map-timeout SEC] [--timeout SEC]
  run_map_bank.py --recount DIR        rebuild summary.json from results.jsonl and ledger.jsonl and compare

Every question is one CLI call (the same path a user takes): off uses artifacts/w2-g/py.sh, the real providers use
artifacts/w2-g/py_live.sh (claude is not on the restricted PATH of py.sh).  Judging and the base summary are the ones of
tests/conduct_ask/run_bank.py.  ``--mode fake`` is a pipeline check only: it scripts an oracle that answers what the fixture
expects (an assumption about a model, not a measurement of one).

Budget (real providers): a question is *reserved* before it starts.  Its worst case is ``WORST = 2 (the word choice) +
--map-max-asks``.  The reservation fits when  asks already in every ledger under ``--budget-root`` (default
artifacts/w2-g/live)  +  asks lost to questions that were killed by ``--timeout`` (WORST each)  +  WORST of every running question
+  WORST of this one  <=  ``--total-budget``, and (when ``--run-budget`` is given) the same count over this run's own ledger
<= ``--run-budget``.  Questions are started strictly in file order; the first one that does not fit (nothing else running to wait
for) and every question after it are not run and are listed in ``summary.not_run_budget`` (no question is picked over another).
A second provider that returns LIMIT_REACHED for 3 questions in a row stops the run (``aborted: CLAUDE_LIMIT`` /
``CODEX_LIMIT``, the second provider's name).  ``--map-effort`` and ``--map-timeout`` are passed to the entry as they are; the
summary's ``g2`` block (conduct_map/v2) holds the per-step asks, the invalid rates, the retries and the timings.
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "conduct_ask"))
import run_bank  # noqa: E402  (judge / summarize of the W2-c fixtures)

ASKS_PER_QUESTION_WORST = 10        # round 1 to 3 (conduct_map/v1): word choice 2 + step 1 2 + step 2 2 x 3 records (kept for the saved runs)
WORD_CHOICE_WORST = 2               # the word choice (llm_choice) asks at most twice for one question (a configured limit, not a measurement)
EXTRA_KEYS = ("asks", "elapsed", "escalations", "mapping_outcomes", "exit_check_escalations", "step1_record_match",
              "answered_by_route", "wrong_or_false_ids")


def load_items(path: Path, subset: Optional[Path]) -> list[dict]:
    items = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if subset is not None:
        keep = [ln.strip() for ln in subset.read_text(encoding="utf-8").splitlines() if ln.strip()]
        items = [i for i in items if i["id"] in set(keep)]
    return items


def ledger_rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def provider_asks(rows: list[dict]) -> list[dict]:
    """The ledger rows that invoked a provider: map_ask rows and word-choice ask rows (not the skipped ones)."""
    return [r for r in rows if r.get("type") in ("map_ask", "ask") and r.get("verdict") != "SKIPPED_DECIDED"]


def _rows_tolerant(path: Path) -> list[dict]:
    """The rows of a ledger that may be appended to right now: a last line that is not complete yet is skipped."""
    out: list[dict] = []
    if not path.is_file():
        return out
    for ln in path.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out


def existing_asks(live_root: Path) -> int:
    return sum(len(provider_asks(_rows_tolerant(p))) for p in live_root.glob("**/ledger.jsonl"))


def worst_per_question(map_max_asks: int) -> int:
    """The most provider asks one question can make: the word choice and the record mapping's cap (a second ask counts)."""
    return WORD_CHOICE_WORST + map_max_asks


class Reservation:
    """Starts the questions in file order and holds back every question whose worst case no longer fits the budget."""

    def __init__(self, root: Path, total: int, worst: int, run_ledger: Path, run_total: Optional[int]):
        self.cond = threading.Condition()
        self.root, self.total, self.worst, self.run_ledger, self.run_total = root, total, worst, run_ledger, run_total
        self.running, self.lost, self.next, self.stopped = 0, 0, 0, False

    def fits(self) -> bool:
        used = existing_asks(self.root) + self.lost + (self.running + 1) * self.worst
        if used > self.total:
            return False
        if self.run_total is not None:
            mine = len(provider_asks(_rows_tolerant(self.run_ledger))) + self.lost + (self.running + 1) * self.worst
            if mine > self.run_total:
                return False
        return True

    def acquire(self, index: int) -> bool:
        """Block until it is question ``index``'s turn; True when its worst case is reserved, False when it must not run."""
        with self.cond:
            while self.next != index:
                self.cond.wait(timeout=5)
            try:
                while True:
                    if self.stopped:
                        return False
                    if self.fits():
                        self.running += 1
                        return True
                    if self.running == 0:
                        self.stopped = True
                        return False
                    self.cond.wait(timeout=5)
            finally:
                self.next += 1
                self.cond.notify_all()

    def release(self, timed_out: bool) -> None:
        with self.cond:
            self.running -= 1
            if timed_out:
                self.lost += self.worst             # the child was killed: the asks it had in flight are not in its ledger
            self.cond.notify_all()


def _order_oracle(recs: list, idx: Optional[int], n: int, escalate: bool) -> Optional[dict]:
    """The oracle of an order question: the whole order family is the record, the phases are the ends of the expected edges
    (sources and sinks of the edge set) and the statement they give is the derived one (a made-up reading, not a measurement)."""
    if not recs or not all(str(r).startswith("phase_order:") for r in recs):
        return None
    edges = [tuple(str(r).split(":", 1)[1].split("->")) for r in recs]
    before = {a for a, _ in edges}
    after = {b for _, b in edges}
    named = sorted((before - after) | (after - before)) or sorted(before | after)
    sinks = sorted(after - before)
    sources = sorted(before - after)
    claim = "order:" + "+".join(sources) + "<" + sinks[0] if len(sinks) == 1 and sources else None
    decides = "決まる" if not escalate else "決まらない"
    script: dict[str, Any] = {"records": ["order:ALL"], "decides": decides, "decides_phases": decides, "phases": named}
    if claim and n:
        script["relations"] = {claim: ["一致" if i == idx else "矛盾" for i in range(n)]}
    return script


def oracle_script(item: dict) -> dict:
    exp = item["expect"]
    recs = list(exp.get("records") or [])
    n = len(item.get("options") or [])
    order = _order_oracle(recs, exp.get("answer_option_index"), n, exp["decision"] != "answer")
    if order is not None:
        return order
    script: dict[str, Any] = {"records": recs, "decides": "決まる" if exp["decision"] == "answer" else "決まらない"}
    if recs and item.get("options"):
        idx = exp.get("answer_option_index")
        script["relations"] = {r: ["一致" if i == idx else "矛盾" for i in range(len(item["options"]))] for r in recs}
    return script


def run_one(item: dict, frames: Path, args: argparse.Namespace, out: Path) -> dict:
    frame = frames / f"{item['frame_id']}.md"
    argv = ["-m", "verantyx.conduct_ask", "--frame", str(frame), "--question", item["question"]]
    for o in item.get("options") or []:
        argv += ["--option", o]
    wrapper = ROOT / "artifacts" / "w2-g" / ("py.sh" if args.mode == "off" else "py_live.sh")
    if args.mode != "off":
        argv += ["--vocab-llm", "codex" if args.mode == "codex" else "fake", "--vocab-ledger", str(Path(args.ledger))]
        argv += ["--map-max-asks", str(args.map_max_asks)]
        if args.mode == "codex":
            argv += ["--map-second", args.second]
            if args.map_effort is not None:
                argv += ["--map-effort", args.map_effort]
            if args.map_timeout is not None:
                argv += ["--map-timeout", str(args.map_timeout)]
        else:
            d = out / "fake_scripts"
            d.mkdir(parents=True, exist_ok=True)
            p = d / f"{item['id']}.json"
            p.write_text(json.dumps(oracle_script(item), ensure_ascii=False) + "\n", encoding="utf-8")
            argv += ["--map-fake", str(p)]
    t0 = time.monotonic()
    try:
        proc = subprocess.run([str(wrapper), *argv], capture_output=True, text=True, cwd=str(ROOT), timeout=args.timeout)
        try:
            res = json.loads(proc.stdout)
        except ValueError:
            res = {"decision": "escalate", "escalate_reason": "INTERNAL_ERROR", "escalate_detail": "UNPARSEABLE_STDOUT"}
        res["_exit"] = proc.returncode
    except subprocess.TimeoutExpired:
        res = {"decision": "escalate", "escalate_reason": "INTERNAL_ERROR", "escalate_detail": "RUN_TIMEOUT", "_exit": None}
    res["_elapsed_s"] = round(time.monotonic() - t0, 2)
    return res


def compact_mapping(res: dict) -> Optional[dict]:
    m = res.get("mapping")
    if not m:
        return None
    s1 = m.get("step1") or {}
    dec = m.get("decides") or {}
    out = {"route": m.get("route"), "outcome": m.get("outcome"), "asks_used": m.get("asks_used"),
           "exit_check": m.get("exit_check"), "rule": {k: (m.get("rule") or {}).get(k) for k in ("decision", "reason", "detail")},
           "step1_status": s1.get("status"), "step1_records": s1.get("records"),
           # round 1 to 3 (v1) carried decides in step 1; v2 asks it on its own (``decides``)
           "step1_decides": s1.get("decides") if "decides" in s1 else dec.get("decides"),
           "step2_status": [s.get("status") for s in m.get("step2") or []],
           "order_status": ((m.get("order") or {}).get("phases") or {}).get("status"),
           "order_picked": (m.get("order") or {}).get("picked"), "order_relation": (m.get("order") or {}).get("relation")}
    if m.get("protocol"):
        order = m.get("order") or {}
        out.update({"protocol": m.get("protocol"), "effort": m.get("effort"), "retries": m.get("retries"),
                    "decides_status": dec.get("status") if dec else None,
                    "step2_relation": [s.get("relation") for s in m.get("step2") or []],
                    "order_decides": order.get("decides"),
                    "order_decides_status": (order.get("decides_step") or {}).get("status")})
    return out


def make_row(item: dict, res: dict, split: str) -> dict:
    row = run_bank.row_for(item, res, split)
    row["records_expected"] = item["expect"].get("records") or []
    row["question"] = item["question"]
    row["options"] = item.get("options")
    row["mapping"] = compact_mapping(res)
    row["elapsed_s"] = res.get("_elapsed_s")
    return row


def provider_limit(res: dict, provider: str) -> bool:
    """Did this question hit the usage limit of ``provider``?  (Read from the result's mapping asks, every step of both routes.)"""
    m = res.get("mapping") or {}
    order = m.get("order") or {}
    steps = [m.get("step1") or {}, m.get("decides") or {}, order.get("phases") or {}, order.get("decides_step") or {}] + list(m.get("step2") or [])
    return any(a.get("provider") == provider and a.get("failure") == "LIMIT_REACHED" for s in steps for a in s.get("asks") or [])


def claude_limit(res: dict, ledger_before: int, ledger: Path) -> bool:
    """Round 1 to 3 name of ``provider_limit(res, "claude")``."""
    return provider_limit(res, "claude")


def _stats(values: list) -> Optional[dict]:
    """mean / median / 90th percentile (nearest rank) / max of a list of numbers, None for no value."""
    if not values:
        return None
    v = sorted(values)
    rank = max(1, -(-len(v) * 90 // 100))              # ceil(0.9 n)
    return {"n": len(v), "mean": round(sum(v) / len(v), 1), "median": round(statistics.median(v), 1), "p90": v[rank - 1], "max": v[-1]}


def g2_block(rows: list[dict], ledger: Path, config: dict) -> dict[str, Any]:
    """The aggregates of conduct_map/v2 (a new key: the aggregates of round 1 to 3 are not touched)."""
    led = ledger_rows(ledger)
    mapped = [r for r in led if r.get("type") == "map_ask"]
    word = [r for r in led if r.get("type") == "ask" and r.get("verdict") != "SKIPPED_DECIDED"]
    verdicts: dict[str, dict[str, int]] = {}
    by_step_ms: dict[str, list] = {}
    reasons: dict[str, int] = {}
    for r in mapped:
        st = verdicts.setdefault(str(r.get("step")), {})
        st[str(r.get("verdict"))] = st.get(str(r.get("verdict")), 0) + 1
        if r.get("verdict") == "INVALID":
            reasons[str(r.get("invalid_reason"))] = reasons.get(str(r.get("invalid_reason")), 0) + 1
        if isinstance(r.get("elapsed_ms"), int):
            by_step_ms.setdefault(str(r.get("step")), []).append(r["elapsed_ms"])
    inv_map = sum(1 for r in mapped if r.get("verdict") == "INVALID")
    inv_all = inv_map + sum(1 for r in word if r.get("verdict") == "INVALID")
    all_ms = [x for v in by_step_ms.values() for x in v]
    retry_rows = [r for r in mapped if r.get("attempt") == 1]
    retry_valid = sum(1 for r in retry_rows if r.get("verdict") in ("PICK", "NONE"))
    dec: dict[str, dict[str, int]] = {}
    for d in led:
        if d.get("type") == "map_decision":
            st = dec.setdefault(str(d.get("step")), {})
            st[str(d.get("status"))] = st.get(str(d.get("status")), 0) + 1
    decides = {"adopted": {}, "not_adopted": {}}
    for d in led:
        if d.get("type") == "map_decision" and d.get("step") == "decides":
            if d.get("status") == "ADOPTED":
                k = str((d.get("result") or {}).get("decides"))
                decides["adopted"][k] = decides["adopted"].get(k, 0) + 1
            else:
                decides["not_adopted"][str(d.get("status"))] = decides["not_adopted"].get(str(d.get("status")), 0) + 1
    maps = [r["mapping"] for r in rows if r.get("mapping") and r["mapping"].get("asks_used") is not None]
    per_q = [m["asks_used"] for m in maps]
    reason_all: dict[str, int] = {}
    reason_answer_expected: dict[str, int] = {}
    for r in rows:
        o = r["observed"]
        if o["decision"] == "escalate":
            reason_all[str(o["reason"])] = reason_all.get(str(o["reason"]), 0) + 1
            if r["expect"]["decision"] == "answer":
                reason_answer_expected[str(o["reason"])] = reason_answer_expected.get(str(o["reason"]), 0) + 1
    cap = config.get("map_max_asks")
    all_asks = len(mapped) + len(word)
    return {
        "protocol": "conduct_map/v2",
        "map_asks_by_step": {k: sum(v.values()) for k, v in sorted(verdicts.items())},
        "map_verdict_by_step": {k: dict(sorted(v.items())) for k, v in sorted(verdicts.items())},
        "invalid_reasons": dict(sorted(reasons.items())),
        "invalid_rate_mapping_asks": {"invalid": inv_map, "rows": len(mapped), "rate": round(inv_map / len(mapped), 4) if mapped else None},
        "invalid_rate_all_asks": {"invalid": inv_all, "rows": all_asks, "rate": round(inv_all / all_asks, 4) if all_asks else None},
        "retries": {"asks": len(retry_rows), "valid_reply": retry_valid,
                    "decisions_with_retry": len({r["decision_id"] for r in retry_rows})},
        "decision_status_by_step": {k: dict(sorted(v.items())) for k, v in sorted(dec.items())},
        "decides_distribution": {k: dict(sorted(v.items())) for k, v in decides.items()},
        "ask_elapsed_ms": {"all_map_asks": _stats(all_ms), "by_step": {k: _stats(v) for k, v in sorted(by_step_ms.items())},
                           "word_choice_asks_have_no_elapsed_field": True},
        "map_asks_per_question": _stats(per_q),
        "all_asks_per_question_mean": round(all_asks / len(rows), 2) if rows else None,
        "questions_over_map_cap": sum(1 for x in per_q if cap is not None and x > cap),
        "escalation_reasons": dict(sorted(reason_all.items())),
        "escalation_reasons_where_answer_expected": dict(sorted(reason_answer_expected.items())),
    }


def extras(rows: list[dict], ledger: Path, config: dict) -> dict[str, Any]:
    asks = provider_asks(ledger_rows(ledger))
    by_provider: dict[str, int] = {}
    by_step: dict[str, int] = {}
    by_failure: dict[str, int] = {}
    by_verdict: dict[str, int] = {}
    for a in asks:
        by_provider[str(a.get("provider"))] = by_provider.get(str(a.get("provider")), 0) + 1
        step = a.get("step") or "word_choice"
        by_step[step] = by_step.get(step, 0) + 1
        by_verdict[str(a.get("verdict"))] = by_verdict.get(str(a.get("verdict")), 0) + 1
        if a.get("failure"):
            by_failure[str(a["failure"])] = by_failure.get(str(a["failure"]), 0) + 1
    times = [r["elapsed_s"] for r in rows if r.get("elapsed_s") is not None]
    esc: dict[str, int] = {}
    esc_expected_answer: dict[str, int] = {}
    outcomes: dict[str, int] = {}
    routes: dict[str, dict] = {}
    for r in rows:
        o = r["observed"]
        if o["decision"] == "escalate":
            k = f"{o['reason']}/{o['detail']}"
            esc[k] = esc.get(k, 0) + 1
            if r["expect"]["decision"] == "answer":
                esc_expected_answer[k] = esc_expected_answer.get(k, 0) + 1
        m = r.get("mapping")
        if m:
            key = str(m["outcome"]).split("/")[0] if str(m["outcome"]).startswith("ESCALATED") else str(m["outcome"])
            outcomes[str(m["outcome"])] = outcomes.get(str(m["outcome"]), 0) + 1
            rt = routes.setdefault(str(m["route"]), {"n": 0, "answered": 0, "correct": 0, "wrong": 0})
            rt["n"] += 1
            if o["decision"] == "answer":
                rt["answered"] += 1
                if r["verdict"] == "correct":
                    rt["correct"] += 1
                if r["verdict"] in ("false_answer", "wrong_answer"):
                    rt["wrong"] += 1
    s1 = [r for r in rows if (r.get("mapping") or {}).get("step1_status") == "ADOPTED"]
    def same_set(r: dict) -> bool:
        got = set(r["mapping"]["step1_records"] or [])
        want = set(r["records_expected"])
        # the whole order family stands for the order edges (the single edges are not shown to the model any more)
        return got == want or (got == {"order:ALL"} and bool(want) and all(str(x).startswith("phase_order:") for x in want))
    match = sum(1 for r in s1 if same_set(r))
    order_rows = [r for r in rows if (r.get("mapping") or {}).get("order_status") is not None]
    order = {"attempted": len(order_rows), "phases_adopted": sum(1 for r in order_rows if r["mapping"]["order_status"] == "ADOPTED"),
             "answered": sum(1 for r in order_rows if r["observed"]["decision"] == "answer"),
             "answered_correct": sum(1 for r in order_rows if r["verdict"] == "correct")}
    s1_all = [r for r in rows if (r.get("mapping") or {}).get("step1_status") is not None]
    return {
        "asks": {"total": len(asks), "by_provider": dict(sorted(by_provider.items())), "by_step": dict(sorted(by_step.items())),
                 "by_verdict": dict(sorted(by_verdict.items())), "failures": dict(sorted(by_failure.items()))},
        "elapsed": {"sum_of_question_seconds": round(sum(times), 2), "median_s": round(statistics.median(times), 2) if times else None,
                    "max_s": max(times) if times else None, "wall_s": config.get("wall_s")},
        "escalations": dict(sorted(esc.items())),
        "escalations_where_answer_expected": dict(sorted(esc_expected_answer.items())),
        "mapping_outcomes": dict(sorted(outcomes.items())),
        "exit_check_escalations": sum(1 for r in rows if (r.get("mapping") or {}).get("exit_check")),
        "step1_record_match": {"step1_adopted": len(s1), "same_set_as_expected": match,
                               "rate": round(match / len(s1), 4) if s1 else None, "questions_with_step1": len(s1_all)},
        "answered_by_route": dict(sorted(routes.items())),
        "order_route": order,
        "wrong_or_false_ids": [r["id"] for r in rows if r["verdict"] in ("false_answer", "wrong_answer")],
        "g2": g2_block(rows, ledger, config),
    }


def run(args: argparse.Namespace) -> int:
    items_path, frames, out = Path(args.items), Path(args.frames), Path(args.out)
    items = load_items(items_path, Path(args.subset) if args.subset else None)
    held = run_bank.holdout_ids(items_path)
    worst = worst_per_question(args.map_max_asks)
    budget_root = Path(args.budget_root).resolve() if args.budget_root else ROOT / "artifacts" / "w2-g" / "live"
    if args.mode == "codex":                 # only the real providers use up the budget (fake is the made-up oracle: no provider is called)
        if worst > args.total_budget or (args.run_budget is not None and worst > args.run_budget):
            print(f"REFUSED: the worst case of one question ({worst}) does not fit the budget; nothing was started")
            return 3
    out.mkdir(parents=True, exist_ok=True)
    if args.mode != "off" and not args.ledger:
        args.ledger = str(out / "ledger.jsonl")
    ledger = Path(args.ledger) if args.ledger else out / "ledger.jsonl"
    todo = [(it, "holdout" if it["frame_id"] in held else "dev") for it in items]
    lock = threading.Lock()
    state = {"streak": 0, "abort": False}
    results: dict[str, dict] = {}
    skipped_budget: list[str] = []
    reservation = (Reservation(budget_root, args.total_budget, worst, ledger, args.run_budget)
                   if args.mode == "codex" else None)

    def work(indexed: tuple[int, tuple[dict, str]]) -> None:
        idx, pair = indexed
        it, _ = pair
        held_slot = False
        if reservation is not None:
            held_slot = reservation.acquire(idx)         # blocks until it is this question's turn (file order)
            if not held_slot:
                with lock:
                    skipped_budget.append(it["id"])
                return
        timed_out = False
        try:
            with lock:
                if state["abort"]:
                    return
            res = run_one(it, frames, args, out)
            timed_out = res.get("escalate_detail") == "RUN_TIMEOUT"
            with lock:
                results[it["id"]] = res
                if args.mode == "codex":
                    state["streak"] = state["streak"] + 1 if provider_limit(res, args.second) else 0
                    if state["streak"] >= 3:
                        state["abort"] = True
        finally:
            if reservation is not None and held_slot:
                reservation.release(timed_out)

    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        list(ex.map(work, list(enumerate(todo))))
    wall = round(time.monotonic() - t0, 2)
    ran = [(it, sp) for it, sp in todo if it["id"] in results]
    rows = [make_row(it, results[it["id"]], sp) for it, sp in ran]
    with (out / "results.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    summary = run_bank.summarize(rows)
    efforts = {"codex": args.map_effort or "low", "claude": args.map_effort or "low"}
    config = {"mode": args.mode, "second": args.second if args.mode == "codex" else None, "map_max_asks": args.map_max_asks,
              "providers": {"codex": f"gpt-6-luna / effort {efforts['codex']}", "claude": f"claude-sonnet-5-5 / effort {efforts['claude']}"},
              "map_effort": args.map_effort, "map_timeout": args.map_timeout, "question_timeout_s": args.timeout,
              "budget": {"root": str(budget_root.relative_to(ROOT)) if budget_root.is_relative_to(ROOT) else str(budget_root),
                         "total": args.total_budget, "run": args.run_budget, "worst_per_question": worst},
              "workers": args.workers, "subset": args.subset, "wall_s": wall,
              "fake_is_an_oracle_assumption": args.mode == "fake"}
    summary.update(extras(rows, ledger, config))
    summary["config"] = config
    summary["aborted"] = f"{args.second.upper()}_LIMIT" if state["abort"] else None
    summary["not_run"] = [it["id"] for it, _ in todo if it["id"] not in results and it["id"] not in skipped_budget]
    summary["not_run_budget"] = [it["id"] for it, _ in todo if it["id"] in skipped_budget]
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("total", "false_answer", "wrong_answer", "q1_rate", "q2_answer_rate",
                                              "escalate_correct_rate")} | {"asks": summary["asks"]["total"], "aborted": summary["aborted"],
                                                                           "not_run_budget": len(summary["not_run_budget"])},
                     ensure_ascii=False))
    return 0


def recount(dirpath: str) -> int:
    d = Path(dirpath)
    rows = [json.loads(ln) for ln in (d / "results.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    fresh = []
    for r in rows:
        item = {"expect": {"decision": r["expect"]["decision"], "answer_option_index": r["expect"]["answer_option_index"],
                           "answer": r["expect"]["answer"]},
                "options": r["expect"]["answer_option_index"] is not None, "w2c": r["w2c"]}
        verdict, reason_match = run_bank.judge(item, {"decision": r["observed"]["decision"],
                                                      "answer_option_index": r["observed"]["answer_option_index"],
                                                      "answer": r["observed"]["answer"], "escalate_reason": r["observed"]["reason"]})
        fresh.append({**r, "verdict": verdict, "reason_match": reason_match})
    old = json.loads((d / "summary.json").read_text(encoding="utf-8"))
    new = run_bank.summarize(fresh)
    new.update(extras(fresh, d / "ledger.jsonl", old.get("config", {})))
    new["config"], new["aborted"], new["not_run"] = old.get("config"), old.get("aborted"), old.get("not_run")
    if "not_run_budget" in old:
        new["not_run_budget"] = old["not_run_budget"]
    # a summary saved by an earlier version of this runner has fewer aggregate keys (e.g. ``order_route``, added in round 2): compare the
    # keys the saved summary has, and say which new keys were not compared
    ignored = sorted(k for k in new if k not in old)
    for k in ignored:
        del new[k]
    a, b = json.dumps(new, sort_keys=True, ensure_ascii=False), json.dumps(old, sort_keys=True, ensure_ascii=False)
    print(f"{d}: {'MATCH' if a == b else 'MISMATCH'} rows={len(rows)} q1_wrong={new['q1_wrong_count']} q2_answer_rate={new['q2_answer_rate']} "
          f"escalate_correct_rate={new['escalate_correct_rate']} asks={new['asks']['total']}" + (f" (not compared, absent in the saved summary: {ignored})" if ignored else ""))
    if a != b:
        for k in sorted(set(new) | set(old)):
            if json.dumps(new.get(k), sort_keys=True) != json.dumps(old.get(k), sort_keys=True):
                print("  differs:", k)
    return 0 if a == b else 1


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default=str(HERE / "items.jsonl"))
    ap.add_argument("--frames", default=str(HERE / "frames"))
    ap.add_argument("--mode", choices=("off", "fake", "codex"), default="off")
    ap.add_argument("--second", choices=("codex", "claude"), default="codex")
    ap.add_argument("--subset")
    ap.add_argument("--out")
    ap.add_argument("--ledger")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--run-budget", type=int)
    ap.add_argument("--total-budget", type=int, default=1300)
    ap.add_argument("--map-max-asks", type=int, default=24)
    ap.add_argument("--map-effort", choices=("low", "medium", "high", "xhigh"), default=None,
                    help="passed to the entry (codex mode only); default: the entry's own (low)")
    ap.add_argument("--map-timeout", type=float, default=None, help="seconds of one record-mapping ask, passed to the entry (codex mode only)")
    ap.add_argument("--budget-root", default=None,
                    help="directory whose ledgers count against --total-budget (default artifacts/w2-g/live; a run of conduct_map/v2 uses artifacts/w2-g/live_g2)")
    ap.add_argument("--timeout", type=float, default=1500.0, help="seconds one question (one entry call) may take")
    ap.add_argument("--recount")
    args = ap.parse_args(argv)
    if args.recount:
        return recount(args.recount)
    if not args.out:
        ap.error("--out is required")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
