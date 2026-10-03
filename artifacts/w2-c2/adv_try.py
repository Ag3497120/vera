import sys, json, os, runpy
frames = "/Users/motonisihikoudai/Projects/vera-impl/wt/W2-c2-S/tests/conduct_ask/w2c2/frames/"
mapfake = "/Users/motonisihikoudai/Projects/vera-impl/wt/W2-c2-S/tests/conduct_ask/w2c2/map_fake_empty.json"
from verantyx import conduct_ask
cands = runpy.run_path(sys.argv[1])["CANDS"]
only = sys.argv[2] if len(sys.argv) > 2 else None
for c in cands:
    fid, q, opts = c[0], c[1], c[2]
    tag = c[3] if len(c) > 3 else ""
    if only and only not in tag: continue
    off = conduct_ask.answer_question(frames + fid + ".md", q, opts)
    fm = conduct_ask.answer_question(frames + fid + ".md", q, opts, vocab_llm="fake", map_fake=mapfake)
    m = fm.get("mapping") or {}
    rule = m.get("rule") or {}
    o = f"{off['decision'][:3]} {off['escalate_reason']}/{off['escalate_detail']}" if off['decision']!='answer' else f"ANS {off['answer']}#{off['answer_option_index']}"
    f = f"{fm['decision'][:3]} {m.get('outcome')} | rule={rule.get('reason')}/{rule.get('detail')}"
    print(f"[{tag}] {fid[:3]} {q} {opts or ''}\n     off={o}\n     fm={f}")
