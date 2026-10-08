"""Measure ``verantyx.conduct_ask`` on the self-made fixtures (not a test: the file name does not start with test_).

  run_bank.py --items ITEMS --frames DIR --vocab-llm off|fake --split dev|holdout|all --out DIR [--subprocess]
  run_bank.py --recount DIR        rebuild summary.json from results.jsonl and compare with the stored one

Judgement follows the B5 scorer of tools/bank_score:
  expected escalate, observed answer          -> false_answer
  expected answer,   observed another answer  -> wrong_answer
  expected answer,   observed the same        -> correct
  expected answer,   observed escalate        -> over_escalate
  expected escalate, observed escalate        -> correct_escalate (and whether the reason type matches)

With --vocab-llm fake, every question gets its own script file under <out>/fake_scripts/<id>.json:
{"pick": <the frame term the item names as nearest>} for an out-of-vocabulary item, else {"pick": null}.
That is an assumption (an LLM that always names the intended nearest term), not a measurement of an LLM.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def norm(s: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(s or "")).casefold().split())


def holdout_ids(items_path: Path) -> set[str]:
    p = items_path.parent / "holdout.txt"
    return {ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()} if p.is_file() else set()


def judge(item: dict, obs: dict) -> tuple[str, Optional[bool]]:
    exp = item["expect"]
    w = item["w2c"]
    if exp["decision"] == "escalate":
        if obs["decision"] == "answer":
            return "false_answer", None
        return "correct_escalate", obs.get("escalate_reason") == w.get("escalate_reason")
    if obs["decision"] != "answer":
        return "over_escalate", None
    if item.get("options"):
        ok = obs.get("answer_option_index") == exp["answer_option_index"]
    else:
        ok = norm(obs.get("answer")) == norm(exp.get("answer")) and norm(obs.get("answer")) != ""
    return ("correct" if ok else "wrong_answer"), None


def frac(n: int, d: int) -> Optional[float]:
    return round(n / d, 4) if d else None


def metrics(rows: list[dict]) -> dict[str, Any]:
    total = len(rows)
    c = {k: sum(1 for r in rows if r["verdict"] == k)
         for k in ("false_answer", "wrong_answer", "correct", "over_escalate", "correct_escalate")}
    ans_exp = [r for r in rows if r["expect"]["decision"] == "answer"]
    esc_exp = [r for r in rows if r["expect"]["decision"] == "escalate"]
    rt = [r for r in esc_exp if r["verdict"] == "correct_escalate"]
    by_cat: dict[str, Any] = {}
    for cat in ("direct", "combined", "oov"):
        sub = [r for r in ans_exp if r["w2c"]["category"] == cat]
        by_cat[cat] = {"n": len(sub), "correct": sum(1 for r in sub if r["verdict"] == "correct"),
                       "rate": frac(sum(1 for r in sub if r["verdict"] == "correct"), len(sub))}
    return {
        "total": total, **c,
        "q1_wrong_count": c["false_answer"] + c["wrong_answer"],
        "q1_rate": frac(c["false_answer"] + c["wrong_answer"], total),
        "answer_expected": len(ans_exp), "q2_answer_rate": frac(c["correct"], len(ans_exp)),
        "q2_by_category": by_cat,
        "escalate_expected": len(esc_exp), "escalate_correct": len(rt),
        "escalate_correct_rate": frac(len(rt), len(esc_exp)),
        "reason_type_match": sum(1 for r in rt if r["reason_match"]),
        "reason_type_match_rate": frac(sum(1 for r in rt if r["reason_match"]), len(rt)),
    }


def summarize(rows: list[dict]) -> dict[str, Any]:
    s = metrics(rows)
    s["by_split"] = {sp: metrics([r for r in rows if r["split"] == sp]) for sp in ("dev", "holdout") if any(r["split"] == sp for r in rows)}
    s["by_lang"] = {lg: metrics([r for r in rows if r["lang"] == lg]) for lg in ("ja", "en") if any(r["lang"] == lg for r in rows)}
    s["by_permission"] = {}
    for lab in ("可", "不可", "上げる"):
        sub = [r for r in rows if r["w2c"].get("permission") == lab]
        s["by_permission"][lab] = {"n": len(sub), "correct": sum(1 for r in sub if r["verdict"] in ("correct", "correct_escalate")),
                                   "false_or_wrong": sum(1 for r in sub if r["verdict"] in ("false_answer", "wrong_answer")),
                                   "over_escalate": sum(1 for r in sub if r["verdict"] == "over_escalate")}
    traps = [r for r in rows if r["w2c"].get("trap")]
    s["trap"] = {"n": len(traps), "correct_escalate": sum(1 for r in traps if r["verdict"] == "correct_escalate"),
                 "false_answer": sum(1 for r in traps if r["verdict"] == "false_answer")}
    none = [r for r in rows if r["w2c"].get("oov_none")]
    s["oov_none"] = {"n": len(none), "correct_escalate": sum(1 for r in none if r["verdict"] == "correct_escalate"),
                     "false_answer": sum(1 for r in none if r["verdict"] == "false_answer")}
    reasons: dict[str, Any] = {}
    for r in rows:
        if r["expect"]["decision"] == "escalate":
            rr = r["w2c"].get("escalate_reason")
            d = reasons.setdefault(rr, {"n": 0, "correct_escalate": 0, "reason_match": 0})
            d["n"] += 1
            d["correct_escalate"] += r["verdict"] == "correct_escalate"
            d["reason_match"] += bool(r.get("reason_match"))
    s["by_expected_reason"] = reasons
    return s


def write_fake_script(out: Path, item: dict) -> Path:
    voc = item["expect"].get("vocab") or {}
    pick = voc.get("nearest_frame_term") if voc.get("out_of_vocabulary") else None
    d = out / "fake_scripts"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{item['id']}.json"
    p.write_text(json.dumps({"pick": pick}, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


def run_one(item: dict, frames: Path, mode: str, out: Path, use_subprocess: bool) -> dict:
    frame = frames / f"{item['frame_id']}.md"
    argv = ["--frame", str(frame), "--question", item["question"]]
    for o in item.get("options") or []:
        argv += ["--option", o]
    argv += ["--vocab-llm", mode]
    if mode == "fake":
        argv += ["--vocab-fake", str(write_fake_script(out, item))]
    if use_subprocess:
        wrapper = ROOT / "artifacts" / "w2-c" / "py.sh"
        cmd = ([str(wrapper)] if wrapper.is_file() else [sys.executable]) + ["-m", "verantyx.conduct_ask", *argv]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), timeout=120)
        try:
            res = json.loads(proc.stdout)
        except ValueError:
            res = {"decision": "escalate", "escalate_reason": "INTERNAL_ERROR", "escalate_detail": "UNPARSEABLE_STDOUT"}
        res["_exit"] = proc.returncode
    else:
        import io
        from contextlib import redirect_stdout
        from verantyx import conduct_ask
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = conduct_ask.main(argv)
        res = json.loads(buf.getvalue())
        res["_exit"] = code
    return res


def row_for(item: dict, res: dict, split: str) -> dict:
    verdict, reason_match = judge(item, res)
    exp = item["expect"]
    voc = res.get("vocab") or {}
    return {
        "id": item["id"], "frame_id": item["frame_id"], "split": split, "lang": item["lang"], "w2c": item["w2c"],
        "expect": {"decision": exp["decision"], "answer_option_index": exp.get("answer_option_index"),
                   "answer": exp.get("answer"), "reason": item["w2c"].get("escalate_reason")},
        "observed": {"decision": res.get("decision"), "answer_option_index": res.get("answer_option_index"),
                     "answer": res.get("answer"), "reason": res.get("escalate_reason"), "detail": res.get("escalate_detail"),
                     "derivation": res.get("derivation"), "frame_term": voc.get("frame_term"),
                     "vocab_outcome": voc.get("outcome"), "kind": res.get("kind"), "exit": res.get("_exit")},
        "verdict": verdict, "reason_match": reason_match,
    }


def run(args: argparse.Namespace) -> int:
    items_path = Path(args.items)
    frames = Path(args.frames)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    held = holdout_ids(items_path)
    items = [json.loads(ln) for ln in items_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    todo = []
    for it in items:
        split = "holdout" if it["frame_id"] in held else "dev"
        if args.split in ("all", split):
            todo.append((it, split))
    if args.vocab_llm == "fake":
        for it, _ in todo:
            write_fake_script(out, it)
    workers = 8 if args.subprocess else 1
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(lambda t: run_one(t[0], frames, args.vocab_llm, out, args.subprocess), todo))
    rows = [row_for(it, res, sp) for (it, sp), res in zip(todo, results)]
    with (out / "results.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    summary = summarize(rows)
    summary["config"] = {"vocab_llm": args.vocab_llm, "split": args.split, "subprocess": bool(args.subprocess)}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("total", "false_answer", "wrong_answer", "q1_rate", "q2_answer_rate",
                                              "escalate_correct_rate", "reason_type_match_rate")}, ensure_ascii=False))
    return 0


def recount(dirpath: str) -> int:
    d = Path(dirpath)
    rows = [json.loads(ln) for ln in (d / "results.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    # judge again from the stored expectation and observation, not from the stored verdict
    fresh = []
    for r in rows:
        item = {"expect": {"decision": r["expect"]["decision"], "answer_option_index": r["expect"]["answer_option_index"],
                           "answer": r["expect"]["answer"]},
                "options": r["expect"]["answer_option_index"] is not None, "w2c": r["w2c"]}
        verdict, reason_match = judge(item, {"decision": r["observed"]["decision"],
                                             "answer_option_index": r["observed"]["answer_option_index"],
                                             "answer": r["observed"]["answer"], "escalate_reason": r["observed"]["reason"]})
        fresh.append({**r, "verdict": verdict, "reason_match": reason_match})
    new = summarize(fresh)
    old = json.loads((d / "summary.json").read_text(encoding="utf-8"))
    old.pop("config", None)
    same = json.dumps(new, sort_keys=True, ensure_ascii=False) == json.dumps(old, sort_keys=True, ensure_ascii=False)
    print(f"{d}: {'MATCH' if same else 'MISMATCH'} rows={len(rows)} q1_wrong={new['q1_wrong_count']} "
          f"q2_answer_rate={new['q2_answer_rate']} escalate_correct_rate={new['escalate_correct_rate']}")
    return 0 if same else 1


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--items")
    ap.add_argument("--frames")
    ap.add_argument("--vocab-llm", choices=("off", "fake"), default="off")
    ap.add_argument("--split", choices=("dev", "holdout", "all"), default="all")
    ap.add_argument("--out")
    ap.add_argument("--subprocess", action="store_true")
    ap.add_argument("--recount")
    args = ap.parse_args(argv)
    if args.recount:
        return recount(args.recount)
    if not (args.items and args.frames and args.out):
        ap.error("--items, --frames and --out are required")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
