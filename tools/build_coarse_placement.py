#!/usr/bin/env python
"""Build the coarse placement (W3-a).  Sub-commands:

  holdout   draw the 2,000 held-out sentences (not used as material)
  build     build a placement directory from the material
  verify    recompute counts and content_sha256 of a placement

The build is deterministic: the same inputs and arguments give the same
``content_sha256`` (a hash over the tables in a fixed order; the sqlite file
bytes are NOT compared).  Nothing here uses a weight, a trained model, an
external dictionary or an LLM: the morphological analyser is used only for
word segmentation and the coarse grammatical class (pos1 / pos2 / orthBase).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from verantyx import coarse_types as ct  # noqa: E402
from verantyx.coarse_types import arm_top, combine_arms  # noqa: E402,F401  (one shared rule)

HOLDOUT_SEED = 20261003
EXIT_STAGE_CACHE_STALE = 4      # the extraction cache lacks the argument chains (W3-a3)
FAMILIES_DEFAULT = ["code", "code_qa", "conversation", "figurative_commonsense",
                    "general_qa", "narrative", "paraphrase_entail", "pro"]

_OPEN = {"（": "）", "(": ")", "「": "」", "『": "』", "［": "］", "[": "]",
         "【": "】"}
_CLOSE = {v: k for k, v in _OPEN.items()}
_JA = re.compile(r"[぀-ヿ㐀-鿿]")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# --- sentences -----------------------------------------------------------------
def first_sentence(text: str) -> str:
    """Up to the first full stop that is outside every bracket pair
    (「」『』（）() [] 【】); the whole text when there is none."""
    depth = 0
    for i, ch in enumerate(text):
        if ch in _OPEN:
            depth += 1
        elif ch in _CLOSE:
            depth = max(0, depth - 1)
        elif ch == "。" and depth == 0:
            return text[: i + 1]
    return text


def strip_parens(s: str) -> str:
    """Remove （…） and (…) groups (nested ones too)."""
    out, depth = [], 0
    for ch in s:
        if ch in "（(":
            depth += 1
        elif ch in "）)":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return "".join(out)


# --- holdout ---------------------------------------------------------------------
def _codex_counts(codex_dir: str, families: Sequence[str]):
    out = []
    for fam in families:
        p = os.path.join(codex_dir, fam + ".db")
        con = sqlite3.connect("file:%s?mode=ro" % p, uri=True)
        n, lo, hi = con.execute("SELECT COUNT(*), MIN(id), MAX(id) FROM rows"
                                ).fetchone()
        out.append((fam, p, n, lo, hi))
        con.close()
    return out


def cmd_holdout(args) -> int:
    t0 = time.time()
    seed = getattr(args, "seed", None) or HOLDOUT_SEED
    avoid_j, avoid_c = set(), set()
    for ap_ in getattr(args, "avoid", None) or []:
        for line in open(ap_, encoding="utf-8"):
            r = json.loads(line)
            if r["source"] == "jawiki":
                avoid_j.add(r["line"])
            else:
                avoid_c.add((r["family"], r["rowid"]))
    rng = random.Random(seed)
    # jawiki: lines that have a body (redirect rows have none)
    body_lines: List[int] = []
    with open(args.jawiki, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if '"text"' in line and '"redirect"' not in line[:200]:
                d = json.loads(line)
                if "text" in d:
                    body_lines.append(i)
    body_lines = [i for i in body_lines if i not in avoid_j]
    picks = rng.sample(body_lines, args.n_jawiki)
    wanted = set(picks)
    jrows = {}
    with open(args.jawiki, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i in wanted:
                d = json.loads(line)
                jrows[i] = {"source": "jawiki", "line": i, "sha": d.get("sha"),
                            "title": d.get("title"),
                            "sentence": first_sentence(d["text"])}
    out_rows = [jrows[i] for i in picks]
    # codex: global order = (family name, rowid); a seeded shuffle of it
    counts = _codex_counts(args.codex_dir, FAMILIES_DEFAULT)
    total = sum(c[2] for c in counts)
    order = list(range(total))
    random.Random(seed).shuffle(order)
    starts, acc = [], 0
    for fam, p, n, lo, hi in counts:
        starts.append(acc)
        acc += n
    cons = {c[0]: sqlite3.connect("file:%s?mode=ro" % c[1], uri=True)
            for c in counts}
    contiguous = {c[0]: (c[4] - c[3] + 1 == c[2]) for c in counts}
    skipped_no_ja = 0
    got: List[dict] = []
    for g in order:
        if len(got) >= args.n_codex:
            break
        # locate family
        fi = 0
        for k in range(len(counts)):
            if g >= starts[k]:
                fi = k
        fam, p, n, lo, hi = counts[fi]
        off = g - starts[fi]
        con = cons[fam]
        if contiguous[fam]:
            rid = lo + off
        else:
            rid = con.execute("SELECT id FROM rows ORDER BY id LIMIT 1 OFFSET ?",
                              (off,)).fetchone()[0]
        r = con.execute("SELECT id, text, body_sha FROM rows WHERE id=?",
                        (rid,)).fetchone()
        if r is None or (fam, rid) in avoid_c:
            continue
        first_line = r[1].split("\n", 1)[0]
        sent = first_sentence(first_line)
        if not _JA.search(sent):
            skipped_no_ja += 1
            continue
        got.append({"source": "codex", "family": fam, "rowid": r[0],
                    "body_sha": r[2], "sentence": sent})
    for c in cons.values():
        c.close()
    out_rows += got
    with open(args.out, "w", encoding="utf-8") as f:
        for r in out_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    meta = {"seed": seed, "n_jawiki": args.n_jawiki,
            "n_codex": len(got), "jawiki_body_lines": len(body_lines),
            "codex_total_rows": total, "codex_skipped_no_japanese": skipped_no_ja,
            "seconds": round(time.time() - t0, 1), "out_sha256": sha256_file(args.out)}
    print(json.dumps(meta, ensure_ascii=False, indent=1))
    return 0

# =====================================================================================
# extraction (worker side)
# =====================================================================================
NOUN_POS2 = ("普通名詞", "固有名詞", "数詞")
ROLES = set(ct.ROLE_PARTICLES)
COORD = {"、", "・", "や", "および", "及び", "または", "又は", "もしくは",
         "若しくは", "かつ", "兼", "と", "，"}
#: Conjunctions that may stand between two parallel hypernyms ("者、もしくはグループ"):
#: a comma may precede them, and the run in front of them is a parallel hypernym too.
CONJ_WORDS = {"もしくは", "若しくは", "または", "又は", "あるいは", "ないし", "および", "及び"}
#: Case particles: a noun run right after one of these, followed by a comma, is an
#: adverbial phrase ("平安から鎌倉時代、…"), not the thing the sentence says X is.
CASE_PARTICLES = {"から", "まで", "より", "に", "で", "へ", "と", "を", "が"}
_COMMAS = ("、", "，")
_TITLE_QUAL = re.compile(r"^(.*\S)\s*[\(（]([^()（）]+)[\)）]\s*$")
_META_TITLE = re.compile(
    r"^(Wikipedia|Category|Template|File|Portal|Help|Project|MediaWiki|"
    r"プロジェクト|利用者|ノート|ファイル|カテゴリ|テンプレート|ヘルプ|Wikipedia‐)[:：]")
_LOG_TITLE = re.compile(r"/(log\d+|Log.*|\d{8})$")
_TAGGER = None
_WCFG: dict = {}
_EXCL_RE = None
_EXCL_TERMS: List[str] = []


_HASH_CACHE_FILE: Optional[str] = None


def cached_sha(path: str) -> str:
    """sha256 of a (large) input, cached by (path, size, mtime) next to the
    output directory so repeated dev builds do not re-read 12 GB."""
    st = os.stat(path)
    key = "%s|%d|%d" % (os.path.abspath(path), st.st_size, int(st.st_mtime))
    cache = {}
    if _HASH_CACHE_FILE and os.path.exists(_HASH_CACHE_FILE):
        try:
            cache = json.load(open(_HASH_CACHE_FILE, encoding="utf-8"))
        except ValueError:
            cache = {}
    if key in cache:
        return cache[key]
    h = sha256_file(path)
    if _HASH_CACHE_FILE:
        cache[key] = h
        with open(_HASH_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    return h


def _worker_init(cfg: dict, excl_terms: List[str]):
    global _TAGGER, _WCFG, _EXCL_RE, _EXCL_TERMS
    import fugashi
    _TAGGER = fugashi.Tagger()
    _WCFG = cfg
    _EXCL_TERMS = list(excl_terms)
    if excl_terms:
        _EXCL_RE = re.compile("|".join(
            re.escape(t) for t in sorted(excl_terms, key=len, reverse=True)))
    else:
        _EXCL_RE = None


def tokenize(tagger, text: str) -> List[Tuple[str, str, str, Optional[str]]]:
    out = []
    for w in tagger(text):
        f = w.feature
        out.append((w.surface, f.pos1 or "", f.pos2 or "", f.orthBase))
    return out


def _is_noun(t) -> bool:
    return t[1] == "名詞" and t[2] in NOUN_POS2


def analyze(toks, acc: dict, maxc: int) -> None:
    """Count, for one tokenised text: noun-run words with their particle
    context and the first verb after, verbal-noun (+する) uses, the coarse
    grammatical class of every content word, and the units that follow a
    number (counter candidates)."""
    occ, pos, sahen, counters = acc["occ"], acc["pos"], acc["sahen"], acc["counters"]
    counters2 = acc["counters2"]
    hearst = acc["hearst"]
    n = len(toks)
    _hearst_scan(toks, hearst, maxc)
    i = 0
    while i < n:
        t = toks[i]
        s, p1, p2, ob = t
        starts_run = _is_noun(t) or (
            p1 == "接頭辞" and i + 1 < n and _is_noun(toks[i + 1]))
        if starts_run:
            j = i
            while j < n:
                u = toks[j]
                if _is_noun(u):
                    j += 1
                elif u[1] == "接尾辞" and u[2] == "名詞的" and j > i:
                    j += 1
                elif u[1] == "接頭辞" and j == i:
                    j += 1
                else:
                    break
            run = toks[i:j]
            nx = toks[j] if j < n else None
            role = ""
            k0 = j
            if nx is not None and nx[1] == "助詞" and nx[0] in ROLES:
                role = nx[0]
                k0 = j + 1
            pred = ""
            if role:
                for k in range(k0, min(n, k0 + 12)):
                    v = toks[k]
                    if v[1] == "補助記号" and v[2] == "句点":
                        break
                    if v[1] == "動詞":
                        pred = v[3] or v[0]
                        break
            is_sahen = False
            if nx is not None:
                if nx[1] == "動詞" and (nx[3] == "する"):
                    is_sahen = True
                elif (nx[0] == "を" and j + 1 < n and toks[j + 1][1] == "動詞"
                      and toks[j + 1][3] == "する"):
                    is_sahen = True
            words = []
            # counter candidates: the unit(s) right after a numeral token
            for q in range(1, len(run)):
                if (run[q - 1][2] == "数詞" and run[q][2] != "数詞"
                        and run[q - 1][0][:1] in "0123456789０１２３４５６７８９"):
                    counters[run[q][0]] += 1            # one morpheme after the numeral
                    if run[q][0].isascii():
                        # which numerals a Latin unit follows (how many different ones)
                        ns_ = acc.setdefault("counter_nums", {}).setdefault(run[q][0], set())
                        if len(ns_) < NUMS_CAP:
                            ns_.add(run[q - 1][0])
                    if q + 1 < len(run) and run[q + 1][2] != "数詞":
                        counters2[run[q][0] + run[q + 1][0]] += 1   # two morphemes: its own table
            if run[0][2] == "数詞":
                pass
            elif len(run) == 1:
                words.append(run[0][3] or run[0][0])
            else:
                rw = "".join(x[0] for x in run)
                if len(rw) <= maxc and ct.notation_type(rw) is None:
                    words.append(rw)
                last = run[-1]
                if _is_noun(last) and last[2] != "数詞":
                    words.append(last[3] or last[0])
                for x in run[:-1]:
                    if _is_noun(x) and x[2] != "数詞":
                        pos[(x[3] or x[0], "N")] += 1
            for w in words:
                if not w or len(w) > maxc:
                    continue
                pos[(w, "N")] += 1
                if role:
                    occ[(w, role, pred)] += 1
                if is_sahen:
                    sahen[w] += 1
            _chain_count(toks, run, j, acc, maxc)
            i = j
            continue
        if p1 in ("動詞", "形容詞") or (p1 == "形状詞" and p2 == "一般"):
            prev = toks[i - 1] if i else None
            skip = False
            if (p1 in ("動詞", "形容詞") and prev is not None
                    and prev[1] == "助詞" and prev[2] == "接続助詞"
                    and prev[0] in ("て", "で")):
                skip = True
            elif p1 == "動詞" and ob == "する" and prev is not None \
                    and prev[1] == "名詞":
                skip = True
            if not skip:
                w = ob or s
                if len(w) <= maxc:
                    pos[(w, {"動詞": "V", "形容詞": "A", "形状詞": "S"}[p1])] += 1
        i += 1


#: auxiliaries (base forms) that change the voice: a predicate followed by one of them is not counted
VOICE_AUX = ("れる", "られる", "せる", "させる")
_CHAIN_ARGS_MAX = 3


def _run_end(toks, i: int) -> Optional[int]:
    """End (exclusive) of the noun run that starts at ``i`` (the same cut ``analyze`` makes), or None."""
    n = len(toks)
    if i >= n:
        return None
    t = toks[i]
    if not (_is_noun(t) or (t[1] == "接頭辞" and i + 1 < n and _is_noun(toks[i + 1]))):
        return None
    j = i
    while j < n:
        u = toks[j]
        if _is_noun(u):
            j += 1
        elif u[1] == "接尾辞" and u[2] == "名詞的" and j > i:
            j += 1
        elif u[1] == "接頭辞" and j == i:
            j += 1
        else:
            break
    return j


def _chain_count(toks, run, j: int, acc: dict, maxc: int) -> None:
    """W3-a3 12.3: the argument chain of one noun run (``toks[:j]`` ends with it).  When the run is
    followed by one of the nine case particles or by a comma (the mark m), look to the right, neighbours
    only: up to three more ``noun run + case particle`` pairs, then a verb.  Anything else breaks the
    chain; the reason is counted (``chain_skips``).  A counted chain is ``(filler run, filler head, m,
    verb, past)``.  A voice auxiliary after the verb (れる られる せる させる) is not counted, nor is a
    verbal noun + する (``sahen``: the last noun run is followed straight by する)."""
    n = len(toks)
    nx = toks[j] if j < n else None
    if nx is None:
        return
    if nx[1] == "助詞" and nx[0] in ct.CASE_PARTICLES_9:
        m = nx[0]
    elif nx[1] == "補助記号" and nx[0] in _COMMAS:
        m = "∅"
    else:
        return
    skips = acc["chain_skips"]
    if run[0][2] == "数詞":
        skips["numeral_start"] += 1
        return
    # the filler: the whole run (when it is a word of the same cut as ``occ``) and its last noun
    if len(run) == 1:
        fh = run[0][3] or run[0][0]
        fr = fh
    else:
        rw = "".join(x[0] for x in run)
        fr = rw if (len(rw) <= maxc and ct.notation_type(rw) is None) else ""
        last = run[-1]
        fh = (last[3] or last[0]) if (_is_noun(last) and last[2] != "数詞") else ""
    if (not fr and not fh) or len(fr) > maxc or len(fh) > maxc:
        skips["no_filler"] += 1
        return
    k = j + 1
    pairs = 0
    while True:
        if k >= n:
            skips["no_verb"] += 1
            return
        t = toks[k]
        if t[1] == "動詞":
            break
        if t[1] == "補助記号" and t[2] == "句点":
            skips["no_verb"] += 1
            return
        e = _run_end(toks, k)
        if e is not None and e < n and toks[e][1] == "動詞" and toks[e][3] == "する":
            skips["sahen"] += 1         # a verbal noun right before する: the verb is "noun + する", not する
            return
        if e is None or e >= n or toks[e][1] != "助詞" or toks[e][0] not in ct.CASE_PARTICLES_9:
            skips["chain_broken"] += 1
            return
        pairs += 1
        if pairs > _CHAIN_ARGS_MAX:
            skips["too_many_args"] += 1
            return
        k = e + 1
    v = toks[k]
    aux = []
    q = k + 1
    while q < n and toks[q][1] == "助動詞":
        aux.append(toks[q][3] or toks[q][0])
        q += 1
    if any(a in VOICE_AUX for a in aux):
        skips["voice"] += 1
        return
    acc["chain"][(fr, fh, m, v[3] or v[0], "た" in aux)] += 1
    skips["counted"] += 1


def _hearst_scan(toks, hearst: Counter, maxc: int) -> None:
    """"AやBなどのY" / "AやBといったY": (A, Y) and (B, Y) are hypernym pairs
    read from running text (an evidence arm of its own, counted per source)."""
    n = len(toks)
    for idx in range(1, n):
        t = toks[idx]
        if t[0] == "など" and t[1] == "助詞":
            lend, j = idx, idx + 1
            if j < n and toks[j][0] == "の" and toks[j][1] == "助詞":
                j += 1
        elif (t[0] == "いっ" and t[1] == "動詞" and toks[idx - 1][0] == "と"
              and idx + 2 < n and toks[idx + 1][0] == "た" and idx >= 2):
            lend, j = idx - 1, idx + 2
        else:
            continue
        k = j
        while k < n and (_is_noun(toks[k]) or (toks[k][1] == "接尾辞" and toks[k][2] == "名詞的")):
            k += 1
        if k == j:
            continue
        y = "".join(x[0] for x in toks[j:k])
        if (len(y) > maxc or y in ct.GENERIC_HEADS or y in ct.META_HEADS
                or toks[j][2] == "数詞"):
            continue
        for a in _tail_runs(toks, lend):
            if a and a != y and len(a) <= maxc and ct.notation_type(a) is None:
                hearst[(a, y)] += 1


def _empty_acc() -> dict:
    return {"occ": Counter(), "pos": Counter(), "sahen": Counter(),
            "counters": Counter(), "counters2": Counter(), "hearst": Counter(),
            "counter_nums": {}, "chain": Counter(), "chain_skips": Counter()}


#: ``counter_nums`` keeps at most this many distinct numerals per Latin unit (only the
#: number of them is read, and only up to ``counter_latin_numerals_min``: a cap above that
#: does not change a result, whatever order the pieces are merged in)
NUMS_CAP = 32


def _merge_nums(dst: dict, src: dict) -> None:
    """Merge ``counter_nums`` tables (unit -> set of numeral spellings), capped."""
    for u, vs in src.items():
        d = dst.setdefault(u, set())
        d |= vs
        if len(d) > NUMS_CAP:
            dst[u] = set(sorted(d)[:NUMS_CAP])


def _coord_before(toks, k: int) -> Optional[int]:
    """The end (exclusive) of the noun run that is coordinated with the run that
    starts at ``k``, or None.  An ordinary coordinator (、 ・ や と …) needs a noun
    right before it; a conjunction (もしくは・または・あるいは・ないし・および・並びに …)
    may follow a comma ("者、もしくはグループ"), and also stands alone."""
    j = k - 1
    if j < 0:
        return None
    t = toks[j]
    conj_at = None
    if t[0] in CONJ_WORDS:
        conj_at = j
    elif t[0] == "は" and t[1] == "助詞" and j >= 1 and toks[j - 1][0] == "また":
        conj_at = j - 1                              # また + は  (または)
    elif t[0] == "に" and t[1] == "助詞" and j >= 1 and toks[j - 1][0] == "並び":
        conj_at = j - 1                              # 並び + に  (並びに)
    if conj_at is not None:
        i = conj_at
        if i >= 1 and toks[i - 1][0] in _COMMAS:
            i -= 1
        if i >= 1 and (_is_noun(toks[i - 1]) or toks[i - 1][1] == "接尾辞"):
            return i
        return None
    if t[0] in COORD and j >= 1 and (_is_noun(toks[j - 1]) or toks[j - 1][1] == "接尾辞"):
        return j
    return None


def _tail_runs(toks, end: int) -> List[str]:
    """Hypernym phrases ending at ``end`` (exclusive): the last noun run, then
    coordinated runs before it (、 ・ や および もしくは …).  A generic head
    (一種・一つ・こと …) is replaced by the run before its の."""
    ys: List[str] = []
    e = end
    guard = 0
    while e > 0 and guard < 8:
        guard += 1
        # find run ending at e
        k = e
        while k > 0 and (_is_noun(toks[k - 1])
                         or (toks[k - 1][1] == "接尾辞" and toks[k - 1][2] == "名詞的")
                         or (toks[k - 1][1] == "接頭辞")):
            k -= 1
        if k == e:
            break
        run = toks[k:e]
        y = "".join(x[0] for x in run)
        if y in ct.GENERIC_HEADS:
            # "Y の 一種": step back over の
            if k >= 2 and toks[k - 1][0] == "の" and toks[k - 1][1] == "助詞":
                e = k - 1
                continue
            break
        if not any(_is_noun(x) for x in run):
            break
        ys.append(y)
        # coordination before this run?
        ce = _coord_before(toks, k)
        if ce is not None:
            e = ce
            continue
        break
    return ys


def first_clause_phrases(tagger, sentence: str) -> List[str]:
    """Fallback when the sentence does not END in a noun phrase ("X は、Yであり、
    …"): after the first topic は, the first noun phrase that is followed by the
    copula (で/だ/です as an auxiliary), a comma or the end -- plus the nouns it is
    coordinated with.  A phrase that stands right after a case particle and in front of a
    comma ("平安から鎌倉時代、") is adverbial and is passed over (W3-a2 F1)."""
    s = strip_parens(sentence).strip().rstrip("。.！!？? ")
    if not s:
        return []
    toks = tokenize(tagger, s)
    n = len(toks)
    p = None
    for i, t in enumerate(toks):
        if t[0] == "は" and t[1] == "助詞":
            p = i
            break
    if p is None:
        return []
    i = p + 1
    while i < n:
        t = toks[i]
        if _is_noun(t) or (t[1] == "接尾辞" and t[2] == "名詞的"):
            j = i
            while j < n and (_is_noun(toks[j]) or (toks[j][1] == "接尾辞" and toks[j][2] == "名詞的")):
                j += 1
            nx = toks[j] if j < n else None
            boundary = (nx is None
                        or (nx[1] == "助動詞" and (nx[3] in ("だ", "です") or nx[0] in ("で", "だっ", "でし")))
                        or (nx[0] in ("、", "，") and nx[1] == "補助記号"))
            if (boundary and nx is not None and nx[0] in _COMMAS and i >= 1
                    and toks[i - 1][1] == "助詞" and toks[i - 1][0] in CASE_PARTICLES):
                boundary = False   # "…から鎌倉時代、": an adverbial phrase, not what X is
            if boundary:
                ys = _tail_runs(toks, j)
                return [y for y in ys if y]
            i = j
        else:
            i += 1
    return []


def hypernym_phrases(tagger, sentence: str) -> Tuple[List[str], str]:
    """(hypernym phrases, reason).  reason is "" when phrases were found."""
    s = strip_parens(sentence).strip()
    s = s.rstrip("。.！!？? ")
    if not s:
        return [], "empty"
    toks = tokenize(tagger, s)
    end = len(toks)
    while end > 0 and toks[end - 1][1] == "補助記号":
        end -= 1
    guard = 0
    while end > 0 and guard < 8:
        guard += 1
        t = toks[end - 1]
        if t[1] == "助動詞" and (t[3] in ("だ", "です", "た") or t[0] in ("で", "だっ", "でし")):
            end -= 1
        elif (t[1] == "動詞" and (t[3] in ("ある", "有る", "在る") or t[0] in ("あっ", "あり"))
              and end >= 2 and toks[end - 2][0] in ("で", "だ")):
            end -= 1
        elif t[1] in ("助動詞", "助詞") and t[0] in ("で",):
            end -= 1
        else:
            break
    while end > 0 and toks[end - 1][1] == "補助記号":
        end -= 1
    if end == 0:
        return [], "empty"
    last = toks[end - 1]
    if not (_is_noun(last) or (last[1] == "接尾辞" and last[2] == "名詞的")):
        return [], "ends_" + (last[1] or "x")
    ys = _tail_runs(toks, end)
    if not ys:
        return [], "no_noun_phrase"
    return ys, ""


def _excl_hit(text: str) -> List[str]:
    if _EXCL_RE is None or not _EXCL_RE.search(text):
        return []
    return [t for t in _EXCL_TERMS if t in text]


_TOPIC_START = re.compile(r"^(?:とは|は)[、，]?")
_JA_ONLY = re.compile(r"^[぀-ヿ一-鿿ー々]+$")


def definition_text(text: str, head: str) -> Tuple[str, str]:
    """(the text the definition sentence is taken from, how it was chosen).

    A lead whose head was cut by an image caption has ``]]`` in it.  The old
    rule took only what follows the LAST ``]]``, which throws the definition away
    when the caption comes after it ("は、日本の元号の一つ。 。]] 大正の後…").
    Now: of the ``]]``-separated parts, the first one that starts with the topic
    marker (は / とは) or with the title is the definition part; when none does,
    the last part is used (as before).  how is "plain" (no ``]]``), "part"
    (a part was chosen and it is the last one: same as before), "part_first" /
    "part_middle" (a part other than the last was chosen), or "last"."""
    if "]]" not in text:
        return text, "plain"
    parts = text.split("]]")
    for i, part in enumerate(parts):
        q = part.strip()
        if _TOPIC_START.match(q) or (head and q.startswith(head)):
            how = "part" if i == len(parts) - 1 else ("part_first" if i == 0 else "part_middle")
            return part, how
    return parts[-1], "last"


def paren_alias_of(dtext: str, head: str, maxc: int) -> Optional[str]:
    """"キツネ（狐）は、…": the first element of the bracket right after the
    title is another spelling of the same thing.  Only a plain Japanese-character
    element (no space, no colon, no digit) counts; a reading with a space, an
    English name, a date or a label ("学名：…") does not."""
    q = dtext.strip()
    if not head or not q.startswith(head):
        return None
    rest = q[len(head):].lstrip()
    if not rest or rest[0] not in "（(":
        return None
    close = {"（": "）", "(": ")"}[rest[0]]
    end = rest.find(close)
    if end < 0:
        return None
    first = re.split(r"[、，,]", rest[1:end])[0].strip()
    if (not first or len(first) > maxc or first == head or not _JA_ONLY.match(first)
            or ct.notation_type(first) is not None):
        return None
    return first


def work_jawiki(task) -> dict:
    """task = (path, byte_start, byte_end, first_line_no, stride, holdout_lines)."""
    path, b0, b1, line0, stride, hold = task
    cfg = _WCFG
    maxc = cfg["max_word_chars"]
    acc = _empty_acc()
    out = {"acc": acc, "defs": [], "aliases": [], "paren_aliases": [], "skips": Counter(),
           "excl": Counter(), "chars": 0, "text_rows": 0, "redirect_rows": 0,
           "rows_used": 0}
    with open(path, "rb") as f:
        f.seek(b0)
        data = f.read(b1 - b0)
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    for off, raw in enumerate(lines):
        ln = line0 + off
        if stride > 1 and ln % stride != 0:
            continue
        if ln in hold:
            out["skips"]["holdout"] += 1
            continue
        try:
            d = json.loads(raw)
        except ValueError:
            out["skips"]["bad_json"] += 1
            continue
        title = d.get("title") or ""
        if "redirect" in d and "text" not in d:
            out["redirect_rows"] += 1
            red = d.get("redirect") or ""
            hits = _excl_hit(title + "\n" + red)
            if hits:
                out["skips"]["excluded_term"] += 1
                for h in hits:
                    out["excl"][h] += 1
                continue
            if _META_TITLE.match(title) or _LOG_TITLE.search(title) or "/" in title:
                out["skips"]["meta_title"] += 1
                continue
            if not title or not red:
                continue
            out["aliases"].append((title, red))
            out["rows_used"] += 1
            continue
        text = d.get("text")
        if text is None:
            out["skips"]["no_text"] += 1
            continue
        out["text_rows"] += 1
        hits = _excl_hit(title + "\n" + text)
        if hits:
            out["skips"]["excluded_term"] += 1
            for h in hits:
                out["excl"][h] += 1
            continue
        out["rows_used"] += 1
        out["chars"] += len(text)
        toks = tokenize(_TAGGER, text)
        analyze(toks, acc, maxc)
        # definition
        if _META_TITLE.match(title) or _LOG_TITLE.search(title):
            out["skips"]["meta_title"] += 1
            continue
        if title.endswith("一覧") or "の一覧" in title:
            out["skips"]["list_article"] += 1
            continue
        m = _TITLE_QUAL.match(title)
        head, qual = (m.group(1), m.group(2)) if m else (title, None)
        if qual is not None and "曖昧さ回避" in qual:
            out["skips"]["disambiguation"] += 1
            continue
        if ct.notation_type(head) is not None:
            out["skips"]["notation_title"] += 1
            continue
        if not head or len(head) > maxc:
            out["skips"]["title_too_long"] += 1
            continue
        dtext, how = definition_text(text, head)
        if how != "plain":
            out["skips"]["bracket_text_" + how] += 1
            if how in ("part_first", "part_middle"):
                out["skips"]["bracket_rule_changed"] += 1   # the old rule read another part
        dtext = dtext.strip().lstrip("。、 ")
        if not dtext:
            out["skips"]["caption_only"] += 1
            continue
        if dtext.startswith("の") and "は" not in dtext:
            # the left-over of an image caption ("の209型の何か"), not a definition (F3)
            out["skips"]["caption_fragment"] += 1
            continue
        sent = first_sentence(dtext)
        ys, why = hypernym_phrases(_TAGGER, sent)
        ys_rec: List[str] = []
        if why:
            ys_rec = first_clause_phrases(_TAGGER, sent)
            out["skips"]["def_" + why + ("_recovered" if ys_rec else "")] += 1
        qys: List[str] = []
        if qual is not None:
            qt = tokenize(_TAGGER, qual)
            qys = _tail_runs(qt, len(qt))
        out["defs"].append((head, qual, ys, qys, ys_rec))
        if qual is None:
            al = paren_alias_of(dtext, head, maxc)
            if al is not None:
                out["paren_aliases"].append((al, head))
    return out


def work_codex(task) -> dict:
    """task = (db_path, family, id_lo, id_hi, stride, hold_ids, hold_shas)."""
    path, fam, lo, hi, stride, hold_ids, hold_shas = task
    cfg = _WCFG
    maxc = cfg["max_word_chars"]
    acc = _empty_acc()
    out = {"acc": acc, "skips": Counter(), "excl": Counter(), "chars": 0,
           "rows": 0, "rows_used": 0, "family": fam}
    con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    try:
        cur = con.execute("SELECT id, text, body_sha FROM rows WHERE id>=? AND id<?"
                          " ORDER BY id", (lo, hi))
        for rid, text, bsha in cur:
            if stride > 1 and rid % stride != 0:
                continue
            out["rows"] += 1
            if (rid in hold_ids) or (bsha in hold_shas):
                out["skips"]["holdout"] += 1
                continue
            if not _JA.search(text):
                out["skips"]["no_japanese"] += 1
                continue
            hits = _excl_hit(text)
            if hits:
                out["skips"]["excluded_term"] += 1
                for h in hits:
                    out["excl"][h] += 1
                continue
            out["rows_used"] += 1
            for line in text.split("\n"):
                if not _JA.search(line):
                    continue
                line = line[:1500]
                out["chars"] += len(line)
                analyze(tokenize(_TAGGER, line), acc, maxc)
    finally:
        con.close()
    return out


# =====================================================================================
# resolution (single process)
# =====================================================================================
def _type_via(y: str, donors: Dict[str, str], min_suffix: int) -> Tuple[Optional[str], Optional[str]]:
    """(type, the donor word it came from) or (None, None)."""
    if y in ct.META_HEADS:
        return None, None   # "X is a word/term/name" says nothing about what X denotes
    t = donors.get(y)
    if t is not None:
        return t, y
    for k in range(1, len(y)):
        suf = y[k:]
        if len(suf) < min_suffix:
            break
        if suf in ct.META_HEADS:
            return None, None   # "…名称" / "…用語": a compound that still talks about the word
        t = donors.get(suf)
        if t is not None:
            return t, suf
    # a taxonomic rank ("…イヌ科イヌ亜科"): the taxon in front of the rank word is
    # what the phrase is a part of (its type is the taxon's)
    for r in ct.RANK_WORDS:
        if y.endswith(r) and len(y) - len(r) >= min_suffix:
            t, via = _type_via(y[: -len(r)], donors, min_suffix)
            if t is not None:
                return t, via
    return None, None


def type_of(y: str, donors: Dict[str, str], min_suffix: int) -> Optional[str]:
    return _type_via(y, donors, min_suffix)[0]


def resolve_definitions(defs, seeds_n: Dict[str, str], cfg, allow=None):
    """Chain the hypernym types.  Round 0 uses only the seeds; each later
    round adds the PLAIN-title headwords the previous round DECIDED from their
    own definition (an article titled "X (qualifier)" describes another sense of
    X: it never feeds the chain and never counts as X's definition).

    ``allow`` (W3-a2 F1): when given, only these heads (and the seeds) may become
    donors -- the heads that stayed DECIDED and uncontradicted in a first full pass.
    A definition entry is ``(head, qualifier, phrases, qualifier phrases[, phrases
    read by the fallback])``; the fallback phrases never feed the chain."""
    min_suf = cfg["min_suffix_chars"]
    dmin = cfg["def_min"]
    donors = dict(seeds_n)
    rounds = []
    defc = qualc = None
    for rnd in range(cfg["max_chain_depth"] + 1):
        defc = defaultdict(Counter)
        qualc = defaultdict(Counter)
        for d in defs:
            head, qual, ys, qys = d[0], d[1], d[2], d[3]
            if qual is None:
                for y in ys:
                    t = type_of(y, donors, min_suf)
                    if t:
                        defc[head][t] += 1
            else:
                for y in qys:
                    t = type_of(y, donors, min_suf)
                    if t:
                        qualc[head][t] += 1
        new = dict(seeds_n)
        decided = 0
        for head, c in defc.items():
            top = arm_top(c, dmin)
            if len(top) == 1 and head not in seeds_n and (allow is None or head in allow):
                new[head] = top[0]
                decided += 1
        rounds.append({"round": rnd, "donors": len(donors), "decided_heads": decided})
        if new == donors:
            break
        donors = new
    return defc, qualc, donors, rounds


def recovered_counts(defs, donors: Dict[str, str], min_suffix: int):
    """The type counts of the definitions read by the fallback (an arm of its own:
    ``definition_recovered``), typed through the final donors."""
    recc: Dict[str, Counter] = defaultdict(Counter)
    for d in defs:
        if len(d) > 4 and d[4] and d[1] is None:
            for y in d[4]:
                t = type_of(y, donors, min_suffix)
                if t:
                    recc[d[0]][t] += 1
    return recc


def donor_dependents(defs, donors: Dict[str, str], min_suffix: int) -> Dict[str, set]:
    """donor word -> the heads whose definition phrase was typed through it."""
    dep: Dict[str, set] = defaultdict(set)
    for d in defs:
        if d[1] is not None:
            continue
        for y in list(d[2]) + (list(d[4]) if len(d) > 4 and d[4] else []):
            t, via = _type_via(y, donors, min_suffix)
            if t:
                dep[via].add(d[0])
    return dep


def build_frame_arm(ctx_src: Dict[Tuple[str, str], Counter], cfg) -> Dict[str, List[Tuple[str, int]]]:
    """pred -> [(ptype, numerator)] for one source (rules that hold)."""
    by_pred: Dict[str, Dict[Tuple[str, str], int]] = defaultdict(dict)
    for (part, pred), cnt in ctx_src.items():
        if not pred:
            continue
        for t, n in cnt.items():
            by_pred[pred][(part, t)] = n
    out = {}
    fmin = cfg["frame_min_total"]
    for pred, slots in by_pred.items():
        total = sum(slots.values())
        if total < fmin:
            continue
        hit = []
        for ptype, conds in ct.PRED_FRAME_RULES:
            ok = True
            num = 0
            for parts, types, pct in conds:
                s = sum(n for (p, t), n in slots.items() if p in parts and t in types)
                if s * 100 < pct * total:
                    ok = False
                    break
                num += s
            if ok:
                hit.append((ptype, num))
        if hit:
            out[pred] = hit
    return out


def stable_json(o) -> str:
    return json.dumps(o, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


from verantyx.coarse_place import cuts_for  # noqa: E402


def build_unit_tables(words_placed: Dict[str, str], attested: Iterable[str], cfg):
    """unit_kin rows for the placed single-type words; atoms from attested."""
    cnt: Dict[Tuple[str, str, str], int] = Counter()
    sample: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    minu = cfg["kin_min_unit_chars"]
    for w, t in words_placed.items():
        n = len(w)
        for a, b in cuts_for(n):
            left, right = w[:a], w[a:]
            if len(left) >= minu:
                cnt[(left, "L", t)] += 1
                sl = sample[(left, "L")]
                if len(sl) < 5 or w < sl[-1]:
                    sl.append(w)
                    sl.sort()
                    del sl[5:]
            if len(right) >= minu:
                cnt[(right, "R", t)] += 1
                sl = sample[(right, "R")]
                if len(sl) < 5 or w < sl[-1]:
                    sl.append(w)
                    sl.sort()
                    del sl[5:]
    tot: Dict[Tuple[str, str], int] = Counter()
    for (u, p, t), n in cnt.items():
        tot[(u, p)] += n
    kmin = cfg["kin_store_min"]
    rows = sorted(((u, p, t, n) for (u, p, t), n in cnt.items() if tot[(u, p)] >= kmin))
    samp = sorted(((u, p, "|".join(s)) for (u, p), s in sample.items() if tot[(u, p)] >= kmin))
    atoms = set()
    for w in attested:
        if len(w) >= 2:
            atoms.add(w[0])
            atoms.add(w[-1])
    return rows, samp, sorted(atoms)


SCHEMA = """
CREATE TABLE headwords(word TEXT PRIMARY KEY, ns TEXT, state TEXT, origin TEXT,
  top TEXT, kind TEXT, n_seen INTEGER, by TEXT) WITHOUT ROWID;
CREATE TABLE evidence(word TEXT, arm TEXT, src TEXT, type TEXT, n INTEGER, base INTEGER,
  PRIMARY KEY(word, arm, src, type)) WITHOUT ROWID;
CREATE TABLE unit_kin(unit TEXT, pos TEXT, type TEXT, n INTEGER,
  PRIMARY KEY(unit, pos, type)) WITHOUT ROWID;
CREATE TABLE unit_sample(unit TEXT, pos TEXT, sample TEXT,
  PRIMARY KEY(unit, pos)) WITHOUT ROWID;
CREATE TABLE atoms(ch TEXT PRIMARY KEY) WITHOUT ROWID;
CREATE TABLE ctx(src TEXT, particle TEXT, pred TEXT, type TEXT, n INTEGER,
  PRIMARY KEY(src, particle, pred, type)) WITHOUT ROWID;
CREATE TABLE counters(unit TEXT PRIMARY KEY, n INTEGER) WITHOUT ROWID;
CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT) WITHOUT ROWID;
CREATE TABLE generated(word TEXT PRIMARY KEY, model TEXT, effort TEXT, batch_id TEXT,
  attempt INTEGER, definition TEXT, hypernym TEXT, phrases TEXT) WITHOUT ROWID;
