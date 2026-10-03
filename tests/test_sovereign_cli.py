"""W4-m: the default entrance, `python -m verantyx.cli sovereign <op>`.

Also pins that the older `sovereign --domain NAME=PATH` build keeps its own behaviour: the nested
operations were added next to it, not over it.
"""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'sovereign'))

from verantyx import cli    # noqa: E402
from verantyx import sovereign as sov    # noqa: E402
import sov_memory_ledger as M    # noqa: E402
import sov_protocol_reader as P    # noqa: E402


def run(capsys, *argv):
    """Call the real `main` with an argv list; return (exit code, stdout lines, stderr)."""
    capsys.readouterr()
    try:
        rc = cli.main(["sovereign", *argv])
    except SystemExit as e:
        rc = e.code
    cap = capsys.readouterr()
    return rc, [ln for ln in cap.out.splitlines() if ln], cap.err


def one(capsys, *argv):
    rc, lines, _err = run(capsys, *argv)
    assert len(lines) == 1, lines
    return rc, json.loads(lines[0])


# ------------------------------------------------------------ operations
def test_the_whole_life_of_a_store_through_the_entrance(tmp_path, capsys):
    R, R2 = str(tmp_path / "R"), str(tmp_path / "R2")
    Path(R2).mkdir()
    rc, out = one(capsys, "create", "--root", R, "--store-id", "s1", "--owner", "owner-a")
    assert (rc, out["verdict"], out["consent_promote"]) == (0, "CREATED", False)
    rc, out = one(capsys, "append", "--root", R, "--store-id", "s1", "--kind", "utterance",
                  "--payload", '{"phrase":"p1"}')
    assert (rc, out["verdict"], out["id"]) == (0, "APPENDED", "s1:1")
    rc, out = one(capsys, "promote", "--root", R, "--store-id", "s1")
    assert (rc, out["verdict"], out["wrote"]) == (0, "NO_CONSENT", 0)
    rc, ev_before, _ = run(capsys, "events", "--root", R, "--store-id", "s1")
    assert rc == 0 and len(ev_before) == 1
    rc, out = one(capsys, "detach", "--root", R, "--store-id", "s1")
    assert (rc, out["verdict"]) == (0, "DETACHED")
    rc, out = one(capsys, "events", "--root", R, "--store-id", "s1")
    assert (rc, out["verdict"]) == (1, "DETACHED")
    rc, out = one(capsys, "attach", "--root", R, "--store-id", "s1")
    assert (rc, out["verdict"], out["same_as_detached"]) == (0, "ATTACHED", True)
    assert run(capsys, "events", "--root", R, "--store-id", "s1")[1] == ev_before
    rc, out = one(capsys, "export", "--root", R, "--store-id", "s1", "--to", R2 + "/s1.sqlite")
    assert (rc, out["verdict"]) == (0, "EXPORTED")
    rc, out = one(capsys, "attach", "--root", R2, "--file", R2 + "/s1.sqlite")
    assert (rc, out["verdict"]) == (0, "ATTACHED")
    assert run(capsys, "events", "--root", R2, "--store-id", "s1")[1] == ev_before
    rc, out = one(capsys, "release", "--root", R, "--store-id", "s1", "--confirm", "wrong")
    assert (rc, out["verdict"]) == (1, "REFUSED_NOT_CONFIRMED")
    rc, out = one(capsys, "release", "--root", R, "--store-id", "s1", "--confirm", "s1")
    assert (rc, out["verdict"]) == (0, "RELEASED")
    assert Path(R, "stores", "s1.sqlite").is_file()                   # Vera left the file
    rc, out = one(capsys, "status", "--root", R, "--store-id", "s1")
    assert rc == 0 and out["stores"][0]["status"] == "RELEASED" and out["stores"][0]["file_present"]
    rc, out = one(capsys, "events", "--root", R, "--store-id", "s1")
    assert (rc, out["verdict"]) == (1, "RELEASED")


def test_events_output_equals_the_python_events_one_per_line(tmp_path, capsys):
    R = str(tmp_path / "R")
    sov.create(R, "s1", "owner-a")
    led = sov.open_ledger(R, "s1", now=M.FakeClock())
    for k, p in (("utterance", {"phrase": "あ"}), ("observation", {"cell": "c"}), ("decision", {"n": 3})):
        led.append({"kind": k, "payload": p})
    rc, lines, _ = run(capsys, "events", "--root", R, "--store-id", "s1")
    assert rc == 0 and [json.loads(x) for x in lines] == led.events()
    assert "あ" in lines[0]                                           # not escaped
    rc, lines, _ = run(capsys, "events", "--root", R, "--store-id", "s1", "--since", "s1:2")
    assert [json.loads(x)["seq"] for x in lines] == [3]
    rc, out = one(capsys, "events", "--root", R, "--store-id", "s1", "--since", "s1:99")
    assert (rc, out["verdict"]) == (1, "UNKNOWN_SINCE")


