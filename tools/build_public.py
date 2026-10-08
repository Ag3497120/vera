#!/usr/bin/env python3
"""Assemble the public layout (vera_base/verantyx/... + overlay) from the development tree.

    python tools/build_public.py --out <dir> [--src <devtree>] [--overlay <dir>]

Standard library only; it never imports verantyx (discovery is done on the file system).

Layers
  package  every file under <src>/verantyx/, found by walking the tree (no hand-written file
           list), copied to vera_base/verantyx/<same relative path>
  overlay  every file under <overlay>/ (the files that exist only on the public side), copied
           to <same relative path>
  generated  pyproject.toml: the overlay's file with its [tool.setuptools.package-data] table
           regenerated from what was found (declared as CONSTRUCTED in manifest.json)

Exclusions are rules, not names: each has an id and a reason, and every excluded file is counted
in manifest.json. A tie between the layers is not broken: the build stops (PATH_COLLISION).
An excluded module that a bundled module still imports stops the build (EXCLUDED_MODULE_IMPORTED).

Exit codes: 0 success / 2 typed error (one JSON line on stderr).
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import warnings
from pathlib import Path, PurePosixPath

SCHEMA = "vera_public_build_manifest_v1"
PKG_ROOT_NAME = "verantyx"          # the directory of the development tree that is the package
OUT_PKG_PREFIX = "vera_base/verantyx"  # where it lands in the public layout
WRAPPER_ROOT = "vera_base"
PYPROJECT = "pyproject.toml"
MANIFEST = "manifest.json"
# "Users directory" absolute-path marker, kept as hex so that neither this file nor the manifest
# carries the literal personal-path string.
PERSONAL_PATTERN_HEX = "2f55736572732f"
PERSONAL_PATTERN = bytes.fromhex(PERSONAL_PATTERN_HEX)

CACHE_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
CACHE_EXTS = {".pyc", ".pyo"}
CACHE_NAMES = {".DS_Store"}
MEASUREMENT_DIRS = {"experiments", "results", "artifacts"}
MEASUREMENT_EXTS = {".log"}
STORE_PREFIX = "vera_store."

# (id, reason, how it is decided). First matching rule wins and is the one counted.
EXCLUDE_RULES = [
    ("vcs", "version-control data", "a path component is .git"),
    ("cache", "interpreter / tool caches",
     "a path component is __pycache__, .pytest_cache, .mypy_cache or .ruff_cache; or the extension is .pyc/.pyo; or the name is .DS_Store"),
    ("store_data", "real data of a Vera store (personal / environment data)",
     "the file name starts with vera_store."),
    ("measurement", "measurement outputs and run logs (not part of the product)",
     "the extension is .log; or a path component is experiments, results or artifacts"),
    ("personal_path", "contains an absolute path under a Users directory (personal environment)",
     "the file bytes contain the marker whose hex is " + PERSONAL_PATTERN_HEX + "; only line numbers are recorded"),
    ("vcs_ignored", "ignored by version control: a local-only file that the author's own ignore rules name",
     "git lists the file as untracked AND ignored (git ls-files --others --ignored --exclude-standard); a tracked file is never excluded by this rule"),
]
RULE_REASON = {rid: reason for rid, reason, _ in EXCLUDE_RULES}


class BuildError(Exception):
    def __init__(self, code: str, detail: str, **extra):
        super().__init__(code)
        self.code, self.detail, self.extra = code, detail, extra

    def as_json(self) -> str:
        return json.dumps({"error": self.code, "detail": self.detail, **self.extra},
                          ensure_ascii=False, sort_keys=True)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def classify(rel: PurePosixPath, data: bytes, ignored: frozenset = frozenset()) -> tuple[str, list[int] | None] | None:
    """Return (rule_id, lines) when `rel` (relative to its layer root) is excluded, else None.

    `ignored` holds the layer-relative paths that git reports as untracked and ignored."""
    parts = rel.parts
    name = parts[-1]
    if ".git" in parts:
        return "vcs", None
    if any(p in CACHE_DIRS for p in parts) or PurePosixPath(name).suffix in CACHE_EXTS or name in CACHE_NAMES:
        return "cache", None
    if name.startswith(STORE_PREFIX):
        return "store_data", None
    if PurePosixPath(name).suffix in MEASUREMENT_EXTS or any(p in MEASUREMENT_DIRS for p in parts[:-1]):
        return "measurement", None
    if PERSONAL_PATTERN in data:
        lines = [i for i, ln in enumerate(data.split(b"\n"), 1) if PERSONAL_PATTERN in ln]
        return "personal_path", lines
    if str(rel) in ignored:
        return "vcs_ignored", None
    return None


def _git(src: Path, *args: str):
    """Run git in `src` without the user's global / system configuration. Returns CompletedProcess.

    Three things would otherwise let the result depend on who runs the tool: ~/.gitconfig and the system
    config (switched off by the two GIT_CONFIG_* variables) and the DEFAULT global ignore file
    ($XDG_CONFIG_HOME/git/ignore, else $HOME/.config/git/ignore), which git reads even when no config names it
    (switched off by core.excludesFile=/dev/null). The ignore rules that are still read are the ones that live
    with the clone: .gitignore files inside the tree (nested ones too) and .git/info/exclude."""
    env = dict(os.environ)
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_OPTIONAL_LOCKS": "0"})
    return subprocess.run(["git", "-c", "core.excludesFile=" + os.devnull, "-C", str(src), *args],
                          capture_output=True, env=env)


def git_survey(src: Path, layer_dirs: dict[str, str | None]) -> tuple[dict, dict[str, set], dict[str, list]]:
    """Ask git which files of each layer directory are ignored / untracked.

    `layer_dirs` maps a layer name to its directory relative to `src` (None when the layer lies outside
    `src`, where git cannot speak for it). Returns (vcs record for the manifest, ignored paths per layer,
    untracked paths per layer); both path sets are relative to the layer directory.
    Anything git cannot answer is recorded with a typed state, never read as "nothing is ignored"."""
    ignored: dict[str, set] = {k: set() for k in layer_dirs}
    untracked: dict[str, list] = {k: [] for k in layer_dirs}
    record: dict = {"state": None, "layers_not_checked": sorted(k for k, v in layer_dirs.items() if v is None)}
    try:
        top = _git(src, "rev-parse", "--show-toplevel")
    except OSError:
        record["state"] = "UNKNOWN_GIT_MISSING"
        return record, ignored, untracked
    if top.returncode != 0 or Path(top.stdout.decode("utf-8", "replace").strip()).resolve() != src:
        record["state"] = "UNKNOWN_NOT_A_GIT_TREE"
        return record, ignored, untracked
    for layer, rel_dir in layer_dirs.items():
        if rel_dir is None:
            continue
        for kind, flags in (("ignored", ["--others", "--ignored", "--exclude-standard"]),
                            ("untracked", ["--others", "--exclude-standard"])):
            r = _git(src, "ls-files", "-z", *flags, "--", rel_dir)
            if r.returncode != 0:
                record["state"] = "UNKNOWN_GIT_ERROR"
                record["failed"] = f"git ls-files ({kind}) exited {r.returncode}"
                return record, {k: set() for k in layer_dirs}, {k: [] for k in layer_dirs}
            for raw in r.stdout.split(b"\0"):
                if not raw:
                    continue
                full = PurePosixPath(raw.decode("utf-8", "surrogateescape"))
                inner = str(full.relative_to(rel_dir)) if rel_dir != "." else str(full)
                (ignored[layer].add(inner) if kind == "ignored" else untracked[layer].append(inner))
    record["state"] = "GIT_WORK_TREE"
    return record, ignored, untracked


def walk_layer(root: Path):
    """Yield (relative PurePosixPath, bytes) for every regular file, in sorted order."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fn in sorted(filenames):
            full = Path(dirpath) / fn
            if not full.is_file():      # broken symlink etc.: not a file we can copy
                continue
            rel = PurePosixPath(*full.relative_to(root).parts)
            yield rel, full.read_bytes()