CREATE TABLE generated_frames(word TEXT PRIMARY KEY, model TEXT, effort TEXT, batch_id TEXT,
  attempt INTEGER, ptype TEXT, frame TEXT) WITHOUT ROWID;
"""

TABLE_ORDER = [("headwords", "word"), ("evidence", "word,arm,src,type"),
               ("unit_kin", "unit,pos,type"), ("unit_sample", "unit,pos"),
               ("atoms", "ch"), ("ctx", "src,particle,pred,type"),
               ("counters", "unit"), ("meta", "k"), ("generated", "word"),
               ("generated_frames", "word")]


def _tables_of(con: sqlite3.Connection):
    have = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return [(t, o) for t, o in TABLE_ORDER if t in have]   # a placement made before `generated` / `generated_frames` existed


def content_sha256(con: sqlite3.Connection) -> str:
    h = hashlib.sha256()
    for tbl, order in _tables_of(con):
        h.update(("#" + tbl + "\n").encode())
        for row in con.execute("SELECT * FROM %s ORDER BY %s" % (tbl, order)):
            h.update(repr(row).encode("utf-8"))
            h.update(b"\n")
    return h.hexdigest()


def table_counts(con: sqlite3.Connection) -> Dict[str, int]:
    return {t: con.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
            for t, _ in _tables_of(con)}


def type_ns(t: str) -> str:
    return "P" if t.startswith("P_") else "N"


def _latin_seen(pos_counter, units) -> Counter:
    """How often each Latin unit (compared without case) occurs as a noun in ONE source."""
    seen: Counter = Counter()
    if not pos_counter or not units:
        return seen
    want = {u.lower() for u in units}
    for (w, cls), n in pos_counter.items():
        if cls == "N" and w.lower() in want:
            seen[w.lower()] += n
    return seen


def _latin_unit_ok(u: str, n: int, seen: Counter, nums, cfg: dict) -> bool:
    """M2: a Latin-script unit counts for a source only when it follows numerals about as
    often as it occurs at all there (share) and follows many different numerals.  A source
    whose numerals were not measured (an old stage, a synthetic ``ex``) is not judged."""
    if nums is None:
        return True                                    # not measured: no verdict
    if n * 100 < cfg["counter_latin_share_pct"] * seen.get(u.lower(), 0):
        return False
    return len(nums.get(u, ())) >= cfg["counter_latin_numerals_min"]


def learn_counters(ex: dict, cfg: dict) -> List[Tuple[str, int]]:
    """The counter-unit table: a unit that follows Arabic numerals often enough IN A SOURCE
    (``counter_min``) is a counter when that holds in ``counter_min_sources`` sources
    (counts of different sources are never added; the table keeps the number of sources).
    One-morpheme units may be up to ``counter_max_chars_single`` characters ("キロメートル",
    "km"); a unit made of TWO morphemes ("件取得") only ``counter_max_chars``.  A source
    counts once per unit (the one-morpheme and two-morpheme tallies are not added).  A unit
    that reads as a TIME unit never goes in; a Latin unit is not dropped because "1km"
    happens to look like an alphanumeric code (F2), but a Latin unit must be 2-3 characters."""
    def unit_ok(u: str) -> bool:
        nt = ct.notation_type("1" + u)
        if nt is not None and nt[0] == "TIME":
            return False
        # a Latin-script unit is 2-3 characters ("kg", "ms", "GHz"): a single letter after a
        # number is as often a code ("3D", "5G") and a longer word is code, not a unit
        if u.isascii() and not (2 <= len(u) <= 3):
            return False
        return True

    unit_srcs: Counter = Counter()
    ctr2 = ex.get("counters2", {})
    nums_all = ex.get("counter_nums")
    for src in sorted(ex["counters"]):
        ok_units = set()
        latin = {u for u, n in ex["counters"][src].items()
                 if n >= cfg["counter_min"] and u.isascii()}
        seen = _latin_seen(ex.get("pos", {}).get(src), latin)
        nums = None if nums_all is None else nums_all.get(src)
        for u, n in ex["counters"][src].items():
            if n >= cfg["counter_min"] and len(u) <= cfg["counter_max_chars_single"]:
                if u.isascii() and not _latin_unit_ok(u, n, seen, nums, cfg):
                    continue
                ok_units.add(u)
        for u, n in ctr2.get(src, {}).items():
            # a Latin unit comes from the one-morpheme table only (the share and the
            # numerals above cannot be measured for a pair)
            if (n >= cfg["counter_min"] and len(u) <= cfg["counter_max_chars"]
                    and not u.isascii()):
                ok_units.add(u)
        for u in ok_units:
            unit_srcs[u] += 1
    return sorted((u, n) for u, n in unit_srcs.items()
                  if n >= cfg["counter_min_sources"] and unit_ok(u))


#: slot constructions (W3-a3 12.5): the marks and the predicate types they are read with.  Predicate
#: TYPES (ids settled by stage 1), never predicate words.
SLOT_TIME_MARKS = ("∅", "に")
SLOT_PLACE_MARKS = ("で", "に")
SLOT_PLACE_PTYPES = ("P_MOVE", "P_EXIST")


def _count_gen_frame(gfstat: Counter, dec: dict, garm: dict) -> None:
    """Count what became of a word that has a generated predicate frame (by outcome and reason)."""
    why = garm.get("why")
    if dec.get("origin") == "estimated":
        gfstat["decided_estimated_generated"] += 1
        if why:
            gfstat[why] += 1
    elif garm["met"]:
        gfstat["decided_direct_upgrade"] += 1
        srcs_ = [k.split("@", 1)[1] for k in dec["by"] if k.startswith("role_distribution@")]
        if srcs_ and all(x.startswith("codex:") for x in srcs_):
            gfstat["decided_direct_upgrade_all_sources_codex"] += 1
        else:
            gfstat["decided_direct_upgrade_with_jawiki"] += 1
    elif why == "GENERATED_NOT_DECIDING":
        gfstat["base_decided_generated_ignored"] += 1
    elif why == "GENERATED_SPLIT":
        gfstat["tie"] += 1


def _stage2(ex: dict, cfg: dict, rec: Dict[str, list], srcs, pos_src, gfstat: Counter,
            n_new_rows: Dict[str, int]):
    """Stage 2 of ``_resolve_stage`` (see there): add the ``role_distribution`` rows of the predicates,
    the ``slot`` rows of the nouns and the ``gen_frame`` rows of the generated predicate frames, and
    decide the words that got a row again.  Returns ``(info for the manifest, generated_frames rows)``."""
    filler_type: Dict[str, str] = {}
    pred_type1: Dict[str, str] = {}
    for w, r in rec.items():
        d = r[5]
        if d["state"] == "DECIDED" and d.get("origin") == "direct" and not any(
                g in d["by"] for g in ct.GEN_ARMS):
            t = d["tops"][0]
            if t.startswith("P_"):
                pred_type1[w] = t
            else:
                filler_type[w] = t
    extra: Dict[str, list] = defaultdict(list)
    case9 = set(ct.CASE_PARTICLES_9)
    per_src: Dict[str, dict] = {}
    lift = cfg["slot_lift_pct"]
    rd_store = cfg["rd_store_min"]
    for src in srcs:
        chain = ex.get("chain", {}).get(src, {})
        pos_n = {w: c.get("N", 0) for w, c in pos_src.get(src, {}).items() if c.get("N", 0)}
        noun_uses = sum(pos_n.values())
        st = Counter()
        rd: Dict[str, Counter] = defaultdict(Counter)
        slot_cnt: Counter = Counter()
        g_time = g_place = 0
        for (fr, fh, m, verb, past), n in chain.items():
            st["chains"] += n
            if m in case9:
                vr = rec.get(verb)
                if vr is not None and "P" in vr[0]:
                    ft = filler_type.get(fr) if fr else None
                    if ft is None and fh:
                        ft = filler_type.get(fh)
                    if ft is None:
                        st["untyped_arguments"] += n
                    else:
                        st["typed_arguments"] += n
                        rd[verb][(m, ft)] += n
            is_time = past and m in SLOT_TIME_MARKS
            is_place = m in SLOT_PLACE_MARKS and pred_type1.get(verb) in SLOT_PLACE_PTYPES
            if is_time or is_place:
                ws = {x for x in (fr, fh) if x}
                if is_time:
                    g_time += n
                    for x in ws:
                        slot_cnt[(x, "TIME")] += n
                if is_place:
                    g_place += n
                    for x in ws:
                        slot_cnt[(x, "PLACE")] += n
        for verb, c in rd.items():
            base = sum(c.values())
            if base >= rd_store:
                st["rd_words"] += 1
                for (part, typ), n in c.items():
                    extra[verb].append((verb, "role_distribution", src, "%s|%s" % (part, typ), n, base))
                    st["rd_rows"] += 1
        glob = {"TIME": g_time, "PLACE": g_place}
        for (w, typ), n in slot_cnt.items():
            wr = rec.get(w)
            if wr is None or "N" not in wr[0]:
                continue
            base = max(pos_n.get(w, 0), n)
            if n * noun_uses * 100 >= lift * glob[typ] * base:
                extra[w].append((w, "slot", src, typ, n, base))
                st["slot_rows_" + typ] += 1
        ctr = ex.get("counters", {}).get(src, {})
        g_q = sum(ctr.values())
        for w, n in ctr.items():
            wr = rec.get(w)
            if wr is None or "N" not in wr[0]:
                continue
            base = max(pos_n.get(w, 0), n)
            if n * noun_uses * 100 >= lift * g_q * base:
                extra[w].append((w, "slot", src, "QUANTITY", n, base))
                st["slot_rows_QUANTITY"] += 1
        st["noun_uses"] = noun_uses
        st["global_time"], st["global_place"], st["global_quantity"] = g_time, g_place, g_q
        per_src[src] = dict(st)
    # generated predicate frames (a model wrote them; arm gen_frame, never a donor)
    gfs = ex.get("gen_frames", {})
    gf_table = []
    order = {p: i for i, p in enumerate(ct.ROLE_PARTICLES)}
    for w in sorted(gfs):
        g = gfs[w]
        r = rec.get(w)
        if r is None:
            gfstat["not_in_material"] += 1
            continue
        if "P" not in r[0]:
            gfstat["ns_not_predicate"] += 1
            continue
        extra[w].append((w, ct.GEN_FRAME_ARM, g["src"], g["ptype"], 1, None))
        for part in sorted(g["frame"], key=lambda x: order[x]):
            for typ in sorted(g["frame"][part]):
                extra[w].append((w, "gen_frame_slot", g["src"], "%s|%s" % (part, typ), 1, None))
        gf_table.append((w, g["model"], g["effort"], g["batch_id"], g["attempt"], g["ptype"],
                         stable_json(g["frame"])))
        gfstat["used"] += 1
    for w, rows in extra.items():
        r = rec[w]
        r[1] = r[1] + rows
        n_new_rows[w] = len(rows)
        r[5] = ct.decide_word([(a_, s_, t_, n_, b_) for (_w, a_, s_, t_, n_, b_) in r[1]], cfg)
    info = {"filler_typed_words": len(filler_type), "predicate_typed_words": len(pred_type1),
            "per_source": per_src, "words_with_new_rows": len(extra),
            "frame_decides": bool(cfg.get("frame_decides", True))}
    return info, gf_table


def _resolve_stage(ex: dict, cfg: dict, allow=None, use_gen: bool = False,
                   use_new: bool = False) -> dict:
    """Everything after extraction: definition chain, aliases, contexts,
    role/sahen/pos_class/frame arms, decisions, unit tables.  ``allow`` (None = every
    head) names the heads that may hand a type down a chain or to a context table.
    ``use_gen``: read the generated definitions (``ex["gen"]``) as an arm of their own
    (``gen_definition``); a word they alone place is an ESTIMATE (generated) and is never
    a donor, a unit-family member or a context donor.
    ``use_new`` (W3-a3): after the decisions above ("stage 1": no new arm), add the distribution of a
    predicate's arguments (``role_distribution``), the time / place / quantity constructions of a noun
    (``slot``) and the generated predicate frames (``ex["gen_frames"]``, arm ``gen_frame``) and decide
    again only the words that got a new row ("stage 2").  The types that stage 2 reads (what a filler
    is, what a predicate is) are stage 1's, so stage 2 never feeds itself."""
    t0 = time.time()
    timing = {}
    seeds_n = {w: t for t, ws in ct.SEEDS_NOUN.items() for w in ws}
    seeds_p = {w: t for t, ws in ct.SEEDS_PRED.items() for w in ws}
    # ---- definitions
    defc, qualc, donors, rounds = resolve_definitions(ex["defs"], seeds_n, cfg, allow)
    recc = recovered_counts(ex["defs"], donors, cfg["min_suffix_chars"])
    timing["definitions_sec"] = round(time.time() - t0, 1)
    dmin, amin = cfg["def_min"], cfg["alias_min"]
    # tier-2 decision per head: plain definition + (strong enough) qualifier
    qmin = cfg["qual_min"]
    t2: Dict[str, tuple] = {}
    for head in set(defc) | set(qualc) | set(recc):
        comb = combine_arms({"definition": arm_top(defc.get(head, {}), dmin),
                             "title_qualifier": arm_top(qualc.get(head, {}), qmin)})
        if comb:
            t2[head] = comb
    # plain-definition decision (used for alias targets and context donors)
    plain: Dict[str, str] = {}
    plain_all: Dict[str, str] = {}
    for head, c in defc.items():
        top = arm_top(c, dmin)
        if len(top) == 1:
            plain_all[head] = top[0]
            if allow is None or head in allow or head in seeds_n:
                plain[head] = top[0]
    # aliases: title -> type of the target (when the target is DECIDED)
    aliasc: Dict[str, Counter] = defaultdict(Counter)
    alias_stats = Counter()
    for title, red in ex["aliases"]:
        rt = None
        if red in seeds_n:
            rt = seeds_n[red]
        elif red in plain:
            rt = plain[red]
        if rt is None:
            alias_stats["unresolved_target"] += 1
            continue
        aliasc[title][rt] += 1
        alias_stats["resolved"] += 1
    timing["aliases_sec"] = round(time.time() - t0, 1)
    # ---- donors for context tables: tier-1/2 DECIDED nouns (alias-typed too
    # only through tier 2 -- aliases do not feed contexts)
    donor_type: Dict[str, str] = dict(seeds_n)
    for h, t in plain.items():
        if h not in donor_type:
            donor_type[h] = t
    srcs = sorted(ex["occ"])
    for src in srcs:
        ex["pos"].setdefault(src, Counter())
    ctx: Dict[str, Dict[Tuple[str, str], Counter]] = {}
    for src in srcs:
        c: Dict[Tuple[str, str], Counter] = defaultdict(Counter)
        for (w, part, pred), n in ex["occ"][src].items():
            t = donor_type.get(w)
            if t is not None:
                c[(part, pred)][t] += n
        ctx[src] = c
    timing["ctx_sec"] = round(time.time() - t0, 1)
    # ---- role votes (leave-one-out)
    cmin, cshare = cfg["ctx_min_total"], cfg["ctx_min_share_pct"]
    clift = cfg["ctx_min_lift_pct"]
    votes: Dict[str, Dict[str, Counter]] = {}
    gsrc: Dict[str, Counter] = {}
    for src in srcs:
        g = Counter()
        for cnt in ctx[src].values():
            g.update(cnt)
        gsrc[src] = g
    for src in srcs:
        cs = ctx[src]
        g = gsrc[src]
        gtot = sum(g.values())
        tot = {k: sum(v.values()) for k, v in cs.items()}
        top1 = {}
        for k, v in cs.items():
            mx = max(v.values())
            tops = [t for t, n in v.items() if n == mx]
            top1[k] = (mx, tops)
        vs: Dict[str, Counter] = defaultdict(Counter)
        for (w, part, pred), n in ex["occ"][src].items():
            k = (part, pred)
            cnt = cs.get(k)
            if cnt is None:
                continue
            tw = donor_type.get(w)
            total = tot[k]
            if tw is not None and tw in cnt:
                adj = dict(cnt)
                adj[tw] = adj[tw] - n
                total -= n
                if total < cmin:
                    continue
                mx = max(adj.values())
                tops = [t for t, c in adj.items() if c == mx]
                if len(tops) != 1 or mx * 100 < cshare * total:
                    continue
                top = tops[0]
            else:
                if total < cmin:
                    continue
                mx, tops = top1[k]
                if len(tops) != 1 or mx * 100 < cshare * total:
                    continue
                top = tops[0]
            if mx * gtot * 100 < clift * g[top] * total:
                continue   # not more typical here than everywhere (base rate)
            vs[w][top] += n
        votes[src] = vs
    timing["votes_sec"] = round(time.time() - t0, 1)
    # ---- hypernym pairs read from running text: type of A = type of Y
    hmin, hshare = cfg["hearst_min"], cfg["hearst_min_share_pct"]
    hear: Dict[str, Dict[str, Counter]] = {}
    min_suf = cfg["min_suffix_chars"]
    ytype_cache: Dict[str, Optional[str]] = {}
    for src in srcs:
        hs_: Dict[str, Counter] = defaultdict(Counter)
        for (a_, y_), n_ in ex.get("hearst", {}).get(src, {}).items():
            if y_ not in ytype_cache:
                ytype_cache[y_] = type_of(y_, donor_type, min_suf)
            t_ = ytype_cache[y_]
            if t_:
                hs_[a_][t_] += n_
        hear[src] = hs_
    timing["hearst_sec"] = round(time.time() - t0, 1)
    # ---- frame arms for verbs
    frame: Dict[str, Dict[str, List[Tuple[str, int]]]] = {
        src: build_frame_arm(ctx[src], cfg) for src in srcs}
    # ---- paren aliases: "X (Y, ...)" lead -- Y is another spelling of X.  Its own
    # arm (counts are never added to the redirect alias arm's)
    pac: Dict[str, Counter] = defaultdict(Counter)
    for al_, head_ in ex.get("paren_aliases", []):
        rt_ = seeds_n.get(head_) or plain.get(head_)
        if rt_ is None:
            alias_stats["paren_unresolved_target"] += 1
            continue
        pac[al_][rt_] += 1
        alias_stats["paren_resolved"] += 1
    # ---- word universe and grammatical classes
    # grammatical-class counts: per source (the namespace vote, the pos_class arm
    # and the sahen share) and summed ONLY for the "seen in the material" gate
    # (a gate is not a vote for a type)
    pos_tot: Dict[str, Counter] = defaultdict(Counter)
    pos_src: Dict[str, Dict[str, Counter]] = {}
    for src, pc_ in ex["pos"].items():
        d: Dict[str, Counter] = defaultdict(Counter)
        for (w, cl), n in pc_.items():
            d[w][cl] += n
            pos_tot[w][cl] += n
        pos_src[src] = d
    min_seen = cfg["min_seen"]
    words = set(donor_type) | set(t2) | set(aliasc) | set(pac) | set(seeds_p) | set(recc)
    for w, c in pos_tot.items():
        if sum(c.values()) >= min_seen:
            words.add(w)
    for src in srcs:
        words.update(votes[src])
        words.update(hear[src])
    # ---- decisions
    hw_rows = []
    ev_rows = []
    stat = Counter()
    funnel = Counter()
    funnel["distinct_words_in_material_any_count"] = len(pos_tot)
    funnel["distinct_words_in_material_min_seen"] = sum(
        1 for c in pos_tot.values() if sum(c.values()) >= min_seen)
    funnel["titles_with_definition_phrase"] = len(defc)
    funnel["titles_with_recovered_phrase"] = len(recc)
    funnel["titles_with_qualifier_phrase"] = len(qualc)
    funnel["alias_titles_with_typed_target"] = len(aliasc)
    funnel["paren_alias_words_with_typed_target"] = len(pac)
    funnel["words_with_a_met_arm_before_decision"] = 0
    placed_single: Dict[str, str] = {}
    gen_rows = ex.get("gen", {}) if use_gen else {}
    gstat: Counter = Counter()
    gen_typed: Dict[str, list] = {}
    gen_used: set = set()
    if use_gen:
        wset = set(words)
        gstat["not_in_material"] = sum(1 for w_ in gen_rows if w_ not in wset)
    # W3-a2 F1: what the donors are, who depends on them, and what each donor's final
    # decision looked like (so a second pass can stop a wrong donor from spreading)
    cand_keys = {h for h in donor_type if h not in seeds_n}
    cand: Dict[str, tuple] = {}
    dep = donor_dependents(ex["defs"], donor_type, min_suf)
    hubs = sorted(dep, key=lambda h: (-len(dep[h]), h))[:50]
    watch = set()
    for h in hubs:
        watch |= dep[h]
    other_met: Dict[str, list] = {}
    rec: Dict[str, list] = {}       # stage 1: word -> [ns, evidence rows, n_votes, n_seen, kind, decision]
    for w in sorted(words):
        pc = pos_tot.get(w, Counter())
        n_seen = sum(pc.values())
        ev = []
        seed_t = seeds_n.get(w) or seeds_p.get(w)
        in_t2 = w in t2 or w in aliasc or w in pac or w in recc
        kind = "seed" if seed_t else ("title" if (w in defc or w in qualc or w in aliasc or w in recc) else (
            "paren_alias" if w in pac else "token"))
        # namespace: each source votes on its own counts (noun uses vs verb /
        # adjective uses); a tie abstains.  Sources that disagree are NOT settled by
        # choosing one: both sets of arms are evaluated ("NP") and the arms overlay
        nsv: Dict[str, Optional[str]] = {}
        for src in srcs:
            ps = pos_src[src].get(w)
            if not ps:
                continue
            nn = ps.get("N", 0)
            npd = ps.get("V", 0) + ps.get("A", 0) + ps.get("S", 0)
            nsv[src] = "N" if nn > npd else ("P" if npd > nn else None)
        if seed_t:
            ns = type_ns(seed_t)
        elif in_t2:
            ns = "N"
        else:
            vs_ = {v for v in nsv.values() if v}
            ns = next(iter(vs_)) if len(vs_) == 1 else "NP"
        if seed_t:
            ev.append((w, "seed", "hand", seed_t, 1, None))
        if "N" in ns:
            for t, n in defc.get(w, {}).items():
                ev.append((w, "definition", "jawiki", t, n, None))
            for t, n in recc.get(w, {}).items():
                ev.append((w, "definition_recovered", "jawiki", t, n, None))
            for t, n in qualc.get(w, {}).items():
                ev.append((w, "title_qualifier", "jawiki", t, n, None))
            for t, n in aliasc.get(w, {}).items():
                ev.append((w, "alias", "jawiki", t, n, None))
            for t, n in pac.get(w, {}).items():
                ev.append((w, "paren_alias", "jawiki", t, n, None))
            for src in srcs:
                v = votes[src].get(w)
                if v:
                    for t, n in v.items():
                        ev.append((w, "role", src, t, n, None))
                sc = ex["sahen"][src].get(w, 0)
                if sc:
                    ev.append((w, "sahen", src, "EVENT_ACT", sc,
                               pos_src[src].get(w, {}).get("N", 0)))
                hv = hear[src].get(w)
                if hv:
                    for t, n in hv.items():
                        ev.append((w, "hearst", src, t, n, None))
        if "P" in ns:
            for src in srcs:
                ps = pos_src[src].get(w)
                if ps:
                    a_s = ps.get("A", 0) + ps.get("S", 0)
                    if a_s:
                        ev.append((w, "pos_class", src, "P_STATE", a_s, ps.get("V", 0)))
                hit = frame[src].get(w)
                if hit:
                    for ptype, num in hit:
                        ev.append((w, "frame", src, ptype, num, None))
        if use_gen and w in gen_rows:
            if ns != "N":
                gstat["ns_not_noun"] += 1
            else:
                g_ = gen_rows[w]
                cnt_ = Counter()
                typed_ = []
                for ph_ in g_["phrases"]:
                    t_ = type_of(ph_, donor_type, min_suf)
                    typed_.append([ph_, t_])
                    if t_:
                        cnt_[t_] += 1
                gen_typed[w] = typed_
                if not cnt_:
                    gstat["no_type"] += 1
                else:
                    gen_used.add(w)
                    for t_, n_ in sorted(cnt_.items()):
                        ev.append((w, ct.GEN_ARM, g_["src"], t_, n_, None))
        n_votes = len(ev)
        if ns == "NP":
            funnel["ns_conflict_or_tied_words"] += 1
            for src in srcs:
                ps = pos_src[src].get(w)
                if ps:
                    ev.append((w, "ns_vote", src, "N", ps.get("N", 0), None))
                    ev.append((w, "ns_vote", src, "P",
                               ps.get("V", 0) + ps.get("A", 0) + ps.get("S", 0), None))
        dec = ct.decide_word([(a_, s_, t_, n_, b_) for (_w, a_, s_, t_, n_, b_) in ev], cfg)
        state, tops, by = dec["state"], dec["tops"], dec["by"]
        if w in cand_keys:
            cand[w] = (state, list(tops),
                       {k_: dict(a_["counts"]) for k_, a_ in dec["arms"].items()
                        if a_["arm"] in ct.DONOR_CONTRA_ARMS})
        if w in watch:
            other_met[w] = [(a_["arm"], tuple(a_["top"])) for a_ in dec["arms"].values()
                            if a_["met"] and a_["arm"] not in ("definition", "definition_recovered")]
        if state == "UNPLACED" and not n_votes and n_seen < min_seen:
            continue
        rec[w] = [ns, ev, n_votes, n_seen, kind, dec]
    # ---- stage 2 (W3-a3): the new arms, only for the words that got a new row
    new_info: Dict[str, object] = {}
    gf_table: list = []
    gfstat: Counter = Counter()
    n_new_rows: Dict[str, int] = {}
    if use_new:
        new_info, gf_table = _stage2(ex, cfg, rec, srcs, pos_src, gfstat, n_new_rows)
    # ---- final rows
    for w in sorted(rec):
        ns, ev, n_votes, n_seen, kind, dec = rec[w]
        state, tops, by = dec["state"], dec["tops"], dec["by"]
        if ns == "NP" and tops:
            kinds_ = {type_ns(t) for t in tops}
            ns = kinds_.pop() if len(kinds_) == 1 else "NP"
        origin = dec.get("origin")
        garm_f = dec["arms"].get(ct.GEN_FRAME_ARM)
        if garm_f is not None:
            _count_gen_frame(gfstat, dec, garm_f)
        elif origin == "estimated":
            gstat["decided_estimated_generated"] += 1
        elif ct.GEN_ARM in dec["arms"]:
            a_g = dec["arms"][ct.GEN_ARM]
            if a_g["met"]:
                gstat["decided_direct_upgrade"] += 1
            elif a_g["why"] == "GENERATED_NOT_DECIDING":
                gstat["base_decided_generated_ignored"] += 1
            elif a_g["why"] == "GENERATED_SPLIT":
                gstat["tie"] += 1
        funnel["rows"] += 1
        if n_votes or n_new_rows.get(w):
            funnel["rows_with_any_evidence"] += 1
        if origin == "direct":
            funnel["rows_placed_direct"] += 1
        elif origin == "estimated":
            funnel["rows_placed_estimated_generated"] += 1
        hw_rows.append((w, ns, state, origin, ",".join(tops), kind, n_seen,
                        "+".join(by)))
        ev_rows.extend(ev)
        stat[(state, ns)] += 1
        # a word placed with a generated sentence or frame in its decision (an upgrade to "direct"
        # included) never feeds the unit families: a generated claim is not passed on
        if state == "DECIDED" and origin == "direct" and not any(g_ in by for g_ in ct.GEN_ARMS):
            placed_single[w] = tops[0]
    timing["decide_sec"] = round(time.time() - t0, 1)
    # ---- unit tables
    attested = [r[0] for r in hw_rows]
    # only noun-side single-type words feed the unit families
    unit_src = {w: t for w, t in placed_single.items()
                if 2 <= len(w) <= cfg["max_word_chars"]}
    uk, us, atoms = build_unit_tables(unit_src, attested, cfg)
    timing["units_sec"] = round(time.time() - t0, 1)
    # ---- ctx rows (contexts with enough donors)
    ctx_rows = []
    for src in srcs:
        for (part, pred), cnt in sorted(ctx[src].items()):
            if sum(cnt.values()) >= cfg["ctx_store_min"]:
                for t, n in sorted(cnt.items()):
                    ctx_rows.append((src, part, pred, t, n))
    ctr_rows = learn_counters(ex, cfg)
    ctx_global = {src: dict(sorted(gsrc[src].items())) for src in srcs}
    gen_table = []
    for w_ in sorted(gen_typed):
        g_ = gen_rows[w_]
        gen_table.append((w_, g_["model"], g_["effort"], g_["batch_id"], g_["attempt"],
                          g_["definition"], g_["hypernym"], stable_json(gen_typed[w_])))
    gstat["used"] = len(gen_used)
    return {"gen_frame_table": gf_table, "gen_frame_stats": dict(gfstat), "new_info": new_info,
            "chain_skips": {k_: dict(v_) for k_, v_ in sorted(ex.get("chain_skips", {}).items())},
            "gen_table": gen_table, "gen_stats": dict(gstat), "funnel": dict(funnel), "ctx_global": ctx_global, "headwords": hw_rows, "evidence": ev_rows, "unit_kin": uk,
            "unit_sample": us, "atoms": atoms, "ctx": ctx_rows,
            "counters": ctr_rows, "stat": stat, "rounds": rounds,
            "alias_stats": alias_stats, "timing": timing,
            "donors": len(donor_type),
            "_donor_type": donor_type, "_cand": cand, "_seeds": set(seeds_n),
            "_hubs": [{"donor": h, "type": donor_type[h], "dependents": len(dep[h]),
                       "dependents_with_other_met_arm_elsewhere": sum(
                           1 for d_ in dep[h]
                           if any(donor_type[h] not in tp_ for _a, tp_ in other_met.get(d_, ())))}
                      for h in hubs]}


