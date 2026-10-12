"""Load experiments/line3/loom/mem_run.py as a module for the tests (the harness scripts are not a package)."""
import importlib.util
import os
import sys

from mem_common import ROOT

_PATH = os.path.join(ROOT, "experiments", "line3", "loom", "mem_run.py")


def load():
    if "mem_run" in sys.modules:
        return sys.modules["mem_run"]
    spec = importlib.util.spec_from_file_location("mem_run", _PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mem_run"] = mod
    spec.loader.exec_module(mod)
    return mod
