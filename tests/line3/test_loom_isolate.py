"""LOOM-d2 tests: the OS half of enforcement layer L3 (verantyx/loom/isolate.py, tools/loom_isolation_profile.sb, experiments/line3/loom/code_harness.py,
`vera loom mcp --isolated`; docs/LINE3_LOCAL_DECISIONS.md "LOOM-d2", L-LOOM-85..).

Everything here runs a real `sandbox-exec`.  When it cannot (not macOS, no /usr/bin/sandbox-exec, or this process is itself inside a sandbox) the
tests that need it are SKIPPED with a typed reason ("ENV_MISSING[sandbox_exec]: isolation_unavailable:<reason>"); the tests of the refusal logic, the profile text and the
policy do not need it and always run.  The only network these tests touch is a connect() that the sandbox must refuse: 127.0.0.1 port 9 and the
documentation address 192.0.2.1 (never routable); no external host is contacted.
"""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import textwrap

import pytest

from verantyx.loom import isolate as iso
from verantyx.loom import ledger as lg
from loom_common import ROOT

_spec = importlib.util.spec_from_file_location("loom_code_harness_d2", os.path.join(ROOT, "experiments/line3/loom/code_harness.py"))
harness = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(harness)

import test_loom_code as tlc            # noqa: E402  (run_text, begun, code_server, sc: the code-run helpers of LOOM-code)

FIXTURE = os.path.join(ROOT, "experiments/line3/loom/fixture_repo")
FIXTURE_DIR = FIXTURE
TASKS_DEMO = os.path.join(ROOT, "experiments/line3/loom/tasks_demo.jsonl")
SKIP = "ENV_MISSING[sandbox_exec]: isolation_unavailable:"     # the suite's classified-skip convention (tests/conftest.py), with the typed reason after it


@pytest.fixture(scope="module")
def probe_result():
    why = iso.available()
    if why:
        pytest.skip(SKIP + why)
    res = harness.probe_fixture()
    if res.status == "unavailable":
        pytest.skip(SKIP + str(res.reason))
    return res


@pytest.fixture
def need_sandbox(probe_result):
    return probe_result


# ---------------------------------------------------------------------------------------------------------------------------------
# the probe: the four properties of the ticket, proved from inside the sandbox
# ---------------------------------------------------------------------------------------------------------------------------------
def test_the_probe_passes_and_is_a_typed_result(probe_result):
    r = probe_result
    assert isinstance(r, iso.ProbeResult) and r.ok and r.status == "passed" and r.mechanism == "sandbox-exec" and r.reason is None
    assert set(r.properties) == set(iso.PROPERTIES) and all(r.properties.values())
    assert r.profile_sha == iso.profile_sha()
    row = r.to_row()
    assert set(row) == {"status", "properties"}                                 # L-LOOM-117: the hashed row has no evidence
    assert set(r.report()) == {"status", "properties", "evidence"}
    json.dumps(row, sort_keys=True)                                             # a plain, serialisable value
    blob = json.dumps(r.report())
    for frag in ("/Users/", "/private/", "/tmp", "/var/", "loom_decoy", "ssh"):
        assert frag not in blob.replace("ls_ssh", "").replace("ssh_ed25519", "").replace("ssh_rsa", "").replace("ssh_known_hosts", ""), frag


def test_property_1_the_network_connect_fails_at_the_os(probe_result):
    net = probe_result.evidence["net"]
    assert probe_result.properties["network_blocked"]
    # EPERM from the sandbox - not ECONNREFUSED (the packet reached the loopback stack) and not a timeout (the packet left the machine)
    assert set(net) == {"loopback_closed_port", "non_routable", "unix_socket", "udp_sendto", "bind_listen"}
    assert set(net.values()) == {"EPERM"}, net


def test_property_2_a_write_outside_the_write_root_fails_and_a_write_inside_works(probe_result):
    wo = probe_result.evidence["write_outside"]
    assert probe_result.properties["write_outside_blocked"] and probe_result.properties["write_inside_ok"]
    assert set(wo) == {"decoy_dir", "home", "tmp", "var_tmp", "readonly_0"}        # readonly_0 = the fixture copy itself: a job cannot rewrite its tests
    assert set(wo.values()) == {"EPERM"}, wo
    assert probe_result.evidence["write_inside"] == "OK"                            # the control: the failures above are the sandbox, not a broken setup


def test_property_3_reading_home_ssh_and_other_secrets_fails(probe_result):
    rs = probe_result.evidence["read_secret"]
    assert probe_result.properties["read_secret_blocked"]
    for k in ("decoy_file", "ls_home", "ls_ssh", "ssh_ed25519", "ssh_known_hosts", "etc_passwd"):
        assert rs[k] == "EPERM", (k, rs)
    assert rs["ssh_rsa"] in ("EPERM", "ENOENT")                                    # a name that does not exist on this machine may answer ENOENT


def test_property_4_the_fixture_is_readable_and_the_bytes_are_the_parents(probe_result):
    assert probe_result.properties["fixture_readable"] and probe_result.evidence["fixture"] == "match"


def test_no_fork_no_exec_and_the_rlimits_are_what_was_asked(probe_result):
    assert probe_result.properties["process_blocked"] and probe_result.evidence["proc"] == {"fork": "EPERM", "exec": "EPERM"}
    lim = iso.Limits()
    assert probe_result.properties["rlimits_set"] and probe_result.evidence["rlimits"]["RLIMIT_CPU"] == lim.cpu_s
    assert probe_result.evidence["rlimits"]["RLIMIT_FSIZE"] == lim.fsize_bytes and probe_result.evidence["rlimits"]["RLIMIT_CORE"] == 0


