#!/usr/bin/env python3
"""Mechanical check of the long-story banks (bank_ls/{dev,heldout_1,heldout_2}/stories.jsonl).

  python3 check_ls.py <split-dir> [<split-dir> ...]      # per-story checks of every given split
  python3 check_ls.py --cross dev heldout_1 heldout_2    # no sentence / question / title / scenario shared between stories or splits

Per story it verifies the spec of docs/LINE3_PUBLIC_DESIGN.md 6.1 / 6.6 as the author brief set it (counts of sessions, messages and
sentences; plant counts and forms; plant spread over the checkpoints; question counts per checkpoint and kind; golds; refs; phrasing form;
absent facts; ledger consistency; share of sentences with no subject of their own).  It reads only the story file and runs no Vera system.
It prints counts only (no story text) unless an error is found.
"""
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLANTS = {"contradiction": 12, "update": 8, "reversal": 4, "list_trap": 8, "repeat": 6}
CUM_CONTRA = [3, 6, 9, 12]
CUM_UPD = [2, 4, 6, 8]
PER_CP = {"plain": 3, "contradiction": 3, "update": 2, "absent": 2}
FRACS = [0.25, 0.5, 0.75, 1.0]
MARKER = re.compile(r"訂正|改めて|今回の|最新|変更|延期|から.{1,30}?(へ|に)(移|改|引き上げ|引き下げ)")
UPDATE_MARK = re.compile(r"から.+?(へ|に).*?(変更|延期|更新|改訂|引き上げ|引き下げ|移|切り替|差し替|繰り上げ|繰り下げ|改め|延び|上が|下が|ずれ|早ま|遅れ|直|変わ|替わ|なった|なりました|した|します)")


def sents(text):
    return [s.strip() for s in re.split(r"(?<=。)", text) if s.strip()]


