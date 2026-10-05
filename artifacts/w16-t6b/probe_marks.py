"""Prints case<TAB>mark<TAB>reason for the t6b attack shapes via run_attest-level Verifier. Usage: python probe_marks.py [path-to-attest.py-to-load]
Builds each ledger with the helpers of tests/test_w16t6b_ledger_verify.py (T7 layout) in a temp dir."""
import importlib.util, sys, tempfile, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if len(sys.argv) > 1:       # load an alternative attest.py (e.g. the base commit's) as verantyx.attest
    import verantyx
    spec = importlib.util.spec_from_file_location("verantyx.attest", sys.argv[1]); m = importlib.util.module_from_spec(spec)
    sys.modules["verantyx.attest"] = m; spec.loader.exec_module(m); verantyx.attest = m
spec = importlib.util.spec_from_file_location("t6b", ROOT / "tests" / "test_w16t6b_ledger_verify.py"); T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)
from verantyx import ledger_events as LE
tmp = Path(tempfile.mkdtemp(prefix="t6bprobe_"))
tree = tmp / "tree"; (tree / "tests").mkdir(parents=True); (tree / "tests" / "test_a.py").write_text("def test_a():\n    assert True\n"); (tree / "pytest.ini").write_text("")
tree = str(tree)
def V(d, cmd, code, head=None, path=None):
    kw = {"ledger": path or T.evpath(d)}
    if head is not None:
        kw["ledger_head"] = head
    try:
        f = T.Verifier(tree, **kw).exit_fact(cmd, code)
    except TypeError as e:
        kw.pop("ledger_head", None); f = T.Verifier(tree, **kw).exit_fact(cmd, code); f = dict(f, reason=f["reason"] + "(head-not-supported)")
    return f
rows = []
def add(name, f): rows.append((name, f["mark"], f["reason"], ",".join(sorted({p["type"] for p in (f.get("evidence") or {}).get("problems", [])})) if f["mark"] == "TESTIMONY" and isinstance(f.get("evidence"), dict) and "problems" in f["evidence"] else ""))
A, B = T.CMD_A, T.CMD_B
d = T.a16(tmp, "a16"); add("a16", V(d, B, 0))
for v in ["prev_empty", "actor_str", "kind_note", "extra_key"]:
    d = T.a16(tmp, "v_" + v); r = T.rows_of(d)[0]
    if v == "prev_empty": r["prev"] = ""
    elif v == "actor_str": r["actor"] = "synth"
    elif v == "kind_note": r["kind"] = "note"
    elif v == "extra_key": r["extra"] = 1
    import hashlib, json
    r["sha"] = hashlib.sha256(json.dumps({k: x for k, x in r.items() if k != "sha"}, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    T.write_rows(d, [r]); add("a16v_" + v, V(d, B, 0))
def three(n): return T.three(tmp, n)
d = three("replace"); rs = T.rows_of(d); rs[1]["data"] = {"cmd": B, "exit_code": 0}; T.write_rows(d, T.recompute(rs), head=None); add("replace", V(d, B, 0))
d = three("delete"); rs = T.rows_of(d); del rs[1]; T.write_rows(d, T.recompute(rs), head=None); add("delete", V(d, A, 0))
d = three("reorder"); rs = T.rows_of(d); rs[0], rs[1] = rs[1], rs[0]; T.write_rows(d, T.recompute(rs), head=None); add("reorder", V(d, B, 3))
d = three("truncate"); T.write_rows(d, T.rows_of(d)[:-1], head=None); add("truncate", V(d, B, 3))
d = three("trunc_head"); pin = T.head_of(d); T.write_rows(d, T.rows_of(d)[:-1], head="last"); add("truncate+head(pinned)", V(d, B, 3, head=pin))
d = three("rep_head"); pin = T.head_of(d); rs = T.rows_of(d); rs[1]["data"] = {"cmd": B, "exit_code": 0}; T.write_rows(d, T.recompute(rs), head="last"); add("replace+head(pinned)", V(d, B, 0, head=pin)); add("replace+head(not pinned, known limit)", V(d, B, 0))
d = three("naive"); rs = T.rows_of(d); rs[1]["data"] = {"cmd": B, "exit_code": 0}; T.write_rows(d, rs, head=None); add("naive", V(d, B, 0))
d = three("nohead"); (d / "HEAD").unlink(); add("no_head", V(d, B, 3))
d = three("name"); c = tmp / "ev.jsonl"; c.write_bytes((d / "events.jsonl").read_bytes()); add("name(ev.jsonl)", V(d, B, 3, path=str(c)))
d = three("dir"); add("dir", V(d, B, 3, path=str(d)))
d = three("good"); add("good_exit3", V(d, B, 3)); add("good_exit0_mismatch", V(d, B, 0)); add("good_other_cmd", V(d, "python -m other", 0))
print("case\tmark\treason\tproblem_types")
for r in rows: print("\t".join(r))