def test_property_5_the_sysctl_that_returns_the_parents_environment_is_denied(probe_result):
    """L-LOOM-114: with `(allow sysctl-read)` a sandboxed process read the full ENVIRONMENT of its parent (KERN_PROCARGS2) and the process table
    (KERN_PROC_ALL).  Under the fixed profile ctypes cannot even be imported (it calls os.uname(), a sysctl); an import failure counts as blocked,
    and if ctypes WERE reachable both calls must answer EPERM."""
    sc = probe_result.evidence["sysctl"]
    assert probe_result.properties["sysctl_procargs_blocked"] is True
    if sc["ctypes_import"] == "OK":
        assert sc.get("libc", "").startswith("blocked:") or (sc["procargs2_parent"] in iso.BLOCKED and sc["proc_all"] in iso.BLOCKED), sc
    else:
        assert sc["ctypes_import"].startswith("blocked:"), sc


def test_the_probe_FAILS_when_sysctl_read_is_allowed_again(tmp_path, monkeypatch, need_sandbox):
    """The new property is not a rubber stamp: put the old `(allow sysctl-read)` back (a copy of the real profile with that one line added) and the
    probe is `failed`, with `sysctl_procargs_blocked` False and every other property still True; the evidence shows the parent's args were reachable."""
    real = open(iso.PROFILE_PATH, encoding="utf-8").read()
    old = tmp_path / "old.sb"
    old.write_text(real.replace("(allow signal (target self))\n", "(allow signal (target self))\n(allow sysctl-read)\n"), encoding="utf-8")
    assert "(allow sysctl-read)" in old.read_text(encoding="utf-8") and "(allow sysctl-read)" not in real.replace(";; ", "").replace("`(allow sysctl-read)`", "")
    monkeypatch.setattr(iso, "PROFILE_PATH", old)
    r = harness.probe_fixture()
    assert r.status == "failed" and r.properties["sysctl_procargs_blocked"] is False
    assert all(v for k, v in r.properties.items() if k != "sysctl_procargs_blocked"), r.properties
    assert r.evidence["sysctl"]["ctypes_import"] == "OK" and r.evidence["sysctl"]["procargs2_parent"] == "OK" and r.evidence["sysctl"]["proc_all"] == "OK"


def test_sysctl_blocked_judges_the_evidence_strictly():
    ok = iso._sysctl_blocked
    assert ok({"ctypes_import": "blocked:EPERM"}) and ok({"ctypes_import": "blocked:ImportError"})
    assert ok({"ctypes_import": "OK", "libc": "blocked:OSError"})
    assert ok({"ctypes_import": "OK", "procargs2_parent": "EPERM", "proc_all": "EACCES"})
    assert not ok({"ctypes_import": "OK", "procargs2_parent": "OK", "proc_all": "EPERM"})
    assert not ok({"ctypes_import": "OK", "procargs2_parent": "EPERM", "proc_all": "OK"})
    assert not ok({"ctypes_import": "OK", "procargs2_parent": "ENOENT", "proc_all": "EPERM"})        # any other answer is not "denied"
    assert not ok({}) and not ok(None) and not ok({"ctypes_import": "OK"})                          # a missing key / a missing section never passes


def test_the_probe_FAILS_under_a_profile_that_does_not_deny(tmp_path, monkeypatch, need_sandbox):
    """The probe is not a rubber stamp: with `(allow default)` the properties are False and the status is `failed`."""
    perm = tmp_path / "permissive.sb"
    perm.write_text("(version 1)\n(allow default)\n")
    monkeypatch.setattr(iso, "PROFILE_PATH", perm)
    made = []
    real_make = iso._make_decoys

    def spy(home):
        out = real_make(home)
        made.append(out)
        return out
    monkeypatch.setattr(iso, "_make_decoys", spy)
    r = harness.probe_fixture()
    assert r.status == "failed" and not r.ok
    assert r.properties["network_blocked"] is False and r.properties["write_outside_blocked"] is False
    assert r.properties["read_secret_blocked"] is False and r.properties["process_blocked"] is False and r.properties["sysctl_procargs_blocked"] is False
    assert r.properties["fixture_readable"] is True and r.properties["write_inside_ok"] is True        # the controls still work
    (base, _secrets, write_outside), = made                                                              # THIS probe's own decoys (other runs may be probing at the same time)
    assert write_outside and not [p for p in write_outside.values() if os.path.exists(p)]               # the probe cleaned up what it wrote into $HOME, /tmp, /var/tmp
    assert not os.path.exists(base)


def test_the_probe_is_unavailable_with_a_typed_reason_when_sandbox_exec_is_missing(monkeypatch):
    monkeypatch.setattr(iso, "SANDBOX_EXEC", "/nonexistent/sandbox-exec")
    r = harness.probe_fixture()
    assert r.status == "unavailable" and r.reason == "sandbox_exec_missing" and not r.ok and r.properties == {}


# ---------------------------------------------------------------------------------------------------------------------------------
# the harness: the gate is the probe
# ---------------------------------------------------------------------------------------------------------------------------------
def k1_run(tmp_path, run_id="d2"):
    srv = tlc.code_server(tmp_path)
    w = tlc.begun(srv, "K1", run_id)
    tlc.sc.weave_k(w, "K1")
    return str(srv.run_dir(run_id))


