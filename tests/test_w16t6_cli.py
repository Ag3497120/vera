"""W16-t6: `vera attest` reaches through verantyx.cli.main; exit codes 0/1/2/3/4 and --record (docs/ATTEST.md)."""
import hashlib
import json

from verantyx import cli
from verantyx.testimony_ledger import TestimonyLedger


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def setup(tmp_path, claimed):
    (tmp_path / "o").mkdir(exist_ok=True)
    (tmp_path / "o" / "x.txt").write_text("hello\n")
    r = tmp_path / "report.md"
    r.write_text("本文\n\n完了:\n- 変更: o/x.txt（sha256 %s）。\n" % claimed)
    return r


def test_exit_0_when_everything_is_recorded(tmp_path, capsys):
    r = setup(tmp_path, sha("hello\n"))
    r.write_text("完了:\n- 数値 T1: 「6 文字」は o/x.txt にある。\n- 数値 T2: 「hello」は o/x.txt にある。\n")
    (tmp_path / "o" / "x.txt").write_text("6 chars hello\n")
    assert cli.main(["attest", str(r), "--tree", str(tmp_path)]) == 4          # T2 has no number: testimony
    r.write_text("完了:\n- 数値 T1: 「6 文字」は o/x.txt にある。\n")
    assert cli.main(["attest", str(r), "--tree", str(tmp_path)]) == 0
    assert "記録" in capsys.readouterr().out


def test_exit_1_on_mismatch_and_4_on_testimony_only(tmp_path, capsys):
    r = setup(tmp_path, "0" * 64)
    assert cli.main(["attest", str(r), "--tree", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "食い違い" in out and "0" * 64 in out and sha("hello\n") in out        # claimed and actual are shown side by side
    r2 = setup(tmp_path, sha("hello\n"))
    assert cli.main(["attest", str(r2), "--tree", str(tmp_path)]) == 4            # sha is right but 'changed' has no base
    free = tmp_path / "free.md"
    free.write_text("テストは通りました。\n")
    assert cli.main(["attest", str(free), "--tree", str(tmp_path)]) == 4
    assert "NO_COMPLETION_SECTION" in capsys.readouterr().out


def test_exit_2_on_bad_arguments(tmp_path, capsys):
    assert cli.main(["attest", str(tmp_path / "missing.md"), "--tree", str(tmp_path)]) == 2
    r = setup(tmp_path, "0" * 64)
    assert cli.main(["attest", str(r), "--tree", str(tmp_path / "nodir")]) == 2


def test_record_writes_attestation_rows_and_no_record_writes_nothing(tmp_path, capsys):
    r = setup(tmp_path, "0" * 64)
    led = tmp_path / "led.jsonl"
    assert cli.main(["attest", str(r), "--tree", str(tmp_path)]) == 1
    assert not led.exists()
    assert cli.main(["attest", str(r), "--tree", str(tmp_path), "--record", str(led), "--extractor", "V"]) == 1
    rows = TestimonyLedger(led).entries()
    att = [e for e in rows if e["type"] == "attestation"]
    assert len(att) == 1 and att[0]["mark"] == "MISMATCH" and att[0]["reason"] == "SHA_DIFFERS" and att[0]["extractor"] == "V"
    assert att[0]["report"]["sha256"] == hashlib.sha256(r.read_bytes()).hexdigest()


def test_exit_3_when_the_record_ledger_is_broken_and_nothing_is_written(tmp_path, capsys):
    r = setup(tmp_path, "0" * 64)
    led = tmp_path / "led.jsonl"
    TestimonyLedger(led)
    lines = led.read_text().splitlines()
    led.write_text(lines[0].replace("verantyx", "tampered") + "\n")
    before = led.read_bytes()
    assert cli.main(["attest", str(r), "--tree", str(tmp_path), "--record", str(led)]) == 3
    assert led.read_bytes() == before


def test_json_output_shape(tmp_path, capsys):
    r = setup(tmp_path, "0" * 64)
    cli.main(["attest", str(r), "--tree", str(tmp_path), "--json"])
    d = json.loads(capsys.readouterr().out)
    assert d["schema"] == "verantyx.attest/1" and d["exit_code"] == 1
    f = d["extractors"]["V"]["claims"][0]["facts"][0]
    assert f["claimed"] == "0" * 64 and f["actual"] == sha("hello\n") and f["evidence"]["path"] == "o/x.txt"
