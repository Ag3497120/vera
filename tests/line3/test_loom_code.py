"""LOOM-code tests: the CODE tier's record index, the gates of a code thread, the tests step and the five tasks K1-K5
(docs/LINE3_LOOM_DESIGN.md 5.2, 10.2; T-LOOM-21..26; L-LOOM-11..13, L-LOOM-70..).

Owner OP-LOOM-2 (a) 「Python のトークン 1 つ、文ごとに 1 十字」.  The tests step runs pytest in a copy of the fixture (experiments/line3/loom/
code_harness.py) and appends an `attest` row; the loom package itself runs no process (test_loom_enforce reads its imports).
"""
import builtins
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys

import pytest

from verantyx.loom import code as codelib
from verantyx.loom import fixture as fx
from verantyx.loom import ledger as lg
from verantyx.loom import read as rd
from verantyx.loom import scripted_code as sc
from verantyx.loom.mcp import LoomServer, append_outside_row
from verantyx.loom.ops import normalize_task, task_view
from verantyx.loom.scripted import ScriptedWeaver, weave_tokyo
from loom_common import CORPUS, ROOT, TASKS, server, task as prose_task

FIXTURE = os.path.join(ROOT, "experiments/line3/loom/fixture_repo")
TASKS_FILE = os.path.join(ROOT, "experiments/line3/loom/tasks_code.jsonl")
_spec = importlib.util.spec_from_file_location("loom_code_harness", os.path.join(ROOT, "experiments/line3/loom/code_harness.py"))
harness = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(harness)


def reader(p):
    with open(p, "rb") as f:
        return f.read()


@pytest.fixture(scope="module")
def index():
    return fx.build_index(FIXTURE, reader)


def code_tasks(fixture=FIXTURE):
    rows = harness.load_tasks(TASKS_FILE, ROOT)
    for r in rows:
        r["fixture"] = fixture
    return rows


def code_server(tmp_path, fixture=FIXTURE):
    return LoomServer(code_tasks(fixture), str(tmp_path / "runs"))


def begun(srv, k="K1", run_id=None):
    w = ScriptedWeaver(srv, "code/" + k.lower(), "test-weaver", run_id)
    assert w.begin()["ok"]
    return w


def refusals_of(w):
    r = w.call("read")
    assert r["ok"], r
    return r["refusals"], r["text"]


def types_of(w):
    return [x["type"] for x in refusals_of(w)[0]]


def thread_of(w, stmts):
    sc.link_all(w, sc.weave_statements(w, stmts))


