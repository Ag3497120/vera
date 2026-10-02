"""Vera が実際に答えた場合の経路（答え・棄権・型の無い結果・異常終了）を、ツリー内の偽 verantyx で通す。

本物の Vera はほぼ全問を棄権するので、答えた観測に採点規則が当たる経路は偽ツリーでしか通せない。
偽ツリーは --tree の配下にあるので出自検査には通る（ツリー外ではない）。
"""
import json
import sys
from pathlib import Path

from tools.bank_score import cli

TABLE = {
    "q-correct": {"kind": "answer", "verdict": "ANSWER", "text": "月曜日です。", "evidence": [{"e": 1}]},
    "q-wrong": {"kind": "answer", "verdict": "ANSWER", "text": "火曜日です。", "evidence": [{"e": 1}]},
    "q-noevidence": {"kind": "answer", "verdict": "ANSWER", "text": "月曜日です。", "evidence": [], "sources": []},
    "q-abstain": {"kind": "unknown", "verdict": "UNKNOWN_UNREAD", "text": "この要求を裏づける導出を確認できません。"},
    "q-should-abstain-but-answers": {"kind": "answer", "verdict": "ANSWER", "text": "断定します。"},
    "q-should-abstain-and-does": {"kind": "unknown", "verdict": "UNKNOWN_NO_EVIDENCE", "text": ""},
    "q-label-notindocs": {"kind": "unknown", "verdict": "NOT_IN_DOCS", "text": ""},
    "q-weird": {"kind": "mystery", "verdict": "WEIRD", "text": "?"},
    "q-created": {"kind": "created", "verdict": "CREATED", "created": True, "text": "候補です。"},
    "q-notcreated": {"kind": "answer", "verdict": "ANSWER", "text": "候補です。"},
    "q-social": {"kind": "social", "text": "こんにちは"},
}
FAKE_CLI = (
    "import json, sys\n"
    f"TABLE = {TABLE!r}\n"
    "def main(argv=None):\n"
    "    q = sys.argv[-1]\n"
    "    if q == 'q-crash':\n"
    "        sys.exit(2)\n"
    "    if q == 'q-nojson':\n"
    "        print('hello'); return 0\n"
    "    print(json.dumps(TABLE[q], ensure_ascii=False)); return 0\n"
    "if __name__ == '__main__':\n"
    "    raise SystemExit(main())\n"
)


def fake_tree(tmp_path: Path) -> Path:
    t = tmp_path / "tree" / "verantyx"
    t.mkdir(parents=True)
    (t / "__init__.py").write_text("")
    (t / "cli.py").write_text(FAKE_CLI)
    return tmp_path / "tree"


def b2(id_, query, expect):
    return {"id": id_, "lang": "ja", "category": "c", "phenomenon": "p", "difficulty": 1,
            "turns": [{"role": "user", "text": query}], "expect": expect, "rationale": "r"}


def b3(id_, brief, expect):
    return {"id": id_, "lang": "ja", "category": "c", "phenomenon": "p", "difficulty": 1, "brief": brief,
            "expect": expect, "rationale": "r"}


def run(bank, items, tmp_path):
    p = tmp_path / "items.jsonl"
    p.write_text("\n".join(json.dumps(i, ensure_ascii=False) for i in items) + "\n", encoding="utf-8")
    out = tmp_path / "out"
    code = cli.main(["--bank", bank, "--items", str(p), "--tree", str(fake_tree(tmp_path)), "--out", str(out),
                     "--python", sys.executable])
    assert code == 0
    rows = [json.loads(l) for l in (out / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    return {r["id"]: r for r in rows}, out


def test_b2_answers_abstains_and_typed_errors_are_classified_from_types(tmp_path):
    ans = {"behavior": "answer", "must_contain_any": [["月曜"]], "must_not_contain": ["火曜"]}
    items = [
        b2("correct", "q-correct", ans),
        b2("wrong", "q-wrong", ans),
        b2("noevidence", "q-noevidence", dict(ans, evidence_required=True)),
        b2("over", "q-abstain", ans),
        b2("false", "q-should-abstain-but-answers", {"behavior": "abstain"}),
        b2("right-abstain", "q-should-abstain-and-does", {"behavior": "abstain"}),
        b2("label", "q-label-notindocs", {"behavior": "answer", "reference": "NOT_IN_DOCS"}),
        b2("label-but-expected-abstain", "q-label-notindocs", {"behavior": "abstain", "reference": "NOT_IN_DOCS"}),
        b2("weird", "q-weird", ans),
        b2("crash", "q-crash", ans),
        b2("nojson", "q-nojson", ans),
        b2("social-ok", "q-social", {"behavior": "social", "must_contain_any": [["こんにちは"]]}),
    ]
    rows, out = run("B2", items, tmp_path)
    got = {k: (v["class"], v["reason"]) for k, v in rows.items()}
    assert got == {
        "correct": ("correct", None),
        "wrong": ("wrong", None),
        "noevidence": ("wrong", None),
        "over": ("over_abstain", None),
        "false": ("false_compliance", None),
        "right-abstain": ("correct_abstain", None),
        "label": ("correct", None),  # 文のチェックでは NOT_IN_DOCS は未記載というラベルの回答
        "label-but-expected-abstain": ("correct_abstain", None),  # 期待が棄権なら NOT_IN_DOCS は棄権のまま
        "weird": ("runtime_error", "UNMAPPED_RESULT_TYPE"),
        "crash": ("runtime_error", "NONZERO_EXIT"),
        "nojson": ("runtime_error", "NOT_JSON"),
        "social-ok": ("correct", None),
    }
    summ = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summ["runtime_error_breakdown"] == {"NONZERO_EXIT": 1, "NOT_JSON": 1, "UNMAPPED_RESULT_TYPE": 1}
    assert summ["headline"]["false_compliance_rate"]["all"] == round(1 / 12, 6)
    assert rows["correct"]["observation"]["argv"] == ["ask", "--mode", "round5", "--", "q-correct"]
    assert rows["correct"]["entry"] == "cli-ask-round5"
    assert (out / "raw" / "0001_correct.json").is_file()


def test_b3_constructed_declaration_comes_from_the_type_not_the_text(tmp_path):
    exp = {"behavior": "generate", "outside": "constructed_only", "constraints": {"must_not_contain": ["公式"]}}
    rows, _ = run("B3", [b3("declared", "q-created", exp), b3("undeclared", "q-notcreated", exp)], tmp_path)
    assert rows["declared"]["class"] == "correct"
    assert rows["undeclared"]["class"] == "wrong"
    assert rows["undeclared"]["checks"]["declared_constructed"]["result"] == "FAIL"