def module_name(out_rel: str) -> tuple[str, bool] | None:
    """Importable module name of an output path of a .py file, and whether it is a package init."""
    p = PurePosixPath(out_rel)
    if p.suffix != ".py":
        return None
    parts = list(p.parts)
    if parts[:2] == [WRAPPER_ROOT, PKG_ROOT_NAME]:
        parts = parts[1:]                    # vera_base is on sys.path: `verantyx.x`
    elif parts[0] != WRAPPER_ROOT:
        return None                          # not importable code of the package
    is_init = parts[-1] == "__init__.py"
    parts = parts[:-1] if is_init else parts[:-1] + [p.stem]
    return ".".join(parts), is_init


def import_targets(modname: str, is_init: bool, tree: ast.AST) -> set[str]:
    """Dotted names that the module may be importing (candidates, both module and attribute)."""
    pkg = modname if is_init else modname.rpartition(".")[0]
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg.split(".") if pkg else []
                cut = node.level - 1
                if cut > len(base):
                    continue
                base = base[:len(base) - cut]
                target = ".".join(base + ([node.module] if node.module else []))
            else:
                target = node.module or ""
            if target:
                out.add(target)
            for a in node.names:
                out.add((target + "." if target else "") + a.name)
    return out


def generate_package_data(out_files: dict[str, bytes]) -> tuple[dict[str, list[str]], list[str]]:
    """Packages (dotted) and the package-data globs, both derived from the assembled files."""
    inits = {str(PurePosixPath(p).parent) for p in out_files
             if PurePosixPath(p).name == "__init__.py" and PurePosixPath(p).parts[0] == WRAPPER_ROOT}
    packages = sorted(d.replace("/", ".") for d in inits)
    data: dict[str, set[str]] = {}
    for p in out_files:
        pp = PurePosixPath(p)
        if pp.parts[0] != WRAPPER_ROOT or pp.suffix == ".py":
            continue
        anc = pp.parent
        while str(anc) not in inits and anc != PurePosixPath("."):
            anc = anc.parent
        if str(anc) not in inits:
            continue
        rel = pp.relative_to(anc)
        glob_name = ("*" + pp.suffix) if pp.suffix else pp.name
        pat = str(rel.parent / glob_name) if rel.parent != PurePosixPath(".") else glob_name
        data.setdefault(str(anc).replace("/", "."), set()).add(pat)
    return {k: sorted(v) for k, v in sorted(data.items())}, packages