def attest_rows(d):
    return [json.loads(l) for l in open(os.path.join(d, "ops.jsonl"), encoding="utf-8") if '"op":"attest"' in l or '"op": "attest"' in l]


def test_the_harness_refuses_every_driver_when_sandbox_exec_is_missing(tmp_path, monkeypatch):
    d = k1_run(tmp_path)
    monkeypatch.setattr(iso, "SANDBOX_EXEC", "/nonexistent/sandbox-exec")
    ran = []
    monkeypatch.setattr(iso, "pytest_job", lambda *a, **k: ran.append(1))
    for driver in ("scripted", "model"):
        r = harness.test_emitted_run(d, driver=driver)
        assert r["status"] == "isolation_failed" and r["probe"]["status"] == "unavailable" and r["probe"]["reason"] == "sandbox_exec_missing", driver
    assert ran == [] and attest_rows(d) == []                                    # nothing ran, nothing attested - not even for the scripted driver
    assert harness.main(["test", d]) == 2                                         # the CLI exit code


def test_the_harness_refuses_when_a_property_does_not_hold_and_nothing_runs(tmp_path, monkeypatch):
    d = k1_run(tmp_path)
    bad = {k: True for k in iso.PROPERTIES}
    bad["network_blocked"] = False
    monkeypatch.setattr(iso, "probe", lambda *a, **k: iso.ProbeResult("failed", profile_sha=iso.profile_sha(), properties=bad))
    monkeypatch.setattr(iso, "pytest_job", lambda *a, **k: pytest.fail("a job was started although the probe failed"))
    r = harness.test_emitted_run(d, driver="scripted")
    assert r["status"] == "isolation_failed" and r["probe"]["status"] == "failed" and r["probe"]["properties"]["network_blocked"] is False
    assert attest_rows(d) == [] and lg.verify(d)["status"] == "OK"


def test_the_token_is_an_override_only_when_the_probe_cannot_pass_and_the_row_says_so(tmp_path, monkeypatch, capsys):
    d = k1_run(tmp_path)
    monkeypatch.setattr(iso, "SANDBOX_EXEC", "/nonexistent/sandbox-exec")
    r = harness.test_emitted_run(d, driver="model", isolation_token="vm-air-test")
    err = capsys.readouterr().err
    assert "ISOLATION OVERRIDE vm-air-test" in err and "python_fallback" in err                                   # logged
    assert r["status"] == "tested" and r["exit_code"] == 0
    iso_row = r["isolation"]
    assert iso_row["mechanism"] == "python_fallback" and iso_row["override"] is True and iso_row["network"] == "monkeypatched"
    assert iso_row["probe"]["status"] == "unavailable" and iso_row["probe"]["reason"] == "sandbox_exec_missing"
    (a,) = attest_rows(d)
    assert a["args"]["isolation_token"] == "vm-air-test" and a["args"]["isolation"]["mechanism"] == "python_fallback"
    assert lg.verify(d)["status"] == "OK"


def test_a_token_does_not_override_a_probe_that_RAN_AND_FAILED(tmp_path, monkeypatch, capsys):
    """L-LOOM-115: the override is for a probe that could not run (`unavailable`).  A probe that ran and found a property false, plus a token, used
    to run the tests with no wall at all."""
    d = k1_run(tmp_path)
    bad = {k: True for k in iso.PROPERTIES}
    bad["sysctl_procargs_blocked"] = False
    monkeypatch.setattr(iso, "probe", lambda *a, **k: iso.ProbeResult("failed", profile_sha=iso.profile_sha(), properties=bad, evidence={"x": 1}))
    started = []
    monkeypatch.setattr(iso, "pytest_job", lambda *a, **k: started.append("sandbox"))
    monkeypatch.setattr(harness, "_run_fallback", lambda *a, **k: started.append("fallback"))
    monkeypatch.setattr(iso.subprocess, "Popen", lambda *a, **k: started.append("popen"))
    r = harness.test_emitted_run(d, driver="model", isolation_token="vm-air-test")
    assert r["status"] == "isolation_failed" and r["probe"]["status"] == "failed" and r["probe"]["properties"]["sysctl_procargs_blocked"] is False
    assert "no token overrides" in r["reason"]
    assert started == [] and attest_rows(d) == [] and "ISOLATION OVERRIDE" not in capsys.readouterr().err        # no process of any kind, no row, no override line
    assert harness.run_pytest(FIXTURE_DIR, "calc/ops.py", "", ["tests/test_ops.py"], isolation_token="vm-air-test")["status"] == "isolation_failed"
    assert started == []
    assert harness.main(["test", d, "--isolation-confirmed", "vm-air-test"]) == 2


def test_the_fallback_launcher_cuts_the_socket_module_and_says_it_is_weak(tmp_path):
    (tmp_path / "netprobe.py").write_text(textwrap.dedent('''
        import socket
        try:
            socket.create_connection(("127.0.0.1", 9), timeout=1)
            print("RESULT connected-or-refused")
        except OSError as e:
            print("RESULT", type(e).__name__, e.errno)
        '''))
    argv = iso.fallback_argv("module", sys.executable, args=[], path=[str(tmp_path)], limits=iso.Limits())
    cfg = json.loads(argv[-1])
    assert cfg["block_socket"] is True and argv[0] == sys.executable and "sandbox-exec" not in argv[0]
    cfg["module"] = "netprobe"
    argv[-1] = json.dumps(cfg)
    out = iso.run_job(argv, iso.clean_env(str(tmp_path)), str(tmp_path), 20)
    assert out.exit_code == 0 and "RESULT PermissionError 1" in out.output, out


