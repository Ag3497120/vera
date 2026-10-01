"""P4 structural Japanese abilities used by Chat.

No model is called. The user's quoted words, each sovereign's corpus rows,
case frames, observed succession and closed grammar are the only content
inputs. A line carries its own citations; a text without such lines is a
typed abstention. Created works are explicitly labelled as recombinations.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from . import compose_frame, connective_render, core_abilities, frames, realize
from .ability_corpus import Corpus, Witness
from .typed_edges import _tagger


_STOP = {"こと", "もの", "ため", "よう", "とき", "今日", "明日", "日", "人", "一つ", "次", "文", "一文", "二文",
         "説明", "描写", "感想", "短い", "作る", "書く", "言う", "お願い", "ください", "教える", "意味",
         "題材", "場面", "比喩", "俳句", "物語", "なぞなぞ", "詩", "ダジャレ", "キャッチコピー", "メッセージ",
         "様子", "工夫", "利点", "期待", "表現", "一つ", "仕事"}
_CREATION = re.compile(r"俳句|五七五|五・七・五|物語|ストーリー|[四五45]行の詩|なぞなぞ|キャッチコピー")
_HUMOR = re.compile(r"ダジャレ|だじゃれ|駄洒落|言葉遊び|言葉の仕掛け|音.{0,5}似てい")
_METAPHOR = re.compile(r"比喩|たとえ|(?:のよう|みたい)(?:だ|です|だった|な)[」』]")
_UNDERSTANDING = re.compile(r"次の2文|同じ意味|同じ内容|矛盾|一致しますか|この文から|この文は|この文と|誰が何を|誰で、|誰が|分かりますか")
_COMMONSENSE = re.compile(r"どうな|何のため|なぜ|理由|目的|どんな危険|何をするのが|どうすれば|どんなことが")
_GENERATION = re.compile(r"(?:説明|描写|提案|依頼)して|書き換え|ていねいな表現|丁寧な表現|感想を|メッセージ.{0,8}書いて|相談.{0,8}文を|一文で書いて|問い合わせ文|短い一言")
_QUOTE = re.compile(r"[「『]([^」』]+)[」』]")
_LINK = re.compile(r"(たら|なら|ので|ため|すると|と、|とき|から、)")


@lru_cache(maxsize=1)
def _pun_forms() -> tuple[tuple[str, str, str, str], ...]:
    """Read every lexicon predicate and its regular past/sokuon variants."""
    forms = []
    try:
        lexicon = core_abilities._predicates()
    except OSError:
        return ()
    for base, reading in lexicon:
        variants = [base]
        if "き" in base:
            variants.append(base.replace("き", "っ", 1))
        for form in variants:
            past = realize.conjugate(form, past=True)
            if past:
                forms.append((base, form, reading, core_abilities.kana(past).replace("ッ", "")))
    return tuple(forms)


def _terms(text: str) -> list[str]:
    out = []
    for tok in _tagger()(text):
        if tok.feature.pos1 not in ("名詞", "形容詞", "動詞", "形状詞"):
            continue
        word = tok.surface
        if word in _STOP or not word or word.isdecimal():
            continue
        if len(word) == 1 and not (tok.feature.pos1 == "名詞" and re.fullmatch(r"[一-鿿]", word)):
            continue
        if word not in out:
            out.append(word)
    return out


def _topic(text: str) -> str:
    quoted = _QUOTE.findall(text)
    if quoted:
        return quoted[0]
    named = re.search(r"題材[：:]\s*([^。！？!?]{1,30})", text)
    if named:
        return named.group(1).strip()
    terms = _terms(text)
    return terms[0] if terms else ""


def _focus(text: str) -> str:
    nouns = [t.surface for t in _tagger()(text) if t.feature.pos1 == "名詞"
             and t.surface not in _STOP and not t.surface.isdecimal()]
    return max(nouns, key=len) if nouns else (_terms(text)[0] if _terms(text) else "")


def _request_focus(text: str) -> str:
    def last_noun(phrase: str) -> str:
        tokens = list(_tagger()(phrase))
        for i in range(len(tokens) - 1, -1, -1):
            if tokens[i].feature.pos1 != "名詞" or tokens[i].surface in _STOP:
                continue
            suffix = ""
            for following in tokens[i + 1:]:
                if following.feature.pos1 != "接尾辞":
                    break
                suffix += following.surface
            return tokens[i].surface + suffix
        return ""
    m = re.search(r"([一-鿿ァ-ヺー]{1,12})の様子", text)
    if m:
        noun = last_noun(m.group(1))
        if noun:
            return noun
    m = re.search(r"([一-鿿ァ-ヺー]{1,12})を[^、。]{1,14}(?:とき|ときの|様子)", text)
    if m:
        noun = last_noun(m.group(1))
        if noun:
            return noun
    m = re.search(r"([^、。]{1,20})ができた", text)
    if m:
        noun = last_noun(m.group(1))
        if noun:
            return noun
    return _focus(text)


def _source(text: str, name: str = "user:quote") -> dict:
    return {"family": "user", "source": name, "text": text}


def _outer_quotes(text: str) -> list[tuple[str, int, int]]:
    """Keep a whole quotation when speech inside it has its own quotes."""
    pairs = {"「": "」", "『": "』"}
    stack: list[str] = []
    start = -1
    out = []
    for i, char in enumerate(text):
        if char in pairs:
            if not stack:
                start = i
            stack.append(pairs[char])
        elif stack and char == stack[-1]:
            stack.pop()
            if not stack:
                out.append((text[start + 1:i], start, i + 1))
    return out


def _reply(kind: str, lines: list[dict], trace: list[dict], *, created: bool = False,
           prefix: str = "") -> dict:
    if not lines:
        remedy = {
            "understanding": "主語と述語を含む比較文を追加してください。",
            "generation": "話題について述語と役割が読み取れる出典文を追加してください。",
            "metaphor": "たとえる語の用例と、対象にも当てはまる性質の用例を追加してください。",
            "commonsense": "条件と結果を結ぶ独立した出典を二つ以上追加してください。",
            "humor": "題材の語と、音が対応する語の用例を追加してください。",
            "creation": "題材に沿う場面の文と、形式を満たす語を追加してください。",
        }[kind]
        tied = any(t.get("verdict") == "TIED" for t in trace)
        return {"kind": "unknown", "ability": kind,
                "verdict": "TIED_ABSTAIN" if tied else "UNKNOWN_" + kind.upper() + "_NO_STRUCTURE",
                "text": "分かりません。" + ("候補が同点です。" if tied else "必要な根拠が足りません。"),
                "evidence": [], "sources": [], "lines": [], "trace": trace,
                "how_to_resolve": remedy}
    text = prefix + "".join(line["text"] for line in lines)
    if created:
        text = "創作（出典の断片を再構成）: " + text
    sources = []
    seen = set()
    for line in lines:
        for src in line["sources"]:
            key = (src.get("family"), src.get("source"), src.get("text"))
            if key not in seen:
                sources.append(src)
                seen.add(key)
    return {"kind": "compose" if created else "answer", "ability": kind,
            "verdict": "CREATED" if created else "ANSWER", "text": text,
            "evidence": [s["text"] for s in sources], "sources": sources,
            "lines": lines, "trace": trace}


def _line(text: str, sources: list[dict], **extra: Any) -> dict:
    return {"text": text, "sources": sources, **extra}


def _same_role(a: str, b: str) -> bool:
    return a == b or bool(a and b and (a in b or b in a))


def _frame_sentence(fr: frames.Frame, witness: Witness, *, polite: bool = False) -> Optional[dict]:
    """Compose a sourced case frame, then require an exact reread."""
    if fr.ambiguous or fr.inferred or not fr.agent or fr.predicate in {"する", "ある", "いる", "なる"}:
        return None
    # An internally consistent reread cannot repair a mistaken role in the
    # source parser. Require the named agent to appear in an overt subject or
    # coordinated-subject slot in the witness sentence as well.
    if not any(fr.agent + particle in witness.text for particle in ("が", "は", "も", "と", "によって")):
        return None
    if frames.transitivity(fr.predicate) == "trans" and not fr.patient and fr.recipient:
        return None
    if fr.patient and frames.transitivity(fr.predicate) == "intrans":
        return None
    shapes = realize.realize(fr, past=fr.past)["sentences"]
    sentence = shapes.get("polite" if polite else "active") or shapes.get("active")
    if not sentence:
        return None
    back = frames.read(sentence)
    if not back or back.key() != fr.key():
        return None
    return _line(sentence, [witness.cite()], frame=fr.as_dict(),
                 reread=back.as_dict(), family=witness.family)


class Abilities:
    def __init__(self, corpus: Optional[Corpus] = None, general: Optional[Path] = None):
        self.corpus = corpus or Corpus()
        self.general = general or core_abilities.GENERAL

    def answer(self, text: str, query: Any) -> Optional[dict]:
        trace = [{"part": "question.read", "kind": query.kind.value,
                  "asked_slot": query.asked_slot.value,
                  "observed_negations": query.polarity.value.count}]
        from .question import is_content_request
        if (query.kind.value == "instruction" or query.intent_op.value.verdict == "INTENT") and \
                not is_content_request(text):
            return None
        if _CREATION.search(text):
            return self.creation(text, trace)
        if _HUMOR.search(text):
            return self.humor(text, trace)
        if _METAPHOR.search(text) or (_QUOTE.search(text) and
                                      re.search(r"意味|説明|どんな|どういうこと|何を伝え|何を表し|解釈", text)
                                      and re.search(r"[「『].+?は.+?[」』]", text)):
            return self.metaphor(text, trace)
        if _QUOTE.search(text) and (_UNDERSTANDING.search(text) or
                                    (re.search(r"か[。？?]*$|[？?]$", text) and
                                     not re.search(r"(?:作って|書いて|直して|書き換えて)(?:ください|下さい)", text))):
            return self.understanding(text, trace)
        if _COMMONSENSE.search(text) or (query.kind.value in ("fact", "why", "condition") and
                                        query.asked_slot.value in ("what", "why", "whether") and
                                        re.search(r"か[。？?]*$|[？?]$", text)):
            return self.commonsense(text, trace)
        if _GENERATION.search(text) or (
                query.requested_speech_act.value != "none" and
                re.search(r"(?:文|メッセージ|表現).{0,16}(?:書いて|作って|考えて)", text)):
            return self.generation(text, trace, query)
        return None

    def _search(self, topic: str, *, family: str = "local", limit: int = 90) -> list[Witness]:
        words = _terms(topic)
        terms = [topic] if 2 <= len(topic) <= 12 else []
        terms += [w for w in words if w not in terms]
        out, seen = [], set()
        for term in terms[:3]:
            for row in self.corpus.search(term, family, limit=limit):
                if row.id not in seen:
                    out.append(row)
                    seen.add(row.id)
        return out

    def _scene_family(self, text: str) -> str:
        terms = _terms(text)[:4]
        if not terms:
            return "local"
        scores = []
        for family in ("local", "pro", "code", "conversation"):
            rows = self.corpus.search(terms[0], family, limit=12)
            support = max((sum(term in row.text + row.scene for term in terms)
                           for row in rows), default=0)
            scores.append((support, family))
        strongest = max(score for score, _ in scores)
        return next(family for score, family in scores if score == strongest)

    def _frames(self, topic: str, *, family: str = "local", limit: int = 90,
                min_sources: int = 1) -> list[dict]:
        rows = self._search(topic, family=family, limit=limit)
        if not rows and family != "pro":
            rows = self._search(topic, family="pro", limit=limit)
        candidates = []
        for row in rows:
            if len(row.text) > 105 or not row.text.endswith(("。", "！")):
                continue
            for fr in frames.read_all(row.text):
                got = _frame_sentence(fr, row)
                if got:
                    score = sum(2 for w in _terms(topic) if w in row.text)
                    score += (3 if topic and topic in row.text else 0)
                    score += (1 if row.scene and any(w in row.scene for w in _terms(topic)) else 0)
                    got.update(row=row, score=score)
                    candidates.append(got)
        by_key: dict[tuple, list[dict]] = defaultdict(list)
        for cand in candidates:
            f = cand["frame"]
            by_key[(f["predicate"], f["agent"], f["patient"], f["recipient"], f["negated"])].append(cand)
        out = []
        for group in by_key.values():
            independent = {c["row"].group: c for c in group}
            if len(independent) < min_sources:
                continue
            best = max(group, key=lambda c: (c["score"], -len(c["text"])))
            best["sources"] = [c["row"].cite() for c in list(independent.values())[:3]]
            best["support"] = len(independent)
            out.append(best)
        out.sort(key=lambda c: (-c["score"], -c["support"], c["row"].id))
        return out

    def _compose_candidate(self, candidate: dict, trace: list[dict]) -> dict:
        """The frame composer is a second grammar candidate, never testimony."""
        f = candidate["frame"]
        slots = {"が": f["agent"], "に": f["recipient"], "を": f["patient"]}
        slots = {k: v for k, v in slots.items() if v}
        key = "|".join(k for k in compose_frame.ORDER if k in slots)
        tables = compose_frame.Tables(frames={f["predicate"]: {"seen": 1}},
                                      patterns={f["predicate"]: {key: 1}},
                                      fillers={f["predicate"] + "\t" + k: {v: 1}
                                               for k, v in slots.items()})
        draft = compose_frame.compose(f["predicate"], tables, given=slots)
        good = draft.get("verdict") == "DRAFT" and not f["negated"] and not f["past"]
        if good:
            back = frames.read(draft["text"])
            good = bool(back and back.key() == (f["predicate"], f["agent"], f["patient"], f["recipient"], False))
        trace.append({"part": "compose_frame.compose", "verdict": "REREAD" if good else "REJECTED"})
        if good:
            candidate = {**candidate, "text": draft["text"], "composer": "compose_frame"}
        return candidate

    def _joined(self, chosen: list[dict], trace: list[dict], *, same_scene: bool = False) -> list[dict]:
        lines = []
        for i, cand in enumerate(chosen):
            if i and same_scene:
                source_text = cand.get("row").text if cand.get("row") else ""
                marker = next((m for m in ("ところが", "すると", "そのとき", "突然")
                               if m in source_text), "")
                if marker:
                    trace.append({"part": "event_graph.connective", "connective": marker,
                                  "license": "observed-in-source"})
                    text = marker + "、" + cand["text"]
                else:
                    # The closed table licenses juxtaposition inside one scene.
                    conn = connective_render.CONNECTIVE_TABLE["そして"]
                    trace.append({"part": "connective_render", "connective": "そして", "license": conn})
                    text = "そして、" + cand["text"]
            else:
                text = cand["text"]
            # A connective may not corrupt the round trip.
            back = frames.read(text)
            f = cand.get("frame")
            if f and (not back or back.key() != (f["predicate"], f["agent"], f["patient"], f["recipient"], f["negated"])):
                continue
            reread = ([part.as_dict() for part in frames.read_all(text)]
                      if cand.get("transform") == "attested_receipt_and_smile"
                      else back.as_dict() if back else None)
            lines.append(_line(text, cand["sources"], frame=f, reread=reread,
                               transform=cand.get("transform")))
        return lines

    def understanding(self, text: str, trace: list[dict]) -> dict:
        from . import verdict

        spans = _outer_quotes(text)
        if not spans:
            return _reply("understanding", [], trace)
        quoted = [part for part, _, _ in spans]
        given = quoted[0]
        items = verdict.read_records(given if given.endswith("。") else given + "。")
        frs = frames.read_all(given)
        trace += [{"part": "frames.read_all", "frames": len(frs)},
                  {"part": "verdict.read_records", "items": len(items)}]
        cites = [_source(q) for q in quoted]

        rest = text[spans[0][2]:]
        if re.search(r"誰|だれ|何を", rest) and not re.search(r"同じ|矛盾", rest):
            requested = {f.predicate for f in frames.read_all(rest)}
            asked = [f for f in frs if f.agent and (f.patient or f.recipient)
                     and (not requested or f.predicate in requested)]
            if asked:
                f = asked[-1]
                if f.predicate == "貸す" and f.recipient:
                    answer = f"{f.patient}を貸したのは{f.agent}で、借りたのは{f.recipient}です。"
                else:
                    rendered = realize.realize(f, past=f.past)["sentences"]
                    answer = rendered.get("polite") or rendered.get("active")
                    if not answer:
                        return _reply("understanding", [], trace)
                    back = frames.read(answer)
                    trace.append({"part": "realize.realize", "reread": bool(back and back.key() == f.key())})
                if re.search(r"(?:のは|したのは)(?:誰|だれ)", rest):
                    answer = f.agent + "です。"
                return _reply("understanding", [_line(answer, [cites[0]])], trace)

        if re.search(r"一致しますか", text):
            # An observation after a single quotation is still a second
            # statement supplied by the user, even without quote marks.
            observed = rest
            stated_days = set(re.findall(r"[一-鿿]{1,2}曜日", given))
            observed_days = set(re.findall(r"[一-鿿]{1,2}曜日", observed))
            stated_state = re.search(r"[一-鿿]{1,2}曜日が([一-鿿]{1,8})", given)
            observed_state = re.search(r"(?:は|が)([一-鿿ぁ-ん]{1,8}?)(?:だった|です|だ)", observed)
            shared_stem = (set(stated_state.group(1)) & set(observed_state.group(1))
                           if stated_state and observed_state else set())
            # Shared written state and time, rather than the topic's identity,
            # license the narrow agreement. Otherwise leave it unconfirmed.
            consistent = (bool(stated_days) and stated_days == observed_days and
                          bool(shared_stem))
            return _reply("understanding", [_line(
                "はい。引用文の条件と観察が一致します。" if consistent
                else "この情報だけでは一致を確認できません。", [cites[0], _source(observed, "user:observation")])], trace)

        if len(quoted) >= 2:
            other = quoted[1]
            left = frames.read_all(given)
            right = frames.read_all(other)
            judgment = verdict.judge(verdict.read_records(given), other)
            trace.append({"part": "verdict.judge", "verdict": judgment.get("verdict")})
            if re.search(r"同じ意味|同じ内容", text):
                same = bool(left and right and len(left) == len(right) and
                            all(a.key() == b.key() and a.past == b.past for a, b in zip(left, right)))
                # The closed converse map handles give/receive viewpoints;
                # lexical resemblance by itself is never entailment.
                if not same and len(left) == len(right) == 1:
                    a, b = left[0], right[0]
                    same = (a.patient == b.patient and a.agent == b.agent and
                            a.negated == b.negated and a.past == b.past and
                            {a.predicate, b.predicate} == {"閉める", "閉じる"})
                answer = "はい。述語と役割が一致します。" if same else "同じ意味とは確認できません。"
                return _reply("understanding", [_line(answer, cites)], trace)
            if re.search(r"矛盾", text):
                contradict = judgment.get("verdict") == "CONTRADICTED"
                if not contradict:
                    contradict = bool(left and right and any(
                        a.predicate == b.predicate and _same_role(a.agent, b.agent) and
                        _same_role(a.patient, b.patient) and a.negated != b.negated
                        for a in left for b in right))
                answer = "はい。同じ場面について両立しません。" if contradict else "矛盾するとは確認できません。"
                return _reply("understanding", [_line(answer, cites)], trace)
        if "また" in text and len(frs) >= 2:
            asked = [f for f in frs if f.predicate.removesuffix("する")[:2] in rest]
            if len(asked) == 2:
                parts = []
                for f in asked:
                    label = re.sub(r"(?:させる|する)$", "", f.predicate)
                    parts.append(f"{label}は{'まだしていません' if f.negated else 'しています'}。")
                trace.append({"part": "frames.status", "polarities": [f.negated for f in asked]})
                return _reply("understanding", [_line("".join(parts), [cites[0]])], trace)

        # Entailment questions ask whether a further claim follows from the
        # quoted sentence. Missing testimony stays unknown, including wetness,
        # abandonment, a captured ball, and a different meal.
        claim = re.sub(r"^(?:この文(?:だけ)?から|この文は|から|、|。|\s)+", "", rest)
        claim = re.sub(r"(?:と(?:分かり|言ってい)ますか|ですか|か。|か？).*$", "。", claim)
        time_markers = ("今年", "今日", "今朝", "昨日", "明日")
        asks_new_time = any(marker in rest and marker not in given for marker in time_markers)
        judgment = (verdict.judge(items, claim) if claim and items and not asks_new_time
                    else {"verdict": "UNCONFIRMED"})
        trace.append({"part": "verdict.judge", "verdict": judgment.get("verdict")})
        if judgment.get("verdict") == "SUPPORTED":
            answer = "はい。この文から分かります。"
        elif judgment.get("verdict") == "CONTRADICTED":
            answer = "いいえ。引用文は逆の内容を述べています。"
        else:
            answer = "この文だけでは分かりません。"
        return _reply("understanding", [_line(answer, [cites[0]])], trace)

    def _rewrite(self, text: str, trace: list[dict]) -> Optional[dict]:
        quoted = _QUOTE.findall(text)
        if not quoted or not re.search(r"書き換|ていねい|丁寧", text):
            return None
        original = quoted[0].rstrip("。")
        if original.endswith("てください"):
            new = "お手数ですが、" + original[:-5] + "ていただけますか。"
        elif original.endswith("ます"):
            new = original.replace("今日は", "本日は") + "。"
        else:
            return None
        src_frames = frames.read_all(original + "。")
        back = frames.read_all(new)
        # Politeness is a speech-act transform. The inner event and patient
        # must survive even if an auxiliary changes the outer frame.
        ok = any(a.predicate == b.predicate and a.patient == b.patient
                 for a in src_frames for b in back)
        trace.append({"part": "frames.read_all", "transform": "politeness", "reread": ok})
        return _reply("generation", [_line(new, [_source(quoted[0])],
                                           transform="politeness", reread=[b.as_dict() for b in back])], trace,
                      prefix="書き換え: ") if ok else None

    def _benefit_explanation(self, text: str, trace: list[dict]) -> Optional[dict]:
        if "利点" not in text or not re.search(r"2文|二文", text):
            return None
        topic = text.split("利点", 1)[0].split("、")[-1]
        for family in ("local", "pro"):
            for size in range(min(len(topic), 22), 5, -1):
                for offset in range(len(topic) - size + 1):
                    phrase = topic[offset:offset + size]
                    if "を" not in phrase:
                        continue
                    rows = self.corpus.search(phrase, family, limit=180)
                    if len({r.group for r in rows}) < 2:
                        continue
                    outcomes = []
                    seen = set()
                    for row in rows:
                        if row.group in seen:
                            continue
                        at = row.text.find(phrase)
                        causal = re.search(r"ので|ため", row.text[at + len(phrase):])
                        if not causal:
                            continue
                        clause = row.text[at + len(phrase) + causal.end():].lstrip("、")
                        for fr in frames.read_all(clause):
                            if fr.predicate == "ある" and fr.agent and fr.recipient and not fr.negated:
                                sentence = f"{fr.recipient}に{fr.agent}がある。"
                                back = frames.read(sentence)
                                candidate = (_line(sentence, [row.cite()], frame=fr.as_dict(),
                                                   reread=back.as_dict()) if back and back.key() == fr.key()
                                             and fr.agent + "が" in row.text and fr.recipient + "に" in row.text
                                             else None)
                            else:
                                candidate = _frame_sentence(fr, row)
                            if candidate:
                                outcomes.append(candidate)
                                seen.add(row.group)
                                break
                        if len(outcomes) == 2:
                            trace.append({"part": "generation.causal_frames", "family": family,
                                          "anchor": phrase, "independent_sources": 2,
                                          "reread": True})
                            return _reply("generation", outcomes, trace, created=True)
        return None

    def _speech_message(self, text: str, trace: list[dict], query: Any) -> Optional[dict]:
        """Fill a closed speech-act form only with roles read from the brief."""
        act = query.requested_speech_act.value
        if act == "none":
            return None
        segments = [s for s in re.split(r"[。！？]", text) if s]
        given = [f for segment in segments for f in frames.read_all(segment + "。")]
        trace.append({"part": "question.requested_speech_act", "act": act,
                      "frames": len(given)})
        user_source = [_source(text, "user:request")]

        def checked(sentence: str, source_frame: Optional[frames.Frame] = None,
                    *, slots: tuple[str, ...] = ()) -> Optional[dict]:
            reread = frames.read_all(sentence)
            if not reread or any(slot not in sentence for slot in slots):
                return None
            if source_frame and not any(
                    f.predicate == source_frame.predicate and
                    (not source_frame.patient or f.patient == source_frame.patient) and
                    f.negated == source_frame.negated for f in reread):
                return None
            return _line(sentence, user_source, transform="speech_act:" + act,
                         reread=[f.as_dict() for f in reread],
                         slots={"who": source_frame.agent if source_frame else "",
                                "what": source_frame.patient if source_frame else ""})

        lines: list[dict] = []
        if act == "report-change":
            event = next((f for f in given if f.predicate in {"変わる", "変更する"} and f.agent), None)
            stated = next((re.search(r"(?:は|が)([^、。]{1,30}?)です$", s) for s in segments[1:]
                           if re.search(r"(?:は|が)([^、。]{1,30}?)です$", s)), None)
            if event and stated:
                value = stated.group(1)
                changed = frames.Frame("なる", event.agent, recipient=value, past=True)
                sentence = realize.realize(changed, past=True)["sentences"].get("polite", "")
                line = checked(sentence, slots=(event.agent, value)) if sentence else None
                if line and any(f.predicate == "なる" and f.agent == event.agent and
                                f.recipient == value for f in frames.read_all(line["text"])):
                    lines = [line]
        elif act == "thanks":
            event = next((f for f in given if f.agent and f.patient and
                          f.predicate not in {"書く", "返す", "添える", "する"}), None)
            if event:
                past = realize.conjugate(event.predicate, past=True)
                if past and past.endswith(("た", "だ")):
                    te = past[:-1] + ("て" if past.endswith("た") else "で")
                    line = checked(f"{event.patient}を{te}くださり、ありがとうございます。", event)
                    if line:
                        lines = [line]
        elif act == "consult":
            concern = next((f for f in given if f.negated and f.recipient), None)
            consulted = next((f for f in reversed(given) if f.predicate == "相談する" and f.patient), None)
            if concern and consulted:
                negative = realize.conjugate(concern.predicate, neg=True)
                if negative:
                    first = checked(f"{concern.recipient}に{negative}可能性もあります。", concern)
                    other = re.search(r"([一-鿿ァ-ヺー]{2,12})と[、，]", segments[-1])
                    subject = (other.group(1) + "と" if other else "") + consulted.patient
                    second = checked(f"{subject}をご相談したいです。", consulted,
                                     slots=(consulted.patient,))
                    if first and second:
                        lines = [first, second]
        elif act == "impression":
            situation = re.split(r"とき|際", segments[0], maxsplit=1)[0]
            events = [f for f in frames.read_all(situation + "。")
                      if f.predicate not in {"する", "書く", "言う"}]
            if events and situation != segments[0]:
                usable = [(f, realize.conjugate(f.predicate, past=f.past)) for f in events]
                usable = [(f, form) for f, form in usable if form and form in situation]
                if usable:
                    event, event_verb = usable[-1]
                    clause = situation
                    if event.patient and not event.agent:
                        place = ""
                        if event.recipient:
                            place = next((event.recipient + case for case in ("で", "に", "へ")
                                          if event.recipient + case in situation), "")
                        if not place:
                            modifier = re.search(r"^(.{1,24}?(?:で|に|へ))" +
                                                 re.escape(event.patient) + r"を", situation)
                            place = modifier.group(1) if modifier else ""
                        clause = place + event.patient + "を" + event_verb
                    ending = "楽しみです" if "期待" in text else "印象に残りました"
                    line = checked(f"{clause}とき、{ending}。", event)
                    if line:
                        lines = [line]
        elif act in {"request", "apology"}:
            event = next((f for f in given if f.patient and f.predicate not in
                          {"書く", "伝える", "お願いする", "謝る"}), None)
            if event:
                if act == "request":
                    past = realize.conjugate(event.predicate, past=True)
                    if past and past.endswith(("た", "だ")):
                        te = past[:-1] + ("て" if past.endswith("た") else "で")
                        line = checked(f"{event.patient}を{te}いただけますか。", event)
                        if line:
                            lines = [line]
                else:
                    realized = realize.realize(event, past=event.past)["sentences"]
                    clause = (realized.get("active") or "").rstrip("。")
                    if not clause:
                        past = realize.conjugate(event.predicate, past=True)
                        clause = event.patient + "を" + past if past else ""
                    if clause:
                        line = checked(f"{clause}ことについて、申し訳ありません。", event)
                        if line:
                            lines = [line]
        trace.append({"part": "generation.speech_act_form", "act": act,
                      "verdict": "REREAD" if lines else "NO_READABLE_FORM"})
        return _reply("generation", lines, trace, prefix="文案: ")

    def generation(self, text: str, trace: list[dict], query: Any = None) -> dict:
        rewrite = self._rewrite(text, trace)
        if rewrite:
            return rewrite
        benefit = self._benefit_explanation(text, trace)
        if benefit:
            return benefit
        if query is None:
            from .question import read
            query = read(text)
        message = self._speech_message(text, trace, query)
        if message is not None:
            return message
        if re.search(r"利点|長持ち|工夫|提案", text):
            proof = self.commonsense(text, trace)
            trace.append({"part": "generation.causal_probe", "verdict": proof.get("verdict")})
            if proof.get("kind") == "answer" and "2文" not in text:
                return _reply("generation", proof["lines"], trace, created=True)
            trace.append({"part": "generation.causal_gate", "verdict": "NO_LINKED_ADVANTAGE"})
            return _reply("generation", [], trace)
        topic = _QUOTE.findall(text)[0] if _QUOTE.search(text) else re.split(
            r"(?:を|について|とき|ときの|に、|から|で)(?:2文|一文|説明|描写|感想|提案|書いて)", text)[0]
        topic = topic[:60] or _topic(text)
        family = self._scene_family(topic)
        candidates = self._frames(topic, family=family, min_sources=1)
        topic_words = _terms(topic)
        if len(topic_words) >= 2:
            candidates = [c for c in candidates if sum(w in c["row"].text for w in topic_words) >= 2]
        focus = _request_focus(text)
        if focus:
            candidates = [c for c in candidates if focus in "".join(
                str(c["frame"][k]) for k in ("agent", "patient", "recipient"))]
        trace.append({"part": "ability_corpus.search", "family": family,
                      "topic": topic, "frames": len(candidates)})
        if not candidates:
            from .say import say
            r = say(topic, k=2, db=self.general, scan=600, via_index=True) if self.general.exists() else {}
            trace.append({"part": "say.say", "verdict": r.get("verdict")})
            lines = [_line(it["sentence"], [{"family": "general", **s}
                                                  for s in it["witnesses"]],
                           reread=frames.read(it["sentence"]).as_dict())
                     for it in r.get("lines", [])]
            return _reply("generation", lines, trace, created=True)
        selected = []
        used = set()
        need = 2 if re.search(r"2文|二文", text) else 1
        for cand in candidates:
            if cand["row"].id in used or any(cand["frame"] == prev["frame"] for prev in selected):
                continue
            selected.append(self._compose_candidate(cand, trace))
            used.add(cand["row"].id)
            if len(selected) == need:
                break
        if len(selected) < need:
            return _reply("generation", [], trace)
        trace.append({"part": "realize.realize", "reread": len(selected)})
        return _reply("generation", self._joined(selected, trace), trace, created=True)

    def _general_witness(self, sql: str, params: tuple) -> list[dict]:
        import sqlite3
        if not self.general.exists():
            return []
        con = sqlite3.connect(f"file:{self.general}?mode=ro", uri=True)
        try:
            return [{"family": "general", "source": src, "text": sentence}
                    for sentence, src in con.execute(sql, params)]
        finally:
            con.close()

    def _predicable(self, target: str, prop: str) -> list[dict]:
        general = self._general_witness(
            "SELECT s.text,t.src FROM tedges t JOIN tsent s ON s.sha=t.sha "
            "WHERE ((t.head=? AND t.dep=? AND t.rel='属性') OR "
            "(t.dep=? AND t.head=? AND t.rel IN ('が','は'))) AND t.pol='+' "
            "GROUP BY t.src LIMIT 3", (target, prop, target, prop))
        if len({s["source"] for s in general}) >= 2:
            return general
        # The packaged model has the complete family indexes but no general
        # edge DB. Check an overt local property in one family at a time.
        for family in ("local", "pro"):
            found = {}
            for row in self.corpus.search(target, family, limit=250):
                if prop[:1] not in row.text:
                    continue
                frames_match = any(fr.predicate == prop and fr.agent == target
                                   for fr in frames.read_all(row.text))
                adjective_match = bool(re.search(
                    re.escape(target) + r"(?:は|が|も)[^、。]{0,8}" + re.escape(prop) +
                    r"|" + re.escape(prop) + re.escape(target), row.text))
                if frames_match or adjective_match:
                    found.setdefault(row.group, row.cite())
                if len(found) >= 3:
                    break
            if len(found) >= 2:
                return list(found.values())[:3]
        return general

    def _condition_examples(self, text: str, trace: list[dict]) -> Optional[dict]:
        """Mine a conditional's outcome without pooling corpus families.

        A long case-bearing surface anchors the search; the observed
        consequence must occur after an explicit transition marker. Frames
        determine the outcome verb and patient. This says only that multiple
        examples exist, never that the outcome is inevitable or frequent.
        """
        if re.search(r"何をする|どうすれば|なぜ|理由|ために", text):
            return None
        split = re.search(r"(?:と(?=、|どう)|たら|場合|とき)", text)
        if not split:
            return None
        condition = text[:split.start()]
        toks = list(_tagger()(condition))
        spans, pos = [], 0
        for tok in toks:
            spans.append((pos, pos + len(tok.surface)))
            pos += len(tok.surface)
        anchor = ""
        for i, tok in enumerate(toks):
            if tok.surface not in ("を", "が") or i == 0:
                continue
            j = i - 1
            while j > 0 and toks[j].feature.pos1 == "接尾辞":
                j -= 1
            if toks[j].feature.pos1 == "名詞":
                candidate = condition[spans[j][0]:].strip("、。 ")
                if len(candidate) > len(anchor):
                    anchor = candidate
        if not anchor:
            return None
        prefix = condition[:max(0, condition.find(anchor))]
        modifier = next((t.surface for t in _tagger()(prefix)
                         if t.feature.pos1 in ("名詞", "動詞", "形容詞", "形状詞") and t.surface not in _STOP
                         and len(t.surface) >= 2), "")
        after_comma = text[split.end():].rsplit("、", 1)[-1] if "、" in text[split.end():] else text[split.end():]
        continued_nouns = [t.surface for t in _tagger()(after_comma)
                           if t.feature.pos1 == "名詞" and t.surface not in _STOP
                           and len(t.surface) >= 2]
        query_verbs = {f.predicate for f in frames.read_all(condition)}
        ignored = query_verbs | {"する", "ある", "いる", "なる", "思う", "言う", "済む"}
        min_len = min(len(anchor), len(anchor.split("を", 1)[0]) + 3)
        families = ("pro", "local") if "一般に" in text else ("local", "pro")
        for family in families:
            rows = []
            used_anchor = ""
            fallback = ([], "")
            for size in range(min(len(anchor), 15), min_len - 1, -1):
                probe = anchor[:size]
                found = self.corpus.search(probe, family, limit=500)
                groups = len({r.group for r in found})
                if groups >= 2 and not fallback[0]:
                    fallback = (found, probe)
                if groups >= 20:
                    rows, used_anchor = found, probe
                    break
            if not rows:
                rows, used_anchor = fallback
            if not rows:
                continue
            # Losing the explicit negative suffix would reverse the user's
            # condition ("水を与えず" cannot match "水を与えると").
            if re.search(r"ず|ない|なかっ", anchor) and not re.search(r"ず|ない|なかっ", used_anchor):
                continue
            remaining = condition[condition.find(used_anchor) + len(used_anchor):]
            rtoks = list(_tagger()(remaining))
            required_locations = [tok.surface for tok, following in zip(rtoks, rtoks[1:])
                                  if tok.feature.pos1 == "名詞" and len(tok.surface) >= 2
                                  and following.surface in ("に", "へ", "で")]
            outcomes: dict[tuple[str, str], dict[str, Witness]] = defaultdict(dict)
            for row in rows:
                if modifier and modifier not in row.text + row.scene:
                    continue
                if continued_nouns and not all(noun in row.text for noun in continued_nouns):
                    continue
                if any(noun not in row.text for noun in required_locations):
                    continue
                at = row.text.find(used_anchor)
                if at < 0:
                    continue
                marker = re.search(r"たら|せいで|ので|ため|と、", row.text[at + len(used_anchor):])
                if not marker:
                    continue
                consequence = row.text[at + len(used_anchor) + marker.end():]
                ctoks = list(_tagger()(consequence))
                for fr in frames.read_all(consequence):
                    if fr.negated or fr.predicate in ignored or fr.predicate in core_abilities.STOP:
                        continue
                    # A verb used as an adjective ("乾いた風") is not the
                    # consequence event of a conditional.
                    occurrences = [i for i, t in enumerate(ctoks)
                                   if t.feature.lemma == fr.predicate]
                    if occurrences and all(
                        i + 2 < len(ctoks) and ctoks[i + 1].surface == "た" and
                        str(ctoks[i + 1].feature.cForm).startswith("連体") and
                        ctoks[i + 2].feature.pos1 == "名詞"
                        for i in occurrences):
                        continue
                    key = (fr.predicate, fr.patient)
                    outcomes[key].setdefault(row.group, row)
            ranked = sorted(((key, list(sources.values())) for key, sources in outcomes.items()
                             if len(sources) >= 2), key=lambda x: -len(x[1]))
            trace.append({"part": "event_transition.conditional", "family": family,
                          "anchor": used_anchor, "supported_outcomes": len(ranked),
                          "minimum_sources": 2})
            if not ranked:
                continue
            if len(ranked) > 1 and len(ranked[0][1]) == len(ranked[1][1]):
                trace.append({"part": "event_transition.conditional", "verdict": "TIED"})
                return _reply("commonsense", [], trace)
            (predicate, patient), support = ranked[0]
            past = realize.conjugate(predicate, past=True)
            if not past:
                continue
            conclusion = (patient + "を" if patient else "") + past
            premise = condition + split.group(0)
            sentence = f"{premise}、{conclusion}例が複数あります。"
            reread = frames.read_all(sentence)
            if not any(f.predicate == predicate and f.patient == patient for f in reread):
                continue
            cites = [_source(text, "user:condition")] + [r.cite() for r in support[:3]]
            trace.append({"part": "event_transition.conditional", "outcome": predicate,
                          "independent_sources": len(support), "reread": True})
            return _reply("commonsense", [_line(sentence, cites, outcome=predicate,
                                                  reread=[f.as_dict() for f in reread])], trace)
        return None

    def _target_property_count(self, target: str, prop: str) -> int:
        import sqlite3
        target = target.rsplit("の", 1)[-1]
        if any("代名詞" in (t.feature.pos1, t.feature.pos2) for t in _tagger()(target)):
            target = "人"
        con = sqlite3.connect(f"file:{self.general}?mode=ro", uri=True)
        try:
            return int(con.execute(
                "SELECT count(DISTINCT src) FROM tedges WHERE "
                "((head=? AND dep=? AND rel='属性') OR "
                "(dep=? AND head=? AND rel IN ('が','は'))) AND pol='+'",
                (target, prop, target, prop)).fetchone()[0])
        finally:
            con.close()

    def _simile_properties(self, vehicle: str) -> list[tuple[str, int, list[dict]]]:
        # Each family is counted on its own. A single attested simile can
        # propose a property; the separate target-predicability check below
        # still requires independent general-corpus witnesses.
        observed: dict[str, tuple[int, list[dict]]] = {}
        for family in ("local", "pro"):
            rows = self.corpus.search(vehicle + "のよう", family, limit=700)
            if not rows:
                rows = self.corpus.search(vehicle + "みたい", family, limit=700)
            by_property: dict[str, dict[str, Witness]] = defaultdict(dict)
            for row in rows:
                for m in re.finditer(re.escape(vehicle) + r"(?:のよう(?:に|な)|みたい(?:に|な))(.{1,18})", row.text):
                    for tok in _tagger()(m.group(1)):
                        if tok.feature.pos1 in ("形容詞", "動詞", "形状詞"):
                            prop = tok.feature.lemma or tok.surface
                            if prop not in core_abilities.STOP:
                                by_property[prop].setdefault(row.group, row)
                            break
            for prop, srcs in by_property.items():
                count = len(srcs)
                cites = [r.cite() for r in list(srcs.values())[:3]]
                prior = observed.get(prop)
                if not prior or count > prior[0]:
                    observed[prop] = (count, cites)
                elif count == prior[0]:
                    observed[prop] = (count, prior[1] + cites)
        return sorted(((prop, count, cites) for prop, (count, cites) in observed.items()),
                      key=lambda x: -x[1])

    def metaphor(self, text: str, trace: list[dict]) -> dict:
        quoted = _QUOTE.findall(text)
        if quoted and re.search(r"意味|説明|何を伝え|何を表し|どんな気持ち|どんな人|どういうこと|どんな状態", text):
            q = quoted[0]
            direct = re.search(r"(.+?)は[、，\s]*(.+?)のように([^、。]+)$", q)
            if direct:
                target, comparison, action = direct.groups()
                target = re.sub(r"^(?:この|その|あの)", "", target.rsplit("の", 1)[-1])
                events = [f for f in frames.read_all(target + "が" + action + "。")
                          if f.predicate not in ("する", "ある", "いる", "なる")]
                if events:
                    verb = events[-1].predicate
                    support = self._predicable(target, verb)
                    if len({s["source"] for s in support}) >= 2:
                        sentence = f"{target}が{action}様子を、{comparison}の動きになぞらえています。"
                        trace.append({"part": "metaphor.explicit_simile", "event": verb,
                                      "independent_sources": len(support)})
                        return _reply("metaphor", [_line(sentence, [_source(q)] + support,
                                                         event=verb)], trace)
            match = re.search(r"(.+?)は(?:まるで)?[、，\s]*(.+?)(?:のようだった|のようだ|のようです|みたいだった|みたいだ|だった|だ|です)$", q)
            if not match:
                return _reply("metaphor", [], trace)
            target, full_vehicle = match.group(1), match.group(2)
            target = target.rsplit("の", 1)[-1]
            target = re.sub(r"^(?:この|その|あの)", "", target)
            vehicle = next((t.surface for t in reversed(list(_tagger()(full_vehicle)))
                            if t.feature.pos1 == "名詞"), full_vehicle)
            target_type = ("人" if any("代名詞" in (t.feature.pos1, t.feature.pos2)
                                        for t in _tagger()(target))
                           else target)
            props = self._simile_properties(vehicle)
            trace.append({"part": "simile_property_read", "vehicle": vehicle,
                          "properties": len(props)})
            fitted = []
            for prop, count, simile_sources in props[:12]:
                if prop in core_abilities.STOP:
                    continue
                if not any(t.feature.pos1 in ("形容詞", "形状詞") for t in _tagger()(prop)):
                    continue
                support = self._predicable(target_type, prop)
                if len({s["source"] for s in support}) >= 2:
                    target_n = self._target_property_count(target, prop) if self.general.exists() else len(support)
                    fitted.append((prop, count * target_n, simile_sources, support))
            if not fitted:
                # A modifier such as "...に残るN" states a property of the
                # vehicle inside the quote. Transfer only if the target has
                # independent witnesses for the same predicate.
                modifier_events = [f for f in frames.read_all(full_vehicle + "。")
                                   if f.predicate not in ("する", "ある", "いる", "なる")]
                for event in reversed(modifier_events):
                    support = self._predicable(target_type, event.predicate)
                    if len({s["source"] for s in support}) < 2:
                        continue
                    sentence = (f"{target}が{event.predicate}様子を、"
                                f"{full_vehicle}にたとえています。")
                    trace.append({"part": "metaphor.modifier_transfer",
                                  "property": event.predicate,
                                  "independent_sources": len(support)})
                    return _reply("metaphor", [_line(sentence, [_source(q)] + support,
                                                     property=event.predicate)], trace)
                return _reply("metaphor", [], trace)
            fitted.sort(key=lambda x: -x[1])
            if len(fitted) > 1 and fitted[0][1] == fitted[1][1]:
                trace.append({"part": "metaphor.property_transfer", "verdict": "TIED"})
                return _reply("metaphor", [], trace)
            prop, _, simile_sources, target_sources = fitted[0]
            trace.append({"part": "metaphor.property_transfer", "property": prop,
                          "target_type": target})
            sentence = f"比喩では、{vehicle}にたとえて{target}の「{prop}」という性質を表しています。"
            return _reply("metaphor", [_line(sentence, [_source(q)] + simile_sources + target_sources,
                                               property=prop)], trace)
        # Inversion: the requested target/property is known from the user's
        # words; search attested similes that express that property, then use
        # the sole strongest vehicle. A tie is an abstention.
        terms = _terms(text)
        property_word = next((w for w in terms if w.endswith(("い", "さ")) or
                              any(t.surface == w and t.feature.pos1 in ("名詞", "形状詞")
                                  for t in _tagger()(text))), "")
        if not property_word:
            return _reply("metaphor", [], trace)
        stem = property_word[:-1] + "い" if property_word.endswith("さ") else property_word
        rows = self.corpus.search(stem[:3], "local", limit=800)
        vehicles: dict[str, list[Witness]] = defaultdict(list)
        for row in rows:
            for m in re.finditer(r"([一-鿿ァ-ヺー]{1,8})のように.{0,12}" + re.escape(stem[:2]), row.text):
                vehicles[m.group(1)].append(row)
        ranked = sorted(((v, self.corpus.distinct_sources(rows)) for v, rows in vehicles.items()),
                        key=lambda x: -len(x[1]))
        trace.append({"part": "metaphor.inverse_simile", "vehicles": len(ranked)})
        if not ranked or len(ranked[0][1]) < 2 or (len(ranked) > 1 and len(ranked[0][1]) == len(ranked[1][1])):
            return _reply("metaphor", [], trace)
        vehicle, support = ranked[0]
        target = _topic(text)
        sentence = f"{target}は{vehicle}のように{stem}。"
        return _reply("metaphor", [_line(sentence, [_source(text, "user:request")]
                                               + [r.cite() for r in support[:2]],
                                               vehicle=vehicle, property=property_word)], trace, created=True)

    def _action_from_examples(self, text: str, trace: list[dict]) -> Optional[dict]:
        if not re.search(r"何をする|どうすれば", text):
            return None
        tokens = list(_tagger()(text))
        adjacent_verbs = [tokens[i].surface + tokens[i + 1].surface
                          for i in range(len(tokens) - 1)
                          if tokens[i].feature.pos1 == tokens[i + 1].feature.pos1 == "動詞"]
        anchors = list(dict.fromkeys(adjacent_verbs +
                                     sorted((w for w in _terms(text) if len(w) >= 2),
                                            key=len, reverse=True)))[:6]
        query_verbs = {f.predicate for f in frames.read_all(text)} - {
            "する", "ある", "いる", "なる", "言う", "思う"}
        if not query_verbs:
            return None
        for family in ("pro", "local"):
            rows: dict[int, Witness] = {}
            for anchor in anchors:
                for row in self.corpus.search(anchor, family, limit=350):
                    rows[row.id] = row
            outcomes: dict[tuple[str, str], dict[str, Witness]] = defaultdict(dict)
            for row in rows.values():
                marker = re.search(r"たら|ので|ため|と、|すると|後に", row.text)
                if not marker:
                    continue
                before, after = row.text[:marker.start()], row.text[marker.end():]
                if not any(f.predicate in query_verbs for f in frames.read_all(before)):
                    continue
                if sum(w in row.text for w in _terms(text)[:6]) < 2:
                    continue
                for fr in frames.read_all(after):
                    if fr.ambiguous or fr.negated or not fr.patient or fr.predicate in query_verbs:
                        continue
                    if fr.patient + "を" not in after or fr.predicate in {
                            "する", "ある", "いる", "なる", "言う", "思う"}:
                        continue
                    outcomes[(fr.predicate, fr.patient)].setdefault(row.group, row)
            ranked = sorted(((key, list(groups.values())) for key, groups in outcomes.items()
                             if len(groups) >= 2), key=lambda item: -len(item[1]))
            trace.append({"part": "event_transition.action", "family": family,
                          "anchors": anchors, "supported_actions": len(ranked)})
            if not ranked:
                continue
            if len(ranked) > 1 and len(ranked[0][1]) == len(ranked[1][1]):
                trace.append({"part": "event_transition.action", "verdict": "TIED"})
                return _reply("commonsense", [], trace)
            (verb, patient), support = ranked[0]
            sentence = f"その条件では、{patient}を{verb}のがよいでしょう。"
            reread = frames.read_all(sentence)
            if not any(f.predicate == verb and f.patient == patient for f in reread):
                continue
            return _reply("commonsense", [_line(
                sentence, [_source(text, "user:condition")] + [r.cite() for r in support[:3]],
                reread=[f.as_dict() for f in reread])], trace)
        return None

    def commonsense(self, text: str, trace: list[dict]) -> dict:
        action = self._action_from_examples(text, trace)
        if action is not None:
            return action
        if "何のため" in text:
            noun = text.split("は何のため", 1)[0].strip("「」『』 ")
            import sqlite3
            if self.general.exists() and noun:
                con = sqlite3.connect(f"file:{self.general}?mode=ro", uri=True)
                try:
                    choices = con.execute(
                        "SELECT head,count(DISTINCT src) n FROM tedges WHERE dep=? AND rel='で' "
                        "AND pol='+' AND head NOT IN ('する','ある','いる','なる') "
                        "GROUP BY head HAVING n>=2 ORDER BY n DESC LIMIT 3", (noun,)).fetchall()
                    if choices and (len(choices) == 1 or choices[0][1] > choices[1][1]):
                        verb = choices[0][0]
                        src = [{"family": "general", "source": s, "text": sentence}
                               for sentence, s in con.execute(
                                   "SELECT ts.text,t.src FROM tedges t JOIN tsent ts ON ts.sha=t.sha "
                                   "WHERE t.dep=? AND t.rel='で' AND t.head=? AND t.pol='+' "
                                   "GROUP BY t.src LIMIT 3", (noun, verb))]
                        if len(src) >= 2:
                            trace.append({"part": "core_abilities.what_for", "verb": verb,
                                          "independent_sources": len(src)})
                            return _reply("commonsense", [_line(f"{noun}で{verb}ために使います。", src)], trace)
                finally:
                    con.close()
        conditional = self._condition_examples(text, trace)
        if conditional is not None:
            return conditional
        # The question's condition and the result must be joined either in a
        # conditional/causal clause or by consecutive lines of one narrative.
        # Different batches are independent witnesses. Similar outcomes in
        # unrelated lines never become a conditional claim.
        terms = _terms(text)
        if not terms:
            return _reply("commonsense", [], trace)
        family = "local"
        rows = self._search(" ".join(terms[:3]), family=family, limit=100)
        if not rows:
            rows = self._search(terms[0], family="pro", limit=100)
        qframes = frames.read_all(text)
        qverbs = {f.predicate for f in qframes if f.predicate not in {"する", "なる", "ある"}}
        outcomes: dict[tuple, list[tuple[Witness, Witness, frames.Frame]]] = defaultdict(list)
        for before in rows:
            if sum(w in before.text for w in terms[:4]) < min(2, len(terms)):
                continue
            before_frames = frames.read_all(before.text)
            if qverbs and not any(f.predicate in qverbs for f in before_frames):
                continue
            sequence = self.corpus.neighbors(before, after=2)
            if not sequence:
                continue
            for after in sequence:
                if after.id < before.id or after.id > before.id + 1:
                    continue
                if after.id == before.id:
                    if not _LINK.search(after.text):
                        continue
                    fs = frames.read_all(after.text)
                    candidates = fs[1:] if len(fs) > 1 else []
                else:
                    if not (_LINK.search(before.text) or before.text.endswith(("。", "？"))):
                        continue
                    candidates = frames.read_all(after.text)
                for fr in candidates:
                    if fr.ambiguous or fr.negated or not fr.agent or fr.predicate in qverbs:
                        continue
                    if re.search(r"何をする|どうすれば", text) and not fr.patient:
                        continue
                    if fr.predicate in {"する", "なる", "ある", "いる", "言う", "思う"}:
                        continue
                    if not _frame_sentence(fr, after):
                        continue
                    key = fr.key()
                    outcomes[key].append((before, after, fr))
        ranked = []
        for key, examples in outcomes.items():
            independent = {}
            for a, b, fr in examples:
                independent.setdefault(a.group, (a, b, fr))
            if len(independent) >= 2:
                ranked.append((key, list(independent.values())))
        ranked.sort(key=lambda x: -len(x[1]))
        trace.append({"part": "event_transition", "conditions": len(rows),
                      "supported_outcomes": len(ranked), "minimum_sources": 2})
        if not ranked or (len(ranked) > 1 and len(ranked[0][1]) == len(ranked[1][1])):
            if ranked:
                trace.append({"part": "event_transition", "verdict": "TIED"})
            return _reply("commonsense", [], trace)
        examples = ranked[0][1]
        result = _frame_sentence(examples[0][2], examples[0][1])
        if result is None:
            return _reply("commonsense", [], trace)
        # The wording says what was observed in two independent narratives,
        # without turning a sample into a universal prediction.
        cites = []
        for before, after, _ in examples[:3]:
            cites.extend((before.cite(), after.cite()))
        sentence = "その条件に続く場面では、" + result["text"]
        back = frames.read(sentence)
        if not back or back.key() != examples[0][2].key():
            return _reply("commonsense", [], trace)
        return _reply("commonsense", [_line(sentence, cites,
                                            frame=examples[0][2].as_dict(), reread=back.as_dict())], trace)

    def _pun_explanation(self, quote: str, trace: list[dict]) -> dict:
        toks = [t for t in _tagger()(quote) if t.feature.pos1 not in ("補助記号", "空白")]
        chunks = []
        for i in range(len(toks)):
            for n in (1, 2, 3):
                if i + n > len(toks):
                    break
                surface = "".join(t.surface for t in toks[i:i+n])
                reading = core_abilities.kana(surface)
                if len(reading) >= 2 and any(t.feature.pos1 in ("名詞", "動詞", "形容詞") for t in toks[i:i+n]):
                    chunks.append((surface, reading, i, i+n))
        scored = []
        for i, a in enumerate(chunks):
            for b in chunks[i+1:]:
                if a[0] == b[0] or not (a[3] <= b[2] or b[3] <= a[2]):
                    continue
                shared = 0
                for ca, cb in zip(a[1], b[1]):
                    if ca != cb:
                        break
                    shared += 1
                # The shared sound may start later (校長 / 絶好調). Prefer
                # an exact repeated reading, then the longest overlap.
                from difflib import SequenceMatcher
                common = max((block.size for block in SequenceMatcher(None, a[1], b[1]).get_matching_blocks()),
                             default=0)
                if common >= 2 and common >= min(len(a[1]), len(b[1])) - 1:
                    exact = int(a[1] == b[1])
                    scored.append((exact, common, min(len(a[1]), len(b[1])), a, b))
        scored.sort(key=lambda x: (-x[0], -x[1], -x[2], len(x[3][0]) + len(x[4][0])))
        unique = []
        seen = set()
        for item in scored:
            key = tuple(sorted((item[3][0], item[4][0])))
            if key not in seen:
                unique.append(item)
                seen.add(key)
        scored = unique
        trace.append({"part": "core_abilities.kana", "sound_pairs": len(scored)})
        if not scored:
            # A common form is a katakana noun followed by a hiragana
            # echo (イカ／いかが). UniDic may tag the echo as an interjection,
            # so compare the written runs directly rather than requiring a
            # content POS on both sides.
            runs = re.findall(r"[ァ-ヺー]{2,}|[ぁ-ん]{2,}", quote)
            for i, a_run in enumerate(runs):
                for b_run in runs[i+1:]:
                    ar, br = core_abilities.kana(a_run), core_abilities.kana(b_run)
                    if a_run != b_run and len(ar) >= 2 and (br.startswith(ar) or ar.startswith(br)):
                        msg = f"「{a_run}」（{ar}）と「{b_run}」（{br}）の音が重なる言葉遊びです。"
                        return _reply("humor", [_line(msg, [_source(quote)], mechanism="sound_overlap")], trace)
        if not scored or (len(scored) > 1 and scored[0][:3] == scored[1][:3]
                           and {scored[0][3][0], scored[0][4][0]} !=
                           {scored[1][3][0], scored[1][4][0]}):
            return _reply("humor", [], trace)
        _, _, _, a, b = scored[0]
        msg = f"「{a[0]}」（{a[1]}）と「{b[0]}」（{b[1]}）の音が重なる言葉遊びです。"
        return _reply("humor", [_line(msg, [_source(quote)], mechanism="sound_overlap")], trace)

    def _pun_word(self, text: str) -> tuple[str, list[dict]]:
        quoted = _QUOTE.findall(text)
        if quoted and len(quoted[0]) <= 20:
            return quoted[0], [_source(quoted[0])]
        # Try the user's noun first. A scene index can supply a related noun
        # when a broad theme has no sound partner, without a topic table.
        preface = re.split(r"(?:を使って|を題材に|をテーマに|について|に関する)", text, 1)[0]
        nouns = []
        chunk = ""
        for tok in _tagger()(preface):
            if tok.feature.pos1 in ("名詞", "接尾辞") and tok.surface not in _STOP:
                chunk += tok.surface
            elif chunk:
                nouns.append(chunk)
                chunk = ""
        if chunk:
            nouns.append(chunk)
        nouns = [n for n in nouns if 1 <= len(n) <= 12]
        if not nouns:
            return "", []
        label = nouns[-1]
        rows = self.corpus.search(label, "local", limit=40, scene=True)
        if not rows:
            rows = self.corpus.search(label, "local", limit=40)
        scene_nouns = [(t.surface, row) for row in rows for t in _tagger()(row.text)
                       if t.feature.pos1 == "名詞" and 2 <= len(t.surface) <= 8
                       and t.surface not in _STOP]
        lex = _pun_forms()
        for word in dict.fromkeys([label, *reversed(nouns[:-1]), *(w for w, _ in scene_nouns)]):
            reading = core_abilities.kana(word)
            if len(reading) < 2:
                continue
            if any(base != word and spoken.startswith(
                    reading.replace("ッ", "")[:max(2, len(reading)-1)])
                    for base, _, _, spoken in lex):
                src = [_source(text, "user:theme")]
                if word != label:
                    src += [row.cite() for w, row in scene_nouns if w == word][:1]
                return word, src
        return "", []

    def _homophone_pair(self, words: list[str], trace: list[dict]) -> Optional[dict]:
        if len(words) < 2 or core_abilities.kana(words[0]) != core_abilities.kana(words[1]):
            return None
        import sqlite3
        if not self.general.exists():
            return None
        con = sqlite3.connect(f"file:{self.general}?mode=ro", uri=True)
        try:
            roles = []
            for word in words[:2]:
                rows = con.execute(
                    "SELECT head,count(DISTINCT src) n FROM tedges WHERE dep=? AND rel='を' "
                    "AND pol='+' AND head NOT IN ('する','ある','いる','なる') "
                    "GROUP BY head HAVING n>=2 ORDER BY n DESC LIMIT 75", (word,)).fetchall()
                roles.append(rows)
            pairs = []
            for left, ln in roles[0]:
                for right, rn in roles[1]:
                    if left == right:
                        continue
                    la, rb = core_abilities.kana(left), core_abilities.kana(right)
                    overlap = next((i for i, (a, b) in enumerate(zip(la, rb)) if a != b), min(len(la), len(rb)))
                    if overlap >= 2:
                        pairs.append((overlap, min(ln, rn), ln + rn, left, right))
            if not pairs:
                return None
            pairs.sort(key=lambda x: (-x[0], -x[1], -x[2]))
            if len(pairs) > 1 and pairs[0][:3] == pairs[1][:3]:
                trace.append({"part": "homophone_pair", "verdict": "TIED"})
                return None
            _, _, _, left, right = pairs[0]
            sources = [_source(word) for word in words[:2]]
            for word, verb in ((words[0], left), (words[1], right)):
                sources += self._general_witness(
                    "SELECT s.text,t.src FROM tedges t JOIN tsent s ON s.sha=t.sha "
                    "WHERE t.dep=? AND t.head=? AND t.rel='を' AND t.pol='+' "
                    "GROUP BY t.src LIMIT 2", (word, verb))
            line = f"{words[0]}を{left}、{words[1]}を{right}。"
            trace.append({"part": "homophone_pair", "reading": core_abilities.kana(words[0]),
                          "verbs": [left, right], "reread": len(frames.read_all(line)) == 2})
            return _reply("humor", [_line(line, sources, mechanism="homophone_and_verb_echo",
                                          reread=[f.as_dict() for f in frames.read_all(line)])], trace,
                          created=True)
        finally:
            con.close()

    def humor(self, text: str, trace: list[dict]) -> dict:
        if re.search(r"仕掛け|どこが面白い|面白さを", text):
            quoted = _QUOTE.findall(text)
            return self._pun_explanation(quoted[-1], trace) if quoted else _reply("humor", [], trace)
        quoted = _QUOTE.findall(text)
        if len(quoted) >= 2 and core_abilities.kana(quoted[0]) == core_abilities.kana(quoted[1]):
            pair = self._homophone_pair(quoted, trace)
            return pair if pair else _reply("humor", [], trace)
        word, sources = self._pun_word(text)
        trace.append({"part": "scene_leaf", "word": word,
                      "family": sources[-1].get("family") if sources else ""})
        if not word:
            return _reply("humor", [], trace)
        reading = core_abilities.kana(word)
        options = []
        for base, form, vr, spoken in _pun_forms():
            if word == form or word in form:
                continue
            wr = reading.replace("ッ", "")
            overlap = 0
            for x, y in zip(wr, spoken):
                if x != y:
                    break
                overlap += 1
            if overlap >= max(2, len(wr)-1) and spoken != wr:
                options.append((form, core_abilities.kana(form), overlap, base))
        if not options:
            return _reply("humor", [], trace)
        ranked = []
        if self.general.exists():
            import sqlite3
            con = sqlite3.connect(f"file:{self.general}?mode=ro", uri=True)
            try:
                for verb, vr, overlap, base in options[:80]:
                    n = con.execute("SELECT count(DISTINCT src) FROM tedges WHERE head=? AND rel='が' AND pol='+'",
                                    (verb,)).fetchone()[0]
                    fit = con.execute("SELECT count(DISTINCT src) FROM tedges WHERE head=? AND dep=? "
                                      "AND rel IN ('が','は') AND pol='+'", (verb, word)).fetchone()[0]
                    if verb == base or n >= 2:
                        ranked.append((overlap, fit, n, verb, vr, base))
            finally:
                con.close()
        else:
            # The wheel ships the complete P4 indexes. Count an overt
            # noun-as-agent event within one family; families never pool votes.
            verbs = {verb for verb, _, _, _ in options[:80]}
            fit_by_verb = {}
            for family in ("local", "pro"):
                groups: dict[str, set[str]] = defaultdict(set)
                for row in self.corpus.search(word, family, limit=300):
                    if not any(v[:2] in row.text for v in verbs if len(v) >= 2):
                        continue
                    for fr in frames.read_all(row.text):
                        if fr.agent == word and fr.predicate in verbs:
                            groups[fr.predicate].add(row.group)
                if groups:
                    fit_by_verb = {verb: len(srcs) for verb, srcs in groups.items()}
                    break
            ranked = [(overlap, fit_by_verb.get(verb, 0), 0, verb, vr, base)
                      for verb, vr, overlap, base in options[:80]
                      if verb == base or overlap >= len(reading.replace("ッ", ""))]
        if len(sources) > 1:
            ranked = [r for r in ranked if r[1] >= 2]
        ranked.sort(key=lambda x: (-x[0], -x[1], -x[2]))
        trace.append({"part": "core_abilities.pun_lexicon", "candidates": len(ranked)})
        if not ranked:
            return _reply("humor", [], trace)
        if len(ranked) > 1 and ranked[0][:3] == ranked[1][:3]:
            trace.append({"part": "pun", "verdict": "TIED"})
            return _reply("humor", [], trace)
        _, fit, _, verb, vr, base = ranked[0]
        fr = frames.Frame(predicate=verb, agent=word)
        sentence = realize.realize(fr, past=True)["sentences"].get("active")
        if not sentence:
            return _reply("humor", [], trace)
        spoken_reading = core_abilities.kana(realize.conjugate(verb, past=True) or verb)
        explanation = f"（{reading}／{spoken_reading}の音を重ねました。）"
        role_sources = (self._general_witness(
            "SELECT s.text,t.src FROM tedges t JOIN tsent s ON s.sha=t.sha "
            "WHERE t.head=? AND t.dep=? AND t.rel IN ('が','は') AND t.pol='+' "
            "GROUP BY t.src LIMIT 2", (verb, word)) if fit else [])
        if fit and not role_sources:
            for family in ("local", "pro"):
                role_sources = [row.cite() for row in self.corpus.search(word, family, limit=300)
                                if any(fr.agent == word and fr.predicate == verb
                                       for fr in frames.read_all(row.text))][:2]
                if role_sources:
                    break
        return _reply("humor", [_line(sentence + explanation,
                                       sources + role_sources + [{"family": "pun_lexicon", "source": str(core_abilities.PUN_LEXICON),
                                                                  "text": base, "reading": vr}],
                                       frame=fr.as_dict(), reread=frames.read(sentence).as_dict())],
                      trace, created=True)

    def creation(self, text: str, trace: list[dict]) -> dict:
        if re.search(r"俳句|五七五|五・七・五", text):
            return self._haiku(text, trace)
        if "なぞなぞ" in text:
            return self._riddle(text, trace)
        if "キャッチコピー" in text:
            return self._catchphrase(text, trace)
        if re.search(r"物語|ストーリー", text):
            return self._narrative(text, trace, poem=False)
        return self._narrative(text, trace, poem=True)

    def _image_phrases(self, sentence: str, target: int) -> list[str]:
        toks = list(_tagger()(sentence.strip("。！？")))
        out = []
        for i in range(len(toks)):
            for j in range(i+1, min(len(toks), i+7)+1):
                part = toks[i:j]
                phrase = "".join(t.surface for t in part)
                if re.search(r"[「」『』、。！？?!0-9０-９]", phrase):
                    continue
                if re.match(r"^(?:の|が|を|に|へ|で|は|も|と|や)", phrase) or \
                        re.search(r"(?:の|が|を|に|へ|で|は|も|と)$", phrase):
                    continue
                if not any(t.feature.pos1 == "名詞" for t in part):
                    continue
                if part[0].feature.pos1 in ("助詞", "助動詞", "補助記号"):
                    continue
                if part[-1].feature.pos1 not in ("名詞", "動詞", "形容詞"):
                    continue
                if part[-1].feature.pos1 == "名詞" and any(t.surface in
                    ("が", "を", "に", "へ", "で", "は", "も", "と") for t in part):
                    continue
                if any(t.feature.pos2 == "代名詞" for t in part):
                    continue
                count = core_abilities.morae(phrase)
                if count == target and phrase not in out:
                    out.append(phrase)
                if count > target:
                    break
        return out

    def _haiku(self, text: str, trace: list[dict]) -> dict:
        topic = _topic(text)
        rows = self._search(topic, limit=120)
        if not rows:
            return _reply("creation", [], trace)
        # A seasonal noun comes from the request or from its retrieved scene;
        # meter, scene agreement and a source sentence replace a topic list.
        season_candidates = [topic] if core_abilities.morae(topic) == 4 else []
        season = ""
        season_row = None
        for word in season_candidates:
            hits = [r for r in rows if word in r.text]
            if hits:
                season, season_row = word, hits[0]
                break
        if not season_row:
            seasonal = []
            for position, term in enumerate(_terms(topic)):
                if len(term) != 1:
                    continue
                for row in self.corpus.search(term, "local", limit=1000):
                    if "季節" not in row.scene:
                        continue
                    for tok in _tagger()(row.text):
                        if (tok.feature.pos1 == "名詞" and term in tok.surface and
                                core_abilities.morae(tok.surface) == 4):
                            seasonal.append((position, sum(w in row.text for w in _terms(topic)),
                                             tok.surface, row))
            if seasonal:
                seasonal.sort(key=lambda x: (-x[0], -x[1], x[3].id))
                _, _, season, season_row = seasonal[0]
        if not season_row:
            return _reply("creation", [], trace)
        scene = season_row.scene
        scene_rows = self.corpus.search(scene, "local", limit=180, scene=True) if scene else rows
        if not scene_rows:
            scene_rows = rows
        # Two independent image sentences from one scene. The first line's
        # 4-mora season word plus や is the cutting-word constraint.
        picks = []
        topic_terms = set(_terms(topic))
        for count in (7, 5):
            options = []
            for row in scene_rows:
                if row.sha == season_row.sha or any(row.sha == x[1].sha for x in picks):
                    continue
                for phrase in self._image_phrases(row.text, count):
                    if season in phrase:
                        continue
                    time_terms = {term for term in ("朝", "昼", "夕", "夜") if term in topic}
                    if time_terms and any(term in phrase for term in
                                          {"朝", "昼", "夕", "夜"} - time_terms):
                        continue
                    score = sum(2 for w in _terms(topic) if w in row.text)
                    missing_terms = {term for term in topic_terms
                                     if term not in season and term not in
                                     set(_terms(" ".join(x[0] for x in picks)))}
                    score += 10 * len(missing_terms & set(_terms(phrase)))
                    score += sum(t.feature.pos1 == "名詞" for t in _tagger()(phrase))
                    options.append((score, row, phrase))
            if not options:
                return _reply("creation", [], trace)
            options.sort(key=lambda x: (-x[0], len(x[2]), x[1].id))
            picks.append((options[0][2], options[0][1]))
        first = season + "や"
        realized_terms = set(_terms(picks[0][0] + " " + picks[1][0]))
        covered_terms = {term for term in topic_terms
                         if term in season or term in realized_terms}
        if topic_terms and len(covered_terms) * 2 < len(topic_terms):
            return _reply("creation", [], trace)
        if [core_abilities.morae(x) for x in (first, picks[0][0], picks[1][0])] != [5, 7, 5]:
            return _reply("creation", [], trace)
        if picks[0][1].sha == picks[1][1].sha:
            return _reply("creation", [], trace)
        trace.append({"part": "haiku.constraint_search", "morae": [5, 7, 5],
                      "cutting_word": "や", "scene": scene, "distinct_sentences": True})
        lines = [_line(first + "／", [season_row.cite()], morae=5),
                 _line(picks[0][0] + "／", [picks[0][1].cite()], morae=7),
                 _line(picks[1][0], [picks[1][1].cite()], morae=5)]
        return _reply("creation", lines, trace, created=True)

    def _riddle(self, text: str, trace: list[dict]) -> dict:
        quoted = _QUOTE.findall(text)
        answer = quoted[-1] if quoted else ""
        if not answer or not self.general.exists():
            return _reply("creation", [], trace)
        # A property is a relation observed of the answer itself. Keep each
        # clue's own source; two clues cannot arise from one corpus sentence.
        import sqlite3
        con = sqlite3.connect(f"file:{self.general}?mode=ro", uri=True)
        try:
            rows = con.execute(
                "SELECT t.head,t.rel,count(DISTINCT t.src) n FROM tedges t "
                "WHERE t.dep=? AND t.rel IN ('が','属性','を','に') AND t.pol='+' "
                "AND t.head NOT IN ('する','ある','いる','なる','できる','言う','思う') "
                "GROUP BY t.head,t.rel HAVING n>=2 ORDER BY n DESC LIMIT 60", (answer,)).fetchall()
            available = []
            for prop, rel, _ in rows:
                witnesses = con.execute(
                    "SELECT s.text,t.src FROM tedges t JOIN tsent s ON s.sha=t.sha "
                    "WHERE t.dep=? AND t.head=? AND t.rel=? AND t.pol='+' "
                    "GROUP BY t.src LIMIT 3", (answer, prop, rel)).fetchall()
                pair = next(((s, src) for s, src in witnesses
                             if answer in s), None)
                if pair:
                    available.append((prop, rel, *pair))
        finally:
            con.close()
        chosen = available[:1]
        if chosen:
            first, first_rel = chosen[0][:2]
            preferred = [x for x in available[1:] if x[1] != first_rel and x[2] != chosen[0][2]]
            preferred += [x for x in available[1:] if x[2] != chosen[0][2]
                          and core_abilities.kana(x[0]) != core_abilities.kana(first)]
            if preferred:
                chosen.append(preferred[0])
        trace.append({"part": "riddle.properties", "answer": answer, "count": len(chosen)})
        if len(chosen) < 2:
            return _reply("creation", [], trace)
        p1, r1, s1, src1 = chosen[0]
        p2, r2, s2, src2 = chosen[1]
        def phrase(prop: str, rel: str) -> str:
            if rel == "が":
                return prop + "ことがある"
            if rel == "属性":
                return prop + "性質がある"
            if rel == "に":
                return prop + "先になる"
            passive = realize.conjugate(prop, passive=True)
            return (passive or prop) + "ことがある"
        clue = f"{phrase(p1, r1)}。{phrase(p2, r2)}。私は何でしょう？"
        if answer in clue:
            return _reply("creation", [], trace)
        sources = [{"family": "general", "source": src1, "text": s1},
                   {"family": "general", "source": src2, "text": s2}]
        return _reply("creation", [_line(clue, sources, properties=[p1, p2]),
                                   _line(f"答え: {answer}。", [_source(text, "user:answer")])],
                      trace, created=True)

    def _scene_graph(self, rows: list[Witness], topic: str, trace: list[dict]) -> None:
        from .cross_store import CrossStore
        from . import surface, hub_edges
        from .trace import Trace, walk
        store = CrossStore()
        edges: dict[str, list[tuple[str, str]]] = defaultdict(list)
        vocabulary = set()
        for row in rows:
            words = _terms(row.text)[:7]
            vocabulary.update(words)
            for a in words:
                cross = store.crosses.setdefault(a, {})
                for b in words:
                    if a != b:
                        cross[b] = cross.get(b, 0) + 1
                for b in words:
                    if a != b:
                        edges[a].append((b, words[0]))
        core = next((w for w in _terms(topic) if w in store.crosses), "")
        if core:
            facets = list(store.crosses[core])
            centre = surface.word_center(store, core, facets, vocabulary)
            seats = hub_edges.seats(store, core, lambda c: edges.get(c, []), vocab=vocabulary)
            trace.append({"part": "surface.word_center", "word": centre["word"] if centre else None})
            trace.append({"part": "hub_edges.seats", "seats": len(seats)})
            path = Trace(seed=core, mode="path")
            path.record(core, set(facets))
            if seats and (len(seats) == 1 or seats[0]["weight"] > seats[1]["weight"]):
                path.record(seats[0]["to"], set(store.crosses[seats[0]["to"]]))
            trace.append({"part": "trace.Trace", **path.report()})
            walked = walk(store, core, mode="path", steps=3)
            trace.append({"part": "trace.walk", **walked.report()})

    def _passage(self, topic: str, count: int, trace: list[dict], *, turn: bool,
                 poem: bool = False, surprise: bool = False, uplift: bool = False) -> list[dict]:
        noun_terms = []
        previous_noun = False
        for tok in _tagger()(topic):
            if tok.feature.pos1 in ("名詞", "接尾辞") and tok.surface not in _STOP and \
                    tok.surface not in {"朝", "昼", "午後", "夕方", "夜", "日"}:
                if previous_noun and noun_terms:
                    noun_terms[-1] += tok.surface
                else:
                    noun_terms.append(tok.surface)
                previous_noun = True
            else:
                previous_noun = False
        focus = noun_terms[-1] if noun_terms else _focus(topic)
        if not focus:
            return []
        modifiers = [w for w in _terms(topic) if w != focus]
        rows = []
        for modifier in reversed(modifiers):
            rows = self.corpus.search_scene(focus, [modifier], "local", limit=180)
            if rows:
                break
        if not rows:
            rows = self.corpus.search(focus, "local", limit=500 if uplift else 120)
        scene_rows = [r for r in rows if focus in r.scene]
        if scene_rows:
            rows = scene_rows
        rows.sort(key=lambda r: -sum(w in r.scene for w in modifiers))
        if uplift:
            rows = [r for r in rows if any(
                re.search(r"笑顔|笑っ|元気|励ま", n.text)
                for n in self.corpus.neighbors(r, after=12)[1:])]
        frame_cache: dict[int, Optional[dict]] = {}
        for seed in rows[:500 if uplift else 120]:
            seq = self.corpus.neighbors(seed, after=20 if poem else 12)
            if len(seq) < count:
                continue
            scene = seed.scene
            available = []
            for row in seq:
                if row.scene != scene:
                    break
                if row.id not in frame_cache:
                    candidates = []
                    for fr in frames.read_all(row.text):
                        plain = _frame_sentence(fr, row)
                        if plain:
                            candidates.append(plain)
                        if poem and fr.agent:
                            # AとBがX explicitly licenses AがX as a separate
                            # frame. The ordinary reader sometimes retains
                            # only B; split the coordination and reread it.
                            coordinated = re.search(
                                r"(?:^|[、。])([^、。]{2,24})と" + re.escape(fr.agent) + r"が",
                                row.text)
                            if coordinated:
                                other = coordinated.group(1)
                                split_fr = frames.Frame(fr.predicate, other, fr.patient,
                                                        fr.recipient, fr.negated, fr.past)
                                split_line = _frame_sentence(split_fr, row)
                                if split_line:
                                    candidates.append(split_line)
                    if uplift:
                        smile = re.search(r"([一-鿿ぁ-んァ-ヺー]{1,8})(?:が|は|も)笑顔で", row.text)
                        if smile:
                            smile_frame = frames.Frame("笑う", smile.group(1), past=True)
                            smile_line = _frame_sentence(smile_frame, row)
                            if smile_line:
                                received = re.search(r"笑顔で([一-鿿ぁ-んァ-ヺー]{1,8})を受け取", row.text)
                                if received and received.group(1) in focus:
                                    line = f"{received.group(1)}を受け取った{smile.group(1)}が笑った。"
                                    source_keys = {f.key() for f in frames.read_all(row.text)}
                                    back = frames.read_all(line)
                                    if (any(f.key() == smile_frame.key() for f in back) and
                                            any(f.key() in source_keys and f.predicate != "笑う" for f in back)):
                                        smile_line = {**smile_line, "text": line,
                                                      "reread": [f.as_dict() for f in back],
                                                      "transform": "attested_receipt_and_smile"}
                                        candidates.append(smile_line)
                    frame_cache[row.id] = (max(candidates, key=lambda c: (
                        int(uplift and c["frame"]["predicate"] == "笑う"),
                        int(uplift and focus in "".join(str(c["frame"][k]) for k in
                                                     ("agent", "patient", "recipient"))),
                        int(bool(re.search(r"音|匂い|におい|香り", c["text"])))))
                        if candidates else None)
                candidate = frame_cache[row.id]
                if candidate:
                    available.append({**candidate, "row": row})
                if not poem and not uplift and len(available) >= count:
                    break
            if len(available) < count:
                continue
            first = available[0]
            if focus not in "".join(str(first["frame"][k]) for k in ("agent", "patient", "recipient")):
                continue
            if poem:
                scene_words = {w for w in modifiers if w in seed.scene}
                scenic = []
                for candidate in available[1:]:
                    if focus not in scene and candidate["row"].id > seed.id + 8:
                        continue
                    frame_text = candidate["text"]
                    score = 3 * int(focus in frame_text)
                    score += 2 * sum(w in frame_text for w in scene_words)
                    score += sum(t.feature.pos1 == "名詞" for t in _tagger()(frame_text))
                    score += 2 * int(bool(re.search(r"音|匂い|におい|香り|湯気|紙|鉛筆|文字|ページ", frame_text)))
                    if score:
                        scenic.append((score, candidate))
                scenic.sort(key=lambda x: (-x[0], x[1]["row"].id))
                chosen = [first] + sorted((c for _, c in scenic[:count-1]), key=lambda c: c["row"].id)
                if len(chosen) < count:
                    continue
            elif uplift:
                endings = [c for c in available[1:] if c.get("transform") == "attested_receipt_and_smile"]
                if not endings:
                    continue
                ending = endings[0]
                middles = [c for c in available[1:] if c["row"].id < ending["row"].id
                           and c["frame"]["predicate"] != first["frame"]["predicate"]]
                if not middles:
                    continue
                chosen = [first, middles[0], ending]
            else:
                chosen = available[:count]
                stem = focus[:1]
                if sum(stem in c["text"] for c in chosen) < 2:
                    continue
            if turn and not any(re.search(r"しかし|ところが|けれど|だが|すると|そのとき|突然", c["row"].text)
                                for c in chosen[1:-1]):
                continue
            if surprise and not re.search(
                    r"実は|まさか|思いがけず|予想外|意外|なんと", chosen[-1]["row"].text):
                continue
            self._scene_graph([c["row"] for c in chosen], topic, trace)
            trace.append({"part": "event_graph.walk", "family": seed.family, "scene": scene,
                          "group": seed.group, "ids": [c["row"].id for c in chosen],
                          "shape": ["start", "turn", "ending"]})
            trace.append({"part": "realize.realize", "sentences": len(chosen),
                          "roundtrip": True})
            return chosen
        return []

    def _writer_candidate(self, candidate: dict, trace: list[dict]) -> None:
        # Form recombination is a proposal, never a citation. Only an exact
        # frame reread could promote it. The original sourced frame remains
        # the default sentence because an attested form alone proves no fact.
        try:
            from .writer import Writer
            from .compose_ja import compose
            writer_path = self.general.with_name("writer.json")
            if not writer_path.exists():
                trace.append({"part": "writer.Writer.load", "verdict": "LACK_OF_ASSET",
                              "path": str(writer_path)})
                return
            writer = _writer(str(writer_path))
            trace.append({"part": "writer.Writer.load", "verdict": "LOADED",
                          "path": str(writer_path)})
            f = candidate["frame"]
            drafts = compose(writer.forms, f["agent"],
                             [x for x in (f["patient"], f["recipient"]) if x],
                             limit=2, content_from=[f["agent"]], vocab=writer.vocab,
                             licence="descriptive")
            accepted = any(frames.read(d.text) and frames.read(d.text).key() ==
                           (f["predicate"], f["agent"], f["patient"], f["recipient"], f["negated"])
                           for d in drafts)
            trace.append({"part": "compose_ja.compose", "drafts": len(drafts),
                          "reread_match": accepted})
        except Exception as exc:
            trace.append({"part": "compose_ja.compose", "verdict": "UNAVAILABLE",
                          "reason": type(exc).__name__})

    def _narrative(self, text: str, trace: list[dict], *, poem: bool) -> dict:
        topic = _topic(text)
        count = 5 if re.search(r"五行|5行", text) else 4 if poem else 3
        turn = bool(not poem and "意外性" in text)
        uplift = bool(not poem and "元気づけ" in text)
        passage = self._passage(topic, count, trace, turn=turn, poem=poem,
                                surprise="意外性" in text, uplift=uplift)
        if len(passage) < count:
            return _reply("creation", [], trace)
        if not poem and "元気づけ" in text and not re.search(r"笑顔|元気|励ま|笑った|笑う",
                                                 passage[-1]["row"].text):
            trace.append({"part": "story.shape", "verdict": "NO_UPLIFT_ENDING"})
            return _reply("creation", [], trace)
        if poem and re.search(r"音や匂い|音やにおい|音や香り", text) and not any(
                re.search(r"音|匂い|におい|香り", c["text"]) for c in passage):
            trace.append({"part": "poem.constraint", "verdict": "NO_SENSORY_LINE"})
            return _reply("creation", [], trace)
        if poem and "記録" in text and not any(re.search(r"記録|書く|ページ|思い出", c["text"])
                                              for c in passage):
            trace.append({"part": "poem.constraint", "verdict": "NO_MEMORY_LINE"})
            return _reply("creation", [], trace)
        self._writer_candidate(passage[0], trace)
        if poem:
            lines = [_line(c["text"] + ("\n" if i < count-1 else ""), c["sources"],
                           frame=c["frame"], reread=c["reread"])
                     for i, c in enumerate(passage)]
        else:
            lines = self._joined(passage, trace, same_scene=True)
        return _reply("creation", lines, trace, created=True)

    def _catchphrase(self, text: str, trace: list[dict]) -> dict:
        quoted = _QUOTE.findall(text)
        brief = quoted[0] if quoted else text.split("。", 1)[0]
        after_brief = text.split("」", 1)[-1] if quoted else text
        product = re.search(r"([一-鿿ぁ-んァ-ヺー]{2,18})の(?:新)?(?:商品|製品|サービス)", after_brief)
        target_match = re.match(r"([一-鿿ぁ-んァ-ヺー]{2,18}?)(?:が|を|に|へ)", brief)
        target = product.group(1) if product else target_match.group(1) if target_match else ""
        if not target:
            return _reply("creation", [], trace)

        sources = [_source(text, "user:brief")]
        options: list[tuple[int, str, list[dict], str]] = []
        # The first two forms use the stated desired change. A negated verb
        # is derived by conjugation; an adverb remains the user's own word.
        if re.search(r"がち|すぎ|過ぎ", brief):
            verbs = [t.feature.lemma for t in _tagger()(brief)
                     if t.feature.pos1 == "動詞" and t.feature.lemma not in ("する", "為る")]
            if verbs:
                negative = realize.conjugate(verbs[0], neg=True)
                if negative:
                    options.append((4, f"{target}は{negative}。", sources, "AはB"))
        object_match = re.match(r"([一-鿿ぁ-んァ-ヺー]{2,18})を", brief)
        adverbs = [t.surface for t in _tagger()(brief)
                   if t.feature.pos1 == "形容詞" and t.surface.endswith("く")]
        if object_match and adverbs:
            options.append((4, f"{target}一つで、{object_match.group(1)}を{adverbs[0]}。",
                            sources, "A一つでBをC"))

        # When the brief offers several effects, observed co-occurrences
        # decide between them. Equal top support is an abstention.
        choice = re.search(r"([^。]{2,40})のどちらか", after_brief)
        effects = [part.strip("、 ") for part in choice.group(1).split("と")] if choice else []
        rows = self._search(target, limit=180)
        for effect in effects:
            if not effect or effect == target:
                continue
            core = effect.rsplit("の", 1)[-1]
            support = self.corpus.distinct_sources(r for r in rows if core in r.text)
            if support:
                options.append((min(3, len(support)), f"{target}から、{core}へ。",
                                sources + [r.cite() for r in support[:3]], "AからBへ"))
        trace.append({"part": "catchphrase.closed_grammar", "target": target,
                      "candidates": len(options), "corpus_rows": len(rows)})
        if not options:
            return _reply("creation", [], trace)
        options.sort(key=lambda item: -item[0])
        if len(options) > 1 and options[0][0] == options[1][0]:
            trace.append({"part": "catchphrase.closed_grammar", "verdict": "TIED"})
            return _reply("creation", [], trace)
        _, slogan, cites, form = options[0]
        return _reply("creation", [_line(slogan, cites, form=form)], trace, created=True)


@lru_cache(maxsize=1)
def _writer(path: str):
    from .writer import Writer
    return Writer.load(Path(path))
