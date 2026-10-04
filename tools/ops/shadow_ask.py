#!/usr/bin/env python3
"""段 2: 問いを質問の十字で計画ソブリンの記録に当て、結果を追記で記録する。

影運用の間、この道具の出力・記録で判断を変えない。返答は従来どおり監査役が行う。
ANSWER でも証拠（ソブリンの記録の文）を引けなければ answer_untraced として数える。
文書は記録の本文を空行で連結しただけで、見出し・出所などの構成した行を入れない。
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
import plan_ingest as P  # noqa: E402

SCHEMA = "vera.ops.shadow.ask/1"


def fold_events(events):
    """plan_record の事件を (doc, section) ごとに畳み、訂正されていないものだけを順に返す。"""
    recs = [e for e in events if isinstance(e["payload"], dict) and e["payload"].get("schema") == P.PLAN_SCHEMA]
    corrected = {e["payload"].get("corrects") for e in recs if e["payload"].get("corrects")}
    live = [e for e in recs if e["id"] not in corrected]
    live.sort(key=lambda e: (str(e["payload"].get("doc")), e["payload"].get("section_index", 0), e["seq"]))
    return live


def trace_sources(sources, doc_text, live):
    """sources の各 text が文書の部分文字列で、かつどの事件の text に含まれるか。"""
    if not sources:
        return False, []
    ids, ok = [], True
    for s in sources:
        t = s.get("text") if isinstance(s, dict) else None
        hit = [e["id"] for e in live if t and t in e["payload"]["text"]]
        if not t or t not in doc_text or not hit:
            ok = False
            continue
        for i in hit:
            if i not in ids:
                ids.append(i)
    return ok, ids


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("question")
    ap.add_argument("--asked-by", choices=["auditor", "mid", "implementer"], default="auditor")
    ap.add_argument("--context")
    ap.add_argument("--root")
    ap.add_argument("--log")
    ap.add_argument("--store-dir")
    ap.add_argument("--run-kind", choices=["operational", "acceptance"], default="operational")
    ap.add_argument("--placement")
    ap.add_argument("--no-placement", action="store_true")
    a = ap.parse_args(argv)
    try:
        return run(a)
    except ToolError as e:
        return C.fail(e)


def run(a):
    root = Path(a.root) if a.root else C.ROOT / "ops/plan_sovereign"
    log = Path(a.log) if a.log else C.ROOT / "ops/shadow/ask_log.jsonl"
    store = Path(a.store_dir) if a.store_dir else log.parent
    C.refuse_hidden(root)
    if a.no_placement:
        placement_path, plc = None, {"path": None, "content_sha256": None}
    else:
        placement_path = a.placement or os.environ.get("VERA_PLACEMENT") or C.DEFAULT_PLACEMENT
        plc = C.placement_info(placement_path)
    base = {"schema": SCHEMA, "type": "entry", "run_kind": a.run_kind, "question": a.question,
            "asked_by": a.asked_by, "context": a.context, "placement": plc, "tree": C.tree_info(),
            "verdict": None}
    sov = {"root": C.rel(root), "store_id": P.STORE_ID, "events_used": [], "state": "OK"}
    doc = {"path": None, "sha256": None, "map_path": None}
    vera = {"called": False, "rc": None, "verdict": None, "values": None, "sources": None,
            "basis_outcome": None}
    evidence, raw, cls, live = [], None, None, []

    # 1. ソブリンを読む（読めない型は ask を呼ばずに棄権として記録）
    expect = Path(os.path.realpath(str(root / "stores" / "plan.sqlite")))
    path, sd = P.store_path(root)
    if path is None:
        sov["state"] = (sd or {}).get("verdict", "UNREADABLE") if sd else "UNREADABLE"
    elif Path(os.path.realpath(path)) != expect:
        sov["state"] = "PLAN_SOVEREIGN_PATH_ELSEWHERE"
    else:
        try:
            live = fold_events(P.read_events(root))
            sov["events_used"] = [e["id"] for e in live]
            if not live:
                sov["state"] = "EMPTY"
        except ToolError as e:
            sov["state"] = e.code.replace("EVENTS_", "", 1)
    if sov["state"] != "OK":
        cls = "abstain"
    else:
        # 2. 文書の書き出し: 本文を空行 1 つで区切って連結するだけ
        dtext = "\n\n".join(e["payload"]["text"] for e in live) + "\n"
        w = C.content_write(store / "docs", dtext, ".md")
        mp = [{"id": e["id"], "doc": e["payload"]["doc"], "section": e["payload"]["section"],
               "text_sha256": e["payload"]["text_sha256"]} for e in live]
        m = C.content_write(store / "docs", json.dumps(mp, ensure_ascii=False, indent=1) + "\n", ".map.json")
        doc = {"path": C.rel(w["path"]), "sha256": w["sha256"], "map_path": C.rel(m["path"])}
        # 3. vera ask
        rc, out, err = C.run_vera(["ask", "--mode", "round5", "--document", w["path"], "--", a.question],
                                  placement=placement_path)
        raw = C.rec_path(C.content_write(store / "raw", out, ".json"))
        vera["called"], vera["rc"] = True, rc
        d = None
        try:
            d = json.loads(out)
        except Exception:
            pass
        if rc != 0 or not isinstance(d, dict):
            cls = "error"
        else:
            vera["verdict"] = d.get("verdict")
            vera["values"] = d.get("values")
            srcs = d.get("sources") or []
            vera["sources"] = [{"text": s.get("text"), "source": s.get("source")} for s in srcs if isinstance(s, dict)]
            bp = d.get("basis_policy")
            vera["basis_outcome"] = bp.get("outcome") if isinstance(bp, dict) else None
            if vera["verdict"] == "ANSWER":
                ok, evidence = trace_sources(srcs, dtext, live)
                cls = "answer" if ok else "answer_untraced"
            elif not vera["values"]:
                cls = "abstain"
            else:
                cls = "unclassified_output"
    e = dict(base, sovereign=sov, document=doc, vera=vera, evidence_events=evidence, raw=raw, shadow_class=cls)
    e["ts"] = C.now_ts()
    e["entry_id"] = C.entry_id(e)
    C.append_jsonl(log, e)
    print(json.dumps({"verdict": "RECORDED", "shadow_class": cls, "entry_id": e["entry_id"], "log": str(log)},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