# ---------------------------------------------------------------------------------------------------------------------------------
# the attest row
# ---------------------------------------------------------------------------------------------------------------------------------
def test_the_attest_row_has_the_isolation_fields_and_no_path(tmp_path, need_sandbox):
    d = k1_run(tmp_path)
    r = harness.test_emitted_run(d, driver="scripted")
    assert r["status"] == "tested" and r["exit_code"] == 0
    (a,) = attest_rows(d)
    isolation = a["args"]["isolation"]
    assert set(isolation) == {"mechanism", "profile_sha", "boot_sha", "python_flags", "limits", "network", "probe"}
    assert isolation["mechanism"] == "sandbox-exec" and isolation["profile_sha"] == iso.profile_sha() and isolation["boot_sha"] == iso.BOOT_SHA
    assert isolation["python_flags"] == ["-s", "-S", "-P"] and isolation["network"] == "denied"
    assert isolation["limits"] == iso.Limits().describe()
    p = isolation["probe"]
    assert p["status"] == "passed" and set(p["properties"]) == set(iso.PROPERTIES) and all(p["properties"].values())
    assert set(p) == {"status", "properties"}                                                       # L-LOOM-117: evidence is NOT hashed
    assert a["args"]["outcome"] == "passed" and a["args"]["pytest_result"] == {"collected": 4, "failed": 0, "exitstatus": 0} and a["args"]["expected_min"] == 4
    # the evidence went to the unhashed sidecar, one line per attest row
    side = [json.loads(l) for l in open(os.path.join(d, harness.EVIDENCE_SIDECAR), encoding="utf-8")]
    assert len(side) == 1 and side[0]["row_i"] == a["i"] and side[0]["profile_sha"] == iso.profile_sha() and side[0]["text_sha"] == a["args"]["text_sha"]
    assert set(side[0]["evidence"]) == {"net", "write_outside", "write_inside", "read_secret", "fixture", "proc", "rlimits", "sysctl"}
    blob = json.dumps(a["args"], ensure_ascii=False)
    for frag in ("/Users/", "/private/", "/var/folders", "/tmp", "loom_code_", "loom_decoy", "Traceback"):
        assert frag not in blob, frag
    assert a["args"]["driver"] == "scripted" and a["args"]["isolation_token"] is None
    assert lg.verify(d)["status"] == "OK"                                                           # the sidecar is outside the chain


def test_the_attest_row_does_not_depend_on_the_machine_dependent_evidence(tmp_path, monkeypatch):
    """L-LOOM-117: the same run attested with ENOENT-flavoured and EPERM-flavoured evidence has the identical row (same args), only the sidecar differs."""
    props = {k: True for k in iso.PROPERTIES}
    rows, sides = [], []
    for i, flavour in enumerate(("ENOENT", "EPERM")):
        d = k1_run(tmp_path / ("r%d" % i), run_id="same")
        monkeypatch.setattr(iso, "probe", lambda *a, _f=flavour, **k: iso.ProbeResult(
            "passed", profile_sha=iso.profile_sha(), properties=props, evidence={"read_secret": {"ssh_rsa": _f}}))
        r = harness.test_emitted_run(d, driver="scripted")
        assert r["status"] == "tested" and r["outcome"] == "passed"
        (a,) = attest_rows(d)
        rows.append(json.dumps(a["args"], sort_keys=True))
        sides.append(json.loads(open(os.path.join(d, harness.EVIDENCE_SIDECAR), encoding="utf-8").read())["evidence"])
    assert rows[0] == rows[1] and "ENOENT" not in rows[0] and "EPERM" not in rows[0]
    assert sides == [{"read_secret": {"ssh_rsa": "ENOENT"}}, {"read_secret": {"ssh_rsa": "EPERM"}}]


# ---------------------------------------------------------------------------------------------------------------------------------
# woven text that passes every gate and attacks: the OS is the wall
# ---------------------------------------------------------------------------------------------------------------------------------
HEAD = "import typing\nB = typing.sys.modules['builtins']\n"          # passes the gates (L-LOOM-78: typing.sys); B.exec is an ATTRIBUTE, not a blocked name
ATTACKS = {
    "network": HEAD + "B.exec(\"import socket as s\")\nA = ('127.0.0.1', 9)\nB.exec(\"s.create_connection(A)\")\n",
    "read_outside": HEAD + "P = '/etc/passwd'\nB.exec(\"open(P).read()\")\n",
    "write_outside": HEAD + "P = '/tmp/loom_pwned_d2'\nB.exec(\"open(P, 'w').write('x')\")\n",
    "fork": HEAD + "B.exec(\"import os\")\nB.exec(\"os.fork()\")\n",
}


@pytest.mark.parametrize("name", sorted(ATTACKS))
def test_a_woven_text_that_passes_the_gates_and_attacks_is_stopped_by_the_os(tmp_path, name, need_sandbox):
    w, em, d = tlc.run_text(tmp_path, ATTACKS[name], run_id="atk_" + name)
    assert em["ok"] is True, em                                                      # the gates let it through (they are not a wall)
    r = harness.test_emitted_run(d)
    assert r["status"] == "tested" and r["isolation"]["mechanism"] == "sandbox-exec"
    assert r["exit_code"] != 0 and "Operation not permitted" in r["tail"], r["tail"]
    assert not os.path.exists("/tmp/loom_pwned_d2")


