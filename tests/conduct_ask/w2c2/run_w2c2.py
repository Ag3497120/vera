#!/usr/bin/env python
"""W2-c2 measurement tool (not collected as a test: the name does not start with ``test_``).

Runs ``conduct_ask.answer_question`` over the frozen W2-c / W2-g data (``tests/conduct_ask/{fixtures,w2g,w2g2,w2g3}``) and
the W2-c2 data (``tests/conduct_ask/w2c2``) in two modes -- ``off`` (the rules alone) and ``fakemap`` (``vocab_llm="fake"``
with an EMPTY record-mapping script, i.e. a made-up mapping that never answers) -- with the code of any source tree, and
compares two runs.  The data and the frames are always read from this tree; the code is read from ``--code-tree``.

  run     --code-tree DIR --label NAME --out DIR     results.jsonl + summary.json
  recount DIR                                        rebuild summary.json from results.jsonl; MATCH when identical
  diff    BEFORE AFTER --out DIR                     c1_diff.tsv + c1_summary.json (acceptance C1, safety lines S1-S3)
  c2      DIR                                        acceptance C2 on the new data (exit 0 only when all hold)
  probe   DIR                                        the b5_rule_probe.py way of counting, for every data set
  table   BEFORE AFTER                               the Markdown tables of docs/CONDUCT_ASK.md section 15 (stdout)
  bank    --out DIR                                  the new data in the shape b5_rule_probe.py reads

Round 3 (W2-c3) adds:
  sentences --code-tree DIR --out FILE               r3_sentences.jsonl through the code of DIR (off, empty made-up mapping, scripted)
  c2r3    DIR --base BASEDIR                         acceptance C2 as pre-registered in round 3 (D12); exit 0 only on C2R3_PASS
  table3  BEFORE AFTER                               the Markdown tables of docs/CONDUCT_ASK.md section 15 (stdout)
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
TREE = HERE.parents[2]
PY = "/Users/motonisihikoudai/vera-wiring/env/bin/python"
MAP_FAKE_EMPTY = HERE / "map_fake_empty.json"

FROZEN = ("fixtures", "w2g", "w2g2", "w2g3")
NEW = "w2c2"
SUPP = "supp"      # round-2 supplement (frozen before the round-2 code changes): tests/conduct_ask/w2c2/supp/
NEWSETS = (NEW, SUPP)
SET_DIRS = {s: TREE / "tests" / "conduct_ask" / s for s in FROZEN + (NEW,)}
SET_DIRS[SUPP] = TREE / "tests" / "conduct_ask" / NEW / SUPP
MODES = ("off", "fakemap")
R3_SENTENCES = HERE / "r3_sentences.jsonl"
R3_SCRIPTS = HERE / "r3_scripts"
REVERTED = ("NEGATED", "INVERTED", "NO_ALLOWLIST")        # round 3: put back to the base code (auditor's ruling of 2026-10-03 14:05)
KEPT = ("WIDER", "BUILTIN")
B2_ITEMS = ("w2c2-negated-route-06", "w2c2-no_allowlist-route-01", "w2c2-no_allowlist-route-02", "w2c2-no_allowlist-route-03",
            "w2c2-no_allowlist-route-04", "w2c2-no_allowlist-route-05", "w2c2-no_allowlist-route-06", "w2c2-no_allowlist-route-07",
            "w2c2-no_allowlist-route-10")                 # the nine route sentences of the original data that a later W2-c rule hands up
SIX = ("decision", "answer", "answer_option_index", "escalate_reason", "escalate_detail", "mapping_outcome")

TRAPS = {"WIDER": "TERM_IN_WIDER_PHRASE", "NEGATED": "NEGATED_QUESTION", "INVERTED": "INVERTED_QUESTION",
         "BUILTIN": "BUILTIN_PROTECTED", "NO_ALLOWLIST": "NO_ALLOWLIST"}
TRAP_DETAILS = tuple(TRAPS.values())
TRAP_OF_DETAIL = {v: k for k, v in TRAPS.items()}
TRACE_KEYS = ("negation", "wider_phrase", "wider_phrase_head_type", "mapping_gate", "permission")
C1_FIELDS = ("decision", "answer", "answer_option_index", "escalate_reason", "escalate_detail")


# ---------------------------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------------------------

def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def load_items(set_name: str) -> list[dict[str, Any]]:
    """Items of one set in one shape: id, set, frame (path), question, options, exp (decision/index/answer), meta."""
    d = SET_DIRS[set_name]
    path = d / "items.jsonl"
    if not path.exists():
        return []
    out = []
    for r in _read_jsonl(path):
        if set_name in NEWSETS:
            t = r["truth"]
            exp = {"decision": t["decision"], "answer_option_index": t.get("answer_option_index"), "answer": t.get("answer")}
            meta = {"trap": r["trap"], "group": r["group"], "lang": r.get("lang"), "expect_rule": r.get("expect_rule")}
        else:
            e = r["expect"]
            exp = {"decision": e["decision"], "answer_option_index": e.get("answer_option_index"), "answer": e.get("answer")}
            meta = {"trap": None, "group": None, "lang": r.get("lang"), "expect_rule": None}
        out.append({"set": set_name, "id": r["id"], "frame": str(d / "frames" / (r["frame_id"] + ".md")),
                    "question": r["question"], "options": r.get("options"), "exp": exp, "meta": meta})
    return out


def all_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for s in FROZEN + NEWSETS:
        items.extend(load_items(s))
    return items


# ---------------------------------------------------------------------------------------------
# run (parent spawns one child with a clean environment; the child imports the code from --code-tree)
# ---------------------------------------------------------------------------------------------

def _child(out_path: str, code_tree: str, map_fake: str) -> int:
    code_tree = os.path.realpath(code_tree) + os.sep
    from verantyx import conduct_ask    # noqa: PLC0415
    bad = [m.__file__ for n, m in sys.modules.items()
           if n.split(".")[0].startswith("verantyx") and getattr(m, "__file__", None)
           and not os.path.realpath(m.__file__).startswith(code_tree)]
    assert not bad, f"verantyx modules outside the code tree {code_tree}: {bad}"
    jobs = json.loads(sys.stdin.read())
    with open(out_path, "w", encoding="utf-8") as fh:
        for j in jobs:
            kw: dict[str, Any] = {}
            if j["mode"] == "fakemap":
                kw = {"vocab_llm": "fake", "map_fake": map_fake}
            try:
                res = conduct_ask.answer_question(j["frame"], j["question"], j["options"], **kw)
            except Exception as exc:    # the entry never raises; if it did that is a finding, not something to hide
                res = {"decision": "EXCEPTION", "escalate_reason": type(exc).__name__, "escalate_detail": str(exc)[:80]}
            m = res.get("mapping") or {}
            rule = m.get("rule") or {}
            ro = (res.get("trace") or {}).get("resolver_outcomes") or {}
            row = {"set": j["set"], "id": j["id"], "mode": j["mode"], "decision": res.get("decision"),
                   "answer": res.get("answer"), "answer_option_index": res.get("answer_option_index"),
                   "escalate_reason": res.get("escalate_reason"), "escalate_detail": res.get("escalate_detail"),
                   "mapping_outcome": m.get("outcome"), "mapping_rule_reason": rule.get("reason"),
                   "mapping_rule_detail": rule.get("detail"), "trace_keys": {k: ro[k] for k in TRACE_KEYS if k in ro},
                   "exp": j["exp"], "meta": j["meta"]}
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return 0


def cmd_run(code_tree: str, label: str, out: str) -> int:
    code_tree = str(Path(code_tree).resolve())
    outdir = Path(out).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    jobs = [{"set": it["set"], "id": it["id"], "mode": mode, "frame": it["frame"], "question": it["question"],
             "options": it["options"], "exp": it["exp"], "meta": it["meta"]} for it in all_items() for mode in MODES]
    env = {"HOME": os.environ.get("HOME", "/"), "PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHONPATH": code_tree, "TMPDIR": "/tmp"}
    rows_path = outdir / "results.jsonl"
    p = subprocess.run([PY, str(Path(__file__).resolve()), "_child", str(rows_path), code_tree, str(MAP_FAKE_EMPTY)],
                       input=json.dumps(jobs, ensure_ascii=False), env=env, cwd=str(outdir), capture_output=True, text=True,
                       timeout=1800)
    if p.returncode != 0:
        sys.stderr.write(p.stderr[-3000:])
        return p.returncode
    rows = _read_jsonl(rows_path)
    summary = make_summary(rows)
    summary["label"] = label
    summary["code_tree"] = code_tree
    summary["code_sha256"] = _sha(Path(code_tree) / "verantyx" / "conduct_ask.py")
    (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} rows to {rows_path}")
    return 0


def _sha(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------------------------

def _rule_view(row: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """(reason, detail) of the RULE layer's result: the final one with the mapping off, the mapping's ``rule`` with it on."""
    if row["mode"] == "fakemap":
        return row.get("mapping_rule_reason"), row.get("mapping_rule_detail")
    return row.get("escalate_reason"), row.get("escalate_detail")


def trap_fired(row: dict[str, Any]) -> Optional[str]:
    """The trap (one of the five) whose detail the rule layer's result carries, else None."""
    _, det = _rule_view(row)
    return TRAP_OF_DETAIL.get(det) if det in TRAP_DETAILS else None