def test_promote_through_the_entrance_on_a_store_prepared_through_python(tmp_path, capsys):
    R = str(tmp_path / "R")
    t = [M.day(0)]
    sov.create(R, "s1", "owner-a", consent_promote=True, now=lambda: M.day(0))
    led = sov.open_ledger(R, "s1", now=lambda: t[0])
    for day in (0, 1, 1):
        t[0] = M.day(day)
        led.append({"kind": "utterance", "payload": {"phrase": "said often"}})
    rc, out = one(capsys, "promote", "--root", R, "--store-id", "s1")
    assert (rc, out["verdict"]) == (0, "PROMOTED")
    assert out["promoted"][0]["key"] == "said often" and out["basis"] == "conversation:s1"
    assert out["thresholds"] == {"d": 2, "n": 3, "source": "prereg"}
    rc, out = one(capsys, "promote", "--root", R, "--store-id", "s1")
    assert (rc, out["verdict"]) == (0, "NOTHING_TO_PROMOTE")
    rc, out = one(capsys, "promotions", "--root", R)
    assert rc == 0 and out["scope"] == "active" and len(out["promotions"]) == 1
    rc, out = one(capsys, "release", "--root", R, "--store-id", "s1", "--confirm", "s1")
    assert out["retired"] == 1
    assert one(capsys, "promotions", "--root", R)[1]["promotions"] == []
    rc, out = one(capsys, "promotions", "--root", R, "--all")
    assert out["scope"] == "all" and out["promotions"][0]["retired"]["reason"] == "RELEASED"


def test_overridden_thresholds_are_shown_as_override(tmp_path, capsys):
    R = str(tmp_path / "R")
    sov.create(R, "s1", "owner-a", consent_promote=True)
    one(capsys, "append", "--root", R, "--store-id", "s1", "--kind", "utterance", "--payload", '{"phrase":"x"}')
    rc, out = one(capsys, "promote", "--root", R, "--store-id", "s1", "--min-count", "1", "--min-days", "1")
    assert (rc, out["verdict"]) == (0, "PROMOTED") and out["thresholds"]["source"] == "override"


def test_consent_through_the_entrance(tmp_path, capsys):
    R = str(tmp_path / "R")
    sov.create(R, "s1", "owner-a")
    rc, out = one(capsys, "consent", "--root", R, "--store-id", "s1", "--promote", "on")
    assert (rc, out["verdict"], out["promote"]) == (0, "CONSENT_RECORDED", True)
    assert sov.describe(R, "s1").consent["promote"] is True
    one(capsys, "consent", "--root", R, "--store-id", "s1", "--promote", "off")
    assert sov.describe(R, "s1").consent["promote"] is False
    rc, out = one(capsys, "create", "--root", R, "--store-id", "s2", "--owner", "o", "--consent-promote")
    assert out["consent_promote"] is True


# ------------------------------------------------------------ exit codes
def test_refusals_and_unreadable_exit_with_1_and_arguments_errors_with_2(tmp_path, capsys):
    R = str(tmp_path / "R")
    assert one(capsys, "create", "--root", R, "--store-id", "bad name", "--owner", "o")[0] == 1
    assert one(capsys, "detach", "--root", R, "--store-id", "nope")[0] == 1
    assert one(capsys, "status", "--root", R, "--store-id", "nope") == (1, {"store_id": "nope", "verdict": "UNKNOWN_STORE"})
    one(capsys, "create", "--root", R, "--store-id", "s1", "--owner", "o")
    assert one(capsys, "create", "--root", R, "--store-id", "s1", "--owner", "o")[1]["verdict"] == "REFUSED_STORE_ID_TAKEN"
    rc, out = one(capsys, "append", "--root", R, "--store-id", "s1", "--kind", "utterance", "--payload", '"just a string"')
    assert (rc, out["verdict"]) == (1, "BAD_PAYLOAD")
    rc, out = one(capsys, "append", "--root", R, "--store-id", "s1", "--kind", "utterance",
                  "--payload", '{"corrects":"s1:9"}')
    assert (rc, out["verdict"]) == (1, "UNKNOWN_CORRECTS_TARGET")
    for argv in (["append", "--root", R, "--store-id", "s1", "--kind", "utterance", "--payload", "{not json"],
                 ["append", "--root", R, "--store-id", "s1", "--kind", "bogus", "--payload", "{}"],
                 ["create", "--store-id", "s9", "--owner", "o"],                       # no --root
                 ["release", "--root", R, "--store-id", "s1"],                        # no --confirm
                 ["attach", "--root", R],                                              # neither id nor file
                 ["attach", "--root", R, "--store-id", "s1", "--file", "x"],          # both
                 ["consent", "--root", R, "--store-id", "s1", "--promote", "maybe"]):
        rc, lines, err = run(capsys, *argv)
        assert rc == 2 and lines == [] and "error" in err, argv


