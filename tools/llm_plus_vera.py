"""PREREGISTERED_2026-09-27_llm_plus_vera.

    python3.11 tools/llm_plus_vera.py answer bonsai|luna
    python3.11 tools/llm_plus_vera.py sheet            # answers for judging, Vera not run
    python3.11 tools/llm_plus_vera.py vera judged.json # run Vera, score against judgments
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

B = Path.home() / "Projects" / "vera-corpus" / "benches"
import os
BENCH = B / os.environ.get("DOCQA_BENCH", "docqa_heldout_raw.json")
OUT = B / os.environ.get("DOCQA_OUT", "docqa_answers.json")

PROMPT = """次の文書だけを根拠に、各質問に日本語の1〜2文で答えてください。文書に書かれていないことは推測せず「文書には書かれていません」と答えてください。
出力は JSON だけ: {{"answers": ["…", "…", …]}}（質問と同じ順・同じ数）

# 文書: {title}
{text}

# 質問
{qs}"""


def ask_bonsai(prompt: str) -> list:
    body = {"model": "prism-ml/bonsai-27b", "temperature": 0,
            "messages": [{"role": "user", "content": prompt}], "max_tokens": 12000,
            "response_format": {"type": "json_schema", "json_schema": {"name": "a", "schema": {
                "type": "object", "properties": {"answers": {"type": "array", "items": {"type": "string"}}},
                "required": ["answers"]}}}}
    req = urllib.request.Request("http://localhost:1234/v1/chat/completions",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3000) as r:
        txt = json.loads(r.read())["choices"][0]["message"]["content"]
    return json.loads(txt[txt.find("{"): txt.rfind("}") + 1])["answers"]


def ask_luna(prompt: str) -> list:
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "s.json").write_text(json.dumps({"type": "object", "properties": {"answers": {
            "type": "array", "items": {"type": "string"}}}, "required": ["answers"], "additionalProperties": False}))
        (d / "e").mkdir()
        subprocess.run(["codex", "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only",
                        "--disable", "browser_use", "--disable", "computer_use", "--disable", "apps",
                        "-m", "gpt-6-luna", "-c", 'model_reasoning_effort="low"', "-C", str(d / "e"),
                        "--output-schema", str(d / "s.json"), "-o", str(d / "o.json"), prompt],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=900)
        return json.loads((d / "o.json").read_text())["answers"]


def answer(model: str) -> None:
    docs = json.loads(BENCH.read_text())["docs"]
    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    rows = []
    for i, d in enumerate(docs):
        qs = "\n".join("%d. %s" % (k + 1, q["question"]) for k, q in enumerate(d["qa"]))
        p = PROMPT.format(title=d["title"], text=d["text"], qs=qs)
        try:
            ans = ask_bonsai(p) if model == "bonsai" else ask_luna(p)
        except Exception as e:  # recorded, not hidden
            ans = ["(error: %s)" % str(e)[:80]] * len(d["qa"])
        for k, q in enumerate(d["qa"]):
            rows.append({"doc": i, "q": k, "question": q["question"], "gold": q["answer"],
                         "answer": ans[k] if k < len(ans) else "(missing)"})
        print(model, i, flush=True)
    out[model] = rows
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


RAG_PROMPT = """次の各質問に、その質問の「参考」の文だけを根拠に、日本語の1〜2文で答えてください。参考に書かれていないことは推測せず「参考には書かれていません」と答えてください。
出力は JSON だけ: {{"answers": ["…", …]}}（質問と同じ順・同じ数）