def _donor_allow(a: dict, cfg: dict):
    """Which chain donors of the first pass may stay donors (F1).  A non-seed donor
    stays when its FINAL decision is DECIDED to the very type it hands down AND no arm
    of another kind (each role/hearst source, alias, paren_alias, title_qualifier, taken
    on its own -- counts are never summed) has a single top type that differs from it
    with at least ``donor_contra_min`` votes.  Seeds are always donors."""
    min_c = cfg["donor_contra_min"]
    allow = set()
    excl = {"not_decided": 0, "contra_arm": 0}
    for w, (state, tops, arms) in sorted(a["_cand"].items()):
        t = a["_donor_type"][w]
        if state != "DECIDED" or tops != [t]:
            excl["not_decided"] += 1
            continue
        contra = False
        for counts in arms.values():
            if not counts:
                continue
            mx = max(counts.values())
            tp = [x for x, c in counts.items() if c == mx]
            if len(tp) == 1 and tp[0] != t and mx >= min_c:
                contra = True
                break
        if contra:
            excl["contra_arm"] += 1
            continue
        allow.add(w)
    return allow, excl


def resolve_all(ex: dict, cfg: dict) -> dict:
    """Resolve in TWO stages (deterministic; the second never feeds the first).
    Stage A: every definition head that is decided from its own definition may hand its
    type down.  Stage B: only the heads that, in stage A, ended DECIDED and were not
    contradicted by an arm of another kind (``_donor_allow``) may -- the chain, the
    context tables, the role votes and the hearst pairs are rebuilt with that donor set.
    ``donor_stage_b`` false = stage A only (the pre-W3-a2 behaviour)."""
    t0 = time.time()
    # stage A never reads the generated definitions: they hand nothing down, so the donor
    # set (and everything built on it) does not depend on them
    a = _resolve_stage(ex, cfg, None, use_gen=not cfg.get("donor_stage_b", True),
                       use_new=not cfg.get("donor_stage_b", True))
    ta = round(time.time() - t0, 1)
    seeds_n = a["_seeds"]
    st_a = {"donors": a["donors"], "non_seed_donors": len(a["_cand"])}
    if not cfg.get("donor_stage_b", True):
        res = a
        res["donor_stats"] = {"enabled": False, "stage_a": st_a, "stage_b": None,
                              "excluded": {"not_decided": 0, "contra_arm": 0},
                              "top_donors": a["_hubs"]}
        res["timing"] = dict(a["timing"], stage_a_sec=ta, stage_b_sec=0.0)
    else:
        allow, excl = _donor_allow(a, cfg)
        t1 = time.time()
        res = _resolve_stage(ex, cfg, allow, use_gen=True, use_new=True)
        tb = round(time.time() - t1, 1)
        res["donor_stats"] = {
            "enabled": True, "donor_contra_min": cfg["donor_contra_min"],
            "stage_a": st_a,
            "stage_b": {"donors": res["donors"],
                        "non_seed_donors": len([h for h in res["_donor_type"] if h not in seeds_n])},
            "excluded": excl, "top_donors": res["_hubs"]}
        res["timing"] = dict(res["timing"], stage_a_sec=ta, stage_b_sec=tb)
    for k in ("_donor_type", "_cand", "_seeds", "_hubs"):
        res.pop(k, None)
    return res


