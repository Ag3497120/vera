"""C5 (W5-b): what the placement-based common-noun check would do to the frozen routing data when the coarse placement is connected.

The product code is NOT changed and NOT connected to the placement: the `PlacementLookup` below lives in this script only.  It asks
`coarse_place.query(lemma, placement=<dir>)` and writes the answer down with `event_cross.PlaceResult.from_coarse_query` (a pure function).
Every explanation of the frozen data is explained twice (the stub lookup, then this one) and every question routed both ways.
Usage (from the tree root):  python artifacts/w5-b/scripts/routing_with_placement.py <placement dir>
"""
import json
import os
import sys
import unicodedata

TREE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, TREE)
from verantyx import coarse_place, event_cross, routing_from_text as rt  # noqa: E402

PLACEMENT = sys.argv[1]
DATA = os.path.join(TREE, "tests", "routing_from_text", "data")
SETS = (("items.jsonl", "explanations"), ("items_mid.jsonl", "explanations"), ("items_reader_shaped.jsonl", "explanations_reader_shaped"),
        ("items_mid_reader_shaped.jsonl", "explanations_reader_shaped"))


class CoarseLookup:
    id = "coarse-place-via-script/1"

    def __init__(self):
        self.asked = {}

    def lookup(self, lemma):
        if lemma not in self.asked:
            self.asked[lemma] = coarse_place.query(lemma, placement=PLACEMENT)
        return event_cross.PlaceResult.from_coarse_query(self.asked[lemma])


def norm(x):
    return unicodedata.normalize("NFKC", x).strip().casefold() if isinstance(x, str) else x


def misroute(expect, out):
    if expect.get("decision") == "undecided":
        return out["agent"] is not None
    return out["agent"] is not None and norm(out["agent"]) != norm(expect.get("agent"))


lookup = CoarseLookup()
cache = {}
questions = route_to_undecided = undecided_to_route = agent_changed = 0
mis_stub = mis_placed = 0
stopped = {}
checks = {}
for items_file, exp_dir in SETS:
    for line in open(os.path.join(DATA, items_file), encoding="utf-8"):
        item = json.loads(line)
        path = os.path.join(DATA, exp_dir, item["explanation_id"] + ".md")
        if path not in cache:
            text = rt.read_explanation(path)
            cache[path] = (rt.explain(text, path), rt.explain(text, path, lookup=lookup))
        stub, placed = cache[path]
        a, b = rt.route_task(stub, item["task"]), rt.route_task(placed, item["task"])
        questions += 1
        mis_stub += misroute(item["expect"], a)
        mis_placed += misroute(item["expect"], b)
        if a["decision"] == "route" and b["decision"] == "undecided":
            route_to_undecided += 1
        elif a["decision"] == "undecided" and b["decision"] == "route":
            undecided_to_route += 1
        elif a["agent"] != b["agent"]:
            agent_changed += 1
for path, (stub, placed) in sorted(cache.items()):
    key = os.path.basename(path)
    for u in placed.extraction.units:
        for r in u.reasons:
            if r.startswith("COMMON_NOUN_SUBJECT:"):
                stopped.setdefault(key, []).append(r)
    checks[key] = placed.extraction.common_noun_check
print("placement:", PLACEMENT)
print("explanations (distinct files):", len(cache), "questions:", questions)
print("route -> undecided because of the check:", route_to_undecided, "| undecided -> route:", undecided_to_route, "| agent changed:", agent_changed)
print("misroutes (scored as run_bank scores them): stub", mis_stub, "| with placement", mis_placed)
print("names stopped as COMMON_NOUN_SUBJECT (explanation: reasons):")
for k in sorted(stopped):
    print(" ", k, sorted(set(stopped[k])))
print("common_noun_check per explanation:")
for k in sorted(checks):
    print(" ", k, json.dumps(checks[k], ensure_ascii=False))
tot = {}
for c in checks.values():
    for k, v in c.items():
        tot[k] = tot.get(k, 0) + v
print("common_noun_check total over the distinct explanations:", json.dumps(tot, ensure_ascii=False))
