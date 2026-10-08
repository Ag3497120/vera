#!/usr/bin/env python3
"""Probe whether failing tests fail because of the test side (stale stubs/expectations) or the product.

Each probe copies the tree to a temp directory, applies a mechanical change to the *tests only*
(never to verantyx/, except probe memory_brief which wraps the return type in the copy), runs the
named tests there, and prints the outcome. The real tree is never modified.
Output is the evidence cited by docs/BASELINE_W0-1.md.
"""
from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORE = shutil.ignore_patterns(".git", "artifacts", "__pycache__", "dist", "build")


def sub_files(root: Path, pattern: str, old: str, new: str, regex: bool = False) -> int:
    changed = 0
    for path in glob.glob(str(root / pattern)):
        text = Path(path).read_text(encoding="utf-8")
        out = re.sub(old, new, text, flags=re.M) if regex else text.replace(old, new)
        if out != text:
            Path(path).write_text(out, encoding="utf-8")
            changed += 1
    return changed


def pytest(root: Path, args: list[str], extra_path: str = "") -> tuple[str, list[str]]:
    """Run pytest in the copy; return (summary line, sorted ids of the tests that still fail)."""
    env = {"HOME": os.environ.get("HOME", ""), "PATH": "/usr/bin:/bin" + extra_path,
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(root)}
    done = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=no", "-rf", *args],
                          cwd=root, env=env, capture_output=True, text=True)
    lines = done.stdout.strip().splitlines()
    failed = sorted(line[len("FAILED "):].split(" - ")[0] for line in lines if line.startswith("FAILED "))
    summary = lines[-1] if lines else done.stderr.strip()[-300:]
    return summary, failed


def main() -> int:
    node = shutil.which("node")
    node_dir = (":" + str(Path(node).parent)) if node else ""
    scratch = ROOT / "artifacts" / "w0-1" / "tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="w01-probe-", dir=str(scratch)) as temp:
        results = []

        def fresh(name: str) -> Path:
            target = Path(temp) / name
            shutil.copytree(ROOT, target, ignore=IGNORE, symlinks=True)
            return target

        names_args = sorted(glob.glob(str(ROOT / "tests/attack/test_semantic_names_*.py")))
        base = fresh("names_base")
        results.append(("names/as-is", pytest(base, [str(p) for p in names_args])))
        probe = fresh("names")
        n = sub_files(probe, "tests/attack/test_semantic_names_*.py", '"名詞", "一般"', '"名詞", "普通名詞"')
        results.append((f"names/common-noun pos2 一般->普通名詞 in {n} test files",
                        pytest(probe, [str(probe / Path(p).relative_to(ROOT)) for p in names_args])))

        unknown_args = ["tests/attack/test_semantic_unknown_injection.py", "tests/attack/test_semantic_unknown_limits.py"]
        base = fresh("unk_base")
        results.append(("predicate_span/as-is", pytest(base, unknown_args)))
        probe = fresh("unk")
        sub_files(probe, "tests/attack/test_semantic_unknown_injection.py",
                  "id=\"c0\", predicate=predicate, span=clause_span, roles=role_nodes,",
                  "id=\"c0\", predicate=predicate, span=clause_span, roles=role_nodes, predicate_span=clause_span,")
        sub_files(probe, "tests/attack/test_semantic_unknown_limits.py",
                  "    span: SpanStub\n    roles: tuple[RoleStub, ...]\n",
                  "    span: SpanStub\n    roles: tuple[RoleStub, ...]\n\n    @property\n    def predicate_span(self):\n        return self.span\n")
        results.append(("predicate_span/stub gains predicate_span", pytest(probe, unknown_args)))

        brief_args = ["tests/attack/test_memory_brief_" + s + ".py"
                      for s in ("differential", "fabrication", "injection", "limits", "paraphrase")]
        base = fresh("brief_base")
        results.append(("memory_brief/as-is", pytest(base, brief_args)))
        probe = fresh("brief")
        sub_files(probe, "tests/attack/test_memory_brief_*.py", r'return \{"records": (.*)\}$',
                  r'return {"verdict": "ANSWER", "records": \1}', regex=True)
        brief_py = probe / "verantyx/memory_brief.py"
        text = brief_py.read_text(encoding="utf-8").replace("def compile_brief(", "def _compile_brief(", 1)
        brief_py.write_text(text + "\n\ndef compile_brief(*a, **k):\n    return _compile_brief(*a, **k).text\n", encoding="utf-8")
        results.append(("memory_brief/ask_about stub answers verdict=ANSWER + compile_brief returns .text (copy only)",
                        pytest(probe, brief_args)))

        if node:
            probe = fresh("lower")
            sub_files(probe, "tests/test_contract_lower.py", "    _vera_env.require(\"node_jitless_quiet\")\n", "")
            sub_files(probe, "tests/test_contract_lower.py", "if completed.returncode or completed.stderr:",
                      "if completed.returncode or completed.stderr.replace('Warning: disabling flag --expose_wasm due to conflicting flags\\n', ''):")
            results.append((f"contract_lower/node={node} with only the --expose_wasm warning tolerated",
                            pytest(probe, ["tests/test_contract_lower.py"], node_dir)))
        else:
            results.append(("contract_lower/no node on PATH", "not run"))

    for label, (summary, failed) in ((l, o if isinstance(o, tuple) else (o, [])) for l, o in results):
        print(f"{label}: {summary}")
        for test_id in failed:
            print(f"    STILL_FAILS {test_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