def test_the_same_construct_without_an_attack_is_not_what_fails(tmp_path, need_sandbox):
    w, em, d = tlc.run_text(tmp_path, HEAD + "B.exec(\"x = 1\")\n", run_id="atk_control")
    assert em["ok"] is True
    r = harness.test_emitted_run(d)
    assert r["status"] == "tested" and "Operation not permitted" not in r["tail"] and "PermissionError" not in r["tail"]


def test_exit_0_without_tests_is_now_tests_incomplete_not_passed(tmp_path, need_sandbox):
    """L-LOOM-116 (was the KNOWN_LIMIT of L-LOOM-92): a gate-passing text that ends the test process with exit code 0 before one test ran used to be
    `passed`.  The `rec` plugin writes pytest's own counts at session finish; the process died first, so there is no file => `tests_incomplete`."""
    w, em, d = tlc.run_text(tmp_path, HEAD.replace("B = typing.sys.modules['builtins']", "B = typing.sys.modules['os']") + "B._exit(0)\n", run_id="forge")
    assert em["ok"] is True
    r = harness.test_emitted_run(d)
    assert r["status"] == "tested" and r["exit_code"] == 0 and r["tail"] == ""                    # the process still says 0 and printed nothing ...
    assert r["outcome"] == "tests_incomplete" and r["passed"] is False and r["pytest_result"] is None      # ... and the harness does not believe it
    (a,) = attest_rows(d)
    assert a["args"]["exit_code"] == 0 and a["args"]["outcome"] == "tests_incomplete" and a["args"]["pytest_result"] is None
    assert lg.verify(d)["status"] == "OK"


def test_KNOWN_LIMIT_a_same_process_forgery_of_the_result_file_still_passes(tmp_path, need_sandbox):
    """Pinned (L-LOOM-116/92): the bar is raised, not closed.  A gate-passing text runs in the SAME process as pytest and can write the result
    file itself (the scratch folder is writable and its path is $HOME) before ending the process.  Closing it is the gate side (block the attribute
    names sys / _sys / modules / os / builtins / _exit in code.py) and is filed as a follow-up; when that lands this test must flip on purpose."""
    text = (HEAD +
            "B.exec(\"import os\")\n"
            "B.exec(\"import json\")\n"
            "B.exec(\"P = os.environ['HOME']\")\n"
            "B.exec(\"P += '/pytest_result.json'\")\n"
            "B.exec(\"F = open(P, 'w')\")\n"
            "B.exec(\"D = {'collected': 99}\")\n"
            "B.exec(\"D['failed'] = 0\")\n"
            "B.exec(\"D['exitstatus'] = 0\")\n"
            "B.exec(\"json.dump(D, F)\")\n"
            "B.exec(\"F.close()\")\n"
            "B.exec(\"os._exit(0)\")\n")
    w, em, d = tlc.run_text(tmp_path, text, run_id="forge2")
    assert em["ok"] is True, em
    r = harness.test_emitted_run(d)
    assert r["status"] == "tested" and r["exit_code"] == 0 and r["outcome"] == "passed" and r["pytest_result"]["collected"] == 99   # forged: not proof


def test_a_shortfall_in_the_collected_count_is_tests_incomplete(tmp_path, monkeypatch, need_sandbox):
    """exit 0 and a file that says so, but fewer tests collected than the test files define: a text that deselected / skipped tests."""
    d = k1_run(tmp_path)
    monkeypatch.setattr(harness, "count_test_functions", lambda *a, **k: 400)                     # more than pytest can have collected
    r = harness.test_emitted_run(d, driver="scripted")
    assert r["status"] == "tested" and r["exit_code"] == 0 and r["pytest_result"] == {"collected": 4, "failed": 0, "exitstatus": 0}
    assert r["outcome"] == "tests_incomplete" and r["passed"] is False and r["expected_min"] == 400
    (a,) = attest_rows(d)
    assert a["args"]["outcome"] == "tests_incomplete" and a["args"]["expected_min"] == 400


def test_judge_requires_the_file_and_all_three_agreements():
    j = harness.judge
    good = {"collected": 4, "failed": 0, "exitstatus": 0}
    assert j(0, good, 4) == "passed" and j(0, dict(good, collected=9), 4) == "passed"
    assert j(0, None, 4) == "tests_incomplete"                                                    # no file
    assert j(0, dict(good, collected=3), 4) == "tests_incomplete"                                 # fewer than N
    assert j(0, dict(good, collected=0), 0) == "tests_incomplete"                                 # N = 0 still needs one test
    assert j(0, dict(good, failed=1), 4) == "tests_incomplete"                                    # a failure behind an exit 0
    assert j(0, dict(good, exitstatus=1), 4) == "tests_incomplete"                                # the file contradicts the process
    for rc in (1, 2, 5, -9, -10):
        assert j(rc, good, 4) == "failed" and j(rc, None, 4) == "failed"                          # a non-zero exit is a failure, whatever the file says


