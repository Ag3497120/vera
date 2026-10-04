"""items.jsonl のキーのパスと型の頻度を数える（W1-s2。ずれ一覧の再計算用）。

値は出さない。ただし閉じた一覧を持つ欄（behavior・state・kind・decision・outside・form.type・態・関係の種類など）だけは
値の頻度を出す。自由文の値、`form.cells` の子のキー（行の値・列名）は出さない（`<row>`・`<col>` として数える）。
標準ライブラリだけ。使い方: python -m tools.bank_score.survey <items.jsonl> [--quarantine <q.json>]
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

# 値の頻度を出してよい（閉じた一覧の）パス。リストは `[]` で表す。
CLOSED_VALUE_PATHS = (
    "lang", "difficulty",
    "expect.behavior", "expect.state", "expect.state[]", "expect.outside", "expect.kind", "expect.decision",
    "expect.label", "expect.readable", "expect.evidence_required", "expect.reply_lang", "expect.polarity",
    "expect.constraints.language", "expect.constraints.register", "expect.constraints.must_not_equal",
    "expect.constraints.form.type", "expect.constraints.form.script", "expect.constraints.form.alternate",
    "expect.constraints.must_relate[].rel", "expect.constraints.must_not_relate[].rel",
    "expect.constraints.must_express[].polarity", "expect.constraints.new_content_words.allowed",
    "expect.clauses[].polarity", "expect.clauses[].tense", "expect.clauses[].modality", "expect.clauses[].voice",
    "expect.clauses[].comparison", "expect.relations[].type", "expect.relations[].type[]",
    "expect.format.polite", "expect.format.plain", "expect.format.bullets", "expect.format.target_lang",
    "expect.escalate_type", "expect.trap", "expect.polarity",
    "expect.must_not[].readable", "expect.must_not[].field", "expect.must_not[].quantifier",
    "expect.vocab.out_of_vocabulary",
    "expect.surface.recommended_marker", "expect.surface.protected_keyword_permitted",
    "expect.surface.escalate_cue_answerable",
)
# 値ではなくキー名の頻度を出してよいパス（役割名・量化の対象・ラベルの鍵など、閉じた集合のキー）
CLOSED_KEY_PATHS = ("expect.clauses[].roles", "expect.clauses[].quantifiers", "expect.format", "expect.choice",
                    "expect.surface", "expect.vocab", "expect.constraints")
CELLS_PATH = "expect.constraints.form.cells"


def _tname(v: object) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "str"
    if isinstance(v, list):
        return "list"
    return "dict"


def _walk(v: object, path: str, types: Counter, values: dict[str, Counter]) -> None:
    types[(path, _tname(v))] += 1
    if path in CLOSED_VALUE_PATHS:
        if isinstance(v, (str, int, bool)) or v is None:
            values.setdefault(path, Counter())[json.dumps(v, ensure_ascii=False)] += 1
    if isinstance(v, dict):
        if path == CELLS_PATH:  # 行の値・列名は問題の中身
            for row, cols in v.items():
                types[(path + ".<row>", _tname(cols))] += 1
                if isinstance(cols, dict):
                    for _col, cands in cols.items():
                        types[(path + ".<row>.<col>", _tname(cands))] += 1
            return
        if path == "expect.clauses[].roles":
            for k, x in v.items():  # 役割名は閉じた一覧なのでキー名を値として数える
                values.setdefault("expect.clauses[].roles(keys)", Counter())[k] += 1
                _walk(x, "expect.clauses[].roles.<role>", types, values)
            return
        if path == "expect.clauses[].quantifiers":
            for k, x in v.items():
                values.setdefault("expect.clauses[].quantifiers(keys)", Counter())[k] += 1
                _walk(x, "expect.clauses[].quantifiers.<role>", types, values)
            return
        for k, x in v.items():
            _walk(x, f"{path}.{k}" if path else k, types, values)
    elif isinstance(v, list):
        for x in v:
            _walk(x, path + "[]", types, values)


def _must_not_shapes(items: list[dict]) -> Counter:
    c: Counter = Counter()
    for it in items:
        mn = (it.get("expect") or {}).get("must_not")
        if isinstance(mn, list):
            for m in mn:
                c[",".join(sorted(m)) if isinstance(m, dict) else _tname(m)] += 1
    return c


def survey(items_path: str) -> dict:
    items = []
    bad_lines = 0
    for ln in Path(items_path).read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            o = json.loads(ln)
        except json.JSONDecodeError:
            bad_lines += 1
            continue
        if isinstance(o, dict):
            items.append(o)
    types: Counter = Counter()
    values: dict[str, Counter] = {}
    for it in items:
        for k, v in it.items():
            _walk(v, k, types, values)
    by_path: dict[str, dict[str, int]] = {}
    for (p, t), n in types.items():
        by_path.setdefault(p, {})[t] = n
    return {
        "n_items": len(items), "bad_json_lines": bad_lines,
        "paths": {p: dict(sorted(d.items())) for p, d in sorted(by_path.items())},
        "closed_values": {p: dict(sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))) for p, c in sorted(values.items())},
        "must_not_shapes": dict(sorted(_must_not_shapes(items).items(), key=lambda kv: (-kv[1], kv[0]))),
    }


def quarantine_shape(path: str) -> dict:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(d, list):
        return {"shape": "list", "n": len(d), "entry_types": dict(Counter(_tname(x) for x in d))}
    keys = {k: _tname(v) for k, v in d.items()}
    out: dict = {"shape": "dict", "keys": keys}
    for k in ("quarantined", "ids"):
        if isinstance(d.get(k), list):
            out[f"{k}_n"] = len(d[k])
            out[f"{k}_entry_types"] = dict(Counter(_tname(x) for x in d[k]))
    return out


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("使い方: python -m tools.bank_score.survey <items.jsonl> [--quarantine <q.json>]", file=sys.stderr)
        return 2
    res = survey(argv[0])
    if "--quarantine" in argv:
        res["quarantine"] = quarantine_shape(argv[argv.index("--quarantine") + 1])
    print(json.dumps(res, ensure_ascii=False, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
