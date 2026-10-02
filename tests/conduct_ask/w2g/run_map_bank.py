"""Measure ``python -m verantyx.conduct_ask`` with the record mapping on the paraphrased self-made fixtures (not a test).

  run_map_bank.py --mode off|fake|codex [--second codex|claude] [--subset IDFILE] --out DIR
                  [--items ITEMS] [--frames DIR] [--ledger PATH] [--workers 4] [--run-budget N] [--total-budget 1300]
                  [--map-max-asks 8] [--timeout SEC]
  run_map_bank.py --recount DIR        rebuild summary.json from results.jsonl and ledger.jsonl and compare

Every question is one CLI call (the same path a user takes): off uses artifacts/w2-g/py.sh, the real providers use
artifacts/w2-g/py_live.sh (claude is not on the restricted PATH of py.sh).  Judging and the base summary are the ones of
tests/conduct_ask/run_bank.py.  ``--mode fake`` is a pipeline check only: it scripts an oracle that answers what the fixture
expects (an assumption about a model, not a measurement of one).

Before a real run the worst case (questions x 10 asks) plus the asks already in every ledger under artifacts/w2-g/live/ must
fit ``--total-budget``, and the worst case must fit ``--run-budget`` when it is given; otherwise nothing is started.
A claude second provider that returns LIMIT_REACHED for 3 questions in a row stops the run (``aborted: CLAUDE_LIMIT``).
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

ASKS_PER_QUESTION_WORST = 10        # word choice 2 + step 1 2 + step 2 2 x 3 records (the configured caps)
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


def existing_asks(live_root: Path) -> int:
    return sum(len(provider_asks(ledger_rows(p))) for p in live_root.glob("**/ledger.jsonl"))


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
    return {"route": m.get("route"), "outcome": m.get("outcome"), "asks_used": m.get("asks_used"),
            "exit_check": m.get("exit_check"), "rule": {k: (m.get("rule") or {}).get(k) for k in ("decision", "reason", "detail")},
            "step1_status": s1.get("status"), "step1_records": s1.get("records"), "step1_decides": s1.get("decides"),
            "step2_status": [s.get("status") for s in m.get("step2") or []],
            "order_status": ((m.get("order") or {}).get("phases") or {}).get("status"),
            "order_picked": (m.get("order") or {}).get("picked"), "order_relation": (m.get("order") or {}).get("relation")}


def make_row(item: dict, res: dict, split: str) -> dict:
    row = run_bank.row_for(item, res, split)
    row["records_expected"] = item["expect"].get("records") or []
    row["question"] = item["question"]
    row["options"] = item.get("options")
    row["mapping"] = compact_mapping(res)
    row["elapsed_s"] = res.get("_elapsed_s")
    return row


def claude_limit(res: dict, ledger_before: int, ledger: Path) -> bool:
    """Did this question hit the claude usage limit?  (Read from the result's mapping asks.)"""
    m = res.get("mapping") or {}
    steps = [m.get("step1") or {}, (m.get("order") or {}).get("phases") or {}] + list(m.get("step2") or [])
    return any(a.get("provider") == "claude" and a.get("failure") == "LIMIT_REACHED" for s in steps for a in s.get("asks") or [])


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
    }


def run(args: argparse.Namespace) -> int:
    items_path, frames, out = Path(args.items), Path(args.frames), Path(args.out)
    items = load_items(items_path, Path(args.subset) if args.subset else None)
    held = run_bank.holdout_ids(items_path)
    if args.mode == "codex":                 # only the real providers use up the budget (fake is the made-up oracle: no provider is called)
        worst = len(items) * ASKS_PER_QUESTION_WORST
        used = existing_asks(ROOT / "artifacts" / "w2-g" / "live")
        if used + worst > args.total_budget:
            print(f"REFUSED: {used} asks already + worst case {worst} > total budget {args.total_budget}; nothing was started")
            return 3
        if args.run_budget is not None and worst > args.run_budget:
            print(f"REFUSED: worst case {worst} > run budget {args.run_budget}; nothing was started")
            return 3
    out.mkdir(parents=True, exist_ok=True)
    if args.mode != "off" and not args.ledger:
        args.ledger = str(out / "ledger.jsonl")
    ledger = Path(args.ledger) if args.ledger else out / "ledger.jsonl"
    todo = [(it, "holdout" if it["frame_id"] in held else "dev") for it in items]
    lock = threading.Lock()
    state = {"streak": 0, "abort": False}
    results: dict[str, dict] = {}

    def work(pair: tuple[dict, str]) -> None:
        it, _ = pair
        with lock:
            if state["abort"]:
                return
        res = run_one(it, frames, args, out)
        with lock:
            results[it["id"]] = res
            if args.second == "claude" and args.mode == "codex":
                state["streak"] = state["streak"] + 1 if claude_limit(res, 0, ledger) else 0
                if state["streak"] >= 3:
                    state["abort"] = True

    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        list(ex.map(work, todo))
    wall = round(time.monotonic() - t0, 2)
    ran = [(it, sp) for it, sp in todo if it["id"] in results]
    rows = [make_row(it, results[it["id"]], sp) for it, sp in ran]
    with (out / "results.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    summary = run_bank.summarize(rows)
    config = {"mode": args.mode, "second": args.second if args.mode == "codex" else None, "map_max_asks": args.map_max_asks,
              "providers": {"codex": "gpt-6-luna / effort low", "claude": "claude-sonnet-5-5 / effort low"},
              "workers": args.workers, "subset": args.subset, "wall_s": wall,
              "fake_is_an_oracle_assumption": args.mode == "fake"}
    summary.update(extras(rows, ledger, config))
    summary["config"] = config
    summary["aborted"] = "CLAUDE_LIMIT" if state["abort"] else None
    summary["not_run"] = [it["id"] for it, _ in todo if it["id"] not in results]
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("total", "false_answer", "wrong_answer", "q1_rate", "q2_answer_rate",
                                              "escalate_correct_rate")} | {"asks": summary["asks"]["total"], "aborted": summary["aborted"]},
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
    ap.add_argument("--map-max-asks", type=int, default=8)
    ap.add_argument("--timeout", type=float, default=1500.0)
    ap.add_argument("--recount")
    args = ap.parse_args(argv)
    if args.recount:
        return recount(args.recount)
    if not args.out:
        ap.error("--out is required")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