def test_refused_release_and_unknown_operations_write_nothing(tmp_path, capsys):
    R = str(tmp_path / "R")
    one(capsys, "create", "--root", R, "--store-id", "s1", "--owner", "o")
    def registry_rows():
        conn = sov._sov_struct_open(R)
        try:
            return len(sov._sov_registry(conn))
        finally:
            conn.close()
    n = registry_rows()
    one(capsys, "release", "--root", R, "--store-id", "s1", "--confirm", "S1")
    assert registry_rows() == n


def test_promotions_tells_zero_promotions_from_no_such_store_from_no_ledger(tmp_path, capsys):
    R = str(tmp_path / "R")
    one(capsys, "create", "--root", R, "--store-id", "s1", "--owner", "o")
    # a registered store with nothing promoted: a real answer, empty
    rc, out = one(capsys, "promotions", "--root", R, "--store-id", "s1")
    assert (rc, out["verdict"], out["structure"], out["promotions"]) == (0, "ANSWER", "PRESENT", [])
    # a mistyped store_id is not "0 promotions"
    for extra in ([], ["--all"]):
        rc, out = one(capsys, "promotions", "--root", R, "--store-id", "typo", *extra)
        assert (rc, out["verdict"], out["store_id"]) == (1, "UNKNOWN_STORE", "typo")
    # a root with no structure ledger says so, and the read creates nothing
    nowhere = tmp_path / "nowhere" / "deeper"
    rc, out = one(capsys, "promotions", "--root", str(nowhere))
    assert (rc, out["verdict"], out["structure"], out["promotions"]) == (0, "ANSWER", "ABSENT", [])
    rc, out = one(capsys, "promotions", "--root", str(nowhere), "--store-id", "s1")
    assert (rc, out["verdict"]) == (1, "UNKNOWN_STORE")
    assert not (tmp_path / "nowhere").exists()


# ------------------------------------------- the build that was already there
def test_sovereign_without_arguments_still_fails_the_old_way(capsys):
    rc, lines, err = run(capsys)
    assert rc == 2 and lines == []
    assert err.rstrip().splitlines()[-1] == "vera sovereign: error: the following arguments are required: --domain"


def test_sovereign_domain_keeps_its_old_answers(capsys):
    rc, out = one(capsys, "--domain", "x")
    assert (rc, out) == (1, {"verdict": "UNKNOWN_BAD_DOMAIN_SPEC", "got": "x", "want": "NAME=PATH"})
    rc, lines, _ = run(capsys, "--domain", "x=/nonexistent_dir_w4m")
    assert rc == 1 and "UNKNOWN_NO_DOMAINS" in "\n".join(lines)


def test_an_operation_together_with_domain_is_an_argument_error(tmp_path, capsys):
    cap = capsys
    cap.readouterr()
    with pytest.raises(SystemExit) as e:
        cli.main(["sovereign", "--domain", "x=y", "status", "--root", str(tmp_path)])
    assert e.value.code == 2
    assert "--domain belongs to the build" in cap.readouterr().err
    assert not (tmp_path / "structure.sqlite").exists()


def test_nested_options_do_not_overwrite_the_build_defaults():
    seen = {}

    def spy(args):
        seen.update(vars(args))
        return 0

    import unittest.mock as mock
    with mock.patch.object(cli, "cmd_sovereign", spy):
        cli.main(["sovereign", "status", "--root", "/nowhere"])
    assert seen["ask"] == [] and seen["name"] == "主権" and seen["out"] is None and seen["n_queries"] == 200
    assert seen["sovereign_op"] == "status" and seen["sov_root"] == "/nowhere"
    assert all(k.startswith("sov_") or k in {"cmd", "store", "fn", "domain", "ask", "questions", "n_queries",
                                               "name", "out", "sovereign_op", "sovereign_parser"}
               for k in seen), sorted(seen)


def test_the_entrance_is_found_by_the_capability_index():
    from verantyx import index
    res = index.search("記憶のソブリン", limit=200)
    assert res["verdict"] == "ANSWER"
    mine = sorted(h["name"] for h in res["hits"]
                  if h["kind"] == "command" and h["about"].startswith("記憶のソブリン:"))
    assert mine == ["append", "attach", "consent", "create", "detach", "events", "export",
                    "promote", "promotions", "release", "status"]


def test_the_same_ledger_read_through_the_entrance_and_python_agree(tmp_path, capsys):
    R = str(tmp_path / "R")
    sov.create(R, "s1", "owner-a")
    for phrase in ("a", "b", "a"):
        one(capsys, "append", "--root", R, "--store-id", "s1", "--kind", "utterance",
            "--payload", json.dumps({"phrase": phrase}))
    rc, lines, _ = run(capsys, "events", "--root", R, "--store-id", "s1")
    via_cli = [json.loads(x)["payload"] for x in lines]
    via_py = [e["payload"] for e in sov.open_ledger(R, "s1").events()]
    assert via_cli == via_py == [{"phrase": "a"}, {"phrase": "b"}, {"phrase": "a"}]
    assert P.candidates(sov.open_ledger(R, "s1"), "phrase")[0][:2] == ("a", 2)
