"""docs/FUSION.md に貼る測定結果と応答の例を、artifacts のファイルから機械で作る（手で書き換えない）。出力: results_paste.md"""
import json, os
A = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rows(name): return [json.loads(l) for l in open(os.path.join(A, name), encoding="utf-8")]
def block(title, text, lang=""): return "\n#### %s\n\n```%s\n%s\n```\n" % (title, lang, text.rstrip("\n"))
out = ["## 4. 測定結果（`artifacts/w10-f01/score_layer0.txt`・`score_layer1.txt` を機械で貼ったもの）\n",
       "検査データの凍結: `data/FROZEN.json`・`freeze.txt`。LLM は `qwen3.8:27b-mlx`（Ollama）、配置は R8、入口は HTTP 経由（`scripts/run_eval.py`）。層 0 は `--max-tokens 200`（自由な答えの長さの上限。速度のため）、層 1 は文法が出力を縛る。\n"]
for n, label in ((0, "層 0（既定）"), (1, "層 1（`--strict`）")):
    out.append(block(label + " — `score_layer%d.txt`" % n, open(os.path.join(A, "score_layer%d.txt" % n), encoding="utf-8").read()))
out.append("\n### 4.1 `qwen3.5:4b`（第 2 ラウンドで追加。同じ検査データ・同じ入口・同じ採点。`score_q35_layer0.txt`・`score_q35_layer1.txt`）\n\n手元の Ollama に後から加わった設計書の推奨モデル（§1.9 (c)）。`qwen3.8:27b-mlx` との比較は、上の表と下の表の同じ行を並べて読む。数値は測った出力そのもの。\n")
for n, label in ((0, "層 0（既定）"), (1, "層 1（`--strict`）")):
    out.append(block("qwen3.5:4b " + label + " — `score_q35_layer%d.txt`" % n, open(os.path.join(A, "score_q35_layer%d.txt" % n), encoding="utf-8").read()))
r0, r1 = rows("eval_layer0.jsonl"), rows("eval_layer1.jsonl")
by0 = {r["id"]: r for r in r0}; by1 = {r["id"]: r for r in r1}
out.append("\n## 5. 応答の例（実際の応答。`eval_layer*.jsonl` から機械で選んで貼る。手で書き換えない）\n")
out.append("選び方: (a) Q001 の層 0・層 1 の応答の全体、(b) 層 0 で outcome が TESTIMONY の応答のうち JSON が最も短いもの、(c) 層 0 の CONSTRUCTED のうち JSON が最も短いもの。\n")
def dump(r): return json.dumps(r["response"], ensure_ascii=False, indent=1)
out.append(block("(a) Q001 `誰が地図を渡した？` — 層 0", dump(by0["Q001"]), "json"))
out.append(block("(a) Q001 `誰が地図を渡した？` — 層 1（`--strict`）", dump(by1["Q001"]), "json"))
t = min((r for r in r0 if r["response"]["vera"]["outcome"]["outcome"] == "TESTIMONY"), key=lambda r: len(dump(r)))
out.append(block("(b) %s `%s` — 層 0、証言" % (t["id"], t["request"]["messages"][0]["content"]), dump(t), "json"))
c = min((r for r in r0 if r["response"]["vera"]["outcome"]["outcome"] == "CONSTRUCTED"), key=lambda r: len(dump(r)))
out.append(block("(c) %s `%s` — 層 0、構成" % (c["id"], c["request"]["messages"][0]["content"]), dump(c), "json"))
open(os.path.join(A, "results_paste.md"), "w", encoding="utf-8").write("\n".join(out))
