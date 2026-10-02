"""公開用の出力（publish）と漏れ検査（leakcheck）: 非公開の出力には問題の中身が入り、公開用には入らない。"""
import json
import sys
from pathlib import Path

import v2_util as U
from tools.bank_score import cli, leakcheck, publish, recount
from v2_util import b2_item, b3_item

TREE = Path(__file__).resolve().parents[2]
PHEN = "この問題は夜間の船着場の鐘の回数を答えさせるものです"
DOC = "船着場の鐘は、夜になると三回だけ鳴らされる。朝の鐘は鳴らされない。"
ANSWER = "夜は三回鳴ります。"
TABLE = {
    "q-bell": {"kind": "answer", "verdict": "ANSWER", "text": ANSWER, "evidence": DOC},
    "q-no": {"kind": "unknown", "verdict": "UNKNOWN_UNREAD", "text": "確認できません。"},
}
FAKE = ("import json, sys\nTABLE = %r\n"
        "def main(argv=None):\n    print(json.dumps(TABLE[sys.argv[-1]], ensure_ascii=False)); return 0\n"
        "if __name__ == '__main__':\n    raise SystemExit(main())\n") % (TABLE,)


def fake_tree(tmp_path):
    t = tmp_path / "tree" / "verantyx"
    t.mkdir(parents=True)
    (t / "__init__.py").write_text("")
    (t / "cli.py").write_text(FAKE)
    return tmp_path / "tree"


def make_run(tmp_path):
    a = b2_item("B2J-ZZ-01", query="q-bell", docs=[DOC], must_contain_any=[["三回"]], reference=ANSWER, evidence=[DOC],
                evidence_required=True)
    a["phenomenon"] = PHEN
    b = b2_item("B2J-ZZ-02", query="q-no", behavior="abstain", reference="確認できません。")
    b["phenomenon"] = PHEN + "その二"
    b["zz_日本語のキー"] = 1  # 非 ASCII の未知キーは公開側で <non-ascii> になる
    items = U.write_jsonl(tmp_path / "items.jsonl", [a, b])
    out = tmp_path / "private" / "B2"
    assert cli.main(["--profile", "v2", "--bank", "B2", "--items", str(items), "--tree", str(fake_tree(tmp_path)),
                     "--out", str(out), "--python", sys.executable]) == 0
    return items, out


