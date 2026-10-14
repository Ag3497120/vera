"""H3: `vera run` -- the local web UI.  The server is bound to an ephemeral port in this process; the model is a fake client.  Checks the exposure rules (loopback only, token, Host / Origin /
Content-Type, no CORS, CSP, no external loads) and the endpoints end to end (documents, memory, trace, ledger, Verify, settings)."""
import http.client
import json
import os
import re
import threading

import pytest

from fakes import ASK_TURNS, DOCS, QUESTION, FakeOpenAI
from test_runner import ANSWER_FIRST, STORY_ONE
from verantyx.harness import cli
from verantyx.harness import keys
from verantyx.harness import server as sv
from verantyx.harness.backends import make_backend

CLEAN = [[b for b in t if b[0] != "text"] for t in ASK_TURNS]
SECRET = "sk-test-SECRET-value-123456"


@pytest.fixture()
def docs(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    for k, v in DOCS.items():
        (d / k).write_text(v, encoding="utf-8")
    return str(d)


@pytest.fixture()
def web(tmp_path, monkeypatch, docs):
    """(call, app): a running server on 127.0.0.1:<ephemeral>; `fake(script)` makes the next backend a FakeOpenAI with that script."""
    app = sv.App({"backend": "openai", "model": "m", "docs": docs, "store": str(tmp_path / "store"), "runs_dir": str(tmp_path / "runs")})
    server = sv.make_server("127.0.0.1", 0, app)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    port = server.server_address[1]
    box = {"script": CLEAN}
    monkeypatch.setattr(sv, "backend_factory", lambda kind, model, base_url, **kw: make_backend("openai", model or "m", base_url, client=FakeOpenAI(box["script"])))
    monkeypatch.setattr(keys, "key_source", lambda provider, env=None: "environment" if provider == "anthropic" else None)

    def call(method, path, body=None, headers=None, token=True, host=None, ctype="application/json"):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
        h = {"Host": host or "127.0.0.1:%d" % port}
        if token:
            h["X-Vera-Token"] = app.token
        if body is not None:
            h["Content-Type"] = ctype
        h.update(headers or {})
        c.request(method, path, body=None if body is None else json.dumps(body), headers=h)
        r = c.getresponse()
        raw = r.read()
        c.close()
        try:
            return r.status, dict(r.getheaders()), json.loads(raw.decode("utf-8")) if raw and r.getheader("Content-Type", "").startswith("application/json") else raw
        except ValueError:
            return r.status, dict(r.getheaders()), raw

    call.set = lambda script: box.__setitem__("script", script)
    call.port = port
    yield call, app
    server.shutdown()
    server.server_close()


# -- the address -------------------------------------------------------------------------------------------------------------------
def test_only_loopback_addresses_are_bound_and_there_is_no_remote_mode():
    for h in ("127.0.0.1", "localhost", "::1", "127.0.0.5", "::ffff:127.0.0.1"):
        assert sv.check_bind(h)
    for h in ("0.0.0.0", "", "192.168.1.5", "example.com", "::", "::ffff:10.0.0.1", "LOCALHOST", "127.0.0.1 "):
        with pytest.raises(sv.ServerError) as e:
            sv.check_bind(h)
        assert e.value.code == "bind_refused"
        with pytest.raises(sv.ServerError):
            sv.check_bind(h, allow_remote=True)                                                          # the flag does not open anything
    with pytest.raises(sv.ServerError) as e:
        sv.make_server("127.0.0.1", 0, sv.App({}), allow_remote=True)
    assert e.value.code == "bind_refused"


def test_the_command_refuses_a_foreign_address(capsys):
    assert cli.main(["run", "--host", "0.0.0.0", "--port", "0"]) == 2
    assert "refusing to bind" in capsys.readouterr().err
    assert cli.main(["run", "--allow-remote", "--port", "0"]) == 2
    assert "not available" in capsys.readouterr().err


# -- the page ----------------------------------------------------------------------------------------------------------------------
def test_the_page_has_the_token_a_strict_csp_and_loads_nothing_from_outside(web):
    call, app = web
    st, h, body = call("GET", "/", token=False)
    page = body.decode("utf-8")
    assert st == 200 and h["Content-Type"].startswith("text/html") and app.token in page and "__VERA_TOKEN__" not in page
    csp = h["Content-Security-Policy"]
    assert re.search(r"script-src 'sha256-[A-Za-z0-9+/=]+'", csp) and re.search(r"style-src 'sha256-[A-Za-z0-9+/=]+'", csp) and "unsafe" not in csp and "default-src 'none'" in csp and "connect-src 'self'" in csp
    assert not [k for k in h if k.lower().startswith("access-control")] and h["X-Content-Type-Options"] == "nosniff" and h["Cache-Control"] == "no-store"
    assert not re.search(r"https?://|//cdn|<link|<img|<iframe|@import|url\(", page), "the page must not load anything"
    assert page.count("<script>") == 1 and page.count("<style>") == 1 and "src=" not in page.replace("srcElement", "")
    import base64, hashlib
    script = re.findall(r"<script>(.*?)</script>", page, re.S)[0]
    assert "sha256-" + base64.b64encode(hashlib.sha256(script.encode()).digest()).decode() in csp


# -- the exposure rules ------------------------------------------------------------------------------------------------------------
def test_every_api_call_needs_the_token_and_the_right_host(web):
    call, app = web
    assert call("GET", "/api/state", token=False)[0] == 403
    assert call("GET", "/api/state", headers={"X-Vera-Token": "wrong"})[0] == 403
    assert call("GET", "/api/state", host="evil.example:%d" % call.port)[0] == 421                   # DNS rebinding
    assert call("GET", "/api/state", host="evil.example")[0] == 421
    st, h, body = call("GET", "/api/state")
    assert st == 200 and body["version"] and not [k for k in h if k.lower().startswith("access-control")]


def test_a_cross_origin_post_a_form_post_and_a_preflight_are_refused(web):
    call, app = web
    assert call("POST", "/api/config", {"model": "x"}, headers={"Origin": "http://evil.example"})[0] == 403
    assert call("POST", "/api/config", {"model": "x"}, headers={"Origin": "http://127.0.0.1:%d" % call.port})[0] == 200
    assert call("POST", "/api/config", {"model": "x"}, ctype="application/x-www-form-urlencoded")[0] == 415
    assert call("POST", "/api/config", {"model": "x"}, ctype="text/plain")[0] == 415
    st, h, _ = call("OPTIONS", "/api/ask", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"})
    assert st == 405 and not [k for k in h if k.lower().startswith("access-control")]
    assert call("PUT", "/api/config", {})[0] == 405 and call("DELETE", "/api/config")[0] == 405
    assert call("GET", "/etc/passwd")[0] == 404 and call("GET", "/webui/index.html")[0] == 404


def test_a_key_value_never_appears_only_whether_one_is_present(web, monkeypatch):
    call, app = web
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    st, _, body = call("GET", "/api/state")
    text = json.dumps(body, ensure_ascii=False)
    assert st == 200 and SECRET not in text and body["keys"]["anthropic"] == {"present": True, "source": "environment", "env": ["ANTHROPIC_API_KEY"], "keychain": "vera-harness / anthropic"}
    assert body["keys"]["openai"]["present"] is False
    keys._remember(SECRET)
    st, _, body = call("POST", "/api/config", {"api_key_env": SECRET})                                  # the variable NAME is a command-line setting: nothing typed here is accepted
    assert st == 403 and SECRET not in json.dumps(body) and body["code"] == "locked_setting"
    assert call("POST", "/api/config", {"api_key": SECRET})[0] == 400                                   # there is no setting that takes a key


def test_settings_are_validated_and_the_dangerous_ones_are_command_line_only(web):
    call, app = web
    for k, v in (("backend", "json"), ("base_url", "https://attacker.example/v1"), ("api_key_env", "HOME"), ("docs", "/etc"), ("store", "/tmp/x"), ("runs_dir", "/tmp/y")):      # the exfiltration probe (H8 p3)
        st, _, body = call("POST", "/api/config", {k: v})
        assert st == 403 and body["code"] == "locked_setting", k
    assert app.config["docs"] != "/etc" and app.config["base_url"] is None and app.config["api_key_env"] is None
    assert call("POST", "/api/config", {"backend": "anthropic"})[0] == 403 and app.config["backend"] == "openai"      # a provider switch would send one provider's key to another's base URL (H8 p6)
    assert call("POST", "/api/config", {"evidence": "v9"})[0] == 400
    assert call("POST", "/api/config", {"gate_filters": ["evidence.v6"]})[0] == 400                      # a loom gate is not a filter
    st, _, body = call("POST", "/api/config", {"temperature": 0.2, "evidence": "v2"})
    assert st == 200 and body["config"]["evidence"] == "v2"
    assert "locked" in call("GET", "/api/state")[2] and "base_url" in call("GET", "/api/state")[2]["locked"]


def test_every_loopback_spelling_of_the_host_header_is_accepted_and_nothing_else(web):
    call, app = web
    for h in ("127.0.0.1", "localhost", "127.0.0.2", "[::1]", "[::ffff:127.0.0.1]"):
        assert call("GET", "/api/state", host="%s:%d" % (h, call.port))[0] == 200, h
    for h in ("evil.example:%d", "127.0.0.1.evil.example:%d", "10.0.0.1:%d", "[::ffff:10.0.0.1]:%d", "127.0.0.1:1%d"):
        assert call("GET", "/api/state", host=h % call.port)[0] == 421, h


def test_a_run_key_cannot_leave_the_runs_and_the_store(web, tmp_path):
    call, app = web
    for k in ("runs:../../..", "runs:../store", "store:../runs", "runs:/etc", "etc:passwd", "nonsense", ""):
        assert call("GET", "/api/ledger?run=" + k.replace("/", "%2F"))[0] in (400, 404), k


# -- documents: ask, trace, ledger, verify ---------------------------------------------------------------------------------------
def test_ask_shows_a_quote_with_its_source_and_nothing_else_of_the_model(web):
    call, app = web
    st, _, body = call("POST", "/api/ask", {"mode": "docs", "question": QUESTION})
    a = body["turn"]["answer"]
    assert st == 200 and a["status"] == "answered" and a["text"] == "松風庵" and a["sources"] == [{"text": "青葉堂の旧称は松風庵。", "source": "青葉堂#1"}] and a["verified"] is True
    assert set(a) == {"status", "text", "sources", "reason", "reason_ja", "verified", "free_text_dropped", "backend", "usage", "detail", "run"}
    assert a["run"].startswith("runs:ask-")
    # the trace and the ledger of the run
    st, _, tr = call("GET", "/api/trace?run=" + a["run"].replace(":", "%3A"))
    ops = [r["op"] for r in tr["rows"]]
    assert st == 200 and ops == ["begin", "harness_meta", "lookup", "read_sentence", "weave_span", "emit", "harness_meta"]
    emit = [r for r in tr["rows"] if r["op"] == "emit"][0]
    assert emit["what"] == "「松風庵」" and all(r["sha"] and r["prev"] for r in tr["rows"])
    assert all(tr["rows"][k]["prev"] == tr["rows"][k - 1]["sha"] for k in range(1, len(tr["rows"])))
    st, _, v = call("POST", "/api/verify", {"run": a["run"]})
    assert st == 200 and v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL"
    # tamper with the ledger: Verify says so
    p = os.path.join(app.resolve_run(a["run"]), "ops.jsonl")
    t = open(p, encoding="utf-8").read().replace("松風庵", "松風菴", 1)
    open(p, "w", encoding="utf-8").write(t)
    assert call("POST", "/api/verify", {"run": a["run"]})[2]["status"] == "TAMPERED"
    st, _, runs = call("GET", "/api/runs")
    assert runs["runs"][0]["run"] == a["run"] and runs["runs"][0]["backend"] == "openai"


def test_a_refusal_is_the_words_and_the_typed_reason(web):
    call, app = web
    call.set([[("tool", "abstain", {"type": "no_record"})]])
    st, _, body = call("POST", "/api/ask", {"mode": "docs", "question": QUESTION})
    a = body["turn"]["answer"]
    assert st == 200 and a["status"] == "refused" and a["reason"] == "no_record" and "書かれていません" in a["reason_ja"] and a["text"] is None and a["sources"] == []


def test_the_models_prose_is_dropped_and_counted_not_shown(web):
    call, app = web
    call.set(ASK_TURNS)                                                                                  # the script includes "text" blocks (prose) before the tool calls
    st, _, body = call("POST", "/api/ask", {"mode": "docs", "question": QUESTION})
    a = body["turn"]["answer"]
    assert a["status"] == "answered" and a["free_text_dropped"] == 2 and "考えます" not in json.dumps(body, ensure_ascii=False)


def test_only_one_run_at_a_time_and_bad_input_is_a_typed_error(web):
    call, app = web
    assert call("POST", "/api/ask", {"mode": "docs", "question": ""})[0] == 400
    assert call("POST", "/api/ask", {"mode": "docs", "question": "あ" * 300})[0] == 400
    assert call("POST", "/api/ask", {"mode": "elsewhere", "question": "x"})[0] == 400
    assert call("POST", "/api/say", {"messages": []})[0] == 400
    app.run_lock.acquire()
    try:
        st, _, body = call("POST", "/api/ask", {"mode": "docs", "question": QUESTION})
        assert st == 409 and body["code"] == "busy"
    finally:
        app.run_lock.release()
    app.config["docs"] = None
    assert call("POST", "/api/ask", {"mode": "docs", "question": QUESTION})[2]["code"] == "no_docs"


# -- memory ------------------------------------------------------------------------------------------------------------------------
def test_memory_say_ask_notes_and_the_position_of_the_question(web):
    call, app = web
    call.set(STORY_ONE)
    st, _, body = call("POST", "/api/say", {"messages": ["広報の担当は山本"]})
    assert st == 200 and body["turn"]["committed"] is True and body["turn"]["session"] == 1
    call.set(ANSWER_FIRST)
    st, _, body = call("POST", "/api/ask", {"mode": "memory", "question": "広報の担当は何ですか"})
    a = body["turn"]["answer"]
    assert st == 200 and a["status"] == "answered" and a["text"] == "山本" and a["sources"][0]["text"] == "広報の担当は山本" and a["run"].startswith("store:answers/")
    st, _, m = call("GET", "/api/memory")
    assert m["present"] is True and m["n_sentences"] == 1 and m["sentences"][0]["text"] == "広報の担当は山本" and set(m["counts"]) == {"SAME_SEAT", "UPDATE", "REVERSAL_X", "ENUMERATION"}
    st, _, pos = call("GET", "/api/position?run=" + a["run"].replace(":", "%3A"))
    assert st == 200 and pos["positions"] and "広報" in (pos["positions"][0]["text"] or "") and pos["positions"][0]["cross"] and pos["positions"][0]["history"][0]["value"] == "山本"
    assert call("POST", "/api/verify", {"run": a["run"]})[2]["status"] == "OK"
    assert call("POST", "/api/verify", {"run": "store:"})[2]["kind"] == "mem_store"


def test_two_told_answers_show_up_as_a_same_seat_note(web):
    call, app = web
    call.set([[("tool", "write", {"text": "広報の担当は山本"}), ("tool", "report", {"contradictions": []})],
              [("tool", "write", {"text": "広報の担当は田中"}), ("tool", "report", {"contradictions": [["1-1", "1-2"]]})]])
    assert call("POST", "/api/say", {"messages": ["広報の担当は山本", "広報の担当は田中"]})[0] == 200
    m = call("GET", "/api/memory")[2]
    seat = [n for n in m["notes"] if n["type"] == "SAME_SEAT"]
    assert seat and seat[0]["text"] == "広報の担当は田中" and seat[0]["earlier"][0]["text"] == "広報の担当は山本"
