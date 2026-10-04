"""The predicate form of the generator (W3-a3, ``--kind pred``) against a FAKE codex.

No test here ever calls the real codex: ``--codex-bin`` is always a script written into tmp_path.  The
noun form is checked here only for what must stay byte-identical (the prompt hash)."""
import hashlib
import json
import os
import pickle
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tools import gen_coarse_evidence as gce
from verantyx import coarse_types as ct

TREE = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
NOUN_PROMPT_SHA = "ded30f48c0a596575d061e75aa0768beb3008969a587a01d2ec39807af031f65"

FAKE = r'''#!%(python)s
import hashlib, json, os, sys, time, select
here = os.path.dirname(os.path.abspath(__file__))
cfg = json.load(open(os.path.join(here, "fake_cfg.json"), encoding="utf-8"))
argv = sys.argv[1:]
prompt = argv[-1]
words = []
for line in prompt.splitlines():
    if line.startswith("WORDS_JSON:"):
        words = json.loads(line[len("WORDS_JSON:"):].strip())
out = argv[argv.index("-o") + 1]
schema = json.load(open(argv[argv.index("--output-schema") + 1], encoding="utf-8"))
t0 = time.time()
rec = {"argv": argv, "t0": t0, "first": words[0] if words else None, "n": len(words),
       "schema_has_ptype": "ptype" in json.dumps(schema), "prompt_has_pred_types": "P_COMMUNICATE" in prompt}
if cfg.get("check_stdin"):
    r, _, _ = select.select([0], [], [], 2.0)
    ok = bool(r) and os.read(0, 1) == b""
    if not ok:
        open(os.path.join(here, "STDIN_NOT_CLOSED"), "w").write("x")
        sys.exit(9)
time.sleep(cfg.get("sleep", 0))
key = words[0] if words else ""
cnt_path = os.path.join(here, "count_" + hashlib.md5(key.encode("utf-8")).hexdigest())
n = 0
if os.path.exists(cnt_path):
    n = int(open(cnt_path).read())
open(cnt_path, "w").write(str(n + 1))
rec["t1"] = time.time()
with open(os.path.join(here, "calls.jsonl"), "a") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
if key in cfg.get("always_fail", []) or n < cfg.get("fail_first", {}).get(key, 0):
    sys.stderr.write("simulated failure\n")
    sys.exit(1)
if cfg.get("tool_use"):
    print(json.dumps({"type": "item.completed", "item": {"type": "command_execution"}}))
print(json.dumps({"type": "item.completed", "item": {"type": "agent_message"}}))
GOOD = {"ptype": "P_MOVE", "frame": [{"particle": "が", "types": ["PERSON"]}, {"particle": "へ", "types": ["PLACE"]}]}
items = []
for w in words:
    if w in cfg.get("missing", []):
        continue
    it = {"word": w}
    spec = cfg.get("special", {}).get(w)
    if w in cfg.get("null", []):
        it.update({"ptype": None, "frame": []})
    elif spec is not None:
        it.update(spec)
    else:
        it.update(GOOD)
    items.append(it)
    if w in cfg.get("dup", []):
        items.append(dict(it, ptype="P_ACT"))
if cfg.get("foreign"):
    items.append({"word": "ゼンゼンチガウ", "ptype": "P_ACT", "frame": []})
json.dump({"items": items}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
'''


def make_fake(tmp: Path, **cfg) -> Path:
    p = tmp / "fakecodex"
    p.write_text(FAKE % {"python": PYTHON}, encoding="utf-8")
    p.chmod(0o755)
    set_cfg(tmp, **cfg)
    return p


def set_cfg(tmp: Path, **cfg):
    (tmp / "fake_cfg.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")


def write_needs(path: Path, n: int, prefix="動"):
    with open(path, "w", encoding="utf-8") as f:
        for i in range(n):
            f.write(json.dumps({"rank": i + 1, "word": "%s%03d" % (prefix, i), "freq": 1000 - i,
                                "state": "UNPLACED", "ns": "P", "kind": "token",
                                "evidence_status": "NO_EVIDENCE"}, ensure_ascii=False) + "\n")


