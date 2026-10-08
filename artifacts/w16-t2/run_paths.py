"""W16-t2 runner: ask / serve / chat(round5) の 3 入口に同じ文書・同じ問いを通して 1 問 1 行の JSONL にする。

  run_paths.py --tree DIR --set SETDIR --out OUT.jsonl --mode old|new [--vp R9DIR | --fileplacement placement.json] [--python PY]

SETDIR: questions.jsonl（{id, docs:[SETDIR/docs 下の名前], question, gold}）と docs/。
親は子プロセスを cwd=TREE・PYTHONPATH=TREE・環境変数を最小にして起こし、子は読み込まれた verantyx* の __file__ が TREE 配下であることを検査する（外れたら止める）。
ask（cli.main の ask --mode round5 --document）・serve（decode_grammar.read_turn の reading）・chat（chat --mode round5 --document --json に問いと /quit を渡す。r2 から旧でも流す）。
mode new は加えて doc_answer.answer を包んで記録した AnswerResult（入口ごと。旧には doc_answer が無いので None）。
"""
import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def child(a):
    tree = Path(a.tree).resolve()
    sys.path.insert(0, str(tree))
    from verantyx import cli, decode_grammar as G
    bad = [m.__file__ for n, m in list(sys.modules.items()) if n.startswith("verantyx") and getattr(m, "__file__", None) and not str(Path(m.__file__).resolve()).startswith(str(tree))]
    assert not bad, "verantyx loaded from outside the tree: %r" % bad
    if a.fileplacement:
        from verantyx import event_cross as EC, observe as O
        fp = O.FilePlacement.from_path(a.fileplacement)
        EC.default_lookup = lambda *x, **k: fp
    log = []
    if a.mode == "new":
        from verantyx import doc_answer
        orig = doc_answer.answer

        def spy(*x, **k):
            r = orig(*x, **k)
            log.append(json.loads(json.dumps(r, ensure_ascii=False, default=str)))     # deep copy now: the basis policy may change the dict afterwards
            return r
        doc_answer.answer = spy
        if a.extra_trigger:      # 実験用（採否は監査役）: 後段の引き金に型を足したときの測定。製品の既定ではない
            doc_answer.QC_TRIGGER = tuple(doc_answer.QC_TRIGGER) + tuple(a.extra_trigger.split(","))
    qs = [json.loads(l) for l in Path(a.set).joinpath("questions.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    docs_dir = Path(a.docs_dir).resolve() if a.docs_dir else Path(a.set).resolve() / "docs"
    with tempfile.TemporaryDirectory(prefix="w16t2_") as tmp:         # W16-t2 r2 (M4): nothing is left in /tmp
        store = str(Path(tmp) / "st.json")
        from verantyx import tui
        rows = []

        def run_main(argv):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = cli.main(argv)
            return rc, buf.getvalue()

        def jload(s):
            try:
                return json.loads(s)
            except ValueError:
                return None
        for q in qs:
            docs = [str(docs_dir / d) for d in q["docs"]]
            row = {"id": q["id"], "question": q["question"], "gold": q.get("gold"), "loaded_from": str(Path(cli.__file__).resolve())}
            log.clear()
            rc, out = run_main(["--store", store, "ask", "--mode", "round5"] + sum([["--document", d] for d in docs], []) + ["--", q["question"]])
            row["ask"] = {"rc": rc, "out": jload(out), "raw_head": None if jload(out) is not None else out[:300]}
            row["ar_ask"] = [dict(x) for x in log] if a.mode == "new" else None
            log.clear()
            try:
                recs = G.load_records(docs)
                reading, _qc = G.read_turn(q["question"], "factual", recs, docs)
            except Exception as exc:
                reading = {"type": "EXCEPTION", "state": type(exc).__name__, "reason": str(exc)[:200], "filler": None, "sources": []}
            row["serve"] = reading
            row["ar_serve"] = [dict(x) for x in log] if a.mode == "new" else None
            # r2: the old tree answers chat too (its row has ar_chat None: there is no doc_answer there)
            log.clear()
            it = iter([q["question"], "/quit"])
            orig_ri = tui.read_input
            tui.read_input = lambda *x, **k: next(it, None)
            try:
                rc, out = run_main(["--store", store, "chat", "--mode", "round5", "--json"] + sum([["--document", d] for d in docs], []))
            finally:
                tui.read_input = orig_ri
            body = "\n".join(l for l in out.split("\n") if not l.startswith("[round5]"))
            row["chat"] = {"rc": rc, "out": jload(body), "raw_head": None if jload(body) is not None else out[:300]}
            row["ar_chat"] = [dict(x) for x in log] if a.mode == "new" else None
            rows.append(row)
    Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in rows), encoding="utf-8")
    print("child done: %d rows, loaded_from=%s" % (len(rows), rows[0]["loaded_from"] if rows else None))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=("old", "new"), required=True)
    ap.add_argument("--vp")
    ap.add_argument("--fileplacement")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--docs-dir")
    ap.add_argument("--extra-trigger")
    ap.add_argument("--child", action="store_true")
    a = ap.parse_args()
    if a.child:
        return child(a)
    env = {"HOME": os.environ.get("HOME", ""), "PATH": "/usr/bin:/bin", "PYTHONPATH": a.tree, "PYTHONDONTWRITEBYTECODE": "1"}
    if a.vp:
        env["VERA_PLACEMENT"] = a.vp
    cmd = [a.python, os.path.abspath(__file__), "--child", "--tree", a.tree, "--set", os.path.abspath(a.set), "--out", os.path.abspath(a.out), "--mode", a.mode]
    if a.extra_trigger:
        cmd += ["--extra-trigger", a.extra_trigger]
    if a.docs_dir:
        cmd += ["--docs-dir", os.path.abspath(a.docs_dir)]
    if a.fileplacement:
        cmd += ["--fileplacement", os.path.abspath(a.fileplacement)]
    r = subprocess.run(cmd, env=env, cwd=a.tree)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
