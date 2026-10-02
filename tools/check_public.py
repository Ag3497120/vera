#!/usr/bin/env python3
"""Check that an assembled public layout (see tools/build_public.py) starts and stands on its own.

    python tools/check_public.py <out> [--label NAME] [--json FILE] [--against DIR]
                                       [--checks a,b,c,d,e,f,p4,scan]
    python tools/check_public.py --digest-only <dir> [--label NAME]

Standard library only. This process never imports verantyx or vera_base: every dynamic check runs in a
child interpreter started as `[sys.executable, -B, -I, -c, code]` with env={"HOME": tmp}, cwd=tmp, so no stray
PYTHON* variable or working directory can put another copy of the package on the path.

Checks (status is PASS / FAIL / UNKNOWN_<reason>; only PASS counts as a pass)
  a    `import vera_base` succeeds in a clean interpreter
  b    every verantyx* / vera_base* module loaded by the children of a, d, e, f (and scan, when run)
       comes from a file inside <out>
  c    pyproject.toml's packages declaration equals the real package directories, every non-.py file is
       covered by package-data, and a wheel built from a copy of <out> holds exactly the files of vera_base/
  d    example.py runs to the end (same view as `python example.py`)
  e    >= 12 fixed unknown inputs sent to the public API (Chat([]) and Chat([constructed document], tree=True))
       return a dict with a str `text`; this checks that it starts and answers, not that the answer is right
  f    the bundled tests collect with 0 collection errors
  p4   no personal absolute path, store data, VCS data, cache or measurement output inside <out>
  scan (information only, not counted in all_pass) import every verantyx.* module and report which fail

Exit codes: 0 every selected check PASS (and <out> unchanged) / 1 otherwise / 2 usage error.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path, PurePosixPath

SCHEMA = "vera_public_check_v1"
ALL_CHECKS = ["a", "b", "c", "d", "e", "f", "p4", "scan"]
COUNTED = ["a", "b", "c", "d", "e", "f", "p4"]          # scan is information only
CHILD_TIMEOUT = 600
PERSONAL_PATTERN = bytes.fromhex("2f55736572732f")      # a Users-directory absolute-path marker, kept as hex
CACHE_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
MEASUREMENT_DIRS = {"experiments", "results", "artifacts"}
WRAPPER = "vera_base"

# fixed unknown inputs for check e: constants, never adjusted to the outcome
UNKNOWN_INPUTS = [
    "", " ", "hello world", "猫", "123456789", "🙂🙂", "a" * 2000, "\x00\x01",
    "東京の人口は?", "これは何ですか。", "ログインできない", "SELECT * FROM t;",
    "<script>alert(1)</script>", "。。。",
]
CONSTRUCTED_DOCUMENT = {"title": "営業案内", "ja": "当店の営業時間は午前10時から午後7時までです。定休日は毎週水曜日です。"}


# ---------------------------------------------------------------- tree helpers
def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fn in sorted(filenames):
            full = Path(dirpath) / fn
            if full.is_file():
                yield PurePosixPath(*full.relative_to(root).parts), full


def tree_digest(root: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    n = 0
    for rel, full in sorted(iter_files(root), key=lambda t: str(t[0])):
        h.update(str(rel).encode("utf-8") + b"\0" + hashlib.sha256(full.read_bytes()).hexdigest().encode() + b"\n")
        n += 1
    return h.hexdigest(), n


# ---------------------------------------------------------------- child processes
# Common prologue: the output goes first on sys.path; the result file is written even when the body raises.
_PROLOGUE = r'''
import sys, json
OUT, RES = sys.argv[1], sys.argv[2]
sys.path.insert(0, OUT)
RESULT = {}
def _modules():
    from pathlib import Path
    out = Path(OUT).resolve()
    inside, outside, nofile = [], [], []
    for name, m in sorted(sys.modules.items()):
        if name.split(".")[0] not in ("verantyx", "vera_base") or m is None:
            continue
        f = getattr(m, "__file__", None)
        paths = [f] if f else list(getattr(m, "__path__", None) or [])
        if not paths:
            nofile.append(name)
            continue
        ok = True
        for p in paths:
            try:
                rp = Path(p).resolve()
            except Exception:
                ok = False
                break
            if not (rp == out or out in rp.parents):
                ok = False
                break
        (inside if ok else outside).append(name)
    return {"inside": len(inside), "outside": outside, "no_file": nofile}
def _finish():
    RESULT["modules"] = _modules()
    with open(RES, "w", encoding="utf-8") as fh:
        json.dump(RESULT, fh, ensure_ascii=False)
'''

_CODE_A = _PROLOGUE + r'''
try:
    import vera_base
    RESULT["imported"] = True
    RESULT["dependency_status"] = vera_base.dependency_status() if hasattr(vera_base, "dependency_status") else None
    import verantyx.chat as _c
    RESULT["chat_is_verantyx_chat"] = vera_base.Chat is _c.Chat
finally:
    _finish()
'''

_CODE_D = _PROLOGUE + r'''
import runpy, os
try:
    import importlib.util as _u
    RESULT["optional"] = {n: (_u.find_spec(n) is not None) for n in ("fugashi", "unidic_lite")}
    ex = os.path.join(OUT, "example.py")
    sys.argv = [ex]
    runpy.run_path(ex, run_name="__main__")
finally:
    _finish()
'''

_CODE_E = _PROLOGUE + r'''
INPUTS = json.loads(sys.argv[3])
DOC = json.loads(sys.argv[4])
def one(make):
    r = {"calls": 0, "exceptions": [], "kinds": {}, "no_parser": 0, "not_dict": 0, "text_not_str": 0, "constructor_exception": None}
    try:
        chat = make()
    except BaseException as exc:
        r["constructor_exception"] = {"type": type(exc).__name__, "name": getattr(exc, "name", None)}
        return r
    for i, q in enumerate(INPUTS):
        r["calls"] += 1
        try:
            a = chat.reply(q)
        except BaseException as exc:
            r["exceptions"].append({"input_index": i, "type": type(exc).__name__, "name": getattr(exc, "name", None)})
            continue
        if not isinstance(a, dict):
            r["not_dict"] += 1
            continue
        if not isinstance(a.get("text"), str):
            r["text_not_str"] += 1
        k = str(a.get("kind", "<no kind>"))
        r["kinds"][k] = r["kinds"].get(k, 0) + 1
        if k == "UNKNOWN_NO_PARSER":
            r["no_parser"] += 1
    return r
try:
    import vera_base
    RESULT["empty"] = one(lambda: vera_base.Chat([]))
    RESULT["with_constructed_document"] = one(lambda: vera_base.Chat([DOC], tree=True))
finally:
    _finish()
'''

_CODE_F = _PROLOGUE + r'''
try:
    import pytest
except ImportError:
    RESULT["pytest_missing"] = True
    _finish()
    raise SystemExit(0)
class Agg:
    def __init__(self):
        self.errors, self.collected = [], 0
    def pytest_collectreport(self, report):
        if report.failed:
            self.errors.append(report.nodeid)
    def pytest_collection_modifyitems(self, items):
        self.collected = len(items)
agg = Agg()
try:
    rc = pytest.main(["--collect-only", "-q", "-p", "no:cacheprovider", "--rootdir", OUT, OUT + "/tests"], plugins=[agg])
    RESULT["pytest_exit"] = int(rc)
    RESULT["collection_errors"] = len(agg.errors)
    RESULT["error_ids"] = sorted(agg.errors)[:50]
    RESULT["collected"] = agg.collected
finally:
    _finish()
'''

_CODE_SCAN = _PROLOGUE + r'''
import importlib, pkgutil
try:
    import vera_base
    import verantyx
    failed_pkg = {}
    def onerror(name):
        exc = sys.exc_info()[1]
        failed_pkg[name] = ("MNF:" + str(getattr(exc, "name", None))) if isinstance(exc, ModuleNotFoundError) else type(exc).__name__
    names = sorted({m.name for m in pkgutil.walk_packages(verantyx.__path__, "verantyx.", onerror=onerror)} | set(failed_pkg))
    ok, mnf, other = 0, {}, {}
    for n in names:
        try:
            importlib.import_module(n)
            ok += 1
        except ModuleNotFoundError as exc:
            mnf[n] = str(exc.name)
        except BaseException as exc:
            other[n] = type(exc).__name__
    RESULT.update({"modules_found": len(names), "ok": ok, "mnf": mnf, "other_exceptions": other})
finally:
    _finish()
'''

_CODE_PROBE = r'''
import sys, json, importlib.util as u
OUT, RES = sys.argv[1], sys.argv[2]
if OUT != "-":
    sys.path.insert(0, OUT)
r = {"optional": {n: (u.find_spec(n) is not None) for n in ("fugashi", "unidic_lite")}}
try:
    r["verantyx_spec"] = u.find_spec("verantyx") is not None
except Exception as exc:
    r["verantyx_spec"] = type(exc).__name__
open(RES, "w").write(json.dumps(r))
'''

_CODE_WHEEL = r'''
import sys, os
os.chdir(sys.argv[1])
import setuptools.build_meta as b
print(b.build_wheel(sys.argv[3]))
'''


def run_child(code: str, args: list[str], tmp: Path, timeout: int = CHILD_TIMEOUT) -> dict:
    """Run `code` in a clean child interpreter. Returns rc/stdout/stderr/result, or a typed failure."""
    res_file = tmp / f"res_{abs(hash((code, tuple(args))))}.json"
    res_file.unlink(missing_ok=True)
    try:
        p = subprocess.run([sys.executable, "-B", "-I", "-c", code, *args[:1], str(res_file), *args[1:]],
                           env={"HOME": str(tmp), "TMPDIR": str(tmp)}, cwd=str(tmp),
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"status": "UNKNOWN_TIMEOUT", "rc": None, "stdout": "", "stderr": "", "result": None}
    result = None
    if res_file.is_file():
        try:
            result = json.loads(res_file.read_text(encoding="utf-8"))
        except ValueError:
            result = None
    return {"status": "RAN", "rc": p.returncode, "stdout": p.stdout, "stderr": p.stderr, "result": result}


def last_exception_type(stderr: str):
    """Exception type name on the last line of a traceback (no paths, no messages)."""
    lines = [ln for ln in stderr.strip().splitlines() if ln.strip()]
    if not lines:
        return None
    m = re.match(r"^([A-Za-z_][\w.]*)(?::|$)", lines[-1])
    return m.group(1) if m else None


# ---------------------------------------------------------------- checks
def check_a(out: Path, tmp: Path, cache: dict) -> dict:
    r = run_child(_CODE_A, [str(out)], tmp)
    cache["a"] = r
    res = r["result"] or {}
    if r["status"] != "RAN":
        return {"status": r["status"]}
    ok = r["rc"] == 0 and res.get("imported") is True
    return {"status": "PASS" if ok else "FAIL", "exit_code": r["rc"], "imported": res.get("imported", False),
            "dependency_status": res.get("dependency_status"),
            "chat_is_verantyx_chat": res.get("chat_is_verantyx_chat"),
            "error_type": None if ok else last_exception_type(r["stderr"])}


def check_d(out: Path, tmp: Path, cache: dict) -> dict:
    r = run_child(_CODE_D, [str(out)], tmp)
    cache["d"] = r
    if r["status"] != "RAN":
        return {"status": r["status"]}
    res = r["result"] or {}
    lines = [ln for ln in r["stdout"].splitlines() if ln.strip()]
    ok = r["rc"] == 0 and "Traceback" not in r["stderr"] and len(lines) >= 1
    optional = res.get("optional") or {}
    return {"status": "PASS" if ok else "FAIL", "exit_code": r["rc"], "stdout_lines": len(lines),
            "stderr_has_traceback": "Traceback" in r["stderr"],
            "degraded": any(v is False for v in optional.values()) if optional else None,
            "optional_dependencies": optional,
            "error_type": None if ok else last_exception_type(r["stderr"])}


def check_e(out: Path, tmp: Path, cache: dict) -> dict:
    r = run_child(_CODE_E, [str(out), json.dumps(UNKNOWN_INPUTS, ensure_ascii=False),
                            json.dumps(CONSTRUCTED_DOCUMENT, ensure_ascii=False)], tmp)
    cache["e"] = r
    if r["status"] != "RAN":
        return {"status": r["status"]}
    res = r["result"]
    if not res or "empty" not in res:
        return {"status": "FAIL", "exit_code": r["rc"], "error_type": last_exception_type(r["stderr"])}
    configs = {"empty": res["empty"], "with_constructed_document": res["with_constructed_document"]}
    ok = True
    total = no_parser = 0
    for c in configs.values():
        bad = c["constructor_exception"] is not None or c["exceptions"] or c["not_dict"] or c["text_not_str"]
        ok = ok and not bad and c["calls"] == len(UNKNOWN_INPUTS)
        total += c["calls"]
        no_parser += c["no_parser"]
    return {"status": "PASS" if ok else "FAIL", "inputs": len(UNKNOWN_INPUTS), "calls_total": total,
            "unknown_no_parser_total": no_parser, "responses_other_than_unknown_no_parser_total": total - no_parser,
            "constructed_documents": [{"kind": "CONSTRUCTED", "title": CONSTRUCTED_DOCUMENT["title"]}],
            "configs": configs}


def check_f(out: Path, tmp: Path, cache: dict) -> dict:
    r = run_child(_CODE_F, [str(out)], tmp)
    cache["f"] = r
    if r["status"] != "RAN":
        return {"status": r["status"]}
    res = r["result"] or {}
    if res.get("pytest_missing"):
        return {"status": "UNKNOWN_PYTEST_MISSING"}
    if "collection_errors" not in res:
        return {"status": "FAIL", "exit_code": r["rc"], "error_type": last_exception_type(r["stderr"])}
    ok = res["collection_errors"] == 0 and res["collected"] > 0
    return {"status": "PASS" if ok else "FAIL", "collected": res["collected"],
            "collection_errors": res["collection_errors"], "error_ids": res["error_ids"],
            "pytest_exit": res["pytest_exit"]}


def check_scan(out: Path, tmp: Path, cache: dict) -> dict:
    r = run_child(_CODE_SCAN, [str(out)], tmp)
    cache["scan"] = r
    if r["status"] != "RAN":
        return {"status": r["status"], "informational": True}
    res = r["result"]
    if not res or "ok" not in res:
        return {"status": "FAIL", "informational": True, "error_type": last_exception_type(r["stderr"])}
    return {"status": "DONE", "informational": True, "modules_found": res["modules_found"], "import_ok": res["ok"],
            "import_failed_module_not_found": dict(sorted(res["mnf"].items())),
            "import_failed_other": dict(sorted(res["other_exceptions"].items()))}


def check_b(cache: dict) -> dict:
    per, bad, missing = {}, {}, []
    for key in ("a", "d", "e", "f", "scan"):
        r = cache.get(key)
        m = (r["result"] or {}).get("modules") if r and r["result"] else None
        if m is None:
            if key in ("a", "d", "e", "f"):
                missing.append(key)
            continue
        per[key] = {"inside": m["inside"], "outside_count": len(m["outside"]), "no_file_count": len(m["no_file"])}
        if m["outside"]:
            bad[key] = sorted(m["outside"])
    if missing or not per:
        # a child that produced no module list cannot have been checked: that is unknown, not a pass
        return {"status": "UNKNOWN_NO_CHILD_RESULT", "children_without_module_list": missing}
    ok = not bad and all(v["inside"] > 0 for k, v in per.items() if k in ("a", "d", "e", "f"))
    return {"status": "PASS" if ok else "FAIL", "per_child": per, "outside_modules": bad}


def _glob_re(pat: str) -> re.Pattern:
    out, i = "", 0
    while i < len(pat):
        if pat.startswith("**", i):
            out += ".*"
            i += 2
        elif pat[i] == "*":
            out += "[^/]*"
            i += 1
        elif pat[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pat[i])
            i += 1
    return re.compile("^" + out + "$")


def check_c(out: Path, tmp: Path) -> dict:
    res: dict = {}
    pp = out / "pyproject.toml"
    if not pp.is_file():
        return {"status": "FAIL", "static": {"error": "pyproject.toml missing"}}
    cfg = tomllib.loads(pp.read_text(encoding="utf-8"))
    st = cfg.get("tool", {}).get("setuptools", {})
    find = st.get("packages", {}).get("find", {}) if isinstance(st.get("packages"), dict) else {}
    include = find.get("include", ["*"])
    exclude = find.get("exclude", [])
    where = find.get("where", ["."])
    where_dirs = [out / w for w in (where if isinstance(where, list) else [where])]

    def dotted_inits(base: Path) -> set[str]:
        s = set()
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames.sort()
            if "__init__.py" in filenames:
                rel = Path(dirpath).relative_to(base)
                if rel.parts:
                    s.add(".".join(rel.parts))
        return s

    declared = set()
    for wd in where_dirs:
        for name in dotted_inits(wd):
            if any(fnmatch.fnmatchcase(name, p) for p in include) and not any(fnmatch.fnmatchcase(name, p) for p in exclude):
                declared.add(name)
    actual = {n for n in dotted_inits(out) if n.split(".")[0] == WRAPPER}

    # python files whose directory has no __init__.py, and non-.py files outside every package-data glob
    init_dirs = {str(rel.parent) for rel, _ in iter_files(out) if rel.name == "__init__.py"}
    no_init = set()
    uncovered = []
    pdata = st.get("package-data", {})
    compiled = {pkg: [_glob_re(g) for g in globs] for pkg, globs in pdata.items()}
    for rel, _ in iter_files(out / WRAPPER):
        full_rel = PurePosixPath(WRAPPER) / rel
        d = str(full_rel.parent)
        if rel.suffix == ".py":
            if d not in init_dirs:
                no_init.add(d)
            continue
        anc = full_rel.parent
        while str(anc) not in init_dirs and anc != PurePosixPath("."):
            anc = anc.parent
        if str(anc) not in init_dirs:
            uncovered.append(str(full_rel))
            continue
        pkg = str(anc).replace("/", ".")
        sub = str(full_rel.relative_to(anc))
        pats = compiled.get(pkg, []) + compiled.get("*", [])
        if not any(p.match(sub) for p in pats):
            uncovered.append(str(full_rel))
    static_ok = declared == actual and not no_init and not uncovered
    res["static"] = {"ok": static_ok, "declared_but_not_real": sorted(declared - actual),
                     "real_but_not_declared": sorted(actual - declared),
                     "python_dirs_without_init": sorted(no_init), "non_python_files_not_in_package_data": sorted(uncovered),
                     "packages_declared": len(declared), "packages_real": len(actual)}

    # wheel from a COPY of the output (building inside the output would leave build/ and *.egg-info)
    work = Path(tempfile.mkdtemp(prefix="wheel_", dir=tmp))
    try:
        copy = work / "src"
        shutil.copytree(out, copy)
        dist = work / "dist"
        dist.mkdir()
        r = run_child(_CODE_WHEEL, [str(copy), str(dist)], tmp)
        if r["status"] != "RAN":
            res["wheel"] = {"status": r["status"]}
        elif r["rc"] != 0:
            msg = r["stderr"]
            if "No module named 'setuptools'" in msg:
                res["wheel"] = {"status": "UNKNOWN_SETUPTOOLS_MISSING"}
            else:
                res["wheel"] = {"status": "FAIL", "error_type": last_exception_type(msg)}
        else:
            wheels = sorted(dist.glob("*.whl"))
            if len(wheels) != 1:
                res["wheel"] = {"status": "FAIL", "wheels_found": len(wheels)}
            else:
                with zipfile.ZipFile(wheels[0]) as z:
                    inwheel = {n for n in z.namelist() if n.startswith(WRAPPER + "/") and not n.endswith("/")}
                onout = {str(PurePosixPath(WRAPPER) / rel) for rel, _ in iter_files(out / WRAPPER)}
                same = inwheel == onout
                res["wheel"] = {"status": "PASS" if same else "FAIL", "files_in_wheel": len(inwheel),
                                "files_in_output": len(onout), "only_in_wheel": sorted(inwheel - onout)[:50],
                                "only_in_output": sorted(onout - inwheel)[:50]}
    finally:
        shutil.rmtree(work, ignore_errors=True)
    wstat = res["wheel"]["status"]
    if not static_ok or wstat == "FAIL":
        status = "FAIL"
    elif wstat != "PASS":
        status = wstat
    else:
        status = "PASS"
    return {"status": status, **res}


def check_p4(out: Path) -> dict:
    found = {"personal_path": [], "store_data": [], "vcs": [], "cache": [], "measurement": []}
    for rel, full in iter_files(out):
        parts = rel.parts
        name = parts[-1]
        data = full.read_bytes()
        if PERSONAL_PATTERN in data:
            lines = [i for i, ln in enumerate(data.split(b"\n"), 1) if PERSONAL_PATTERN in ln]
            found["personal_path"].append({"path": str(rel), "lines": lines})
        if name.startswith("vera_store."):
            found["store_data"].append(str(rel))
        if ".git" in parts:
            found["vcs"].append(str(rel))
        if any(p in CACHE_DIRS for p in parts) or name.endswith((".pyc", ".pyo")) or name == ".DS_Store":
            found["cache"].append(str(rel))
        if name.endswith(".log") or any(p in MEASUREMENT_DIRS for p in parts[:-1]):
            found["measurement"].append(str(rel))
    # directories (an empty .git or __pycache__ directory is also contamination)
    for dirpath, dirnames, _ in os.walk(out):
        for d in dirnames:
            rel = str(Path(dirpath, d).relative_to(out))
            if d == ".git":
                found["vcs"].append(rel + "/")
            if d in CACHE_DIRS:
                found["cache"].append(rel + "/")
    counts = {k: len(v) for k, v in found.items()}
    return {"status": "PASS" if not any(counts.values()) else "FAIL", "counts": counts, "found": found}


def public_diff(out: Path, other: Path) -> dict:
    a = {str(rel): full for rel, full in iter_files(out)}
    b = {str(rel): full for rel, full in iter_files(other)}
    added = sorted(set(a) - set(b))
    removed = sorted(set(b) - set(a))
    modified = sorted(p for p in set(a) & set(b) if a[p].read_bytes() != b[p].read_bytes())
    return {"added": added, "removed": removed, "modified": modified,
            "counts": {"added": len(added), "removed": len(removed), "modified": len(modified),
                       "unchanged": len(set(a) & set(b)) - len(modified)}}


# ---------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("out", nargs="?")
    ap.add_argument("--label", default="unlabeled")
    ap.add_argument("--json", default=None)
    ap.add_argument("--against", default=None)
    ap.add_argument("--checks", default=",".join(ALL_CHECKS))
    ap.add_argument("--digest-only", default=None, metavar="DIR")
    args = ap.parse_args(argv)

    if args.digest_only:
        d = Path(args.digest_only)
        if not d.is_dir():
            print(json.dumps({"error": "USAGE", "detail": "--digest-only needs an existing directory"}), file=sys.stderr)
            return 2
        digest, n = tree_digest(d)
        print(json.dumps({"label": args.label, "digest": digest, "files": n}, sort_keys=True))
        return 0
    if not args.out or not Path(args.out).is_dir():
        print(json.dumps({"error": "USAGE", "detail": "an existing output directory is required"}), file=sys.stderr)
        return 2
    selected = [c.strip() for c in args.checks.split(",") if c.strip()]
    unknown = [c for c in selected if c not in ALL_CHECKS]
    if unknown or not selected:
        print(json.dumps({"error": "USAGE", "detail": "unknown or empty --checks", "unknown": unknown}), file=sys.stderr)
        return 2

    out = Path(args.out).resolve()
    digest_start, nfiles = tree_digest(out)
    tmp = Path(tempfile.mkdtemp(prefix="check_public_"))
    cache: dict = {}
    checks: dict = {}
    try:
        probe_in = run_child(_CODE_PROBE, [str(out)], tmp)
        probe_out = run_child(_CODE_PROBE, ["-"], tmp)
        # a, d, e, f (and scan) are run when selected or when b needs their module lists
        need = set(selected)
        if "b" in need:
            need |= {"a", "d", "e", "f"}
        runners = {"a": check_a, "d": check_d, "e": check_e, "f": check_f, "scan": check_scan}
        for key in ("a", "d", "e", "f", "scan"):
            if key in need:
                r = runners[key](out, tmp, cache)
                if key in selected:
                    checks[key] = r
        if "b" in selected:
            checks["b"] = check_b(cache)
        if "c" in selected:
            checks["c"] = check_c(out, tmp)
        if "p4" in selected:
            checks["p4"] = check_p4(out)
        diff = public_diff(out, Path(args.against).resolve()) if args.against else None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    digest_end, _ = tree_digest(out)
    unchanged = digest_start == digest_end
    counted = [c for c in selected if c in COUNTED]
    all_pass = unchanged and all(checks[c]["status"] == "PASS" for c in counted)
    report = {
        "schema": SCHEMA,
        "label": args.label,
        "python": {"version": sys.version, "implementation": sys.implementation.name},
        "optional_dependencies": (probe_in["result"] or {}).get("optional"),
        "external_verantyx_reachable": (probe_out["result"] or {}).get("verantyx_spec"),
        "checks_selected": selected,
        "checks": dict(sorted(checks.items())),
        "out_digest_start": digest_start,
        "out_digest_end": digest_end,
        "out_file_count": nfiles,
        "out_unchanged": unchanged,
        "all_pass": all_pass,
    }
    if diff is not None:
        report["public_diff"] = diff
    text = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.json:
        Path(args.json).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
