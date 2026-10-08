from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXPECTED_TRACKED_TESTS = {
    "tests/test_basis_policy_entry.py",
    "tests/test_basis_policy_form.py",
    "tests/test_basis_policy_table.py",
    "tests/test_basis_policy_w5c.py",
    "tests/test_basis_policy_w5c_r3.py",
    "tests/test_basis_policy_w5e.py",
}
FORBIDDEN_PRODUCT = (
    "verantyx/cli.py", "verantyx/semantic_read.py", "verantyx/sovereign.py", "verantyx/observe.py",
    "verantyx/event_cross.py", "verantyx/coarse_place.py", "verantyx/coarse_types.py",
)


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                          check=True).stdout


def main() -> None:
    status = git("status", "--short", "--untracked-files=all")
    changed = []
    for line in status.splitlines():
        path = line[3:]
        changed.append(path)
        allowed = (path in {"docs/READING_SOUNDNESS.md", "docs/BASIS_POLICY.md", "docs/OBSERVATION.md",
                            "verantyx/semantic_reader.py", "verantyx/basis_policy.py"}
                   or path.startswith("tests/") or path.startswith("artifacts/w5-f/"))
        if not allowed:
            raise SystemExit(f"out-of-scope path: {path}")
    tracked_tests = set(git("diff", "--name-only", "--", "tests/").splitlines())
    if tracked_tests != EXPECTED_TRACKED_TESTS:
        raise SystemExit(f"tracked test-file set differs: {sorted(tracked_tests)}")
    forbidden_changes = subprocess.run(["git", "-C", str(ROOT), "diff", "--stat", "--", *FORBIDDEN_PRODUCT],
                                       capture_output=True, text=True, check=True).stdout
    if forbidden_changes.strip():
        raise SystemExit(f"forbidden product changes:\n{forbidden_changes}")
    semantic_diff = git("diff", "-U0", "--", "verantyx/semantic_reader.py")
    deleted = sum(1 for line in semantic_diff.splitlines() if line.startswith("-") and not line.startswith("---"))
    if deleted:
        raise SystemExit(f"semantic_reader.py has {deleted} removed lines")
    result = ["scope=OK", f"status_paths={len(changed)}", "tracked_existing_test_files=" + ",".join(sorted(tracked_tests)),
              f"semantic_reader_removed_lines={deleted}", "semantic_reader_hunks:"]
    result.extend(line for line in semantic_diff.splitlines() if line.startswith("@@"))
    result.extend(("status:", status.rstrip()))
    output = ROOT / "artifacts/w5-f/scope_check.txt"
    output.write_text("\n".join(result) + "\n", encoding="utf-8")
    print(output.read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    main()
