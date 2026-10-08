"""W5-c round 3 synthetic sweep of ``apply_to_ask`` (factual question), sovereign in 4 states.

family (the 9 index families + 10 others: document, general, x, jawiki, conversation_form, code_parts, pun_lexicon, user,
no key, 3) x origin (absent, None, "", "zzz", "human", 3) x result type (5) x mode (3) x documents (2) x human (2) x
reference (2) x companion (alone, request text, generated, human_confirmed) x sovereign (none / consenting /
consenting + a recorded yes with a sentence that differs from the result's text / not consenting).

For a combination whose source set holds an unknown origin (independent definition below, not the product's) it checks:
no ANSWER_*, no CONFIRM_REQUEST, no REFERENCE_GENERATED, the policy applied (no pass-through), a typed abstention,
no sources and no confirm block in the output, the recorded sentence absent from the output. For the others it counts
the outcomes and flags an ANSWER_HUMAN_BASIS that none of the three declared reasons explains.
Every sovereign root is hashed (all files) at the start, every 20,000 calls and at the end.
Usage: r3_synth.py WORKDIR   (PYTHONPATH=<tree>)"""
import copy, hashlib, itertools, json, os, sys
from collections import Counter
from pathlib import Path
from verantyx import ability_corpus, basis_policy as bp, sovereign as sov

work = Path(sys.argv[1]); work.mkdir(parents=True, exist_ok=True)
Q = "窓は？"
RECORD = "人の答え。"
BODY = "窓が光った。"
FAMILIES = list(ability_corpus.FAMILIES) + ["document", "general", "x", "jawiki", "conversation_form", "code_parts",
                                           "pun_lexicon", "user", "MISSING", 3]
ORIGINS = ["MISSING", "NONE_VALUE", "", "zzz", "human", 3]
TYPES = [("answer", "ANSWER"), ("social", None), ("answer", "PARTIAL"), ("unknown", "UNKNOWN_X"), ("refusal", "UNKNOWN_Y")]
MODES = ["legacy", "round5", "engine"]
GEN = {"family": "local", "source": "g0", "text": BODY, "sha": "w", "origin": "generated", "source_file": "f.jsonl", "line": 4}
USER = {"family": "user", "source": "user:request", "text": Q}
HC = {"family": "memory_sovereign", "source": "e1", "text": BODY, "origin": "human_confirmed"}
COMP = {"alone": [], "request": [USER], "generated": [GEN], "human_confirmed": [HC]}


def make(family, origin):
    s = {"source": "x1", "text": BODY, "source_file": "f.jsonl", "line": 1, "sha": "s1"}
    if family != "MISSING":
        s["family"] = family
    if origin != "MISSING":
        s["origin"] = None if origin == "NONE_VALUE" else origin
    return s


def unknown_expected(family, origin, mode, docs):
    """Independent of the product: is this one source of unknown origin?"""
    if origin != "MISSING" and origin != "NONE_VALUE":
        return True                                   # an origin value outside the closed vocabulary
    if family == "user":
        return False                                  # the request text itself
    if family == "document" and mode == "round5" and docs:
        return False                                  # the user's own document, handed over in this call
    return True


