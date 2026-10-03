"""Writes tests/coarse_place/data/w3a4_r7_answer_sha.tsv from p1/r7_before.tsv (answers of the BASE code on r7/run1):
the 12 words the cover rule would change, the 13 NOT_CONFIRMED words of W5-d and the 48 direct generated-frame words.
usage: make_r7_answer_sha.py <tree>"""
import json, sys
import verantyx.coarse_place as cp
tree = sys.argv[1]
assert cp.__file__.startswith(tree + "/")
R7 = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1"
A = tree + "/artifacts/w3-a4/"
TWELVE = "向かえる 嫁ぐ 昇る 流れ込む 潜る 移す 行ける 送り返す 逃げ込む 通う 飛び込む よぶ".split()
NOTCONF = "うたう たたえる みせる 交わす 命じる 問い合わせる 潜める 示せる 薦める 見せ合う 言い換える 訴える 謳う".split()
before = {}
for l in open(A + "p1/r7_before.tsv", encoding="utf-8"):
    w, h, fs = l.rstrip("\n").split("\t")
    before[w] = (h, fs)
import sqlite3
con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % R7, uri=True)
gfw = sorted(r[0] for r in con.execute("select distinct word from evidence where arm='gen_frame'"))
direct48 = [w for w in gfw if cp.query(w, placement=R7)["origin"] == "direct"]
print("direct generated-frame words:", len(direct48))
rows = []
for kind, ws in (("twelve", TWELVE), ("not_confirmed", NOTCONF), ("direct", direct48)):
    for w in ws:
        h, fs = before[w]
        rows.append((kind, w, h, fs))
with open(tree + "/tests/coarse_place/data/w3a4_r7_answer_sha.tsv", "w", encoding="utf-8") as f:
    for r in rows:
        f.write("\t".join(r) + "\n")
print(len(rows))
