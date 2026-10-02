"""python -m tools.bank_score --bank <B1|B2|B3|B5> --items <path> ... --tree <Vera のツリー> --out <dir>"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import adapters, schema
from .classify import CLASS_JA
from .report import build_summary, dumps, render_md, write_jsonl
from .runner import Session
from .score import score_observation
from .strategies import STRATEGIES, not_applicable, observe_strategy

EXIT_OK, EXIT_INPUT, EXIT_INVALID = 0, 2, 3
_OUTPUT_NAMES = ("results.jsonl", "results.partial.jsonl", "summary.json", "summary.md", "run_meta.json",
                 "INVALID.json", "raw", "baselines")


class InvalidRun(Exception):
    """ツリー外の verantyx を読んだ（出自検査で無効）。"""

    def __init__(self, stage: str, detail: dict):
        super().__init__(stage)
        self.stage = stage
        self.detail = detail


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m tools.bank_score",
                                 description="評価バンクの採点器。Vera は既定の入口だけから別プロセスで呼ぶ。")
    ap.add_argument("--bank", required=True, choices=list(schema.BANKS))
    ap.add_argument("--items", required=True)
    ap.add_argument("--quarantine")
    ap.add_argument("--frames", help="B5 の枠ファイルのディレクトリ（B5 では必須、他では不可）")
    ap.add_argument("--tree", required=True, help="測る Vera のツリー（PYTHONPATH になる）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--entry", help="入口（B1/B5: cli、B2: cli-ask-round5|cli-ask、B3: cli-ask-round5）")
    ap.add_argument("--timeout", type=float, default=60.0, help="1 問あたりの秒数（既定 60）")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--corpus-root", help="VERA_CORPUS_ROOT（既定は空の一時ディレクトリ）")
    return ap


def _safe(s: str) -> str:
    return re.sub(r"[^\w\-.]", "_", s)[:60]


def _git(tree: str, *args: str) -> str | None:
    try:
        cp = subprocess.run(["git", "-C", tree, *args], capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return cp.stdout.decode("utf-8", "replace").strip() if cp.returncode == 0 else None


def _meta_fields(rec: dict) -> dict:
    raw = rec["raw"] or {}

    def pick(k: str, typ: tuple) -> object:
        v = raw.get(k)
        return v if isinstance(v, typ) and not isinstance(v, bool) else None
    return {"lang": pick("lang", (str,)), "category": pick("category", (str,)),
            "phenomenon": pick("phenomenon", (str,)), "difficulty": pick("difficulty", (int,))}


def _row(rec: dict, bank: str, entry: str | None, **kw: object) -> dict:
    row = {"id": rec["id"], "line": rec["line"], "bank": bank, **_meta_fields(rec),
           "class": None, "class_ja": None, "reason": None, "reason_detail": [], "entry": entry,
           "capability": None, "observation": None, "checks": {}, "notes": [], "unknown_expect_keys": [],
           "elapsed_ms": 0}
    row.update(kw)
    if row["class"]:
        row["class_ja"] = CLASS_JA[row["class"]]
    return row


def _scored(row: dict, sc: dict) -> dict:
    row.update({"class": sc["class"], "class_ja": sc["class_ja"], "reason": sc["reason"], "checks": sc["checks"],
                "notes": sc["notes"], "unknown_expect_keys": sc["unknown_expect_keys"]})
    return row


def _check_provenance(sess: Session, stage: str) -> None:
    if sess.outside:
        raise InvalidRun(stage, {"outside": sess.outside})


def run(args: argparse.Namespace) -> int:
    bank = args.bank
    try:
        entry = adapters.check_entry(bank, args.entry)
    except ValueError as e:
        print(f"入力の誤り: {e}", file=sys.stderr)
        return EXIT_INPUT
    if bank == "B5" and not args.frames:
        print("入力の誤り: B5 には --frames が必要", file=sys.stderr)
        return EXIT_INPUT
    if bank != "B5" and args.frames:
        print("入力の誤り: --frames は B5 だけが受け取る（黙って無視しない）", file=sys.stderr)
        return EXIT_INPUT
    if args.timeout <= 0:
        print("入力の誤り: --timeout は正の数", file=sys.stderr)
        return EXIT_INPUT
    if not Path(args.tree).is_dir():
        print(f"入力の誤り: --tree がディレクトリでない: {args.tree}", file=sys.stderr)
        return EXIT_INPUT
    frames = Path(args.frames) if args.frames else None
    if frames is not None and not frames.is_dir():
        print(f"入力の誤り: --frames がディレクトリでない: {args.frames}", file=sys.stderr)
        return EXIT_INPUT
    try:
        quarantine_ids = schema.load_quarantine(args.quarantine)
        recs = schema.read_items(args.items, bank, frames)
    except schema.InputError as e:
        print(f"入力の誤り: {e}", file=sys.stderr)
        return EXIT_INPUT

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name in _OUTPUT_NAMES:  # 前回の出力（とくに summary.*）を残さない
        p = out / name
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    (out / "raw").mkdir()

    qset = set(quarantine_ids)
    ids_present = {r["id"] for r in recs}
    kept = [r for r in recs if r["id"] not in qset]
    quarantine = {"count": len(recs) - len(kept), "ids": sorted(r["id"] for r in recs if r["id"] in qset),
                  "not_in_items": sorted(qset - ids_present)}

    sess = Session(args.python, args.tree, args.corpus_root, args.timeout)
    rows: list[dict] = []
    timing = {"vera_calls_ms_total": 0.0}
    vera_calls = unreachable_n = 0
    try:
        pre = sess.precheck()
        timing["precheck_ms"] = pre.pop("elapsed_ms")
        if pre["outside"] is None or pre["import_error"] or pre["outside"]:
            raise InvalidRun("precheck", {"outside": pre["outside"] or [], "precheck": pre})
        for seq, rec in enumerate(kept, start=1):
            if rec["errors"]:
                rows.append(_row(rec, bank, entry, **{"class": "unscorable", "reason": "ITEM_INVALID",
                                                      "reason_detail": rec["errors"]}))
                continue
            reach = adapters.reachability(bank, entry, rec["case"])
            if not reach["reachable"]:
                unreachable_n += 1
                rows.append(_row(rec, bank, entry, **{"class": "unreachable", "capability": reach["capability"],
                                                      "reason_detail": reach["reasons"]}))
                continue
            call = adapters.build_call(bank, entry, rec["case"])
            r = sess.run_ask(seq, call["argv"], call["files"])
            vera_calls += 1
            timing["vera_calls_ms_total"] = round(timing["vera_calls_ms_total"] + r["elapsed_ms"], 1)
            _check_provenance(sess, f"item:{rec['id']}")
            if r["provenance"] is None and r["reason"] is None:
                # 出自を確かめられなかった子プロセスの答えは採点に使わない（ツリー外を読んで
                # 型つき JSON を出し、出自を書かずに終わる経路を塞ぐ）。
                raise InvalidRun(f"item:{rec['id']}", {"reason": "PROVENANCE_UNVERIFIED", "outside": [],
                                                       "detail": "子プロセスが出自記録を書かずに終了した"})
            raw_doc = {"id": rec["id"], "entry": entry, "argv": call["argv"], "exit_code": r["exit_code"],
                       "reason": r["reason"], "stdout_json": r["stdout_json"], "stdout_text": r["stdout_text"],
                       "stderr": r["stderr"], "provenance": r["provenance"], "elapsed_ms": r["elapsed_ms"]}
            raw_text = sess.redact(json.dumps(raw_doc, ensure_ascii=False, sort_keys=True, indent=1))
            (out / "raw" / f"{seq:04d}_{_safe(rec['id'])}.json").write_text(raw_text + "\n", encoding="utf-8")
            row_kw = {"elapsed_ms": r["elapsed_ms"]}
            if r["reason"] is not None:
                # タイムアウト・異常終了・JSON でない出力は採点に使わない（runtime_error）ので、出自が無くても続ける。
                # ただし出自を確かめられなかったことは行に残す（summary の runtime_error_provenance_unverified）。
                if r["provenance"] is None:
                    row_kw["reason_detail"] = ["PROVENANCE_UNVERIFIED"]
                row = _row(rec, bank, entry, **{"class": "runtime_error", "reason": r["reason"],
                                                "observation": {"exit_code": r["exit_code"], "entry": entry,
                                                                "argv": call["argv"]}, **row_kw})
            else:
                obs = adapters.observe(bank, r["stdout_json"], entry, call["argv"], r["exit_code"], rec["raw"])
                if obs["state"] == "unmapped":
                    row = _row(rec, bank, entry, **{"class": "runtime_error", "reason": "UNMAPPED_RESULT_TYPE",
                                                    "observation": obs, **row_kw})
                else:
                    row = _row(rec, bank, entry, observation=obs, **row_kw)
                    _scored(row, score_observation(bank, rec["raw"], rec["case"], obs))
            rows.append(row)
        strat_rows: dict[str, list[dict]] = {}
        for s in STRATEGIES:
            if not_applicable(bank, s) is not None:
                continue
            srows = []
            for rec in kept:
                if rec["errors"]:
                    srows.append(_row(rec, bank, f"strategy:{s}", **{"class": "unscorable", "reason": "ITEM_INVALID",
                                                                     "reason_detail": rec["errors"]}))
                    continue
                obs = observe_strategy(bank, s, rec["case"])
                srows.append(_scored(_row(rec, bank, f"strategy:{s}", observation=obs),
                                     score_observation(bank, rec["raw"], rec["case"], obs)))
            strat_rows[s] = srows
    except InvalidRun as e:
        if rows:
            write_jsonl(out / "results.partial.jsonl", rows)
        inv = {"verdict": "INVALID_PROVENANCE", "stage": e.stage, "tree": os.path.realpath(args.tree),
               "note": "ツリー外の verantyx を読んだ（または出自を確かめられなかった）ので採点は無効", **e.detail,
               "processes_checked": sess.processes_checked}
        (out / "INVALID.json").write_text(sess.redact(json.dumps(inv, ensure_ascii=False, sort_keys=True, indent=1)) + "\n",
                                          encoding="utf-8")
        print(f"採点は無効: ツリー外の verantyx を読んだ ({e.stage})。{out / 'INVALID.json'} を見よ", file=sys.stderr)
        sess.close()
        raw_dir = out / "raw"
        if raw_dir.is_dir() and not any(raw_dir.iterdir()):
            raw_dir.rmdir()
        return EXIT_INVALID
    finally:
        sess.close()  # 一時ディレクトリは異常終了でも残さない（close は何度呼んでもよい）
    meta = {
        "bank": bank,
        "entry": entry,
        "entry_note": "既定: README が最初に案内する vera CLI のうち、そのバンクの入力を受け取り型つきの結果を返す最初のサブコマンド",
        "python": args.python,
        "args": {"items": args.items, "quarantine": args.quarantine, "frames": args.frames,
                 "corpus_root": args.corpus_root, "timeout_s": args.timeout, "entry_option": args.entry},
        "tree_realpath": os.path.realpath(args.tree),
        "tree_head": _git(args.tree, "rev-parse", "HEAD"),
        "verantyx_untouched": (_git(args.tree, "status", "--porcelain", "--", "verantyx") == ""),
        "child_env": sess.env_for_meta(),
        "child_argv_template": ["<python>", "-c", "<BOOTSTRAP: runpy.run_module('verantyx.cli', run_name='__main__')>",
                                "run", "ask", "[--mode round5] [--document <file>...] -- <query>"],
        "precheck": pre,
        "provenance_total": {"processes_checked": sess.processes_checked,
                             "processes_unverified": sess.processes_unverified,
                             "outside_count": len(sess.outside)},
        "vera_calls": vera_calls,
        "unreachable_not_called": unreachable_n,
        "raw_path_redactions": sess.redactions,
        "quarantine": quarantine,
        "timing": timing,
    }
    sess.close()
    write_jsonl(out / "results.jsonl", rows)
    for s, srows in strat_rows.items():
        write_jsonl(out / "baselines" / s / "results.jsonl", srows)
    (out / "run_meta.json").write_text(json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
                                       encoding="utf-8")
    summary = build_summary(bank, rows, strat_rows, quarantine)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
                                      encoding="utf-8")
    (out / "summary.md").write_text(render_md(summary) + "\n", encoding="utf-8")
    h = summary["headline"]
    print(f"{bank} entry={entry} total={summary['total']} " + " ".join(
        f"{k}={v['count']}" for k, v in summary["classes"].items()))
    print(f"correct_rate={h['correct_rate']['all']} wrong_rate={h['wrong_rate']['all']} "
          f"false_compliance_rate={h['false_compliance_rate']['all']}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return run(args)