def run(tmp, needs, out_dir, fake, *extra, bs=2):
    return gce.main(["run", "--kind", "pred", "--needs", str(needs), "--out-dir", str(out_dir),
                     "--codex-bin", str(fake), "--batch-size", str(bs), *extra])


def ledger(out_dir):
    return [json.loads(l) for l in open(Path(out_dir) / "ledger.jsonl", encoding="utf-8")]


def starts(out_dir):
    return [e for e in ledger(out_dir) if e["ev"] == "start"]


def calls(tmp):
    p = tmp / "calls.jsonl"
    return [json.loads(l) for l in open(p, encoding="utf-8")] if p.exists() else []


@pytest.fixture
def env(tmp_path):
    needs = tmp_path / "needs.jsonl"
    write_needs(needs, 8)
    return tmp_path, needs, tmp_path / "G"


def max_overlap(cs):
    ev = sorted([(c["t0"], 1) for c in cs] + [(c["t1"], -1) for c in cs])
    cur = best = 0
    for _t, d in ev:
        cur += d
        best = max(best, cur)
    return best


# --- the noun form is untouched ----------------------------------------------------------------
def test_the_noun_prompt_and_its_hash_did_not_change():
    assert gce.prompt_template_sha256() == NOUN_PROMPT_SHA
    assert gce.sha256_text(gce.PROMPT_HEAD + gce.WORDS_PREFIX) == NOUN_PROMPT_SHA
    assert gce.PROMPT_HEAD.startswith("あなたは日本語の辞書の編集者です。")
    assert gce.SCHEMA["properties"]["items"]["items"]["required"] == ["word", "definition", "hypernym"]


# --- the prompt and the schema ---------------------------------------------------------------------
def test_the_predicate_prompt_lists_the_closed_inventories_from_coarse_types_and_no_test_word():
    """2026-10-04 20:38:46 +0900: before this test read 17 NOUN_TYPES; now check the same 17 FRAME_NOUN_TYPES because predicates exclude the new 18th id."""
    h = gce.PRED_PROMPT_HEAD
    for k, v in ct.PRED_TYPES.items():
        assert "- %s: %s" % (k, v) in h
    for k, v in ct.FRAME_NOUN_TYPES.items():
        assert "- %s: %s" % (k, v) in h
    assert len(re.findall(r"^- P_[A-Z]+:", h, re.M)) == 13 and len(re.findall(r"^- [A-Z_]+: ", h, re.M)) == 13 + len(ct.FRAME_NOUN_TYPES)
    assert "が を に で へ と から まで より" in h
    p = gce.build_prompt_pred(["アア", "イイ"])
    assert p.splitlines()[-1] == 'WORDS_JSON: ["アア", "イイ"]'
    assert gce.prompt_template_sha256_pred() == gce.sha256_text(gce.PRED_PROMPT_HEAD + gce.WORDS_PREFIX)
    assert gce.prompt_template_sha256_pred() != gce.prompt_template_sha256()
    # no word of any test data (the verb data included) appears in the prompt
    fz = TREE / "tests/coarse_place/data"
    terms = set()
    for name in ("typed_vocab", "unknown_words", "dev_vocab", "dev_unknown", "predicate_check",
                 "dev_verbs", "verb_check_300"):
        for line in (fz / (name + ".jsonl")).read_text(encoding="utf-8").splitlines():
            terms.add(json.loads(line)["term"])
    # the names the prompt itself carries (type names) are not test words; every test word of two
    # characters or more must be absent from the prompt as a token between the structural characters
    for t in sorted(terms):
        if len(t) >= 2:
            assert t not in h.replace("、", " ").replace("（", " ").replace("）", " ").split(), t
    # and the examples in the prompt are place-holders, never a real word
    spans = re.findall(r"[<]([^>]*)[>]", h)
    assert not [t for t in terms if t in spans]


