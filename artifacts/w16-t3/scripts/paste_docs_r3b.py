"""第 3 ラウンドのレビュー（M1・M2・M3）への対応の docs/FUSION.md 更新（冪等）。数値は出力ファイルから機械で貼る。
  - §9.8 に「極性（否定）」と「選択の問い」の既知の穴を足す
  - §9.12 に測定（artifacts/w16-t3/r3b/）と、R6-2 の期待の前後を書く（§9.11 の事前登録は手書きで、ここでは触らない）
paste_docs_r3.py（§9.10 まで。§9.11 以降は残す）の後に流す。"""
import collections
import json
import sys

sys.path.insert(0, "/Users/motonisihikoudai/Projects/vera-impl/wt/W16-t3-S/artifacts/w16-t3/scripts")
from paste_docs_r3 import type_counts  # noqa: E402

CWD = "/Users/motonisihikoudai/Projects/vera-impl/wt/W16-t3-S"
ART = CWD + "/artifacts/w16-t3"
R3 = ART + "/r3"
RB = ART + "/r3b"
DOC = CWD + "/docs/FUSION.md"

HOLES_B = """
- **極性（否定）の取り違えは検出できない**（第 3 ラウンドのレビュー M3。裁定の内容語の定義の範囲外）。内容語の被覆は助動詞（ない・ません）を見ず、`非自立可能`（ある・なる・できる）も外すので、肯定と否定を取り違えても被覆される。例: 引用 `予備の在庫はない。` に答え `予備の在庫があります。`、引用 `駐車場は利用できる。` に答え `駐車場は利用できません。` はどちらも `anchored` になる（`artifacts/w16-t3/r3b/probe_polarity_choice.txt`）。T3-1 の見逃し 9 のうち W1 の 4 件（S1-ANS-05・S2-ANS-07・S3-ANS-05・S4-ANS-07）は 4 件とも否定の取り違え（答え「求める」・引用「…求めない。」など）。`非自立可能` の除外を外すと `する` で偽の錨なしが出る（レビューの反実仮想では T3-2 の S1-PARA1d で 3 行）ので外していない。直すかどうかは監査役の判断。
- **選択の問いでは、引用に無い方の選択肢を答えても `anchored` になる**（R3。問いの語の除外の帰結。第 3 ラウンドのレビュー M3）。問いに選択肢が並ぶと、その語は被覆の対象から外れる。再現: 問い `会場は大会議室と小会議室のどちらですか`、引用 `会場は小会議室である。`、答え `大会議室です。` → `anchored`（`probe_polarity_choice.txt`）。裁定の「問いの語の繰り返しは除く」の意図がどこまでかの確認が要る。"""


def read(p):
    return open(p, encoding="utf-8").read().rstrip("\n")


def main():
    doc = open(DOC, encoding="utf-8").read()
    if "極性（否定）の取り違えは検出できない" not in doc:
        a = doc.index("### 9.9 ")
        doc = doc[:a].rstrip("\n") + "\n" + HOLES_B + "\n\n" + doc[a:]
    if "### 9.12 " in doc:
        doc = doc[:doc.index("### 9.12 ")].rstrip("\n") + "\n"
    old = [json.loads(l) for l in open(R3 + "/cases.jsonl", encoding="utf-8") if l.strip()]
    new = [json.loads(l) for l in open(RB + "/cases_r3b.jsonl", encoding="utf-8") if l.strip()]
    r62o = next(c for c in old if c["id"] == "R6-2")
    r62n = next(c for c in new if c["id"] == "R6-2")
    dist = collections.Counter((c["type"], c["expect"]) for c in new)
    t31 = read(RB + "/t31_result.txt").split("\n\n候補ごとの印:")[0]
    parts = [
        "### 9.12 第 3 ラウンドのレビュー（M1・M2・M3）への対応の測定（`artifacts/w16-t3/r3b/`。出力ファイルから機械で貼った。`r3/` は上書きしていない）\n",
        "- 事前登録 §9.11（日時 `r3b/prereg_r3b_time.txt` = %s、`prereg_r3b.sha256`）→ 検査データ凍結 `cases_r3b.jsonl`（%d 件。型ごと: %s、`cases_r3b.sha256`、日時 `cases_r3b_time.txt` = %s）→ コードの修正、の順（時刻の順は prereg < cases < `quote_check.py` の更新）。" % (
            read(RB + "/prereg_r3b_time.txt"), len(new), type_counts(new), read(RB + "/cases_r3b_time.txt")),
        "- 型 × 期待: " + json.dumps({"%s/%s" % k: v for k, v in sorted(dist.items())}, ensure_ascii=False),
        "- 直す前（`content_before.txt`）の末尾: `" + read(RB + "/content_before.txt").splitlines()[-1] + "`（R6-2・N1-01・N1-02・N3-01 の 4 件が赤）。直した後（`content_after.txt`）: `" + read(RB + "/content_after.txt").splitlines()[-1] + "`。",
        "- **凍結した期待を後から変えたもの（1 件）: R6-2**。`cases.jsonl` は書き換えず、`cases_r3b.jsonl` で置き換えた。理由は §9.11 の R6′（候補 {a.txt, b.txt} と {c.txt} が交わらず、20日 と 30日 が違う）。\n",
        "旧（`r3/cases.jsonl` の R6-2 の全文）:\n\n```json\n" + json.dumps(r62o, ensure_ascii=False) + "\n```\n",
        "新（`r3b/cases_r3b.jsonl` の R6-2 の全文）:\n\n```json\n" + json.dumps(r62n, ensure_ascii=False) + "\n```\n",
        "#### T3-1（自作の集合）— `r3b/t31_result.txt`（`r3/` と byte 一致。M1・M2 の修正で印は 1 つも変わらない）\n",
        "```\n" + t31 + "\n```\n",
        "#### T3-2（実機は流し直さず、保存した raw を再照合）— `r3b/t32_recheck.txt`\n",
        "```\n" + read(RB + "/t32_recheck.txt") + "\n```\n",
        "#### T3-3（K653 の byte 一致）— `r3b/t33_k653.txt`\n",
        "```\n" + read(RB + "/t33_k653.txt") + "\n```\n",
    ]
    doc = doc.rstrip("\n") + "\n\n" + "\n".join(parts)
    open(DOC, "w", encoding="utf-8").write(doc)
    print("ok")


if __name__ == "__main__":
    main()
