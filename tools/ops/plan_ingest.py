#!/usr/bin/env python3
"""段 2: ops/decisions/*.md を人の記録として計画ソブリン（store_id plan）に取り込む。

影運用の間、この道具の出力・記録で判断を変えない。取り込みは追記のみで、
Vera がソブリンへ書く経路は作らない（vera ask の環境変数は子プロセスから消す）。
ソブリンの sqlite は直接開かず、vera sovereign の入口だけを通す。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _common as C  # noqa: E402
from _common import ToolError  # noqa: E402

PLAN_SCHEMA = "vera.ops.plan_record/1"
META_PREFIX = "<!-- ops-meta "
META_SUFFIX = " -->"
STORE_ID = "plan"
AUTHORS = ("owner", "auditor")


def parse_decision(text):
    """(meta, sections[(heading, author, body)]) か ToolError(reason)。"""
    lines = text.split("\n")
    first = lines[0] if lines else ""
    if not (first.startswith(META_PREFIX) and first.endswith(META_SUFFIX)):
        raise ToolError("MISSING_META")
    try:
        meta = json.loads(first[len(META_PREFIX):-len(META_SUFFIX)])
    except Exception:
        raise ToolError("META_NOT_JSON")
    if not isinstance(meta, dict) or not isinstance(meta.get("sections"), dict):
        raise ToolError("META_NO_SECTIONS")
    secs, cur = [], None
    for line in lines[1:]:
        if line.startswith("## "):
            cur = [line, []]
            secs.append(cur)
        elif cur is None:
            if line.strip():
                raise ToolError("TEXT_OUTSIDE_SECTION")
        else:
            cur[1].append(line)
    if not secs:
        raise ToolError("NO_SECTIONS")
    seen = set()
    for heading, _ in secs:  # 同じ見出しが 2 つ以上ある文書はどちらも選ばず拒否する
        if heading in seen:
            raise ToolError("DUPLICATE_SECTION", heading)
        seen.add(heading)
    out = []
    for heading, body in secs:
        author = meta["sections"].get(heading)
        if author not in AUTHORS:
            raise ToolError("MISSING_AUTHOR", heading)
        out.append((heading, author, "\n".join(body).strip("\n")))
    if set(meta["sections"]) != {h for h, _, _ in out}:
        raise ToolError("META_SECTION_NOT_IN_BODY")
    return meta, out


def vera_json(args):
    rc, out, err = C.run_vera(args, placement=None)
    try:
        return rc, json.loads(out)
    except Exception:
        return rc, None


def read_events(root):
    """events の各行（JSON）を返す。読めなければ ToolError。"""
    rc, out, err = C.run_vera(["sovereign", "events", "--root", str(root), "--store-id", STORE_ID], placement=None)
    evs = []
    for ln in out.splitlines():
        if not ln.strip():
            continue
        try:
            d = json.loads(ln)
        except Exception:
            raise ToolError("EVENTS_UNREADABLE", ln[:80])
        if "payload" not in d:
            raise ToolError("EVENTS_" + str(d.get("verdict", "UNREADABLE")))
        evs.append(d)
    if rc != 0:
        raise ToolError("EVENTS_RC_NONZERO", str(rc))
    return evs


def store_path(root):
    """registry が示す plan の path（なければ None）。"""
    rc, d = vera_json(["sovereign", "status", "--root", str(root), "--store-id", STORE_ID])
    if not d or d.get("verdict") != "ANSWER":
        return None, d
    for s in d.get("stores", []):
        if s.get("store_id") == STORE_ID:
            return s.get("path"), d
    return None, d


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root")
    ap.add_argument("--decisions")
    ap.add_argument("--owner", default="owner")
    a = ap.parse_args(argv)
    try:
        return run(a)
    except ToolError as e:
        print(json.dumps({"verdict": "INGEST_FAILED", "code": e.code, "detail": e.detail}, ensure_ascii=False))
        return 1


def run(a):
    root = Path(a.root) if a.root else C.ROOT / "ops/plan_sovereign"
    ddir = Path(a.decisions) if a.decisions else C.ROOT / "ops/decisions"
    C.refuse_hidden(root)
    C.refuse_hidden(ddir)
    expect = Path(os.path.realpath(str(root / "stores" / "plan.sqlite")))
    path, _ = store_path(root)
    if path is None:
        rc, d = vera_json(["sovereign", "create", "--root", str(root), "--store-id", STORE_ID, "--owner", a.owner])
        if not d or d.get("verdict") != "CREATED":
            raise ToolError("CREATE_FAILED", json.dumps(d, ensure_ascii=False))
        path, _ = store_path(root)
    if path is None or Path(os.path.realpath(path)) != expect:
        raise ToolError("PLAN_SOVEREIGN_PATH_ELSEWHERE", f"registry={path} expected={expect}")

    events = read_events(root)
    latest = {}  # (doc, section) -> 最新の plan_record 事件
    for ev in events:
        p = ev["payload"]
        if isinstance(p, dict) and p.get("schema") == PLAN_SCHEMA:
            k = (p.get("doc"), p.get("section"))
            if k not in latest or ev["seq"] > latest[k]["seq"]:
                latest[k] = ev

    appended = corrected = skipped = 0
    refused = []
    dreal = Path(os.path.realpath(str(ddir)))
    for f in sorted(ddir.glob("*.md"), key=lambda p: p.name):
        if Path(os.path.realpath(str(f))).parent != dreal:
            refused.append({"doc": f.name, "reason": "OUTSIDE_DECISIONS_DIR"})
            continue
        C.refuse_hidden(f)
        doc = f"ops/decisions/{f.name}"
        try:
            meta, secs = parse_decision(f.read_text(encoding="utf-8"))
        except ToolError as e:
            refused.append({"doc": doc, "reason": e.code + (f":{e.detail}" if e.detail else "")})
            continue
        for idx, (heading, author, body) in enumerate(secs):
            tsha = C.sha256_text(body)
            prev = latest.get((doc, heading))
            if prev is not None and prev["payload"].get("text_sha256") == tsha:
                skipped += 1
                continue
            payload = {"schema": PLAN_SCHEMA, "doc": doc, "section": heading, "section_index": idx,
                       "author": author, "text": body, "text_sha256": tsha,
                       "source": meta.get("source"), "source_lines": meta.get("source_lines"),
                       "source_sha256": meta.get("source_sha256")}
            if prev is not None:
                payload["corrects"] = prev["id"]
            rc, d = vera_json(["sovereign", "append", "--root", str(root), "--store-id", STORE_ID,
                               "--kind", "decision", "--payload", json.dumps(payload, ensure_ascii=False)])
            if not d or d.get("verdict") != "APPENDED":
                raise ToolError("APPEND_FAILED", json.dumps(d, ensure_ascii=False))
            if prev is not None:
                corrected += 1
            else:
                appended += 1
    print(json.dumps({"verdict": "INGESTED", "appended": appended, "corrected": corrected,
                      "skipped_unchanged": skipped, "refused": refused,
                      "store": {"path": str(expect), "file_sha256": C.sha256_file(expect)}},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
