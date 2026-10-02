"""Verify what an AI wrote against the documents you gave it — claim by claim.

The product face of the typed-edge work. Two steps:

    compile   documents -> a typed-edge store (who did what to whom, polarity,
              modality, source line). Nothing is learned; the store is the
              documents, read.
    verify    text -> every asserted relation in it, each judged against the
              store, each verdict carrying the source lines that decided it.

Verdicts, per claim (a claim is one typed edge the text ASSERTS — a quoted,
hedged or conditional clause in the checked text is reported as such and
never judged as an assertion):

    SUPPORTED       the documents assert the same relation, same polarity
    CONTRADICTED    the documents assert it with the opposite polarity, or
                    the same event with a different participant in the same
                    role (花子が渡した vs 太郎が渡した, same object), or the
                    opposite pole of the same property axis dominates
    UNSUPPORTED     the documents speak of these words, not this relation
    NOT_IN_DOCS     the documents never mention the subject — no judgment

It says "your documents do not support this", never "this is false". A
claim about something the documents never covered is NOT_IN_DOCS, and may be
perfectly true.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .typed_edges import POLES, RATIO, _opposite, axis_hit, build, extract

_SPLIT = re.compile(r"(?<=[。！？!?])\s*|\n+")


def sentences(text: str) -> List[str]:
    return [s.strip() for s in _SPLIT.split(text or "") if s and s.strip()]


# --- compile ----------------------------------------------------------------

def compile_docs(paths: Iterable[Path], out: Path) -> Dict[str, Any]:
    """Read .txt / .md files (or a directory of them) into a store."""
    rows: List[Tuple[str, str, str]] = []
    files: List[Path] = []
    for p in paths:
        p = Path(p).expanduser()
        files += sorted(p.rglob("*")) if p.is_dir() else [p]
    for f in files:
        if not f.is_file() or f.suffix.lower() not in (".txt", ".md"):
            continue
        for n, s in enumerate(sentences(f.read_text(encoding="utf-8", errors="ignore"))):
            rows.append((hashlib.sha1(s.encode()).hexdigest(), s, "%s:%d" % (f.name, n + 1)))
    out = Path(out).expanduser()
    if out.exists():
        out.unlink()
    rep = build(out, rows)
    return {"store": str(out), "files": len(files), **rep}


def compile_rows(named_texts, out: Path, decisions: Optional[Sequence[Dict[str, Any]]] = None
                 ) -> Dict[str, Any]:
    """Like compile_docs, for documents handed over as (name, text) — Cleanroom's
    page holds the project folder, so the bridge receives the texts.

    `decisions` are the owner's own records ({id, at, text, supersedes: [ids]}):
    what the owner wrote or chose to keep, never what the work AI said unasked.
    Each sentence is sourced "decision:<id>@<at>", and supersession is kept so
    an answer is judged against the owner's CURRENT decision, not a replaced one.
    """
    rows: List[Tuple[str, str, str]] = []
    for name, text in named_texts:
        for n, s in enumerate(sentences(text)):
            rows.append((hashlib.sha1(s.encode()).hexdigest(), s, "%s:%d" % (name, n + 1)))
    sup: List[Tuple[str, str]] = []
    for d in decisions or ():
        did, at = str(d.get("id", "")), str(d.get("at", ""))
        for s in sentences(str(d.get("text", ""))):
            # the same sentence may be both a document line and a decision: keep both
            rows.append((hashlib.sha1(("decision:" + did + s).encode()).hexdigest(), s,
                         "decision:%s@%s" % (did, at)))
        for old in d.get("supersedes") or ():
            sup.append((did, str(old)))
    out = Path(out).expanduser()
    if out.exists():
        out.unlink()
    rep = build(out, rows)
    con = sqlite3.connect(str(out))
    con.execute("CREATE TABLE IF NOT EXISTS supersedes (new TEXT, old TEXT)")
    con.executemany("INSERT INTO supersedes VALUES (?,?)", sup)
    con.commit()
    con.close()
    return {"files": len(named_texts), "decisions": len(decisions or ()), **rep}


def _decision(src: str) -> Optional[Tuple[str, str]]:
    """(id, at) for a decision source, None for a document line."""
    if not src.startswith("decision:"):
        return None
    body = src[len("decision:"):]
    did, _, at = body.partition("@")
    return did, at


def _superseded(con) -> set:
    try:
        return {r[0] for r in con.execute("SELECT old FROM supersedes")}
    except sqlite3.OperationalError:
        return set()


def _current(con, rows: Sequence[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Drop witnesses from decisions the owner replaced."""
    gone = _superseded(con)
    out = []
    for pol, sha in rows:
        r = con.execute("SELECT src FROM tsent WHERE sha=?", (sha,)).fetchone()
        d = _decision(r[0]) if r else None
        if d and d[0] in gone:
            continue
        out.append((pol, sha))
    return out


