"""入口 verantyx.cli.main で凍結データを流し、verdict・values・text を TSV に。使い方: measure_range.py OUT.tsv OUT_TRUNC.tsv"""
import contextlib, io, json, sys, tempfile, unicodedata
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from verantyx import cli
NFKC = lambda s: unicodedata.normalize("NFKC", s)
rows = [json.loads(l) for l in (ROOT / "tests/reading_soundness/w3f1_kinship.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
out_all, out_bad = [], []
head = "id\tkind\tnoun\tverdict\tvalues\ttext\tflag"
for r in rows:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); (td / "d.txt").write_text(r["document"] + "\n", encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.main(["--store", str(td / "st.json"), "ask", "--mode", "round5", "--document", str(td / "d.txt"), "--", r["question"]])
        o = json.loads(buf.getvalue())
    vals = o.get("values", [])
    flag = ""
    if r["kind"] == "role":
        if o.get("verdict") == "ANSWER" and [NFKC(v) for v in vals] != [NFKC(v) for v in r["expect_values"]]:
            flag = "TRUNCATED" if all(NFKC(r["expect_values"][0]).startswith(NFKC(v)) for v in vals) and vals else "WRONG_VALUE"
        elif o.get("verdict") != "ANSWER":
            flag = "NOT_ANSWER"
    else:
        if o.get("verdict") == "ANSWER" and "はい" in (o.get("text") or ""):
            flag = "FALSE_YES"
    line = "\t".join([r["id"], r["kind"], r["noun"], str(o.get("verdict")), json.dumps(vals, ensure_ascii=False), (o.get("text") or "").replace("\n", " "), flag])
    out_all.append(line)
    if flag in ("TRUNCATED", "WRONG_VALUE", "FALSE_YES"): out_bad.append(line)
Path(sys.argv[1]).write_text(head + "\n" + "\n".join(out_all) + "\n", encoding="utf-8")
Path(sys.argv[2]).write_text(head + "\n" + "\n".join(out_bad) + ("\n" if out_bad else ""), encoding="utf-8")
print(len(out_all), len(out_bad))
