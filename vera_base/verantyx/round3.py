"""Deterministic family handoff for general questions and composition."""
from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Any

from .family_library import FamilyLibrary, _norm, _terms

_LIVE_TIME = re.compile(r"今日|本日|現在|いまの|今の|最新|速報|リアルタイム|明日|今週|\b(?:today|current|latest|live|tomorrow)\b", re.I)
_LIVE_DYNAMIC = re.compile(r"天気|気温|花粉|株価|為替|運行状況|交通情報|ニュース|選挙結果|時刻|価格|相場|首相|大統領|社長|代表|順位|試合結果|予定|営業時間|在庫|空席|発売|\b(?:weather|stock price|exchange rate|news|forecast|president|ceo|schedule|availability)\b", re.I)
_CODE = re.compile(r"コード|関数|プログラム|実装|Python|JavaScript|TypeScript|SQL|正規表現|スクリプト|API|デバッグ|アルゴリズム|\b(?:code|function|script|regex|program)\b", re.I)
_HAIKU = re.compile(r"俳句|五七五|五・七・五")
_PUN = re.compile(r"ダジャレ|だじゃれ|駄洒落|言葉遊び|なぞなぞ")
_METAPHOR = re.compile(r"比喩|たとえ|ように|みたい|メタファー")
_STORY = re.compile(r"物語|ストーリー|お話")
_POEM = re.compile(r"詩|ポエム")
_UNDERSTAND = re.compile(r"同じ意味|言い換え|矛盾|含意|誰が何を|誰が.*(?:した|された)|\b(?:entail|paraphrase|contradict)\b", re.I)
_COMMON = re.compile(r"なぜ|どうして|何のため|どうな|どうすれば|原因|結果|危険|常識")
_CREATIVE_WORDS = {"俳句", "物語", "ストーリー", "お話", "詩", "ポエム", "作る", "書く", "ください",
                   "創作", "短い", "一つ", "台詞", "場面"}
_SOCIAL_START = re.compile(r"^(?:こんにちは|こんばんは|おはよう|はじめまして|やあ|どうも|ありがとう|さようなら|またね)")
_FEELING = re.compile(r"疲れ|つらい|辛い|悲しい|うれしい|嬉しい|不安|寂しい|楽しい|落ち込|緊張|憂鬱|安心")


def route(text: str, reading: Any) -> tuple[str, str | None, str]:
    """Return family, requested stored slot, route reason. No evidence vote."""
    act = reading.speech_act.value.act
    social_prefix = bool(_SOCIAL_START.search(text) and not re.search(
        r"何|なぜ|どこ|いつ|いくら|どうして|天気|株価|コード|関数", text))
    feeling_turn = bool(_FEELING.search(text) and re.search(
        r"^(?:私は|自分は|今日は|少し|ちょっと|とても|なんだか|疲れ|つらい|悲しい|嬉しい|不安|寂しい|落ち込)", text) and
        not re.search(r"なぜ|どうして|原因|理由", text))
    if social_prefix or feeling_turn or act in ("greeting", "thanks", "apology", "farewell") or re.search(
            r"^(?:疲れ|つらい|辛い|悲しい|うれしい|嬉しい|不安|寂しい|楽しい)|(?:今日は|少し|とても).{0,8}(?:疲れ|つらい|悲しい|嬉しい|不安)", text) or reading.kind.value == "chat" and re.fullmatch(
            r"(?:こんにちは|こんばんは|おはよう|やあ|どうも|ありがとう|ごめん)(?:です)?[。!！?？]*", text):
        return "conversation", "social", "speech_act"
    creative = bool(_HAIKU.search(text) or _PUN.search(text) or _STORY.search(text) or _POEM.search(text))
    if (_LIVE_TIME.search(text) and _LIVE_DYNAMIC.search(text) and
            not (creative and re.search(r"作って|書いて|考えて", text))):
        return "live", None, "temporal_request"
    if _CODE.search(text) and (reading.kind.value != "definition" or "```" in text):
        return "code_qa", "code", "code_cue"
    if _UNDERSTAND.search(text):
        return "paraphrase_entail", "who" if reading.asked_slot.value == "who" else "relation", "relation_cue"
    if _HAIKU.search(text):
        return "figurative_commonsense", "haiku", "haiku_cue"
    if _PUN.search(text):
        return "figurative_commonsense", "pun", "pun_cue"
    if _METAPHOR.search(text):
        return "figurative_commonsense", "metaphor", "figurative_cue"
    if _STORY.search(text):
        return "narrative", "story", "narrative_cue"
    if _POEM.search(text):
        return "narrative", "poem", "narrative_cue"
    if _COMMON.search(text) and reading.kind.value in ("fact", "why", "condition"):
        return "figurative_commonsense", "why", "causal_cue"
    return "general_qa", reading.asked_slot.value or "what", "question_kind"