def _newest(con, shas: Sequence[str]) -> Tuple[int, str]:
    """(rank, at): decisions outrank documents; among decisions, the latest."""
    best = (0, "")
    for sha in shas:
        r = con.execute("SELECT src FROM tsent WHERE sha=?", (sha,)).fetchone()
        d = _decision(r[0]) if r else None
        cand = (1, d[1]) if d else (0, "")
        best = max(best, cand)
    return best


# --- verify -----------------------------------------------------------------

def _witness(con, sha: str) -> Dict[str, str]:
    r = con.execute("SELECT text, src FROM tsent WHERE sha=?", (sha,)).fetchone()
    return {"text": r[0], "source": r[1]} if r else {}


def _held(con, word: str) -> bool:
    return con.execute("SELECT 1 FROM tedges WHERE head=? OR dep=? LIMIT 1",
                       (word, word)).fetchone() is not None


_ANS = "mod IN ('assert','cond_then')"

#: は names the topic, which may be the subject or the object; it is matched
#: against both, and both are matched against it.
_ROLE_EQ = {"が": ("が", "は"), "を": ("を", "は"), "は": ("は", "が", "を")}


def _event_subject(con, sha: str, ev: int) -> str:
    rows = dict(con.execute("SELECT rel, dep FROM tedges WHERE sha=? AND ev=? AND rel IN ('が','は')",
                            (sha, ev)).fetchall())
    return rows.get("が") or rows.get("は") or ""


def judge(con, e, doer: str = "") -> Dict[str, Any]:
    """`doer` is the claim event's own が/は participant, if any. Two lines are
    only compared when they are about the same doer: 「課長は発行しない」 and
    「総務課が発行する」 are two events, not a document disagreeing with itself."""
    head, rel, dep, pol = e.head, e.rel, e.dep, e.pol
    subject = head if rel == "属性" else dep
    if not _held(con, subject):
        return {"verdict": "NOT_IN_DOCS", "witnesses": []}
    rels = _ROLE_EQ.get(rel, (rel,))
    raw = con.execute(
        f"SELECT pol, sha, ev FROM tedges WHERE head=? AND rel IN ({','.join('?' * len(rels))}) "
        f"AND dep=? AND {_ANS}", (head, *rels, dep)).fetchall()
    if doer and rel not in ("が", "は"):
        raw = [(p, sha, ev) for p, sha, ev in raw
               if _event_subject(con, sha, ev) in ("", doer)]
    same = _current(con, [(p, sha) for p, sha, _ in raw])
    agree = [sha for p, sha in same if p == pol]
    oppose = [sha for p, sha in same if p != pol]
    if agree and oppose:
        # The owner's latest decision settles it; a decision outranks a document.
        na, no = _newest(con, agree), _newest(con, oppose)
        if na != no:
            if na > no:
                return {"verdict": "SUPPORTED", "why": "最新の決定と一致（古い記述とは逆）",
                        "witnesses": [_witness(con, s) for s in agree[:2]]}
            return {"verdict": "CONTRADICTED", "why": "最新の決定と逆",
                    "witnesses": [_witness(con, s) for s in oppose[:2]]}
    if oppose and not agree:
        return {"verdict": "CONTRADICTED", "why": "文書は肯定・否定が逆",
                "witnesses": [_witness(con, s) for s in oppose[:3]]}
    if agree and not oppose:
        return {"verdict": "SUPPORTED",
                "witnesses": [_witness(con, s) for s in agree[:3]]}
    if agree and oppose:
        return {"verdict": "CONTRADICTED", "why": "文書どうしが食い違っている",
                "witnesses": [_witness(con, s) for s in (agree[:2] + oppose[:2])]}
    # Property axis: the documents may hold the opposite pole of the same axis.
    if rel == "属性" and pol == "+":
        axis = [dep[:1]] if dep else []
        opp = _opposite(axis) or _opposite([dep[:2]])
        if opp:
            rows = con.execute(
                f"SELECT dep, sha FROM tedges WHERE head=? AND rel='属性' AND pol='+' AND {_ANS}",
                (head,)).fetchall()
            other = [sha for w, sha in rows if axis_hit(w, opp)]
            # The documents are the authority here, not a crowd: one line
            # giving the opposite pole is enough to contradict.
            if other:
                return {"verdict": "CONTRADICTED", "why": "文書は反対の性質を書いている",
                        "witnesses": [_witness(con, s) for s in other[:3]]}
    # Role: the same event (verb + another participant) with someone else in
    # this role. 花子が太郎に資料Aを渡した vs 太郎が…資料Aを渡した.
    if rel in ("が", "に", "を"):
        rows = con.execute(
            f"SELECT a.dep, a.sha FROM tedges a WHERE a.head=? AND a.rel=? AND a.dep<>? AND a.pol=? AND {_ANS.replace('mod', 'a.mod')}",
            (head, rel, dep, pol)).fetchall()
        others = [(w, sha) for w, sha in rows]
        if others:
            # only a conflict if that event shares another participant with
            # the claim's own event (same object / same recipient)
            return {"verdict": "UNSUPPORTED", "why": "文書ではこの役は %s"
                    % "・".join(sorted({w for w, _ in others})[:3]),
                    "witnesses": [_witness(con, s) for _, s in others[:3]]}
    return {"verdict": "UNSUPPORTED", "witnesses": []}