def check_story(r, errors, info):
    t = r.get("id", "?")

    def e(m):
        errors.append(f"{t}: {m}")

    S = r["sessions"]
    n = len(S)
    if not 10 <= n <= 20:
        e(f"{n} sessions")
    allsent = 0
    for si, s in enumerate(S):
        if not 8 <= len(s) <= 25:
            e(f"session {si} has {len(s)} messages")
        for mi, m in enumerate(s):
            if set(m) != {"speaker", "text"} or not m["speaker"].strip() or not m["text"].strip():
                e(f"malformed message [{si},{mi}]")
                continue
            if not m["text"].endswith("。"):
                e(f"message [{si},{mi}] does not end in 。")
            allsent += len(sents(m["text"]))
    if not 600 <= allsent <= 1000:
        e(f"{allsent} sentences")
    full = "\n".join(m["text"] for s in S for m in s)

    def txt(ref, lab):
        s, i = ref
        if not (0 <= s < n and 0 <= i < len(S[s])):
            e(f"{lab}: bad ref {ref}")
            return ""
        return S[s][i]["text"]

    # checkpoints
    cps = r.get("checkpoints", [])
    after = []
    if len(cps) != 4:
        e(f"{len(cps)} checkpoints")
    for k, c in enumerate(cps):
        want = math.ceil(n * FRACS[k]) - 1
        if c.get("index") != k or abs(c.get("fraction", 0) - FRACS[k]) > 1e-9 or c.get("after_session") != want:
            e(f"checkpoint {k} is {c}, want after_session {want}")
        after.append(c.get("after_session", -1))

    # plants
    pc = Counter(p["kind"] for p in r["plants"])
    if dict(pc) != PLANTS:
        e(f"plant counts {dict(pc)} want {PLANTS}")
    contra_done, upd_done = [], []
    planted_vals = {}  # (ref tuple, value) of contradicted / updated slots
    for j, p in enumerate(r["plants"]):
        k, v, refs, lab = p["kind"], p["values"], [tuple(x) for x in p["message_refs"]], f"plant {j} ({p['kind']})"
        texts = [txt(x, lab) for x in refs]
        if k in ("contradiction", "reversal"):
            if len(v) != 2 or len(refs) != 2 or v[0] == v[1]:
                e(f"{lab}: needs 2 distinct values and 2 refs")
                continue
            if refs[0] >= refs[1]:
                e(f"{lab}: refs not in message order")
            for i in (0, 1):
                if v[i] not in texts[i]:
                    e(f"{lab}: value {v[i]!r} not in ref {refs[i]}")
                vs = [x for x in sents(texts[i]) if v[i] in x]
                if k == "contradiction" and any(MARKER.search(x) for x in vs):
                    e(f"{lab}: the sentence of ref {refs[i]} carrying the value has an update/scope marker")
            if k == "contradiction":
                contra_done.append(max(refs[0][0], refs[1][0]))
                planted_vals.update({(refs[0], v[0]): j, (refs[1], v[1]): j})
            else:
                for i in (0, 1):
                    if v[1 - i] in texts[i]:
                        e(f"{lab}: ref {refs[i]} also states the opposite direction")
                a = re.match(r"(.+)は(.+)の前提$", v[0])
                if not a or v[1] != f"{a.group(2)}は{a.group(1)}の前提":
                    e(f"{lab}: values are not the same pair reversed")
        elif k == "update":
            old = [tuple(x) for x in p.get("old_refs", [])]
            if len(v) != 2 or len(refs) != 1 or not old:
                e(f"{lab}: needs old,new, 1 ref and old_refs")
                continue
            tx = texts[0]
            if not (v[0] in tx and v[1] in tx and UPDATE_MARK.search(tx) and tx.index(v[0]) < tx.index(v[1])):
                e(f"{lab}: ref lacks 'old から new + marker'")
            for o in old:
                if o >= refs[0] or v[0] not in txt(o, lab):
                    e(f"{lab}: old_ref {o} is not an earlier message holding the old value")
            for si in range(refs[0][0] + 1):
                for mi, m in enumerate(S[si]):
                    if (si, mi) < refs[0] and re.search(r"(?<![0-9])" + re.escape(v[1]) + r"(?![0-9])", m["text"]):
                        e(f"{lab}: new value {v[1]!r} already stated at [{si},{mi}]")
            upd_done.append(refs[0][0])
            planted_vals.update({(o, v[0]): j for o in old})
            planted_vals[(refs[0], v[1])] = j
        elif k == "list_trap":
            if len(refs) < 2 or len(v) < 2:
                e(f"{lab}: needs >= 2 refs and 2 values (the two look-alike facts may share a value)")
            for val in v:
                if not any(val in tx for tx in texts):
                    e(f"{lab}: {val!r} in no ref")
        elif k == "repeat":
            if len(v) != 1 or len(refs) < 2 or len({x[0] for x in refs}) < 2:
                e(f"{lab}: needs 1 value restated across >= 2 sessions")
                continue
            ss = set()
            for x, tx in zip(refs, texts):
                hit = [s for s in sents(tx) if v[0] in s]
                if len(hit) != 1:
                    e(f"{lab}: value not in exactly one sentence of {x}")
                ss.update(hit)
            if len(ss) != 1:
                e(f"{lab}: restatements not identical")
            else:
                sen = next(iter(ss))
                occ = sorted((si, mi) for si, s in enumerate(S) for mi, m in enumerate(s) if sen in m["text"])
                if occ != sorted(refs):
                    e(f"{lab}: occurrences {occ} != refs {sorted(refs)}")
        else:
            e(f"{lab}: unknown kind")
    for c, (a_ct, a_up) in enumerate(zip(CUM_CONTRA, CUM_UPD)):
        if c < len(after):
            if sum(1 for x in contra_done if x <= after[c]) < a_ct:
                e(f"fewer than {a_ct} contradictions completed by checkpoint {c}")
            if sum(1 for x in upd_done if x <= after[c]) < a_up:
                e(f"fewer than {a_up} updates completed by checkpoint {c}")

    # ledger
    led = r.get("ledger", [])
    byslot = defaultdict(set)
    slot_of = {}
    for x in led:
        ref = tuple(x["ref"])
        if x["value"] not in txt(ref, "ledger"):
            e(f"ledger value {x['value']!r} not in {ref}")
        byslot[x["slot"]].add(x["value"])
        slot_of[(ref, x["value"])] = x["slot"]
    planted_slots = {slot_of[kv] for kv in planted_vals if kv in slot_of}
    for p in r["plants"]:  # a reversal states one pair in two directions: its slots legitimately carry two values
        if p["kind"] == "reversal":
            for x in p["message_refs"]:
                for v in p["values"]:
                    if (tuple(x), v) in slot_of:
                        planted_slots.add(slot_of[(tuple(x), v)])
    for kv in planted_vals:
        if kv not in slot_of:
            e(f"ledger lacks the planted statement {kv}")
    for slot, vs in byslot.items():
        if len(vs) > 1 and slot not in planted_slots:
            e(f"ledger slot {slot!r} has {len(vs)} values and is not a planted contradiction/update")
    if len(led) < 150:
        info.append(f"{t}: ledger has only {len(led)} entries")

    # subject-less
    sl = r.get("subjectless_refs", [])
    cnt = 0
    for s_, i_, k_ in sl:
        tx = txt((s_, i_), "subjectless")
        ss = sents(tx)
        if not 0 <= k_ < len(ss):
            e(f"subjectless ref {[s_, i_, k_]} out of range")
        else:
            cnt += 1
    share = len(set(map(tuple, sl))) / max(allsent, 1)
    if share < 0.30:
        e(f"subject-less share {share:.2f} < 0.30")

    # questions
    qs = r["questions"]
    if len(qs) != 40:
        e(f"{len(qs)} questions")
    per = defaultdict(Counter)
    used = Counter()
    nonabs = defaultdict(lambda: [0, 0])
    plain_trap = 0
    for j, q in enumerate(qs):
        lab = f"Q{j}"
        k, g, refs, c = q["kind"], q["gold"], [tuple(x) for x in q.get("refs", [])], q.get("checkpoint")
        if k not in PER_CP or c not in (0, 1, 2, 3):
            e(f"{lab}: bad kind/checkpoint {k}/{c}")
            continue
        per[c][k] += 1
        qt = q["q"]
        if not qt.endswith("？"):
            e(f"{lab}: does not end in ？")
        if re.search(r"矛盾|食い違|変更後|変更された|変わった|最新|言われていない|書かれていない|二つ|両方", qt):
            e(f"{lab}: question announces its kind")
        if re.search(r"記録(され|上|では)", qt):
            info.append(f"{t}: Q{j} says 記録されて/上/では (mild kind hint)")
        for x in refs:
            if x[0] > after[c]:
                e(f"{lab}: ref {x} after checkpoint {c}")
        texts = [txt(x, lab) for x in refs]
        if k == "contradiction":
            m = [(i, p) for i, p in enumerate(r["plants"]) if p["kind"] == "contradiction" and [tuple(x) for x in p["message_refs"]] == refs]
            if len(m) != 1 or g != f"矛盾: {m[0][1]['values'][0]} と {m[0][1]['values'][1]}":
                e(f"{lab}: gold does not match a contradiction plant on the same refs")
            else:
                used[m[0][0]] += 1
        elif k == "update":
            m = [(i, p) for i, p in enumerate(r["plants"]) if p["kind"] == "update" and [tuple(x) for x in p["message_refs"]] == refs]
            if len(m) != 1 or g != m[0][1]["values"][1]:
                e(f"{lab}: gold is not the new value of an update plant on the same refs")
            else:
                used[m[0][0]] += 1
        elif k == "plain":
            if not refs or not any(g in tx for tx in texts):
                e(f"{lab}: plain gold not in its refs")
            for p in r["plants"]:
                if p["kind"] in ("contradiction", "update") and g in p["values"] and any(tuple(x) in refs for x in p["message_refs"]):
                    e(f"{lab}: plain gold is a contradicted/updated value")
            for i, p in enumerate(r["plants"]):
                if p["kind"] == "list_trap" and g in p["values"] and any(tuple(x) in refs for x in p["message_refs"]):
                    plain_trap += 1
                    break
        else:  # absent
            if g != "記録なし" or refs:
                e(f"{lab}: absent needs gold 記録なし and no refs (refs may only repeat subject_refs: normalised at packaging)")
            if not q.get("subject_refs"):
                e(f"{lab}: absent lacks subject_refs")
            for x in q.get("subject_refs", []):
                txt(tuple(x), lab)
            terms = q.get("absent_terms") or []
            if not terms:
                e(f"{lab}: absent lacks absent_terms")
            for term in terms:
                if term in full:
                    e(f"{lab}: absent term {term!r} occurs in the story")
        if k != "absent":
            if g in qt:
                e(f"{lab}: gold in the question")
            for gv in (g.replace("矛盾: ", "").split(" と ") if k == "contradiction" else [g]):
                if gv in qt:
                    e(f"{lab}: gold value {gv!r} in the question")
            ss_, as_, f_ = q.get("stored_slot", ""), q.get("asked_slot", ""), q.get("form")
            if not ss_ or not any(ss_ in tx for tx in texts):
                e(f"{lab}: stored_slot {ss_!r} not in its refs")
            if f_ == "same":
                if ss_ not in qt:
                    e(f"{lab}: form same but stored_slot not in the question")
            elif f_ == "rephrased":
                if ss_ in qt or not as_ or as_ not in qt or any(as_ in tx for tx in texts):
                    e(f"{lab}: form rephrased violated (stored in q / asked missing / asked in refs)")
                nonabs[c][1] += 1
            else:
                e(f"{lab}: form {f_!r}")
            nonabs[c][0] += 1
        elif q.get("form") != "absent":
            e(f"{lab}: absent form must be 'absent'")
    for c in range(4):
        if dict(per[c]) != PER_CP:
            e(f"checkpoint {c} kinds {dict(per[c])} want {PER_CP}")
        if nonabs[c][1] < 4:
            e(f"checkpoint {c}: {nonabs[c][1]} rephrased of {nonabs[c][0]} (< 4)")
    reph = sum(v[1] for v in nonabs.values())
    nn = sum(v[0] for v in nonabs.values())
    if reph * 2 < nn:
        e(f"rephrased {reph}/{nn} < half")
    for i, p in enumerate(r["plants"]):
        if p["kind"] in ("contradiction", "update") and used[i] != 1:
            e(f"plant {i} ({p['kind']}) asked {used[i]} times, want 1")
    if plain_trap < 4:
        e(f"only {plain_trap} plain questions on enumeration-trap facts (< 4)")
    return dict(id=t, sessions=n, messages=sum(len(s) for s in S), sentences=allsent, subjectless=round(share, 3),
                plants=dict(pc), questions=dict(Counter(q["kind"] for q in qs)), rephrased=f"{reph}/{nn}", plain_on_traps=plain_trap,
                ledger=len(led))


