"""Separate, append-safe question-family libraries for round 3.

The SQLite file holds attested questions and answers.  A conductive six-arm
tree holds routing surfaces only; its nodes never contain answer rows.  The
predicate index is the bounded 後退 when the surface cannot pick a leaf.
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import pickle
import re
import sqlite3
import time
import tokenize
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from . import conduct_tree
from .bot import _ja_words
from .cross_store import CrossStore
from .hierarchy import Node
from .lang import ja_content_runs
from .question import _slot
from .verdict import read_records

FAMILIES = ("general_qa", "code_qa", "figurative_commonsense", "narrative", "paraphrase_entail")
LEAF_CAP = 400
FRAME_CAP = 2000
FORMAT = 1
_PUN = re.compile(r"ダジャレ|だじゃれ|駄洒落|言葉遊び|なぞなぞ")
_HAIKU = re.compile(r"俳句|五七五|五・七・五")
_POEM = re.compile(r"詩|ポエム")
_STORY = re.compile(r"物語|ストーリー|お話")
_METAPHOR = re.compile(r"比喩|たとえ|ように|みたい|メタファー")
# One represented unknown per attested scene. These are grammatical question
# markers, not topics or example-specific words. Long markers precede prefixes.
_SCOPED_FOCUS = re.compile(
    r"何のため|何故|どうして|なぜ|どのように|どんなふうに|どうやって|どうすれば|"
    r"いくら|いくつ|何キログラム|何リットル|何営業日前|何円|何時|何年|何曜|"
    r"何(?:人|名|回|台|本|個|件|組|隻|種類|品目|脚|単位|冊|匹|点|枚|日)|"
    r"誰|だれ|(?<!な)いつ|どこ|どちらへ|なに|どれ|どんな|どの|何|どう|"
    r"\b(?:how much|how many|who|when|where|what|why|how)\b", re.I)
_UNREPRESENTED_FOCUS = {
    "何故", "何日", "どのように", "どんなふうに", "どうやって", "どうすれば", "どう", "how",
}


def _scoped_slot(question: str) -> str:
    """Only a single explicit focus may type a synthetic scene question.

    _slot's default ``what`` is useful to the old router but is not evidence
    that an unrecognised question has one represented answer slot.
    """
    focuses = list(_SCOPED_FOCUS.finditer(question))
    if len(focuses) != 1 or focuses[0].group().casefold() in _UNREPRESENTED_FOCUS:
        return ""
    focus = focuses[0]
    # Indefinites such as 誰か/何か are not a requested unknown.
    if re.match(r"か(?!ら)|でも", question[focus.end():]):
        return ""
    slot = _slot(question, "fact")
    return slot if slot == _slot(focus.group(), "fact") else ""


def _norm(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text.casefold())


def _terms(text: str) -> tuple[str, ...]:
    words = _ja_words(text)
    words.update(w.casefold() for w in re.findall(r"[A-Za-z][A-Za-z0-9_+#.-]*", text))
    return tuple(sorted(w for w in words if len(w) >= 2 and not w.isdecimal()))


def _record_variants(family: str, row: dict) -> tuple[list[str], str, str]:
    """Question surfaces, answer, and matching slot; never use an eval label."""
    kind = str(row.get("kind") or "")
    if family == "general_qa":
        variants = [str(x) for x in row.get("q_variants", []) if x]
        return variants, str(row.get("answer") or ""), (
            "social" if kind == "greeting" else _slot(variants[0], "fact") if variants else "what")
    if family == "code_qa":
        return [str(row.get("question") or "")], str(row.get("answer_text") or ""), "code"
    if family == "figurative_commonsense":
        if kind == "pun":
            return [" ".join(str(row.get(k) or "") for k in ("theme", "word_a", "word_b"))], str(row.get("pun") or ""), "pun"
        if kind == "haiku":
            return [" ".join(str(row.get(k) or "") for k in ("theme", "kigo", "season"))], str(row.get("haiku") or ""), "haiku"
        if kind == "simile_metaphor":
            return [" ".join(str(row.get(k) or "") for k in ("expression", "vehicle", "target"))], str(row.get("plain_meaning") or ""), "metaphor"
        if kind == "cause_effect":
            return [str(row.get("cause") or ""), *map(str, row.get("phrasings") or ())], str(row.get("effect") or ""), "why"
    if family == "narrative":
        variants = [" ".join(str(row.get(k) or "") for k in ("title", "theme", "setting"))]
        if kind == "story":
            return variants, "\n".join(str(s.get("text") or "") for s in row.get("sentences", [])), "story"
        return variants, "\n".join(map(str, row.get("lines") or ())), "poem"
    if family == "paraphrase_entail":
        if kind == "who_did_what":
            question = str(row.get("question") or "")
            slot = _scoped_slot(question)
            sentence = row.get("sentence")
            if not slot or not isinstance(sentence, str) or not sentence.strip():
                return [], "", ""
            return [question], str(row.get("answer") or ""), slot
        return [str(row.get("s1") or "") + " " + str(row.get("s2") or "")], str(row.get("label") or ""), "relation"
    return [], "", ""


def _group(family: str, row: dict) -> str:
    if family == "general_qa":
        return str(row.get("kind") or "") + "/" + str(row.get("domain") or "")
    if family == "code_qa":
        return str(row.get("lang") or "") + "/" + str(row.get("context") or "")
    if family == "paraphrase_entail":
        return str(row.get("kind") or "") + "/" + str(row.get("phenomenon") or "")
    return str(row.get("kind") or "") + "/" + str(row.get("theme") or row.get("setting") or "")


def _source_paths(corpus: Path, family: str) -> list[Path]:
    # Filename and split both gate ingestion. In-progress final lines are
    # handled by the offset reader; ledger and heldout files are never read.
    return sorted((corpus / "codex" / family / "from_pro").glob("records_*.jsonl"))


class FamilyLibrary:
    def __init__(self, directory: str | Path, family: str):
        if family not in FAMILIES:
            raise ValueError(f"unsupported family: {family}")
        self.directory = Path(directory)
        self.family = family
        self.db_path = self.directory / "family.db"
        self.route_path = self.directory / "route.pkl"
        self.con = sqlite3.connect(self.db_path)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA cache_size=-65536")
        self.con.execute("PRAGMA mmap_size=268435456")
        self.root: conduct_tree.Node | None = None
        self._route_mtime_ns = 0
        if self.route_path.exists():
            with self.route_path.open("rb") as f:
                version, self.root = pickle.load(f)
            if version != FORMAT:
                raise ValueError("unsupported family route format")
            self._route_mtime_ns = self.route_path.stat().st_mtime_ns

    def _refresh_route(self) -> None:
        if not self.route_path.exists():
            return
        mtime = self.route_path.stat().st_mtime_ns
        if mtime != self._route_mtime_ns:
            with self.route_path.open("rb") as f:
                version, route = pickle.load(f)
            if version != FORMAT:
                raise ValueError("unsupported family route format")
            self.root, self._route_mtime_ns = route, mtime

    @staticmethod
    def _schema(con: sqlite3.Connection) -> None:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS records(
                id INTEGER PRIMARY KEY, sha TEXT UNIQUE, leaf TEXT NOT NULL,
                grp TEXT NOT NULL, kind TEXT, slot TEXT, answer TEXT NOT NULL,
                source TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS variants(
                id INTEGER PRIMARY KEY, rid INTEGER NOT NULL, text TEXT NOT NULL,
                norm TEXT NOT NULL, terms TEXT NOT NULL, leaf TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS variants_norm ON variants(norm);
            CREATE INDEX IF NOT EXISTS variants_leaf ON variants(leaf);
            CREATE INDEX IF NOT EXISTS variants_rid ON variants(rid);
            CREATE TABLE IF NOT EXISTS terms(token TEXT NOT NULL, leaf TEXT NOT NULL, rid INTEGER NOT NULL,
                                             PRIMARY KEY(token,leaf,rid)) WITHOUT ROWID;
            CREATE INDEX IF NOT EXISTS terms_leaf_token ON terms(leaf,token,rid);
            CREATE TABLE IF NOT EXISTS frames(predicate TEXT NOT NULL, rid INTEGER NOT NULL,
                                              agent TEXT, patient TEXT, recipient TEXT, negated INTEGER,
                                              PRIMARY KEY(predicate,rid)) WITHOUT ROWID;
            CREATE TABLE IF NOT EXISTS relations(a TEXT NOT NULL,b TEXT NOT NULL,rid INTEGER NOT NULL,
                                                 PRIMARY KEY(a,b,rid)) WITHOUT ROWID;
            CREATE TABLE IF NOT EXISTS relation_seen(rid INTEGER PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS predicate_relations(premise TEXT,entailed TEXT,rid INTEGER,
                PRIMARY KEY(premise,entailed,rid)) WITHOUT ROWID;
            CREATE INDEX IF NOT EXISTS predicate_relations_entailed ON predicate_relations(entailed,premise,rid);
            CREATE TABLE IF NOT EXISTS predicate_relation_seen(rid INTEGER PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, offset INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS leaves(grp TEXT PRIMARY KEY, part INTEGER NOT NULL, count INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        """)

    @classmethod
    def build(cls, corpus: str | Path, family: str, directory: str | Path,
              *, leaf_cap: int = LEAF_CAP) -> dict:
        """Append complete train lines only; recompile routing after new rows."""
        if leaf_cap < 1:
            raise ValueError("leaf_cap must be positive")
        started = time.perf_counter()
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(target / "family.db")
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        cls._schema(con)
        inserted = 0
        read_lines = 0
        held = Counter()
        for path in _source_paths(Path(corpus), family):
            size = path.stat().st_size  # frozen prefix; writer may append
            saved = con.execute("SELECT offset FROM files WHERE path=?", (str(path),)).fetchone()
            offset = int(saved[0]) if saved else 0
            if offset > size:
                raise ValueError(f"source was truncated: {path}")
            with path.open("rb") as stream, con:
                stream.seek(offset)
                while stream.tell() < size:
                    begin = stream.tell()
                    line = stream.readline(size - begin)
                    if not line.endswith(b"\n"):
                        break
                    offset = stream.tell()
                    read_lines += 1
                    try:
                        row = json.loads(line)
                    except (ValueError, UnicodeDecodeError):
                        continue
                    if (not isinstance(row, dict) or row.get("split") != "train" or
                            "verdict" in row or row.get("family") != family):
                        continue
                    variants, answer, slot = _record_variants(family, row)
                    if family == "paraphrase_entail" and row.get("kind") == "who_did_what" and not variants:
                        reason = ("missing_scene" if not isinstance(row.get("sentence"), str)
                                  or not row["sentence"].strip() else "unsupported_question_slot")
                        held[reason] += 1
                    variants = [v.strip() for v in variants if v.strip()]
                    if not variants or not answer:
                        continue
                    sha = str(row.get("sha") or hashlib.sha256(line).hexdigest())
                    if con.execute("SELECT 1 FROM records WHERE sha=?", (sha,)).fetchone():
                        continue
                    grp = _group(family, row)
                    state = con.execute("SELECT part,count FROM leaves WHERE grp=?", (grp,)).fetchone()
                    part, count = (int(state[0]), int(state[1])) if state else (0, 0)
                    if count >= leaf_cap:
                        part, count = part + 1, 0
                    leaf = f"{grp}/{part:05d}"
                    cur = con.execute("INSERT INTO records(sha,leaf,grp,kind,slot,answer,source,payload)"
                                      " VALUES(?,?,?,?,?,?,?,?)",
                                      (sha, leaf, grp, str(row.get("kind") or ""), slot, answer,
                                       str(row.get("source") or ""), json.dumps(row, ensure_ascii=False)))
                    rid = cur.lastrowid
                    con.execute("INSERT OR REPLACE INTO leaves VALUES(?,?,?)", (grp, part, count + 1))
                    all_terms: set[str] = set()
                    for variant in variants:
                        tokens = _terms(variant)
                        con.execute("INSERT INTO variants(rid,text,norm,terms,leaf) VALUES(?,?,?,?,?)",
                                    (rid, variant, _norm(variant), json.dumps(tokens, ensure_ascii=False), leaf))
                        all_terms.update(tokens)
                    con.executemany("INSERT OR IGNORE INTO terms VALUES(?,?,?)",
                                    ((t, leaf, rid) for t in all_terms))
                    for item in read_records(variants[0]):
                        frame = item.frame
                        if frame.predicate:
                            con.execute("INSERT OR IGNORE INTO frames VALUES(?,?,?,?,?,?)",
                                        (frame.predicate, rid, frame.agent, frame.patient,
                                         frame.recipient, int(frame.negated)))
                    inserted += 1
                con.execute("INSERT OR REPLACE INTO files VALUES(?,?)", (str(path), offset))
        con.commit()
        if family == "paraphrase_entail":
            # Extract only an attested predicate equivalence with matching
            # roles. The source pair's label is never transferred wholesale.
            with con:
                for rid, encoded in con.execute(
                        "SELECT id,payload FROM records WHERE kind='pair' AND "
                        "id NOT IN (SELECT rid FROM relation_seen)"):
                    row = json.loads(encoded)
                    if row.get("label") == "paraphrase":
                        left = [x.frame for x in read_records(str(row.get("s1") or "")) if x.frame.predicate]
                        right = [x.frame for x in read_records(str(row.get("s2") or "")) if x.frame.predicate]
                        if len(left) == len(right) == 1:
                            a, b = left[0], right[0]
                            if (a.predicate != b.predicate and a.agent and _norm(a.agent) == _norm(b.agent)
                                    and (not a.patient or not b.patient or _norm(a.patient) == _norm(b.patient))
                                    and (not a.recipient or not b.recipient or
                                         _norm(a.recipient) == _norm(b.recipient))
                                    and a.negated == b.negated and a.past == b.past):
                                p, q = sorted((a.predicate, b.predicate))
                                con.execute("INSERT OR IGNORE INTO relations VALUES(?,?,?)", (p, q, rid))
                    con.execute("INSERT OR IGNORE INTO relation_seen VALUES(?)", (rid,))
            from .frames import canonical
            with con:
                for rid, encoded in con.execute(
                        "SELECT id,payload FROM records WHERE kind='pair' AND "
                        "id NOT IN (SELECT rid FROM predicate_relation_seen)"):
                    row = json.loads(encoded)
                    label = row.get("label")
                    if label in ("paraphrase", "entail", "entails", "entailment"):
                        left = [item.frame for item in read_records(str(row.get("s1") or "")) if item.frame.predicate]
                        right = [item.frame for item in read_records(str(row.get("s2") or "")) if item.frame.predicate]
                        if len(left) == len(right) == 1:
                            premise, entailed = left[0], right[0]
                            patients_match = (_norm(premise.patient) == _norm(entailed.patient) or
                                not premise.patient and entailed.patient and entailed.patient in premise.predicate or
                                not entailed.patient and premise.patient and premise.patient in entailed.predicate)
                            if (premise.agent and _norm(premise.agent) == _norm(entailed.agent) and
                                    patients_match and _norm(premise.recipient) == _norm(entailed.recipient) and
                                    premise.negated == entailed.negated and premise.past == entailed.past):
                                first, second = canonical(premise.predicate), canonical(entailed.predicate)
                                con.execute("INSERT OR IGNORE INTO predicate_relations VALUES(?,?,?)", (first, second, rid))
                                if label == "paraphrase":
                                    con.execute("INSERT OR IGNORE INTO predicate_relations VALUES(?,?,?)", (second, first, rid))
                    con.execute("INSERT OR IGNORE INTO predicate_relation_seen VALUES(?)", (rid,))
        route_path = target / "route.pkl"
        if inserted or not route_path.exists():
            root = cls._compile_route(con, family)
            temporary = route_path.with_suffix(".tmp")
            with temporary.open("wb") as f:
                pickle.dump((FORMAT, root), f, protocol=pickle.HIGHEST_PROTOCOL)
            temporary.replace(route_path)
        count = con.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        leaves = con.execute("SELECT COUNT(DISTINCT leaf) FROM records").fetchone()[0]
        con.close()
        if family == "general_qa":
            from .evidence_library import EvidenceLibrary
            evidence = EvidenceLibrary.from_qa(target)
        else:
            evidence = None
        return {"family": family, "rows": count, "new_rows": inserted, "lines_read": read_lines,
                "held_who_did_what": dict(held),
                "leaves": leaves, "leaf_cap": leaf_cap,
                "build_s": round(time.perf_counter() - started, 3),
                "db_bytes": (target / "family.db").stat().st_size,
                "route_bytes": route_path.stat().st_size, "evidence": evidence}

    @staticmethod
    def _compile_route(con: sqlite3.Connection, family: str) -> conduct_tree.Node | None:
        crosses: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(dict))
        for leaf, encoded in con.execute("SELECT leaf,terms FROM variants ORDER BY id"):
            tokens = json.loads(encoded)[:10]
            for core in tokens:
                facets = crosses[leaf][core]
                for facet in tokens:
                    if facet != core:
                        facets[facet] = facets.get(facet, 0) + 1
        if not crosses:
            return None
        stores: dict[str, dict] = {}
        for leaf, values in crosses.items():
            # Every core remains a held routing term. Cap only its surface
            # neighbours, not the source questions or answer rows.
            stores[leaf] = {core: dict(sorted(facets.items(), key=lambda kv: (-kv[1], kv[0]))[:8])
                            for core, facets in values.items()}
        level = {name: Node(name=name, store=CrossStore(crosses=cross))
                 for name, cross in sorted(stores.items())}
        depth = 0
        while len(level) > 6:
            size = (len(level) + 5) // 6
            names = list(level)
            level = {f"{family}:L{depth}:{i // size}": Node(
                name=f"{family}:L{depth}:{i // size}",
                children={name: level[name] for name in names[i:i + size]})
                for i in range(0, len(names), size)}
            depth += 1
        hierarchy = Node(name=family, children=level)
        return conduct_tree.build(stores, hierarchy=hierarchy)

    def _candidate_ids(self, text: str, tokens: tuple[str, ...], slot: str,
                       route: dict) -> tuple[list[int], str]:
        exact = [int(r[0]) for r in self.con.execute(
            "SELECT DISTINCT rid FROM variants WHERE norm=? LIMIT 80", (_norm(text),))]
        if exact:
            return exact, "exact_surface"
        if route.get("verdict") == "ROUTED" and tokens:
            leaf = route["leaf"]
            marks = ",".join("?" for _ in tokens)
            ids = [int(r[0]) for r in self.con.execute(
                f"SELECT rid FROM terms WHERE leaf=? AND token IN ({marks}) "
                "GROUP BY rid ORDER BY COUNT(*) DESC LIMIT 100", (leaf, *tokens))]
            if ids:
                return ids, "conduct"
        # Predicate-keyed, fixed budget. No whole-family nearest-neighbour
        # scan is allowed to turn an unrecognised question into an answer.
        ids: list[int] = []
        for item in read_records(text):
            if not item.frame.predicate:
                continue
            for r in self.con.execute("SELECT rid FROM frames WHERE predicate=? LIMIT ?",
                                      (item.frame.predicate, FRAME_CAP)):
                rid = int(r[0])
                if rid not in ids:
                    ids.append(rid)
                if len(ids) >= FRAME_CAP:
                    break
            if len(ids) >= FRAME_CAP:
                break
        return ids, "fallback_frames" if ids else "refused"

    def ask(self, text: str, *, slot: str | None = None, kind: str | None = None,
            context: str | None = None) -> dict:
        """Retrieve an attested answer; scene rows require exact explicit scope.

        ``context`` is the unchanged source sentence for who_did_what, never
        implicit general knowledge. It neither approves the corpus label nor
        claims the independent semantic verifier has checked it.
        """
        started = time.perf_counter()
        self._refresh_route()
        tokens = _terms(text)
        runs = ja_content_runs(text)
        anchor = next((r for r in runs if len(r) >= 2), None)
        route = (conduct_tree.descend(self.root, sorted(set(tokens) | set(runs)), anchor=anchor)
                 if self.root is not None else {"verdict": "UNKNOWN_NO_ROUTE", "trail": []})
        requested_slot = slot or _slot(text, "fact")
        ids, path = self._candidate_ids(text, tokens, requested_slot, route)
        if not ids:
            return self._refusal(path, route, started, "UNKNOWN_NO_MATCH")
        marks = ",".join("?" for _ in ids)
        records = {int(r["id"]): r for r in self.con.execute(
            f"SELECT * FROM records WHERE id IN ({marks})", ids)}
        variants: dict[int, list[tuple[str, set[str]]]] = defaultdict(list)
        for row in self.con.execute(f"SELECT rid,text,terms FROM variants WHERE rid IN ({marks})", ids):
            variants[int(row["rid"])].append((row["text"], set(json.loads(row["terms"]))))
        query_terms = set(tokens)
        ranked = []
        scope_refusals = set()
        for rid, record in records.items():
            if self.family == "paraphrase_entail" and record["kind"] == "who_did_what":
                payload = json.loads(record["payload"])
                question = str(payload.get("question") or "")
                actual_slot = _scoped_slot(question)
                if not actual_slot or not isinstance(payload.get("sentence"), str) or not payload["sentence"].strip():
                    scope_refusals.add("UNKNOWN_UNSUPPORTED_SCENE")
                    continue
                if actual_slot != record["slot"]:
                    scope_refusals.add("UNKNOWN_INDEX_REBUILD_REQUIRED")
                    continue
                if context is None:
                    scope_refusals.add("UNKNOWN_CONTEXT_REQUIRED")
                    continue
                if context != payload["sentence"] or text != question:
                    scope_refusals.add("UNKNOWN_CONTEXT_MISMATCH")
                    continue
            if record["slot"] != requested_slot or (kind and record["kind"] != kind):
                continue
            scores = []
            for variant, own in variants[rid]:
                if _norm(variant) == _norm(text):
                    scores.append(10.0)
                elif query_terms and own:
                    shared = len(query_terms & own)
                    if shared >= 2:
                        scores.append(.5 * shared / len(query_terms) + .5 * shared / len(own))
            if scores:
                ranked.append((max(scores), rid))
        ranked.sort(key=lambda x: (-x[0], x[1]))
        if not ranked and scope_refusals:
            # All are refusals, not competing evidence. Do not choose a scene
            # or an answer merely because one refusal reason sorts first.
            result = self._refusal(path, route, started, "UNKNOWN_SCENE_SCOPE")
            result["scope_reasons"] = sorted(scope_refusals)
            result["how_to_resolve"] = "元の文と単一項目の質問をそのまま指定し、未対応の索引は別バージョンで再構築してください。"
            return result
        if not ranked or ranked[0][0] < .62:
            return self._refusal(path, route, started, "UNKNOWN_WEAK_MATCH")
        if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < .06:
            return self._refusal(path, route, started, "TIED_ABSTAIN")
        score, rid = ranked[0]
        row = records[rid]
        payload = json.loads(row["payload"])
        answer = row["answer"]
        if self.family == "code_qa" and payload.get("code"):
            answer = self._code_answer(text, payload)
        source_id = f"{row['source']}:{row['sha']}"
        result = {"kind": "answer", "verdict": "ANSWER", "text": answer,
                "family": self.family, "source": source_id,
                "sources": [{"family": self.family, "source": source_id,
                             "question": variants[rid][0][0], "text": row["answer"]}],
                "evidence": [row["answer"]], "payload": payload,
                "path": path, "route_trace": route, "score": round(score, 3),
                "ms": round((time.perf_counter() - started) * 1000, 3)}
        if self.family == "paraphrase_entail" and row["kind"] == "who_did_what":
            result["scope"] = {"kind": "attested_example", "sentence": payload["sentence"],
                               "question": payload["question"], "matching": "exact"}
            result["sources"][0]["text"] = payload["sentence"]
            result["sources"][0]["answer"] = answer
            result["evidence"] = [payload["sentence"]]
        return result

    def _code_answer(self, text: str, payload: dict) -> str:
        code = str(payload["code"])
        lang = str(payload.get("lang") or "")
        # Only explicit Python token substitutions are allowed. String and
        # comment contents are never changed by an identifier rename.
        named = re.search(r"(?:関数名(?:は|を)|function named)\s*[`「]?([A-Za-z_][A-Za-z_0-9]*)", text, re.I)
        literal = re.search(r"(?:文字列|リテラル)[「『]([^」』]{0,30})[」』]を[「『]([^」』]{0,30})[」』]に", text)
        adaptations: list[str] = []
        if lang.casefold() == "python" and (named or literal):
            try:
                tree = ast.parse(code)
                definitions = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                stream = list(tokenize.generate_tokens(io.StringIO(code).readline))
                changed = stream[:]
                if named and len(definitions) == 1:
                    old = definitions[0].name
                    if (named.group(1) != old and not any(
                            t.type == tokenize.NAME and t.string == named.group(1) for t in stream)):
                        changed = [t._replace(string=named.group(1))
                                   if t.type == tokenize.NAME and t.string == old else t for t in changed]
                        adaptations.append("関数名")
                if literal:
                    old, new = literal.group(1), literal.group(2)
                    positions = []
                    for i, token in enumerate(changed):
                        if token.type == tokenize.STRING:
                            try:
                                if ast.literal_eval(token.string) == old:
                                    positions.append(i)
                            except (ValueError, SyntaxError):
                                pass
                    if len(positions) == 1 and old != new:
                        index = positions[0]
                        changed[index] = changed[index]._replace(string=repr(new))
                        adaptations.append("文字列")
                if adaptations:
                    candidate = tokenize.untokenize(changed)
                    ast.parse(candidate)
                    code = candidate
            except (SyntaxError, ValueError, tokenize.TokenError):
                adaptations.clear()
        fence = "python" if lang.casefold() == "python" else lang.casefold()
        note = ("指定された" + "と".join(adaptations) + "に置き換えた例です。"
                if adaptations else "出典にあるコードをそのまま示す例です。")
        return f"{payload.get('answer_text', '')}\n\n{note}\n```{fence}\n{code}\n```"

    def _refusal(self, path: str, route: dict, started: float, verdict: str) -> dict:
        return {"kind": "unknown", "verdict": verdict,
                "text": "根拠が一致する質問を見つけられません。",
                "how_to_resolve": "質問と同じ対象・項目を扱う出典を追加してください。",
                "evidence": [], "sources": [], "family": self.family,
                "path": path, "route_trace": route,
                "ms": round((time.perf_counter() - started) * 1000, 3)}

    def relation_answer(self, text: str) -> dict | None:
        """Apply an attested predicate relation to a newly read sentence pair."""
        if self.family != "paraphrase_entail":
            return None
        quoted = re.findall(r"[「『]([^」』]+)[」』]", text)
        if len(quoted) != 2:
            return None
        frames = [[item.frame for item in read_records(sentence) if item.frame.predicate]
                  for sentence in quoted]
        if any(len(group) != 1 for group in frames):
            return None
        left, right = frames[0][0], frames[1][0]
        if (not left.agent or _norm(left.agent) != _norm(right.agent) or left.past != right.past or
                left.patient and right.patient and _norm(left.patient) != _norm(right.patient) or
                left.recipient and right.recipient and _norm(left.recipient) != _norm(right.recipient)):
            return None
        p, q = sorted((left.predicate, right.predicate))
        witnesses = list(self.con.execute(
            "SELECT r.source,r.sha,r.payload FROM relations x JOIN records r ON r.id=x.rid "
            "WHERE x.a=? AND x.b=? LIMIT 8", (p, q)))
        if not witnesses:
            return None
        source, sha, encoded = witnesses[0]
        pair = json.loads(encoded)
        same = left.negated == right.negated
        answer = ("はい。同じ行為を言い換えています。" if same else
                  "いいえ。一方はその行為を否定しています。")
        evidence = str(pair["s1"]) + " / " + str(pair["s2"])
        return {"kind": "answer", "verdict": "ANSWER", "text": answer,
                "family": self.family, "source": f"{source}:{sha}",
                "evidence": [evidence], "sources": [{"family": self.family,
                "source": f"{source}:{sha}", "text": evidence}],
                "path": "predicate_relation_lexicon",
                "relation": {"predicates": [p, q], "same_roles": True,
                             "same_tense": True, "same_polarity": same}}

    def close(self) -> None:
        self.con.close()
