"""E7: re-run, with the default entry, the three out-of-scope defects written in docs/CORPUS_INDEX.md section 11.

Output: oos_repro.json (the exact command line, the result's kind / verdict / text / basis_origin, the corpus
steps of the trace, and the first cited sources). Nothing here changes behaviour; it only asks.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parent.parent
PY = "/Users/motonisihikoudai/vera-wiring/env/bin/python"
IDX = "/Users/motonisihikoudai/Projects/vera-impl/build/p4-W1c"
CASES = [
    ("oos1_inflection", "窓を開けると、どうなりますか？", "with_index"),
    ("oos2_scene_family_tie", "湯気の中の朝の台所の様子を一文で描写してください。", "default"),
    ("oos2b_scene_family_tie_with_index", "湯気の中の朝の台所の様子を一文で描写してください。", "with_index"),
    ("oos3_fact_question_answered_from_generated", "富士山の高さは？", "with_index"),
]


def main() -> int:
    out = []
    for name, text, state in CASES:
        env = {k: v for k, v in os.environ.items() if k not in ("VERA_P4_INDEX", "VERA_W1C_INDEX")}
        env.update(PYTHONPATH=str(TREE), PYTHONDONTWRITEBYTECODE="1")
        if state == "with_index":
            env["VERA_P4_INDEX"] = IDX
        p = subprocess.run([PY, "-m", "verantyx.cli", "ask", text], capture_output=True, text=True, env=env, cwd=str(TREE), timeout=600)
        s = p.stdout
        r = json.loads(s[s.find("{"):])
        cmd = (("VERA_P4_INDEX=" + IDX + " ") if state == "with_index" else "env -u VERA_P4_INDEX ") + \
              f"PYTHONPATH=<ツリー> PYTHONDONTWRITEBYTECODE=1 python -m verantyx.cli ask \"{text}\""
        out.append(dict(
            name=name, state=state, command=cmd, kind=r.get("kind"), verdict=r.get("verdict"), ability=r.get("ability"),
            text=r.get("text"), basis_origin=r.get("basis_origin"),
            corpus_trace=[dict(part=t.get("part"), family=t.get("family"), index=t.get("index"), frames=t.get("frames"))
                          for t in r.get("trace", []) if str(t.get("part", "")).startswith("ability_corpus")],
            first_sources=[dict(family=x.get("family"), origin=x.get("origin"), source_file=x.get("source_file"), line=x.get("line"),
                                text=str(x.get("text"))[:40]) for x in (r.get("sources") or [])[:2]]))
    (HERE / "oos_repro.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for o in out:
        print(o["name"], o["kind"], o["verdict"], o["basis_origin"], o["text"][:40], [(t["part"][-6:], t["family"], t["index"]) for t in o["corpus_trace"]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
