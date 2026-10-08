"""smoke の終了コードと契約済みの標準出力形を記録する。"""
from __future__ import annotations

import json
from pathlib import Path
import sys


def _status(out: Path, name: str):
    try:
        return int((out / (name + ".exit")).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _json_object(path: Path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON の最上位が object ではありません")
    return value


def main(argv):
    mode = argv[1]
    out = Path(argv[2])
    checks = {}

    help_text = (out / "help.stdout").read_text(encoding="utf-8", errors="replace")
    checks["help"] = {
        "pass": _status(out, "help") == 0 and "usage: vera" in help_text,
        "exit_code": _status(out, "help"),
        "required_text_present": "usage: vera" in help_text,
    }
    try:
        read_result = _json_object(out / "read.stdout")
        read_shape = (
            read_result.get("schema") == "verantyx.semantic_read/1"
            and read_result.get("lang") == "ja"
            and type(read_result.get("readable")) is bool
            and isinstance(read_result.get("clauses"), list)
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        read_shape = False
    checks["read"] = {
        "pass": _status(out, "read") == 0 and read_shape,
        "exit_code": _status(out, "read"),
        "registered_output_shape": read_shape,
    }
    try:
        ask_result = _json_object(out / "ask.stdout")
        ask_shape = isinstance(ask_result.get("verdict"), str)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        ask_shape = False
    checks["ask"] = {
        "pass": _status(out, "ask") == 0 and ask_shape,
        "exit_code": _status(out, "ask"),
        "registered_output_shape": ask_shape,
    }
    checks["serve"] = {
        "pass": _status(out, "serve") == 0,
        "exit_code": _status(out, "serve"),
        "registered_output_shape": _status(out, "serve") == 0,
    }
    passed = all(row["pass"] for row in checks.values())
    result = {
        "verdict": "PASS" if passed else "FAIL",
        "mode": mode,
        "checks": checks,
        "all_smoke_checks_pass": passed,
    }
    (out / "p1-verification.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if passed or mode == "baseline" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
