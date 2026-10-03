import json, sys, collections
Q = sys.argv[1]
def load(n): return {w: a for w, a in (json.loads(l) for l in open(f"{Q}/{n}_r8.jsonl", encoding="utf-8"))}
ov, ov0, ovb = load("ov"), load("ov0"), load("ovb")
def states(d): return collections.Counter(a.get("frame_status") for a in d.values())
print("r8 words", len(ov), len(ov0), len(ovb))
print("frame_status counts ov :", dict(states(ov)))
print("frame_status counts ov0:", dict(states(ov0)))
print("frame_status counts ovb:", dict(states(ovb)))
diff = [w for w in ov if ov[w] != ov0[w]]
print("words changed by R1 (ov vs ov0):", len(diff))
keys = collections.Counter(); he_ok = True
for w in diff:
    ks = sorted(k for k in set(ov[w]) | set(ov0[w]) if ov[w].get(k) != ov0[w].get(k)); keys.update(ks)
    if ov[w].get("frame_unconfirmed", {}).get("へ") != ["PLACE"]: he_ok = False
print("keys that differ:", dict(keys), " | all have frame_unconfirmed['へ']==['PLACE']:", he_ok)
for k in ("state", "origin", "top", "frame_status", "frame"):
    print("changed", k, sum(1 for w in ov if ov[w].get(k) != ov0[w].get(k)))
for w in diff: print(json.dumps([w, ["frame_unconfirmed"], ov0[w].get("frame"), ov0[w].get("frame_unconfirmed"), ov[w].get("frame_unconfirmed")], ensure_ascii=False))
def empty(d): return [w for w, a in d.items() if a.get("frame_status") == "CONFIRMED" and a.get("frame") == {}]
for n, d in (("ovb(base coarse_place)", ovb), ("ov0(round1 coarse_place)", ov0), ("ov(now)", ov)):
    e = empty(d); print(f"{n} r8 CONFIRMED with frame=={{}}:", len(e), e)
# ignored (informational): CONFIRMED words whose gen_frame arm has cover.ignored non-empty
ign = []; cov = []
for w, a in ov.items():
    if a.get("frame_status") != "CONFIRMED": continue
    arm = (a.get("axes") or {}).get("gen_frame") or {}
    c = arm.get("cover")
    if c is not None: cov.append(w)
    if c and c.get("ignored"): ign.append(w)
print("CONFIRMED words whose answer carries cover (axes):", len(cov), " ; with cover.ignored non-empty:", len(ign), ign)