def S(*lines):
    """Statements from lines indented by 4 spaces per depth."""
    return [((len(l) - len(l.lstrip(" "))) // 4, [t for _, t in codelib.tokens_of(l.strip() + "\n")]) for l in lines]


# ---------------------------------------------------------------------------------------------------------------------
# the record index (L-LOOM-11, L-LOOM-70)
# ---------------------------------------------------------------------------------------------------------------------
def test_the_index_holds_the_package_and_not_the_tests(index):
    assert index.paths == ["calc/__init__.py", "calc/counter.py", "calc/fmt.py", "calc/ops.py"]
    assert not any(p.startswith("tests/") for p in index.paths)
    for name in ("double", "total", "show_sum", "square", "cube", "fmt_all"):         # the answers' names are in the held-out tests only
        assert index.occurrences(name) is None
    assert index.file_sha["calc/ops.py"] == hashlib.sha256(reader(os.path.join(FIXTURE, "calc/ops.py"))).hexdigest()


def test_every_token_has_path_line_col_provenance(index):
    occ = index.occurrences("mul")
    assert [(p, l, c) for p, l, c, _ in occ] == [("calc/__init__.py", 1, 26), ("calc/ops.py", 8, 4)]
    src = open(os.path.join(FIXTURE, "calc/ops.py"), encoding="utf-8").read().splitlines()
    assert src[7][4:7] == "mul"                                                        # col is 0-based, line is 1-based
    for surface, occs in index.postings.items():
        for p, l, c, sid in occs:
            text = open(os.path.join(FIXTURE, p), encoding="utf-8").read().splitlines()[l - 1]
            assert text[c:c + len(surface)] == surface and index.sentences[sid]["source"].split(":")[0] == p


def test_a_unit_provenance_carries_the_occurrences_and_the_file_shas(index):
    pv = index.prov("(")
    assert pv["tier"] == "CODE" and pv["n"] == len(index.postings["("]) > codelib.OCC_SHOWN
    assert len(pv["occ"]) == codelib.OCC_SHOWN and set(pv["files"]) == {o[0] for o in pv["occ"]}
    assert all(pv["files"][p] == index.file_sha[p] for p in pv["files"])


def test_logical_lines_are_the_sentences(index):
    by_source = {s["source"]: s for s in index.sentences}
    assert by_source["calc/counter.py:8"]["tokens"] == ["def", "bump", "(", "self", ",", "step", ")", ":"]
    assert by_source["calc/fmt.py:6"]["tokens"] == ["return", '"("', "+", "str", "(", "a", ")", "+", '", "', "+", "str", "(", "b", ")", "+", '")"']   # a STRING is one token
    assert [s["source"] for s in index.sentences] == sorted([s["source"] for s in index.sentences], key=lambda x: (x.split(":")[0], int(x.split(":")[1])))


def test_definitions_have_kind_and_scope(index):
    d = {(x["path"], x["name"], x["scope"]): x["kind"] for x in index.defs}
    assert d[("calc/ops.py", "ZERO", "<module>")] == "assign" and d[("calc/ops.py", "add", "<module>")] == "def"
    assert d[("calc/counter.py", "Counter", "<module>")] == "class" and d[("calc/counter.py", "bump", "Counter")] == "def"
    assert d[("calc/counter.py", "add", "<module>")] == "import" and d[("calc/ops.py", "out", "pairs")] == "assign"
    assert index.top_names("calc/ops.py") == ["ZERO", "add", "mul", "pairs"] and index.top_names("nowhere.py") == []
    assert index.module_path == {"calc": "calc/__init__.py", "calc.counter": "calc/counter.py", "calc.fmt": "calc/fmt.py", "calc.ops": "calc/ops.py"}
    assert index.defined_in("add") == ["calc/ops.py:4"]                               # an import is not where a name is defined


def test_the_index_is_deterministic_and_does_not_depend_on_the_order_or_the_folder(index, tmp_path):
    files = fx.read_files(FIXTURE, reader)
    again = codelib.CodeIndex(dict(reversed(list(files.items()))))
    assert again.sha == index.sha and again.postings == index.postings and again.defs == index.defs
    shutil.copytree(FIXTURE, str(tmp_path / "elsewhere"), ignore=shutil.ignore_patterns("__pycache__"))
    assert fx.build_index(str(tmp_path / "elsewhere"), reader).sha == index.sha
    (tmp_path / "elsewhere" / "calc" / "ops.py").write_text("ZERO = 1\n")
    assert fx.build_index(str(tmp_path / "elsewhere"), reader).sha != index.sha


def test_a_token_that_spans_lines_is_not_a_unit_and_a_bad_file_is_a_value_error():
    ix = codelib.CodeIndex({"m.py": b'x = """a\nb"""\ny = 1\n'})
    assert ix.occurrences('"""a\nb"""') is None and ix.occurrences("y") is not None and ix.occurrences("=") is not None
    with pytest.raises(ValueError):
        codelib.CodeIndex({"bad.py": b"def (:\n"})


def test_the_listing_skips_pycache_dotfolders_and_tests(tmp_path):
    for rel in ("a.py", "pkg/b.py", "tests/t.py", "pkg/test_x.py", "__pycache__/c.py", ".hid/d.py", "e.txt"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x = 1\n")
    assert fx.list_files(tmp_path) == ["a.py", "pkg/b.py"]
    assert codelib.module_of("pkg/__init__.py") == "pkg" and codelib.module_of("a.py") == "a"


# ---------------------------------------------------------------------------------------------------------------------
# lookup / add record / read_sentence on a code task
# ---------------------------------------------------------------------------------------------------------------------
def test_lookup_returns_record_tokens_with_provenance(tmp_path, index):
    w = begun(code_server(tmp_path))
    r = w.call("lookup", text="mul", tier="CODE")
    m = r["matches"][0]
    assert r["ok"] and m["tier"] == "CODE" and m["surface"] == "mul" and m["n"] == 2
    assert m["occ"] == [["calc/__init__.py", 1, 26], ["calc/ops.py", 8, 4]]
    assert [s["source"] for s in m["sentences"]] == ["calc/__init__.py:1", "calc/ops.py:8"]
    assert w.call("lookup", text="mul", tier="any")["matches"] == r["matches"]
    assert w.call("lookup", text="double", tier="CODE") == {"ok": True, "matches": []}
    assert w.call("lookup", text="mul", tier="WORD")["refusal"] == "tier_not_in_task"
    big = w.call("lookup", text="(", tier="CODE")["matches"][0]
    assert big["n"] == 15 and len(big["occ"]) == codelib.OCC_SHOWN and len(big["sids"]) == len({o[3] for o in index.postings["("]}) == 13 and len(big["sentences"]) == codelib.SENTENCES_SHOWN


def test_add_record_seats_a_unit_with_the_index_provenance(tmp_path, index):
    w = begun(code_server(tmp_path))
    r = w.call("add", text="mul", kind="record", tier="CODE")
    assert r["ok"] and r["prov"] == index.prov("mul") and r["kind"] == "record"
    assert w.call("add", text="double", kind="record", tier="CODE") ["refusal"] == "not_a_record"
    c = w.call("open_cross", tier="CODE", L=1)["cid"]
    assert w.call("seat", cid=c, seat="centre", uid=r["uid"])["ok"]
    w.call("link", cid=c)
    seg = [s for s in w.call("read")["annotated"] if s["kind"] == "record"][0]
    assert seg["s"] == "mul" and seg["tier"] == "CODE" and seg["prov"] == {"tier": "CODE", "n": 2}


def test_a_constructed_code_unit_must_not_be_a_token_the_fixture_has(tmp_path):
    w = begun(code_server(tmp_path))
    for tok in ("mul", "def", "(", ":", "return", "x"):
        r = w.call("add", text=tok, kind="constructed")
        assert r["refusal"] == "constructed_shadows_record" and r["detail"]["tiers"] == ["CODE"], tok
    for tok in ("double", "2", "'new'", "cube"):
        assert w.call("add", text=tok, kind="constructed")["ok"], tok
    assert w.call("add", text="a b", kind="constructed")["refusal"] == "bad_unit_text"           # the one-token rule still comes first


def test_read_sentence_of_a_code_task(tmp_path, index):
    w = begun(code_server(tmp_path))
    sid = [s["source"] for s in index.sentences].index("calc/ops.py:8")
    r = w.call("read_sentence", sid=sid)
    assert r["ok"] and r["source"] == "calc/ops.py:8" and r["units"] == {"CODE": ["def", "mul", "(", "a", ",", "b", ")", ":"]}
    assert w.call("read_sentence", sid=index.n_sentences)["refusal"] == "unknown_sid"


def test_a_code_task_without_a_fixture_keeps_the_typed_refusals(tmp_path):
    w = ScriptedWeaver(server(tmp_path), "code/ca", "m")
    w.begin()
    assert w.call("lookup", text="x", tier="CODE")["refusal"] == "code_index_unavailable"
    assert w.call("add", text="x", kind="record", tier="CODE")["refusal"] == "code_index_unavailable"
    assert w.call("read_sentence", sid=0)["refusal"] == "code_index_unavailable"
    assert w.call("add", text="x", kind="constructed")["ok"]                              # no index: no shadow check


def test_the_header_names_the_index_and_prose_is_unchanged(tmp_path, index):
    srv = code_server(tmp_path)
    w = begun(srv)
    assert srv.runs[w.run_id].run.header()["code_index_sha"] == index.sha
    ps = server(tmp_path / "p")
    res = ScriptedWeaver(ps, "demo/tokyo_ca", "m").begin()
    assert res["header"]["code_index_sha"] is None and set(res["task"]) == {"task_id", "text", "lang", "mode", "tiers", "caps"}


# ---------------------------------------------------------------------------------------------------------------------
# tasks: target / tests
# ---------------------------------------------------------------------------------------------------------------------
def test_the_code_task_bank_is_valid_and_the_view_carries_target_and_tests():
    rows = harness.load_tasks(TASKS_FILE, ROOT)
    assert [r["task_id"] for r in rows] == ["code/k1", "code/k2", "code/k3", "code/k4", "code/k5"]
    for r in rows:
        nt = normalize_task(r)
        tv = task_view(nt)
        assert tv["target"] == r["target"] and tv["tests"] == r["tests"] and "fixture" not in tv and "corpus" not in tv and tv["tiers"] == ["CODE"]
        assert os.path.isfile(os.path.join(FIXTURE, r["target"]["file"])) and all(os.path.isfile(os.path.join(FIXTURE, t)) for t in r["tests"])
    assert "target" not in task_view(normalize_task(prose_task("p")))


@pytest.mark.parametrize("bad", [{"target": {"file": "../x.py"}}, {"target": {"file": "/etc/x.py"}}, {"target": {"file": "a.txt"}}, {"target": "calc/ops.py"},
                                 {"target": {"file": "a.py", "line": 3}}, {"tests": []}, {"tests": ["a.sh"]}, {"tests": "tests/t.py"}, {"tests": ["a//b.py"]}])
def test_a_bad_target_or_tests_is_refused_at_load(bad):
    with pytest.raises(ValueError):
        normalize_task(dict({"task_id": "t", "text": "x", "lang": "code", "mode": "record_only"}, **bad))
    with pytest.raises(ValueError):
        normalize_task(dict({"task_id": "t", "text": "x", "lang": "prose", "mode": "record_only"}, target={"file": "a.py"}))


# ---------------------------------------------------------------------------------------------------------------------
# the gates, pure (gate_refusals)
# ---------------------------------------------------------------------------------------------------------------------
def gate(index, text, ctx=("ZERO", "add", "mul", "pairs")):
    n = len(text.splitlines())
    return codelib.gate_refusals(text, index, ctx, ["c%d" % (i + 1) for i in range(n)])


def kinds(rs):
    return [(r["type"], r.get("name") or r.get("construct") or r.get("module")) for r in rs]


def test_builtins_are_pinned_to_cpython_311():
    assert codelib.BUILTINS == tuple(sorted(n for n in dir(builtins) if n not in codelib.SITE_ADDED_BUILTINS)) or sys.version_info[:2] != (3, 11)
    assert list(codelib.BUILTINS) == sorted(codelib.BUILTINS) and set(codelib.BLOCKED_NAMES) <= set(codelib.BUILTINS)
    assert codelib.STDLIB_ALLOWED == ("math", "itertools", "functools", "collections", "re", "json", "fractions", "typing", "dataclasses", "operator", "string")


def test_definition_first_accepts_what_is_defined_earlier(index):
    ok = [
        "def f(x):\n    return mul(x, 2)\n",                                              # a context name (the target file's top level) and a parameter
        "def f(x):\n    return f(x)\n",                                                   # recursion: a def is bound before its body
        "y = 1\ndef g():\n    return y\n",                                               # an earlier module-level binding, seen from a body
        "def f(xs):\n    out = 0\n    for x in xs:\n        out = add(out, x)\n    return out\n",
        "def f(xs):\n    return [mul(x, x) for x in xs]\n",
        "def f(xs):\n    return [x for x in xs if x]\n",
        "from calc.ops import add\ndef f(a):\n    return add(a, a)\n",
        "import math\nz = math.floor(2)\n",
        "def f():\n    return len('a')\n",                                                # a builtin
        "a, b = 1, 2\nc = a + b\n",
    ]
    for t in ok:
        assert gate(index, t) == [], t


def test_definition_first_refuses_a_name_not_bound_earlier(index):
    r = gate(index, "def f(x):\n    return mul(x, y)\n")
    assert [(x["type"], x["name"], x["line"], x["cid"]) for x in r] == [("undefined_name", "y", 2, "c2")]
    assert gate(index, "def f(x):\n    return g(x)\ndef g(x):\n    return x\n")[0]["name"] == "g"        # a FORWARD reference is refused (L-LOOM-12)
    assert kinds(gate(index, "x = x + 1\n")) == [("undefined_name", "x")]                  # the value is read before the target is bound
    assert kinds(gate(index, "def f(x):\n    return x\ny = x\n")) == [("undefined_name", "x")]              # a parameter does not leak
    assert kinds(gate(index, "def f(xs):\n    return [i for i in xs]\nj = i\n")) == [("undefined_name", "i")]   # a comprehension variable does not leak
    assert kinds(gate(index, "def f(a=zz):\n    return a\n")) == [("undefined_name", "zz")]                    # a default is read in the enclosing scope


def test_a_name_of_another_module_is_not_a_context_name_and_the_refusal_says_where_it_is(index):
    r = gate(index, "def show(a):\n    return fmt_num(a)\n", ctx=("ZERO", "add", "mul", "pairs"))
    assert r[0]["name"] == "fmt_num" and r[0]["defined_in"] == ["calc/fmt.py:1"]
    assert gate(index, "def show(a):\n    return fmt_num(a)\n", ctx=index.top_names("calc/fmt.py")) == []
    assert gate(index, "def show(a):\n    return fmt_num(a)\n", ctx=("fmt_num",)) == []
    imp = "from calc.fmt import fmt_num\ndef show(a):\n    return fmt_num(a)\n"
    assert gate(index, imp) == []
    assert gate(index, "import calc.fmt\nx = calc.fmt.fmt_num(1)\n") == []


def test_the_import_gate(index):
    assert gate(index, "from calc.ops import add, mul\n") == [] and gate(index, "from calc import ops\n") == [] and gate(index, "import calc.ops\n") == []
    assert gate(index, "from math import floor\nimport json, re\n") == []
    bad = {
        "import os\n": ("os", "module"), "import calc.nosuch\n": ("calc.nosuch", "module"), "from os import path\n": ("os", "module"),
        "from calc.ops import nosuch\n": ("calc.ops", "name"), "from . import x\n": (".", "relative"), "from .ops import add\n": (".ops", "relative"),
        "import numpy\n": ("numpy", "module"),
    }
    for t, (mod, why) in bad.items():
        r = [x for x in gate(index, t) if x["type"] == "import_not_allowed"]
        assert len(r) == 1 and r[0]["module"] == mod and r[0]["reason"] == why and r[0]["line"] == 1, t
    # a refused import still binds its names: one refusal, not a cascade
    assert [x["type"] for x in gate(index, "from os import path\nx = path\n")] == ["import_not_allowed"]
    # no index (a code task without a fixture): only the stdlib list passes
    assert [x["type"] for x in codelib.gate_refusals("import calc.ops\nimport math\n", None, (), ["c1", "c2"])] == ["import_not_allowed"]


UNSUPPORTED = {
    "class A:\n    pass\n": "ClassDef", "async def f():\n    pass\n": "AsyncFunctionDef", "x = lambda a: a\n": "Lambda",
    "while True:\n    pass\n": "While", "try:\n    pass\nexcept E:\n    pass\n": "Try", "with a as b:\n    pass\n": "With",
    "def f():\n    global g\n": "Global", "del x\n": "Delete", "match x:\n    case 1:\n        pass\n": "Match",
    "@d\ndef f():\n    pass\n": "decorator", "def f():\n    yield 1\n": "Yield", "x = [i for i in a if i]\ny = {i for i in a}\n": "SetComp",
    "d = {1: 2}\n": "Dict", "s = {1}\n": "Set", "x = a if b else c\n": "IfExp", "x = f'{a}'\n": "JoinedStr", "if (n := 1):\n    pass\n": "NamedExpr",
    "x += 1\n": "AugAssign", "pass\n": "Pass", "assert x\n": "Assert", "raise E\n": "Raise", "from m import *\n": "star_import",
    "def f(*a):\n    pass\n": "def_signature", "def f(a, *, b):\n    pass\n": "def_signature", "def f(a: int):\n    pass\n": "annotation",
    "def f() -> int:\n    pass\n": "annotation", "f(*a)\n": "Starred", "f(**k)\n": "star_args", "1\n": "expr_statement", "'doc'\n": "expr_statement",
    "if a:\n    pass\nelse:\n    pass\n": "else_clause", "for i in a:\n    pass\nelse:\n    pass\n": "else_clause",
    "x = eval(a)\n": "call:eval", "exec(a)\n": "call:exec", "x = open(a)\n": "call:open", "getattr(a, b)\n": "call:getattr", "setattr(a, b, c)\n": "call:setattr",
    "compile(a, b, c)\n": "call:compile", "__import__(a)\n": "call:__import__", "x = yield\n": "Yield", "x = await y\n": "Await",
}


@pytest.mark.parametrize("text,construct", sorted(UNSUPPORTED.items()))
def test_unsupported_constructs_are_refused_with_a_typed_reason(index, text, construct):
    try:
        import ast
        ast.parse(text)
    except SyntaxError:
        pytest.skip("not valid at module level on this Python")
    r = [x for x in gate(index, text, ctx=("a", "b", "c", "x", "d", "E", "m", "f", "k", "y", "g", "n")) if x["type"] == "unsupported_construct"]
    assert construct in [x["construct"] for x in r], (text, r)
    assert all(isinstance(x["line"], int) for x in r)


def test_the_supported_subset_is_exactly_def_return_assign_call_if_for_import(index):
    text = ("import math\nfrom calc.ops import add\ndef f(a, b=1):\n    t = (a, b)\n    u = [a, b][0]\n    v = a.real\n    w = -a + b * 2 > 1 and not a\n"
            "    if a:\n        add(a, b)\n    for i in t:\n        u = u[0:1]\n    return [add(i, j) for i in t for j in u if i]\n")
    assert gate(index, text) == []


def test_several_gates_report_together_in_the_fixed_order(tmp_path):
    w = begun(code_server(tmp_path), "K1")
    thread_of(w, S("import os", "def f(x):", "    return mul(x, y)", "z = 1 ; w = 2"))
    rs, text = refusals_of(w)
    assert [x["type"] for x in rs] == ["undefined_name", "import_not_allowed", "cross_not_one_statement"]
    assert [x["cid"] for x in rs] == ["c3", "c1", "c4"]
    # an unsupported construct suppresses definition-first (a name in a tree the loom does not read is not judged)
    w2 = begun(code_server(tmp_path / "b"), "K1")
    thread_of(w2, S("import os", "def f(x):", "    return mul(x, y)", "x = lambda a: b"))
    assert [(x["type"], x.get("construct") or x["module"]) for x in refusals_of(w2)[0]] == [("import_not_allowed", "os"), ("unsupported_construct", "Lambda")]
    assert rd.REFUSAL_ORDER.index("parse_error") < rd.REFUSAL_ORDER.index("undefined_name") < rd.REFUSAL_ORDER.index("import_not_allowed") \
        < rd.REFUSAL_ORDER.index("unsupported_construct") < rd.REFUSAL_ORDER.index("cross_not_one_statement") < rd.REFUSAL_ORDER.index("layout_changed_tokens")
    assert "code_gates_incomplete" not in rd.REFUSAL_ORDER and not hasattr(codelib, "GATES_MISSING_IN_CORE")


# ---------------------------------------------------------------------------------------------------------------------
# the gates through read / emit
# ---------------------------------------------------------------------------------------------------------------------
def test_a_good_code_thread_has_no_refusal_and_no_code_gates_incomplete(tmp_path):
    w = begun(code_server(tmp_path), "K1")
    thread_of(w, S("def double(x):", "    return mul(x, 2)"))
    rs, text = refusals_of(w)
    assert rs == [] and text == "def double(x):\n    return mul(x, 2)\n"
    r = w.call("emit")
    assert r["ok"] and r["status"] == "emitted" and r["output_sha"] == hashlib.sha256(text.encode()).hexdigest()
    assert r["shares"]["constructed"] == len("double") + len("2") and r["shares"]["record"] > 0 and "".join(s["s"] for s in r["annotated"]) == text


def test_emit_refuses_with_the_typed_reason_and_the_run_stays_open(tmp_path):
    w = begun(code_server(tmp_path), "K1")
    thread_of(w, S("def double(x):", "    return mul(x, y)"))
    r = w.call("emit")
    assert r["ok"] is False and r["refusal"] == "undefined_name"
    d = r["detail"]["refusals"][0]
    assert d["name"] == "y" and d["line"] == 2 and d["cid"] == "c2" and d["defined_in"] == []
    assert w.call("status")["closed"] is None


def test_a_constructed_name_needs_a_definition_cross_earlier_in_the_thread(tmp_path):
    srv = code_server(tmp_path)
    w = begun(srv, "K1", "r1")
    thread_of(w, S("double2 = 1", "def f(x):", "    return mul(x, double2)"))
    assert refusals_of(w)[0] == []                                                      # the assignment cross comes first: bound
    w2 = begun(srv, "K1", "r2")
    cs = sc.weave_statements(w2, S("double2 = 1", "def f(x):", "    return mul(x, double2)"))
    sc.link_all(w2, [cs[1], cs[2], cs[0]])                                              # the same crosses, the definition last
    rs, _ = refusals_of(w2)
    assert [(x["type"], x["name"]) for x in rs] == [("undefined_name", "double2")]


def test_the_import_cross_must_come_before_the_use_and_the_refusal_names_the_module(tmp_path):
    w = begun(code_server(tmp_path), "K3", "k3a")
    thread_of(w, S("def f(a, b):", "    return fmt_num(add(a, b))"))
    rs, _ = refusals_of(w)
    assert [(x["type"], x["name"]) for x in rs] == [("undefined_name", "add")] and rs[0]["defined_in"] == ["calc/ops.py:4"]
    w2 = begun(code_server(tmp_path / "b"), "K3", "k3b")
    cs = sc.weave_statements(w2, S("def f(a, b):", "    return fmt_num(add(a, b))", "from calc . ops import add"))
    sc.link_all(w2, [cs[0], cs[1], cs[2]])                                               # the import last
    assert [x["type"] for x in refusals_of(w2)[0]] == ["undefined_name"]
    w3 = begun(code_server(tmp_path / "c"), "K3", "k3c")
    cs = sc.weave_statements(w3, S("def f(a, b):", "    return fmt_num(add(a, b))", "from calc . ops import add"))
    sc.link_all(w3, [cs[2], cs[0], cs[1]])
    assert refusals_of(w3)[0] == []


def test_import_not_allowed_through_the_loom(tmp_path):
    w = begun(code_server(tmp_path), "K1")
    thread_of(w, S("import os"))
    rs, text = refusals_of(w)
    assert text == "import os\n" and [(x["type"], x["module"], x["reason"], x["cid"]) for x in rs] == [("import_not_allowed", "os", "module", "c1")]


def test_unsupported_construct_through_the_loom(tmp_path):
    w = begun(code_server(tmp_path), "K1")
    thread_of(w, S("class A :", "    pass"))
    rs, _ = refusals_of(w)
    assert {x["type"] for x in rs} >= {"unsupported_construct"} and {x["construct"] for x in rs if x["type"] == "unsupported_construct"} == {"ClassDef", "Pass"}
    assert w.call("emit")["refusal"] == "unsupported_construct"


def test_one_statement_per_cross(tmp_path):
    w = begun(code_server(tmp_path), "K1")
    thread_of(w, S("a = 1 ; b = 2"))
    rs, _ = refusals_of(w)
    assert [(x["type"], x["reason"], x["statements"], x["cid"]) for x in rs] == [("cross_not_one_statement", "several_statements", 2, "c1")]
    w2 = begun(code_server(tmp_path / "b"), "K1")
    thread_of(w2, S("def f(a): return a"))                                               # a header and its body on one line
    assert [x["reason"] for x in refusals_of(w2)[0]] == ["several_statements"]
    w3 = begun(code_server(tmp_path / "c"), "K1")
    thread_of(w3, S("x = mul (", "1 , 2 )"))                                              # one statement over two crosses
    rs, text = refusals_of(w3)
    assert text == "x = mul(\n1, 2)\n" and [(x["reason"], x["line"], x["cid"]) for x in rs] == [("continuation", 2, "c2")]


def test_an_empty_cross_prints_nothing_and_the_line_numbers_follow_the_printing_crosses(tmp_path):
    w = begun(code_server(tmp_path), "K1")
    empty = w.call("open_cross", tier="CODE", L=1)["cid"]
    w.call("link", cid=empty)
    cs = sc.weave_statements(w, S("def f(x):", "    return mul(x, y)"))
    sc.link_all(w, cs)
    rs, text = refusals_of(w)
    assert text == "def f(x):\n    return mul(x, y)\n" and rs[0]["line"] == 2 and rs[0]["cid"] == cs[1]


def test_parse_error_stops_the_whole_text_gates_and_layout_changed_tokens_still_fires(tmp_path):
    w = begun(code_server(tmp_path), "K1")
    thread_of(w, S("def"))
    assert types_of(w) == ["parse_error"]
    w2 = begun(code_server(tmp_path / "b"), "K1")
    a = w2.call("add", text="1", kind="constructed")["uid"]
    b = w2.call("add", text=".", kind="record", tier="CODE")["uid"]
    c = w2.call("add", text="real", kind="constructed")["uid"]
    cid = w2.call("open_cross", tier="CODE", L=3)["cid"]
    w2.call("seat", cid=cid, seat="centre", uid=a)
    w2.call("seat_run", cid=cid, arm="+x", uids=[b, c])
    w2.call("link", cid=cid)
    assert "layout_changed_tokens" in types_of(w2)


def test_a_depth_that_does_not_match_the_statements_is_a_parse_error(tmp_path):
    w = begun(code_server(tmp_path), "K1")
    thread_of(w, [sc.S(0, "def f ( x ) :"), sc.S(0, "return x")])
    assert types_of(w) == ["parse_error"]


def test_the_whole_text_gates_run_for_a_code_task_without_a_fixture_too(tmp_path):
    w = ScriptedWeaver(server(tmp_path), "code/ca", "m")
    w.begin()
    def cross(toks, depth=0):
        us = [w.call("add", text=t, kind="constructed")["uid"] for t in toks]
        c = w.call("open_cross", tier="CODE", L=max(1, len(toks) - 1), depth=depth)["cid"]
        w.call("seat", cid=c, seat="centre", uid=us[0])
        w.call("seat_run", cid=c, arm="+x", uids=us[1:])
        w.call("link", cid=c)
    cross(["def", "f", "(", "x", ")", ":"])
    cross(["return", "x"], 1)
    r = w.call("emit")
    assert r["ok"] and r["text"] == "def f(x):\n    return x\n"


# ---------------------------------------------------------------------------------------------------------------------
# K1-K5
# ---------------------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def k_results(tmp_path_factory):
    rd_ = tmp_path_factory.mktemp("k")
    tasks = code_tasks()
    out = {}
    for k, var in (("K1", "reference"), ("K2", "reference"), ("K3", "naive"), ("K3", "reference"), ("K3", "wrong_arity"),
                   ("K4", "naive"), ("K4", "reference"), ("K5", "reference")):
        out[(k, var)] = harness.run_k(k, var, rd_, tasks)
    return out


EXPECT_TEXT = {
    ("K1", "reference"): "def double(x):\n    return mul(x, 2)\n",
    ("K2", "reference"): "def total(xs):\n    out = 0\n    for x in xs:\n        out = add(out, x)\n    return out\n",
    ("K3", "reference"): "from calc.ops import add\ndef show_sum(a, b):\n    return fmt_num(add(a, b))\n",
    ("K3", "wrong_arity"): "from calc.ops import add\ndef show_sum(a, b):\n    return fmt_num(add(a))\n",
    ("K4", "reference"): "def square(x):\n    return mul(x, x)\ndef cube(x):\n    return mul(x, square(x))\n",
    ("K5", "reference"): "def fmt_all(xs):\n    return [fmt_num(x) for x in xs]\n",
}


@pytest.mark.parametrize("key", sorted(EXPECT_TEXT))
def test_k_emits_the_expected_bytes(k_results, key):
    r = k_results[key]
    assert r["emit"]["ok"] and r["emit"]["text"] == EXPECT_TEXT[key]
    assert r["tests"]["status"] == "tested"
    assert r["tests"]["exit_code"] == (1 if key == ("K3", "wrong_arity") else 0), r["tests"]["tail"]


def test_k1_k2_k5_emit_and_their_tests_pass(k_results):
    for key in (("K1", "reference"), ("K2", "reference"), ("K5", "reference")):
        assert k_results[key]["emit"]["status"] == "emitted" and k_results[key]["tests"]["passed"] is True


def test_k3_and_k4_carelessly_woven_are_refused_with_undefined_name_and_leave_no_output(k_results):
    for k, name in (("K3", "add"), ("K4", "square")):
        r = k_results[(k, "naive")]
        assert r["emit"]["ok"] is False and r["emit"]["refusal"] == "undefined_name" and r["tests"] == {"status": "no_output"}
        d = r["emit"]["detail"]["refusals"]
        assert [(x["type"], x["name"]) for x in d] == [("undefined_name", name)]
        assert lg.emitted_output(r["run_dir"])["status"] == "no_output"
        assert lg.verify(r["run_dir"])["status"] == "OK"
    # the K3 refusal points at the import it needs
    assert k_results[("K3", "naive")]["emit"]["detail"]["refusals"][0]["defined_in"] == ["calc/ops.py:4"]


def test_k3_k4_repaired_runs_hold_both_the_refusal_and_the_emit(k_results):
    for k in ("K3", "K4"):
        rows = [json.loads(l) for l in open(os.path.join(k_results[(k, "reference")]["run_dir"], "ops.jsonl"), encoding="utf-8")]
        emits = [r for r in rows if r["op"] == "emit"]
        assert [e["result"].get("refusal", "ok") for e in emits] == ["undefined_name", "ok"]
        assert rows[-1]["op"] == "attest" and rows[-1]["actor"] == "harness" and rows[-1]["args"]["kind"] == "tests" and rows[-1]["args"]["exit_code"] == 0


def test_the_wrong_arity_call_is_not_a_static_gate_the_tests_step_catches_it(k_results):
    r = k_results[("K3", "wrong_arity")]
    assert r["emit"]["ok"] and r["tests"]["exit_code"] == 1 and "TypeError" in r["tests"]["tail"]


def test_the_attest_row_is_exact_and_carries_no_path_or_time(k_results):
    r = k_results[("K1", "reference")]
    rows = [json.loads(l) for l in open(os.path.join(r["run_dir"], "ops.jsonl"), encoding="utf-8")]
    a = rows[-1]
    assert a["op"] == "attest" and a["actor"] == "harness" and a["result"] == {"ok": True}
    args = dict(a["args"])
    isolation = args.pop("isolation")                                                          # LOOM-d2 (L-LOOM-86): the proof of the sandbox
    assert args == {"kind": "tests", "tests": ["tests/test_k1.py", "tests/test_ops.py"], "target": "calc/ops.py",
                    "code_index_sha": json.loads(open(os.path.join(r["run_dir"], "ops.jsonl"), encoding="utf-8").readline())["result"]["header"]["code_index_sha"],
                    "tests_sha": a["args"]["tests_sha"], "driver": "scripted", "isolation_token": None,
                    "text_sha": hashlib.sha256(EXPECT_TEXT[("K1", "reference")].encode()).hexdigest(), "exit_code": 0,
                    "outcome": "passed", "pytest_result": {"collected": 4, "failed": 0, "exitstatus": 0}, "expected_min": 4}       # L-LOOM-116
    assert len(a["args"]["tests_sha"]) == 64
    assert isolation["mechanism"] == "sandbox-exec" and isolation["network"] == "denied" and len(isolation["profile_sha"]) == 64
    assert isolation["probe"]["status"] == "passed" and all(isolation["probe"]["properties"].values()) and len(isolation["probe"]["properties"]) == 8
    assert set(isolation["probe"]) == {"status", "properties"}                                  # L-LOOM-117: no machine-dependent evidence in the hashed row
    blob = json.dumps(a["args"], ensure_ascii=False)
    for frag in ("/Users/", "/private/", "/var/folders", "/tmp", "loom_code_", "loom_decoy"):
        assert frag not in blob, frag


def test_the_fixture_is_red_for_the_new_functions_and_green_for_the_old_ones():
    base = harness.run_pytest(FIXTURE, "calc/ops.py", "", ["tests/test_ops.py", "tests/test_fmt.py", "tests/test_counter.py"])
    assert base["exit_code"] == 0
    assert harness.run_pytest(FIXTURE, "calc/ops.py", "", ["tests/test_k1.py"])["exit_code"] != 0                    # double does not exist yet
    assert harness.run_pytest(FIXTURE, "calc/ops.py", "def double(x):\n    return x\n", ["tests/test_k1.py"])["exit_code"] == 1   # a wrong double fails
    assert harness.run_pytest(FIXTURE, "calc/ops.py", "def double(x):\n    return mul(x, 2)\n", ["tests/test_k1.py"])["exit_code"] == 0
    assert not any(n == "__pycache__" for _, dirs, _f in os.walk(FIXTURE) for n in dirs)                                # the fixture itself is never written


def test_run_pytest_never_writes_the_real_fixture(tmp_path):
    before = {p: hashlib.sha256(reader(p)).hexdigest() for p in [os.path.join(d, f) for d, _, fs in os.walk(FIXTURE) for f in fs]}
    harness.run_pytest(FIXTURE, "calc/ops.py", "def double(x):\n    return mul(x, 2)\n", ["tests/test_k1.py"])
    after = {p: hashlib.sha256(reader(p)).hexdigest() for p in [os.path.join(d, f) for d, _, fs in os.walk(FIXTURE) for f in fs]}
    assert before == after


# ---------------------------------------------------------------------------------------------------------------------
# the ledger of a code run
# ---------------------------------------------------------------------------------------------------------------------
def test_a_code_run_verifies_and_replays_byte_for_byte(k_results):
    for key in sorted(k_results):
        d = k_results[key]["run_dir"]
        v = lg.verify(d)
        assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL", (key, v)
        rep = lg.replay(d)
        assert rep.identical and b"".join(rep.lines) == open(os.path.join(d, "ops.jsonl"), "rb").read()
    out = lg.emitted_output(k_results[("K5", "reference")]["run_dir"])
    assert out["status"] == "emitted" and out["text"] == EXPECT_TEXT[("K5", "reference")]


def test_a_changed_fixture_file_is_code_index_sha_mismatch(k_results, tmp_path):
    srv = code_server(tmp_path, fixture=str(tmp_path / "fx"))
    shutil.copytree(FIXTURE, str(tmp_path / "fx"), ignore=shutil.ignore_patterns("__pycache__"))
    w = begun(srv, "K1", "chg")
    sc.weave_k(w, "K1")
    d = srv.run_dir("chg")
    assert lg.verify(d)["status"] == "OK"
    with open(str(tmp_path / "fx" / "calc" / "ops.py"), "a") as f:
        f.write("\nEXTRA = 1\n")
    v = lg.verify(d)
    assert v["status"] == "REPLAY_INPUTS_MISMATCH" and v["replay"]["mismatch"] == "code_index_sha_mismatch"
    assert lg.emitted_output(d)["status"] == "run_not_verified"


def test_a_run_whose_fixture_is_missing_from_meta_is_a_typed_inputs_status(k_results, tmp_path):
    shutil.copytree(k_results[("K1", "reference")]["run_dir"], str(tmp_path / "copy"))
    meta = json.load(open(str(tmp_path / "copy" / "meta.json")))
    del meta["fixture"]
    json.dump(meta, open(str(tmp_path / "copy" / "meta.json"), "w"))
    v = lg.verify(str(tmp_path / "copy"))
    assert v["status"] == "REPLAY_INPUTS_MISMATCH" and v["replay"]["mismatch"] == "fixture_unresolved"
    meta["fixture"] = str(tmp_path / "no_such_folder")
    json.dump(meta, open(str(tmp_path / "copy" / "meta.json"), "w"))
    assert lg.verify(str(tmp_path / "copy"))["replay"]["mismatch"] in ("code_index_sha_mismatch", "fixture_unreadable")


def test_the_fixture_is_read_through_the_sandbox_and_a_link_out_of_it_is_refused(tmp_path):
    fxd = tmp_path / "fx"
    shutil.copytree(FIXTURE, str(fxd), ignore=shutil.ignore_patterns("__pycache__"))
    secret = tmp_path / "secret.py"
    secret.write_text("TOKEN = 1\n")
    os.symlink(str(secret), str(fxd / "calc" / "leak.py"))
    srv = code_server(tmp_path, fixture=str(fxd))
    assert srv.begin("code/k1", "m", "leak") == {"ok": False, "refusal": "path_outside_sandbox", "detail": {}}
    assert not os.path.exists(str(tmp_path / "runs" / "leak"))


def test_a_code_run_leaves_only_the_run_folder(tmp_path):
    before = {os.path.join(d, f): os.stat(os.path.join(d, f)).st_mtime_ns for d, _, fs in os.walk(FIXTURE) for f in fs}
    srv = code_server(tmp_path)
    w = begun(srv, "K1", "only")
    sc.weave_k(w, "K1")
    assert {os.path.join(d, f) for d, _, fs in os.walk(FIXTURE) for f in fs} == set(before)
    assert all(os.stat(p).st_mtime_ns == m for p, m in before.items())
    assert sorted(os.listdir(str(tmp_path / "runs" / "only"))) == [".lock", "HEAD", "meta.json", "ops.jsonl", "timing.jsonl"]


def test_a_second_process_can_append_the_attest_row(tmp_path):
    srv = code_server(tmp_path)
    w = begun(srv, "K1", "att")
    sc.weave_k(w, "K1")
    d = srv.run_dir("att")
    append_outside_row(d, "harness", "attest", {"kind": "tests", "exit_code": 0})
    assert lg.verify(d)["status"] == "OK"
    r = srv.call("status", {"run_id": "att"})                                                    # the live server rebuilds from the file: closed
    assert r["refusal"] == "run_closed" and r["detail"]["closed"][0] == "emitted"


def test_prose_demo_bytes_are_unchanged_by_the_code_tier(tmp_path):
    srv = server(tmp_path)
    r = weave_tokyo(ScriptedWeaver(srv, "demo/tokyo_ca", "scripted", "demo"))
    assert r["text"] == "東京は日本の首都です"
    row0 = json.loads(open(os.path.join(str(tmp_path / "runs" / "demo"), "ops.jsonl"), encoding="utf-8").readline())
    assert set(row0["result"]["task"]) == {"task_id", "text", "lang", "mode", "tiers", "caps"} and row0["result"]["header"]["code_index_sha"] is None


# ---------------------------------------------------------------------------------------------------------------------
# determinism: the scripted K weaves are byte-identical under PYTHONHASHSEED 0 / 1 / 12345
# ---------------------------------------------------------------------------------------------------------------------
_PROBE = r"""
import hashlib, json, os, sys, tempfile
sys.path.insert(0, sys.argv[1])
from verantyx.loom.mcp import LoomServer
from verantyx.loom.scripted import ScriptedWeaver
from verantyx.loom import scripted_code as sc
rows = [json.loads(l) for l in open(sys.argv[2], encoding="utf-8")]
for r in rows:
    r["corpus"] = sys.argv[3]; r["fixture"] = sys.argv[4]
d = tempfile.mkdtemp()
srv = LoomServer(rows, d)
out = {}
for k, var in (("K1", "reference"), ("K2", "reference"), ("K3", "naive"), ("K3", "reference"), ("K4", "naive"), ("K4", "reference"), ("K5", "reference")):
    w = ScriptedWeaver(srv, "code/" + k.lower(), "scripted", "%s-%s" % (k, var))
    w.begin()
    sc.weave_k(w, k, var)
    out["%s-%s" % (k, var)] = hashlib.sha256(open(os.path.join(d, "%s-%s" % (k, var), "ops.jsonl"), "rb").read()).hexdigest()
print(json.dumps(out, sort_keys=True))
"""


def test_scripted_code_runs_are_byte_identical_across_hash_seeds():
    outs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
        p = subprocess.run([sys.executable, "-c", _PROBE, ROOT, TASKS_FILE, CORPUS, FIXTURE], env=env, capture_output=True, text=True, timeout=300)
        assert p.returncode == 0, p.stderr
        outs.append(p.stdout.strip())
    assert outs[0] == outs[1] == outs[2] and len(json.loads(outs[0])) == 7


def test_the_same_run_twice_in_this_process_is_byte_identical(tmp_path):
    shas = []
    for i in range(2):
        srv = code_server(tmp_path / str(i))
        w = begun(srv, "K3", "same")
        sc.weave_k(w, "K3")
        shas.append(hashlib.sha256(open(os.path.join(str(srv.run_dir("same")), "ops.jsonl"), "rb").read()).hexdigest())
    assert shas[0] == shas[1]


# ---------------------------------------------------------------------------------------------------------------------
# after the review (L-LOOM-78..84): the gates are not a safety wall; the harness refuses a model's weave without isolation
# ---------------------------------------------------------------------------------------------------------------------
import subprocess as _subprocess

CTX_ALL = ("ZERO", "add", "mul", "pairs", "a", "b", "p", "x", "f", "g")

# snippet -> the unsupported_construct it must be refused with; None = it PASSES every gate (a documented limit, L-LOOM-72) and is stopped
# only by the harness (isolation_required)
PROBES = {
    "import typing\nCWD = typing.sys.modules['os'].getcwd()\n": None,
    "import operator\nx = operator.attrgetter('__class__')(1)\n": None,
    "f = eval\nf('1')\n": "name:eval",
    "x = ().__class__.__base__.__subclasses__()\n": "dunder_attribute",
    "x = globals()['__builtins__']\n": "call:globals",
    "x = [open][0]('p')\n": "name:open",
    "import functools\nx = functools.partial(eval, 'x')\n": "name:eval",
    "breakpoint()\n": "call:breakpoint",
    "x = input()\n": "call:input",
    "x = locals()\n": "call:locals",
    "x = vars(a)\n": "call:vars",
    "delattr(a, 'b')\n": "call:delattr",
    "g = getattr\n": "name:getattr",
    "x = map(exec, a)\n": "name:exec",
    "x = __loader__\n": "dunder_name",
    "x = __builtins__\n": "dunder_name",
    "x = a.__dict__\n": "dunder_attribute",
    "x = (1).__class__\n": "dunder_attribute",
}


@pytest.mark.parametrize("text,construct", sorted(PROBES.items(), key=lambda kv: kv[0]))
def test_each_probe_is_refused_by_the_gates_or_left_to_the_harness(index, text, construct):
    r = [x for x in gate(index, text, ctx=CTX_ALL) if x["type"] == "unsupported_construct"]
    if construct is None:
        assert gate(index, text, ctx=CTX_ALL) == []
    else:
        assert construct in [x["construct"] for x in r], (text, r)


def test_a_blocked_name_is_refused_when_merely_read_bound_or_passed(index):
    for name in codelib.BLOCKED_NAMES:
        for text in ("x = %s\n" % name, "g(%s)\n" % name, "x = [%s]\n" % name):
            got = [x["construct"] for x in gate(index, text, ctx=CTX_ALL) if x["type"] == "unsupported_construct"]
            assert ("name:" + name) in got, (text, got)
        called = [x["construct"] for x in gate(index, "%s()\n" % name, ctx=CTX_ALL) if x["type"] == "unsupported_construct"]
        assert ("call:" + name) in called and ("name:" + name) not in called
    assert {"globals", "locals", "vars", "breakpoint", "input", "delattr"} <= set(codelib.BLOCKED_NAMES)
    assert gate(index, "x = a.real\n", ctx=CTX_ALL) == [] and gate(index, "x = _a_\ny = __a\n", ctx=("_a_", "__a")) == []   # not a dunder


def run_text(tmp_path, text, run_id="pr", k="K1"):
    """A code run whose thread is `text` (one cross per line); returns (weaver, the result of emit, the run folder)."""
    srv = code_server(tmp_path)
    w = begun(srv, k, run_id)
    thread_of(w, S(*text.splitlines()))
    return w, w.call("emit"), str(srv.run_dir(run_id))


def no_process(monkeypatch):
    def boom(*a, **kw):
        raise AssertionError("a process was started")
    monkeypatch.setattr(_subprocess, "run", boom)
    monkeypatch.setattr(_subprocess, "Popen", boom)


@pytest.mark.parametrize("text,construct", sorted(PROBES.items(), key=lambda kv: kv[0]))
def test_each_probe_is_refused_at_emit_or_runs_only_inside_the_os_sandbox(tmp_path, monkeypatch, text, construct):
    if construct is not None:                                      # refused at emit: no output, nothing to test, no process
        no_process(monkeypatch)
        w, em, d = run_text(tmp_path, text)
        assert em["ok"] is False and em["refusal"] == "unsupported_construct", em
        assert harness.test_emitted_run(d) == {"status": "no_output"}
        assert harness.test_emitted_run(d, driver="scripted") == {"status": "no_output"}
        rows = [json.loads(l) for l in open(os.path.join(d, "ops.jsonl"), encoding="utf-8")]
        assert not any(x["op"] == "attest" for x in rows)           # nothing was attested, nothing was run
    else:                                                          # passes every gate: the OS sandbox is the wall (LOOM-d2), the harness runs it
        w, em, d = run_text(tmp_path, text)
        assert em["ok"] is True, em
        r = harness.test_emitted_run(d)                            # a "model" driver, no token: sandboxed all the same
        assert r["status"] == "tested" and r["isolation"]["mechanism"] == "sandbox-exec" and r["isolation"]["probe"]["status"] == "passed"
        rows = [json.loads(l) for l in open(os.path.join(d, "ops.jsonl"), encoding="utf-8")]
        assert rows[-1]["op"] == "attest" and rows[-1]["args"]["driver"] == "model" and rows[-1]["args"]["isolation"]["mechanism"] == "sandbox-exec"


def test_a_model_weave_runs_sandboxed_without_a_token_and_a_token_never_lowers_a_passing_probe(tmp_path, monkeypatch):
    srv = code_server(tmp_path)
    w = begun(srv, "K1", "iso")
    sc.weave_k(w, "K1")                                             # a K1 weave by a "model" (the harness is not told it is scripted)
    d = str(srv.run_dir("iso"))
    for bad in ("", "x", "has space", "a;b", "a" * 65, "-lead", 7):
        assert harness.test_emitted_run(d, isolation_token=bad)["status"] == "isolation_token_invalid", bad
    res = harness.test_emitted_run(d)                               # no token, driver "model": NOT refused any more (L-LOOM-85)
    assert res["status"] == "tested" and res["exit_code"] == 0 and res["isolation"]["mechanism"] == "sandbox-exec"
    res = harness.test_emitted_run(d, isolation_token="vm-test-1")  # a token with a passing probe: still the OS sandbox, the token only recorded
    assert res["status"] == "tested" and res["isolation"]["mechanism"] == "sandbox-exec"
    rows = [json.loads(l) for l in open(os.path.join(d, "ops.jsonl"), encoding="utf-8")]
    a = rows[-1]
    assert a["op"] == "attest" and a["args"]["driver"] == "model" and a["args"]["isolation_token"] == "vm-test-1"
    assert a["args"]["isolation"]["mechanism"] == "sandbox-exec" and not a["args"]["isolation"].get("override")
    assert lg.verify(d)["status"] == "OK"


def test_the_cli_runs_every_driver_sandboxed_and_the_flag_is_only_an_override(tmp_path, monkeypatch, capsys):
    srv = code_server(tmp_path)
    w = begun(srv, "K1", "cli")
    sc.weave_k(w, "K1")
    d = str(srv.run_dir("cli"))
    assert harness.main(["test", d]) == 0                           # no flag: the probe passes, the run is sandboxed
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "tested" and out["exit_code"] == 0 and "tail" not in out and out["isolation"]["mechanism"] == "sandbox-exec"
    assert harness.main(["test", d, "--isolation-confirmed", "vm-cli-1"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "tested" and out["isolation"]["mechanism"] == "sandbox-exec"          # the flag did not lower the sandbox
    assert harness.main(["probe"]) == 0
    probe = json.loads(capsys.readouterr().out)
    assert probe["status"] == "passed" and probe["mechanism"] == "sandbox-exec" and len(probe["profile_sha"]) == 64


def test_the_process_gets_no_stdin_a_60_s_timeout_a_cleared_env_and_the_names_after_a_double_dash(monkeypatch):
    from verantyx.loom import isolate as iso
    seen = {}

    def fake_probe(policy, fixture_file, write_dir, limits=iso.Limits(), **kw):
        return iso.ProbeResult("passed", profile_sha=iso.profile_sha(), properties={k: True for k in iso.PROPERTIES})

    def fake_popen(argv, **kw):
        seen.update(kw, argv=argv)
        raise RuntimeError("stop here")
    monkeypatch.setattr(iso, "probe", fake_probe)
    monkeypatch.setattr(iso.subprocess, "Popen", fake_popen)
    with pytest.raises(RuntimeError, match="stop here"):
        harness.run_pytest(FIXTURE, "calc/ops.py", "", ["tests/test_ops.py"])
    assert harness.TIMEOUT_S == 60 and seen["stdin"] is _subprocess.DEVNULL
    argv = seen["argv"]
    assert argv[0] == iso.SANDBOX_EXEC and argv[1:3] == ["-f", str(iso.PROFILE_PATH)]          # through sandbox-exec, with the one static profile
    i = argv.index("-c")
    assert argv[i - 3:i] == ["-s", "-S", "-P"]                                                    # no user site, no site.py, no cwd on sys.path
    cfg = json.loads(argv[i + 2])
    assert cfg["kind"] == "pytest" and cfg["args"][-2:] == ["--", "tests/test_ops.py"] and ("RLIMIT_CPU", 50) in [tuple(x) for x in cfg["rlimits"]]
    assert set(seen["env"]) == {"PATH", "HOME", "TMPDIR", "USER", "LOGNAME", "PYTHONHASHSEED", "PYTHONDONTWRITEBYTECODE", "PYTEST_DISABLE_PLUGIN_AUTOLOAD"}
    assert seen["env"]["PATH"] == "/usr/bin:/bin" and seen["env"]["HOME"] != os.environ.get("HOME") and "PYTHONPATH" not in seen["env"]


# -- D2: what was tested ---------------------------------------------------------------------------------------------------
def fixture_copy(tmp_path, name="fx"):
    dst = str(tmp_path / name)
    shutil.copytree(FIXTURE, dst, ignore=shutil.ignore_patterns("__pycache__"))
    return dst


def test_the_attest_row_names_what_the_run_named_not_the_caller(tmp_path):
    fxd = fixture_copy(tmp_path)
    srv = code_server(tmp_path, fixture=fxd)
    w = begun(srv, "K3", "named")
    sc.weave_k(w, "K3")
    d = str(srv.run_dir("named"))
    named = harness.what_the_run_names(d)
    assert named == {"fixture": str(os.path.realpath(fxd)), "target": "calc/fmt.py", "tests": ["tests/test_k3.py", "tests/test_fmt.py"],
                     "code_index_sha": srv.runs["named"].run.code_index.sha}
    import inspect
    assert "task" not in inspect.signature(harness.test_emitted_run).parameters and "fixture_root" not in inspect.signature(harness.test_emitted_run).parameters
    res = harness.test_emitted_run(d, driver="scripted")
    a = [json.loads(l) for l in open(os.path.join(d, "ops.jsonl"), encoding="utf-8")][-1]["args"]
    assert res["status"] == "tested" and a["target"] == "calc/fmt.py" and a["tests"] == named["tests"] and a["code_index_sha"] == named["code_index_sha"]
    assert a["tests_sha"] == res["tests_sha"] and a["exit_code"] == 0


def test_a_changed_test_file_changes_tests_sha_and_a_changed_package_file_is_not_verified(tmp_path):
    fxd = fixture_copy(tmp_path)
    srv = code_server(tmp_path, fixture=fxd)
    w = begun(srv, "K1", "tsha")
    sc.weave_k(w, "K1")
    d = str(srv.run_dir("tsha"))
    r1 = harness.test_emitted_run(d, driver="scripted", append_attest=False)
    r1b = harness.test_emitted_run(d, driver="scripted", append_attest=False)
    assert r1["status"] == "tested" and r1["tests_sha"] == r1b["tests_sha"] and r1["code_index_sha"] == r1b["code_index_sha"]
    with open(os.path.join(fxd, "tests", "test_k1.py"), "a") as f:
        f.write("\n\ndef test_extra():\n    assert True\n")
    assert lg.verify(d)["status"] == "OK"                                                         # tests/ is outside the index: the run still verifies ...
    r2 = harness.test_emitted_run(d, driver="scripted", append_attest=False)
    assert r2["status"] == "tested" and r2["tests_sha"] != r1["tests_sha"] and r2["code_index_sha"] == r1["code_index_sha"]   # ... and the sha moves
    with open(os.path.join(fxd, "tests", "conftest.py"), "w") as f:                               # a new helper file moves it too
        f.write("X = 1\n")
    r3 = harness.test_emitted_run(d, driver="scripted", append_attest=False)
    assert r3["tests_sha"] not in (r1["tests_sha"], r2["tests_sha"])
    with open(os.path.join(fxd, "calc", "ops.py"), "a") as f:                                     # a package file moves the index sha: the run does not verify
        f.write("\nEXTRA = 1\n")
    assert harness.test_emitted_run(d, driver="scripted")["status"] == "run_not_verified"


def test_the_copy_is_checked_against_the_index_sha_before_anything_runs(monkeypatch):
    no_process(monkeypatch)
    r = harness.run_pytest(FIXTURE, "calc/ops.py", "", ["tests/test_ops.py"], expect_index_sha="0" * 64)
    assert r["status"] == "fixture_changed" and r["expected"] == "0" * 64 and len(r["found"]) == 64


def test_the_tests_sha_is_the_sha_of_the_held_out_bytes_only():
    idx = fx.build_index(FIXTURE, reader)
    from pathlib import Path
    a = harness.held_out_sha(Path(FIXTURE), idx)
    held = {}
    for d, _, fs in os.walk(FIXTURE):
        for n in fs:
            rel = os.path.relpath(os.path.join(d, n), FIXTURE).replace(os.sep, "/")
            if n.endswith(".py") and rel not in idx.file_sha and "__pycache__" not in rel:
                held[rel] = hashlib.sha256(reader(os.path.join(d, n))).hexdigest()
    assert sorted(held) == ["tests/test_counter.py", "tests/test_fmt.py", "tests/test_k1.py", "tests/test_k2.py", "tests/test_k3.py",
                            "tests/test_k4.py", "tests/test_k5.py", "tests/test_ops.py"]
    assert a == hashlib.sha256(json.dumps({"v": "tests_sha.v1", "files": held}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def test_a_run_that_names_no_target_and_tests_is_not_a_code_run_for_the_harness(tmp_path):
    srv = server(tmp_path)
    weave_tokyo(ScriptedWeaver(srv, "demo/tokyo_ca", "scripted", "demo"))
    assert harness.test_emitted_run(str(tmp_path / "runs" / "demo"), driver="scripted") == {"status": "not_a_code_run"}


# -- D3 ------------------------------------------------------------------------------------------------------------------------
def test_the_fixture_readme_marks_the_k_tests_as_placeholders():
    txt = open(os.path.join(FIXTURE, "README.md"), encoding="utf-8").read()
    assert "PLACEHOLDERS" in txt and "held-out" in txt and "test_k1.py" in txt and "test_k5.py" in txt
    assert not any(p.endswith("README.md") for p in fx.list_files(FIXTURE))


# -- D4 / D5 -------------------------------------------------------------------------------------------------------------------
def test_a_prose_task_with_a_fixture_or_context_names_is_refused_at_load(tmp_path):
    base = {"task_id": "t", "text": "x", "lang": "prose", "mode": "record_only"}
    for extra in ({"fixture": FIXTURE}, {"context_names": ["add"]}):
        with pytest.raises(ValueError):
            normalize_task(dict(base, **extra))
    bad = prose_task("p")
    bad["fixture"] = FIXTURE
    with pytest.raises(ValueError):
        LoomServer([bad], str(tmp_path / "runs"))
    ok = normalize_task(dict(base, lang="code", fixture=FIXTURE, context_names=["add"]))
    assert ok["fixture"] == FIXTURE and ok["context_names"] == ["add"]


@pytest.mark.parametrize("name", ["-x.py", "--pyargs.py", "-", "-/a.py", "-k/../x.py"])
def test_a_relpath_starting_with_a_dash_is_refused(name):
    base = {"task_id": "t", "text": "x", "lang": "code", "mode": "record_only"}
    with pytest.raises(ValueError):
        normalize_task(dict(base, tests=[name]))
    with pytest.raises(ValueError):
        normalize_task(dict(base, target={"file": name}))
    assert normalize_task(dict(base, tests=["tests/-x.py"]))["tests"] == ["tests/-x.py"]       # a dash inside the path is not an option


@pytest.mark.parametrize("bad", [[""], ["1a"], ["a b"], ["class"], "add", [1], ["a.b"]])
def test_context_names_must_be_identifiers(bad):
    with pytest.raises(ValueError):
        normalize_task({"task_id": "t", "text": "x", "lang": "code", "mode": "record_only", "context_names": bad})


def test_begin_checks_the_target_and_the_context_names_against_the_index(tmp_path):
    n = [0]

    def srv_with(**extra):
        rows = code_tasks()[:1]
        rows[0].update(extra)
        n[0] += 1
        return LoomServer(rows, str(tmp_path / ("r%d" % n[0])))
    s = srv_with(target={"file": "calc/nope.py"})
    r = s.begin("code/k1", "m", "t1")
    assert r == {"ok": False, "refusal": "target_not_in_fixture", "detail": {"file": "calc/nope.py"}}
    assert not os.path.exists(str(s.sandbox.runs_root / "t1"))
    r = srv_with(target={"file": "tests/test_ops.py"}).begin("code/k1", "m", "t2")              # a test file is not in the index: not a target
    assert r["refusal"] == "target_not_in_fixture"
    r = srv_with(context_names=["add", "no_such_name"]).begin("code/k1", "m", "t3")
    assert r == {"ok": False, "refusal": "unknown_context_name", "detail": {"name": "no_such_name"}}
    ok = srv_with(context_names=["add", "fmt_num"]).begin("code/k1", "m", "t4")                 # names of other modules of the fixture are known
    assert ok["ok"] is True and ok["task"]["context_names"] == ["add", "fmt_num"]


# -- D6 ------------------------------------------------------------------------------------------------------------------------
def test_a_line_count_that_differs_from_the_cross_count_is_refused_not_skipped(index):
    r = codelib.gate_refusals("x = 1\ny = 2\n", index, (), ["c1"])
    assert [(x["type"], x["lines"], x["crosses"]) for x in r] == [("line_cross_mismatch", 2, 1)] and "cid" not in r[0]
    assert codelib.gate_refusals("x = 1\ny = 2\n", index, (), ["c1", "c2"]) == []
    assert rd.REFUSAL_ORDER.index("cross_not_one_statement") < rd.REFUSAL_ORDER.index("line_cross_mismatch") < rd.REFUSAL_ORDER.index("layout_changed_tokens")


def test_replay_reads_the_fixture_through_the_sandbox_so_fixture_outside_sandbox_fires(k_results, tmp_path):
    from verantyx.loom.mcp import Sandbox
    d = str(tmp_path / "copy")
    shutil.copytree(k_results[("K1", "reference")]["run_dir"], d)
    meta = json.load(open(os.path.join(d, "meta.json")))
    outside = tmp_path / "outside"
    outside.mkdir()                                                                   # a folder with NO .py file: nothing would ever be read from it
    sb = Sandbox(str(tmp_path / "runs2"), [meta["corpus"]], [FIXTURE])
    assert lg.replay(d, loader=sb.read_bytes).identical                                 # the real fixture is inside the sandbox
    meta["fixture"] = str(outside)
    json.dump(meta, open(os.path.join(d, "meta.json"), "w"))
    rep = lg.replay(d, loader=sb.read_bytes)
    assert rep.status == "INPUTS" and rep.mismatch == "fixture_outside_sandbox"
    meta["fixture"] = str(tmp_path / "no_such_folder")                                  # a root that is not a folder: typed, not a hash mismatch
    json.dump(meta, open(os.path.join(d, "meta.json"), "w"))
    sb.read_roots.append((tmp_path / "no_such_folder").resolve())
    assert lg.replay(d, loader=sb.read_bytes).mismatch == "fixture_unreadable"
    assert lg.replay(d).mismatch == "fixture_unreadable"                                # the default loader too