def _role_conflicts(con, claims) -> Dict[int, Dict[str, Any]]:
    """Event-level check: a claim event (verb + roles) against document
    events with the same verb and at least one other identical participant,
    where the checked role is filled by someone else."""
    out: Dict[int, Dict[str, Any]] = {}
    by_ev: Dict[int, List[Any]] = {}
    ctx: Dict[int, Dict[str, str]] = {}
    for k, e in enumerate(claims):
        if e.rel in ("が", "に", "を", "で", "は"):
            ctx.setdefault(e.ev, {})[e.rel] = e.dep
        if e.rel in ("が", "に", "を", "で"):   # は is ambiguous: never the role checked
            by_ev.setdefault(e.ev, []).append((k, e))
    for ev, items in by_ev.items():
        roles = ctx.get(ev, {})
        if len(roles) < 2:
            continue
        verb = items[0][1].head
        docs = con.execute(
            f"SELECT sha, ev, rel, dep FROM tedges WHERE head=? AND pol='+' AND {_ANS}",
            (verb,)).fetchall()
        events: Dict[Tuple[str, int], Dict[str, str]] = {}
        for sha, dev, rel, dep in docs:
            events.setdefault((sha, dev), {})[rel] = dep
        # Reversal: the documents' event has the claim's participants in the
        # swapped roles (花子が太郎を / 太郎が花子を).
        for (sha, _dev), r in events.items():
            for (k1, e1) in items:
                for (k2, e2) in items:
                    if k1 < k2 and r.get(e1.rel) == e2.dep and r.get(e2.rel) == e1.dep \
                            and e1.dep != e2.dep:
                        hit = {"verdict": "CONTRADICTED",
                               "why": "文書では役割が逆",
                               "witnesses": [_witness(con, sha)]}
                        out.setdefault(k1, hit)
                        out.setdefault(k2, hit)
        for k, e in items:
            if k in out:
                continue
            for (sha, _dev), r in events.items():
                if r.get(e.rel) and r[e.rel] != e.dep and any(
                        r.get(o) == v for o, v in roles.items() if o != e.rel):
                    out[k] = {"verdict": "CONTRADICTED",
                              "why": "文書の同じ出来事では「%s」の役は %s" % (e.rel, r[e.rel]),
                              "witnesses": [_witness(con, sha)]}
                    break
    return out


def verify(store: Path, text: str) -> Dict[str, Any]:
    con = sqlite3.connect(f"file:{Path(store).expanduser()}?mode=ro", uri=True)
    report = []
    tally: Dict[str, int] = {}
    for s in sentences(text):
        es = extract(s)
        asserted = [e for e in es if e.mod in ("assert", "cond_then")]
        other = [e for e in es if e.mod not in ("assert", "cond_then")]
        roles = _role_conflicts(con, asserted)
        claims = []
        subj = {}
        for e in asserted:
            if e.rel in ("が", "は"):
                subj.setdefault(e.ev, e.dep)
        for k, e in enumerate(asserted):
            j = judge(con, e, subj.get(e.ev, ""))
            if k in roles and j["verdict"] != "SUPPORTED":
                j = roles[k]
            tally[j["verdict"]] = tally.get(j["verdict"], 0) + 1
            claims.append({"claim": "%s ─%s→ %s%s" % (e.head, e.rel, e.dep,
                                                    "（否定）" if e.pol == "-" else ""),
                           **j})
        for e in other:
            claims.append({"claim": "%s ─%s→ %s" % (e.head, e.rel, e.dep),
                           "verdict": "NOT_ASSERTED", "modality": e.mod})
        report.append({"sentence": s, "claims": claims})
    con.close()
    worst = ("CONTRADICTED" if tally.get("CONTRADICTED") else
             "UNSUPPORTED" if tally.get("UNSUPPORTED") else
             "SUPPORTED" if tally.get("SUPPORTED") else "NOTHING_CHECKABLE")
    return {"overall": worst, "tally": tally, "sentences": report,
            "note": "judged against YOUR documents only; unsupported is not false"}


