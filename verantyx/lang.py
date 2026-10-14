"""Japanese run segmentation used by the line-3 grammar layer (trimmed copy of verantyx/lang.py of the research tree).

Only what verantyx.line3 and verantyx.loom read is kept: `detect`, `strip_attribution`, `ja_content_runs` and the tables they use.
The ingest / ask / topic functions of the research tree needed the cross store and are not part of the harness.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# script detection
# ---------------------------------------------------------------------------

_RE_JA = re.compile(r"[぀-ヿ一-鿿]")
_RE_LATIN = re.compile(r"[A-Za-zÀ-ɏ]")
_RE_KANA = re.compile(r"[ぁ-んァ-ヶー]")
_RE_HAN = re.compile(r"[㐀-䶿一-鿿]")


#: A latin WORD, for the language vote. `_RE_LATIN` stays character-based
#: because the `latin` verdict below still needs to know whether there is any
#: latin at all.
_RE_LATIN_WORD = re.compile(r"[A-Za-zＡ-Ｚａ-ｚ][A-Za-z0-9Ａ-Ｚａ-ｚ０-９.+#_-]*")


def detect(text: str) -> str:
    """Script heuristic: "ja" | "zh" | "en" | "latin".

    Chinese and Japanese share the ideographs, so counting them cannot tell
    the languages apart — and cataloguing a real corpus showed the cost:
    Chinese documents were routed down the Japanese path and 如果 and 配置
    surfaced as "topics" with Chinese facets attached. What does separate
    them is kana: running Japanese prose without any kana is close to
    nonexistent, while Chinese never has it. Han without kana, at a length
    where the absence is meaningful, is therefore called "zh".

    Short han-only fragments (交通情報 — a headline, a label) stay "ja":
    four characters without kana is normal Japanese, forty is not.
    """
    t = text or ""
    n_ja = len(_RE_JA.findall(t))
    # Latin is counted in WORDS, Japanese in characters, because that is the
    # fair comparison: 実装言語 is four characters and one word, TypeScript is
    # ten characters and one word. Counting latin per character called
    # 「実装言語はTypeScriptを用いる。」 English — nine Japanese characters
    # against ten latin ones — and routed a Japanese sentence to the English
    # decomposer, which cored it under `typescript` and attached no facets.
    # One long tool name was enough to change the language of a sentence.
    n_lat = len(_RE_LATIN_WORD.findall(t))
    if n_ja > n_lat:
        han = len(_RE_HAN.findall(t))
        if han >= 6 and not _RE_KANA.search(t):
            return "zh"
        return "ja"
    if n_lat == 0:
        return "latin"
    # English vs other latin languages is decided by the caller via lang=;
    # auto default treats latin as English (richest pipeline).
    return "en"


# ---------------------------------------------------------------------------
# Japanese (elementary, tokenizer-free)
# ---------------------------------------------------------------------------

# A content run is a katakana word, or an ideograph sequence that may
# contain digits and end in one okurigana character.
#
# Each extension is a measured failure in a domain where the loss is fatal:
#
#   digits inside runs   「国道4号」 split into 国道+号 and dropped the 4;
#                        「第3条」 became 第+条 and 「1日2錠」 became 日+錠.
#                        A legal system that cannot say WHICH article, or a
#                        medical one that loses the dose, is not weaker —
#                        it is unusable, because the number was the claim.
#   trailing okurigana   「土砂崩れ」→ 土砂崩, 「通行止め」→ 通行止. The single
#                        trailing kana from a closed set is taken only when
#                        what follows is a particle, punctuation, or the end,
#                        so inflections (崩れて…) still stop at the stem.
#   conjunction heads    Legal and administrative Japanese joins nouns with
#                        又は・若しくは・及び・並びに, and the ideograph run
#                        swallowed the head: 「消防長又は消防署長」 became
#                        消防長又 + 消防署長, so the first party to a statute
#                        was stored under a word that does not exist. Found
#                        blind on 災害対策基本法 and 消防法 — 334,330 characters
#                        where every provision names two or three parties this
#                        way. The head is only released when its own particle
#                        follows (又は, 若しくは, 及び, 並びに), so 及第 and 並木
#                        keep theirs.
#   kanji then katakana  「水洗トイレ」 and 「仮設トイレ」 are single nouns, and
#                        splitting at the script change filed both under
#                        トイレ. Measured on two revisions of 内閣府's toilet
#                        guidance: 「汲み取り式のトイレが多数使用不可」 and
#                        「水洗トイレが使用可能になった」 became one topic
#                        holding both poles — a manufactured contradiction
#                        out of a document distinguishing two kinds of
#                        toilet, in the same paragraph, on purpose. Joining
#                        removed it and changed nothing else across five
#                        corpora. The join is one-way: katakana followed by
#                        kanji stays separate, because that boundary is where
#                        a loanword ends and the next word begins.
#
# い/な stay unconditional as before (adjective endings); the new set is
# conditional to avoid swallowing conjugation.
#
# The katakana class is spelled out rather than written as the block range
# ゠-ヿ because two characters in that block are punctuation, not letters:
# ・ (U+30FB) and ゠ (U+30A0). Taking the block wholesale made ・ a content
# run of its own, and 内閣府's damage reports bullet every line with it — so
# ・ became a CORE, and 「・今後、…復旧を進める」 and 「…断水あり・漏水あり」 were
# filed as claims about the same subject. That was the only detection the
# four-revision corpus produced, and it was false. ー (U+30FC) is a letter
# and stays: 「データ」「ラーメン」 need it.
#: Latin is a content run in Japanese prose, and leaving it out silently
#: removed a whole domain. 「実装言語はTypeScriptを用いる」 came back as
#: ['実装言語', '用い'] — the term the sentence is about was invisible — and
#: 「認証はAPIキーを用いる」 as ['認証', 'キー'], because only the katakana
#: tail matched. Every downstream layer inherited it: the store never linked
#: 実装言語 to TypeScript, so sibling inference, covenant checking and
#: attestation all worked on Japanese law and on nothing with a latin name.
#:
#: The latin branch is FIRST so a mixed token stays whole: APIキー matches
#: from the A, where the katakana branch would have taken キー alone. The
#: trailing class carries version and package punctuation — C++, .NET, JWT,
#: node-fetch — because a rule about a tool names the tool exactly.
_JA_RUN = re.compile(
    r"[A-Za-zＡ-Ｚａ-ｚ][A-Za-z0-9Ａ-Ｚａ-ｚ０-９.+#_-]*[ァ-ヺヽヾヿー]*"
    r"|[ァ-ヺヽヾヿー]+"
    r"|(?:(?![又若及並](?:は|しく|び))[㐀-䶿一-鿿0-9０-９])+[ァ-ヺヽヾヿー]*"
    r"(?:[いな]|[れめきちりつけ](?=[はがをにでとのへもや、。！？\s]|$))?"
)
_ALL_DIGITS = re.compile(r"^[0-9０-９]+$")
#: Words that are grammatically nouns and informationally nothing — formal
#: nouns, pronouns, and temporal/positional deictics. Excluded because a
#: content run becomes a CORE, and a core is meant to be a topic.
#:
#: Measured, not assembled from a grammar book. Ingesting 2,491 documents
#: from this author's repositories put 次(667), 彼(552), 現在(325), 今(235)
#: and 私(220) among the twenty most-discussed "topics" in the corpus. None
#: of them is a topic; they are what sentences are built out of.
#:
#: Kept to words that are near-always function-like. 中 and 上 are omitted on
#: purpose — 中 is genuinely ambiguous (「中止」の中 vs 「作業中」) and dropping a
#: real topic is the more expensive error for an index whose purpose is to
#: show what a body of work is about.
# Stopwords now ship as data (lang_data/ja_grammar.json) so an expert
# can extend them with an overlay instead of editing source. The
# rationale for each group lives with the data's git history.
from .ja_grammar import STOPWORDS as _JA_STOP
_JA_QUESTION = ("何", "誰", "どこ", "いつ", "なぜ", "どう", "ですか", "とは")


#: A date or a clock time. Excluded from cores for the reason the stopword
#: list exists — a core is meant to be a topic, and 「７月29日」 is not one.
#: Measured: 「７月29日（水）に開設した熊本刑務所の避難所につき、８月３日（月）を
#: もって閉鎖」 cored under ７月29日, so the shelter that opened and closed had
#: no topic to be filed under. Dates cannot be a word list, so this is a
#: shape: digits FIRST, then a temporal kanji. 国道4号 and 第3条 carry their
#: digit inside the name and are untouched.
_JA_DATE = re.compile(r"[0-9０-９]+(?:[年月日時分秒][0-9０-９]*)+$")

#: A date the layout has broken apart. PDF extraction spaces the digits from
#: their unit — 「７月 30 日」 — so the run scanner sees 月 and 日 as separate
#: single-character runs and only 日 survives, becoming the CORE. 内閣府's
#: ferry table then filed 7/29 and 7/30 under one topic called 日 and reported
#: them as a contradiction: two different days, read as one thing disagreeing
#: with itself. Whether the space is there is a fact about the PDF, not about
#: the sentence, so the run is judged on its surroundings.
_JA_DATE_PIECE = re.compile(r"[年月日時分秒]")
_JA_DATE_BEFORE = re.compile(r"[0-9０-９][\s ]*$")


#: （水）（月）— a single character alone inside brackets is a label: the
#: weekday beside a date, or an item marker. Read as content, 水 and 月 are
#: two perfectly ordinary nouns (water, moon), and in
#: 「７月29日（水）に開設した…８月３日（月）をもって閉鎖」 they were chosen as the
#: subjects of 開設 and 閉鎖 — Wednesday opened the shelter and Monday closed
#: it. Filtered here rather than in one caller, because a label is not
#: content for any purpose.
_JA_BRACKETS = ("（）", "()", "〔〕", "[]", "【】")


#: A compound particle wraps one kanji in kana — に対して、に関する、に基づく、
#: に際して、に応じて、に沿って、に向けて、に係る. The kanji is the middle of a
#: grammatical unit, not a noun, but a script-run scanner sees an isolated
#: ideograph and hands it back as content. 対 was then chosen as the SUBJECT
#: of a fire-code provision. Matched by shape rather than by list, because
#: the shape is what makes it a particle.
_JA_COMPOUND_PARTICLE = re.compile(r"^[にへを]$")
_JA_PARTICLE_TAIL = re.compile(r"^(?:し|す|する|して|づ|じ|っ|わ|い|り)")


def _inside_compound_particle(text: str, start: int, end: int) -> bool:
    if end - start != 1 or start < 1:
        return False
    if not _JA_COMPOUND_PARTICLE.match(text[start - 1]):
        return False
    return bool(_JA_PARTICLE_TAIL.match(text[end:end + 2]))


def _split_date_piece(text: str, run: str, start: int) -> bool:
    """One temporal character with a digit in front of it, across a space."""
    if len(run) != 1 or not _JA_DATE_PIECE.match(run):
        return False
    return bool(_JA_DATE_BEFORE.search(text[:start]))


def _bracketed_label(text: str, start: int, end: int) -> bool:
    if end - start != 1 or start < 1 or end >= len(text):
        return False
    return text[start - 1] + text[end] in _JA_BRACKETS


#: The provenance suffix `document_ingest` appends. Its own words are not
#: content, and once latin became a content run they started arriving as
#: facets — every ingested Japanese sentence gained `by` and `reported`, plus
#: whatever latin the filename held. Excluded by SPAN rather than by a word
#: list, so a source called `policy.docx` does not contribute `docx` either.
#: The citation suffix `ingest_documents` appends to every sentence. One
#: definition, because both decomposers have to agree on where the claim
#: ends — they did not, and only the Japanese one skipped it. The English
#: path read the label as content, so `en／99-year lease.txt` became the
#: facets `en` and `txt`: 6,608 of 138,797 facets on the English sovereign,
#: touching 43.5% of its cores, until `strip_attribution` was applied there
#: too.
#: Greedy, and anchored to the end, because the suffix is APPENDED and the
#: label may itself contain brackets. `[^)]*\)` stopped at the first bracket
#: of `en／Burden of proof (law).txt`, leaving `.txt)` in the sentence — which
#: is where 545 of the 566 surviving `txt` facets came from, i.e. every
#: Wikipedia disambiguation title in the corpus.
ATTRIBUTION = re.compile(r"\((?:reported|said) by .*\)\s*$")
_JA_ATTRIBUTION = ATTRIBUTION


def strip_attribution(text: str) -> str:
    """The claim without its citation suffix.

    Structure is read from this; provenance keeps the full string. Splitting
    the two is what lets a citation be stored without spending an arm's face
    on it.
    """
    return ATTRIBUTION.sub("", text or "").strip()


def ja_content_runs(text: str) -> List[str]:
    text = text or ""
    skip = [(m.start(), m.end()) for m in _JA_ATTRIBUTION.finditer(text)]
    out: List[str] = []
    for m in _JA_RUN.finditer(text):
        if any(a <= m.start() < b for a, b in skip):
            continue
        r = m.group(0)
        if (r in _JA_STOP or _ALL_DIGITS.match(r) or _JA_DATE.match(r)
                or _bracketed_label(text, m.start(), m.end())
                or _inside_compound_particle(text, m.start(), m.end())
                or _split_date_piece(text, r, m.start())):
            continue
        out.append(r)
    return out
