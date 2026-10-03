"""p2_words.py <r8 run dir> <extract cache (read only)> word...
For each word: headwords row; role_distribution rows per source and base; gen_frame type and generated_frames
frame; sahen_verb uses per source from the cache; coarse_place.query state/origin/top/frame_status.
When a word has no role_distribution row: typed and untyped argument counts per source (the stage-2 info)."""
import json, pickle, sqlite3, sys
import verantyx
from verantyx import coarse_place as cp
assert verantyx.__file__.startswith('/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a4-S/')
run, cache = sys.argv[1], sys.argv[2]
words = sys.argv[3:]
con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % run, uri=True)
ex = pickle.load(open(cache, "rb"))
m = json.load(open(run + "/manifest.json", encoding="utf-8"))
rd_store = m["config"]["rd_store_min"]
st2 = m["argument_chains"]["stage2"]["per_source"]
ok = True
for w in words:
    print("=== %s" % w)
    h = con.execute("select ns,state,origin,top,kind,n_seen,by from headwords where word=?", (w,)).fetchone()
    print("headwords: ns,state,origin,top,kind,n_seen,by =", h)
    rd = {}
    for src, typ, n, base in con.execute("select src,type,n,base from evidence where word=? and arm='role_distribution'", (w,)):
        rd.setdefault(src, {"base": base, "rows": {}})["rows"][typ] = n
    print("role_distribution:", json.dumps(rd, ensure_ascii=False, sort_keys=True))
    gf = con.execute("select ptype,frame,model,effort from generated_frames where word=?", (w,)).fetchone()
    gt = [r for r in con.execute("select src,type from evidence where word=? and arm='gen_frame'", (w,))]
    print("gen_frame evidence:", gt, " generated_frames row:", gf)
    sv = {s: c[w] for s, c in ex["sahen_verb"].items() if c.get(w)}
    print("sahen_verb uses per source (cache):", json.dumps(sv, ensure_ascii=False, sort_keys=True))
    sv_chain = {}
    for s, c in ex["chain_sahen"].items():
        tot = sum(n for (fr, fh, mk, v, past), n in c.items() if v == w)
        if tot:
            sv_chain[s] = tot
    print("chain_sahen arguments per source (cache, before typing):", json.dumps(sv_chain, ensure_ascii=False, sort_keys=True))
    a = cp.query(w, placement=run)
    print("query: state=%s origin=%s top=%s frame_status=%s namespace=%s" % (
        a.get("state"), a.get("origin"), a.get("top"), a.get("frame_status"), a.get("namespace")))
    good = bool(h) and "P" in (h[0] or "") and (h[5] or 0) > 0 and bool(rd)
    print("条件(ns に P・n_seen>0・どこかの出所に role_distribution の行): %s" % ("満たす" if good else "満たさない"))
    if not rd:
        print("role_distribution の行が無い理由の手がかり（rd_store_min=%d: 型つきの項が出所内でこの数未満）:" % rd_store)
        print("  出所ごとの chain_sahen の項の数（型づけ前）:", sv_chain, "（型つき・型なしの内訳は段 2 で語ごとには保存されない。出所の合計は manifest stage2.per_source.<src>.typed_arguments / untyped_arguments）")
    ok = ok and good
print("ALL_OK" if ok else "NOT_ALL_OK")