def test_private_output_leaks_and_public_output_does_not_and_recount_matches(tmp_path, capsys):
    items, priv = make_run(tmp_path)
    assert leakcheck.main(["--items", str(items), "--scan", str(priv)]) == 1  # raw・phenomenon・observation に中身がある
    pub = tmp_path / "public" / "B2"
    assert publish.main([str(priv), str(pub)]) == 0
    assert leakcheck.main(["--items", str(items), "--scan", str(tmp_path / "public")]) == 0
    names = sorted(p.name for p in pub.rglob("*"))
    assert "raw" not in names
    rows = [json.loads(l) for l in (pub / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert all("phenomenon" not in r and "observation" not in r and "notes" not in r for r in rows)
    assert {r["id"] for r in rows} == {"B2J-ZZ-01", "B2J-ZZ-02"}
    by = {r["id"]: r for r in rows}
    assert by["B2J-ZZ-02"]["unknown_expect_keys"] == ["<non-ascii>"]
    assert by["B2J-ZZ-01"]["checks"]["must_contain_any"] == {"result": "PASS", "detail": {}}  # 必須語は残らない
    assert recount.main([str(pub)]) == 0  # 公開側の行だけから要約が再計算できる
    sp = json.loads((pub / "summary.json").read_text(encoding="utf-8"))
    assert sp == json.loads((priv / "summary.json").read_text(encoding="utf-8"))  # 消した欄は要約に使われていない
    assert sp["unknown_expect_keys"] == {"<non-ascii>": 1}
    meta = (pub / "run_meta.json").read_text(encoding="utf-8")
    assert PHEN not in meta and DOC not in meta
    assert PHEN not in (pub / "summary.md").read_text(encoding="utf-8")


def test_publish_redacts_non_ascii_reason_detail_and_checks_but_keeps_ascii_codes(tmp_path):
    row = {"id": "x", "line": 1, "bank": "B2", "lang": "ja", "category": "c", "difficulty": 1, "class": "unscorable",
           "class_ja": "採点不能", "reason": "ITEM_INVALID",
           "reason_detail": ["BAD_TYPE:expect.max_chars", "DUPLICATE_DOCUMENT_NAME:日本語の名前.txt", "日本語だけ",
                             "BAD_MUST_NOT[0]"],
           "entry": "e", "capability": None, "phenomenon": "中身", "observation": {"text": "中身"}, "raw": "中身",
           "checks": {"r": {"result": "UNJUDGED", "detail": {"reason": "NEEDS_READER", "found": ["中身"],
                                                            "surface_approx": "PASS"}},
                      "s": {"result": "FAIL", "detail": {"reason": "日本語の理由", "x": 1}}},
           "unknown_expect_keys": ["expect.k", "expect.日本語"], "notes": [{"n": "中身"}]}
    p = publish.public_row(row)
    assert p["reason_detail"] == ["BAD_TYPE:expect.max_chars", "DUPLICATE_DOCUMENT_NAME:<redacted>", "<redacted>",
                                  "BAD_MUST_NOT[0]"]
    assert p["checks"]["r"] == {"result": "UNJUDGED", "detail": {"reason": "NEEDS_READER", "surface_approx": "PASS"}}
    assert p["checks"]["s"] == {"result": "FAIL", "detail": {"reason": "<redacted>"}}
    assert p["unknown_expect_keys"] == ["expect.k", "<non-ascii>"]
    assert not {"phenomenon", "observation", "raw", "notes"} & set(p)


def test_publish_refuses_when_public_summary_differs_from_private(tmp_path, monkeypatch):
    items, priv = make_run(tmp_path)
    s = json.loads((priv / "summary.json").read_text(encoding="utf-8"))
    s["total"] += 1  # 非公開側の保存値を壊す → 再計算と一致しない
    (priv / "summary.json").write_text(json.dumps(s), encoding="utf-8")
    assert publish.main([str(priv), str(tmp_path / "public" / "B2")]) == 1


def test_leakcheck_windows_short_strings_and_identifier_exclusion(tmp_path):
    items = tmp_path / "items.jsonl"
    long_s = "あいうえおかきくけこさしすせそ"  # 15 字: 12 字の窓すべて
    items.write_text(json.dumps({"id": "i1", "lang": "ja", "brief": long_s, "materials": ["八字の短い語です", "FIELD_ID_NAME"],
                                 "expect": {}}, ensure_ascii=False) + "\n", encoding="utf-8")
    scan = tmp_path / "scan"
    scan.mkdir()
    (scan / "a.md").write_text("関係ない文。うえおかきくけこさしすせ。", encoding="utf-8")  # 窓の一部（12 字）に当たる
    (scan / "b.md").write_text("八字の短い語です と FIELD_ID_NAME と 十一字未満のあいうえお", encoding="utf-8")
    (scan / "c.md").write_text("あいうえおかきくけこ（11 字だけ）", encoding="utf-8")  # 12 字未満は窓にならない
    f, n = leakcheck.scan([str(items)], [], [str(scan)], [])
    hits = {(Path(x["file"]).name, x["id"]) for x in f}
    assert ("a.md", "i1") in hits and ("b.md", "i1") in hits and not any(h[0] == "c.md" for h in hits)
    assert all(x["field"] in ("brief", "materials") for x in f)  # 識別子（FIELD_ID_NAME）は照合語にならない
    # 除外（--exclude）は走査しない
    f2, _ = leakcheck.scan([str(items)], [], [str(scan)], [str(scan / "a.md"), str(scan / "b.md")])
    assert f2 == []
    # 出力に照合語そのものを書かない
    rc = leakcheck.main(["--items", str(items), "--scan", str(scan)])
    assert rc == 1


def test_leakcheck_scans_json_string_values_even_when_escaped(tmp_path):
    items = tmp_path / "items.jsonl"
    items.write_text(json.dumps({"id": "i1", "brief": "エスケープされた長い問題文の一部です", "expect": {}}, ensure_ascii=False) + "\n",
                     encoding="utf-8")
    scan = tmp_path / "scan"
    scan.mkdir()
    (scan / "x.json").write_text(json.dumps({"k": "エスケープされた長い問題文の一部です"}, ensure_ascii=True), encoding="utf-8")
    f, _ = leakcheck.scan([str(items)], [], [str(scan)], [])
    assert len(f) == 1 and f[0]["id"] == "i1"


def test_publish_refuses_to_delete_a_non_empty_directory_that_is_not_a_previous_publish_output(tmp_path):
    from tools.bank_score import publish
    priv = tmp_path / "priv"
    priv.mkdir()
    (priv / "results.jsonl").write_text("", encoding="utf-8")
    (priv / "run_meta.json").write_text("{}", encoding="utf-8")
    other = tmp_path / "somebody_elses_dir"
    other.mkdir()
    (other / "notes.txt").write_text("消えてはいけない", encoding="utf-8")
    assert publish.publish(priv, other) == 2
    assert (other / "notes.txt").read_text(encoding="utf-8") == "消えてはいけない"


def test_publish_refuses_when_the_public_path_is_a_regular_file(tmp_path):
    from tools.bank_score import publish
    priv = tmp_path / "priv"
    priv.mkdir()
    (priv / "results.jsonl").write_text("", encoding="utf-8")
    (priv / "run_meta.json").write_text("{}", encoding="utf-8")
    f = tmp_path / "a_file"
    f.write_text("消えてはいけない", encoding="utf-8")
    assert publish.publish(priv, f) == 2
    assert f.read_text(encoding="utf-8") == "消えてはいけない"
