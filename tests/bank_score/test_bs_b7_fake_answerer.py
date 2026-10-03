"""B7（根拠の方針）を偽の答え手（`basis_policy.outcome` を返す偽の verantyx/cli.py）で通す。T2（9 類の分類）・T3（provenance）・
T6（表層ベースライン）と、要約・recount・再現性・入力の誤り。期待は fixtures/B7/expected.json（手で書いて凍結したもの）。

偽ツリーは --tree の配下にあるので出自検査には通る。偽の答え手は返す JSON に `_probe`（子に渡った argv・env・文書の中身・索引の全行）を
入れる（採点には使わない。採点器は実行の終わりに一時ディレクトリを消すので、子が出力に写すしか後から見る方法が無い）。
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

from tools.bank_score import cli, recount

FIX = Path(__file__).parent / "fixtures" / "B7"
ITEMS = [json.loads(l) for l in (FIX / "items.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
FAKE = json.loads((FIX / "fake_outputs.json").read_text(encoding="utf-8"))
EXPECTED = json.loads((FIX / "expected.json").read_text(encoding="utf-8"))
STRATS = ["b7_a_human_sources", "b7_b_human_present", "b7_c_kind_then_a", "b7_d_always_abstain",
          "b7_e_reference_over_c"]

FAKE_CLI = (
    "import json, os, sqlite3, sys\n"
    f"TABLE = {FAKE!r}\n"
    "def main(argv=None):\n"
    "    a = sys.argv[1:]\n"
    "    spec = TABLE[a[-1]]\n"
    "    if '_exit' in spec:\n"
    "        sys.exit(spec['_exit'])\n"
    "    doc = None\n"
    "    if '--document' in a:\n"
    "        doc = open(a[a.index('--document') + 1], encoding='utf-8').read()\n"
    "    idx = os.environ.get('VERA_P4_INDEX')\n"
    "    listing = sorted(os.listdir(idx)) if idx and os.path.isdir(idx) else None\n"
    "    rows = meta = None\n"
    "    db = os.path.join(idx, 'local.db') if idx else None\n"
    "    if db and os.path.isfile(db):\n"
    "        con = sqlite3.connect('file:%s?mode=ro' % db, uri=True)\n"
    "        rows = [list(r) for r in con.execute('SELECT * FROM rows')]\n"
    "        meta = [list(r) for r in con.execute('SELECT * FROM meta')]\n"
    "        con.close()\n"
    "    out = dict(spec)\n"
    "    out['_probe'] = {'argv': a, 'env': dict(os.environ), 'document_text': doc, 'p4_listing': listing,\n"
    "                     'p4_rows': rows, 'p4_meta': meta}\n"
    "    print(json.dumps(out, ensure_ascii=False))\n"
    "    return 0\n"
    "if __name__ == '__main__':\n"
    "    raise SystemExit(main())\n"
)


def fake_tree(base: Path) -> Path:
    t = base / "tree" / "verantyx"
    t.mkdir(parents=True)
    (t / "__init__.py").write_text("")
    (t / "cli.py").write_text(FAKE_CLI)
    return base / "tree"


def run_b7(base: Path, name: str = "out", extra: list[str] | None = None) -> tuple[int, Path]:
    base.mkdir(parents=True, exist_ok=True)
    tree = base / "tree"
    if not tree.exists():
        fake_tree(base)
    out = base / name
    code = cli.main(["--profile", "v2", "--bank", "B7", "--items", str(FIX / "items.jsonl"), "--tree", str(tree),
                     "--out", str(out), "--python", sys.executable, *(extra or [])])
    return code, out


@pytest.fixture(scope="module")
def run1(tmp_path_factory):
    base = tmp_path_factory.mktemp("b7run")
    code, out = run_b7(base)
    assert code == 0
    rows = [json.loads(l) for l in (out / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    return {"out": out, "base": base, "rows": {r["id"]: r for r in rows}, "order": [r["id"] for r in rows],
            "summary": json.loads((out / "summary.json").read_text(encoding="utf-8"))}


def raw_probe(out: Path, seq: int, id_: str) -> dict:
    p = out / "raw" / f"{seq:04d}_{cli._safe(id_)}.json"
    return json.loads(p.read_text(encoding="utf-8"))


# ---- T2 -----------------------------------------------------------------------------------------------
def test_fixture_has_enough_items_and_the_required_kinds():
    assert len(ITEMS) >= 12
    expects = {(i["expect"]["result"], i["lang"]) for i in ITEMS if i["id"] != "fx-ja-invalid"}
    for e in ("ANSWER_HUMAN_BASIS", "ANSWER_FORM_FROM_GENERATED", "CONSTRUCTED", "CONFIRM_REQUEST",
              "REFERENCE_GENERATED", "ABSTAIN"):
        assert (e, "ja") in expects and (e, "en") in expects, e
    assert sum(1 for i in ITEMS if not i["generated_snippets"]) >= 3
    assert len({i["request"] for i in ITEMS}) == len(ITEMS)
    assert {"fx-ja-content-fail", "fx-en-content-fail", "fx-ja-confirm-assertive"} <= {i["id"] for i in ITEMS}


def test_t2_every_row_matches_the_frozen_expectation(run1):
    rows = run1["rows"]
    assert run1["order"] == [i["id"] for i in ITEMS]
    for id_, exp in EXPECTED["items"].items():
        r = rows[id_]
        assert (r["class"], r["reason"], r["class_approx"]) == (exp["class"], exp["reason"], exp["class_approx"]), id_
        if "content_from_generated" in exp:
            assert r["checks"]["w3_content"]["detail"]["content_from_generated"] == exp["content_from_generated"], id_
    assert set(rows) == set(EXPECTED["items"])


def test_t2_named_cases(run1):
    rows = run1["rows"]
    for id_ in ("fx-ja-content-fail", "fx-en-content-fail"):
        assert rows[id_]["class"] == "wrong" and rows[id_]["reason"] == "W3_CONTENT_FROM_GENERATED"
        assert rows[id_]["checks"]["w3_content"]["detail"]["content_from_generated"]
    assert rows["fx-ja-confirm-assertive"]["reason"] == "W4_CONFIRM_ASSERTIVE"
    assert rows["fx-ja-human-from-form"]["class"] == "correct"  # E=ANSWER_HUMAN_BASIS, O=ANSWER_FORM_FROM_GENERATED
    assert rows["fx-ja-human-from-form"]["b7"]["outcome"] == "ANSWER_FORM_FROM_GENERATED"
    assert rows["fx-en-form-reversed"]["reason"] == "OUTCOME_NOT_EXPECTED"  # 逆は不可
    assert rows["fx-ja-confirm-product"]["class"] == "unscorable" and rows["fx-ja-confirm-product"]["class_approx"] == "correct"
    assert rows["fx-ja-confirm-unobserved"]["class"] == "correct"
    assert rows["fx-ja-crash"]["reason"] == "NONZERO_EXIT"
    assert rows["fx-ja-missing-absent"]["reason"] == rows["fx-en-missing-null"]["reason"] == "OUTCOME_MISSING"
    assert rows["fx-ja-invalid"]["reason"] == "ITEM_INVALID" and "b7" not in rows["fx-ja-invalid"]
    assert rows["fx-ja-invalid"]["reason_detail"] == ["BAD_VALUE:request_kind"]
    assert rows["fx-en-missing-null"]["checks"]["outcome"]["detail"] == {
        "kind": "OUTCOME_NULL", "policy_reason": "NO_CITED_SOURCES", "reason": "OUTCOME_MISSING"}
    assert rows["fx-ja-missing-absent"]["checks"]["outcome"]["detail"]["kind"] == "BASIS_POLICY_ABSENT"


def test_t2_classes_sum_and_misread_zero(run1):
    s = run1["summary"]
    assert s["total"] == len(ITEMS) and s["class_sum"] == s["total"]
    assert s["classes"]["misread"]["count"] == 0
    assert {k: v["count"] for k, v in s["classes"].items()} == EXPECTED["vera_classes"] | {
        "unreachable": 0, "misread": 0}
    assert s["approx"]["classes"] == EXPECTED["vera_classes_approx"]
    assert s["approx"]["class_sum"] == s["total"]
    assert s["profile"] == "v2" and s["bank"] == "B7"
    assert s["runtime_error_breakdown"] == {"NONZERO_EXIT": 1}
    assert s["unscorable_breakdown"] == {"ITEM_INVALID": 1, "JUDGE_UNAVAILABLE": 2, "OUTCOME_MISSING": 2}
    assert s["item_invalid_codes"] == {"BAD_VALUE:request_kind": 1}
    assert s["judge_unavailable_reasons"] == {"CONFIRM_TEXT_UNTERMINATED_TAIL": 1, "UNKNOWN_EXPECT_KEYS": 1}
    assert s["unknown_expect_keys"] == {"expect.extra_flag": 1}
    assert set(s["by_unit"]) == {f"g{n:02d}" for n in range(1, 11)}


# ---- 要約の見出し・by_expect・内訳 -------------------------------------------------------------------------
def test_headline_macro_recall_by_expect_and_breakdown(run1):
    s = run1["summary"]
    g = s["headline"]["generated_only_answer"]
    for k, v in EXPECTED["generated_only_answer"].items():
        assert g[k] == v, k
    assert g["condition"] and g["definition"]
    m = s["headline"]["macro_recall"]
    assert m["value"] == EXPECTED["macro_recall"] and m["correct_only"] == EXPECTED["macro_recall_correct_only"]
    assert m["coin_level"] == 0.357 and m["definition"] and m["coin_level_source"]
    assert sorted(m["expects_used"]) == sorted(EXPECTED["by_expect"])
    assert set(s["by_expect"]) == set(EXPECTED["by_expect"])  # 6 値すべての鍵
    for e, exp in EXPECTED["by_expect"].items():
        got = s["by_expect"][e]
        assert got["total"] == exp["total"] and got["recall"] == exp["recall"], e
        assert got["recall_correct_only"] == exp["recall_correct_only"], e
        assert got["observed_outcomes"] == exp["observed_outcomes"], e
        assert sum(got[k] for k in ("correct", "wrong", "misread", "over_abstain", "correct_abstain", "false_compliance",
                                    "unreachable", "runtime_error", "unscorable")) == got["total"]
    assert s["by_expect_excluded_item_invalid"] == 1
    assert s["b7"]["confirm_text"] == EXPECTED["confirm_text"]
    assert s["b7"]["outcome_missing"] == EXPECTED["outcome_missing"]
    assert s["b7"]["content_from_generated_rows"] == EXPECTED["content_from_generated_rows"]


# ---- T6 ---------------------------------------------------------------------------------------------
def test_t6_baselines_equal_hand_computed_values(run1):
    b = run1["summary"]["baselines"]
    assert list(b["strategies"]) == STRATS  # 既存の 6 戦略は B7 の要約に出ない
    for s in STRATS:
        e = b["strategies"][s]
        exp = EXPECTED["baselines"][s]
        for k, v in exp["classes"].items():
            assert e["classes"][k] == v, (s, k)
        assert sum(e["classes"][k] for k in ("correct", "wrong", "over_abstain", "correct_abstain", "unscorable",
                                              "misread", "false_compliance", "runtime_error", "unreachable")) == len(ITEMS)
        assert e["pass_rate"] == exp["pass_rate"] == round(exp["classes"]["correct"] / len(ITEMS), 6), s
        assert e["correct_rate"] == e["pass_rate"]  # correct_abstain を足さない
        assert e["macro_recall"] == exp["macro_recall"], s
        assert e["correct_abstain"] == exp["classes"]["correct_abstain"]
    assert [w["strategy"] for w in b["weak_fixture"]] == EXPECTED["weak_fixture"]
    assert b["threshold"] == 0.35 and "足さない" in b["pass_rate_definition"]
    assert b["strategies"]["b7_d_always_abstain"]["pass_rate"] == 0.0  # 全問棄権でも正答率は 0


def test_t6_strategy_rows_match_embedded_and_expected(run1):
    out, rows = run1["out"], run1["rows"]
    for s in STRATS:
        sr = [json.loads(l) for l in (out / "baselines" / s / "results.jsonl").read_text(encoding="utf-8").splitlines()]
        assert [r["id"] for r in sr] == [i["id"] for i in ITEMS]
        for r in sr:
            exp = EXPECTED["strategies"][s][r["id"]]
            assert r["class"] == exp["class"], (s, r["id"])
            if r["id"] == "fx-ja-invalid":
                assert r["reason"] == "ITEM_INVALID"
                continue
            assert r["observation"]["outcome"] == exp["outcome"], (s, r["id"])
            emb = rows[r["id"]]["b7"]["strategies"][s]
            assert (emb["outcome"], emb["class"]) == (exp["outcome"], exp["class"])
            assert emb["class"] == r["class"] and emb["class_approx"] == r["class_approx"]


def test_strategy_text_is_empty_and_no_confirm_text(run1):
    sr = [json.loads(l) for l in (run1["out"] / "baselines" / "b7_b_human_present" / "results.jsonl").read_text(
        encoding="utf-8").splitlines()]
    cr = [r for r in sr if r.get("observation", {}) and r["observation"].get("outcome") == "CONFIRM_REQUEST"]
    assert cr and all(r["observation"]["confirm_text"] is None and r["observation"]["text"] == "" for r in cr)
    # 戦略 (b) の CONFIRM_REQUEST は文が観測できないので誤答にも採点不能にもしない
    assert all(r["checks"]["w4_confirm_form"]["detail"]["reason"] == "CONFIRM_TEXT_NOT_OBSERVED" for r in cr)


# ---- T3: provenance --------------------------------------------------------------------------------------
def _expected_argv(it: dict, seq: int) -> list[str]:
    argv = ["--store", "store.json", "ask", "--mode", "round5"]
    if it["human_sources"]:
        argv += ["--document", f"<WORK>/docs/q{seq:04d}.txt"]
    argv += ["--request-kind", it["request_kind"]]
    if it["human_present"]:
        argv.append("--human-present")
    if it["show_reference"]:
        argv.append("--show-generated-reference")
    return argv + ["--", it["request"]]


def _valid_items():
    return [(seq, it) for seq, it in enumerate(ITEMS, start=1) if it["id"] not in ("fx-ja-invalid", "fx-ja-crash")]


def test_t3_child_argv_env_document_and_index(run1):
    out = run1["out"]
    paths = set()
    for seq, it in _valid_items():
        probe = raw_probe(out, seq, it["id"])["stdout_json"]["_probe"]
        # (a) argv は完全一致
        assert probe["argv"] == _expected_argv(it, seq), it["id"]
        # (b) env: 既存の 8 鍵（+ 親が VERA_PLACEMENT を持てばそれ）+ VERA_P4_INDEX の完全一致。
        #     macOS は子の環境に __CF_USER_TEXT_ENCODING を OS が足すので、__CF_ で始まる鍵だけは除いて比べる
        env = {k: v for k, v in probe["env"].items() if not k.startswith("__CF_")}
        want = {"PATH", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "HOME", "VERA_CORPUS_ROOT", "BANK_SCORE_PROVENANCE",
                "LANG", "PYTHONIOENCODING", "VERA_P4_INDEX"} | ({"VERA_PLACEMENT"} if os.environ.get("VERA_PLACEMENT") else set())
        assert set(env) == want, (it["id"], set(env) ^ want)
        assert env["PATH"] == os.environ.get("PATH", "")
        assert re.fullmatch(r"<WORK>/p4/q\d{4}", env["VERA_P4_INDEX"]) and env["VERA_P4_INDEX"] == f"<WORK>/p4/q{seq:04d}"
        paths.add(env["VERA_P4_INDEX"])
        # (c) 文書の中身
        want_doc = "\n".join(it["human_sources"]) + "\n" if it["human_sources"] else None
        assert probe["document_text"] == want_doc
        # (d) 索引: 生成の文が 1 本以上で local.db だけ、0 本なら空のディレクトリ（家族の db が無い）
        assert probe["p4_listing"] == (["local.db"] if it["generated_snippets"] else []), it["id"]
        if it["generated_snippets"]:
            assert [r[1] for r in probe["p4_rows"]] == it["generated_snippets"]
            assert all("generated" in r for r in probe["p4_rows"])
        else:
            assert probe["p4_rows"] is None
    assert len(paths) == len(_valid_items())  # VERA_P4_INDEX は問ごとに違う場所


def test_t3_nothing_from_the_question_metadata_reaches_the_child(run1):
    out = run1["out"]
    n = 0
    for seq, it in _valid_items():
        probe = raw_probe(out, seq, it["id"])["stdout_json"]["_probe"]
        env_values = [v for k, v in probe["env"].items() if k != "PATH" and not k.startswith("__CF_")]
        cols = [str(c) for r in (probe["p4_rows"] or []) for c in r] + [str(c) for r in (probe["p4_meta"] or []) for c in r]
        haystack = list(probe["argv"]) + env_values + [probe["document_text"] or ""] + cols
        ex = it["expect"]
        secrets = [it["category"], it["phenomenon"], it["rationale"], json.dumps(ex, ensure_ascii=False), ex["result"],
                   *ex["must_not"]]
        for sec in secrets:
            assert len(sec) >= 4
            for h in haystack:
                assert sec not in h, (it["id"], sec)
        # (f) lang は argv の要素・env の値に等しいものが無く、--lang も無い
        assert it["lang"] not in probe["argv"] and it["lang"] not in env_values and "--lang" not in probe["argv"]
        # (g) unit は argv・env の値に部分文字列として現れない
        assert not any(it["unit"] in h for h in list(probe["argv"]) + env_values), it["id"]
        n += 1
    assert n >= 30


def test_t3_run_meta_records_the_per_item_index_and_nothing_else_in_env(run1):
    meta = json.loads((run1["out"] / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["bank"] == "B7" and meta["entry"] == "cli-ask-round5-basis" and meta["profile"] == "v2"
    assert set(meta["child_env"]) == {"PATH", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "HOME", "VERA_CORPUS_ROOT",
                                      "BANK_SCORE_PROVENANCE", "LANG", "PYTHONIOENCODING"} | (
        {"VERA_PLACEMENT"} if os.environ.get("VERA_PLACEMENT") else set())
    assert "VERA_P4_INDEX" in meta["child_env_per_item"]
    assert meta["vera_calls"] == len(ITEMS) - 1  # ITEM_INVALID は Vera を呼ばない
    assert meta["provenance_total"]["outside_count"] == 0 and meta["provenance_total"]["processes_unverified"] == 0
    assert "--request-kind" in " ".join(meta["child_argv_template"])
    raw = raw_probe(run1["out"], 1, ITEMS[0]["id"])
    assert raw["b7_inputs"]["document"] == "<WORK>/docs/q0001.txt" and raw["b7_inputs"]["p4_index"] == "<WORK>/p4/q0001"
    assert raw["b7_inputs"]["p4_rows"] == 0 and len(raw["b7_inputs"]["document_sha256"]) == 64


def test_the_row_b7_block(run1):
    r = run1["rows"]["fx-ja-human"]
    b = r["b7"]
    assert (b["expect_result"], b["request_kind"], b["n_human_sources"], b["n_generated_snippets"], b["human_present"],
            b["show_reference"], b["generated_only"], b["outcome"]) == (
        "ANSWER_HUMAN_BASIS", "factual", 2, 0, False, False, False, "ANSWER_HUMAN_BASIS")
    assert set(b["strategies"]) == set(STRATS)
    assert run1["rows"]["fx-ja-crash"]["b7"]["outcome"] is None  # 観測が無い行
    assert run1["rows"]["fx-ja-crash"]["b7"]["generated_only"] is True
    assert run1["rows"]["fx-en-abstain-example-mixed"]["b7"]["generated_only"] is None  # 未決
    assert run1["rows"]["fx-ja-missing-absent"]["b7"]["outcome"] == "OUTCOME_MISSING"


# ---- 要約に問題の中身を出さない・recount・再現性 ---------------------------------------------------------------
def test_summary_has_no_question_contents(run1):
    text = (run1["out"] / "summary.json").read_text(encoding="utf-8") + (run1["out"] / "summary.md").read_text(encoding="utf-8")
    for it in ITEMS:
        for s in [it["request"], *it["human_sources"], *it["generated_snippets"]]:
            assert s not in text, s
    for toks in EXPECTED["items"].values():
        for t in toks.get("content_from_generated", []):
            if len(t) >= 3:
                assert t not in text, t
    for fake in FAKE.values():
        t = fake.get("text") if isinstance(fake, dict) else None
        if t and len(t) >= 8:
            assert t not in text


def test_recount_matches_for_b7(run1, capsys):
    assert recount.main([str(run1["out"])]) == 0
    assert "summary.json 一致 / summary.md 一致" in capsys.readouterr().out


def test_two_runs_give_identical_summaries(run1, tmp_path):
    code, out2 = run_b7(tmp_path)
    assert code == 0
    for name in ("summary.json", "summary.md"):
        assert (out2 / name).read_bytes() == (run1["out"] / name).read_bytes(), name


def test_summary_md_has_the_b7_sections(run1):
    md = (run1["out"] / "summary.md").read_text(encoding="utf-8")
    for needle in ("## B7: 根拠の方針", "generated_only_answer", "macro_recall", "0.357", "## 期待の型ごと（by_expect）",
                   "b7_e_reference_over_c", "ANSWER_FORM_FROM_GENERATED"):
        assert needle in md, needle
    assert "echo_input" not in md  # 既存の 6 戦略は B7 の表に出ない


# ---- 入力の誤り -------------------------------------------------------------------------------------------
def test_input_errors_exit_2(tmp_path, capsys):
    tree = fake_tree(tmp_path)
    base = ["--bank", "B7", "--items", str(FIX / "items.jsonl"), "--tree", str(tree), "--out", str(tmp_path / "o"),
            "--python", sys.executable]
    assert cli.main(base) == 2  # 既定の profile（w1s）は不可
    assert "B7 は --profile v2 だけ" in capsys.readouterr().err
    assert cli.main(["--profile", "w1s", *base]) == 2
    assert cli.main(["--profile", "v2", *base, "--frames", str(tmp_path)]) == 2
    assert cli.main(["--profile", "v2", *base, "--entry", "cli"]) == 2
    assert cli.main(["--profile", "v2", "--bank", "B7", "--items", str(tmp_path / "none.jsonl"), "--tree", str(tree),
                     "--out", str(tmp_path / "o2"), "--python", sys.executable]) == 2
    assert cli.main(["--profile", "v2", *base, "--entry", "cli-ask-round5-basis"]) == 0


def test_prepare_failure_makes_a_typed_runtime_error_without_calling_vera(tmp_path, monkeypatch):
    from tools.bank_score import runner
    monkeypatch.setattr(runner.Session, "prepare_b7", lambda self, seq, hs, gs: {"error": "B7_PREPARE_FAILED", "detail": "OSError"})
    items = tmp_path / "one.jsonl"
    items.write_text(json.dumps(ITEMS[0], ensure_ascii=False) + "\n", encoding="utf-8")
    tree = fake_tree(tmp_path)
    out = tmp_path / "out"
    assert cli.main(["--profile", "v2", "--bank", "B7", "--items", str(items), "--tree", str(tree), "--out", str(out),
                     "--python", sys.executable]) == 0
    row = json.loads((out / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert (row["class"], row["reason"], row["reason_detail"]) == ("runtime_error", "B7_PREPARE_FAILED", ["OSError"])
    assert json.loads((out / "run_meta.json").read_text(encoding="utf-8"))["vera_calls"] == 0
    assert row["b7"]["outcome"] is None