def _refuse(verdict: str, text: str, how: str) -> dict:
    return {"kind": "unknown", "verdict": verdict, "text": text,
            "how_to_resolve": how, "evidence": [], "sources": []}


def _substantive(result: dict | None) -> bool:
    return bool(result and result.get("kind") not in ("unknown", "not_yet", "cannot", "unreadable")
                and not re.search(r"分かりません|わかりません|確認できません|根拠が足りません", str(result.get("text") or "")))


def _named_topic_terms(text: str) -> set[str]:
    quoted = re.search(r"(?:題材[：:]\s*)?[「『]([^」』]+)[」』]", text)
    labelled = re.search(r"題材[：:]\s*([^。！？!?]{2,40})", text)
    topic = quoted.group(1) if quoted else labelled.group(1) if labelled else ""
    return {word for word in _terms(topic) if word not in _CREATIVE_WORDS}


def _topic_covered(text: str, created: str) -> bool:
    topics = _named_topic_terms(text)
    if not topics:
        return True
    covered = sum(word in created for word in topics)
    return covered >= min(2, len(topics))


class GeneralRouter:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self._loaded: dict[str, FamilyLibrary] = {}

    def available(self) -> bool:
        return any((self.root / name / "family.db").exists() for name in
                   ("general_qa", "code_qa", "figurative_commonsense", "narrative", "paraphrase_entail")) or any(
                   (self.root / name / "evidence" / "evidence.db").exists()
                   for name in ("local", "pro", "jawiki"))

    def library(self, family: str) -> FamilyLibrary | None:
        if family in self._loaded:
            return self._loaded[family]
        if (self.root / family / "family.db").exists():
            self._loaded[family] = FamilyLibrary(self.root / family, family)
            return self._loaded[family]
        return None

    @staticmethod
    def _trace(family: str, status: str, **details: Any) -> dict:
        return {"part": "round3.family." + family, "status": status, "family": family, **details}

    def answer(self, text: str, reading: Any, *, abilities: Any = None) -> tuple[dict, list[dict]]:
        family, slot, reason = route(text, reading)
        trace = [{"part": "round3.route", "status": "ran", "family": family,
                  "slot": slot, "reason": reason}]
        if family == "live":
            trace.append(self._trace("live", "abstained", verdict="UNKNOWN_LIVE_DATA"))
            return _refuse("UNKNOWN_LIVE_DATA", "現在の情報を確認できません。",
                           "地域と時刻を指定して、気象機関などの最新情報を確認してください。"), trace
        if family == "code_qa":
            from .code_compose import answer as compose_code
            result = compose_code(text)
            trace.append(self._trace("code_qa", "ran" if result["verdict"] == "ANSWER" else "abstained",
                                     role="spec_composer", path=result.get("path")))
            return result, trace
        if family == "conversation":
            social = self._conversation_supply(text, reading)
            trace.append(self._trace("conversation", "ran" if social else "abstained",
                                     role="social_supply", verdict=social.get("verdict") if social else "UNKNOWN_NO_STRICT_TURN"))
            if social:
                return social, trace
            trace.append(self._trace("general_qa", "abstained", role="social_not_factual"))
            social = self._social_frame(text, reading)
            if social:
                return social, trace
            family, slot = "general_qa", "social"
        if family == "general_qa" and slot != "social" or family == "figurative_commonsense" and slot == "why":
            return self._evidence_answer(text, reading, trace)
        if family == "paraphrase_entail" and abilities is not None:
            structural = abilities.answer(text, reading)
            trace.append({"part": "round3.verdict_frames", "status": "ran" if structural else "abstained",
                          "verdict": structural.get("verdict") if structural else None})
            if _substantive(structural):
                return structural, trace
        lib = self.library(family)
        if lib is None:
            trace.append(self._trace(family, "abstained", reason="library not built"))
            if family == "figurative_commonsense" and slot == "why":
                family = "general_qa"
                lib = self.library(family)
                slot = reading.asked_slot.value or "why"
                if lib is not None:
                    trace.append(self._trace(family, "ran", reason="causal family unavailable"))
            if lib is None:
                return _refuse("UNKNOWN_FAMILY_NOT_BUILT", "この分野の出典がまだありません。",
                               f"tools/build_round3.py で {family} を構築してください。"), trace
        kind = None
        if family == "figurative_commonsense":
            kind = {"pun": "pun", "haiku": "haiku", "metaphor": "simile_metaphor", "why": "cause_effect"}.get(slot)
        elif family == "narrative":
            kind = slot
        elif family == "general_qa" and slot == "social":
            kind = "greeting"
        elif family == "paraphrase_entail":
            kind = "who_did_what" if slot == "who" else "pair"
        if family == "paraphrase_entail" and kind == "pair":
            relation = lib.relation_answer(text)
            trace.append({"part": "round3.relation_lexicon",
                          "status": "ran" if relation else "abstained",
                          "verdict": relation.get("verdict") if relation else "UNKNOWN_NO_ATTESTED_PREDICATE_RELATION"})
            if relation:
                return relation, trace
        causal_direction_unclear = (family == "figurative_commonsense" and slot == "why" and
                                   bool(re.search(r"なぜ|どうして|何のため|理由|危険|注意", text)))
        if causal_direction_unclear:
            result = _refuse("UNKNOWN_CAUSAL_DIRECTION", "因果の向きが確認できません。",
                             "原因と結果の向きが明示された出典を追加してください。")
            result.update(path="refused", route_trace={"verdict": "UNKNOWN_NO_ROUTE", "trail": []})
        else:
            result = lib.ask(text, slot=slot, kind=kind)
        trace.append(self._trace(family, "ran" if result.get("verdict") == "ANSWER" else "abstained",
                                 verdict=result.get("verdict"), path=result.get("path"),
                                 route=result.get("route_trace")))
        if result.get("verdict") == "ANSWER":
            if family == "paraphrase_entail" and kind == "pair":
                # The label is licensed only for this exact attested pair.
                given = re.sub(r"[\s\W_]+", "", text.casefold())
                pair = result["payload"]
                attested = re.sub(r"[\s\W_]+", "", (pair["s1"] + pair["s2"]).casefold())
                if given != attested:
                    trace.append(self._trace(family, "abstained", reason="pair label is not transferable"))
                else:
                    return result, trace
            else:
                return result, trace
        if family == "code_qa":
            supplemental = self._code_supply(text)
            trace.append(self._trace("code", "ran" if supplemental else "abstained",
                                     reason="separate P4 code corpus"))
            if supplemental:
                return supplemental, trace
        if family == "figurative_commonsense" and slot == "haiku":
            composed = self._compose_haiku(lib, text)
            trace.append({"part": "round3.compose.haiku", "status": "ran" if composed else "abstained",
                          "verdict": composed.get("verdict") if composed else "UNKNOWN_NO_COMPATIBLE_LINES"})
            if composed:
                return composed, trace
        if family == "figurative_commonsense" and slot == "metaphor":
            composed = self._compose_metaphor(lib, text)
            trace.append({"part": "round3.compose.metaphor", "status": "ran" if composed else "abstained",
                          "verdict": composed.get("verdict") if composed else "UNKNOWN_NO_ATTESTED_VEHICLE"})
            if composed:
                return composed, trace
        if family == "figurative_commonsense" and slot == "pun":
            composed = self._compose_pun(lib, text)
            trace.append({"part": "round3.compose.pun", "status": "ran" if composed else "abstained",
                          "verdict": composed.get("verdict") if composed else "UNKNOWN_NO_READING_MECHANISM"})
            if composed:
                return composed, trace
        if family == "narrative" and slot == "story":
            composed = self._compose_story(lib, text)
            trace.append({"part": "round3.compose.story", "status": "ran" if composed else "abstained",
                          "verdict": composed.get("verdict") if composed else "UNKNOWN_NO_SHARED_ACTOR"})
            if composed:
                return composed, trace
        if family in ("figurative_commonsense", "narrative", "general_qa") and abilities is not None:
            structural = abilities.answer(text, reading)
            trace.append({"part": "round3.p4_composition", "status": "ran" if structural else "abstained",
                          "verdict": structural.get("verdict") if structural else None})
            if _substantive(structural):
                return structural, trace
        if family == "figurative_commonsense" and slot == "why":
            other = self.library("general_qa")
            if other is not None:
                proposal = other.ask(text, slot=reading.asked_slot.value or "why")
                trace.append(self._trace("general_qa", "ran" if proposal.get("verdict") == "ANSWER" else "abstained",
                                         verdict=proposal.get("verdict"), path=proposal.get("path")))
                if proposal.get("verdict") == "ANSWER":
                    return proposal, trace
        return result, trace

    def _evidence_answer(self, text: str, reading: Any, trace: list[dict]) -> tuple[dict, list[dict]]:
        from .answer_slots import read_slot, select
        from .evidence_library import EvidenceLibrary
        asked = reading.case_frame.value if reading.case_frame else read_slot(text, reading.asked_slot.value or "what")
        trace.append({"part": "answer_slots.read_slot", "status": "ran", "frame": asked.as_dict()})
        if not hasattr(self, "_evidence"):
            self._evidence = {}
        candidates, aliases = [], {}
        relations = self.library("paraphrase_entail")
        used_relations = []
        has_directed = bool(relations and relations.con.execute(
            "SELECT 1 FROM sqlite_master WHERE name='predicate_relations'").fetchone())
        related_keys = []
        if has_directed:
            for predicate in asked.predicates:
                related_keys.extend(row[0] for row in relations.con.execute(
                    "SELECT DISTINCT premise FROM predicate_relations WHERE entailed=? LIMIT 40", (predicate,)))
        def relation(asked_predicate, stated_predicate, sentence):
            if relations is None:
                return False
            if has_directed:
                row = relations.con.execute(
                    "SELECT r.source,r.sha,r.payload FROM predicate_relations p JOIN records r ON r.id=p.rid "
                    "WHERE p.premise=? AND p.entailed=? LIMIT 1", (stated_predicate, asked_predicate)).fetchone()
            else:
                left, right = sorted((asked_predicate, stated_predicate))
                row = relations.con.execute(
                    "SELECT r.source,r.sha,r.payload FROM relations p JOIN records r ON r.id=p.rid WHERE p.a=? AND p.b=? LIMIT 1",
                    (left, right)).fetchone()
            if row is None:
                return False
            payload = json.loads(row["payload"])
            from .frames import canonical, read_all
            first = read_all(payload["s1"])
            second = read_all(payload["s2"])
            if len(first) != 1 or len(second) != 1:
                return False
            premise = next((frame for frame in (*first, *second) if canonical(frame.predicate) == stated_predicate), None)
            entailed = next((frame for frame in (*first, *second) if canonical(frame.predicate) == asked_predicate), None)
            if premise is None or entailed is None:
                return False
            if premise.patient and premise.patient != entailed.patient:
                if not any(canonical(frame.predicate) == stated_predicate and frame.patient == premise.patient
                           for frame in read_all(sentence)):
                    return False
            used_relations.append({"family": "paraphrase_entail", "source": row["source"] + ":" + row["sha"],
                                   "text": payload["s1"] + " / " + payload["s2"]})
            return True
        for family in ("general_qa", "local", "pro", "jawiki"):
            directory = self.root / family / "evidence"
            if not (directory / "evidence.db").exists():
                trace.append(self._trace(family, "abstained", role="answer_sentences", reason="evidence not built"))
                continue
            if family not in self._evidence:
                self._evidence[family] = EvidenceLibrary(directory, family)
            rows, route_trace = self._evidence[family].candidates(asked, related_keys=tuple(related_keys))
            candidates.extend(rows)
            aliases.update(route_trace["aliases"])
            trace.append(self._trace(family, "ran" if rows else "abstained", role="answer_sentences", **route_trace))
        selected = select(candidates, asked, aliases=aliases, relation=relation)
        trace.append({"part": "answer_slots.select", "status": "ran" if selected["verdict"] == "ANSWER" else "abstained",
                      "verdict": selected["verdict"], "qualified_candidates": len(selected.get("rows", []))})
        if selected["verdict"] == "ANSWER":
            from .answer_slots import qualifies
            rows = selected["rows"]
            used_relations.clear()
            for row in rows:
                qualifies(row["text"], asked, context=row["context"], context_slot=row["slot"], aliases=aliases, relation=relation)
            sources = [{"family": row["family"], "source": row["source"], "text": row["text"],
                        "context": row["context"]} for row in rows]
            sources.extend(used_relations)
            evidence = list(dict.fromkeys([rows[0]["text"], *[row["context"] for row in rows if row["context"]]]))
            return {"kind": "answer", "verdict": "ANSWER", "text": "「" + rows[0]["text"] + "」（出典: " + rows[0]["source"] + "）",
                    "source": rows[0]["source"], "evidence": evidence, "sources": sources,
                    "path": "subject_predicate_slot", "frame": asked.as_dict()}, trace
        closest = selected["candidates"]
        result = _refuse(selected["verdict"], "求められた枠の根拠を確定できません。" +
                         ("\n候補:\n" + "\n".join("- " + row["text"] for row in closest) if closest else ""),
                         "主語、求める述語と値が明記された独立の出典を追加してください。")
        result.update(candidates=closest, evidence=[row["text"] for row in closest],
                      sources=[{"family": row["family"], "source": row["source"], "text": row["text"]} for row in closest])
        return result, trace

    @staticmethod
    def _social_frame(text: str, reading: Any) -> dict | None:
        act = reading.speech_act.value.act
        if _SOCIAL_START.search(text):
            act = "thanks" if text.startswith("ありがとう") else "farewell" if text.startswith(("さようなら", "またね")) else "greeting"
        forms = {"greeting": "こんにちは。", "thanks": "どういたし" + "まして。", "apology": "お話を" + "聞きます。",
                 "farewell": "また、" + "お話ししましょう。"}
        if act not in forms:
            if _FEELING.search(text):
                act = "feeling"
                spoken = "気持ちを" + "聞かせてください。"
            else:
                return None
        else:
            spoken = forms[act]
            if act == "greeting":
                if text.startswith("おはよう"):
                    spoken = "おはよう" + "ございます。"
                elif text.startswith("こんばんは"):
                    spoken = "こんばんは。"
                elif text.startswith("はじめまして"):
                    spoken = "はじめまして。"
        return {"kind": "social", "verdict": "ANSWER", "text": spoken, "path": "speech_act_frame",
                "evidence": [text], "sources": [{"family": "conversation", "source": "conversation_form:" + act,
                "text": spoken}, {"family": "user", "source": "user:turn", "text": text}],
                "trace": [{"part": "round4.social_frame", "status": "ran", "act": act, "factual_claim": False,
                           "frame": reading.case_frame.value.as_dict() if reading.case_frame else None}]}

    @staticmethod
    def _creative_rows(lib: FamilyLibrary, text: str, slot: str) -> list[dict]:
        topics = sorted((t for t in _terms(text) if t not in _CREATIVE_WORDS), key=lambda t: (-len(t), t))
        for topic in topics:
            found = [dict(row) for row in lib.con.execute(
                "SELECT DISTINCT r.* FROM terms t JOIN records r ON r.id=t.rid "
                "WHERE t.token=? AND r.slot=? ORDER BY r.id LIMIT 120", (topic, slot))]
            if len(found) >= 2:
                return found
        return []

    def _compose_haiku(self, lib: FamilyLibrary, text: str) -> dict | None:
        from .core_abilities import morae
        from .typed_edges import _tagger
        rows = self._creative_rows(lib, text, "haiku")
        for i, first in enumerate(rows):
            a = json.loads(first["payload"])
            lines_a = a.get("lines") or []
            if len(lines_a) != 3 or morae(str(lines_a[0])) != 5 or morae(str(lines_a[1])) != 7:
                continue
            if a.get("kigo") and not any(str(a["kigo"]) in str(line) for line in lines_a):
                continue
            for second in rows[i + 1:]:
                b = json.loads(second["payload"])
                lines_b = b.get("lines") or []
                if (a.get("season") != b.get("season") or a.get("theme") != b.get("theme") or
                        len(lines_b) != 3 or morae(str(lines_b[2])) != 5 or
                        lines_a[2] == lines_b[2]):
                    continue
                if not any(tok.feature.pos1 == "名詞" and tok.surface not in {"上", "下", "中", "先", "もの", "こと"}
                           for tok in _tagger()(str(lines_b[2]))):
                    continue
                lines = [str(lines_a[0]), str(lines_a[1]), str(lines_b[2])]
                if [morae(line) for line in lines] != [5, 7, 5]:
                    continue
                if not _topic_covered(text, "／".join(lines)):
                    continue
                asked_season = next((s for s in ("春", "夏", "秋", "冬") if s in text), None)
                if asked_season and a.get("season") != asked_season:
                    continue
                sources = [{"family": lib.family, "source": f"{first['source']}:{first['sha']}",
                            "text": lines[0] + "／" + lines[1]},
                           {"family": lib.family, "source": f"{second['source']}:{second['sha']}",
                            "text": lines[2]}]
                return {"kind": "answer", "verdict": "ANSWER", "text": "創作: " + "／".join(lines),
                        "evidence": [s["text"] for s in sources], "sources": sources,
                        "family": lib.family, "path": "haiku_recombination",
                        "reread": {"morae": [5, 7, 5], "season": a.get("season")}}
        return None

    def _compose_story(self, lib: FamilyLibrary, text: str) -> dict | None:
        from .verdict import read_records
        rows = self._creative_rows(lib, text, "story")
        def events(row: dict) -> tuple[dict, dict[str, str]]:
            payload = json.loads(row["payload"])
            shape = {str(s.get("shape")): str(s.get("text") or "") for s in payload.get("sentences", [])}
            return payload, shape
        def agents(lines: list[str]) -> set[str]:
            return {item.frame.agent for line in lines for item in read_records(line)
                    if item.frame.agent and len(item.frame.agent) >= 2}
        for i, first in enumerate(rows):
            a, shape_a = events(first)
            if not all(shape_a.get(k) for k in ("start", "development")):
                continue
            shared_a = agents([shape_a["start"], shape_a["development"]])
            if not shared_a:
                continue
            for second in rows[i + 1:]:
                b, shape_b = events(second)
                if a.get("setting") != b.get("setting") or a.get("tone") != b.get("tone"):
                    continue
                if not all(shape_b.get(k) for k in ("turn", "ending")):
                    continue
                if not shared_a.intersection(agents([shape_b["turn"], shape_b["ending"]])):
                    continue
                lines = [shape_a["start"], shape_a["development"], shape_b["turn"], shape_b["ending"]]
                if any(not read_records(line) for line in lines):
                    continue
                if not _topic_covered(text, "\n".join(lines)):
                    continue
                sources = [{"family": lib.family, "source": f"{first['source']}:{first['sha']}",
                            "text": "\n".join(lines[:2])},
                           {"family": lib.family, "source": f"{second['source']}:{second['sha']}",
                            "text": "\n".join(lines[2:])}]
                return {"kind": "answer", "verdict": "ANSWER", "text": "創作: " + "\n".join(lines),
                        "evidence": lines, "sources": sources, "family": lib.family,
                        "path": "labelled_story_walk", "reread": {"shapes": ["start", "development", "turn", "ending"]}}
        return None

    @staticmethod
    def _compose_metaphor(lib: FamilyLibrary, text: str) -> dict | None:
        from .verdict import read_records
        quoted = re.search(r"[「『]([^」』]{1,14})[」』]を[「『]([^」』]{1,14})[」』]に(?:たとえ|例え)", text)
        plain = re.search(r"([^、。\s]{1,14})を([^、。\s]{1,14})に(?:たとえ|例え)", text)
        if quoted:
            target, vehicle = quoted.group(1), quoted.group(2)
        elif plain:
            target, vehicle = plain.group(1), plain.group(2)
        else:
            return None
        matches = [dict(row) for row in lib.con.execute(
            "SELECT DISTINCT r.* FROM terms t JOIN records r ON r.id=t.rid "
            "WHERE t.token=? AND r.slot='metaphor' LIMIT 80", (vehicle,))]
        suitable = []
        for row in matches:
            payload = json.loads(row["payload"])
            if payload.get("vehicle") == vehicle and payload.get("property"):
                suitable.append((row, payload))
        properties = {str(p["property"]) for _, p in suitable}
        if len(properties) != 1:
            return None
        row, payload = suitable[0]
        property_text = str(payload["property"]).rstrip("。")
        line = f"{target}は{vehicle}のように{property_text}。"
        parsed = read_records(line)
        if not parsed or not any(item.frame.agent == target for item in parsed):
            return None
        source = f"{row['source']}:{row['sha']}"
        evidence = str(payload.get("expression") or "") + " → " + property_text
        return {"kind": "answer", "verdict": "ANSWER", "text": "創作: " + line,
                "family": lib.family, "source": source, "path": "vehicle_property_transfer",
                "evidence": [evidence, text],
                "sources": [{"family": lib.family, "source": source, "text": evidence},
                            {"family": "user", "source": "user:target", "text": target}],
                "reread": {"agent": target, "predicate": parsed[0].frame.predicate}}

    @staticmethod
    def _compose_pun(lib: FamilyLibrary, text: str) -> dict | None:
        from .core_abilities import kana
        named = re.search(r"[「『]([^」』]{1,12})[」』]で(?:ダジャレ|だじゃれ|駄洒落|言葉遊び)", text)
        if not named:
            return None
        noun = named.group(1)
        reading = kana(noun)
        if not reading:
            return None
        # The mechanism must already be attested at this reading. Applying
        # it changes only the written noun, and rereading checks the sound.
        proposals = []
        for row in lib.con.execute("SELECT source,sha,payload FROM records WHERE slot='pun'"):
            payload = json.loads(row["payload"])
            if kana(str(payload.get("reading") or "")) != reading:
                continue
            original = str(payload.get("pun") or "")
            for key in ("word_a", "word_b"):
                word = str(payload.get(key) or "")
                if word and word != noun and word in original and kana(word) == reading:
                    changed = original.replace(word, noun, 1)
                    if changed != original and noun in changed:
                        proposals.append((changed, row, original, word))
                    break
        unique = {item[0] for item in proposals}
        if len(unique) != 1:
            return None
        changed, row, original, word = proposals[0]
        if kana(word) != kana(noun):
            return None
        source = f"{row['source']}:{row['sha']}"
        return {"kind": "answer", "verdict": "ANSWER", "text": "創作: " + changed,
                "family": lib.family, "source": source, "path": "reading_substitution",
                "evidence": [original],
                "sources": [{"family": lib.family, "source": source, "text": original},
                            {"family": "user", "source": "user:noun", "text": noun}],
                "reread": {"reading": reading, "changed_word": noun}}

    @staticmethod
    def _conversation_supply(text: str, reading: Any = None) -> dict | None:
        from .ability_corpus import Corpus
        if reading is None:
            from .question import read
            reading = read(text)
        framed = GeneralRouter._social_frame(text, reading)
        if framed is None:
            return None
        corpus = Corpus()
        spoken = str(framed["text"]).strip("。！？!? \n")
        if len(spoken) < 2:
            return None
        replies = [row for row in corpus.search(spoken, family="conversation", limit=60)
                   if _norm(row.text) == _norm(spoken)]
        if not replies:
            return None
        return dict(framed, family="conversation", source=replies[0].source,
                    evidence=[framed["text"]], sources=[row.cite() for row in replies], path="speech_act_supply")

    @staticmethod
    def _code_supply(text: str) -> dict | None:
        from .ability_corpus import Corpus
        corpus = Corpus()
        terms = [t for t in _terms(text) if t.casefold() not in {"コード", "関数", "実装", "プログラム", "python", "javascript"}]
        if not terms:
            return None
        rows = corpus.search(max(terms, key=len), family="code", limit=60)
        scored = []
        query_terms = set(_terms(text))
        for row in rows:
            own = set(_terms(row.text))
            shared = len(query_terms & own)
            if shared >= 2:
                scored.append((shared / max(1, len(query_terms)), row))
        scored.sort(key=lambda pair: -pair[0])
        if not scored or scored[0][0] < .75 or len(scored) > 1 and scored[0][0] == scored[1][0]:
            return None
        witness = scored[0][1]
        return {"kind": "answer", "verdict": "ANSWER", "text": witness.text,
                "family": "code", "source": witness.source, "evidence": [witness.text],
                "sources": [witness.cite()], "path": "code_supply"}
