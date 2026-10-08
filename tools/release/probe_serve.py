"""新しい venv の `vera serve --no-llm` 起動と /v1/models を調べる。"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main(argv):
    vera, store, cwd, log_path, response_path, trace_dir, trace_file = argv[1:]
    port = _free_port()
    log = Path(log_path)
    response_file = Path(response_path)
    command = [vera, "--store", store, "serve", "--no-llm", "--port", str(port)]
    child_env = os.environ.copy()
    child_env["PYTHONPATH"] = trace_dir
    child_env["VERA_OPEN_TRACE_FILE"] = trace_file
    with log.open("w", encoding="utf-8") as output:
        proc = subprocess.Popen(
            command, cwd=cwd, stdout=output, stderr=subprocess.STDOUT,
            start_new_session=True, env=child_env,
        )
        response = None
        failure = None
        deadline = time.monotonic() + 20
        try:
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    failure = "serve process exited before endpoint answered"
                    break
                try:
                    with urlopen("http://127.0.0.1:{}/v1/models".format(port), timeout=1) as r:
                        body = json.loads(r.read().decode("utf-8"))
                        response = {"http_status": r.status, "body": body}
                    break
                except (OSError, URLError, UnicodeDecodeError, json.JSONDecodeError):
                    time.sleep(0.2)
            if response is None and failure is None:
                failure = "endpoint did not answer before timeout"
            if response is not None:
                models = response["body"].get("data") if isinstance(response["body"], dict) else None
                if not (
                    response["http_status"] == 200
                    and isinstance(models, list)
                    and models
                    and isinstance(models[0], dict)
                    and models[0].get("id") == "vera-no-llm"
                ):
                    failure = "unexpected /v1/models response shape"
            if response is not None:
                response_file.write_text(
                    json.dumps(response, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
        finally:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
            try:
                exit_code = proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                failure = failure or "serve process did not stop after SIGINT"
                proc.kill()
                exit_code = proc.wait(timeout=5)
    if exit_code != 0:
        failure = failure or "serve process exited with nonzero status"
    result = {
        "verdict": "PASS" if failure is None else "FAIL",
        "http_status": response.get("http_status") if response else None,
        "model_id": (
            response["body"]["data"][0].get("id")
            if response and isinstance(response["body"], dict)
            and response["body"].get("data") else None
        ),
        "process_exit_code": exit_code,
        "detail": failure,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if failure is None else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