def read_generated(path: str, excl_terms: Sequence[str], tagger):
    """Read ``definitions.jsonl`` (written by tools/gen_coarse_evidence.py collect).

    Returns ``(rows, drops, n_lines)``.  ``rows[word]`` = {definition, hypernym, phrases,
    model, effort, batch_id, attempt, src}: the phrases are read from the generated
    definition sentence by the SAME rules as a Wikipedia lead (``hypernym_phrases``, then
    ``first_clause_phrases``), plus the generated hypernym field as one phrase; each
    distinct phrase counts once.  A generated row is a sentence a model wrote, not a
    testimony from the material: its source is always ``generated:<model>:<effort>``.
    Dropped, with a count by reason: ``abstained`` (the model answered null),
    ``excluded_term`` (the word or its text holds a held-out test word), ``dup_word``
    (a word that appears twice is not taken: no tie is broken by order)."""
    rx = None
    if excl_terms:
        rx = re.compile("|".join(re.escape(t) for t in sorted(excl_terms, key=len, reverse=True)))
    drops: Counter = Counter()
    raw: Dict[str, dict] = {}
    dup = set()
    n_lines = 0
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        n_lines += 1
        r = json.loads(line)
        w = r["word"]
        if w in raw or w in dup:
            dup.add(w)
            raw.pop(w, None)
            continue
        raw[w] = r
    drops["dup_word"] = len(dup)
    for k_ in ("abstained", "excluded_term"):
        drops[k_] += 0          # a reason that did not occur still shows as 0 in the manifest
    rows: Dict[str, dict] = {}
    for w in sorted(raw):
        r = raw[w]
        d, h = r.get("definition"), r.get("hypernym")
        if r.get("abstained") or (not d and not h):
            drops["abstained"] += 1
            continue
        if rx is not None and rx.search("\n".join([w, d or "", h or ""])):
            drops["excluded_term"] += 1
            continue
        ys: List[str] = []
        if d:
            sent = first_sentence(d.strip())
            ys, why = hypernym_phrases(tagger, sent)
            if why:
                ys = first_clause_phrases(tagger, sent)
        if h and h.strip():
            ys = list(ys) + [h.strip()]
        seen_, ph = set(), []
        for y in ys:
            if y and y not in seen_ and y != w:
                seen_.add(y)
                ph.append(y)
        pv = r.get("provenance") or {}
        model, effort = pv.get("model"), pv.get("effort")
        rows[w] = {"definition": d, "hypernym": h, "phrases": ph, "model": model,
                   "effort": effort, "batch_id": pv.get("batch_id"),
                   "attempt": pv.get("attempt"),
                   "src": "generated:%s:%s" % (model, effort)}
    return rows, drops, n_lines


