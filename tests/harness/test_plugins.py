"""H4: the plugin registry (entry point group `vera.plugins`), the plugins a ledger records, and `verify` saying INPUTS for a plugin that is not there.  Fake clients, fake entry points."""
import json
import os

import pytest

from fakes import ASK_TURNS, DOCS, QUESTION, FakeOpenAI
from test_runner import ANSWER_FIRST, STORY_ONE
from verantyx.harness import cli
from verantyx.harness import plugins as pl
from verantyx.harness import runner as rn
from verantyx.harness.backends import BackendError, make_backend

CLEAN = [[b for b in t if b[0] != "text"] for t in ASK_TURNS]


class EP:
    """A fake entry point."""

    def __init__(self, name, provider, value="fake.module:provider"):
        self.name, self.value, self._p = name, value, provider

    def load(self):
        if isinstance(self._p, Exception):
            raise self._p
        return self._p


def refuse_numbers(question, answer, sources):
    return "has_digit" if any(c.isdigit() for c in answer) else None


def refuse_all(question, answer, sources):
    return "never"


def boom(question, answer, sources):
    raise RuntimeError("oops")


def mine(version="1.0"):
    return [pl.Plugin("gate", "refuse-all", version, refuse_all, "refuses everything"),
            pl.Plugin("gate", "no-digits", version, refuse_numbers),
            pl.Plugin("gate", "boom", version, boom),
            pl.Plugin("note_kind", "mentions-yamamoto", version, pl.NoteKind(lambda rows: [{"sid": i, "text": "山本が出ます"} for i, r in enumerate(rows) if "山本" in r.get("sent", "")])),
            pl.Plugin("backend", "fakegpt", version, lambda model, base_url=None, **kw: make_backend("openai", model, base_url, client=FakeOpenAI(CLEAN)), "a test backend")]


@pytest.fixture()
def reg():
    """A registry with the built-ins and the plugins above installed; restored afterwards."""
    r = pl.discover([EP("mine", lambda: mine())])
    pl.set_registry(r)
    yield r
    pl.set_registry(None)