def test_the_result_file_is_checked_not_trusted(tmp_path):
    import pathlib
    sc_ = pathlib.Path(tmp_path)
    f = sc_ / iso.RESULT_NAME
    assert harness.read_pytest_result(sc_) is None                                                # absent
    for bad in ("not json", "[]", '{"collected": 1}', '{"collected": 1, "failed": 0, "exitstatus": 0, "x": 1}',
                '{"collected": "1", "failed": 0, "exitstatus": 0}', '{"collected": true, "failed": 0, "exitstatus": 0}',
                '{"collected": -1, "failed": 0, "exitstatus": 0}', '{"collected": 1.0, "failed": 0, "exitstatus": 0}'):
        f.write_text(bad)
        assert harness.read_pytest_result(sc_) is None, bad
    f.write_text('{"collected": 4, "failed": 0, "exitstatus": 0}')
    assert harness.read_pytest_result(sc_) == {"collected": 4, "failed": 0, "exitstatus": 0}


def test_n_is_the_static_count_of_test_functions_in_the_named_files(tmp_path):
    import pathlib
    w = pathlib.Path(tmp_path)
    (w / "t_a.py").write_text("def test_one():\n    pass\n\nasync def test_two():\n    pass\n\ndef helper():\n    pass\n\n"
                              "class TestC:\n    def test_m(self):\n        pass\n    def other(self):\n        pass\n\n"
                              "class Plain:\n    def test_not_collected(self):\n        pass\n")
    (w / "t_b.py").write_text("def test_x(:\n    pass\ndef test_y():\n    pass\n")             # does not parse: regex fallback
    assert harness.count_test_functions(w, ["t_a.py"]) == 3
    assert harness.count_test_functions(w, ["t_b.py"]) == 2 and harness.count_test_functions(w, ["t_a.py", "t_b.py", "missing.py"]) == 5
    fx = os.path.join(ROOT, "experiments/line3/loom/fixture_repo")
    import pathlib as _p
    assert harness.count_test_functions(_p.Path(fx), ["tests/test_k1.py", "tests/test_ops.py"]) == 4


# ---------------------------------------------------------------------------------------------------------------------------------
# limits and the launcher kinds
# ---------------------------------------------------------------------------------------------------------------------------------
def run_module(tmp_path, source, limits=iso.Limits(), timeout=30):
    """Run `job.py` (source) with the module launcher inside the sandbox, the way the MCP server is run."""
    work = os.path.realpath(str(tmp_path))
    scratch = os.path.join(work, "scratch")
    os.makedirs(scratch, exist_ok=True)
    mods = os.path.join(work, "mods")
    os.makedirs(mods, exist_ok=True)
    with open(os.path.join(mods, "job.py"), "w") as f:
        f.write(textwrap.dedent(source))
    policy = iso.Policy.make(read=[mods], write=[scratch])
    argv = iso.launcher_argv(policy, "module", path=[mods], limits=limits, module="job")
    return iso.run_job(argv, iso.clean_env(scratch), cwd=scratch, timeout=timeout, limits=limits), scratch


def test_the_module_launcher_the_mcp_server_uses_is_walled_too(tmp_path, need_sandbox):
    real_home = os.path.expanduser("~")
    out, scratch = run_module(tmp_path, """
        import os, socket
        for label, fn in (("net", lambda: socket.create_connection(("127.0.0.1", 9), timeout=1)),
                          ("ssh", lambda: os.listdir(%r)),
                          ("write", lambda: open("/tmp/loom_pwned_d2_mod", "w")),
                          ("inside", lambda: open(os.path.join(os.environ["HOME"], "ok.txt"), "w").write("x"))):
            try:
                fn()
                print("RESULT", label, "OK")
            except OSError as e:
                print("RESULT", label, e.errno)
        """ % (real_home + "/.ssh",))
    got = dict((ln.split()[1], ln.split()[2]) for ln in out.output.splitlines() if ln.startswith("RESULT"))
    assert got == {"net": "1", "ssh": "1", "write": "1", "inside": "OK"}, out.output
    assert not os.path.exists("/tmp/loom_pwned_d2_mod")


def test_the_memory_watchdog_kills_a_job_past_the_cap(tmp_path, need_sandbox):
    out, _ = run_module(tmp_path, '''
        import time
        blob = bytearray(600 * 1024 * 1024)
        for i in range(0, len(blob), 4096):
            blob[i] = 1
        time.sleep(30)
        ''', limits=iso.Limits(mem_rss_bytes=200 << 20), timeout=30)
    assert out.killed == "memory" and out.exit_code == iso.KILL_MEMORY


def test_the_wall_clock_timeout_kills_the_whole_process_group(tmp_path, need_sandbox):
    import time
    t0 = time.monotonic()
    out, _ = run_module(tmp_path, "import time\ntime.sleep(60)\n", timeout=2)
    assert out.killed == "timeout" and out.exit_code == iso.KILL_TIMEOUT == -9 and time.monotonic() - t0 < 15


def test_the_file_size_rlimit_stops_a_big_write(tmp_path, need_sandbox):
    out, scratch = run_module(tmp_path, '''
        import os
        try:
            with open(os.path.join(os.environ["HOME"], "big.bin"), "wb") as f:
                f.write(b"x" * (4 << 20))
                f.flush()
            print("RESULT wrote")
        except OSError as e:
            print("RESULT", e.errno)
        ''', limits=iso.Limits(fsize_bytes=1 << 20))
    assert "RESULT wrote" not in out.output and os.path.getsize(os.path.join(scratch, "big.bin")) <= 1 << 20


