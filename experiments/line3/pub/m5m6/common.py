"""PUB-M5/M6 measurement helpers (offline, no model, no API).  Shared by meter.py, bank_ls_dev.py, templates.py, perf.py.

`m2` is the PUB-M2 measurement module (its `drive` replays writes into a real mem.v4 store); `C` is the memfix helper module (meter runs, plants, gold matching)."""
from __future__ import annotations

import collections
import importlib.util
import multiprocessing
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiments", "line3", "mem", "memfix"))

import memfix_common as C  # noqa: E402  (also puts experiments/line3/loom on the path and imports mem_run)
from verantyx.loom import memanswer as ma  # noqa: E402
from verantyx.loom import memask as mask  # noqa: E402
from verantyx.loom import memory as mem  # noqa: E402

DEFAULT_WORKERS = 4                         # the CI runner has 4 vCPU
OUT = HERE                                  # every output is written next to the scripts, under experiments/line3/pub/m5m6/


def load_m2() -> Any:
    path = os.path.join(ROOT, "experiments", "line3", "pub", "m2", "measure.py")
    spec = importlib.util.spec_from_file_location("pub_m2_measure", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pub_m2_measure"] = mod
    spec.loader.exec_module(mod)
    return mod


def pmap(fn: Callable[[Any], Any], items: Sequence[Any], workers: int) -> List[Any]:
    """fn over items in `workers` processes, results in the order of `items` (deterministic)."""
    if workers <= 1 or len(items) <= 1:
        return [fn(x) for x in items]
    with multiprocessing.get_context("fork").Pool(workers) as pool:
        return pool.map(fn, items, chunksize=1)


def pct(a: int, b: int) -> Optional[float]:
    return round(100.0 * a / b, 1) if b else None


def write_json(path: str, obj: Any) -> None:
    import json
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=1) + "\n")


def write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def judge_recall(res: dict, kind: str, gold_vals: Sequence[str], lenient: bool) -> dict:
    """reached: every gold value is among the live answers; extra: live answers that are no gold value; exact: reached, nothing extra and the right verdict (plain / updated: ANSWER or UPDATED with the gold as
    its only answer; contradicted: CHOICE with exactly the gold values).  `answers` are the display texts of the live groups."""
    ans: List[str] = []
    for g in res.get("answers", []):
        for a in g["answers"]:
            if a not in ans:
                ans.append(a)
    hit = [any(C.match(g, a, lenient) for a in ans) for g in gold_vals]
    extra = [a for a in ans if not any(C.match(g, a, lenient) for g in gold_vals)]
    reached = bool(ans) and all(hit)
    if kind == "contradicted":
        exact = reached and not extra and res["verdict"] == "CHOICE" and len(res["answers"]) == len(gold_vals)
    else:
        exact = reached and not extra and res["verdict"] in ("ANSWER", "UPDATED")
    return {"reached": reached, "exact": exact, "extra": extra, "answers": ans}
