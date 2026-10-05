"""K653: 基点と新しい木の k287_serve.py の出力（310 行）を行ごとに比べる。変わってよい行 = 基点の行で layer 0・FACTUAL・LLM を呼んだ・reading が QUESTION_CROSS でない（quote_mode が真になる行）。
使い方: k653_compare.py BASE.jsonl NEW.jsonl"""
import json
import sys

FACTUAL = "factual"


def load(p):
    return [l.rstrip("\n") for l in open(p, encoding="utf-8")]


def may_change(row):
    res = row.get("res")
    if not res or row.get("layer") != 0:
        return False
    v = res["vera"]
    return v["request_kind"] == FACTUAL and v["llm"]["called"] is True and v["reading"]["type"] != "QUESTION_CROSS"


def main(a, b):
    A, B = load(a), load(b)
    print("rows base", len(A), "new", len(B))
    if len(A) != len(B):
        print("LENGTH_MISMATCH")
        return 1
    allowed = changed_allowed = other_changed = 0
    keys_only_added = 0
    bad = []
    for x, y in zip(A, B):
        rx, ry = json.loads(x), json.loads(y)
        if may_change(rx):
            allowed += 1
            if x != y:
                changed_allowed += 1
                if rx["id"] != ry["id"] or rx["layer"] != ry["layer"]:
                    bad.append(rx["id"])
                if "quote_check" in ry["res"]["vera"]:
                    keys_only_added += 1
        elif x != y:
            other_changed += 1
            bad.append(rx["id"])
    print("rows where change is allowed (layer 0, FACTUAL, LLM called, not QUESTION_CROSS):", allowed)
    print("  of which actually changed:", changed_allowed, "; of which carry vera.quote_check:", keys_only_added)
    print("rows outside that set:", len(A) - allowed)
    print("rows outside that set that changed (pass = 0):", other_changed)
    if bad:
        print("changed ids outside the set:", bad[:20])
    return 0 if other_changed == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