def read_generated_frames(path: str, excl_terms: Sequence[str]):
    """Read ``frames.jsonl`` (written by tools/gen_coarse_evidence.py collect --kind pred).

    Returns ``(rows, drops, n_lines)``.  ``rows[word]`` = {ptype, frame ({particle: [noun types]}),
    model, effort, batch_id, attempt, src}.  A generated frame is what a model wrote when asked, not a
    testimony from the material: its source is always ``generated:<model>:<effort>``.  Dropped, with a
    count by reason: ``abstained`` (the model answered null), ``invalid`` (a type or a particle outside
    the closed inventory), ``excluded_term`` (the word holds a held-out test word) and ``dup_word`` (a
    word that appears twice is not taken: no tie is broken by order)."""
    rx = None
    if excl_terms:
        rx = re.compile("|".join(re.escape(t) for t in sorted(excl_terms, key=len, reverse=True)))
    drops: Counter = Counter()
    for k_ in ("abstained", "invalid", "excluded_term"):
        drops[k_] += 0
    raw: Dict[str, dict] = {}
    dup = set()
    n_lines = 0
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        n_lines += 1
        r = json.loads(line)
        w = r["word"]
        if w in raw or w in dup:
            dup.add(w)
            raw.pop(w, None)
            continue
        raw[w] = r
    drops["dup_word"] = len(dup)
    rows: Dict[str, dict] = {}
    for w in sorted(raw):
        r = raw[w]
        if r.get("abstained") or r.get("ptype") is None:
            drops["abstained"] += 1
            continue
        fr = r.get("frame") or {}
        ok = r["ptype"] in ct.PRED_TYPES and isinstance(fr, dict)
        if ok:
            for part, ts in fr.items():
                if part not in ct.CASE_PARTICLES_9 or not ts or any(t not in ct.NOUN_TYPES for t in ts):
                    ok = False
                    break
        if not ok:
            drops["invalid"] += 1
            continue
        if rx is not None and rx.search(w):
            drops["excluded_term"] += 1
            continue
        pv = r.get("provenance") or {}
        model, effort = pv.get("model"), pv.get("effort")
        rows[w] = {"ptype": r["ptype"], "frame": {p: sorted(set(ts)) for p, ts in fr.items()},
                   "model": model, "effort": effort, "batch_id": pv.get("batch_id"),
                   "attempt": pv.get("attempt"), "src": "generated:%s:%s" % (model, effort)}
    return rows, drops, n_lines


