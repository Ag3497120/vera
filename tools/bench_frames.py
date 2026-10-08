"""PREREGISTERED_2026-09-27_frames — run the sealed paraphrase bench."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from verantyx.frames import canonical, read  # noqa: E402

BENCH = Path.home() / "Projects" / "vera-corpus" / "benches" / (
    sys.argv[1] if len(sys.argv) > 1 else "paraphrase_heldout_raw.json")


def _c(key):
    # 追記2: participants compared by name without role words, both sides
    return (key[0], canonical(key[1]), canonical(key[2]), canonical(key[3]), key[4])


def k(s):
    f = read(s)
    return _c(f.key()) if f else None


def main() -> None:
    groups = json.loads(BENCH.read_text())["groups"]
    para_ok = para_n = con_ok = con_n = gold_ok = 0
    fails = []
    for g in groups:
        b = k(g["base"])
        gold = g["frame"]
        gk = _c((gold["predicate"], gold["agent"], gold["patient"], gold["recipient"], gold["negated"]))
        if b and (b[0], b[1], b[2], b[4]) == (gk[0], gk[1], gk[2], gk[4]):
            gold_ok += 1
        else:
            fails.append(("gold", g["base"], b, gold))
        for p in g["paraphrases"]:
            para_n += 1
            kp = k(p)
            if b and kp == b:
                para_ok += 1
            else:
                fails.append(("para", g["base"], p, b, kp))
        for c in g["contrasts"]:
            con_n += 1
            kc = k(c["sentence"])
            ok = False
            if b and kc:
                if c["change"] == "role_swap":
                    # any two roles exchanged, the third unchanged (追記1)
                    r_b, r_c = list(b[1:4]), list(kc[1:4])
                    ok = kc[0] == b[0] and kc[4] == b[4] and any(
                        r_c[x] == r_b[y] and r_c[y] == r_b[x] and r_b[x] != r_b[y]
                        and r_c[3 - x - y] == r_b[3 - x - y]
                        for x in range(3) for y in range(x + 1, 3))
                elif c["change"] == "negation":
                    ok = kc[:4] == b[:4] and kc[4] != b[4]
                else:
                    diff = sum(x != y for x, y in zip(kc[1:4], b[1:4]))
                    ok = kc[0] == b[0] and diff == 1 and kc[4] == b[4]
            if ok:
                con_ok += 1
            else:
                fails.append(("contrast", c["change"], g["base"], c["sentence"], b, kc))
    rep = {"groups": len(groups),
           "paraphrase_agree": round(para_ok / para_n, 3), "n_para": para_n,
           "contrast_correct_difference": round(con_ok / con_n, 3), "n_contrast": con_n,
           "gold_agree": round(gold_ok / len(groups), 3)}
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    Path(BENCH.with_suffix(".fails.json")).write_text(
        json.dumps(fails, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
