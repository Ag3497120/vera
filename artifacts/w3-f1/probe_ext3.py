"""JSONL を入口 verantyx.cli.main で流し id・kind・verdict・values・text・reason を TSV に。使い方: probe_ext3.py IN.jsonl OUT.tsv（このファイルのあるツリーを測る）"""
import contextlib, io, json, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from verantyx import cli
lines = ["id\tkind\tform\tdocument\tquestion\tverdict\tvalues\ttext\treason"]
for l in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    if not l.strip(): continue
    r = json.loads(l)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); (td / "d.txt").write_text(r["document"] + "\n", encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.main(["--store", str(td / "st.json"), "ask", "--mode", "round5", "--document", str(td / "d.txt"), "--", r["question"]])
        o = json.loads(buf.getvalue())
    reason = o.get("reason") or o.get("reasons") or o.get("abstain_reason") or ""
    if not isinstance(reason, str): reason = json.dumps(reason, ensure_ascii=False)
    lines.append("\t".join([r["id"], r["kind"], r.get("form", ""), r["document"], r["question"], str(o.get("verdict")),
                 json.dumps(o.get("values", []), ensure_ascii=False), (o.get("text") or "").replace("\n", " "), reason.replace("\n", " ").replace("\t", " ")]))
Path(sys.argv[2]).write_text("\n".join(lines) + "\n", encoding="utf-8")
print(len(lines) - 1)
