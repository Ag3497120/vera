"""W5-c round 3 entrance demo: `python -m verantyx.cli ask` in a subprocess (the child's environment is the bank
scorer's: HOME and VERA_CORPUS_ROOT are empty temp dirs, no VERA_P4_INDEX / VERA_SOVEREIGN_* unless a case sets
the index). Usage: r3_cli_demo.py TREE WORKDIR   (WORKDIR is created fresh under the scratchpad, outside the tree)."""
import json, os, sqlite3, subprocess, sys
from pathlib import Path

tree, work = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(tree))
from tools.build_p4_corpus_index import build            # noqa: E402

work.mkdir(parents=True, exist_ok=True)
home, corpus = work / "home", work / "corpus"
home.mkdir(exist_ok=True); corpus.mkdir(exist_ok=True)
memo = work / "memo.txt"
memo.write_text("花子は太郎に資料を渡した。", encoding="utf-8")
memo2 = work / "memo2.txt"
memo2.write_text("花子が太郎に資料を渡した。", encoding="utf-8")        # the document tests/test_one_request_goal_route.py uses
Q_DOC = "誰が太郎に資料を渡しましたか？"
Q_PARA = "資料の出来事を一文で言い換えてください。"
Q_IDX = "雨の日に傘を持たずに外出すると、どうなりますか？"
ROWS = ["雨の日に傘を持たずに出たら、髪が濡れた。", "雨の日に傘を持たずに出たら、服が濡れた。"]
src = work / "local.jsonl"
src.write_text("".join(json.dumps({"text": t, "source": f"g{i}", "scene": "雨", "sha": f"h{i}"}, ensure_ascii=False)
                       + "\n" for i, t in enumerate(ROWS)), encoding="utf-8")
build(src, work / "idx_null" / "local.db", "local")
with sqlite3.connect(work / "idx_null" / "local.db") as con:
    con.execute("UPDATE rows SET origin = NULL")


def run(label, q, *args, index=None):
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(home), "VERA_CORPUS_ROOT": str(corpus),
           "PYTHONPATH": str(tree), "PYTHONDONTWRITEBYTECODE": "1"}
    if index:
        env["VERA_P4_INDEX"] = str(work / index)
    cmd = [sys.executable, "-m", "verantyx.cli", "--store", str(work / "s.json"), "ask", q, *args]
    done = subprocess.run(cmd, cwd=tree, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=180)
    out = json.loads(done.stdout)
    n = out.get("basis_policy", {})
    print(f"## {label}\n   argv: ask <Q> {' '.join(args)}   index={index}")
    print(f"   rc={done.returncode} kind={out.get('kind')} verdict={out.get('verdict')} outcome={n.get('outcome')} "
          f"basis={n.get('basis')} unknown_origin={n.get('counts', {}).get('unknown_origin')} "
          f"classify_version={n.get('classify_version')} text={str(out.get('text'))[:40]!r}")


print("tree:", tree)
run("(a) round5 + --document: the user's own document answers", Q_DOC, "--mode", "round5", "--document", str(memo))
run("(b) round5 + --document: a request to rephrase the document", Q_PARA, "--mode", "round5", "--document", str(memo2))
run("(c1) NULL-origin index, plain", Q_IDX, index="idx_null")
run("(c2) NULL-origin index, human present", Q_IDX, "--human-present", index="idx_null")
run("(c3) NULL-origin index, human present + reference column", Q_IDX, "--human-present",
    "--show-generated-reference", index="idx_null")