def test_the_job_gets_no_stdin_and_a_cleared_environment(tmp_path, need_sandbox, monkeypatch):
    monkeypatch.setenv("LOOM_SECRET_FOR_TEST", "leak")
    out, _ = run_module(tmp_path, '''
        import os, sys
        print("RESULT env", sorted(os.environ))
        print("RESULT stdin", repr(sys.stdin.read()))
        ''')
    assert "LOOM_SECRET_FOR_TEST" not in out.output and "RESULT stdin ''" in out.output
    assert "'PYTHONHASHSEED'" in out.output and "'PATH'" in out.output


# ---------------------------------------------------------------------------------------------------------------------------------
# the profile and the policy: no sandbox needed
# ---------------------------------------------------------------------------------------------------------------------------------
EXPECTED_PROFILE_SHA = "020a227bb749f5395135789ea910ead431ec4a8cfef226418e7d100f6c22f509"     # after L-LOOM-114 (no sysctl-read); the old one was f887c336...


def test_the_profile_sha_is_deterministic_and_machine_independent():
    a, b = iso.profile_sha(), iso.profile_sha()
    assert a == b == hashlib.sha256(open(iso.PROFILE_PATH, "rb").read()).hexdigest() and len(a) == 64
    text = open(iso.PROFILE_PATH, encoding="utf-8").read()
    for frag in ("/Users", "/private/var/folders", "/opt/homebrew", "motonisihikoudai", "/tmp"):
        assert frag not in text, frag                                              # paths arrive as -D parameters: the file names the RULES, not the machine
    out = subprocess.run([sys.executable, "-c", "from verantyx.loom import isolate as i; print(i.profile_sha())"], cwd="/", capture_output=True,
                         text=True, env={"PATH": "/usr/bin:/bin", "PYTHONPATH": ROOT, "PYTHONHASHSEED": "7"})
    assert out.stdout.strip() == a, out
    assert a == EXPECTED_PROFILE_SHA, "the profile changed: review tools/loom_isolation_profile.sb, then pin the new sha (a deliberate act)"


def test_the_profile_denies_what_the_ticket_says():
    text = open(iso.PROFILE_PATH, encoding="utf-8").read()
    rules = [ln for ln in text.splitlines() if not ln.lstrip().startswith(";;")]
    body = "\n".join(rules)
    assert "(deny default)" in body and "(deny network*)" in body
    assert "(allow network" not in body and "process-fork" not in body and "(allow default" not in body and "mach-lookup" not in body
    assert "file-write*" in body and body.count("(allow file-write*") == 1
    assert "(allow process-exec (literal (param \"EXEC0\")) (literal (param \"EXEC1\")))" in body


def test_the_policy_params_fill_every_slot_and_reject_overflow_and_relative_paths(tmp_path):
    (tmp_path / "w").mkdir()
    pol = iso.Policy.make(read=[tmp_path], write=[tmp_path / "w"])
    params = pol.params()
    assert len([k for k in params if k.startswith("RT")]) == iso.N_RT and len([k for k in params if k.startswith("READ")]) == iso.N_READ
    assert len([k for k in params if k.startswith("WRITE")]) == iso.N_WRITE and len([k for k in params if k.startswith("LIST")]) == iso.N_LIST
    assert params["READ0"] == os.path.realpath(str(tmp_path)) and params["READ1"] == iso.NOPLACE
    assert all(os.path.isabs(v) for v in params.values())
    assert params["EXEC0"] == os.path.realpath(sys.executable)
    with pytest.raises(ValueError):
        iso.Policy(read=tuple("/x%d" % i for i in range(iso.N_READ + 1)), write=(), runtime=(), python=sys.executable)
    with pytest.raises(ValueError):
        iso.Policy(read=("relative/path",), write=(), runtime=(), python=sys.executable)
    argv = iso.sandbox_argv(pol, ["/bin/true"])
    assert argv[0] == iso.SANDBOX_EXEC and argv[-1] == "/bin/true" and argv.count("-D") == len(params)
    assert iso.sandbox_argv(pol, ["/bin/true"]) == argv                                  # deterministic order


def test_the_runtime_roots_name_the_venv_the_framework_and_the_symlinks_to_the_interpreter():
    roots = iso.runtime_roots()
    assert os.path.realpath(sys.prefix) in roots or any(os.path.realpath(sys.prefix).startswith(r + "/") for r in roots)
    assert any(os.path.realpath(sys.base_prefix) == r or os.path.realpath(sys.base_prefix).startswith(r + "/") for r in roots)
    assert len(roots) <= iso.N_RT and roots == tuple(sorted(set(roots)))
    home = os.path.expanduser("~")
    assert not any(r == home or r.startswith(home + "/.") for r in roots)               # no dot-folder of $HOME is ever a runtime root


# ---------------------------------------------------------------------------------------------------------------------------------
# `vera loom mcp --isolated`
# ---------------------------------------------------------------------------------------------------------------------------------
def test_serve_isolated_refuses_with_exit_3_when_the_probe_fails_and_never_execs(tmp_path, monkeypatch, capsys, need_sandbox):
    perm = tmp_path / "permissive.sb"
    perm.write_text("(version 1)\n(allow default)\n")
    monkeypatch.setattr(iso, "PROFILE_PATH", perm)
    monkeypatch.setattr(iso.os, "execve", lambda *a, **k: pytest.fail("execve although the probe failed"))
    rc = iso.serve_isolated(TASKS_DEMO, str(tmp_path / "runs"))
    err = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert rc == 3 and err["status"] == "isolation_failed" and err["probe"]["status"] == "failed"


