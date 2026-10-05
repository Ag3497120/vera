#!/usr/bin/env python3
"""README の数値・言い切り・公開前の点検の検査器（W16-t11。標準ライブラリだけ。verantyx を import しない）。

サブコマンド:
  numbers    R-1: 仕様 (numbers.json) の各行を、出所の `git show <commit>:<path>` から再計算し、
             README の数値と突き合わせる。--spec-only なら出所の再計算だけ。
  claims     R-2: 言い切りの語（claim_words.json。凍結済み）を含む文は、[N-xx] の印で
             分母と集合名のある行を参照していなければならない。
  prepublish R-4: 公開する木の文書にユーザー名・絶対パス・hidden/・秘密の形が無いこと。

終了コード: 0 = 全部 OK / 1 = 1 件以上の不一致 / 2 = 使い方の誤り・出所が読めない（SOURCE_UNREADABLE）。
出所は必ず git の commit から読む（作業ツリーのファイルは読まない）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_REPO = HERE.parent
DEFAULT_SPEC = DEFAULT_REPO / "artifacts" / "w16-t11" / "numbers.r2.json"
DEFAULT_WORDS = DEFAULT_REPO / "artifacts" / "w16-t11" / "claim_words.r1.json"
DEFAULT_README = "public_overlay/README.md"
DEFAULT_PUBLIC_FILES = [
    "public_overlay/README.md",
    "public_overlay/KNOWN_ISSUES.md",
    "public_overlay/EVAL.md",
    "CHANGELOG.md",
]


class SourceUnreadable(Exception):
    pass


class UsageError(Exception):
    pass


# --------------------------------------------------------------------------- 仕様と出所

def load_spec(paths):
    rows = []
    seen = set()
    for p in paths:
        try:
            data = json.loads(Path(p).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise UsageError(f"仕様を読めない: {p}: {e}")
        for r in data:
            if r["id"] in seen:
                raise UsageError(f"仕様の id が重複: {r['id']}")
            seen.add(r["id"])
            rows.append(r)
    return rows


def git_show(repo, commit, path):
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "show", f"{commit}:{path}"],
            capture_output=True, check=False)
    except OSError as e:
        raise SourceUnreadable(f"SOURCE_UNREADABLE git を起動できない: {e}")
    if out.returncode != 0:
        raise SourceUnreadable(
            f"SOURCE_UNREADABLE {commit}:{path}: {out.stderr.decode('utf-8', 'replace').strip()}")
    return out.stdout.decode("utf-8")


def _flags(s):
    f = 0
    for ch in s or "":
        f |= {"S": re.S, "M": re.M, "I": re.I}[ch]
    return f


def extract(row, text):
    """(value, denominator) を出所の本文から取る。取れなければ ValueError(理由)。"""
    e = row["extract"]
    kind = e["kind"]
    if kind == "regex":
        ms = list(re.finditer(e["pattern"], text, _flags(e.get("flags"))))
        if len(ms) != 1:
            raise ValueError(f"正規表現の一致が {len(ms)} 回（ちょうど 1 回でなければならない）")
        g = e["groups"]
        m = ms[0]
        value = m.group(g["value"])
        den = m.group(g["denominator"]) if "denominator" in g else row["denominator"]
        return value, den
    if kind == "jsonl_count":
        lines = [json.loads(x) for x in text.splitlines() if x.strip()]
        where = e.get("where", {})
        n = sum(1 for d in lines if all(d.get(k) == v for k, v in where.items()))
        return str(n), str(len(lines))
    if kind == "unmeasured":
        if e["needle"] not in text:
            raise ValueError(f"「未測定」の根拠の語 {e['needle']!r} が出所に無い")
        return "未測定", "n/a"
    raise ValueError(f"未知の extract.kind: {kind}")


def check_spec(rows, repo):
    """出所の再計算。(problems, notes)。SourceUnreadable は上へ。"""
    problems = []
    cache = {}
    for r in rows:
        key = (r["commit"], r["source"])
        if key not in cache:
            cache[key] = git_show(repo, *key)
        text = cache[key]
        try:
            value, den = extract(r, text)
        except ValueError as e:
            problems.append(f"SPEC_EXTRACT {r['id']}: {e}")
            continue
        if value != r["value"]:
            problems.append(f"SPEC_VALUE {r['id']}: 仕様 {r['value']!r} / 出所 {value!r} ({r['source']})")
        if den != r["denominator"]:
            problems.append(f"SPEC_DENOMINATOR {r['id']}: 仕様 {r['denominator']!r} / 出所 {den!r} ({r['source']})")
        for a in r.get("aux", []):
            if a not in text:
                problems.append(f"SPEC_AUX {r['id']}: 補助の数字 {a!r} が出所に無い")
        if not r.get("set"):
            problems.append(f"SPEC_NO_SET {r['id']}: 集合名が無い")
    return problems


# --------------------------------------------------------------------------- 文の切り出し

FENCE = re.compile(r"^\s*```")
MARK = re.compile(r"\[(N-\d\d)\]")


def strip_front_matter(text):
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5:]
    return text


def units(text, include_code=False):
    """(行番号, 文) の列。表の 1 行は 1 つの文。コード囲みは既定で除く。"""
    out = []
    in_code = False
    for ln, line in enumerate(text.split("\n"), 1):
        if FENCE.match(line):
            in_code = not in_code
            continue
        if in_code:
            if include_code and line.strip():
                out.append((ln, line.strip()))
            continue
        s = line.strip()
        if not s:
            continue
        if s.startswith("|"):
            if re.match(r"^\|[\s:|-]+\|?$", s):
                continue
            out.append((ln, s))
            continue
        s = re.sub(r"^#+\s*(\d+[.)]?\s*)?", "", s)
        s = re.sub(r"^(\d+[.)]|[-*])\s+", "", s)
        for part in re.split(r"(?<=。)|(?<=[.!?])\s+", s):
            part = part.strip()
            if part:
                out.append((ln, part))
    return out


EXCLUDE = [
    r"`[^`]*`",
    r"\]\([^)]*\)",
    r"\[N-\d\d\]|\bN-\d\d\b",
    r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b\d{4}/\d{1,2}/\d{1,2}\b",
    r"\b\d{1,2}:\d{2}(?::\d{2})?\b",
    # 版番号だけを除く（v で始まる / 3 部分以上 / -preview・aN が付く）。印の無い 57.8・100.0 は除かない。
    r"\bv\d+(?:\.\d+)+(?:-preview|a\d+)?",
    r"\b\d+\.\d+\.\d+(?:\.\d+)*(?:-preview|a\d+)?",
    r"\b\d+\.\d+(?:-preview|a\d+)",
    r"\b(?=[0-9a-f]*[a-f])(?=[0-9a-f]*\d)[0-9a-f]{7,40}\b",
    r"§\s*\d+(?:\.\d+)*",
    r"\b[A-Z][A-Za-z0-9]*-[A-Za-z0-9]*\d[A-Za-z0-9]*\b",
    r"\b[A-Za-z]+\d+[A-Za-z]*\b",          # run1, v1, sha256, r9, T3, K652, A1 など（識別子）
    r"(?:layer|層)\s*\d+",                  # 層の名前（layer 0 / 層 0）
]
EXCLUDE_RE = [re.compile(p) for p in EXCLUDE]
TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?%?")


def numeric_tokens(s):
    for rx in EXCLUDE_RE:
        s = rx.sub(" ", s)
    toks = []
    for m in TOKEN.finditer(s):
        t = m.group(0).rstrip(",")
        toks.append(t)
    return toks


def table_cells(row):
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    return cells


# --------------------------------------------------------------------------- numbers

def split_languages(text):
    i = text.find("\n## 日本語")
    if i == -1:
        return text, ""
    return text[:i], text[i:]


def check_readme_numbers(rows, readme_text):
    by_id = {r["id"]: r for r in rows}
    body = strip_front_matter(readme_text)
    problems = []
    for ln, s in units(body):
        cells = table_cells(s) if s.startswith("|") else None
        marks = MARK.findall(s)
        if cells and re.fullmatch(r"N-\d\d", cells[0]):
            marks = [cells[0]] + marks
        toks = numeric_tokens(s)
        if not toks:
            continue
        if marks:
            allowed = set()
            for m in marks:
                if m not in by_id:
                    problems.append(f"README_UNKNOWN_ID L{ln}: {m}")
                    continue
                r = by_id[m]
                allowed.update([r["value"], r["denominator"]] + list(r.get("aux", [])))
            for t in toks:
                if t not in allowed:
                    problems.append(f"README_NUMBER_NOT_IN_SPEC L{ln}: {t!r} は {','.join(marks)} の値・分母・補助のどれでもない: {s[:100]}")
        else:
            problems.append(f"README_UNMARKED_NUMBER L{ln}: 印の無い文に数値 {toks}: {s[:100]}")
    # 表の突き合わせ（言語ごと）
    en, ja = split_languages(body)
    for lang, part in (("en", en), ("ja", ja)):
        found = {}
        for ln, s in units(part):
            if not s.startswith("|"):
                continue
            c = table_cells(s)
            if len(c) >= 4 and re.fullmatch(r"N-\d\d", c[0]):
                if c[0] in found:
                    problems.append(f"TABLE_DUPLICATE_ID[{lang}] L{ln}: {c[0]}")
                found[c[0]] = (ln, c)
        for rid, (ln, c) in found.items():
            if rid not in by_id:
                problems.append(f"TABLE_UNKNOWN_ID[{lang}] L{ln}: {rid}")
                continue
            r = by_id[rid]
            if r["kind"] == "unmeasured":
                if not c[2].startswith(r["value"]):
                    problems.append(f"TABLE_VALUE[{lang}] {rid}: 表 {c[2]!r} / 仕様 {r['value']!r}")
            elif c[2] != r["value"]:
                problems.append(f"TABLE_VALUE[{lang}] {rid}: 表 {c[2]!r} / 仕様 {r['value']!r}")
            if c[3] != r["denominator"]:
                problems.append(f"TABLE_DENOMINATOR[{lang}] {rid}: 表 {c[3]!r} / 仕様 {r['denominator']!r}")
        need = [r["id"] for r in rows if r.get("in_readme", True)]
        for rid in need:
            if rid not in found:
                problems.append(f"TABLE_MISSING[{lang}] {rid}: 仕様の行が {lang} の表に無い")
    return problems


def cmd_numbers(a):
    rows = load_spec(a.spec or [DEFAULT_SPEC])
    problems = check_spec(rows, a.repo)
    print(f"仕様 {len(rows)} 行を出所から再計算: 不一致 {len(problems)}")
    if not a.spec_only:
        text = Path(a.repo, a.readme).read_text(encoding="utf-8")
        rp = check_readme_numbers(rows, text)
        print(f"README ({a.readme}) の照合: 不一致 {len(rp)}")
        problems += rp
    for p in problems:
        print("NG", p)
    print("OK" if not problems else "FAIL")
    return 1 if problems else 0


# --------------------------------------------------------------------------- claims

def load_words(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return [re.compile(w) for k in ("ja", "en") for w in d[k]]


def check_claims(rows, words, files, repo):
    by_id = {r["id"]: r for r in rows}
    problems = []
    n_hits = 0
    for f in files:
        p = Path(repo, f)
        if not p.exists():
            raise UsageError(f"ファイルが無い: {f}")
        text = strip_front_matter(p.read_text(encoding="utf-8"))
        for ln, s in units(text, include_code=True):
            hit = [w.pattern for w in words if w.search(s)]
            if not hit:
                continue
            n_hits += 1
            marks = MARK.findall(s)
            cells = table_cells(s) if s.startswith("|") else []
            if cells and re.fullmatch(r"N-\d\d", cells[0]):
                marks = [cells[0]] + marks
            ok = False
            for m in marks:
                r = by_id.get(m)
                if r and r.get("denominator") not in (None, "", "n/a") and r.get("set"):
                    ok = True
            if not ok:
                problems.append(f"CLAIM_WITHOUT_DENOMINATOR {f}:{ln}: 語 {hit} 印 {marks}: {s[:100]}")
    return problems, n_hits


def cmd_claims(a):
    rows = load_spec(a.spec or [DEFAULT_SPEC])
    words = load_words(a.words)
    files = a.files or DEFAULT_PUBLIC_FILES
    problems, n = check_claims(rows, words, files, a.repo)
    print(f"言い切りの語を含む文 {n} 件、分母・集合名のある印の無いもの {len(problems)} 件（対象 {len(files)} ファイル）")
    for p in problems:
        print("NG", p)
    print("OK" if not problems else "FAIL")
    return 1 if problems else 0


# --------------------------------------------------------------------------- prepublish

SECRET_PATTERNS = {
    "SECRET_sk": r"sk-[A-Za-z0-9]{20,}",
    "SECRET_ghp": r"ghp_[A-Za-z0-9]{10,}",
    "SECRET_github_pat": r"github_pat_[A-Za-z0-9_]{10,}",
    "SECRET_hf": r"hf_[A-Za-z0-9]{20,}",
    "SECRET_aws": r"AKIA[0-9A-Z]{16}",
    "SECRET_privkey": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "SECRET_slack": r"xox[bp]-[A-Za-z0-9-]+",
}
PATH_PATTERNS = {
    "ABS_PATH_Users": r"/Users/",
    "ABS_PATH_home": r"/home/",
    "ABS_PATH_private_tmp": r"/private/tmp/",
    "INTERNAL_vera_impl": r"vera-impl",
    "INTERNAL_vera_wiring": r"vera-wiring",
    "INTERNAL_codex_corpus": r"vera-codex-corpus",
    "INTERNAL_hidden": r"hidden/",
    "EMAIL": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+",
}


def runtime_names(repo):
    names = {}
    u = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    if len(u) >= 3:
        names["LOCAL_USER_NAME"] = u
    try:
        out = subprocess.run(["git", "-C", str(repo), "config", "user.name"],
                             capture_output=True, text=True, check=False).stdout.strip()
        if len(out) >= 3:
            names["GIT_ACCOUNT_NAME"] = out
    except OSError:
        pass
    return names


def prepublish_scan(files, repo, extra_names=None):
    pats = {}
    pats.update({k: re.compile(v) for k, v in SECRET_PATTERNS.items()})
    pats.update({k: re.compile(v) for k, v in PATH_PATTERNS.items()})
    for k, v in {**runtime_names(repo), **(extra_names or {})}.items():
        pats[k] = re.compile(re.escape(v))
    hits = []
    for f in files:
        p = Path(repo, f)
        if not p.exists():
            raise UsageError(f"ファイルが無い: {f}")
        for ln, line in enumerate(p.read_text(encoding="utf-8").split("\n"), 1):
            for k, rx in pats.items():
                if rx.search(line):
                    hits.append((k, f, ln, line.strip()[:80]))
    return hits, sorted(pats)


def expand_files(repo, files):
    out = []
    for f in files:
        p = Path(repo, f)
        if p.is_dir():
            out += sorted(str(x.relative_to(repo)) for x in p.rglob("*") if x.is_file() and x.suffix in (".md", ".txt", ".json", ".toml", ".py"))
        else:
            out.append(f)
    return out


def cmd_prepublish(a):
    files = expand_files(a.repo, a.files or DEFAULT_PUBLIC_FILES)
    hits, kinds = prepublish_scan(files, a.repo)
    counts = {k: 0 for k in kinds}
    for k, *_ in hits:
        counts[k] += 1
    print(f"対象 {len(files)} ファイル、型 {len(kinds)} 種")
    for k in kinds:
        print(f"  {k}: {counts[k]}")
    for k, f, ln, line in hits:
        print("NG", k, f"{f}:{ln}", line)
    print(f"合計 {len(hits)} 件")
    print("OK" if not hits else "FAIL")
    return 1 if hits else 0


# --------------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("numbers", "claims", "prepublish"):
        sp = sub.add_parser(name)
        sp.add_argument("--repo", default=str(DEFAULT_REPO))
        sp.add_argument("--spec", action="append")
        if name == "numbers":
            sp.add_argument("--readme", default=DEFAULT_README)
            sp.add_argument("--spec-only", action="store_true")
        if name == "claims":
            sp.add_argument("--words", default=str(DEFAULT_WORDS))
        if name in ("claims", "prepublish"):
            sp.add_argument("--files", nargs="+")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        return {"numbers": cmd_numbers, "claims": cmd_claims, "prepublish": cmd_prepublish}[a.cmd](a)
    except SourceUnreadable as e:
        print("NG", e)
        print("FAIL")
        return 2
    except UsageError as e:
        print("usage:", e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
