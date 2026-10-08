# pytest plugin (-p no_live_guard): a start of a codex / claude process is refused with OSError and logged to $W2G_GUARD_LOG
import json, os, subprocess
_Popen = subprocess.Popen
class _GuardPopen(_Popen):
    def __init__(self, args, *a, **k):
        argv = list(args) if isinstance(args, (list, tuple)) else [args]
        first = os.fspath(argv[0]) if argv else ""
        if os.path.basename(first) in ("codex", "claude"):
            with open(os.environ["W2G_GUARD_LOG"], "a", encoding="utf-8") as f:
                f.write(json.dumps({"argv0": first, "test": os.environ.get("PYTEST_CURRENT_TEST")}) + "\n")
            raise OSError("a live provider process is blocked by no_live_guard")
        super().__init__(args, *a, **k)
subprocess.Popen = _GuardPopen
