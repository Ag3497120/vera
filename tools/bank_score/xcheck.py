"""python -m tools.bank_score.xcheck: 設計者が audit/ に書いた近似採点と、この採点器の判定を突き合わせる（W1-s2 手順 9）。

- 設計者のスクリプトは **別プロセス**で importlib.util.spec_from_file_location により読み、純粋な関数だけを呼ぶ
  （`main()` は呼ばない。呼ぶと audit/baseline.json を上書きするバンクがある）。子プロセスは `-B`・
  PYTHONDONTWRITEBYTECODE=1・cwd は一時ディレクトリ・PYTHONPATH なし。標準入力で (問題, 出力) を受け、標準出力で判定を返す。
  終了時に `sys.modules` に verantyx で始まるものがあれば失敗（終了コード 1）。
- バンクのディレクトリ（--items の親）の全ファイルの sha256 を実行前後で取り、変わっていたら終了コード 3。
- 出力: agreement.json（probe 別の一致数・不一致数）と mismatches.jsonl。設計者の理由は **最初の ASCII の語だけ**
  （missing・forbidden・state など）。問題の中身（必須語・禁止語・B1 の must_not の値）は書かない。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from . import schema
from .classify import classify
from .judge import build_probe_observations
from .score import score_observation
from .strategies import STRATEGIES, not_applicable, observe_strategy
from .v2 import b1, b3
from .v2.score import b1_output

EXIT_OK, EXIT_FAIL, EXIT_INPUT, EXIT_CHANGED = 0, 1, 2, 3
PASS_CLASSES = ("correct", "correct_abstain")
MARK = "@@XCHECK@@"

_CHILD = r'''
import importlib.util, json, sys
script, bank = sys.argv[1], sys.argv[2]
sys.argv = [script]
spec = importlib.util.spec_from_file_location("designer_scorer_module", script)
mod = importlib.util.module_from_spec(spec)
sys.modules["designer_scorer_module"] = mod
spec.loader.exec_module(mod)
queries = json.load(sys.stdin)
out = []
for q in queries:
    try:
        if bank == "B1":
            v, d = mod.judge(q["item"], q["out"])
            out.append({"verdict": v, "detail": d if isinstance(d, str) else ("hits" if d else None)})
        elif bank == "B2":
            ok, why = mod.judge(q["item"], q["text"], q["state"])
            out.append({"pass": bool(ok), "detail": why[0] if why else None})
        elif bank == "B3":
            r = {}
            for mode in ("lenient", "upper"):
                ok, why = mod.score(q["item"], q["text"], q["state"], mode)
                r[mode] = {"pass": bool(ok), "detail": why or None}
            out.append(r)
        else:
            ok = mod.score(q["item"], (q["dec"], q["val"]))
            out.append({"pass": bool(ok), "detail": None})
    except Exception as e:
        out.append({"error": type(e).__name__})
bad = sorted(m for m in sys.modules if m.split(".")[0].startswith("verantyx"))
sys.stdout.write("\n" + "@@XCHECK@@" + json.dumps({"results": out, "verantyx_modules": bad}))
'''


def sha_tree(root: Path) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def first_word(s: object) -> str | None:
    """設計者の理由の最初の ASCII の語だけ（中身を写さない）。"""
    if not isinstance(s, str):
        return None
    m = re.match(r"[A-Za-z_]+", s.strip())
    return m.group(0) if m else "<non-ascii>"


def run_designer(script: str, bank: str, queries: list[dict]) -> tuple[list[dict], list[str], str]:
    with tempfile.TemporaryDirectory() as tmp:
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONDONTWRITEBYTECODE": "1", "HOME": tmp,
               "LANG": "C.UTF-8", "PYTHONIOENCODING": "utf-8"}
        cp = subprocess.run([sys.executable, "-B", "-c", _CHILD, script, bank], input=json.dumps(queries),
                            capture_output=True, text=True, cwd=tmp, env=env, timeout=3600)
    if cp.returncode != 0 or MARK not in cp.stdout:
        return [], [], f"child_exit={cp.returncode}"
    payload = json.loads(cp.stdout.rsplit(MARK, 1)[1])
    return payload["results"], payload["verantyx_modules"], ""


def designer_input(bank: str, item: dict, obs: dict) -> dict | None:
    if bank == "B1":
        return {"item": item, "out": b1_output(obs)}
    if bank == "B2":
        return {"item": item, "text": obs.get("text") or "", "state": "abstain" if obs["state"] == "abstain" else "answer"}
    if bank == "B3":
        st = b3.b3_state(obs)
        return None if st is None else {"item": item, "text": obs.get("text") or "", "state": st}
    dec = "escalate" if obs["state"] == "abstain" else "answer"
    oi = obs.get("answer_option_index")
    return {"item": item, "dec": dec, "val": oi if isinstance(oi, int) and not isinstance(oi, bool) else obs.get("answer")}


B1_MAP = {"correct": "correct", "correct_abstain": "correct", "misread": "misread", "over_abstain": "abstain",
          "wrong": "incomplete", "false_compliance": "incomplete", "unscorable": "UNJUDGED"}


def _rules(sc: dict, result: str) -> list[str]:
    return sorted(k for k, c in sc["checks"].items() if c["result"] == result)


def _build_queries(bank: str, recs: list[dict], probes: list[str]) -> tuple[list[dict], dict]:
    """(設計者に渡す問い, 飛ばした数)。設計者の関数に渡せない観測（型が決まらない B3 など）は黙って捨てず、probe 別に数える。"""
    qs: list[dict] = []
    skipped: dict = {}
    for rec in recs:
        for probe in probes:
            if probe == "strategies":
                pairs = []
                for s in STRATEGIES:
                    if not_applicable(bank, s) is None:
                        pairs.append((f"strategy:{s}", 0, observe_strategy(bank, s, rec["case"], "v2")))
            else:
                pairs = [(probe, o["probe_index"], o) for o in build_probe_observations(bank, probe, rec["raw"], rec["case"])]
            for name, idx, obs in pairs:
                q = designer_input(bank, rec["raw"], obs)
                if q is None:
                    key = "strategies" if name.startswith("strategy:") else name
                    skipped[key] = skipped.get(key, 0) + 1
                    continue
                sc = score_observation(bank, rec["raw"], rec["case"], obs, "v2")
                qs.append({"id": rec["id"], "probe": name, "index": idx, "q": q, "sc": sc, "obs": obs})
    return qs, skipped


def _upper_class(sc: dict, obs: dict) -> str:
    """主分類で UNJUDGED の規則を PASS とみなした分類（設計者の upper との突き合わせ用）。"""
    rs = [("PASS" if c["result"] == "UNJUDGED" else c["result"]) for c in sc["checks"].values()]
    ov = "FAIL" if "FAIL" in rs else "PASS"
    if not rs:
        ov = "UNJUDGED"
    k, _ = classify(misread=sc["class"] == "misread", side=sc["side"], state=obs["state"], overall=ov,
                    abstain_overall=("FAIL" if "FAIL" in [c["result"] for n, c in sc["checks"].items()
                                                         if n in ("refusal_text_must_not_contain",
                                                                  "abstain_text_must_not_contain")] else None))
    return k


def compare(bank: str, qs: list[dict], res: list[dict]) -> list[dict]:
    """問題×probe ごとの突き合わせ行。agree は bool、kind は比較の種類。"""
    rows = []
    for q, r in zip(qs, res):
        sc = q["sc"]
        base = {"id": q["id"], "probe": q["probe"], "index": q["index"], "ours_class": sc["class"],
                "ours_class_approx": sc.get("class_approx"), "ours_fail_rules": _rules(sc, "FAIL"),
                "ours_unjudged_rules": _rules(sc, "UNJUDGED")}
        if "error" in r:
            rows.append({**base, "kind": "designer_error", "agree": False, "designer": r["error"]})
        elif bank == "B1":
            ours = B1_MAP[sc["class"]]
            rows.append({**base, "kind": "b1_verdict", "agree": ours == r["verdict"], "ours": ours,
                         "designer": r["verdict"], "designer_reason": first_word(r["detail"])})
        elif bank == "B3":
            ours_len = sc["class_approx"] in PASS_CLASSES
            ours_up = _upper_class(sc, q["obs"]) in PASS_CLASSES
            rows.append({**base, "kind": "b3_lenient", "agree": ours_len == r["lenient"]["pass"],
                         "ours": ours_len, "designer": r["lenient"]["pass"],
                         "designer_reason": first_word(r["lenient"]["detail"])})
            rows.append({**base, "kind": "b3_upper", "agree": ours_up == r["upper"]["pass"], "ours": ours_up,
                         "designer": r["upper"]["pass"], "designer_reason": first_word(r["upper"]["detail"])})
        else:
            ours = sc["class"] in PASS_CLASSES
            rows.append({**base, "kind": "pass", "agree": ours == r["pass"], "ours": ours, "designer": r["pass"],
                         "designer_reason": first_word(r.get("detail"))})
    return rows


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m tools.bank_score.xcheck")
    ap.add_argument("--bank", required=True, choices=list(schema.BANKS))
    ap.add_argument("--profile", default="v2", choices=["v2"])
    ap.add_argument("--items", required=True)
    ap.add_argument("--quarantine")
    ap.add_argument("--frames")
    ap.add_argument("--designer", required=True, help="設計者の採点スクリプト（関数だけを別プロセスで呼ぶ）")
    ap.add_argument("--probes", default="reference,strategies")
    ap.add_argument("--out", required=True)
    return ap


def run(args: argparse.Namespace) -> int:
    bank = args.bank
    probes = [p for p in args.probes.split(",") if p]
    bad = [p for p in probes if p not in ("reference", "strategies", "alt_answers", "wrong_answers")]
    if bad:
        print(f"入力の誤り: 不明な probe {bad}", file=sys.stderr)
        return EXIT_INPUT
    frames = Path(args.frames) if args.frames else None
    root = Path(args.items).resolve().parent
    try:
        qinfo = schema.load_quarantine_info(args.quarantine)
        recs = schema.read_items(args.items, bank, frames, "v2")
    except schema.InputError as e:
        print(f"入力の誤り: {e}", file=sys.stderr)
        return EXIT_INPUT
    if not Path(args.designer).is_file():
        print("入力の誤り: --designer が無い", file=sys.stderr)
        return EXIT_INPUT
    qset = set(qinfo["ids"])
    kept = [r for r in recs if r["id"] not in qset and not r["errors"]]
    before = sha_tree(root)
    qs, skipped = _build_queries(bank, kept, probes)
    results, vmods, err = run_designer(str(Path(args.designer).resolve()), bank, [{**x["q"]} for x in qs])
    after = sha_tree(root)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    if changed:
        print(f"バンクのファイルが変わった（{len(changed)} 件）。中止", file=sys.stderr)
        return EXIT_CHANGED
    if err or len(results) != len(qs):
        print(f"設計者のスクリプトの実行に失敗: {err}", file=sys.stderr)
        return EXIT_FAIL
    if vmods:
        print(f"設計者のスクリプトの子プロセスが verantyx を読んだ: {vmods}", file=sys.stderr)
        return EXIT_FAIL
    rows = compare(bank, qs, results)
    agg: dict = {}
    for r in rows:
        name = r["probe"] if r["probe"].startswith("strategy:") is False else "strategies"
        key = f"{name}/{r['kind']}"
        a = agg.setdefault(key, {"n": 0, "agree": 0, "disagree": 0, "by_strategy": {}})
        a["n"] += 1
        a["agree" if r["agree"] else "disagree"] += 1
        if r["probe"].startswith("strategy:"):
            s = a["by_strategy"].setdefault(r["probe"], {"n": 0, "disagree": 0})
            s["n"] += 1
            s["disagree"] += 0 if r["agree"] else 1
    agreement = {"bank": bank, "profile": "v2", "designer_script": Path(args.designer).name, "n_items": len(kept),
                 "probes": agg, "skipped": dict(sorted(skipped.items())), "bank_files_unchanged": True, "bank_files_hashed": len(before),
                 "child_loaded_verantyx": False,
                 "note": "mismatches.jsonl に不一致の 1 件ずつ（id・probe・こちらの分類・設計者の判定・設計者の理由の最初の語）"}
    (out / "agreement.json").write_text(json.dumps(agreement, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
                                        encoding="utf-8")
    with (out / "mismatches.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            if not r["agree"]:
                f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    for k, a in sorted(agg.items()):
        print(f"{bank} {k}: n={a['n']} agree={a['agree']} disagree={a['disagree']}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    return run(_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
