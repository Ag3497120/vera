"""入口 verantyx.cli.main で拡張の 5 データを流し、id・kind・form/group・verdict・values・text・reason を TSV に。
使い方: measure_range_ext3.py OUT.tsv   （W3-f1 の作業ツリー＝このファイルのあるツリーを測る）"""
import contextlib, io, json, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from verantyx import cli
files = ["w3f1_prohibition.jsonl", "w3f1_time_place.jsonl", "w3f1_ext_range.jsonl", "w3f1_time_place_suffix.jsonl", "w3f1_prohibition_nde.jsonl"]
lines = ["file\tid\tkind\tgroup\tdocument\tquestion\tverdict\tvalues\ttext\treason"]
for fn in files:
    for l in (ROOT / "tests/reading_soundness" / fn).read_text(encoding="utf-8").splitlines():
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
        cells = [fn, r["id"], r["kind"], r.get("form") or r.get("group") or r.get("time_word", ""), r["document"], r["question"],
                 str(o.get("verdict")), json.dumps(o.get("values", []), ensure_ascii=False), (o.get("text") or "").replace("\n", " "), reason.replace("\n", " ").replace("\t", " ")]
        lines.append("\t".join(cells))
Path(sys.argv[1]).write_text("\n".join(lines) + "\n", encoding="utf-8")
print(len(lines) - 1)