def test_the_schema_is_closed_and_its_enums_are_the_inventories():
    """2026-10-04 20:38:46 +0900: before the enum used NOUN_TYPES (17); now it uses FRAME_NOUN_TYPES (17) while NOUN_TYPES is 18, preserving the predicate contract."""
    s = gce.PRED_SCHEMA
    item = s["properties"]["items"]["items"]
    assert s["additionalProperties"] is False and item["additionalProperties"] is False
    assert item["required"] == ["word", "ptype", "frame"]
    assert set(item["properties"]["ptype"]["enum"]) == set(ct.PRED_TYPES) | {None}
    fr = item["properties"]["frame"]["items"]
    assert fr["additionalProperties"] is False and fr["required"] == ["particle", "types"]
    assert fr["properties"]["particle"]["enum"] == list(ct.CASE_PARTICLES_9) and len(fr["properties"]["particle"]["enum"]) == 9
    assert fr["properties"]["types"]["items"]["enum"] == list(ct.FRAME_NOUN_TYPES) and len(ct.FRAME_NOUN_TYPES) == 17


def test_the_prompt_command_prints_both_hashes(capsys):
    assert gce.main(["prompt", "--kind", "pred"]) == 0
    out = capsys.readouterr().out
    assert "template_sha256 " + gce.prompt_template_sha256_pred() in out
    assert "schema_sha256 " + gce.schema_sha256(gce.PRED_SCHEMA) in out
    assert gce.main(["prompt"]) == 0
    assert "template_sha256 " + NOUN_PROMPT_SHA in capsys.readouterr().out


# --- the call -----------------------------------------------------------------------------------------
def test_calls_run_in_parallel_up_to_the_slot_count_and_slots_are_capped_at_twelve(env):
    tmp, needs, G = env
    fake = make_fake(tmp, sleep=0.5)
    write_needs(needs, 16)
    t0 = time.time()
    assert run(tmp, needs, G, fake, "--slots", "4") == 0
    wall = time.time() - t0
    cs = calls(tmp)
    assert len(cs) == 8 and 2 <= max_overlap(cs) <= 4 and wall < 8 * 0.5
    with pytest.raises(SystemExit):
        run(tmp, needs, tmp / "G2", fake, "--slots", "13")


def test_the_command_has_the_model_effort_sandbox_a_pred_schema_and_the_codex_bin_is_required(env):
    tmp, needs, G = env
    fake = make_fake(tmp)
    assert run(tmp, needs, G, fake, "--limit-batches", "1", "--extra-config", "mcp_servers.x.enabled=false") == 0
    c = calls(tmp)[0]
    argv = c["argv"]
    assert argv[argv.index("-m") + 1] == "gpt-6-luna"
    assert 'model_reasoning_effort="low"' in argv
    assert argv[argv.index("-s") + 1] == "read-only"
    assert "--ephemeral" in argv and "--skip-git-repo-check" in argv and "mcp_servers.x.enabled=false" in argv
    assert c["schema_has_ptype"] is True and c["prompt_has_pred_types"] is True
    sl = starts(G)[0]["argv"]
    assert sl[sl.index("-m") + 1] == "gpt-6-luna" and 'model_reasoning_effort="low"' in sl and "read-only" in sl
    assert not any("WORDS_JSON" in a for a in sl)
    meta = json.loads((G / "batches.json").read_text(encoding="utf-8"))["meta"]
    assert meta["kind"] == "pred" and meta["prompt_template_sha256"] == gce.prompt_template_sha256_pred()
    assert meta["schema_sha256"] == gce.schema_sha256(gce.PRED_SCHEMA)
    assert json.loads((G / "schema.json").read_text(encoding="utf-8")) == gce.PRED_SCHEMA
    with pytest.raises(SystemExit):
        gce.main(["run", "--kind", "pred", "--needs", str(needs), "--out-dir", str(G)])


