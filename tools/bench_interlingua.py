"""PREREGISTERED_2026-09-28_interlingua — run the sealed JA<->EN bench."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verantyx import en_frames as en  # noqa: E402
from verantyx.frames import Frame, canonical, read as ja_read  # noqa: E402

B = Path.home() / "Projects" / "vera-corpus" / "benches" / (sys.argv[1] if len(sys.argv) > 1 else "jaen_heldout_raw.json")
items = json.loads(B.read_text())["items"]


def to_en(fr, gloss):
    """Replace the Japanese words of a frame by their glossary English."""
    def m(w):
        if not w:
            return ""
        if w in gloss:
            return gloss[w]
        c = canonical(w)
        if c in gloss:
            return gloss[c]
        hits = [k for k in gloss if k and (k in w or w in k)]
        return gloss[max(hits, key=len)] if hits else w
    return Frame(m(fr.predicate), m(fr.agent), m(fr.patient), m(fr.recipient), fr.negated)


def swapped(a, b):
    ra, rb = list(a[1:4]), list(b[1:4])
    return a[0] == b[0] and a[4] == b[4] and any(
        rb[x] == ra[y] and rb[y] == ra[x] and ra[x] != ra[y] and rb[3 - x - y] == ra[3 - x - y]
        for x in range(3) for y in range(x + 1, 3))


rt = cross = para = para_n = con = con_n = 0
fails = []
for it in items:
    gloss = {g["ja"]: g["en"] for g in it["glossary"]}
    jf = ja_read(it["ja"])
    jm = to_en(jf, gloss) if jf else None
    kj = en.key(jm)
    ke = en.key(en.read(it["en"]))
    # 1 round trip: JA -> frame -> English sentence -> frame
    s = en.realize(jm) if jm else ""
    kr = en.key(en.read(s)) if s else None
    rt += bool(kj) and kr == kj
    if not (kj and kr == kj):
        fails.append(("roundtrip", it["ja"], s, kj, kr))
    # 2 cross-lingual
    cross += bool(kj) and kj == ke
    if not (kj and kj == ke):
        fails.append(("cross", it["ja"], it["en"], kj, ke))
    # 3 English paraphrases
    for p in it["en_paraphrases"]:
        para_n += 1
        kp = en.key(en.read(p))
        para += bool(ke) and kp == ke
        if not (ke and kp == ke):
            fails.append(("para", it["en"], p, ke, kp))
    # 4 contrasts against the Japanese structure
    for c in it["en_contrasts"]:
        con_n += 1
        kc = en.key(en.read(c["sentence"]))
        ok = False
        if kj and kc:
            if c["change"] == "role_swap":
                ok = swapped(kj, kc)
            elif c["change"] == "negation":
                ok = kc[:4] == kj[:4] and kc[4] != kj[4]
            else:
                ok = kc[0] == kj[0] and kc[4] == kj[4] and sum(x != y for x, y in zip(kc[1:4], kj[1:4])) == 1
        con += ok
        if not ok:
            fails.append(("contrast", c["change"], it["ja"], c["sentence"], kj, kc))
n = len(items)
rep = {"n": n, "roundtrip": round(rt / n, 3), "cross_lingual": round(cross / n, 3),
       "en_paraphrase": round(para / max(para_n, 1), 3), "contrast": round(con / max(con_n, 1), 3)}
print(json.dumps(rep, ensure_ascii=False, indent=1))
B.with_suffix(".fails.json").write_text(json.dumps(fails, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
