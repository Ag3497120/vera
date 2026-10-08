"""W16-t6: the three extractors (V fixed sentences, a JSON, b regex) build the same claim objects (docs/ATTEST.md sections 2 and 4)."""
import json
import unicodedata

from verantyx import attest

SHA64 = "1a2b" * 16

TICKET = """報告本文

完了:
- 受入 T2-1: `pytest -q tests/test_w16t2_paths.py` を実行し、終了コード 0、出力 artifacts/w16-t2/t2_1.txt（sha256 1a2b…）。
- 変更: verantyx/doc_answer.py（sha256 …）、verantyx/cli.py（sha256 …）。
- 追加したテスト: tests/test_w16t2_paths.py の 12 件が通った。
"""


def _sig(c):
    return {k: v for k, v in c.items() if k not in ("line", "text")}


def test_ticket_example_is_read_with_abbreviated_sha_kept():
    claims, found = attest.parse_v(TICKET)
    assert found
    assert [c["kind"] for c in claims] == ["acceptance", "changed", "changed", "tests_added"]
    a = claims[0]
    assert (a["id"], a["cmd"], a["exit"]) == ("T2-1", "pytest -q tests/test_w16t2_paths.py", 0)
    assert a["out"]["path"] == "artifacts/w16-t2/t2_1.txt" and a["out"]["sha"].rstrip(".") == "1a2b"
    assert [(c["path"], c["sha"]) for c in claims[1:3]] == [("verantyx/doc_answer.py", "..."), ("verantyx/cli.py", "...")]
    assert (claims[3]["path"], claims[3]["count"]) == ("tests/test_w16t2_paths.py", 12)


def test_ticket_example_with_full_sha_and_halfwidth_forms():
    full = TICKET.replace("1a2b…", SHA64)
    half = full.replace("（", "(").replace("）", ")").replace("：", ":")
    for text in (full, half, full.replace("。\n", "\n")):
        claims, _ = attest.parse_v(text)
        assert claims[0]["out"]["sha"] == SHA64 and len(claims) == 4


def test_off_form_lines_are_counted_not_dropped():
    text = "完了:\n- 受入 T1-1: `pytest -q tests/a.py` を実行し、終了コード 0。\n- すべて完了しました\n- 変更: a.py\n"
    claims, found = attest.parse_v(text)
    assert found and [c["kind"] for c in claims] == ["acceptance", "offform", "offform"]
    assert [c["line"] for c in claims] == [2, 3, 4]


def test_section_ends_at_non_bullet_and_no_section_is_reported():
    text = "完了:\n- 追加したテスト: tests/a.py の 1 件が通った。\n\n- 追加したテスト: tests/b.py の 2 件が通った。\n"
    claims, _ = attest.parse_v(text)
    assert len(claims) == 1
    claims, found = attest.parse_v("テストは通りました。完了です。\n")
    assert claims == [] and not found


def test_json_block_without_attest_key_is_ignored_and_broken_one_is_offform():
    ok = '```json\n{"foo": 1}\n```\n'
    assert attest.parse_a(ok) == []
    broken = '```json\n{"attest": 1, "claims": [\n```\n'
    got = attest.parse_a(broken)
    assert [c["kind"] for c in got] == ["offform"]
    unknown = '```json\n{"attest": 1, "claims": [{"kind": "magic"}]}\n```\n'
    assert [c["kind"] for c in attest.parse_a(unknown)] == ["offform"]


def test_V_and_a_make_the_same_claim_set():
    out = {"attest": 1, "claims": [
        {"kind": "acceptance", "id": "T2-1", "command": "pytest -q tests/a.py", "exit_code": 0, "output": {"path": "o/x.txt", "sha256": SHA64}},
        {"kind": "changed", "files": [{"path": "p/a.py", "sha256": SHA64}, {"path": "p/b.py", "sha256": SHA64}]},
        {"kind": "tests_added", "path": "tests/a.py", "count": 3, "passed": True},
        {"kind": "number", "id": "T3", "text": "12 passed", "path": "o/x.txt"}]}
    lines = ["完了:", "- 受入 T2-1: `pytest -q tests/a.py` を実行し、終了コード 0、出力 o/x.txt（sha256 %s）。" % SHA64,
             "- 変更: p/a.py（sha256 %s）、p/b.py（sha256 %s）。" % (SHA64, SHA64), "- 追加したテスト: tests/a.py の 3 件が通った。", "- 数値 T3: 「12 passed」は o/x.txt にある。"]
    report = "\n".join(lines) + "\n```json\n" + json.dumps(out, ensure_ascii=False) + "\n```\n"
    v, _ = attest.parse_v(report)
    a = attest.parse_a(report)
    assert len(v) == len(a) == 5
    assert [_sig(x) for x in v] == [_sig(x) for x in a]


def test_b_reads_free_text_with_its_pre_registered_rules():
    text = ("`pytest -q tests/test_x.py` は終了コード 0 だった。\n"
            "tests/test_x.py は 7 passed。\n"
            "出力 out/a.txt (sha256 %s)\n"
            "「12 件を処理」は out/a.txt にある。\n" % SHA64)
    kinds = [c["kind"] for c in attest.parse_b(text)]
    assert kinds == ["acceptance", "tests_added", "file_sha", "number"]
    assert attest.parse_b("何も申告しない文章です。\n") == []


def test_nfkc_is_all_the_normalisation_there_is():
    s = "ａｂｃ１２３（x）"
    assert attest.nfkc(s) == unicodedata.normalize("NFKC", s)


def test_b_does_not_pair_several_paths_or_counts_on_one_line():
    """amendment 1 (docs/ATTEST.md): a line with two test paths, or two counts, is a tie: an ambiguous claim (testimony), never a chosen pair."""
    from verantyx.attest import Verifier
    for line in ("pytest tests/a.py tests/b.py は 339 passed", "tests/a.py は 3 passed、1 passed の別実行もある"):
        claims = attest.parse_b(line + "\n")
        assert len(claims) == 1 and claims[0].get("ambiguous") is True
    f = Verifier("/nonexistent").verify(claims[0])
    assert [(x["mark"], x["reason"]) for x in f] == [("TESTIMONY", "AMBIGUOUS_CLAIM")]
    one = attest.parse_b("tests/a.py は 3 passed\n")
    assert one[0]["count"] == 3 and not one[0].get("ambiguous")
