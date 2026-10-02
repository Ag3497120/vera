"""HTTP server speaking the Ollama and OpenAI chat APIs, so apps written for them can use Vera.

    python -m vera_base.server --port 11435
    POST /api/chat, /api/generate            (Ollama)
    POST /v1/chat/completions, GET /v1/models (OpenAI)
Standard library only. The model name is "vera-base-ja"; there are no weights."""
from __future__ import annotations

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = "vera-base-ja"
_chat = None


DOCS = None


def chat():
    global _chat
    if _chat is None:
        if DOCS:
            from vera_base import Bot
            _chat = Bot.from_dir(DOCS)      # a bot for these documents
        else:
            from vera_base import Chat
            _chat = Chat([])
    return _chat


def reply(messages):
    user = [m for m in messages if m.get("role") == "user"]
    text = user[-1]["content"] if user else ""
    if isinstance(text, list):
        text = " ".join(p.get("text", "") for p in text if isinstance(p, dict))
    return chat().reply(text)["text"]


class H(BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path in ("/api/tags",):
            return self._send({"models": [{"name": MODEL, "model": MODEL, "size": 0, "details": {"family": "vera", "format": "rules"}}]})
        if self.path == "/v1/models":
            return self._send({"object": "list", "data": [{"id": MODEL, "object": "model", "owned_by": "vera"}]})
        self._send({"status": "ok", "model": MODEL})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        t = time.time()
        if self.path == "/api/chat":
            text = reply(body.get("messages", []))
            return self._send({"model": MODEL, "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                               "message": {"role": "assistant", "content": text}, "done": True,
                               "total_duration": int((time.time() - t) * 1e9)})
        if self.path == "/api/generate":
            text = reply([{"role": "user", "content": body.get("prompt", "")}])
            return self._send({"model": MODEL, "response": text, "done": True, "total_duration": int((time.time() - t) * 1e9)})
        if self.path == "/v1/chat/completions":
            text = reply(body.get("messages", []))
            return self._send({"id": "vera-%d" % int(t * 1000), "object": "chat.completion", "created": int(t), "model": MODEL,
                               "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                               "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}})
        self._send({"error": "unknown path"}, 404)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=11435)
    ap.add_argument("--docs", default=None, help="folder of .txt/.md documents: serve a bot for them")
    a = ap.parse_args()
    global DOCS
    DOCS = a.docs
    print("vera-base-ja on http://%s:%d (Ollama /api/chat, OpenAI /v1/chat/completions)" % (a.host, a.port))
    ThreadingHTTPServer((a.host, a.port), H).serve_forever()


if __name__ == "__main__":
    main()