# =====================================================================================
# the build command
# =====================================================================================
def _load_terms(paths: Sequence[str]) -> Dict[str, List[str]]:
    out = {}
    for p in paths or []:
        ts = []
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line:
                ts.append(json.loads(line)["term"])
        out[p] = ts
    return out


def _jawiki_chunks(path: str, nchunks_target: int):
    """(byte_start, byte_end, first_line_no) chunks aligned to line starts."""
    size = os.path.getsize(path)
    approx = max(1, size // nchunks_target)
    chunks = []
    with open(path, "rb") as f:
        pos, line_no = 0, 0
        while pos < size:
            end = min(size, pos + approx)
            if end < size:
                f.seek(end)
                f.readline()
                end = f.tell()
            f.seek(pos)
            nl = 0
            remaining = end - pos
            while remaining > 0:
                blk = f.read(min(1 << 22, remaining))
                if not blk:
                    break
                nl += blk.count(b"\n")
                remaining -= len(blk)
            chunks.append((pos, end, line_no))
            line_no += nl
            pos = end
    return chunks, line_no


def cmd_build(args) -> int:
    import multiprocessing as mp
    global _HASH_CACHE_FILE
    if args.out:
        _HASH_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(args.out)), ".input_hash_cache.json")
    t_start = time.time()
    started = now_utc()
    if not args.out:
        print(json.dumps({"state": "UNKNOWN_OUT_UNSET"}))
        return 2
    cfg = dict(ct.DEFAULT_CONFIG)
    if args.config:
        cfg.update(json.load(open(args.config, encoding="utf-8")))
    cfg_text = stable_json(cfg)
    # frozen check
    frozen_sha = None
    if args.frozen:
        fr = json.load(open(args.frozen, encoding="utf-8"))
        root = os.path.dirname(os.path.dirname(os.path.abspath(args.frozen)))
        root = os.path.dirname(root)
        for rel, meta in fr["files"].items():
            if rel == "verantyx/coarse_types.py":
                continue
            p = os.path.join(root, rel)
            if not os.path.exists(p) or sha256_file(p) != meta["sha256"]:
                print(json.dumps({"state": "FROZEN_MISMATCH", "file": rel}))
                return 3
        frozen_sha = sha256_file(args.frozen)
    excl = _load_terms(args.exclude_terms)
    excl_terms = sorted({t for ts in excl.values() for t in ts})
    hold_lines, hold_codex, hold_shas = set(), set(), set()
    hold_info = None
    if args.holdout:
        hold_info = []
        for hp in args.holdout:
            nj0, nc0 = len(hold_lines), len(hold_codex)
            for line in open(hp, encoding="utf-8"):
                r = json.loads(line)
                if r["source"] == "jawiki":
                    hold_lines.add(r["line"])
                    hold_shas.add(r["sha"])
                else:
                    hold_codex.add((r["family"], r["rowid"]))
                    hold_shas.add(r["body_sha"])
            hold_info.append({"path": hp, "sha256": sha256_file(hp),
                              "jawiki_lines": len(hold_lines) - nj0,
                              "codex_rows": len(hold_codex) - nc0})
    stride = args.sample_stride
    jobs = args.jobs
    cache_path = args.stage_cache
    ex = None
    stage_t = {}
    inputs = []
    skips_total: Dict[str, Counter] = {"jawiki": Counter()}
    excl_counts = Counter()
    if cache_path and os.path.exists(cache_path):
        import pickle
        with open(cache_path, "rb") as f:
            ex = pickle.load(f)
        if "chain" not in ex or "chain_skips" not in ex:
            # an old extraction knows nothing of the argument chains: reading it as "counted zero" would
            # make every distribution arm silently empty (W3-a3 12.3)
            print(json.dumps({"state": "STAGE_CACHE_STALE", "stage_cache": cache_path,
                              "missing": [k for k in ("chain", "chain_skips") if k not in ex]}))
            return EXIT_STAGE_CACHE_STALE
        stage_t["extraction_sec"] = 0.0
        stage_t["extraction_from_cache"] = cache_path
        inputs = ex["inputs"]
        skips_total = ex["skips"]
        excl_counts = ex["excl"]
    else:
        ctxm = mp.get_context("fork")
        ex = {"occ": {}, "pos": {}, "sahen": {}, "counters": {}, "counters2": {},
              "counter_nums": {}, "chain": {}, "chain_skips": {},
              "defs": [], "aliases": [], "paren_aliases": [], "hearst": {}}
        t1 = time.time()
        # ---- jawiki
        jw_in = {"name": "jawiki_leads", "path": args.jawiki,
                 "bytes": os.path.getsize(args.jawiki)}
        chunks, nlines = _jawiki_chunks(args.jawiki, max(8, jobs * 6))
        jw_in["lines"] = nlines
        tasks = [(args.jawiki, b0, b1, l0, stride, hold_lines) for b0, b1, l0 in chunks]
        occ_j = Counter()
        hearst_j = Counter()
        sahen_j = Counter()
        ctr_j = Counter()
        ctr2_j = Counter()
        nums_j: dict = {}
        chain_j = Counter()
        chain_sk_j = Counter()
        pos_j = Counter()
        npos_j = Counter()
        jw_stats = Counter()
        with ctxm.Pool(jobs, initializer=_worker_init, initargs=(cfg, excl_terms)) as pool:
            for k, r in enumerate(pool.imap(work_jawiki, tasks)):
                a = r["acc"]
                occ_j.update(a["occ"])
                hearst_j.update(a["hearst"])
                sahen_j.update(a["sahen"])
                ctr_j.update(a["counters"])
                ctr2_j.update(a["counters2"])
                _merge_nums(nums_j, a["counter_nums"])
                chain_j.update(a["chain"])
                chain_sk_j.update(a["chain_skips"])
                pos_j.update(a["pos"])
                ex["defs"].extend(r["defs"])
                ex["aliases"].extend(r["aliases"])
                ex["paren_aliases"].extend(r["paren_aliases"])
                skips_total["jawiki"].update(r["skips"])
                excl_counts.update({"jawiki:" + t: n for t, n in r["excl"].items()})
                jw_stats["chars"] += r["chars"]
                jw_stats["text_rows"] += r["text_rows"]
                jw_stats["redirect_rows"] += r["redirect_rows"]
                jw_stats["rows_used"] += r["rows_used"]
                print("[jawiki %d/%d] %.0fs" % (k + 1, len(tasks), time.time() - t1),
                      file=sys.stderr, flush=True)
        jw_in.update({"sha256": cached_sha(args.jawiki), "stats": dict(jw_stats)})
        inputs.append(jw_in)
        ex["occ"]["jawiki"] = occ_j
        ex["hearst"]["jawiki"] = hearst_j
        ex["sahen"]["jawiki"] = sahen_j
        ex["counters"]["jawiki"] = ctr_j
        ex["counters2"]["jawiki"] = ctr2_j
        ex["counter_nums"]["jawiki"] = nums_j
        ex["chain"]["jawiki"] = chain_j
        ex["chain_skips"]["jawiki"] = chain_sk_j
        ex["pos"]["jawiki"] = pos_j
        stage_t["jawiki_sec"] = round(time.time() - t1, 1)
        # ---- codex
        t2 = time.time()
        fams = args.families.split(",") if args.families else FAMILIES_DEFAULT
        if args.codex_dir:
            ctasks = []
            for fam in fams:
                p = os.path.join(args.codex_dir, fam + ".db")
                if not os.path.exists(p):
                    continue
                con = sqlite3.connect("file:%s?mode=ro" % p, uri=True)
                n, lo, hi = con.execute("SELECT COUNT(*), MIN(id), MAX(id) FROM rows").fetchone()
                con.close()
                inputs.append({"name": "codex:" + fam, "path": p,
                               "bytes": os.path.getsize(p), "rows": n,
                               "sha256": cached_sha(p),
                               "origin": "generated"})
                hold_ids = {rid for (f, rid) in hold_codex if f == fam}
                step = 40000
                for a in range(lo, hi + 1, step):
                    ctasks.append((p, fam, a, min(hi + 1, a + step), stride,
                                   hold_ids, hold_shas))
            accs: Dict[str, dict] = {}
            cstats: Dict[str, Counter] = defaultdict(Counter)
            with ctxm.Pool(jobs, initializer=_worker_init, initargs=(cfg, excl_terms)) as pool:
                for k, r in enumerate(pool.imap(work_codex, ctasks)):
                    fam = r["family"]
                    src = "codex:" + fam
                    a = r["acc"]
                    acc = accs.setdefault(src, _empty_acc())
                    acc["occ"].update(a["occ"])
                    acc["hearst"].update(a["hearst"])
                    acc["pos"].update(a["pos"])
                    acc["sahen"].update(a["sahen"])
                    acc["counters"].update(a["counters"])
                    acc["counters2"].update(a["counters2"])
                    _merge_nums(acc["counter_nums"], a["counter_nums"])
                    acc["chain"].update(a["chain"])
                    acc["chain_skips"].update(a["chain_skips"])
                    skips_total.setdefault(src, Counter()).update(r["skips"])
                    excl_counts.update({src + ":" + t: n for t, n in r["excl"].items()})
                    cstats[src]["rows"] += r["rows"]
                    cstats[src]["rows_used"] += r["rows_used"]
                    cstats[src]["chars"] += r["chars"]
                    if k % 20 == 0:
                        print("[codex %d/%d] %.0fs" % (k + 1, len(ctasks), time.time() - t2),
                              file=sys.stderr, flush=True)
            for src in sorted(accs):
                a = accs[src]
                ex["occ"][src] = a["occ"]
                ex["hearst"][src] = a["hearst"]
                ex["sahen"][src] = a["sahen"]
                ex["counters"][src] = a["counters"]
                ex["counters2"][src] = a["counters2"]
                ex["counter_nums"][src] = a["counter_nums"]
                ex["chain"][src] = a["chain"]
                ex["chain_skips"][src] = a["chain_skips"]
                ex["pos"][src] = a["pos"]
            for inp in inputs:
                if inp["name"].startswith("codex:"):
                    inp["stats"] = dict(cstats.get(inp["name"], {}))
        stage_t["codex_sec"] = round(time.time() - t2, 1)
        stage_t["extraction_sec"] = round(time.time() - t1, 1)
        ex["inputs"] = inputs
        ex["skips"] = skips_total
        ex["excl"] = excl_counts
        if cache_path:
            import pickle
            with open(cache_path, "wb") as f:
                pickle.dump(ex, f, protocol=4)
    # ---- generated definitions (a different origin: never part of the extraction cache)
    gen_info = None
    ex = dict(ex)
    ex["gen"] = {}
    if args.generated:
        import fugashi
        tg = time.time()
        gen_rows, gen_drops, gen_lines = read_generated(
            args.generated, excl_terms, fugashi.Tagger())
        ex["gen"] = gen_rows
        gen_info = {"path": os.path.abspath(args.generated), "sha256": sha256_file(args.generated),
                    "lines": gen_lines, "rows_read": len(gen_rows),
                    "dropped_by_reason": dict(gen_drops),
                    "read_sec": round(time.time() - tg, 1)}
        if args.generated_ledger:
            gen_info["ledger_path"] = os.path.abspath(args.generated_ledger)
            gen_info["ledger_sha256"] = sha256_file(args.generated_ledger)
            led = [json.loads(l) for l in open(args.generated_ledger, encoding="utf-8") if l.strip()]
            ok_b = {e["batch"] for e in led if e["ev"] == "end" and e.get("status") == "ok"}
            all_b = {e["batch"] for e in led}
            gen_info["calls"] = sum(1 for e in led if e["ev"] == "start")
            gen_info["batches_ok"] = len(ok_b)
            gen_info["batches_failed"] = len(all_b - ok_b)
        used_models = {(r["model"], r["effort"]) for r in gen_rows.values()}
        gen_info["models"] = sorted("%s:%s" % m for m in used_models)
        gen_info["model"] = sorted({m for m, _e in used_models})[0] if used_models else None
        gen_info["effort"] = sorted({e for _m, e in used_models})[0] if used_models else None
    # ---- generated predicate frames (a different origin as well: never part of the cache)
    ex["gen_frames"] = {}
    gf_info = None
    if args.generated_frames:
        tg = time.time()
        gf_rows, gf_drops, gf_lines = read_generated_frames(args.generated_frames, excl_terms)
        ex["gen_frames"] = gf_rows
        gf_info = {"path": os.path.abspath(args.generated_frames),
                   "sha256": sha256_file(args.generated_frames),
                   "lines": gf_lines, "rows_read": len(gf_rows),
                   "dropped_by_reason": dict(gf_drops),
                   "read_sec": round(time.time() - tg, 1)}
        if args.generated_frames_ledger:
            gf_info["ledger_path"] = os.path.abspath(args.generated_frames_ledger)
            gf_info["ledger_sha256"] = sha256_file(args.generated_frames_ledger)
            led = [json.loads(l) for l in open(args.generated_frames_ledger, encoding="utf-8") if l.strip()]
            ok_b = {e["batch"] for e in led if e["ev"] == "end" and e.get("status") == "ok"}
            all_b = {e["batch"] for e in led}
            gf_info["calls"] = sum(1 for e in led if e["ev"] == "start")
            gf_info["batches_ok"] = len(ok_b)
            gf_info["batches_failed"] = len(all_b - ok_b)
        used_m = {(r["model"], r["effort"]) for r in gf_rows.values()}
        gf_info["models"] = sorted("%s:%s" % m for m in used_m)
        gf_info["model"] = sorted({m for m, _e in used_m})[0] if used_m else None
        gf_info["effort"] = sorted({e for _m, e in used_m})[0] if used_m else None
    # ---- resolve
    t3 = time.time()
    res = resolve_all(ex, cfg)
    stage_t["resolve_sec"] = round(time.time() - t3, 1)
    # ---- write sqlite
    t4 = time.time()
    os.makedirs(args.out, exist_ok=True)
    dbp = os.path.join(args.out, "placement.sqlite")
    tmp = dbp + ".tmp"
    for p in (tmp, tmp + "-journal"):
        if os.path.exists(p):
            os.remove(p)
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO headwords VALUES (?,?,?,?,?,?,?,?)", res["headwords"])
    con.executemany("INSERT INTO evidence VALUES (?,?,?,?,?,?)", sorted(set(res["evidence"])))
    con.executemany("INSERT INTO unit_kin VALUES (?,?,?,?)", res["unit_kin"])
    con.executemany("INSERT INTO unit_sample VALUES (?,?,?)", res["unit_sample"])
    con.executemany("INSERT INTO atoms VALUES (?)", [(a,) for a in res["atoms"]])
    con.executemany("INSERT INTO ctx VALUES (?,?,?,?,?)", res["ctx"])
    con.executemany("INSERT INTO counters VALUES (?,?)", res["counters"])
    con.executemany("INSERT INTO generated VALUES (?,?,?,?,?,?,?,?)", res["gen_table"])
    con.executemany("INSERT INTO generated_frames VALUES (?,?,?,?,?,?,?)", res["gen_frame_table"])
    meta = {"config": cfg_text, "types_version": ct.TYPES_VERSION,
            "schema_version": "1", "ctx_global": stable_json(res["ctx_global"])}
    con.executemany("INSERT INTO meta VALUES (?,?)", sorted(meta.items()))
    con.commit()
    counts = table_counts(con)
    csha = content_sha256(con)
    con.close()
    os.replace(tmp, dbp)
    stage_t["write_sec"] = round(time.time() - t4, 1)
    # ---- manifest
    st = res["stat"]
    outputs = {"tables": counts, "headwords": counts["headwords"],
               "by_state_ns": {"%s/%s" % k: v for k, v in sorted(st.items())}}
    placed = [r for r in res["headwords"] if r[3] == "direct"]
    outputs["placed_direct"] = len(placed)
    outputs["placed_estimated_generated"] = sum(1 for r in res["headwords"] if r[3] == "estimated")
    outputs["funnel"] = res["funnel"]
    outputs["by_state"] = dict(Counter(r[2] for r in res["headwords"]))
    outputs["by_ns_placed"] = dict(Counter(r[1] for r in placed))
    outputs["by_kind_placed"] = dict(Counter(r[5] for r in placed))
    outputs["by_top_placed"] = dict(Counter(r[4] for r in placed if "," not in r[4]))
    outputs["by_arm_placed"] = dict(Counter(a for r in placed for a in r[7].split("+")))
    outputs["evidence_by_arm"] = dict(Counter(e[1] for e in res["evidence"]))
    outputs["evidence_by_src"] = dict(Counter(e[2] for e in res["evidence"]))
    skips = {k: dict(v) for k, v in ex["skips"].items()}
    git_head = None
    git_dirty = None
    try:
        import subprocess
        root = os.path.dirname(HERE)
        git_head = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                                  capture_output=True, text=True).stdout.strip()
        git_dirty = bool(subprocess.run(["git", "-C", root, "status", "--porcelain"],
                                        capture_output=True, text=True).stdout.strip())
    except Exception:
        pass
    materials = [
        {"name": "jawiki lead sentences", "path": args.jawiki, "role": "definition / alias / role / pos material"},
        {"name": "codex generated corpus index (train)", "path": args.codex_dir,
         "role": "role / pos material per family (origin: generated)"} if args.codex_dir else None,
        {"name": "hand-written seeds", "path": "verantyx/coarse_types.py (SEEDS_NOUN, SEEDS_PRED)"},
        {"name": "notation rules", "path": "verantyx/coarse_types.py (notation_type)"},
        {"name": "predicate frame rule table", "path": "verantyx/coarse_types.py (PRED_FRAME_RULES)"},
        {"name": "stop-word lists (they give no type)",
         "path": "verantyx/coarse_types.py (GENERIC_HEADS, META_HEADS, RANK_WORDS)"},
        {"name": "paren alias (the first bracket element after a title)",
         "role": "derived from the jawiki leads above (an arm of its own)"},
        {"name": "generated definition sentences (a model wrote them; not a testimony)",
         "path": args.generated, "origin": "generated",
         "model": (gen_info or {}).get("model"), "effort": (gen_info or {}).get("effort"),
         "role": "arm gen_definition: places only a word nothing else decided, as an estimate "
                 "(generated); never settles a tie; never a donor"} if args.generated else None,
        {"name": "predicate argument chains (neighbouring noun runs + case particles + a verb)",
         "role": "arms role_distribution (predicates) and slot (nouns): shown, never alone a decider; "
                 "derived from the jawiki and codex material above"},
        {"name": "K62 table (the predicate types and frames W3-b1 reads; a copy)",
         "path": "verantyx/coarse_types.py (K62_FRAMES)", "role": "reverse lookup of role_distribution"},
        {"name": "generated predicate frames (a model wrote them; not a testimony)",
         "path": args.generated_frames, "origin": "generated",
         "model": (gf_info or {}).get("model"), "effort": (gf_info or {}).get("effort"),
         "role": "arm gen_frame: an estimate (generated) unless the distribution arms back the same "
                 "type and cover its particles; never a donor"} if args.generated_frames else None,
        {"name": "unidic-lite via fugashi", "use": "word segmentation, the coarse word class (pos1, pos2) and orthBase ONLY; no finer dictionary sense labels"},
    ]
    materials = [m for m in materials if m]
    manifest = {
        "build_started_at_utc": started, "build_finished_at_utc": now_utc(),
        "duration_sec": round(time.time() - t_start, 1),
        "stage_seconds": stage_t | res["timing"],
        "args": {"sample_stride": stride, "jobs": jobs,
                 "exclude_terms": args.exclude_terms, "holdout": args.holdout,
                 "frozen": args.frozen, "jawiki": args.jawiki,
                 "codex_dir": args.codex_dir, "families": args.families,
                 "stage_cache": cache_path, "generated": args.generated,
                 "generated_ledger": args.generated_ledger,
                 "generated_frames": args.generated_frames,
                 "generated_frames_ledger": args.generated_frames_ledger},
        "frozen_sha256": frozen_sha,
        "coarse_types_sha256": sha256_file(os.path.join(os.path.dirname(HERE), "verantyx", "coarse_types.py")),
        "builder_sha256": sha256_file(os.path.abspath(__file__)),
        "config": cfg, "config_sha256": sha256_text(cfg_text),
        "inputs": ex["inputs"], "skipped_rows_by_reason": skips,
        "excluded_term_hits": dict(ex["excl"]),
        "excluded_terms_total": len(excl_terms),
        "holdout": hold_info,
        "hypernym_rounds": res["rounds"], "alias_stats": dict(res["alias_stats"]),
        "donor_stats": res["donor_stats"],
        "generated": (dict(gen_info, **{"used": res["gen_stats"].get("used", 0),
                                        "dropped_by_reason": dict(
                                            gen_info["dropped_by_reason"],
                                            **{k: res["gen_stats"].get(k, 0)
                                               for k in ("ns_not_noun", "no_type", "not_in_material")}),
                                        "outcomes": {k: v for k, v in res["gen_stats"].items()
                                                     if k in ("tie", "decided_estimated_generated",
                                                              "decided_direct_upgrade",
                                                              "base_decided_generated_ignored")}})
                      if gen_info else None),
        "generated_frames": (dict(gf_info, **{
            "used": res["gen_frame_stats"].get("used", 0),
            "dropped_by_reason": dict(gf_info["dropped_by_reason"], **{
                k: res["gen_frame_stats"].get(k, 0)
                for k in ("ns_not_predicate", "not_in_material")}),
            "outcomes": {k: v for k, v in sorted(res["gen_frame_stats"].items())
                         if k not in ("used", "ns_not_predicate", "not_in_material")}})
                             if gf_info else None),
        "argument_chains": {"skipped_or_counted_by_reason": res["chain_skips"],
                            "stage2": res["new_info"]},
        "donors": res["donors"],
        "materials": materials,
        "seed_counts": {"noun": sum(len(v) for v in ct.SEEDS_NOUN.values()),
                        "pred": sum(len(v) for v in ct.SEEDS_PRED.values())},
        "outputs": outputs, "content_sha256": csha,
        "placement_bytes": os.path.getsize(dbp),
        "git_head": git_head, "git_dirty": git_dirty,
        "types_version": ct.TYPES_VERSION,
        "no_weights_no_models": True,
    }
    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    print(json.dumps({"state": "BUILT", "out": args.out, "content_sha256": csha,
                      "headwords": counts["headwords"], "placed_direct": len(placed),
                      "duration_sec": manifest["duration_sec"]}, ensure_ascii=False))
    return 0