def rule_raised(row: dict[str, Any]) -> bool:
    """The b5_rule_probe.py notion: with the made-up mapping, ``mapping.outcome`` starts with NOT_ASKED."""
    return row["mode"] == "fakemap" and str(row.get("mapping_outcome") or "").startswith("NOT_ASKED")


def answer_matches(row: dict[str, Any]) -> bool:
    e = row["exp"]
    if row["decision"] != "answer" or e["decision"] != "answer":
        return False
    if e.get("answer_option_index") is not None:
        return row.get("answer_option_index") == e["answer_option_index"]
    return str(row.get("answer")).strip() == str(e.get("answer")).strip()


def make_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    per: dict[str, Any] = {}
    for s in FROZEN + NEWSETS:
        for mode in MODES:
            rs = [r for r in rows if r["set"] == s and r["mode"] == mode]
            if not rs:
                continue
            key = f"{s}/{mode}"
            dec = collections.Counter(f"{r['exp']['decision']}->{r['decision']}" for r in rs)
            fired = collections.Counter(f"{trap_fired(r)}/exp_{r['exp']['decision']}" for r in rs if trap_fired(r))
            raised = collections.Counter(f"{r.get('mapping_rule_detail')}/exp_{r['exp']['decision']}" for r in rs if rule_raised(r))
            wrong = [r["id"] for r in rs if r["decision"] == "answer" and not answer_matches(r)]
            per[key] = {"n": len(rs), "decisions": dict(sorted(dec.items())), "trap_fired": dict(sorted(fired.items())),
                        "rule_raised_by_detail": dict(sorted(raised.items())),
                        "rule_raised_total": sum(raised.values()),
                        "rule_raised_by_trap": sum(v for k, v in raised.items() if k.split("/")[0] in TRAP_DETAILS),
                        "wrong_answers": wrong}
    return {"rows": len(rows), "per": per}


def cmd_recount(d: str) -> int:
    p = Path(d)
    rows = _read_jsonl(p / "results.jsonl")
    saved = json.loads((p / "summary.json").read_text(encoding="utf-8"))
    fresh = make_summary(rows)
    same = all(saved.get(k) == v for k, v in fresh.items())
    print("MATCH" if same else "MISMATCH")
    return 0 if same else 1


# ---------------------------------------------------------------------------------------------
# diff (C1)
# ---------------------------------------------------------------------------------------------

def _index(d: str) -> dict[tuple[str, str, str], dict[str, Any]]:
    return {(r["set"], r["id"], r["mode"]): r for r in _read_jsonl(Path(d) / "results.jsonl")}


def _fields(mode: str) -> tuple[str, ...]:
    return C1_FIELDS + (("mapping_outcome",) if mode == "fakemap" else ())


def _kind(b: dict[str, Any], a: dict[str, Any]) -> str:
    if b["decision"] == "escalate" and a["decision"] == "answer":
        return "escalate->answer(correct)" if answer_matches(a) else "escalate->answer(WRONG)"
    if b["decision"] == "answer" and a["decision"] != "answer":
        return "answer->escalate"
    if b["decision"] == "answer" and a["decision"] == "answer":
        return "answer->other answer"
    if (b["mode"] == "off" and b.get("escalate_reason") == "FRAME_SILENT" and a.get("escalate_reason") == "VOCAB_UNMAPPED"
            and b.get("escalate_detail") == a.get("escalate_detail")):
        return "FRAME_SILENT->VOCAB_UNMAPPED"
    if (b["mode"] == "off" and b.get("escalate_detail") == "TERM_IN_WIDER_PHRASE" and a.get("escalate_reason") == "FRAME_SILENT"
            and a.get("escalate_detail") == "NO_RECORD_DECIDES"):
        return "TERM_IN_WIDER_PHRASE->NO_RECORD_DECIDES(narrow reading also silent)"
    if b["mode"] == "fakemap" and str(b.get("mapping_outcome") or "").startswith("NOT_ASKED") \
            and not str(a.get("mapping_outcome") or "").startswith("NOT_ASKED"):
        return "NOT_ASKED->mapping"
    return "other"