def render_package_data(table: dict[str, list[str]]) -> str:
    lines = ["[tool.setuptools.package-data]"]
    for pkg, pats in table.items():
        lines.append(f"{json.dumps(pkg, ensure_ascii=False)} = [{', '.join(json.dumps(x, ensure_ascii=False) for x in pats)}]")
    return "\n".join(lines) + "\n"


_HEADER = re.compile(r"^\[tool\.setuptools\.package-data\]\s*$")


def rewrite_pyproject(text: str, table: dict[str, list[str]]) -> str:
    lines = text.splitlines(keepends=True)
    start = next((i for i, ln in enumerate(lines) if _HEADER.match(ln)), None)
    block = render_package_data(table)
    if start is None:
        sep = "" if (not text or text.endswith("\n")) else "\n"
        new = text + sep + ("\n" if text else "") + block
    else:
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if lines[j].lstrip().startswith("["):
                end = j
                break
        tail = lines[end:]
        new = "".join(lines[:start]) + block + ("\n" if tail else "") + "".join(tail)
    got = tomllib.loads(new).get("tool", {}).get("setuptools", {}).get("package-data")
    if got != table:
        raise RuntimeError("generated package-data table does not read back identically")
    return new


def assemble(src: Path, overlay: Path, stage: Path) -> dict:
    pkg_dir = src / PKG_ROOT_NAME
    if not pkg_dir.is_dir():
        raise BuildError("SRC_MISSING", f"no {PKG_ROOT_NAME}/ directory under the source tree")
    if not overlay.is_dir():
        raise BuildError("OVERLAY_MISSING", "overlay directory not found")
    if not (overlay / PYPROJECT).is_file():
        raise BuildError("PYPROJECT_MISSING", f"overlay has no {PYPROJECT}")

    def rel_to_src(d: Path) -> str | None:
        try:
            r = d.resolve().relative_to(src)
        except ValueError:
            return None
        return str(PurePosixPath(*r.parts)) if r.parts else "."

    vcs, ignored_by_layer, untracked_by_layer = git_survey(
        src, {"package": rel_to_src(pkg_dir), "overlay": rel_to_src(overlay)})

    included: dict[str, tuple[str, bytes]] = {}     # out path -> (origin, bytes)
    excluded: list[dict] = []
    excluded_mods: dict[str, str] = {}              # module name -> source path (for the import check)

    def take(layer: str, root: Path, out_prefix: str, src_prefix: str):
        for rel, data in walk_layer(root):
            out_path = (out_prefix + "/" + str(rel)) if out_prefix else str(rel)
            hit = classify(rel, data, frozenset(ignored_by_layer[layer]))
            if hit:
                rule, lines = hit
                rec = {"source_path": f"{src_prefix}/{rel}" if src_prefix else str(rel),
                       "layer": layer, "rule": rule, "reason": RULE_REASON[rule]}
                if lines is not None:
                    rec["lines"] = lines
                excluded.append(rec)
                mn = module_name(out_path)
                if mn:
                    excluded_mods[mn[0]] = rec["source_path"]
                continue
            if out_path in included:
                raise BuildError("PATH_COLLISION", "two layers provide the same output path; neither is chosen",
                                 path=out_path, layers=[included[out_path][0], layer])
            included[out_path] = (layer, data)
            if layer == "package" and str(rel) in untracked_set:
                untracked_included.append(out_path)

    untracked_set = set(untracked_by_layer["package"])     # only the product layer reports untracked files
    untracked_included: list[str] = []
    take("package", pkg_dir, OUT_PKG_PREFIX, PKG_ROOT_NAME)
    take("overlay", overlay, "", "public_overlay")

    if MANIFEST in included:
        raise BuildError("PATH_COLLISION", "overlay provides the manifest path", path=MANIFEST)

    # D4: a bundled module must not import a module that was excluded.
    unparsed: list[str] = []
    for out_path in sorted(included):
        mn = module_name(out_path)
        if not mn:
            continue
        try:
            with warnings.catch_warnings():     # product code is read, not run: its own warnings are not ours
                warnings.simplefilter("ignore")
                tree = ast.parse(included[out_path][1], filename=out_path)
        except (SyntaxError, ValueError):
            unparsed.append(out_path)
            continue
        hit = sorted(t for t in import_targets(mn[0], mn[1], tree) if t in excluded_mods)
        if hit:
            raise BuildError("EXCLUDED_MODULE_IMPORTED",
                             "a bundled module imports a module that an exclusion rule removed",
                             importer=out_path, imported=hit, excluded_source=[excluded_mods[h] for h in hit])

    # pyproject: regenerate the package-data table from what was found.
    plain = {p: d for p, (_, d) in included.items()}
    table, packages = generate_package_data(plain)
    overlay_pyproject = included.pop(PYPROJECT)[1]
    new_pyproject = rewrite_pyproject(overlay_pyproject.decode("utf-8"), table).encode("utf-8")
    included[PYPROJECT] = ("generated", new_pyproject)

    # write
    for out_path in sorted(included):
        dest = stage / out_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(included[out_path][1])

    files = []
    for out_path in sorted(included):
        origin, data = included[out_path]
        rec = {"path": out_path, "origin": origin, "sha256": sha256_bytes(data), "bytes": len(data)}
        if origin in ("overlay", "generated"):
            counterpart = src / out_path
            if not counterpart.is_file():
                rec["dev_counterpart"] = "absent"
            else:
                rec["dev_counterpart"] = "same" if counterpart.read_bytes() == data else "differs"
        if origin == "generated":
            rec["kind"] = "CONSTRUCTED"
        files.append(rec)
    excluded.sort(key=lambda r: (r["layer"], r["source_path"]))

    by_origin = {k: sum(1 for f in files if f["origin"] == k) for k in ("package", "overlay", "generated")}
    by_rule = {rid: sum(1 for e in excluded if e["rule"] == rid) for rid, _, _ in EXCLUDE_RULES}
    vcs["untracked_included"] = sorted(untracked_included)
    vcs["untracked_policy"] = ("untracked, non-ignored files of the package layer are INCLUDED and listed here; "
                               "ignored ones are excluded by rule vcs_ignored; the overlay layer reports only ignored files")
    manifest = {
        "schema": SCHEMA,
        "rules": {
            "include": [
                {"id": "package_tree", "how": "every file found by walking verantyx/ is copied to " + OUT_PKG_PREFIX + "/<same relative path>; there is no file list"},
                {"id": "overlay_tree", "how": "every file found by walking the overlay directory is copied to <same relative path>"},
                {"id": "package_data", "how": "pyproject.toml's [tool.setuptools.package-data] table is regenerated from the non-.py files found under vera_base/ (nearest ancestor with __init__.py = the package)"},
            ],
            "exclude": [{"id": rid, "reason": reason, "test": how} for rid, reason, how in EXCLUDE_RULES],
            "exclude_order": "the first matching rule in the listed order is the one recorded and counted",
            "collision": "if the package layer and the overlay produce the same output path, the build stops with PATH_COLLISION (no layer wins)",
            "excluded_module_import": "if a bundled .py imports a module whose file was excluded, the build stops with EXCLUDED_MODULE_IMPORTED",
            "personal_path_pattern_hex": PERSONAL_PATTERN_HEX,
            "vcs_survey": "when --src is the root of a git work tree, git is asked which files are ignored (excluded by vcs_ignored) and which are untracked (included and listed in vcs.untracked_included, package layer only). The ignore rules read are those that live with the clone: .gitignore files inside the tree (nested ones included) and .git/info/exclude (a per-clone local rule file, so two clones of the same commit can differ). The user's global git config, the default global ignore file ($XDG_CONFIG_HOME/git/ignore or $HOME/.config/git/ignore) and the system config are NOT read. Otherwise vcs.state is UNKNOWN_GIT_MISSING / UNKNOWN_NOT_A_GIT_TREE / UNKNOWN_GIT_ERROR and no file is excluded on that ground",
        },
        "vcs": vcs,
        "packages": packages,
        "files": files,
        "excluded": excluded,
        "generated": [{"path": PYPROJECT, "part": "tool.setuptools.package-data", "kind": "CONSTRUCTED"}],
        "import_check": {"unparsed_python_files": unparsed},
        "counts": {
            "files_by_origin": by_origin,
            "files_total_excluding_manifest": len(files),
            "excluded_by_rule": by_rule,
            "excluded_total": len(excluded),
            "untracked_included_total": len(untracked_included),
            "note": "manifest.json is not listed in files (it cannot contain its own hash) and is not counted",
        },
    }
    (stage / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--src", default=None)
    ap.add_argument("--overlay", default=None)
    args = ap.parse_args(argv)

    src = Path(args.src).resolve() if args.src else Path(__file__).resolve().parent.parent
    overlay = Path(args.overlay).resolve() if args.overlay else src / "public_overlay"
    out = Path(args.out).absolute()
    stage = None
    try:
        if out.exists() and (not out.is_dir() or any(out.iterdir())):
            raise BuildError("OUT_NOT_EMPTY", "--out must not exist or must be an empty directory (nothing was changed)")
        resolved_out = out.resolve()
        if resolved_out == src or src in resolved_out.parents:
            raise BuildError("OUT_INSIDE_SRC", "--out must be outside the development tree")
        out.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".build_public_", dir=out.parent))
        manifest = assemble(src, overlay, stage)
        os.chmod(stage, 0o755)
        os.replace(stage, out)
        stage = None
    except BuildError as exc:
        print(exc.as_json(), file=sys.stderr)
        return 2
    finally:
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)
    print(json.dumps({"ok": True, "counts": manifest["counts"], "packages": len(manifest["packages"])},
                     ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
