"""W10-f01: 検査データを `vera serve --backend ollama` の HTTP 経由で 1 問ずつ流す（測るものと同じ経路）。データ固有の値は持たない。

  python run_eval.py --docs-dir DIR --questions Q.jsonl --port N --model M --placement P --out OUT.jsonl [--strict] [--tree TREE]

子プロセスは cwd=TREE・PYTHONPATH=TREE で起こす（外部の別物 verantyx が読まれる事故を避ける）。TREE の既定は現在の作業ディレクトリ。
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request


def http(url, body=None, timeout=300):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs-dir", required=True)
    ap.add_argument("--questions", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--placement", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--tree", default=os.getcwd())
    ap.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    ap.add_argument("--max-tokens", type=int, default=None, help="OpenAI max_tokens sent with each request (layer 0 free answers only; a grammar bounds its own output)")
    a = ap.parse_args()
    docs = sorted(glob.glob(os.path.join(a.docs_dir, "*.txt")))
    if not docs:
        sys.exit("no .txt in " + a.docs_dir)
    scratch = tempfile.mkdtemp(prefix="w10f01-eval-")
    argv = [sys.executable, "-m", "verantyx.cli", "--store", os.path.join(scratch, "store.json"), "serve", "--backend", "ollama", "--model", a.model,
            "--port", str(a.port), "--placement", a.placement, "--ollama-url", a.ollama_url]
    for d in docs:
        argv += ["--document", d]
    if a.strict:
        argv.append("--strict")
    env = dict(os.environ, PYTHONPATH=a.tree, PYTHONDONTWRITEBYTECODE="1")
    child = subprocess.Popen(argv, cwd=a.tree, env=env, stdout=open(os.path.join(scratch, "server.log"), "w"), stderr=subprocess.STDOUT)
    base = "http://127.0.0.1:%d" % a.port
    try:
        for _ in range(120):
            try:
                http(base + "/v1/models", timeout=2)
                break
            except Exception:
                if child.poll() is not None:
                    sys.exit("server exited early; see %s" % os.path.join(scratch, "server.log"))
                time.sleep(0.5)
        else:
            sys.exit("server did not come up")
        questions = [json.loads(l) for l in open(a.questions, encoding="utf-8") if l.strip()]
        with open(a.out, "w", encoding="utf-8") as out:
            for q in questions:
                req = {"model": a.model, "messages": [{"role": "user", "content": q["question"]}],
                       "vera": {"request_kind": q.get("request_kind", "factual"), "human_present": bool(q.get("human_present", False))}}
                if a.max_tokens is not None:
                    req["max_tokens"] = a.max_tokens
                t = time.perf_counter()
                try:
                    status, resp = http(base + "/v1/chat/completions", req)
                except Exception as exc:
                    status, resp = None, {"error": "%s: %s" % (type(exc).__name__, exc)}
                out.write(json.dumps({"id": q["id"], "request": req, "http_status": status, "wall_ms": round((time.perf_counter() - t) * 1000, 1), "response": resp},
                                     ensure_ascii=False) + "\n")
                out.flush()
                print(q["id"], status, (resp.get("vera") or {}).get("outcome", {}).get("outcome"), flush=True)
    finally:
        child.terminate()
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
    print("server log:", os.path.join(scratch, "server.log"))


if __name__ == "__main__":
    main()
