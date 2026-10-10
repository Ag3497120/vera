"""G3-k: the grammar intake of every bank question (no reading): form, slot, unknown RUN words with their pattern type and stand-in counts (chance =
n_standins / pool).  usage: intake_survey.py bank3|bank2 [ids|all]   (stdout; fulllead only)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
from verantyx.line3 import space as sp, wiring as W   # noqa: E402

bank = sys.argv[1]
want = None if len(sys.argv) < 3 or sys.argv[2] == "all" else sys.argv[2].split(",")
space = sp.build_space(sp.load_jsonl(os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")))
ix, _ = W.context_of(type("O", (), {"space": space})())
for l in open(os.path.join(ROOT, "experiments/line3", bank, bank + ".tsv"), encoding="utf-8"):
    if l.startswith("#") or not l.strip():
        continue
    r = l.rstrip("\n").split("\t")
    if r[2] != "fulllead" or (want and r[0] not in want):
        continue
    gi = W.intake(space, r[4], ix)
    print(json.dumps({"id": r[0], "kind": r[1], "form": gi.form, "slot": gi.slot, "units": list(gi.units), "n_added": len(gi.standins),
                      "words": [{"w": w.word, "type": w.type, "via": w.via, "n": w.n_standins, "pool": w.pool, "added": len(w.added)} for w in gi.words]},
                     ensure_ascii=False))