{blocks}"""


def _retrieve(question: str, sents: list, k: int = 5) -> list:
    """Top-k document sentences by overlap of content words — a plain retriever,
    the kind a RAG pipeline puts in front of an LLM."""
    from verantyx.typed_edges import _tagger
    def words(t):
        return {w.feature.lemma or w.surface for w in _tagger()(t)
                if w.feature.pos1 in ("名詞", "動詞", "形容詞") and len(w.surface) > 1}
    q = words(question)
    scored = sorted(((len(q & words(s)), i) for i, s in enumerate(sents)), key=lambda x: (-x[0], x[1]))
    return [sents[i] for _, i in scored[:k]]


def answer_rag(model: str) -> None:
    import re
    docs = json.loads(BENCH.read_text())["docs"]
    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    rows = []
    for i, d in enumerate(docs):
        sents = [x for x in re.split(r"(?<=。)", d["text"]) if x.strip()]
        blocks, refs = [], []
        for k, q in enumerate(d["qa"]):
            r = _retrieve(q["question"], sents)
            refs.append(r)
            blocks.append("## 質問%d: %s\n参考:\n%s" % (k + 1, q["question"], "\n".join("- " + x for x in r)))
        p = RAG_PROMPT.format(blocks="\n\n".join(blocks))
        try:
            ans = ask_bonsai(p) if model == "bonsai" else ask_luna(p)
        except Exception as e:
            ans = ["(error: %s)" % str(e)[:80]] * len(d["qa"])
        for k, q in enumerate(d["qa"]):
            rows.append({"doc": i, "q": k, "question": q["question"], "gold": q["answer"],
                         "answer": ans[k] if k < len(ans) else "(missing)", "refs": refs[k]})
        print(model, i, flush=True)
    out[model] = rows
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


def sheet() -> None:
    out = json.loads(OUT.read_text())
    for m, rows in out.items():
        print("=====", m)
        for r in rows:
            print("%s|%d.%d|Q:%s|G:%s|A:%s" % (m, r["doc"], r["q"], r["question"], r["gold"], r["answer"]))


def vera(judged_path: str) -> None:
    from verantyx.verify import compile_rows, verify
    docs = json.loads(BENCH.read_text())["docs"]
    judged = json.loads(Path(judged_path).read_text())  # {"bonsai": {"0.3": "wrong", ...}, ...}
    out = json.loads(OUT.read_text())
    rep = {}
    with tempfile.TemporaryDirectory() as tmp:
        stores = {}
        for i, d in enumerate(docs):
            st = Path(tmp) / ("d%d.db" % i)
            compile_rows([(d["title"], d["text"])], st)
            stores[i] = st
        detail = []
        for m, rows in out.items():
            t = {"correct": 0, "wrong": 0, "wrong_stopped": 0, "correct_stopped": 0}
            for r in rows:
                key = "%d.%d" % (r["doc"], r["q"])
                j = judged[m].get(key)
                if j not in ("right", "wrong"):
                    continue
                v = verify(stores[r["doc"]], r["answer"])
                stop = v["overall"] == "CONTRADICTED"
                if j == "wrong":
                    t["wrong"] += 1
                    t["wrong_stopped"] += stop
                else:
                    t["correct"] += 1
                    t["correct_stopped"] += stop
                detail.append({"model": m, "key": key, "judged": j, "stopped": stop,
                               "answer": r["answer"], "gold": r["gold"],
                               "why": [c.get("why") for s in v["sentences"] for c in s["claims"]
                                       if c["verdict"] == "CONTRADICTED"]})
            n = t["correct"] + t["wrong"]
            passed = n - t["wrong_stopped"] - t["correct_stopped"]
            rep[m] = {**t, "llm_error_rate": round(t["wrong"] / max(n, 1), 3),
                      "catch_rate": round(t["wrong_stopped"] / max(t["wrong"], 1), 3),
                      "false_alarm": round(t["correct_stopped"] / max(t["correct"], 1), 3),
                      "error_rate_reaching_user": round((t["wrong"] - t["wrong_stopped"]) / max(passed, 1), 3)}
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    (B / "docqa_vera_detail.json").write_text(json.dumps(detail, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    {"answer": lambda: answer(sys.argv[2]), "answer_rag": lambda: answer_rag(sys.argv[2]),
     "sheet": sheet, "vera": lambda: vera(sys.argv[2])}[sys.argv[1]]()
