"""python -m tools.bank_score.publish <private> <public>: 非公開の出力から、問題の中身を含まない公開用の出力を作る（D12）。

v2 バンクは評価バンクなので、実行の出力（raw の argv・本文、規則の detail の必須語や禁止語、Vera の本文、phenomenon）には
問題の中身が入る。リポジトリに入れてよいのは、この公開用だけ。残す欄は下の表のとおり（id・位置・バンク・言語・分類・
理由の型・規則ごとの PASS/FAIL と理由コードだけ）。`raw/`・`phenomenon`・`observation`・`notes` は写さない。
公開側の行から要約を作り直して、非公開側の要約と一致しなければ終了コード 1（消した欄が要約に使われていない証拠）。
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

from .adapters import CAPABILITY_REASONS
from .recount import recompute
from .sanitize import clean_code, clean_key
from .report import read_jsonl, write_jsonl

KEEP = ("id", "line", "bank", "lang", "category", "difficulty", "unit", "class", "class_ja", "class_approx", "reason",
        "entry", "capability", "evidence_match", "probe", "probe_index", "side")
PLAIN_CODE = re.compile(r"^[A-Z][A-Z_0-9]*$")
APPROX_VALUES = ("PASS", "FAIL", "UNJUDGED")
_FIXED_TEXTS = set(CAPABILITY_REASONS.values())


def clean_checks(checks: dict) -> dict:
    out = {}
    for name, c in sorted((checks or {}).items()):
        d = c.get("detail") or {}
        det: dict = {}
        if isinstance(d.get("reason"), str) and PLAIN_CODE.match(d["reason"]):
            det["reason"] = d["reason"]
        elif d.get("reason") is not None:
            det["reason"] = "<redacted>"
        if d.get("surface_approx") in APPROX_VALUES:
            det["surface_approx"] = d["surface_approx"]
        out[clean_key(name)] = {"result": c["result"], "detail": det}
    return out


def public_row(r: dict) -> dict:
    out = {k: r[k] for k in KEEP if k in r}
    if r.get("class") == "unreachable":
        out["reason_detail"] = [x if x in _FIXED_TEXTS else "<redacted>" for x in (r.get("reason_detail") or [])]
    else:
        out["reason_detail"] = [clean_code(x) for x in (r.get("reason_detail") or [])]
    out["checks"] = clean_checks(r.get("checks") or {})
    out["unknown_expect_keys"] = [clean_key(k) for k in (r.get("unknown_expect_keys") or [])]
    return out


def publish(private: Path, public: Path) -> int:
    if not (private / "results.jsonl").is_file() or not (private / "run_meta.json").is_file():
        print(f"非公開の出力として読めない: {private}", file=sys.stderr)
        return 2
    if public.resolve() == private.resolve() or private.resolve() in public.resolve().parents:
        print("公開先が非公開の中にある", file=sys.stderr)
        return 2
    if public.exists():
        # 消してよいのは、以前の publish の出力（results.jsonl と run_meta.json がある）か空のディレクトリだけ。
        # それ以外（利用者の別のディレクトリ）を再帰的に消さない。
        if not public.is_dir():
            print(f"公開先が通常のディレクトリではない（ファイルなど）ので消さない: {public}", file=sys.stderr)
            return 2
        if any(public.iterdir()) and not ((public / "results.jsonl").is_file() and (public / "run_meta.json").is_file()):
            print(f"公開先が以前の publish の出力に見えないので消さない: {public}", file=sys.stderr)
            return 2
        shutil.rmtree(public)
    public.mkdir(parents=True)
    write_jsonl(public / "results.jsonl", [public_row(r) for r in read_jsonl(private / "results.jsonl")])
    bdir = private / "baselines"
    if bdir.is_dir():
        for d in sorted(p for p in bdir.iterdir() if p.is_dir()):
            write_jsonl(public / "baselines" / d.name / "results.jsonl",
                        [public_row(r) for r in read_jsonl(d / "results.jsonl")])
    shutil.copyfile(private / "run_meta.json", public / "run_meta.json")
    summ_priv, md_priv = recompute(private)
    summ_pub, md_pub = recompute(public)
    stored = json.loads((private / "summary.json").read_text(encoding="utf-8"))
    ok_priv = json.loads(json.dumps(summ_priv, ensure_ascii=False)) == stored
    ok_same = json.loads(json.dumps(summ_pub, ensure_ascii=False)) == json.loads(json.dumps(summ_priv, ensure_ascii=False)) \
        and md_pub == md_priv
    if not (ok_priv and ok_same):
        print(f"publish {private} -> {public}: 要約が一致しない（非公開の保存値と再計算 {'一致' if ok_priv else '不一致'}、"
              f"公開側と非公開側 {'一致' if ok_same else '不一致'}）。消した欄が要約に使われている", file=sys.stderr)
        return 1
    (public / "summary.json").write_text(json.dumps(summ_pub, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
                                         encoding="utf-8")
    (public / "summary.md").write_text(md_pub + "\n", encoding="utf-8")
    print(f"publish {private} -> {public}: 要約一致（非公開と公開が同じ数）。raw/ ・phenomenon・observation・notes は写していない")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("使い方: python -m tools.bank_score.publish <private> <public>", file=sys.stderr)
        return 2
    return publish(Path(argv[0]), Path(argv[1]))


if __name__ == "__main__":
    sys.exit(main())