def snap(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


roots = {}
roots["none"] = None
r = work / "sov_consent"; assert sov.create(str(r), "s1", "o", consent_promote=True)["verdict"] == "CREATED"; roots["consent"] = (r, "s1")
r = work / "sov_yes"; assert sov.create(str(r), "s1", "o", consent_promote=True)["verdict"] == "CREATED"
rec = {"record": "basis_confirmation", "status": "HUMAN_CONFIRMED", "witness": "user_confirmation", "confirm_id": "abc",
       "query": Q, "claim": RECORD, "generated_sources": [], "table_version": 1, "origin": "human_confirmed"}
assert sov.append_basis_confirmation(str(r), "s1", rec)["verdict"] == "APPENDED"; roots["consent+yes"] = (r, "s1")
r = work / "sov_noconsent"; assert sov.create(str(r), "s1", "o", consent_promote=False)["verdict"] == "CREATED"; roots["no_consent"] = (r, "s1")
before = {k: snap(v[0]) for k, v in roots.items() if v}
for k in ("VERA_SOVEREIGN_ROOT", "VERA_SOVEREIGN_STORE", "VERA_P4_INDEX"):
    os.environ.pop(k, None)

n = 0
bad = Counter(); bad_examples = []
unknown_n = 0; other_hist = Counter(); unexplained = Counter(); unknown_hist = Counter()
for sname, sv in roots.items():
    if sv:
        os.environ["VERA_SOVEREIGN_ROOT"], os.environ["VERA_SOVEREIGN_STORE"] = str(sv[0]), sv[1]
    else:
        os.environ.pop("VERA_SOVEREIGN_ROOT", None); os.environ.pop("VERA_SOVEREIGN_STORE", None)
    for family, origin, (kind, verdict), mode, docs, human, ref, cname in itertools.product(
            FAMILIES, ORIGINS, TYPES, MODES, (False, True), (False, True), (False, True), COMP):
        src = make(family, origin)
        sources = [src] + copy.deepcopy(COMP[cname])
        result = {"kind": kind, "verdict": verdict, "text": "窓が光ります。", "door": "chat", "sources": sources,
                  "evidence": [BODY], "trace": [{"part": "p", "status": "ran"}]}
        frozen = copy.deepcopy(result)
        out, rc = bp.apply_to_ask(result, bp.AskPolicy(human_present=human, show_reference=ref), query=Q, mode=mode,
                                  documents=["memo.txt"] if docs else [])
        n += 1
        note = out["basis_policy"]; oc = note["outcome"]
        if result != frozen:
            bad["input_modified"] += 1
        has_unknown = unknown_expected(family, origin, mode, docs)
        if has_unknown:
            unknown_n += 1
            unknown_hist[oc] += 1
            problems = []
            if oc is None or oc.startswith("ANSWER_"): problems.append("ANSWER_OR_PASSTHROUGH")
            if oc in ("CONFIRM_REQUEST", "REFERENCE_GENERATED"): problems.append(oc)
            if note.get("applied") is not True: problems.append("NOT_APPLIED")
            if out.get("kind") == "answer" or out.get("verdict") in ("ANSWER", "CONFIRM_REQUEST"): problems.append("ANSWER_SIDE_TYPE")
            if out.get("sources") != []: problems.append("SOURCES_KEPT")
            if "confirm" in out: problems.append("CONFIRM_BLOCK")
            if RECORD in json.dumps(out, ensure_ascii=False): problems.append("RECORD_TEXT_IN_OUTPUT")
            if rc != 0: problems.append("RC")
            for p in problems:
                bad[p] += 1
                if len(bad_examples) < 5:
                    bad_examples.append((p, sname, family, origin, kind, verdict, mode, docs, human, ref, cname, oc))
        else:
            other_hist[(oc if oc is not None else "PASSTHROUGH")] += 1
            if oc == "ANSWER_HUMAN_BASIS":
                explained = (cname == "human_confirmed"
                             or (family == "document" and mode == "round5" and docs and origin in ("MISSING", "NONE_VALUE"))
                             or (sname == "consent+yes" and cname == "generated"))
                if not explained:
                    unexplained[(sname, family if isinstance(family, str) else repr(family), cname)] += 1
        if n % 20000 == 0:
            for k, v in roots.items():
                if v and snap(v[0]) != before[k]:
                    bad["SOVEREIGN_CHANGED:" + k] += 1
after = {k: snap(v[0]) for k, v in roots.items() if v}
for k in before:
    if before[k] != after[k]:
        bad["SOVEREIGN_CHANGED:" + k] += 1
print("combinations:", n, " with an unknown origin (independent definition):", unknown_n)
print("unknown-origin combinations by outcome:", dict(sorted(unknown_hist.items(), key=lambda kv: str(kv[0]))))
print("BAD (unknown origin and an answer / pass-through / confirm / reference / kept source / leaked record / sovereign changed):", dict(bad))
for e in bad_examples:
    print("  example:", e)
print("other combinations (no unknown origin) by outcome:", dict(sorted(other_hist.items(), key=lambda kv: str(kv[0]))))
print("ANSWER_HUMAN_BASIS among them that no declared reason explains:", sum(unexplained.values()), dict(unexplained))
print("sovereign files hashed at start and end:", {k: len(v) for k, v in before.items()}, "unchanged:", before == after)