def cmd_verify(args) -> int:
    pl = args.placement
    mp_ = os.path.join(pl, "manifest.json")
    dbp = os.path.join(pl, "placement.sqlite")
    if not (os.path.exists(mp_) and os.path.exists(dbp)):
        print(json.dumps({"state": "MISSING", "placement": pl}))
        return 4
    m = json.load(open(mp_, encoding="utf-8"))
    con = sqlite3.connect("file:%s?mode=ro" % dbp, uri=True)
    counts = table_counts(con)
    bad = []
    for t, n in m["outputs"]["tables"].items():
        if counts.get(t) != n:
            bad.append({"table": t, "manifest": n, "actual": counts.get(t)})
    # derived counts
    hw = con.execute("SELECT COUNT(*) FROM headwords WHERE origin='direct'").fetchone()[0]
    if hw != m["outputs"]["placed_direct"]:
        bad.append({"placed_direct": m["outputs"]["placed_direct"], "actual": hw})
    for st, n in m["outputs"]["by_state"].items():
        a = con.execute("SELECT COUNT(*) FROM headwords WHERE state=?", (st,)).fetchone()[0]
        if a != n:
            bad.append({"state": st, "manifest": n, "actual": a})
    sha = content_sha256(con)
    con.close()
    if sha != m["content_sha256"]:
        bad.append({"content_sha256": m["content_sha256"], "actual": sha})
    print(json.dumps({"state": "OK" if not bad else "MISMATCH", "placement": pl,
                      "content_sha256": sha, "counts": counts, "bad": bad},
                     ensure_ascii=False))
    return 0 if not bad else 4


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("holdout")
    h.add_argument("--jawiki", required=True)
    h.add_argument("--codex-dir", required=True)
    h.add_argument("--out", required=True)
    h.add_argument("--n-jawiki", type=int, default=1000)
    h.add_argument("--n-codex", type=int, default=1000)
    h.add_argument("--seed", type=int, default=None)
    h.add_argument("--avoid", action="append", default=[])
    b = sub.add_parser("build")
    b.add_argument("--jawiki", required=True)
    b.add_argument("--codex-dir", default=None)
    b.add_argument("--families", default=None)
    b.add_argument("--out", default=None)
    b.add_argument("--sample-stride", type=int, default=1)
    b.add_argument("--exclude-terms", action="append", default=[])
    b.add_argument("--holdout", action="append", default=[])
    b.add_argument("--frozen", default=None)
    b.add_argument("--jobs", type=int, default=8)
    b.add_argument("--config", default=None, help="JSON of config overrides")
    b.add_argument("--generated", default=None,
                   help="definitions.jsonl made by tools/gen_coarse_evidence.py collect")
    b.add_argument("--generated-ledger", default=None,
                   help="the generator's ledger.jsonl (its calls and batches go in the manifest)")
    b.add_argument("--generated-frames", default=None,
                   help="frames.jsonl made by tools/gen_coarse_evidence.py collect --kind pred")
    b.add_argument("--generated-frames-ledger", default=None,
                   help="the predicate generator's ledger.jsonl (its calls and batches go in the manifest)")
    b.add_argument("--stage-cache", default=None,
                   help="pickle path: reuse (or write) the extraction stage")
    v = sub.add_parser("verify")
    v.add_argument("--placement", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "holdout":
        return cmd_holdout(args)
    if args.cmd == "build":
        return cmd_build(args)
    return cmd_verify(args)


if __name__ == "__main__":
    sys.exit(main())