def test_serve_isolated_types_a_missing_task_bank_and_a_missing_sandbox(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(iso.os, "execve", lambda *a, **k: pytest.fail("execve"))
    assert iso.serve_isolated(str(tmp_path / "nope.jsonl"), str(tmp_path / "runs")) == 3
    assert json.loads(capsys.readouterr().err.strip())["reason"] == "tasks_missing"
    monkeypatch.setattr(iso, "SANDBOX_EXEC", "/nonexistent/sandbox-exec")
    assert iso.serve_isolated(TASKS_DEMO, str(tmp_path / "runs")) == 3
    err = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert err["status"] == "isolation_failed" and err["probe"]["reason"] == "sandbox_exec_missing"


def test_the_isolated_server_lists_its_20_tools_and_begins_a_run_inside_the_sandbox(tmp_path, need_sandbox):
    pytest.importorskip("mcp")
    import asyncio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    runs = tmp_path / "runs"
    runs.mkdir()

    async def go():
        params = StdioServerParameters(command=sys.executable, args=["-m", "verantyx.cli", "loom", "mcp", "--tasks", TASKS_DEMO, "--runs-dir", str(runs),
                                                                  "--isolated"],
                                       env={"PYTHONPATH": ROOT, "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"}, cwd=ROOT)
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                tools = await s.list_tools()
                res = await s.call_tool("begin", {"task_id": "demo/tokyo_ca", "model": "iso-test"})
                return sorted(t.name for t in tools.tools), res.content[0].text
    names, begin = asyncio.run(asyncio.wait_for(go(), 60))
    assert len(names) == 20 and {"begin", "emit", "abstain", "lookup", "add", "read"} <= set(names)
    assert '"header"' in begin and '"error"' not in begin.lower()
    made = os.listdir(str(runs))
    assert len(made) == 1 and sorted(os.listdir(str(runs / made[0]))) == [".lock", "HEAD", "meta.json", "ops.jsonl", "timing.jsonl"]
    # L-LOOM-118: a run made under --isolated says so (begin result and the unhashed meta.json), the chain does not
    assert json.loads(begin)["isolated"] is True
    meta = json.load(open(str(runs / made[0] / "meta.json"), encoding="utf-8"))
    assert meta["isolated"] is True and meta["isolation_profile_sha"] == iso.profile_sha()
    assert "isolated" not in open(str(runs / made[0] / "ops.jsonl"), encoding="utf-8").read()
    assert lg.verify(str(runs / made[0]))["status"] == "OK"
    assert not [n for n in os.listdir(str(runs)) if n.startswith(".loom_probe")]         # the probe's control file was removed


def test_a_run_made_without_isolation_says_isolated_false_and_the_chain_is_the_same(tmp_path):
    from loom_common import server
    srv = server(tmp_path)
    res = srv.begin("demo/tokyo_ca", "m", "plain")
    assert res["isolated"] is False
    meta = json.load(open(str(tmp_path / "runs" / "plain" / "meta.json"), encoding="utf-8"))
    assert meta["isolated"] is False and "isolation_profile_sha" not in meta
    row0 = json.loads(open(str(tmp_path / "runs" / "plain" / "ops.jsonl"), encoding="utf-8").readline())
    assert "isolated" not in row0["result"]                                    # not hashed: a replay on any machine must give the same row 0


def test_the_isolation_claim_is_read_once_and_believed_only_when_etc_passwd_cannot_be_opened(monkeypatch):
    from verantyx.loom import mcp as m
    sha = iso.profile_sha()
    monkeypatch.delenv("LOOM_ISOLATED", raising=False)
    assert m.isolation_claim() is None                                         # no claim
    monkeypatch.setenv("LOOM_ISOLATED", "yes")
    assert m.isolation_claim() is None                                         # not a sha
    monkeypatch.setenv("LOOM_ISOLATED", sha)
    assert m.isolation_claim() is None                                         # claimed, but /etc/passwd is readable here: not believed

    def denied(*a, **k):
        raise PermissionError(1, "Operation not permitted")
    monkeypatch.setattr(m, "open", denied, raising=False)
    assert m.isolation_claim() == sha                                          # claimed and the wall is felt
    monkeypatch.delenv("LOOM_ISOLATED")
    assert m.isolation_claim() is None                                         # felt but not claimed: not isolated by this launcher


def test_the_isolated_server_begins_a_code_run_and_reads_its_fixture(tmp_path, need_sandbox):
    """L-LOOM-114 check: after `sysctl-read` was removed the sandboxed server still builds the CODE index from the fixture (`code/k1`) and writes the run."""
    pytest.importorskip("mcp")
    import asyncio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    runs = tmp_path / "runs"
    runs.mkdir()
    tasks = os.path.join(ROOT, "experiments/line3/loom/tasks_code.jsonl")

    async def go():
        params = StdioServerParameters(command=sys.executable, args=["-m", "verantyx.cli", "loom", "mcp", "--tasks", tasks, "--runs-dir", str(runs),
                                                                  "--isolated"],
                                       env={"PYTHONPATH": ROOT, "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"}, cwd=ROOT)
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                res = await s.call_tool("begin", {"task_id": "code/k1", "model": "iso-test"})
                return res.content[0].text
    begin = json.loads(asyncio.run(asyncio.wait_for(go(), 60)))
    assert "refusal" not in begin and begin["isolated"] is True and len(begin["header"]["code_index_sha"]) == 64, begin
    (made,) = os.listdir(str(runs))
    assert lg.verify(str(runs / made))["status"] == "OK"
