"""S7: ツリー外の verantyx を読んだら採点を無効にして止まる。本物のツリーでは出自が全部ツリー内。"""
import json
import sys
from pathlib import Path

from tools.bank_score import cli
from tools.bank_score.runner import Session

TREE = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"


def make_fake_tree(tmp_path: Path) -> Path:
    """tree/verantyx は __path__ に外部の verantyx を足す。cli.py は外にあって型つき JSON を返すだけ。"""
    outside = tmp_path / "outside" / "verantyx"
    outside.mkdir(parents=True)
    (outside / "__init__.py").write_text("")
    (outside / "cli.py").write_text(
        "import json\n"
        "def main(argv=None):\n"
        "    print(json.dumps({'kind': 'answer', 'verdict': 'ANSWER', 'text': 'x'}))\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n")
    fake = tmp_path / "fake_tree" / "verantyx"
    fake.mkdir(parents=True)
    (fake / "__init__.py").write_text(f"__path__.append({str(outside)!r})\n")
    return tmp_path / "fake_tree"


def run_cli(tree: Path, out: Path, items: Path | None = None) -> int:
    return cli.main(["--bank", "B2", "--items", str(items or FIX / "B2" / "items.jsonl"), "--tree", str(tree),
                     "--out", str(out), "--python", sys.executable])


def test_provenance_fake_tree_reading_outside_verantyx_stops_with_exit_3(tmp_path, capsys):
    fake = make_fake_tree(tmp_path)
    out = tmp_path / "out"
    assert run_cli(fake, out) == 3
    inv = json.loads((out / "INVALID.json").read_text(encoding="utf-8"))
    assert inv["verdict"] == "INVALID_PROVENANCE"
    listed = json.dumps(inv["outside"], ensure_ascii=False)
    assert str(tmp_path / "outside") in listed or "outside" in listed
    assert any("cli" in o["module"] for o in inv["outside"])
    assert not (out / "summary.json").exists() and not (out / "summary.md").exists()
    assert not (out / "results.jsonl").exists()


def test_provenance_outside_detected_per_process_during_a_run(tmp_path):
    fake = make_fake_tree(tmp_path)
    sess = Session(sys.executable, str(fake), None, 60)
    try:
        r = sess.run_ask(1, ["ask", "--", "こんにちは"], [])
        assert r["stdout_json"]["text"] == "x"  # 外部の偽 cli が実行された
        assert sess.outside, "ツリー外の出自が検出されていない"
        assert any("outside" in loc for o in sess.outside for loc in o["locations"])
    finally:
        sess.close()


def test_provenance_tree_without_verantyx_is_invalid_exit_3(tmp_path):
    empty = tmp_path / "empty_tree"
    empty.mkdir()
    out = tmp_path / "out"
    assert run_cli(empty, out) == 3  # この venv では外部の editable verantyx が読まれる（または import 失敗）。どちらも無効
    inv = json.loads((out / "INVALID.json").read_text(encoding="utf-8"))
    assert inv["stage"] == "precheck"
    assert inv.get("outside") or inv["precheck"]["import_error"]
    assert not (out / "summary.json").exists()


def test_provenance_stale_outputs_are_removed_when_invalid(tmp_path):
    # 事前検査に通ったあとでツリー外が見つかった場合の後始末は InvalidRun の経路。ここでは古い出力が残らないことを確かめる
    fake = make_fake_tree(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    (out / "summary.json").write_text("{}")
    (out / "results.jsonl").write_text("")
    assert run_cli(fake, out) == 3
    assert not (out / "summary.json").exists() and not (out / "results.jsonl").exists()


def test_provenance_real_tree_all_modules_inside_and_recorded(tmp_path):
    sess = Session(sys.executable, str(TREE), None, 60)
    try:
        pre = sess.precheck()
        assert pre["outside"] == [] and pre["import_error"] is None and pre["modules"] > 0
        r = sess.run_ask(1, ["ask", "--", "こんにちは"], [])
        assert r["reason"] is None and isinstance(r["stdout_json"], dict)
        assert r["provenance"]["outside"] == [] and r["provenance"]["modules"] > 0
        assert sess.outside == [] and sess.processes_unverified == 0
    finally:
        sess.close()


def test_dash_leading_query_reaches_vera_as_a_query_thanks_to_double_dash(tmp_path):
    sess = Session(sys.executable, str(TREE), None, 60)
    try:
        r = sess.run_ask(1, ["ask", "--", "-5 と 3 の和は？"], [])
        assert r["reason"] is None and r["exit_code"] == 0 and isinstance(r["stdout_json"], dict)
        r2 = sess.run_ask(2, ["ask", "--mode", "round5", "--", "-5 と 3 の和は？"], [])
        assert r2["reason"] is None and isinstance(r2["stdout_json"], dict)
    finally:
        sess.close()


def test_child_environment_is_rebuilt_not_inherited(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/somewhere/else")
    monkeypatch.setenv("VERA_SECRET_LEAK", "1")
    sess = Session(sys.executable, str(TREE), None, 60)
    try:
        env = sess.env(sess.work / "prov" / "x.json")
        assert env["PYTHONPATH"] == str(TREE.resolve()) or env["PYTHONPATH"] == str(TREE)
        assert "VERA_SECRET_LEAK" not in env
        assert set(env) == {"PATH", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "HOME", "VERA_CORPUS_ROOT",
                            "BANK_SCORE_PROVENANCE", "LANG", "PYTHONIOENCODING"}
        assert env["HOME"].startswith(str(sess.work)) and env["VERA_CORPUS_ROOT"].startswith(str(sess.work))
    finally:
        sess.close()


def test_timeout_is_a_runtime_error_type_not_a_crash(tmp_path):
    slow = tmp_path / "slow_tree" / "verantyx"
    slow.mkdir(parents=True)
    (slow / "__init__.py").write_text("")
    (slow / "cli.py").write_text("import time\ntime.sleep(30)\n")
    sess = Session(sys.executable, str(tmp_path / "slow_tree"), None, 1.5)
    try:
        r = sess.run_ask(1, ["ask", "--", "x"], [])
        assert r["reason"] == "TIMEOUT" and r["stdout_json"] is None
    finally:
        sess.close()


def test_non_json_and_nonzero_exit_are_typed(tmp_path):
    t = tmp_path / "t" / "verantyx"
    t.mkdir(parents=True)
    (t / "__init__.py").write_text("")
    (t / "cli.py").write_text("print('plain text')\n")
    sess = Session(sys.executable, str(tmp_path / "t"), None, 30)
    try:
        assert sess.run_ask(1, ["ask", "--", "x"], [])["reason"] == "NOT_JSON"
    finally:
        sess.close()
    (t / "cli.py").write_text("import sys\nprint('{}')\nsys.exit(2)\n")
    sess = Session(sys.executable, str(tmp_path / "t"), None, 30)
    try:
        assert sess.run_ask(1, ["ask", "--", "x"], [])["reason"] == "NONZERO_EXIT"
    finally:
        sess.close()
