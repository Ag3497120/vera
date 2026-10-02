"""python -m tools.bank_score.leakcheck --items <I>... [--frames <D>] --scan <path>... [--exclude <path>...]

評価バンクの **問題の中身** が公開物（リポジトリに入るファイル）に漏れていないかを調べる。
照合語は問題の中身の欄だけから作る（B1: input・rationale・phenomenon、B2: turns・documents・check_claim・reference・
alt_answers・wrong_answers の text・must_* の語・evidence・rationale・phenomenon、B3: brief・materials・reference・provenance・
rationale・phenomenon・must_* の語・cells の値、B5: question・options・answer・evidence・rationale・phenomenon・must_* の語、
それに frames の本文）。NFKC と空白の連続を 1 つにした上で、12 字以上の文字列は 12 字の窓すべて、8〜11 字の文字列はそれ全体を
照合語にする。役割名・ラベル・型名のような ASCII の識別子（`^[A-Za-z0-9_:\\-.]+$`）は照合語にしない。
**ただし 2 つの絞り込みを足した**（W1-s2 判断記録 37。足さないと、英語の一般的な語句や「一文で説明してください」のような共通の依頼文が
大量の偽の当たりになり、検査が使えない）: (1) 12 字の窓のうち **ASCII だけの窓は照合語にしない**（代わりに 30 字の窓を使う）。
(2) **3 問以上（または 3 つ以上の枠）に現れる窓は照合語にしない**（共通の言い回しであって、特定の問題の中身ではない）。
当たったら、ファイル・位置・問題の id・欄名を出して終了コード 1（照合語そのものは出さない）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

IDENT = re.compile(r"^[A-Za-z0-9_:\-.]+$")
ASCII_WINDOW = 30  # ASCII だけの文字列に使う窓の長さ
COMMON_MIN_SOURCES = 3  # この数以上の問題・枠に現れる窓は共通の言い回しとして照合語にしない
WS = re.compile(r"\s+")
MAX_REPORT_PER_FILE = 20
TEXT_SUFFIXES = {".py", ".md", ".json", ".jsonl", ".txt", ".yml", ".yaml", ".toml", ".cfg", ".csv", ".log", ""}


def _n(s: str) -> str:
    return WS.sub(" ", unicodedata.normalize("NFKC", s)).strip()


def _strings(v: object, out: list[str]) -> None:
    if isinstance(v, str):
        out.append(v)
    elif isinstance(v, list):
        for x in v:
            _strings(x, out)
    elif isinstance(v, dict):
        for x in v.values():
            _strings(x, out)


def _fields(it: dict) -> list[tuple[str, list[str]]]:
    """問題 1 件の (欄名, 文字列の一覧)。中身の欄だけ。"""
    e = it.get("expect") if isinstance(it.get("expect"), dict) else {}
    cons = e.get("constraints") if isinstance(e.get("constraints"), dict) else {}
    out: list[tuple[str, list[str]]] = []

    def add(name: str, v: object) -> None:
        ss: list[str] = []
        _strings(v, ss)
        out.append((name, ss))

    for k in ("input", "rationale", "phenomenon", "brief", "materials", "check_claim", "reference", "alt_answers"):
        if k in it:
            add(k, it[k])
    for t in it.get("turns") or []:
        if isinstance(t, dict):
            add("turns.content", t.get("content"))
    for d in it.get("documents") or []:
        if isinstance(d, dict):
            add("documents.text", d.get("text"))
    for w in it.get("wrong_answers") or []:
        if isinstance(w, dict):
            add("wrong_answers.text", w.get("text"))
    for k in ("reference", "provenance", "evidence", "answer", "question", "options", "must_contain_any",
              "must_contain_all", "must_not_contain", "must_not_equal"):
        if k in e:
            add(f"expect.{k}", e[k])
    for k in ("must_contain_any", "must_contain_all", "must_not_contain", "must_not_equal", "refusal_text_must_not_contain",
              "order", "starts_with"):
        if k in cons:
            add(f"constraints.{k}", cons[k])
    form = cons.get("form")
    if isinstance(form, dict) and isinstance(form.get("cells"), dict):
        add("constraints.form.cells", form["cells"])  # 行の値・列名・候補
    return out


def _is_ascii(s: str) -> bool:
    return all(ord(c) < 128 for c in s)


def build_needles(items_paths: list[str], frames: list[str]) -> dict[str, tuple[str, str]]:
    """照合語 → (問題の id, 欄名)。窓の長さは 12（非 ASCII を含む窓）か 30（ASCII だけの窓）、8〜11 字の文字列は全体。"""
    needles: dict[str, tuple[str, str]] = {}
    sources: dict[str, set[str]] = {}

    def add(w: str, who: str, field: str) -> None:
        needles.setdefault(w, (who, field))
        sources.setdefault(w, set()).add(who)

    def put(s: str, who: str, field: str) -> None:
        t = _n(s)
        if not t or IDENT.match(t):
            return
        if len(t) >= 12:
            for i in range(len(t) - 11):
                w = t[i:i + 12]
                if not IDENT.match(w) and not _is_ascii(w):
                    add(w, who, field)
            for i in range(len(t) - ASCII_WINDOW + 1):
                w = t[i:i + ASCII_WINDOW]
                if _is_ascii(w) and not IDENT.match(w):
                    add(w, who, field)
        elif len(t) >= 8 and not _is_ascii(t):
            add(t, who, field)  # 8〜11 字の ASCII だけの文字列（英語の短い語句）は一般的なので照合語にしない

    for p in items_paths:
        for ln in Path(p).read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            try:
                it = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if not isinstance(it, dict):
                continue
            who = str(it.get("id"))
            for field, ss in _fields(it):
                for s in ss:
                    put(s, who, field)
    for d in frames:
        for f in sorted(Path(d).glob("*")):
            if f.is_file():
                put(f.read_text(encoding="utf-8"), f"frame:{f.stem}", "frame")
    return {w: v for w, v in needles.items() if len(sources[w]) < COMMON_MIN_SOURCES}


def _scan_text(text: str, needles12: dict, needles30: dict, needles_short: list[str], info: dict) -> list[tuple[int, str, str]]:
    """text（正規化済み）の中の照合語の当たり (位置, id, 欄名)。"""
    hits: list[tuple[int, str, str]] = []
    n = len(text)
    for i in range(max(0, n - 11)):
        w = text[i:i + 12]
        if w in needles12:
            who, field = needles12[w]
            hits.append((i, who, field))
            if len(hits) >= MAX_REPORT_PER_FILE:
                return hits
    if needles30:
        for i in range(max(0, n - ASCII_WINDOW + 1)):
            w = text[i:i + ASCII_WINDOW]
            if w in needles30:
                who, field = needles30[w]
                hits.append((i, who, field))
                if len(hits) >= MAX_REPORT_PER_FILE:
                    return hits
    for s in needles_short:
        j = text.find(s)
        if j >= 0:
            who, field = info[s]
            hits.append((j, who, field))
            if len(hits) >= MAX_REPORT_PER_FILE:
                break
    return hits


def _iter_files(paths: list[str], excludes: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        pp = Path(p)
        cands = [pp] if pp.is_file() else sorted(x for x in pp.rglob("*") if x.is_file())
        for f in cands:
            r = f.resolve()
            if any(ex == r or ex in r.parents for ex in excludes):
                continue
            if "__pycache__" in f.parts or f.suffix == ".pyc":
                continue
            files.append(f)
    return files


def scan(items: list[str], frames: list[str], paths: list[str], excludes: list[str]) -> tuple[list[dict], int]:
    needles = build_needles(items, frames)
    needles12 = {k: v for k, v in needles.items() if len(k) == 12}
    needles30 = {k: v for k, v in needles.items() if len(k) == ASCII_WINDOW}
    short = sorted(k for k in needles if len(k) < 12)
    short_info = {k: needles[k] for k in short}
    ex = [Path(e).resolve() for e in excludes]
    findings: list[dict] = []
    nfiles = 0
    for f in _iter_files(paths, ex):
        if f.suffix not in TEXT_SUFFIXES:
            continue
        try:
            raw = f.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        nfiles += 1
        texts = [_n(raw)]
        if f.suffix in (".json", ".jsonl"):
            ss: list[str] = []
            try:
                if f.suffix == ".jsonl":
                    for ln in raw.splitlines():
                        if ln.strip():
                            _strings(json.loads(ln), ss)
                else:
                    _strings(json.loads(raw), ss)
                texts.append(_n("\n".join(ss)))
            except json.JSONDecodeError:
                pass
        seen: set[tuple] = set()
        for t in texts:
            for pos, who, field in _scan_text(t, needles12, needles30, short, short_info):
                key = (who, field)
                if key in seen:
                    continue
                seen.add(key)
                line = raw[:max(0, pos)].count("\n") + 1 if t is texts[0] else None
                findings.append({"file": str(f), "line_approx": line, "id": who, "field": field})
    return findings, nfiles


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.bank_score.leakcheck")
    ap.add_argument("--items", action="append", default=[], required=True)
    ap.add_argument("--frames", action="append", default=[])
    ap.add_argument("--scan", action="append", default=[], required=True)
    ap.add_argument("--exclude", action="append", default=[])
    args = ap.parse_args(argv)
    findings, nfiles = scan(args.items, args.frames, args.scan, args.exclude)
    for f in findings:
        print(f"LEAK file={f['file']} line≈{f['line_approx']} item={f['id']} field={f['field']}")
    print(f"leakcheck: scanned_files={nfiles} leaks={len(findings)}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