def split_checks(dirs):
    errors, info, rows = [], [], []
    for d in dirs:
        f = Path(d) / "stories.jsonl"
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                row = check_story(r, errors, info)
                if row:
                    rows.append((str(d), row))
    return errors, info, rows


def cross(dirs):
    errors, info = [], []
    sent_home, q_home, title_home, spk_home = {}, {}, {}, defaultdict(set)
    nsent = 0
    for d in dirs:
        for line in (Path(d) / "stories.jsonl").read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            me = f"{d}/{r['id']}"
            if r["title"] in title_home:
                errors.append(f"title {r['title']!r} in {me} and {title_home[r['title']]}")
            title_home[r["title"]] = me
            for s in r["sessions"]:
                for m in s:
                    spk_home[m["speaker"]].add(me)
                    for st in sents(m["text"]):
                        st = st.strip()
                        if len(st) < 8:
                            continue
                        nsent += 1
                        if st in sent_home and sent_home[st] != me:
                            errors.append(f"sentence shared by {me} and {sent_home[st]}: {st[:40]}...")
                        sent_home.setdefault(st, me)
            for q in r["questions"]:
                if q["q"] in q_home and q_home[q["q"]] != me:
                    errors.append(f"question shared by {me} and {q_home[q['q']]}: {q['q'][:40]}")
                q_home.setdefault(q["q"], me)
    # scenario overlap: shared character 14-grams between two stories (as a share of the smaller story's 14-grams)
    grams = {}
    for d in dirs:
        for line in (Path(d) / "stories.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                t = "".join(m["text"] for s in r["sessions"] for m in s)
                grams[f"{d}/{r['id']}"] = {t[i:i + 14] for i in range(len(t) - 13)}
    names = sorted(grams)
    worst = 0.0
    for i, x in enumerate(names):
        for y in names[i + 1:]:
            sh = len(grams[x] & grams[y]) / max(1, min(len(grams[x]), len(grams[y])))
            worst = max(worst, sh)
            if sh > 0.05:
                errors.append(f"stories {x} and {y} share {sh:.1%} of their 14-grams")
    info.append(f"largest shared-14-gram share between two stories: {worst:.2%}")
    shared = {s: h for s, h in spk_home.items() if len(h) > 1}
    info.append(f"{nsent} sentences (>= 8 chars) compared; {len(q_home)} distinct questions; speakers shared by more than one story: {len(shared)}")
    return errors, info, shared


def main():
    a = sys.argv[1:]
    if a and a[0] == "--cross":
        dirs = [HERE / x for x in a[1:]]
        errors, info, shared = cross(dirs)
        print("cross-split check:", " ".join(a[1:]))
        for x in info:
            print("INFO", x)
        for s, h in sorted(shared.items()):
            print("INFO speaker", s, "in", sorted(h))
    else:
        dirs = [HERE / x if not Path(x).is_absolute() else Path(x) for x in a]
        errors, info, rows = split_checks(dirs)
        for d, row in rows:
            print(Path(d).name, json.dumps(row, ensure_ascii=False))
        for x in info:
            print("INFO", x)
    if errors:
        print(f"FAIL ({len(errors)} errors)")
        for x in errors[:200]:
            print("-", x)
        return 1
    print("PASS (0 errors)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
