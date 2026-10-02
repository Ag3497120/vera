"""P5: tools/build_public.py and tools/check_public.py, driven through their command lines.

Small synthetic trees check determinism (P1), discovery by rule (P3), exclusion (P4) and the typed stops;
one test builds the real development tree. Standard library + pytest only; verantyx is never imported.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "tools" / "build_public.py"
CHECK = ROOT / "tools" / "check_public.py"

OVERLAY_PYPROJECT = """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "synthetic"
version = "0"

[tool.setuptools.packages.find]
include = ["vera_base*"]

[tool.setuptools.package-data]
"vera_base.verantyx" = ["stale_entry/*.json"]
"""


def run(script, *args, cwd=None, env=None):
    return subprocess.run([sys.executable, "-B", str(script), *map(str, args)],
                          capture_output=True, text=True, cwd=cwd, env=env)


def build(src, overlay, out, env=None):
    return run(BUILD, "--src", src, "--overlay", overlay, "--out", out, env=env)


def write(path: Path, text: str = "", data: bytes | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if data is not None:
        path.write_bytes(data)
    else:
        path.write_text(text, encoding="utf-8")


@pytest.fixture
def synth(tmp_path):
    src = tmp_path / "dev"
    overlay = src / "public_overlay"
    write(src / "verantyx" / "__init__.py", "")
    write(src / "verantyx" / "sub" / "__init__.py", "")
    write(src / "verantyx" / "sub" / "m.py", "X = 1\n")
    write(src / "verantyx" / "datadir" / "x.json", '{"a": 1}\n')
    write(overlay / "vera_base" / "__init__.py", "")
    write(overlay / "pyproject.toml", OVERLAY_PYPROJECT)
    write(overlay / "example.py", "print('ok')\n")
    return src, overlay


def manifest_of(out: Path):
    return json.loads((out / "manifest.json").read_text(encoding="utf-8"))


def test_p1_deterministic(synth, tmp_path):
    src, overlay = synth
    o1, o2 = tmp_path / "o1", tmp_path / "o2"
    assert build(src, overlay, o1).returncode == 0
    assert build(src, overlay, o2).returncode == 0
    d1 = json.loads(run(CHECK, "--digest-only", o1).stdout)
    d2 = json.loads(run(CHECK, "--digest-only", o2).stdout)
    assert d1["digest"] == d2["digest"] and d1["files"] == d2["files"] > 0
    assert (o1 / "manifest.json").read_bytes() == (o2 / "manifest.json").read_bytes()
    m = manifest_of(o1)
    assert m["schema"] == "vera_public_build_manifest_v1"
    # the personal-path marker must not be spelled out in the manifest
    assert ("/" + "Users" + "/") not in (o1 / "manifest.json").read_text(encoding="utf-8")


def test_p3_new_subpackage_is_found_without_changing_the_tool(synth, tmp_path):
    src, overlay = synth
    o1 = tmp_path / "o1"
    assert build(src, overlay, o1).returncode == 0
    before = manifest_of(o1)
    assert "vera_base.verantyx.brand_new" not in before["packages"]

    write(src / "verantyx" / "brand_new" / "__init__.py", "")
    write(src / "verantyx" / "brand_new" / "table.json", "{}\n")
    write(src / "verantyx" / "brand_new" / "deep" / "z.json", "{}\n")
    o2 = tmp_path / "o2"
    assert build(src, overlay, o2).returncode == 0
    after = manifest_of(o2)
    paths = {f["path"] for f in after["files"]}
    for rel in ("__init__.py", "table.json", "deep/z.json"):
        assert (o2 / "vera_base" / "verantyx" / "brand_new" / rel).is_file()
        assert f"vera_base/verantyx/brand_new/{rel}" in paths
    assert "vera_base.verantyx.brand_new" in after["packages"]
    import tomllib
    table = tomllib.loads((o2 / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["setuptools"]["package-data"]
    assert "table.json" in table["vera_base.verantyx.brand_new"] or "*.json" in table["vera_base.verantyx.brand_new"]
    assert "deep/*.json" in table["vera_base.verantyx.brand_new"]
    # the stale hand-written entry of the overlay's pyproject is replaced, and declared as constructed
    assert "stale_entry" not in (o2 / "pyproject.toml").read_text(encoding="utf-8")
    assert {"path": "pyproject.toml", "part": "tool.setuptools.package-data", "kind": "CONSTRUCTED"} in after["generated"]
    gen = [f for f in after["files"] if f["path"] == "pyproject.toml"][0]
    assert gen["origin"] == "generated" and gen["kind"] == "CONSTRUCTED"


def test_p4_exclusions_by_rule(synth, tmp_path):
    src, overlay = synth
    write(src / "verantyx" / "__pycache__" / "m.cpython-311.pyc", data=b"\x00\x01")
    write(src / "verantyx" / "vera_store.json", "{}")
    write(src / "verantyx" / ".git" / "config", "[core]\n")
    write(src / "verantyx" / "run.log", "log\n")
    write(src / "verantyx" / "leak.py", "P = '" + "/" + "Users" + "/someone/x'\n")
    out = tmp_path / "out"
    r = build(src, overlay, out)
    assert r.returncode == 0, r.stderr
    for rel in ("__pycache__", "vera_store.json", ".git", "run.log", "leak.py"):
        assert not (out / "vera_base" / "verantyx" / rel).exists()
    by_source = {e["source_path"]: e for e in manifest_of(out)["excluded"]}
    expect = {
        "verantyx/__pycache__/m.cpython-311.pyc": "cache",
        "verantyx/vera_store.json": "store_data",
        "verantyx/.git/config": "vcs",
        "verantyx/run.log": "measurement",
        "verantyx/leak.py": "personal_path",
    }
    for source, rule in expect.items():
        assert by_source[source]["rule"] == rule, source
        assert by_source[source]["reason"]
    assert by_source["verantyx/leak.py"]["lines"] == [1]
    assert "someone" not in json.dumps(manifest_of(out))        # line contents are never recorded
    counts = manifest_of(out)["counts"]["excluded_by_rule"]
    assert counts == {"cache": 1, "measurement": 1, "personal_path": 1, "store_data": 1, "vcs": 1, "vcs_ignored": 0}
    chk = run(CHECK, out, "--checks", "p4")
    assert chk.returncode == 0, chk.stdout
    report = json.loads(chk.stdout)
    assert report["checks"]["p4"]["status"] == "PASS" and report["out_unchanged"] is True


def test_p4_check_detects_contamination(synth, tmp_path):
    src, overlay = synth
    out = tmp_path / "out"
    assert build(src, overlay, out).returncode == 0
    write(out / "vera_base" / "verantyx" / "vera_store.json", "{}")
    write(out / "vera_base" / "verantyx" / "note.txt", "see " + "/" + "Users" + "/x\n")
    chk = run(CHECK, out, "--checks", "p4")
    assert chk.returncode == 1
    p4 = json.loads(chk.stdout)["checks"]["p4"]
    assert p4["status"] == "FAIL" and p4["counts"]["store_data"] == 1 and p4["counts"]["personal_path"] == 1


def test_vcs_unknown_states_are_typed_not_silent(synth, tmp_path):
    """A source tree that is not a git work tree: nothing is excluded on that ground, and the manifest says so."""
    src, overlay = synth
    out = tmp_path / "out"
    assert build(src, overlay, out).returncode == 0
    vcs = manifest_of(out)["vcs"]
    assert vcs["state"] == "UNKNOWN_NOT_A_GIT_TREE"
    assert vcs["untracked_included"] == []
    assert manifest_of(out)["counts"]["excluded_by_rule"]["vcs_ignored"] == 0


def _git(cwd, *args):
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r


def test_vcs_ignored_files_are_excluded_and_untracked_are_listed(synth, tmp_path):
    """git-ignored files (e.g. a local scratch .py and *.local.json) never reach the output; they are recorded."""
    src, overlay = synth
    write(src / ".gitignore", "verantyx/dialogue_context.py\n*.local.json\n")
    write(src / "verantyx" / "dialogue_context.py", "def f(:\n")          # unparseable local scratch, ignored
    write(src / "verantyx" / "my.local.json", '{"token": "x"}\n')           # ignored by pattern
    write(src / "verantyx" / "datadir" / "also.local.json", "{}\n")          # ignored in a sub-directory
    write(src / "verantyx" / "forced.local.json", "{}\n")                    # ignored but tracked (force-added): kept
    write(overlay / "vera_base" / "mine.local.json", "{}\n")                  # the overlay layer follows the same rule
    out = tmp_path / "out"
    if shutil.which("git") is None:
        # no git here: the typed state is what must be recorded, and nothing may be excluded on that ground
        r = build(src, overlay, out)
        assert r.returncode == 0, r.stderr
        assert manifest_of(out)["vcs"]["state"] == "UNKNOWN_GIT_MISSING"
        assert (out / "vera_base" / "verantyx" / "my.local.json").is_file()
        return
    _git(src, "init", "-q", ".")
    _git(src, "add", "verantyx/__init__.py", "verantyx/sub/__init__.py")
    _git(src, "add", "-f", "verantyx/forced.local.json")
    ignored_listing = _git(src, "ls-files", "--others", "--ignored", "--exclude-standard").stdout.split()
    assert "verantyx/dialogue_context.py" in ignored_listing           # the scenario really is a git-ignored one
    r = build(src, overlay, out)
    assert r.returncode == 0, r.stderr
    m = manifest_of(out)
    assert m["vcs"]["state"] == "GIT_WORK_TREE"
    pkg = out / "vera_base" / "verantyx"
    assert not (pkg / "dialogue_context.py").exists() and not (pkg / "my.local.json").exists()
    assert not (pkg / "datadir" / "also.local.json").exists()
    assert not (out / "vera_base" / "mine.local.json").exists()
    assert (pkg / "forced.local.json").is_file()                        # tracked: never excluded by the ignore rule
    by_source = {e["source_path"]: e for e in m["excluded"]}
    for source, layer in (("verantyx/dialogue_context.py", "package"), ("verantyx/my.local.json", "package"),
                          ("verantyx/datadir/also.local.json", "package"), ("public_overlay/vera_base/mine.local.json", "overlay")):
        assert by_source[source]["rule"] == "vcs_ignored" and by_source[source]["layer"] == layer, source
    assert m["counts"]["excluded_by_rule"]["vcs_ignored"] == 4 == m["counts"]["excluded_total"]
    # untracked, non-ignored files of the package layer are included and made visible; tracked ones are not listed
    untracked = m["vcs"]["untracked_included"]
    assert "vera_base/verantyx/sub/m.py" in untracked and "vera_base/verantyx/datadir/x.json" in untracked
    assert "vera_base/verantyx/__init__.py" not in untracked and "vera_base/verantyx/forced.local.json" not in untracked
    assert m["counts"]["untracked_included_total"] == len(untracked)
    assert (pkg / "sub" / "m.py").is_file()


def test_users_global_ignore_files_do_not_change_the_output(synth, tmp_path):
    """The result must not depend on who runs the tool: the user's DEFAULT global ignore file
    ($XDG_CONFIG_HOME/git/ignore, $HOME/.config/git/ignore) names an ordinary untracked file; it must stay."""
    import os
    src, overlay = synth
    out_plain, out_xdg, out_home = tmp_path / "o_plain", tmp_path / "o_xdg", tmp_path / "o_home"
    if shutil.which("git") is None:
        r = build(src, overlay, out_plain)
        assert r.returncode == 0, r.stderr
        assert manifest_of(out_plain)["vcs"]["state"] == "UNKNOWN_GIT_MISSING"   # typed record instead of a skip
        return
    _git(src, "init", "-q", ".")
    xdg, home = tmp_path / "xdg", tmp_path / "home"
    for d in (xdg / "git", home / ".config" / "git"):
        d.mkdir(parents=True)
        (d / "ignore").write_text("x.json\n", encoding="utf-8")                # names verantyx/datadir/x.json
    base = {k: v for k, v in os.environ.items() if k not in ("HOME", "XDG_CONFIG_HOME")}
    r_plain = build(src, overlay, out_plain, env={**base, "HOME": str(tmp_path / "empty_home")})
    r_xdg = build(src, overlay, out_xdg, env={**base, "HOME": str(tmp_path / "empty_home"), "XDG_CONFIG_HOME": str(xdg)})
    r_home = build(src, overlay, out_home, env={**base, "HOME": str(home)})
    for r in (r_plain, r_xdg, r_home):
        assert r.returncode == 0, r.stderr
    # the scenario is real: the same git, asked the ordinary way under that environment, WOULD list the file as ignored
    ignored = subprocess.run(["git", "-C", str(src), "ls-files", "--others", "--ignored", "--exclude-standard"],
                             capture_output=True, text=True, env={**base, "HOME": str(home)}).stdout.split()
    assert "verantyx/datadir/x.json" in ignored
    for out in (out_plain, out_xdg, out_home):
        assert (out / "vera_base" / "verantyx" / "datadir" / "x.json").is_file()
        assert manifest_of(out)["counts"]["excluded_by_rule"]["vcs_ignored"] == 0
    assert (out_plain / "manifest.json").read_bytes() == (out_xdg / "manifest.json").read_bytes() \
        == (out_home / "manifest.json").read_bytes()
    assert (out_plain / "pyproject.toml").read_bytes() == (out_xdg / "pyproject.toml").read_bytes() \
        == (out_home / "pyproject.toml").read_bytes()


def test_ignored_module_that_is_imported_stops_the_build(synth, tmp_path):
    src, overlay = synth
    write(src / ".gitignore", "verantyx/scratch.py\n")
    write(src / "verantyx" / "scratch.py", "Y = 1\n")
    write(src / "verantyx" / "sub" / "m.py", "from .. import scratch\n")
    out = tmp_path / "out"
    if shutil.which("git") is None:
        r = build(src, overlay, out)           # no git: nothing is excluded on that ground, and that is typed
        assert r.returncode == 0, r.stderr
        assert manifest_of(out)["vcs"]["state"] == "UNKNOWN_GIT_MISSING"
        return
    _git(src, "init", "-q", ".")
    r = build(src, overlay, out)
    assert r.returncode == 2
    assert json.loads(r.stderr.strip().splitlines()[-1])["error"] == "EXCLUDED_MODULE_IMPORTED"
    assert not out.exists()


def test_excluded_module_imported_stops_the_build(synth, tmp_path):
    src, overlay = synth
    write(src / "verantyx" / "leak.py", "P = '" + "/" + "Users" + "/someone/x'\n")
    write(src / "verantyx" / "sub" / "m.py", "from .. import leak\n")
    out = tmp_path / "out"
    r = build(src, overlay, out)
    assert r.returncode == 2
    assert json.loads(r.stderr.strip().splitlines()[-1])["error"] == "EXCLUDED_MODULE_IMPORTED"
    assert not out.exists()
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".build_public_")]


def test_path_collision_stops_the_build(synth, tmp_path):
    src, overlay = synth
    write(overlay / "vera_base" / "verantyx" / "sub" / "m.py", "X = 2\n")
    out = tmp_path / "out"
    r = build(src, overlay, out)
    assert r.returncode == 2
    err = json.loads(r.stderr.strip().splitlines()[-1])
    assert err["error"] == "PATH_COLLISION" and err["path"] == "vera_base/verantyx/sub/m.py"
    assert not out.exists()


def test_out_not_empty_is_refused_and_nothing_is_removed(synth, tmp_path):
    src, overlay = synth
    out = tmp_path / "out"
    write(out / "keep.txt", "precious\n")
    r = build(src, overlay, out)
    assert r.returncode == 2
    assert json.loads(r.stderr.strip().splitlines()[-1])["error"] == "OUT_NOT_EMPTY"
    assert (out / "keep.txt").read_text(encoding="utf-8") == "precious\n"


def test_real_tree_is_assembled_by_rule(tmp_path):
    out = tmp_path / "real"
    r = build(ROOT, ROOT / "public_overlay", out)
    assert r.returncode == 0, r.stderr
    pkg_src = ROOT / "verantyx"
    pkg_out = out / "vera_base" / "verantyx"
    assert (pkg_out / "domains" / "__init__.py").is_file()
    for pat in ("failure_packs/*.json", "constructions/*.py", "lang_data/*.json", "data/*.json", "*.html"):
        want = {p.relative_to(pkg_src).as_posix() for p in pkg_src.glob(pat)
                if ("/" + "Users" + "/").encode() not in p.read_bytes()}
        got = {p.relative_to(pkg_out).as_posix() for p in pkg_out.glob(pat)}
        assert want, pat
        assert want == got, pat
    chk = run(CHECK, out, "--checks", "p4,c")
    assert chk.returncode == 0, chk.stdout
    checks = json.loads(chk.stdout)["checks"]
    assert checks["p4"]["status"] == "PASS" and checks["c"]["status"] == "PASS"