def compute_diff(before: str, after: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    bi, ai = _index(before), _index(after)
    missing = sorted(set(bi) ^ set(ai))
    changes: list[dict[str, Any]] = []
    for key in sorted(set(bi) & set(ai)):
        b, a = bi[key], ai[key]
        changed = [f for f in _fields(b["mode"]) if b.get(f) != a.get(f)]
        if not changed:
            continue
        changes.append({"set": key[0], "id": key[1], "mode": key[2], "frozen": key[0] in FROZEN,
                        "exp_decision": b["exp"]["decision"], "trap_before": trap_fired(b), "trap_after": trap_fired(a),
                        "fields": changed, "before": {f: b.get(f) for f in _fields(b["mode"])},
                        "after": {f: a.get(f) for f in _fields(b["mode"])}, "kind": _kind(b, a)})
    frozen_keys = [k for k in bi if k[0] in FROZEN and k in ai]
    s1_became = sorted(f"{k[1]}/{k[2]}" for k in frozen_keys
                       if bi[k]["exp"]["decision"] == "escalate" and bi[k]["decision"] != "answer" and ai[k]["decision"] == "answer")
    s1_after = sorted(f"{k[1]}/{k[2]}" for k in frozen_keys if ai[k]["exp"]["decision"] == "escalate" and ai[k]["decision"] == "answer")
    s2_after = sorted(f"{k[1]}/{k[2]}" for k in frozen_keys
                      if ai[k]["exp"]["decision"] == "answer" and ai[k]["decision"] == "answer" and not answer_matches(ai[k]))
    s2_new = sorted(f"{k[1]}/{k[2]}" for k in frozen_keys
                    if ai[k]["exp"]["decision"] == "answer" and ai[k]["decision"] == "answer" and not answer_matches(ai[k])
                    and (bi[k]["decision"] != "answer" or answer_matches(bi[k])))
    s3 = [c for c in changes if c["frozen"] and c["mode"] == "off" and c["before"]["decision"] == "escalate"
          and c["after"]["decision"] == "answer"]
    s3_bad = [f"{c['id']}" for c in s3 if not c["kind"].endswith("(correct)")]
    fc = [c for c in changes if c["frozen"]]
    summ = {
        "frozen_questions": len({(k[0], k[1]) for k in frozen_keys}),
        "frozen_rows_compared": len(frozen_keys),
        "missing_keys": [list(k) for k in missing],
        "S1_became_answer_when_expected_escalate": {"count": len(s1_became), "ids": s1_became},
        "S1_after_answer_when_expected_escalate_total": {"count": len(s1_after), "ids": s1_after},
        "S2_wrong_answer_when_expected_answer_after": {"count": len(s2_after), "ids": s2_after},
        "S2_new_wrong_answer": {"count": len(s2_new), "ids": s2_new},
        "S3_off_escalate_to_answer": {"count": len(s3), "all_match_expectation": not s3_bad, "not_matching": s3_bad,
                                      "ids": [c["id"] for c in s3]},
        "C1_changed_rows": len(fc),
        "C1_changed_questions": len({(c["set"], c["id"]) for c in fc}),
        "C1_by_mode": dict(collections.Counter(c["mode"] for c in fc)),
        "C1_questions_by_mode": {m: len({(c["set"], c["id"]) for c in fc if c["mode"] == m}) for m in MODES},
        "C1_by_expectation": dict(collections.Counter(f"exp_{c['exp_decision']}" for c in fc)),
        "C1_by_trap_before": dict(collections.Counter(str(c["trap_before"]) for c in fc)),
        "C1_by_kind": dict(collections.Counter(c["kind"] for c in fc)),
        "C1_by_mode_and_kind": dict(collections.Counter(f"{c['mode']}/{c['kind']}" for c in fc)),
        "C1_by_mode_trap_expectation": dict(collections.Counter(
            f"{c['mode']}/{c['trap_before']}/exp_{c['exp_decision']}" for c in fc)),
        "S_lines_hold": not s1_became and not s2_new and not s3_bad and not missing,
    }
    return changes, summ


def cmd_diff(before: str, after: str, out: str) -> int:
    changes, summ = compute_diff(before, after)
    outdir = Path(out)
    outdir.mkdir(parents=True, exist_ok=True)
    cols = ["set", "id", "mode", "exp_decision", "trap_before", "trap_after", "kind", "fields", "before", "after"]
    with open(outdir / "c1_diff.tsv", "w", encoding="utf-8") as fh:
        fh.write("\t".join(cols) + "\n")
        for c in changes:
            if not c["frozen"]:
                continue
            fh.write("\t".join(json.dumps(c[k], ensure_ascii=False) if isinstance(c[k], (dict, list)) else str(c[k]) for k in cols) + "\n")
    with open(outdir / "w2c2_diff.tsv", "w", encoding="utf-8") as fh:
        fh.write("\t".join(cols) + "\n")
        for c in changes:
            if c["frozen"]:
                continue
            fh.write("\t".join(json.dumps(c[k], ensure_ascii=False) if isinstance(c[k], (dict, list)) else str(c[k]) for k in cols) + "\n")
    (outdir / "c1_summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: summ[k] for k in ("C1_changed_rows", "C1_changed_questions", "C1_questions_by_mode", "S_lines_hold")}))
    return 0


# ---------------------------------------------------------------------------------------------
# C2
# ---------------------------------------------------------------------------------------------

def _new_rows(d: str, set_name: str = NEW) -> dict[str, dict[str, dict[str, Any]]]:
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for r in _read_jsonl(Path(d) / "results.jsonl"):
        if r["set"] == set_name:
            out.setdefault(r["id"], {})[r["mode"]] = r
    return out


def judge_c2(rows: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    """The C2 definition, judged from result rows alone (the same judgement is made independently in the test)."""
    verdicts: list[dict[str, Any]] = []
    for iid, modes in sorted(rows.items()):
        off, fm = modes["off"], modes["fakemap"]
        grp, trap = off["meta"]["group"], off["meta"]["trap"]
        fm_asked = not str(fm.get("mapping_outcome") or "").startswith("NOT_ASKED")
        det = TRAPS[trap]
        fire = (trap_fired(off) == trap) or (trap_fired(fm) == trap)
        why: list[str] = []
        if grp == "raise":
            want = tuple(off["meta"]["expect_rule"][k] for k in ("reason", "detail"))
            for r in (off, fm):
                if r["decision"] != "escalate":
                    why.append(f"{r['mode']}:decision={r['decision']}")
                elif (r["escalate_reason"], r["escalate_detail"]) != want:
                    why.append(f"{r['mode']}:rule={r['escalate_reason']}/{r['escalate_detail']}")
            if fm_asked:
                why.append(f"fakemap:{fm.get('mapping_outcome')}")
        elif grp == "route":
            if not fm_asked:
                why.append(f"fakemap:not_routed({fm.get('escalate_reason')}/{fm.get('escalate_detail')})")
            for r in (off, fm):
                if r["decision"] == "answer" and not answer_matches(r):
                    why.append(f"{r['mode']}:WRONG_ANSWER")
        elif grp == "transfer":
            if not fm_asked:
                why.append(f"fakemap:not_routed({fm.get('escalate_reason')}/{fm.get('escalate_detail')})")
            for r in (off, fm):
                if r["decision"] != "escalate":
                    why.append(f"{r['mode']}:decision={r['decision']}")
        verdicts.append({"id": iid, "trap": trap, "group": grp, "detail": det, "base_fire": fire, "pass": not why, "why": why,
                         "off": f"{off['decision']} {off['escalate_reason']}/{off['escalate_detail']}",
                         "fakemap": f"{fm['decision']} {fm.get('mapping_outcome')} | rule={fm.get('mapping_rule_reason')}/{fm.get('mapping_rule_detail')}"})
    return {"verdicts": verdicts}


def cmd_c2(d: str, set_name: str = NEW) -> int:
    rows = _new_rows(d, set_name)
    if not rows:
        print("NO_NEW_DATA")
        return 1
    print(f"# set: {set_name} ({SET_DIRS[set_name].relative_to(TREE)})")
    v = judge_c2(rows)["verdicts"]
    print("id\ttrap\tgroup\ttrap_fires_in_this_run\tpass\toff\tfakemap\twhy")
    for x in v:
        print("\t".join([x["id"], x["trap"], x["group"], "yes" if x["base_fire"] else "no", "yes" if x["pass"] else "NO",
                         x["off"], x["fakemap"], ";".join(x["why"])]))
    print("---")
    for trap in TRAPS:
        for g in ("raise", "route", "transfer"):
            xs = [x for x in v if x["trap"] == trap and x["group"] == g]
            print(f"{trap}/{g}: n={len(xs)} pass={sum(x['pass'] for x in xs)} trap_fires_in_this_run={sum(x['base_fire'] for x in xs)}")
    core = [x for x in v if x["group"] in ("raise", "route")]
    ok = all(x["pass"] for x in core)
    print(f"RAISE_AND_ROUTE_ALL_PASS: {ok}")
    print(f"TRANSFER_PASS: {sum(x['pass'] for x in v if x['group'] == 'transfer')}/{sum(1 for x in v if x['group'] == 'transfer')}")
    print(f"RAISE_ROUTE_TRAP_FIRES_ALL_YES: {all(x['base_fire'] for x in core)}")
    print("C2_PASS" if ok else "C2_FAIL")
    return 0 if ok else 1


# ---------------------------------------------------------------------------------------------
# probe (the b5_rule_probe.py way of counting)
# ---------------------------------------------------------------------------------------------

def cmd_probe(d: str) -> int:
    rows = [r for r in _read_jsonl(Path(d) / "results.jsonl") if r["mode"] == "fakemap"]
    groups = {"frozen (fixtures+w2g+w2g2+w2g3)": [r for r in rows if r["set"] in FROZEN], "new (w2c2)": [r for r in rows if r["set"] == NEW],
              "supplement (w2c2/supp)": [r for r in rows if r["set"] == SUPP]}
    for name, rs in groups.items():
        print(f"== {name}: {len(rs)} questions, fakemap (empty made-up mapping)")
        c = collections.Counter((r["exp"]["decision"], r["decision"], str(r.get("mapping_outcome"))[:40]) for r in rs)
        for k, n in sorted(c.items(), key=lambda x: -x[1]):
            print(n, k)
        print("--- rule details for answerable items that were not asked")
        c2 = collections.Counter(str(r.get("mapping_rule_detail"))[:40] for r in rs if r["exp"]["decision"] == "answer" and rule_raised(r))
        for k, n in c2.most_common(20):
            print(n, k)
        print("--- rule details for escalate-expected items that were not asked")
        c3 = collections.Counter(str(r.get("mapping_rule_detail"))[:40] for r in rs if r["exp"]["decision"] == "escalate" and rule_raised(r))
        for k, n in c3.most_common(20):
            print(n, k)
        print(f"answerable and raised by the rule layer: {sum(c2.values())} of {sum(1 for r in rs if r['exp']['decision'] == 'answer')}")
        print(f"escalate-expected and raised by the rule layer: {sum(c3.values())} of {sum(1 for r in rs if r['exp']['decision'] == 'escalate')}")
        print(f"escalate-expected and answered: {sum(1 for r in rs if r['exp']['decision'] == 'escalate' and r['decision'] == 'answer')}")
    return 0


# ---------------------------------------------------------------------------------------------
# table (docs section 15)
# ---------------------------------------------------------------------------------------------

def _raised_count(rows: list[dict[str, Any]], sets: tuple[str, ...], exp: str, detail: Optional[str]) -> int:
    n = 0
    for r in rows:
        if r["set"] not in sets or r["mode"] != "fakemap" or r["exp"]["decision"] != exp or not rule_raised(r):
            continue
        det = r.get("mapping_rule_detail")
        if detail is None or det == detail:
            n += 1
    return n


def _off_fired_count(rows: list[dict[str, Any]], sets: tuple[str, ...], exp: str, detail: str) -> int:
    return sum(1 for r in rows if r["set"] in sets and r["mode"] == "off" and r["exp"]["decision"] == exp
               and r.get("escalate_detail") == detail)


def cmd_table(before: str, after: str) -> int:
    b = _read_jsonl(Path(before) / "results.jsonl")
    a = _read_jsonl(Path(after) / "results.jsonl")
    fro, new = FROZEN, (NEW,)
    nq = lambda rows, sets, exp: len({(r["set"], r["id"]) for r in rows if r["set"] in sets and r["exp"]["decision"] == exp})  # noqa: E731
    out: list[str] = []
    out.append("**表 15-1 規則層で上がる問の数**（`--vocab-llm fake` ＋ 空の対応づけの台本 = 作り物の対応づけ。`mapping.outcome` が `NOT_ASKED` で始まる問を、`mapping.rule.detail` 別に数えた。前 = 基点 `5cae978` のコード、後 = 変更後のコード）")
    out.append("")
    out.append("| detail | 凍結データ 期待 answer 前 | 後 | 凍結データ 期待 escalate 前 | 後 | 新データ 期待 answer 前 | 後 | 新データ 期待 escalate 前 | 後 |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for det in TRAP_DETAILS:
        cells = []
        for sets in (fro, new):
            for exp in ("answer", "escalate"):
                cells += [str(_raised_count(b, sets, exp, det)), str(_raised_count(a, sets, exp, det))]
        out.append(f"| `{det}` | " + " | ".join(cells) + " |")
    cells = []
    for sets in (fro, new):
        for exp in ("answer", "escalate"):
            tb = sum(_raised_count(b, sets, exp, d) for d in TRAP_DETAILS)
            ta = sum(_raised_count(a, sets, exp, d) for d in TRAP_DETAILS)
            cells += [str(tb), str(ta)]
    out.append("| 5 つの罠の計 | " + " | ".join(cells) + " |")
    cells = []
    for sets in (fro, new):
        for exp in ("answer", "escalate"):
            ob = _raised_count(b, sets, exp, None) - sum(_raised_count(b, sets, exp, d) for d in TRAP_DETAILS)
            oa = _raised_count(a, sets, exp, None) - sum(_raised_count(a, sets, exp, d) for d in TRAP_DETAILS)
            cells += [str(ob), str(oa)]
    out.append("| 罠以外の規則の計 | " + " | ".join(cells) + " |")
    cells = []
    for sets in (fro, new):
        for exp in ("answer", "escalate"):
            n = nq(b, sets, exp)
            cells += [str(n), str(n)]
    out.append("| 問の総数 | " + " | ".join(cells) + " |")
    out.append("")
    out.append("**表 15-2 規則だけ（`off`）で罠の detail を返した問の数**（reason は問わない。上げ続けた問も、別の reason で上げ直した問も数える）")
    out.append("")
    out.append("| detail | 凍結データ 期待 answer 前 | 後 | 凍結データ 期待 escalate 前 | 後 | 新データ 期待 answer 前 | 後 | 新データ 期待 escalate 前 | 後 |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for det in TRAP_DETAILS:
        cells = []
        for sets in (fro, new):
            for exp in ("answer", "escalate"):
                cells += [str(_off_fired_count(b, sets, exp, det)), str(_off_fired_count(a, sets, exp, det))]
        out.append(f"| `{det}` | " + " | ".join(cells) + " |")
    out.append("")
    changes, summ = compute_diff(before, after)
    out.append("**表 15-3 凍結データ（349 問 × 2 モード）で前後に変わった行（C1）と安全の線**")
    out.append("")
    out.append("| 項目 | 値 |")
    out.append("|---|---|")
    out.append(f"| 比べた凍結データの問 | {summ['frozen_questions']} |")
    out.append(f"| どれかの欄が変わった行（問 × モード） | {summ['C1_changed_rows']} |")
    out.append(f"| どれかの欄が変わった問 | {summ['C1_changed_questions']} |")
    for m in MODES:
        out.append(f"| 　うち `{m}` で変わった問 | {summ['C1_questions_by_mode'][m]} |")
    for k, v in sorted(summ["C1_by_mode_and_kind"].items()):
        out.append(f"| 　変化の種類 `{k}` | {v} |")
    out.append(f"| S1: 期待 escalate で、前は答えず後は答えた問 | {summ['S1_became_answer_when_expected_escalate']['count']} |")
    out.append(f"| S2: 期待 answer で、前は答え合っていた（または答えなかった）のに後に別の答えになった行 | {summ['S2_new_wrong_answer']['count']} |")
    out.append(f"| S3: `off` で escalate から answer に変わった行 | {summ['S3_off_escalate_to_answer']['count']}（全部が期待と一致: {summ['S3_off_escalate_to_answer']['all_match_expectation']}） |")
    out.append("")
    v = judge_c2(_new_rows(after))["verdicts"]
    out.append("**表 15-4 新データ（`tests/conduct_ask/w2c2/`）の C2 の判定（変更後のコード）**")
    out.append("")
    out.append("| 罠 | `raise` 合格/件数 | `route` 合格/件数 | `transfer` 合格/件数 |")
    out.append("|---|---|---|---|")
    for trap in TRAPS:
        cells = []
        for g in ("raise", "route", "transfer"):
            xs = [x for x in v if x["trap"] == trap and x["group"] == g]
            cells.append(f"{sum(x['pass'] for x in xs)}/{len(xs)}")
        out.append(f"| `{trap}` | " + " | ".join(cells) + " |")
    vb = judge_c2(_new_rows(before))["verdicts"]
    out.append("")
    out.append("**表 15-5 新データの同じ判定を基点のコードで取ったもの**（`raise` は基点でも上がるので合格、`route` は基点では誤って上げるので不合格になる）")
    out.append("")
    out.append("| 罠 | `raise` 合格/件数 | `route` 合格/件数 | `transfer` 合格/件数 |")
    out.append("|---|---|---|---|")
    for trap in TRAPS:
        cells = []
        for g in ("raise", "route", "transfer"):
            xs = [x for x in vb if x["trap"] == trap and x["group"] == g]
            cells.append(f"{sum(x['pass'] for x in xs)}/{len(xs)}")
        out.append(f"| `{trap}` | " + " | ".join(cells) + " |")
    for title, rdir in (("表 15-6 補いのデータ（`tests/conduct_ask/w2c2/supp/`、第 2 ラウンドの凍結）の C2 の判定（変更後のコード）", after),
                        ("表 15-7 補いのデータの同じ判定を基点のコードで取ったもの", before)):
        vs = judge_c2(_new_rows(rdir, SUPP))["verdicts"]
        out.append("")
        out.append(f"**{title}**")
        out.append("")
        out.append("| 罠 | `raise` 合格/件数 | `route` 合格/件数 |")
        out.append("|---|---|---|")
        for trap in ("NEGATED", "NO_ALLOWLIST"):
            cells = []
            for g in ("raise", "route"):
                xs = [x for x in vs if x["trap"] == trap and x["group"] == g]
                cells.append(f"{sum(x['pass'] for x in xs)}/{len(xs)}")
            out.append(f"| `{trap}` | " + " | ".join(cells) + " |")
    print("\n".join(out))
    return 0


# ---------------------------------------------------------------------------------------------
# bank (the shape b5_rule_probe.py reads)
# ---------------------------------------------------------------------------------------------

def cmd_bank(out: str) -> int:
    outdir = Path(out)
    (outdir / "frames").mkdir(parents=True, exist_ok=True)
    rows = _read_jsonl(SET_DIRS[NEW] / "items.jsonl")
    with open(outdir / "items.jsonl", "w", encoding="utf-8") as fh:
        for r in rows:
            e = {"frame_id": r["frame_id"], "question": r["question"], "options": r.get("options"), "decision": r["truth"]["decision"]}
            fh.write(json.dumps({"id": r["id"], "category": f"{r['trap']}/{r['group']}", "expect": e}, ensure_ascii=False) + "\n")
    for f in sorted((SET_DIRS[NEW] / "frames").glob("*.md")):
        shutil.copyfile(f, outdir / "frames" / f.name)
    print(f"wrote {len(rows)} items to {outdir}")
    return 0


# ---------------------------------------------------------------------------------------------
# round 3: sentences (a fixed list of sentences, run through the code of any tree)
# ---------------------------------------------------------------------------------------------

def _child_sentences(out_path: str, code_tree: str, map_fake: str) -> int:
    code_tree = os.path.realpath(code_tree) + os.sep
    from verantyx import conduct_ask, conduct_map    # noqa: PLC0415
    from verantyx.llm_choice import ChoiceLedger     # noqa: PLC0415
    from verantyx.project_frame import load_conduct_frame    # noqa: PLC0415
    bad = [m.__file__ for n, m in sys.modules.items()
           if n.split(".")[0].startswith("verantyx") and getattr(m, "__file__", None)
           and not os.path.realpath(m.__file__).startswith(code_tree)]
    assert not bad, f"verantyx modules outside the code tree {code_tree}: {bad}"
    jobs = json.loads(sys.stdin.read())
    with open(out_path, "w", encoding="utf-8") as fh:
        for j in jobs:
            for mode in j["modes"]:
                if mode == "off":
                    kw: dict[str, Any] = {}
                elif mode == "fakemap_empty":
                    kw = {"vocab_llm": "fake", "map_fake": map_fake}
                else:       # fakemap_script: a scripted (made-up) mapping with a fixed order, as tests/conduct_ask/map_helpers.py does
                    script = json.loads(Path(j["script_path"]).read_text(encoding="utf-8"))
                    view = conduct_ask.build_view(load_conduct_frame(j["frame"]))
                    mapper = conduct_map.RecordMapper(conduct_map.fake_pair(script, view, j["options"]), ChoiceLedger(None),
                                                      order_source=lambda n: list(range(n)))
                    kw = {"vocab_llm": "fake", "mapper": mapper}
                try:
                    res = conduct_ask.answer_question(j["frame"], j["question"], j["options"], **kw)
                except Exception as exc:
                    res = {"decision": "EXCEPTION", "escalate_reason": type(exc).__name__, "escalate_detail": str(exc)[:80]}
                m = res.get("mapping") or {}
                ro = (res.get("trace") or {}).get("resolver_outcomes") or {}
                row = {"id": j["id"], "mode": mode, "decision": res.get("decision"), "answer": res.get("answer"),
                       "answer_option_index": res.get("answer_option_index"), "escalate_reason": res.get("escalate_reason"),
                       "escalate_detail": res.get("escalate_detail"), "mapping_outcome": m.get("outcome"),
                       "mapping_exit_check": m.get("exit_check"), "mapping_gate": ro.get("mapping_gate")}
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return 0


def load_r3_sentences() -> list[dict[str, Any]]:
    return _read_jsonl(R3_SENTENCES)


def cmd_sentences(code_tree: str, out: str) -> int:
    code_tree = str(Path(code_tree).resolve())
    outp = Path(out).resolve()
    outp.parent.mkdir(parents=True, exist_ok=True)
    jobs = []
    for r in load_r3_sentences():
        job = {"id": r["id"], "frame": str(SET_DIRS[NEW] / "frames" / (r["frame_id"] + ".md")), "question": r["question"],
               "options": r["options"], "modes": ["off", "fakemap_empty"]}
        if r.get("script"):
            job["modes"].append("fakemap_script")
            job["script_path"] = str(R3_SCRIPTS / (r["script"] + ".json"))
        jobs.append(job)
    env = {"HOME": os.environ.get("HOME", "/"), "PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHONPATH": code_tree, "TMPDIR": "/tmp"}
    p = subprocess.run([PY, str(Path(__file__).resolve()), "_child_sentences", str(outp), code_tree, str(MAP_FAKE_EMPTY)],
                       input=json.dumps(jobs, ensure_ascii=False), env=env, cwd=str(outp.parent), capture_output=True, text=True,
                       timeout=1800)
    if p.returncode != 0:
        sys.stderr.write(p.stderr[-3000:])
        return p.returncode
    print(f"wrote {len(_read_jsonl(outp))} rows to {outp}")
    return 0


# ---------------------------------------------------------------------------------------------
# round 3: C2 as read in D12
# ---------------------------------------------------------------------------------------------

def _six(r: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(r.get(k) for k in SIX)


def judge_c2r3(after: str, base: str) -> dict[str, Any]:
    """C2-K (the two traps that were kept: raise and route, new data) and C2-R (the three that were put back: every row of the
    new data and of the supplement, both modes, the six fields equal to the base code's)."""
    a_new, b_new = _new_rows(after, NEW), _new_rows(base, NEW)
    a_sup, b_sup = _new_rows(after, SUPP), _new_rows(base, SUPP)
    reverted_details = {TRAPS[t] for t in REVERTED}
    table: list[dict[str, Any]] = []
    stopped: list[str] = []
    k_raise = [0, 0]
    k_route = [0, 0]
    r_same = [0, 0]
    transfer = [0, 0]
    transfer_rows: list[dict[str, Any]] = []
    for iid, modes in sorted(a_new.items()):
        off, fm = modes["off"], modes["fakemap"]
        trap, grp = off["meta"]["trap"], off["meta"]["group"]
        fm_asked = not str(fm.get("mapping_outcome") or "").startswith("NOT_ASKED")
        why: list[str] = []
        verdict = "-"
        if trap in KEPT and grp == "raise":
            want = tuple(off["meta"]["expect_rule"][k] for k in ("reason", "detail"))
            for r in (off, fm):
                if r["decision"] != "escalate":
                    why.append(f"{r['mode']}:decision={r['decision']}")
                elif (r["escalate_reason"], r["escalate_detail"]) != want:
                    why.append(f"{r['mode']}:rule={r['escalate_reason']}/{r['escalate_detail']}")
            if fm_asked:
                why.append(f"fakemap:{fm.get('mapping_outcome')}")
            k_raise[1] += 1
            k_raise[0] += not why
            verdict = "K-raise:" + ("PASS" if not why else "FAIL")
        elif trap in KEPT and grp == "route":
            for r in (off, fm):
                if r["decision"] == "answer" and not answer_matches(r):
                    why.append(f"{r['mode']}:WRONG_ANSWER")
            if not fm_asked:
                det = fm.get("mapping_rule_detail")
                if det in reverted_details:
                    verdict = "K-route:PASS(ROUTE_STOPPED_BY_REVERTED_TRAP)"
                    stopped.append(iid)
                else:
                    why.append(f"fakemap:stopped_by_{fm.get('mapping_rule_reason')}/{det}")
            if verdict == "-":
                verdict = "K-route:" + ("PASS" if not why else "FAIL")
            elif why:
                verdict = "K-route:FAIL"
            k_route[1] += 1
            k_route[0] += not why
        elif trap in REVERTED:
            verdict = "R:"
        if grp == "transfer":
            transfer[1] += 1
            transfer[0] += fm_asked
            transfer_rows.append({"id": iid, "trap": trap, "routed": fm_asked})
        table.append({"id": iid, "trap": trap, "group": grp, "verdict": verdict, "why": why,
                      "off": f"{off['decision']} {off['escalate_reason']}/{off['escalate_detail']}",
                      "fakemap": f"{fm['decision']} {fm.get('mapping_outcome')} | rule={fm.get('mapping_rule_reason')}/{fm.get('mapping_rule_detail')}"})
    different: list[str] = []
    for (am, bm) in ((a_new, b_new), (a_sup, b_sup)):
        for iid, modes in sorted(am.items()):
            if modes["off"]["meta"]["trap"] not in REVERTED:
                continue
            for mode in MODES:
                r_same[1] += 1
                if _six(modes[mode]) == _six(bm[iid][mode]):
                    r_same[0] += 1
                else:
                    different.append(f"{iid}/{mode}")
    for t in table:
        if t["trap"] in REVERTED and t["id"] in different_ids(different):
            t["verdict"] = "R:DIFFERENT_FROM_BASE"
        elif t["trap"] in REVERTED:
            t["verdict"] = "R:SAME_AS_BASE"
    b2_ok = all(i in a_new and a_new[i]["off"]["meta"]["trap"] in REVERTED for i in B2_ITEMS)
    ok = k_raise[0] == k_raise[1] and k_route[0] == k_route[1] and r_same[0] == r_same[1] and b2_ok
    return {"table": table, "k_raise": k_raise, "k_route": k_route, "stopped": stopped, "r_same": r_same, "different": different,
            "transfer": transfer, "transfer_rows": transfer_rows, "b2_ok": b2_ok, "pass": ok}


def different_ids(different: list[str]) -> set[str]:
    return {d.rsplit("/", 1)[0] for d in different}


def cmd_c2r3(d: str, base: str) -> int:
    j = judge_c2r3(d, base)
    print("id\ttrap\tgroup\tverdict\toff\tfakemap\twhy")
    for t in j["table"]:
        print("\t".join([t["id"], t["trap"], t["group"], t["verdict"], t["off"], t["fakemap"], ";".join(t["why"])]))
    print("---")
    print(f"C2K_RAISE: {j['k_raise'][0]}/{j['k_raise'][1]}")
    print(f"C2K_ROUTE: {j['k_route'][0]}/{j['k_route'][1]}")
    print(f"ROUTE_STOPPED_BY_REVERTED_TRAP: {j['stopped']}")
    print(f"C2R_SAME_AS_BASE: {j['r_same'][0]}/{j['r_same'][1]}")
    print(f"C2R_DIFFERENT_FROM_BASE: {j['different']}")
    print(f"B2_ITEMS (not judged as route): {list(B2_ITEMS)}")
    print(f"B2_ITEMS_ALL_IN_REVERTED_TRAPS: {j['b2_ok']}")
    print(f"TRANSFER_ROUTED: {j['transfer'][0]}/{j['transfer'][1]}")
    by_trap = collections.Counter((t["trap"], t["routed"]) for t in j["transfer_rows"])
    for trap in TRAPS:
        print(f"TRANSFER_ROUTED[{trap}]: {by_trap[(trap, True)]}/{by_trap[(trap, True)] + by_trap[(trap, False)]}")
    print("C2R3_PASS" if j["pass"] else "C2R3_FAIL")
    return 0 if j["pass"] else 1


# ---------------------------------------------------------------------------------------------
# round 3: table3 (docs section 15)
# ---------------------------------------------------------------------------------------------

def _wider_norm(v: Optional[str]) -> str:
    if v is None:
        return "(no wider-phrase step)"
    parts = v.split(":")
    if parts[:2] == ["ESCALATE", "EVIDENCE"]:
        return "ESCALATE:EVIDENCE:" + parts[2]
    return v


def cmd_table3(before: str, after: str) -> int:
    b = _read_jsonl(Path(before) / "results.jsonl")
    a = _read_jsonl(Path(after) / "results.jsonl")
    groups = (("凍結データ（349 問）", FROZEN), ("新データ（`w2c2`、159 問）", (NEW,)), ("補いのデータ（`w2c2/supp`、46 問）", (SUPP,)))
    nq = lambda rows, sets, exp: len({(r["set"], r["id"]) for r in rows if r["set"] in sets and r["exp"]["decision"] == exp})  # noqa: E731
    out: list[str] = []
    out.append("**表 15-1 規則層で上がる問の数**（`--vocab-llm fake` ＋ 空の対応づけの台本 = 作り物の対応づけ。`mapping.outcome` が `NOT_ASKED` で始まる問を、`mapping.rule.detail` 別に数えた。前 = 基点 `5cae978` のコード、後 = 第 3 ラウンドのコード）")
    for title, sets in groups:
        out.append("")
        out.append(f"{title}")
        out.append("")
        out.append("| detail | 期待 answer 前 | 後 | 期待 escalate 前 | 後 |")
        out.append("|---|---|---|---|---|")
        for det in TRAP_DETAILS:
            cells = []
            for exp in ("answer", "escalate"):
                cells += [str(_raised_count(b, sets, exp, det)), str(_raised_count(a, sets, exp, det))]
            out.append(f"| `{det}` | " + " | ".join(cells) + " |")
        cells = []
        for exp in ("answer", "escalate"):
            tb = sum(_raised_count(b, sets, exp, d) for d in TRAP_DETAILS)
            ta = sum(_raised_count(a, sets, exp, d) for d in TRAP_DETAILS)
            cells += [str(tb), str(ta)]
        out.append("| 5 つの罠の計 | " + " | ".join(cells) + " |")
        cells = []
        for exp in ("answer", "escalate"):
            ob = _raised_count(b, sets, exp, None) - sum(_raised_count(b, sets, exp, d) for d in TRAP_DETAILS)
            oa = _raised_count(a, sets, exp, None) - sum(_raised_count(a, sets, exp, d) for d in TRAP_DETAILS)
            cells += [str(ob), str(oa)]
        out.append("| 罠以外の規則の計 | " + " | ".join(cells) + " |")
        cells = []
        for exp in ("answer", "escalate"):
            n = nq(b, sets, exp)
            cells += [str(n), str(n)]
        out.append("| 問の総数 | " + " | ".join(cells) + " |")
    out.append("")
    changes, summ = compute_diff(before, after)
    out.append("**表 15-2 凍結データ（349 問 × 2 モード）で前後に変わった行（C1）と安全の線**")
    out.append("")
    out.append("| 項目 | 値 |")
    out.append("|---|---|")
    out.append(f"| 比べた凍結データの問 | {summ['frozen_questions']} |")
    out.append(f"| どれかの欄が変わった行（問 × モード） | {summ['C1_changed_rows']} |")
    out.append(f"| どれかの欄が変わった問 | {summ['C1_changed_questions']} |")
    for m in MODES:
        out.append(f"| 　うち `{m}` で変わった問 | {summ['C1_questions_by_mode'][m]} |")
    for k, v in sorted(summ["C1_by_mode_and_kind"].items()):
        out.append(f"| 　変化の種類 `{k}` | {v} |")
    out.append(f"| S1: 期待 escalate で、前は答えず後は答えた問 | {summ['S1_became_answer_when_expected_escalate']['count']} |")
    out.append(f"| S2: 期待 answer で、前は答え合っていた（または答えなかった）のに後に別の答えになった行 | {summ['S2_new_wrong_answer']['count']} |")
    out.append(f"| S3: `off` で escalate から answer に変わった行 | {summ['S3_off_escalate_to_answer']['count']}（全部が期待と一致: {summ['S3_off_escalate_to_answer']['all_match_expectation']}） |")
    out.append("")
    j = judge_c2r3(after, before)
    jb = judge_c2r3(before, before)
    out.append("**表 15-3 C2 の第 3 ラウンドの読み（D12）の判定**（`c2r3`。後 = 第 3 ラウンドのコードの結果、基点 = 基点の結果自身を入れたもの）")
    out.append("")
    out.append("| 項目 | 後 | 基点 |")
    out.append("|---|---|---|")
    out.append(f"| C2-K raise（残した罠 `WIDER`・`BUILTIN`、新データ）合格/件数 | {j['k_raise'][0]}/{j['k_raise'][1]} | {jb['k_raise'][0]}/{jb['k_raise'][1]} |")
    out.append(f"| C2-K route（同上）合格/件数 | {j['k_route'][0]}/{j['k_route'][1]} | {jb['k_route'][0]}/{jb['k_route'][1]} |")
    out.append(f"| 　うち `ROUTE_STOPPED_BY_REVERTED_TRAP` | {', '.join('`' + i + '`' for i in j['stopped']) or 'なし'} | {', '.join('`' + i + '`' for i in jb['stopped']) or 'なし'} |")
    out.append(f"| C2-R（戻した罠 3 つ、新データと補い、両モード）基点と 6 欄が一致した行/行数 | {j['r_same'][0]}/{j['r_same'][1]} | {jb['r_same'][0]}/{jb['r_same'][1]} |")
    out.append(f"| transfer（新データ、判定に入れない）対応づけに回った問/件数 | {j['transfer'][0]}/{j['transfer'][1]} | {jb['transfer'][0]}/{jb['transfer'][1]} |")
    by_trap = collections.Counter((t["trap"], t["routed"]) for t in j["transfer_rows"])
    by_trap_b = collections.Counter((t["trap"], t["routed"]) for t in jb["transfer_rows"])
    for trap in TRAPS:
        out.append(f"| 　`{trap}` の transfer | {by_trap[(trap, True)]}/{by_trap[(trap, True)] + by_trap[(trap, False)]} | {by_trap_b[(trap, True)]}/{by_trap_b[(trap, True)] + by_trap_b[(trap, False)]} |")
    out.append(f"| 判定に入れない元の新データの route 9 問（B2） | {len(B2_ITEMS)} 問、全部が戻した罠の側: {j['b2_ok']} | |")
    out.append(f"| C2R3 | {'PASS' if j['pass'] else 'FAIL'} | {'PASS' if jb['pass'] else 'FAIL'} |")
    out.append("")
    out.append("**表 15-4 D10: 広い語句の段（`trace.resolver_outcomes.wider_phrase`）の値別の件数**（凍結 349 ＋ 新 159 ＋ 補い 46 = 554 問。`off` は規則だけ、`fakemap` は作り物の対応づけ）")
    out.append("")
    out.append("| 値 | `off` | `fakemap` |")
    out.append("|---|---|---|")
    cnt = {m: collections.Counter(_wider_norm((r.get("trace_keys") or {}).get("wider_phrase")) for r in a if r["mode"] == m) for m in MODES}
    for k in sorted(set(cnt["off"]) | set(cnt["fakemap"])):
        out.append(f"| `{k}` | {cnt['off'][k]} | {cnt['fakemap'][k]} |")
    out.append("")
    out.append("**表 15-5 最終の出力の `FRAME_SILENT/TERM_IN_WIDER_PHRASE` と `VOCAB_UNMAPPED/TERM_IN_WIDER_PHRASE` の件数**")
    out.append("")
    out.append("| 最終の (reason, detail) | `off` 前 | 後 | `fakemap` 前 | 後 |")
    out.append("|---|---|---|---|---|")
    for rd in (("FRAME_SILENT", "TERM_IN_WIDER_PHRASE"), ("VOCAB_UNMAPPED", "TERM_IN_WIDER_PHRASE")):
        cells = []
        for m in MODES:
            for rows in (b, a):
                cells.append(str(sum(1 for r in rows if r["mode"] == m and (r.get("escalate_reason"), r.get("escalate_detail")) == rd)))
        out.append(f"| `{rd[0]}/{rd[1]}` | " + " | ".join(cells) + " |")
    print("\n".join(out))
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "_child":
        return _child(*argv[1:4])
    if argv and argv[0] == "_child_sentences":
        return _child_sentences(*argv[1:4])
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--code-tree", required=True)
    p.add_argument("--label", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("recount")
    p.add_argument("dir")
    p = sub.add_parser("diff")
    p.add_argument("before")
    p.add_argument("after")
    p.add_argument("--out", required=True)
    p = sub.add_parser("c2")
    p.add_argument("dir")
    p.add_argument("--set", default=NEW, choices=NEWSETS)
    p = sub.add_parser("probe")
    p.add_argument("dir")
    p = sub.add_parser("table")
    p.add_argument("before")
    p.add_argument("after")
    p = sub.add_parser("bank")
    p.add_argument("--out", required=True)
    p = sub.add_parser("sentences")
    p.add_argument("--code-tree", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("c2r3")
    p.add_argument("dir")
    p.add_argument("--base", required=True)
    p = sub.add_parser("table3")
    p.add_argument("before")
    p.add_argument("after")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        return cmd_run(a.code_tree, a.label, a.out)
    if a.cmd == "recount":
        return cmd_recount(a.dir)
    if a.cmd == "diff":
        return cmd_diff(a.before, a.after, a.out)
    if a.cmd == "c2":
        return cmd_c2(a.dir, a.set)
    if a.cmd == "probe":
        return cmd_probe(a.dir)
    if a.cmd == "table":
        return cmd_table(a.before, a.after)
    if a.cmd == "bank":
        return cmd_bank(a.out)
    if a.cmd == "sentences":
        return cmd_sentences(a.code_tree, a.out)
    if a.cmd == "c2r3":
        return cmd_c2r3(a.dir, a.base)
    if a.cmd == "table3":
        return cmd_table3(a.before, a.after)
    return 2


if __name__ == "__main__":
    sys.exit(main())
