"""既知の穴（偽の錨なし・閉じない型）を、実際に流した出力から機械で出す（docs §10.11 に貼る）。使い方: cd <W> && holes_probe.py > artifacts/w16-t3b/holes_probe.txt
各行の正誤（correct = 支えられた正しい答え / wrong = 支えのない誤答）は **手で決めた**（コードを流して決めていない）。分類は出力から機械で: wrong で anchored = 閉じない型、correct で anchored 以外 = 偽の錨なし。
文は自分で書いた新しい文。H-01〜H-04 は凍結 cases_c.jsonl から読む。"""
import json
import os
import sys
import tempfile

from verantyx import decode_grammar as G
from verantyx import quote_check as QC

W = os.getcwd()
assert all(m.__file__.startswith(W + "/") for n, m in sys.modules.items() if n.startswith("verantyx") and getattr(m, "__file__", None))
CASES = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(W, "artifacts/w16-t3b/cases_c.jsonl"), encoding="utf-8") if l.strip()}
ROWS = []


def row(i, kind, truth, doc, question, answer, quotes):
    ROWS.append((i, kind, truth, {"doc.txt": doc}, question, answer, [("doc.txt", n, t) for n, t in quotes]))


for hid, kind in (("H-01", "R13 受け身（は／を の組が違う）"), ("H-02", "R13 対称な と の入れ替え"), ("H-03", "R13 に と へ は別の組"), ("H-04", "R14 て で終わる連なりは比べない（引用が過去）")):
    c = CASES[hid]
    ROWS.append((hid, kind, "correct", c["docs"], c["question"], c["answer"], [(q["source"], q["line"], q["text"]) for q in c["quotes"]]))
# 偽の錨なし（正しい答えが落ちる）。新しい文
row("N-01", "R13 目的語の主題化（は／を）", "correct", "課長が出張届を受理した。", "出張届はどうなりましたか", "出張届は課長が受理した。", [(1, "課長が出張届を受理した。")])
row("N-02", "R14 連用中止形（`拭き、`）は連なりが空なので非過去と数える", "correct", "窓を拭き、床を掃いた。", "窓はどうしましたか", "窓を拭いた。", [(1, "窓を拭き、床を掃いた。")])
row("N-03", "R14 丁寧形の時制違い（同じ見出し語で過去と非過去）", "correct", "新人を採用する。", "新人はどうなりますか", "新人を採用しました。", [(1, "新人を採用する。")])
# 閉じない型（誤答が anchored のまま）。新しい文
row("N-04", "R14 て で終わる連なり（引用が非過去）", "wrong", "扉を閉めて、施錠する。", "扉はどうしましたか", "扉を閉めた。", [(1, "扉を閉めて、施錠する。")])
row("N-05", "R14 名詞＋だ の述語は対象外", "wrong", "当番は山本だ。", "当番は誰でしたか", "当番は山本だった。", [(1, "当番は山本だ。")])
row("N-06", "名詞の連なりの切れ方が答えと引用で違う語（係長 は引用で 係＋長）は R13 でなく既存の 3b が先に落とす（reason が R13 でない。誤答は落ちる）", "wrong", "課長が係長に書類を渡した。", "書類はどうなりましたか", "係長が課長に書類を渡した。", [(1, "課長が係長に書類を渡した。")])
# R15 の改訂（問いの語の繰り返し）の周辺
row("N-07", "R15 正しい対照: 問いの語（受付）がどの引用にも無い。項目に入れないので 1 つの引用で支えられれば anchored", "correct", "窓口は午前9時に開く。", "受付は何時に開きますか", "受付は午前9時に開く。", [(1, "窓口は午前9時に開く。")])
row("N-08", "R15 問いの語の繰り返し・主語が引用 1、述語が引用 2（改訂で閉じた型の別の文）", "wrong", "売店は日曜に休む。\n食堂は祝日も営業する。", "売店はいつ営業しますか", "売店は祝日も営業する。", [(1, "売店は日曜に休む。"), (2, "食堂は祝日も営業する。")])
row("N-09", "R15 答えの主語が問いに無く、1 つの引用に主語と述語が揃わない（要素なし）", "wrong", "守衛は夜間に巡回する。\n受付は昼間に対応する。", "巡回は誰がしますか", "守衛は昼間に対応する。", [(1, "守衛は夜間に巡回する。"), (2, "受付は昼間に対応する。")])
print("%-5s %-8s %-11s %-30s  %s" % ("id", "正誤(手)", "印", "reason", "分類 / 種類"))
for i, kind, truth, docs, question, answer, quotes in ROWS:
    d = tempfile.mkdtemp()
    ps = []
    for name, body in docs.items():
        p = os.path.join(d, name)
        open(p, "w", encoding="utf-8").write(body + "\n")
        ps.append(p)
    r = QC.check(answer, [{"source": s, "line": n, "text": t} for s, n, t in quotes], G.load_records(ps), question=question).to_dict()
    v = r["verdict"]
    cls = ("閉じない型" if v == "anchored" else "ok") if truth == "wrong" else ("ok" if v == "anchored" else "偽の錨なし")
    print("%-5s %-8s %-11s %-30s  %s / %s" % (i, truth, v, r.get("reason") or "-", cls, kind))
    print("      Q: %s | A: %s | 引用: %s" % (question, answer, " / ".join(t for _, _, t in quotes)))