@pytest.fixture()
def docs(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    for k, v in DOCS.items():
        (d / k).write_text(v, encoding="utf-8")
    return str(d)


def oa(script):
    return make_backend("openai", "fake-gpt", client=FakeOpenAI(script))


# -- the registry -----------------------------------------------------------------------------------------------------------------
def test_the_builtins_are_registered_the_same_way_with_or_without_installed_metadata(reg):
    for r in (pl.discover([]), pl.discover([EP("vera-builtin", __import__("verantyx.harness.builtin_plugins", fromlist=["x"]).plugins, "verantyx.harness.builtin_plugins:plugins")])):
        assert r.names("backend") == ["anthropic", "json", "openai"]
        assert r.names("gate") == ["evidence.v%d" % n for n in range(1, 7)]
        assert r.names("memory_profile") == ["m6c-v17", "m6d-v17"]
        assert r.names("note_kind") == ["enumeration", "reversal_x", "same_seat", "update"]
        assert all(p.builtin for p in r.all()) and not r.errors
        assert r.get("memory_profile", "m6d-v17").obj.answer_version == rn.MEM_ANSWER_VERSION and r.get("memory_profile", "m6d-v17").obj.versions == dict(rn.MEM_BUNDLE)


def test_a_plugin_is_one_more_entry_point_and_cannot_shadow_a_builtin(reg):
    assert reg.get("gate", "no-digits").version == "1.0" and not reg.get("gate", "no-digits").builtin
    r = pl.discover([EP("evil", lambda: [pl.Plugin("gate", "evidence.v6", "9", refuse_all)]), EP("bad", lambda: [pl.Plugin("gate", "Bad Name", "1", refuse_all)]),
                     EP("broken", ImportError("no module named x")), EP("notplugins", lambda: [42]), EP("good", lambda: [pl.Plugin("gate", "ok-one", "1", refuse_all)])])
    assert r.get("gate", "evidence.v6").version == "1" and r.get("gate", "ok-one") is not None            # the built-in stays, the good one loads
    assert len(r.errors) == 4 and {e["origin"].split("=")[0] for e in r.errors} == {"evil", "bad", "broken", "notplugins"}
    with pytest.raises(pl.PluginError) as e:
        r.require("gate", "nope")
    assert e.value.code == "unknown_plugin"


def test_the_manifest_is_canonical_and_the_mismatch_tokens_are_typed(reg):
    used = [reg.get("gate", "no-digits"), reg.get("backend", "openai"), reg.get("gate", "no-digits")]
    m = pl.manifest(used)
    assert json.loads(m) == [{"kind": "backend", "name": "openai", "version": "0.1.0"}, {"kind": "gate", "name": "no-digits", "version": "1.0"}]
    assert pl.mismatch(pl.parse_manifest(m), reg) is None and pl.mismatch(None, reg) is None
    assert pl.mismatch([{"kind": "gate", "name": "zzz", "version": "1"}], reg) == "unknown_plugin:gate/zzz"
    assert pl.mismatch([{"kind": "gate", "name": "no-digits", "version": "0.9"}], reg) == "plugin_version:gate/no-digits:0.9!=1.0"
    assert pl.parse_manifest("not json") is None and pl.parse_manifest('[{"kind": 1}]') is None


# -- a gate filter: refuse only ---------------------------------------------------------------------------------------------------
def test_a_gate_filter_can_only_refuse_and_the_ledger_records_it(reg, docs, tmp_path):
    a = rn.ask(QUESTION, docs, oa(CLEAN), str(tmp_path / "r1"), gate_filters=["no-digits"])
    assert a.status == "answered" and a.text == "松風庵"                                    # no digit in the quote: the filter passes it
    meta = [json.loads(ln) for ln in open(os.path.join(a.run_dir, "ops.jsonl"), encoding="utf-8")][1]
    declared = json.loads(meta["args"]["plugins"])
    assert {"kind": "gate", "name": "no-digits", "version": "1.0"} in declared and {"kind": "gate", "name": "evidence.v6", "version": "1"} in declared
    assert {"kind": "backend", "name": "openai", "version": "0.1.0"} in declared
    assert rn.verify_path(a.run_dir)["status"] == "OK" and rn.replay_path(a.run_dir)["status"] == "IDENTICAL"

    b = rn.ask(QUESTION, docs, oa(CLEAN), str(tmp_path / "r2"), gate_filters=["refuse-all"])
    assert b.status == "refused" and b.reason == "plugin_refused" and b.text is None and b.sources == []
    assert b.detail["plugin"] == {"kind": "gate", "name": "refuse-all", "version": "1.0", "code": "never"}
    assert "プラグイン: gate/refuse-all 1.0（never）" in b.render() and "プラグインのゲート" in b.render()
    assert rn.verify_path(b.run_dir)["status"] == "OK"                                       # the run itself is sound; the filter only withheld the answer

    c = rn.ask(QUESTION, docs, oa(CLEAN), str(tmp_path / "r3"), gate_filters=["boom"])
    assert c.reason == "plugin_refused" and c.detail["plugin"]["code"] == "filter_error:RuntimeError"      # a failing filter fails closed


def test_a_loom_gate_is_chosen_with_evidence_not_as_a_filter(reg, docs, tmp_path):
    with pytest.raises(rn.HarnessError) as e:
        rn.ask(QUESTION, docs, oa(CLEAN), str(tmp_path / "r"), gate_filters=["evidence.v2"])
    assert e.value.code == "bad_plugin"
    with pytest.raises(rn.HarnessError) as e:
        rn.ask(QUESTION, docs, oa(CLEAN), str(tmp_path / "r"), gate_filters=["nope"])
    assert e.value.code == "unknown_plugin"


# -- verify says INPUTS ----------------------------------------------------------------------------------------------------------
def test_verify_and_replay_say_INPUTS_when_a_declared_plugin_is_gone_or_changed(reg, docs, tmp_path, capsys):
    a = rn.ask(QUESTION, docs, oa(CLEAN), str(tmp_path / "runs"), gate_filters=["no-digits"])
    assert rn.verify_path(a.run_dir)["status"] == "OK"
    pl.set_registry(pl.discover([]))                                                           # the plugin is not installed any more
    v = rn.verify_path(a.run_dir)
    assert v["status"] == "REPLAY_INPUTS_MISMATCH" and v["replay"] == {"status": "INPUTS", "mismatch": "unknown_plugin:gate/no-digits"}
    r = rn.replay_path(a.run_dir)
    assert r["status"] == "INPUTS" and r["identical"] is False and r["mismatch"] == "unknown_plugin:gate/no-digits"
    assert cli.main(["verify", a.run_dir]) == 1 and "unknown_plugin:gate/no-digits" in capsys.readouterr().err
    assert cli.main(["replay", a.run_dir]) == 2                                                # INPUTS is exit 2, like a missing corpus
    pl.set_registry(pl.discover([EP("mine", lambda: mine("2.0"))]))                            # installed, but another version
    assert rn.verify_path(a.run_dir)["replay"]["mismatch"] == "plugin_version:gate/no-digits:1.0!=2.0"
    pl.set_registry(reg)
    assert rn.verify_path(a.run_dir)["status"] == "OK"


def test_a_tampered_ledger_is_tampered_before_it_is_anything_else(reg, docs, tmp_path):
    a = rn.ask(QUESTION, docs, oa(CLEAN), str(tmp_path / "runs"), gate_filters=["no-digits"])
    p = os.path.join(a.run_dir, "ops.jsonl")
    t = open(p, encoding="utf-8").read().replace("no-digits", "no-digitz", 1)
    open(p, "w", encoding="utf-8").write(t)
    pl.set_registry(pl.discover([]))
    assert rn.verify_path(a.run_dir)["status"] == "TAMPERED"


def test_a_run_that_declares_no_plugins_has_no_mismatch(reg, docs, tmp_path):
    a = rn.ask(QUESTION, docs, oa(CLEAN), str(tmp_path / "runs"))
    p = os.path.join(a.run_dir, "ops.jsonl")
    assert rn.plugin_mismatch(a.run_dir) is None
    pl.set_registry(pl.discover([]))
    assert rn.verify_path(a.run_dir)["status"] == "OK"                                         # the built-ins are always there


# -- memory: profile, note kinds, the answer run's declaration --------------------------------------------------------------------
def test_memory_profile_note_kind_and_filter_are_recorded_and_checked(reg, tmp_path):
    store = str(tmp_path / "store")
    r = rn.mem_say(store, ["広報の担当は山本です"], oa(STORY_ONE), profile="m6c-v17")
    assert r.committed
    a = rn.mem_ask(store, "広報の担当は何ですか", oa(ANSWER_FIRST), profile="m6c-v17", note_kinds=["mentions-yamamoto"], gate_filters=["no-digits"])
    assert a.status == "answered" and a.text == "山本" and a.detail["annotations"] == [{"kind": "mentions-yamamoto", "version": "1.0", "sid": 0, "text": "山本が出ます"}]
    rows = [json.loads(ln) for ln in open(os.path.join(a.run_dir, "ops.jsonl"), encoding="utf-8")]
    declared = [json.loads(x["args"]["plugins"]) for x in rows if x["op"] == "harness_meta"][0]
    assert {"kind": "memory_profile", "name": "m6c-v17", "version": "1"} in declared and {"kind": "note_kind", "name": "mentions-yamamoto", "version": "1.0"} in declared
    assert rn.verify_path(store)["status"] == "OK" and rn.verify_path(a.run_dir)["status"] == "OK"
    pl.set_registry(pl.discover([]))
    assert rn.verify_path(a.run_dir)["replay"]["mismatch"].startswith("unknown_plugin:")
    assert rn.verify_path(store)["status"] == "REPLAY_INPUTS_MISMATCH"                          # the store verifies its answers too


def test_the_default_memory_run_declares_the_builtin_profile(reg, tmp_path):
    store = str(tmp_path / "store")
    rn.mem_say(store, ["広報の担当は山本"], oa(STORY_ONE))
    sess = os.path.join(store, "sessions")
    ops = os.path.join(sess, sorted(os.listdir(sess))[0], "ops.jsonl")
    rows = [json.loads(ln) for ln in open(ops, encoding="utf-8")]
    meta = [x for x in rows if x["op"] == "harness_meta"]
    assert len(meta) == 1 and {"kind": "memory_profile", "name": rn.MEMORY_PROFILE_DEFAULT, "version": "1"} in json.loads(meta[0]["args"]["plugins"])


# -- backends and the command line ------------------------------------------------------------------------------------------------
def test_a_backend_plugin_is_selected_by_name(reg, docs, tmp_path, capsys):
    b = make_backend("fakegpt", "m")
    assert b.name == "openai"
    with pytest.raises(BackendError) as e:
        make_backend("nonesuch", "m")
    assert e.value.code == "bad_backend" and "fakegpt" in str(e.value)
    rc = cli.main(["ask", "--docs", docs, "--runs-dir", str(tmp_path / "runs"), "--backend", "fakegpt", "--model", "m", "--gate-filter", "refuse-all", QUESTION])
    out = capsys.readouterr().out
    assert rc == 1 and out.startswith("分かりません（理由: plugin_refused")


def test_vera_plugins_lists_builtins_and_installed_plugins(reg, capsys):
    assert cli.main(["plugins"]) == 0
    out = capsys.readouterr().out
    assert "backend         openai" in out and "built-in" in out and "gate            no-digits" in out and "plugin (mine=" in out
    assert cli.main(["plugins", "--json"]) == 0
    j = json.loads(capsys.readouterr().out)
    assert {p["name"] for p in j["plugins"]} >= {"anthropic", "evidence.v6", "no-digits", "m6d-v17"} and j["errors"] == []