def test_the_child_gets_a_closed_stdin(env):
    tmp, needs, G = env
    fake = make_fake(tmp, check_stdin=True)
    p = subprocess.Popen([PYTHON, str(TREE / "tools/gen_coarse_evidence.py"), "run", "--kind", "pred",
                          "--needs", str(needs), "--out-dir", str(G), "--codex-bin", str(fake),
                          "--batch-size", "4", "--slots", "2"],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = p.communicate(timeout=60)
    finally:
        if p.poll() is None:
            p.kill()
    assert p.returncode == 0, err
    assert not (tmp / "STDIN_NOT_CLOSED").exists()
    assert gce.summarize(str(G))["batches_ok"] == 2


def test_the_ledger_resume_retry_and_the_cap_work_as_for_nouns(env):
    tmp, needs, G = env
    fake = make_fake(tmp)
    assert run(tmp, needs, G, fake, "--slots", "2", "--limit-batches", "2") == 0
    first = (G / "ledger.jsonl").read_text(encoding="utf-8")
    for e in ledger(G):
        if e["ev"] == "start":
            assert set(e) >= {"batch", "attempt", "words_sha", "words", "prompt_sha256", "argv", "t"}
        else:
            assert e["status"] == "ok" and e["n_items"] == 2 and e["out_sha256"] == gce.sha256_file(e["out_path"])
    assert run(tmp, needs, G, fake, "--slots", "2") == 0                       # resumes with the rest only
    assert (G / "ledger.jsonl").read_text(encoding="utf-8").startswith(first)
    assert len(starts(G)) == 4 and len(calls(tmp)) == 4
    assert run(tmp, needs, G, fake) == 0 and len(starts(G)) == 4                # nothing left to call
    # a batch that fails twice succeeds on the third try; the cap counts retries (fresh words: the fake
    # counts the calls it saw per first word)
    G2 = tmp / "G2"
    write_needs(needs, 8, prefix="別")
    set_cfg(tmp, fail_first={"別000": 2})
    assert run(tmp, needs, G2, fake, "--slots", "1") == 0
    assert [e["attempt"] for e in starts(G2) if e["words"][0] == "別000"] == [1, 2, 3]
    G3 = tmp / "G3"
    write_needs(needs, 8, prefix="続")
    set_cfg(tmp, always_fail=["続000"])
    assert run(tmp, needs, G3, fake, "--max-calls", "4", "--slots", "1") == 0
    assert len(starts(G3)) == 4
    G4 = tmp / "G4"
    write_needs(needs, 20, prefix="余")
    set_cfg(tmp)
    assert run(tmp, needs, G4, fake, "--max-calls", "5", "--slots", "4") == 0
    s = gce.summarize(str(G4))
    assert len(starts(G4)) == 5 and s["calls"] == 5 and s["not_run_cap"] == 5 and s["kind"] == "pred"


def test_a_tool_use_is_rejected_and_a_codex_that_cannot_start_is_a_typed_failure(env):
    tmp, needs, G = env
    fake = make_fake(tmp, tool_use=True)
    assert run(tmp, needs, G, fake, "--limit-batches", "1", "--max-retries", "0") == 0
    e = [x for x in ledger(G) if x["ev"] == "end"][0]
    assert e["status"] == "tool_use" and e["reason"].startswith("TOOL_USE:")
    G2 = tmp / "G2"
    assert run(tmp, needs, G2, tmp / "does_not_exist", "--limit-batches", "1", "--max-retries", "0") == 0
    e = [x for x in ledger(G2) if x["ev"] == "end"][0]
    assert e["status"] == "failed" and e["reason"] == "OSERROR"


# --- the output checks ------------------------------------------------------------------------------------
def test_output_checks_duplicates_foreign_words_nulls_double_particles_and_values_outside_the_inventory(env):
    tmp, needs, G = env
    special = {
        "動002": {"ptype": "P_ACT", "frame": [{"particle": "を", "types": ["ARTIFACT"]},
                                              {"particle": "を", "types": ["PERSON"]}]},     # one particle twice
        "動004": {"ptype": "P_NOT_A_TYPE", "frame": []},                                      # outside the inventory
        "動006": {"ptype": "P_ACT", "frame": [{"particle": "の", "types": ["ARTIFACT"]}]},     # a particle outside the nine
    }
    fake = make_fake(tmp, dup=["動001"], foreign=True, null=["動000"], special=special)
    assert run(tmp, needs, G, fake, "--slots", "4") == 0
    out = tmp / "frames.jsonl"
    assert gce.main(["collect", "--kind", "pred", "--out-dir", str(G), "--out", str(out)]) == 0
    rows = {json.loads(l)["word"]: json.loads(l) for l in open(out, encoding="utf-8")}
    assert "動001" not in rows                                  # came back twice: not taken
    assert "動004" not in rows and "動006" not in rows           # invalid: not taken
    assert rows["動000"]["abstained"] is True and rows["動000"]["ptype"] is None and rows["動000"]["frame"] == {}
    assert rows["動002"]["ptype"] == "P_ACT" and rows["動002"]["frame"] == {}     # the double particle: no frame, no choice by order
    assert rows["動003"]["ptype"] == "P_MOVE" and rows["動003"]["frame"] == {"が": ["PERSON"], "へ": ["PLACE"]}
    s = gce.summarize(str(G))
    assert s["words_dup_dropped"] == 1 and s["words_foreign_dropped"] >= 1
    assert s["words_abstained"] == 1 and s["words_invalid"] == 2 and s["words_frame_dup_particle"] == 1
    assert s["kind"] == "pred" and s["words_answered"] == 8 - 1 - 2           # 8 asked; dup and two invalid dropped
    # a word that does not come back is `missing`, not an abstention
    G2 = tmp / "G2"
    set_cfg(tmp, missing=["動001"])
    assert run(tmp, needs, G2, fake, "--limit-batches", "1") == 0
    assert gce.summarize(str(G2))["words_missing"] == 1


def test_collect_is_deterministic_in_batch_order_with_the_origin_on_every_row(env):
    tmp, needs, G = env
    fake = make_fake(tmp)
    assert run(tmp, needs, G, fake, "--slots", "4") == 0
    a, b = tmp / "a.jsonl", tmp / "b.jsonl"
    assert gce.main(["collect", "--kind", "pred", "--out-dir", str(G), "--out", str(a)]) == 0
    assert gce.main(["collect", "--kind", "pred", "--out-dir", str(G), "--out", str(b)]) == 0
    assert a.read_bytes() == b.read_bytes()
    rows = [json.loads(l) for l in open(a, encoding="utf-8")]
    assert [r["word"] for r in rows] == ["動%03d" % i for i in range(8)]
    for r in rows:
        p = r["provenance"]
        assert set(r) == {"word", "ptype", "frame", "abstained", "provenance"}
        assert p["origin"] == "generated" and p["model"] == "gpt-6-luna" and p["effort"] == "low"
        assert re.match(r"b\d{5}_[0-9a-f]{12}$", p["batch_id"]) and p["attempt"] == 1 and p["out_sha256"]
        assert r["abstained"] is False and r["ptype"] == "P_MOVE" and set(r["frame"]) == {"が", "へ"}
    raw = next((G / "raw").iterdir())
    raw.write_text('{"items": []}', encoding="utf-8")
    assert gce.main(["collect", "--kind", "pred", "--out-dir", str(G), "--out", str(tmp / "c.jsonl")]) == 4


def test_summarize_numbers_come_from_the_ledger(env):
    tmp, needs, G = env
    fake = make_fake(tmp, sleep=0.2)
    assert run(tmp, needs, G, fake, "--slots", "2") == 0
    s = gce.summarize(str(G))
    assert s["calls"] == 4 and s["batches_total"] == 4 and s["batches_ok"] == 4 and s["ok_rate"] == 1.0
    assert s["words_requested"] == 8 and s["words_answered"] == 8 and s["calls_per_word_requested"] == 0.5
    assert s["wall_sec"] >= 0.2 and s["sum_call_sec"] >= 0.8 and s["kind"] == "pred"
    outp = tmp / "sum.json"
    assert gce.main(["summarize", "--kind", "pred", "--out-dir", str(G), "--out", str(outp)]) == 0
    assert json.loads(outp.read_text(encoding="utf-8"))["calls"] == 4


# --- the list of verbs -------------------------------------------------------------------------------------
def make_placement(tmp: Path, rows):
    d = tmp / "pl"
    d.mkdir()
    con = sqlite3.connect(str(d / "placement.sqlite"))
    con.execute("CREATE TABLE headwords(word TEXT PRIMARY KEY, ns TEXT, state TEXT, origin TEXT,"
                " top TEXT, kind TEXT, n_seen INTEGER, by TEXT) WITHOUT ROWID")
    con.execute("CREATE TABLE evidence(word TEXT, arm TEXT, src TEXT, type TEXT, n INTEGER, base INTEGER,"
                " PRIMARY KEY(word, arm, src, type)) WITHOUT ROWID")
    for r in rows:
        con.execute("INSERT INTO headwords VALUES (?,?,?,?,?,?,?,?)", r)
    con.commit()
    con.close()
    (d / "manifest.json").write_text(json.dumps({"content_sha256": "abc123"}), encoding="utf-8")
    return d


def write_cache(path: Path, verbs, adjs):
    from collections import Counter
    pos = {"jawiki": Counter(), "codex:code": Counter()}
    for w, (a, b) in verbs.items():
        pos["jawiki"][(w, "V")] += a
        pos["codex:code"][(w, "V")] += b
    for w, (a, b) in adjs.items():
        pos["jawiki"][(w, "A")] += a
        pos["codex:code"][(w, "S")] += b
    with open(path, "wb") as f:
        pickle.dump({"pos": pos}, f)


def test_the_list_of_verbs_is_by_frequency_keeps_the_boundary_tie_and_only_verbs(tmp_path):
    rows = [("う%02d" % i, "P", "UNPLACED", None, "", "token", 100 - i // 3, "") for i in range(30)]
    rows += [("名詞語", "N", "UNPLACED", None, "", "token", 900, ""),                        # a noun: not a verb
             ("決定語", "P", "DECIDED", "direct", "P_ACT", "token", 800, "seed"),              # decided: not needed
             ("形容語", "P", "UNPLACED", None, "", "token", 700, ""),                          # an adjective
             ("両用語", "NP", "MULTIPLE", "direct", "P_ACT,P_STATE", "token", 650, ""),
             ("同数語", "NP", "UNPLACED", None, "", "token", 600, "")]                         # as many verb as adjective uses
    pl = make_placement(tmp_path, rows)
    verbs = {"う%02d" % i: (5, 5) for i in range(30)}
    verbs.update({"名詞語": (0, 0), "決定語": (9, 9), "形容語": (3, 3), "両用語": (8, 2), "同数語": (4, 4)})
    cache = tmp_path / "c.pkl"
    write_cache(cache, verbs, {"形容語": (30, 30), "同数語": (4, 4), "名詞語": (50, 50)})
    out, meta = tmp_path / "needs.jsonl", tmp_path / "needs.meta.json"
    assert gce.main(["needs", "--kind", "pred", "--placement", str(pl), "--stage-cache", str(cache),
                     "--n", "9", "--out", str(out), "--meta", str(meta)]) == 0
    got = [json.loads(l) for l in open(out, encoding="utf-8")]
    m = json.loads(meta.read_text(encoding="utf-8"))
    words = [g["word"] for g in got]
    for bad in ("名詞語", "決定語", "形容語", "同数語"):
        assert bad not in words
    assert "両用語" in words and got[0]["word"] == "両用語"                                  # 650 is the most frequent verb
    fs = [g["freq"] for g in got]
    assert fs == sorted(fs, reverse=True)
    boundary = fs[8]                                           # the 9th word's frequency: EVERY word with it is in
    all_at_boundary = [r for r in rows if r[0].startswith("う") and r[6] == boundary]
    assert sum(1 for g in got if g["freq"] == boundary) == len(all_at_boundary) > 1 and len(got) > 9
    assert m["kind"] == "pred" and m["total"] == len(got) and m["boundary_freq"] == boundary
    assert all(g["ns"] in ("P", "NP") and g["verb_uses"] > g["adjective_uses"] for g in got)
    same = [g["word"] for g in got if g["freq"] == boundary]
    assert same == sorted(same) and [g["rank"] for g in got] == list(range(1, len(got) + 1))
    # a missing cache is a typed stop, not a guess
    assert gce.main(["needs", "--kind", "pred", "--placement", str(pl), "--n", "10", "--out", str(out),
                     "--meta", str(meta)]) == 2


def test_the_selection_never_reads_the_verb_test_data():
    text = (TREE / "tools/gen_coarse_evidence.py").read_text(encoding="utf-8")
    assert "tests/coarse_place/data" not in text and "dev_verbs" not in text and "verb_check" not in text
    import inspect
    assert list(inspect.signature(gce.select_needs_pred).parameters) == ["placement", "n", "stage_cache"]
