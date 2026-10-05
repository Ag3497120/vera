"""系 A'・A・B・C・D の呼び出しの部品（Ollama・OpenAI 互換・`vera serve` の子プロセス）。"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

OLLAMA_URL = "http://127.0.0.1:11434"
FIRST_PORT = 18790


def http_json(url, body=None, timeout=300):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read())


def llm_call(backend, url, model, messages, timeout, max_tokens=256, api_key=None):
    """素の LLM（A'・A・B）。verantyx.llm_backend の関数を直接呼ぶ。-> {"ok","content","error","usage"}。"""
    from verantyx import llm_backend
    if backend == "ollama":
        return llm_backend._ollama_chat(url, model, messages, None, timeout=timeout, max_tokens=max_tokens)
    if backend == "openai":
        return llm_backend._openai_chat(url, api_key, model, messages, None, timeout=timeout, max_tokens=max_tokens)
    return {"ok": False, "content": None, "usage": {}, "error": {"type": "BAD_BACKEND", "detail": str(backend)}}


def port_busy(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def pick_port(start):
    p = start
    while port_busy(p):
        p += 1
    return p


def ollama_tags(url=OLLAMA_URL):
    try:
        return http_json(url + "/api/tags", timeout=10)[1]
    except Exception as exc:
        return {"error": "%s: %s" % (type(exc).__name__, exc)}


def ollama_ps(url=OLLAMA_URL):
    try:
        return http_json(url + "/api/ps", timeout=10)[1]
    except Exception as exc:
        return {"error": "%s: %s" % (type(exc).__name__, exc)}


def model_digest(url, model):
    for m in (ollama_tags(url).get("models") or []):
        if m.get("name") == model or m.get("model") == model:
            return m.get("digest")
    return "UNKNOWN_NOT_FOUND"


def uptime_line():
    try:
        return subprocess.run(["uptime"], capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception as exc:
        return "UNKNOWN: %s" % exc


def git_head(tree):
    try:
        return subprocess.run(["git", "-C", tree, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception as exc:
        return "UNKNOWN: %s" % exc


def vera_argv(python, store, model, port, placement, ollama_url, documents, strict):
    """`--store` は **サブコマンドの前**（後ろに置くと黙って捨てられる）。"""
    argv = [python, "-m", "verantyx.cli", "--store", store, "serve", "--backend", "ollama", "--model", model,
            "--port", str(port), "--placement", placement, "--ollama-url", ollama_url]
    for d in documents:
        argv += ["--document", d]
    if strict:
        argv.append("--strict")
    return argv


class VeraServer:
    """`vera serve --backend ollama` を子プロセスで起こす。cwd・PYTHONPATH = tree（外部の別物 verantyx を読まない）。"""

    def __init__(self, tree, argv, log_path, ready_timeout=120):
        self.tree, self.argv, self.log_path, self.ready_timeout = tree, argv, log_path, ready_timeout
        self.proc = None
        self.port = int(argv[argv.index("--port") + 1])

    def __enter__(self):
        env = dict(os.environ, PYTHONPATH=self.tree, PYTHONDONTWRITEBYTECODE="1")
        self.log = open(self.log_path, "w")
        self.proc = subprocess.Popen(self.argv, cwd=self.tree, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        base = "http://127.0.0.1:%d" % self.port
        t0 = time.time()
        while time.time() - t0 < self.ready_timeout:
            if self.proc.poll() is not None:
                raise RuntimeError("vera serve exited early (rc=%s); see %s" % (self.proc.returncode, self.log_path))
            try:
                http_json(base + "/v1/models", timeout=2)
                return self
            except Exception:
                time.sleep(0.5)
        raise RuntimeError("vera serve did not come up in %ss; see %s" % (self.ready_timeout, self.log_path))

    def __exit__(self, *exc):
        if self.proc is not None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        try:
            self.log.close()
        except Exception:
            pass
        return False

    def rss_kb(self):
        try:
            out = subprocess.run(["ps", "-o", "rss=", "-p", str(self.proc.pid)], capture_output=True, text=True, timeout=10).stdout.strip()
            return int(out)
        except Exception:
            return None

    def chat(self, body, timeout=600):
        return http_json("http://127.0.0.1:%d/v1/chat/completions" % self.port, body, timeout=timeout)
