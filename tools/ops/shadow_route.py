#!/usr/bin/env python3
"""段 1: 分業の影運用。チケットの課題宣言から `vera route` を呼び、結果を追記で記録する。

影運用の間、この道具の出力・記録で判断を変えない。記録はどの判断の入力にもしない。
課題 (role/kind/size) は人が宣言したものだけを使う。散文から推さない。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _common as C  # noqa: E402
from _common import ToolError  # noqa: E402

SCHEMA = "vera.ops.shadow.route/1"
FENCE_OPEN = "```shadow-task"
FENCE_CLOSE = "```"


def find_blocks(text):
    """行単位の完全一致で囲みを探す。各囲みの中身（文字列）の列を返す。"""
    blocks, cur = [], None
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if cur is None:
            if line == FENCE_OPEN:
                cur = []
        else:
            if line == FENCE_CLOSE:
                blocks.append("\n".join(cur))
                cur = None
            else:
                cur.append(line)
    if cur is not None:  # 閉じていない囲みは不正として 1 個に数える
        blocks.append(None)
    return blocks


def validate_decl(decl):
    """宣言の形と値の検査。値の一覧は verantyx.agent_routing から import する。"""
    from verantyx.agent_routing import ROLES, SIZES, TASK_KINDS

    if not isinstance(decl, dict) or not isinstance(decl.get("jobs"), list) or not decl["jobs"]:
        return False
    names = []
    for j in decl["jobs"]:
        if not isinstance(j, dict) or not isinstance(j.get("job"), str):
            return False
        t = j.get("task")
        if not isinstance(t, dict):
            return False
        if t.get("role") not in ROLES or t.get("kind") not in TASK_KINDS or t.get("size") not in SIZES:
            return False
        names.append(j["job"])
    if len(set(names)) != len(names):  # 同じ job 名の重複は不正（どちらも選ばない）
        return False
    return True


def load_decl(text, task_file):
    """(decl|None, task_source, task_status)。"""
    blocks = find_blocks(text)
    if len(blocks) >= 2:
        return None, "block", "TASK_DECLARATION_AMBIGUOUS"
    block_decl = None
    if len(blocks) == 1:
        try:
            if blocks[0] is None:
                raise ValueError
            block_decl = json.loads(blocks[0])
        except Exception:
            return None, "block", "TASK_DECLARATION_INVALID"
    file_decl = None
    if task_file is not None:
        try:
            file_decl = json.loads(Path(task_file).read_text(encoding="utf-8"))
        except Exception:
            return None, "task_file", "TASK_DECLARATION_INVALID"
    if block_decl is not None and file_decl is not None:
        if block_decl != file_decl:
            return None, "block", "TASK_DECLARATION_CONFLICT"
        decl, src = block_decl, "block"
    elif block_decl is not None:
        decl, src = block_decl, "block"
    elif file_decl is not None:
        decl, src = file_decl, "task_file"
    else:
        return None, "none", "TASK_NOT_DECLARED"
    if not validate_decl(decl):
        return None, src, "TASK_DECLARATION_INVALID"
    return decl, src, "OK"


def compose_explanation(agents_dir, policy):
    parts = []
    d = Path(agents_dir)
    files = sorted(d.glob("*.md"), key=lambda p: p.name) if d.is_dir() else []
    files = list(files)
    if Path(policy).is_file():
        files.append(Path(policy))
    texts = []
    for f in files:
        t = f.read_text(encoding="utf-8")
        texts.append(t)
        parts.append({"path": C.rel(f), "sha256": C.sha256_text(t)})
    return "\n".join(texts), parts


def classify(rc, out):
    """(shadow_class, vera欄)。最上位の欄だけを見る。"""
    v = {"called": True, "rc": rc, "decision": None, "agent": None, "undecided_reason": None,
         "abstention_type": None, "decided_by": None, "evidence": None}
    try:
        d = json.loads(out)
    except Exception:
        return "error", v
    if rc != 0 or not isinstance(d, dict):
        return "error", v
    v["decision"] = d.get("decision")
    v["agent"] = d.get("agent")
    v["undecided_reason"] = d.get("undecided_reason")
    ab = d.get("abstention")
    v["abstention_type"] = ab.get("type") if isinstance(ab, dict) else None
    v["decided_by"] = d.get("decided_by")
    v["evidence"] = d.get("evidence")
    if v["decision"] == "route":
        return "route", v
    if v["decision"] == "undecided":
        return "undecided", v
    return "error", v


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ticket")
    ap.add_argument("--task-file")
    ap.add_argument("--agents-dir")
    ap.add_argument("--policy")
    ap.add_argument("--log")
    ap.add_argument("--store-dir", help="explanations/ raw/ の置き場（既定: ログのあるディレクトリ）")
    ap.add_argument("--run-kind", choices=["operational", "acceptance"], default="operational")
    ap.add_argument("--placement")
    ap.add_argument("--no-placement", action="store_true")
    a = ap.parse_args(argv)
    try:
        return run(a)
    except ToolError as e:
        return C.fail(e)


def run(a):
    import os

    ticket = Path(a.ticket)
    C.refuse_hidden(ticket)
    if a.task_file:
        C.refuse_hidden(a.task_file)
    try:
        text = ticket.read_text(encoding="utf-8")
    except Exception as e:
        raise ToolError("TICKET_UNREADABLE", f"{ticket}: {type(e).__name__}")
    tk = {"path": C.rel(ticket), "sha256": C.sha256_text(text)}
    agents_dir = Path(a.agents_dir) if a.agents_dir else C.ROOT / "ops/agents"
    policy = Path(a.policy) if a.policy else C.ROOT / "ops/routing_policy.md"
    log = Path(a.log) if a.log else C.ROOT / "ops/shadow/route_log.jsonl"
    store = Path(a.store_dir) if a.store_dir else log.parent

    if a.no_placement:
        placement_path, plc = None, {"path": None, "content_sha256": None}
    else:
        placement_path = a.placement or os.environ.get("VERA_PLACEMENT") or C.DEFAULT_PLACEMENT
        plc = C.placement_info(placement_path)
    tree = C.tree_info()
    decl, src, status = load_decl(text, a.task_file)
    expl_text, parts = compose_explanation(agents_dir, policy)
    if status == "OK" and not parts:
        status = "NO_EXPLANATION"
    base = {"schema": SCHEMA, "type": "entry", "run_kind": a.run_kind, "ticket": tk,
            "task_source": src, "task_status": status, "placement": plc, "tree": tree, "verdict": None}
    expl = {"path": None, "sha256": None, "parts": parts}
    n = 0
    if status != "OK":
        e = dict(base, job=None, task=None, explanation=expl, raw=None, shadow_class="not_called",
                 vera={"called": False, "rc": None, "decision": None, "agent": None,
                       "undecided_reason": None, "abstention_type": None, "decided_by": None,
                       "evidence": None})
        e["ts"] = C.now_ts()
        e["entry_id"] = C.entry_id(e)
        C.append_jsonl(log, e)
        n += 1
    else:
        w = C.content_write(store / "explanations", expl_text, ".md")
        expl = {"path": C.rel(w["path"]), "sha256": w["sha256"], "parts": parts}
        for j in decl["jobs"]:
            rc, out, err = C.run_vera(
                ["route", "--explanation", w["path"], "--task", json.dumps(j["task"], ensure_ascii=False)],
                placement=placement_path)
            raw = C.rec_path(C.content_write(store / "raw", out, ".json"))
            cls, v = classify(rc, out)
            e = dict(base, job=j["job"], task=j["task"], explanation=expl, raw=raw, shadow_class=cls, vera=v)
            e["ts"] = C.now_ts()
            e["entry_id"] = C.entry_id(e)
            C.append_jsonl(log, e)
            n += 1
    print(json.dumps({"verdict": "RECORDED", "entries": n, "task_status": status, "log": str(log)},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