def conflicts(store: Path, limit: int = 50) -> List[Dict[str, Any]]:
    """Pairs of current lines that assert opposite polarity of one relation —
    between two decisions, or a decision and a document. The owner picks which
    one stands; nothing is resolved silently."""
    con = sqlite3.connect(f"file:{Path(store).expanduser()}?mode=ro", uri=True)
    gone = _superseded(con)
    rows = con.execute(
        f"SELECT a.head, a.rel, a.dep, a.sha, b.sha FROM tedges a JOIN tedges b "
        f"ON a.head=b.head AND a.rel=b.rel AND a.dep=b.dep AND a.pol='+' AND b.pol='-' "
        f"WHERE a.mod IN ('assert','cond_then') AND b.mod IN ('assert','cond_then') LIMIT ?",
        (limit * 4,)).fetchall()
    out, seen = [], set()
    for h, r, d, sa, sb in rows:
        wa, wb = _witness(con, sa), _witness(con, sb)
        da, db = _decision(wa.get("source", "")), _decision(wb.get("source", ""))
        if (da and da[0] in gone) or (db and db[0] in gone):
            continue
        key = (sa, sb)
        if key in seen:
            continue
        seen.add(key)
        out.append({"relation": "%s ─%s→ %s" % (h, r, d), "yes": wa, "no": wb})
        if len(out) >= limit:
            break
    con.close()
    return out


def regression() -> Dict[str, Any]:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        doc = Path(d) / "doc.txt"
        doc.write_text("花子が太郎に資料Aを渡した。氷は冷たい。氷は冷たい。"
                       "倉庫の鍵は総務課が管理する。申請は窓口で受け付けない。", encoding="utf-8")
        st = Path(d) / "s.db"
        compile_docs([doc], st)
        def v(t):
            return [c["verdict"] for x in verify(st, t)["sentences"] for c in x["claims"]]
        checks = {
            "supported": "SUPPORTED" in v("花子が資料Aを渡した。"),
            "role_swap": "CONTRADICTED" in v("太郎が資料Aを渡した。"),
            "topic_context": "CONTRADICTED" in v("倉庫の鍵は経理課が管理する。"),
            "reversal": "CONTRADICTED" in v("資料Aが花子を渡した。"),
            "negation": "CONTRADICTED" in v("申請は窓口で受け付ける。") or
                        "CONTRADICTED" in v("窓口で申請を受け付ける。"),
            "pole": "CONTRADICTED" in v("氷は熱い。"),
            "not_in_docs": v("ペンギンは飛ばない。") in (["NOT_IN_DOCS"], ["NOT_IN_DOCS", "NOT_IN_DOCS"]),
            "quote_not_judged": "NOT_ASSERTED" in v("部長は「太郎が資料Aを渡した」と言った。"),
            "different_doer_not_conflict": "CONTRADICTED" not in v("課長は鍵を管理しない。"),
        }
        st2 = Path(d) / "s2.db"
        compile_rows([("規程.txt", "経費の精算は経理課が行う。")], st2, decisions=[
            {"id": "n1", "at": "2026-01-10", "text": "出張の日当は支給しない。"},
            {"id": "n2", "at": "2026-09-01", "text": "出張の日当は支給する。", "supersedes": ["n1"]},
            {"id": "n3", "at": "2026-09-02", "text": "経費の精算は総務課が行う。"}])
        def v2(t):
            return [c["verdict"] for x in verify(st2, t)["sentences"] for c in x["claims"]]
        checks["superseded_ignored"] = "SUPPORTED" in v2("出張の日当を支給する。") and \
            "CONTRADICTED" not in v2("出張の日当を支給する。")
        checks["decision_outranks_doc"] = "SUPPORTED" in v2("総務課が経費の精算を行う。")
        checks["conflict_listed"] = any("日当" in c["relation"] for c in conflicts(st2)) is False
    return {"all_pass": all(checks.values()), **checks}
