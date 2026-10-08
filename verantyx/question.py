"""Read a question once and hand typed, attributed readings to answerers.

The reader does not change the surface text. In particular, typo candidates
and named senses are proposals, not replacements or document evidence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, Literal, Mapping, Optional, TypeVar

from . import intent, intent_frames, polarity, sense_split, stage_split, typo_recovery
from . import meaning_assets
from .answer_slots import SlotFrame, read_slot

Kind = Literal[
    "fact", "multi_hop", "comparison", "condition", "exception", "count",
    "negation", "why", "summary", "definition", "instruction", "chat",
]
AskedSlot = Literal["who", "what", "when", "where", "how many", "how much", "why", "whether"]
T = TypeVar("T")


@dataclass(frozen=True)
class Sourced(Generic[T]):
    value: T
    part: str


@dataclass(frozen=True)
class Stage:
    condition: str
    head: str
    fragment: str
    span: tuple[int, int]


@dataclass(frozen=True)
class StageReading:
    verdict: str
    stages: tuple[Stage, ...] = ()
    chain: str = ""
    cuts: tuple[int, ...] = ()
    stage_terms: tuple[tuple[str, ...], ...] = ()
    tokenizer: str = ""
    text: str = ""
    reason: str = ""


@dataclass(frozen=True)
class TypoCandidate:
    term: str
    word: str
    overlap_units: int
    edit_distance: int


@dataclass(frozen=True)
class TypoCheck:
    term: str
    verdict: str


@dataclass(frozen=True)
class TypoReading:
    verdict: str
    checks: tuple[TypoCheck, ...] = ()
    candidates: tuple[TypoCandidate, ...] = ()
    missing_assets: tuple[str, ...] = ()


@dataclass(frozen=True)
class SenseReading:
    verdict: str
    surface: str = ""
    core: Optional[str] = None
    lead_tokens: tuple[str, ...] = ()
    alternatives: tuple[str, ...] = ()
    missing_assets: tuple[str, ...] = ()


@dataclass(frozen=True)
class IntentReading:
    verdict: str
    op: Optional[str | tuple[str, ...]] = None
    args: Optional[Mapping[str, str] | tuple[Mapping[str, str], ...]] = None


@dataclass(frozen=True)
class SpeechAct:
    act: str
    reason: str


@dataclass(frozen=True)
class Query:
    surface: Sourced[str]
    kind: Sourced[Kind]
    asked_slot: Sourced[Optional[AskedSlot]]
    stages: Sourced[StageReading]
    typo: Sourced[TypoReading]
    sense: Sourced[SenseReading]
    polarity: Sourced[polarity.PolarityReading]
    intent_op: Sourced[IntentReading]
    speech_act: Sourced[SpeechAct]
    requested_speech_act: Sourced[str]
    case_frame: Sourced[SlotFrame] | None = None
    semantic_plan: Sourced[object] | None = None


def read_semantic(text: str) -> Sourced:
    """Opt-in source-bound plan, without passing through legacy answer slots."""
    from .semantic_reader import read_request
    return Sourced(read_request(text), 'semantic_reader.read_request')


_JA_TERM = re.compile(r"[㐀-䶿一-鿿々ァ-ヺー]{2,5}")
_EN_TERM = re.compile(r"[A-Za-z]{3,12}")
_SOCIAL = re.compile(r"^(?:こんにちは|こんばんは|おはよう|はじめまして|やあ|どうも|さようなら|またね|ありがとう|ごめん|すみません)[。！!？?]*$")
_GENERATION = re.compile(
    r"(?:説明|解説|書き換え|言い換え|要約|まとめ|描写|表現|提案|依頼)して(?:ください|下さい)"
    r"|(?:俳句|詩|物語|なぞなぞ|ダジャレ|キャッチコピー|メッセージ|一文|[0-9０-９一二三四五六七八九十]+文)"
    r".{0,35}(?:作って|書いて|考えて|言って)(?:ください|下さい)"
    r"|(?:丁寧|ていねい|短い一言|問い合わせ文).{0,55}(?:依頼して|尋ねて|書いて)(?:ください|下さい)"
    r"|(?:作って|書いて|考えて|言って)(?:ください|下さい)"
)
_ANSWER_REQUEST = re.compile(r"(?:答えて|教えて|挙げて|示して|述べて|列挙して)(?:ください|下さい)")
_ACTION = re.compile(
    r"(?:開いて|開けて|閉じて|閉めて|起動して|検索して|探して|調べて|覚えて|記録して|"
    r"忘れて|削除して|消して|実行して|止めて|停止して|送って|送信して|"
    r"コミットして|プッシュして|保存して|コピーして|移動して|作って|書いて|"
    r"インストールして|表示して|変更して|更新して|追加して|選択して|確認して)"
    r"(?:ください|下さい|くれ|ほしい|欲しい)?[。！!？?]*$"
)
_WH = re.compile(r"誰|だれ|何|なに|どこ|いつ|なぜ|どうして|いくら|どれ|どのよう|どんな|どちら|\b(?:who|what|when|where|why|how|which)\b", re.I)


def _is_generation(text: str) -> bool:
    code_request = bool(re.search(r"コード|関数|プログラム|Python|JavaScript|SQL|シェル", text, re.I) and
                        re.search(r"書いて|作って|生成して|実装して|修正して|直して", text))
    if not _GENERATION.search(text) and not code_request:
        return False
    # Creating or writing an actual file is an operation. A requested poem,
    # explanation, rewrite, or draft is content to return to the user.
    if re.search(r"(?:ファイル|フォルダ|ディレクトリ)を作って(?:ください|下さい)", text):
        return False
    if re.search(r"ファイルに.{0,30}書いて(?:ください|下さい)?", text):
        return False
    return True


def is_content_request(text: str) -> bool:
    """True when a request asks for answer text rather than an external act."""
    return _is_generation(text) or bool(_ANSWER_REQUEST.search(text))


def _genuine_instruction(text: str, act: str) -> bool:
    if act not in ("request", "command") or _is_generation(text):
        return False
    if _WH.search(text) or re.search(r"か[。？?]*$|[？?]$", text):
        return False
    return bool(_ACTION.search(text))


def _kind(text: str, act: str, staged: StageReading) -> Kind:
    q = text.strip()
    if _SOCIAL.match(q) or act in ("thanks", "apology", "refusal"):
        return "chat"
    if _genuine_instruction(q, act):
        return "instruction"
    if re.search(r"(?:とは|って何|どういう意味|の意味|定義)", q):
        return "definition"
    if re.search(r"(?:要約|まとめて|要点|概要)", q):
        return "summary"
    if _is_generation(q):
        if re.search(r"(?:なぜ|どうして|理由|何のため)", q):
            return "why"
        return "chat"
    if re.search(r"(?:なぜ|どうして|理由は|理由を|何のため)", q):
        return "why"
    if re.search(r"(?:比べ|比較|どう違|どう異な|違い|差が|差は|より何|どちらが|どちらの|と.{0,40}それぞれ何)", q):
        return "comparison"
    if re.search(r"(?:と.{0,25}では.{0,35}どのような|と.{0,25}では.{0,35}それぞれ|"
                 r"[^。]{2,15}と[^。]{2,15}ではどちら)", q):
        return "comparison"
    if re.search(r"(?:例外|対象外|適用されません|適用されなかった|"
                 r"書かなかった|含めない|かかりません|認められる|"
                 r"(?:どのような|どんな)とき.{0,15}かから)", q):
        return "exception"
    if re.search(r"(?:何(?:人|名|回|台|本|個|件|組|隻|種類|品目|脚|単位|冊|匹|点|枚|日(?!前))|いくつ|合計何|最大何台|上限を何単位)", q):
        return "count"
    if staged.verdict == "STAGED" and len(staged.stages) > 1:
        return "multi_hop"
    if re.search(r"(?:また|それぞれ|誰が.{0,30}誰が|何を.{0,60}誰に|何を.{0,60}何を|"
                 r"合わせると|反映して|その場合でも|実際の|"
                 r"その後|何をするか|となり、.{0,40}間)", q):
        return "multi_hop"
    if q.count("か。") + q.count("か？") + q.count("か?") >= 2:
        return "multi_hop"
    if re.search(r"(?:しなかった|されません|できません|必要はない|必要がない|できない|"
                 r"していない|しない|いなかった|認められません)", q):
        return "negation"
    if re.search(r"(?:場合|なら|たとき|どんなとき|どのようなとき|れば|たら|どの条件)", q):
        return "condition"
    return "fact"


def _slot(text: str, kind: Kind) -> Optional[AskedSlot]:
    if kind in ("chat", "instruction"):
        return None
    if kind == "why" or re.search(r"なぜ|どうして|何のため|\bwhy\b", text, re.I):
        return "why"
    if re.search(r"いくら|何円|何リットル|何キログラム|金額|\bhow much\b", text, re.I):
        return "how much"
    if kind == "count" or re.search(r"何(?:人|名|回|台|本|個|件|組|隻|種類|品目|脚|単位|冊|匹|点|枚|日(?!前))|いくつ|\bhow many\b", text, re.I):
        return "how many"
    if re.search(r"誰|だれ|\bwho\b", text, re.I):
        return "who"
    if re.search(r"(?<!な)いつ|何時|何日|何年|何曜|何営業日前|\bwhen\b", text, re.I):
        return "when"
    if re.search(r"どこ|どちらへ|(?:場所|所在地|住所)(?:を|は).{0,10}(?:教え|何|示)|\bwhere\b", text, re.I):
        return "where"
    if re.search(r"何|なに|どれ|どの|どんな|\bwhat\b", text, re.I):
        return "what"
    if re.search(r"(?:か|でしょう)[。？?]*$|\b(?:is|are|can|does|do|did)\b", text, re.I):
        return "whether"
    return "what"


def _requested_speech_act(text: str) -> str:
    """Classify a requested utterance by its act, never by its topic."""
    if re.search(r"お礼|感謝|ありがとう", text):
        return "thanks"
    if re.search(r"謝罪|お詫び|謝る", text):
        return "apology"
    if re.search(r"相談|助言を求め", text):
        return "consult"
    if re.search(r"感想|印象|期待", text):
        return "impression"
    if re.search(r"変更|変わった|変わる|知らせる|報告", text) and re.search(
            r"メッセージ|文|伝える|知らせる|報告", text):
        return "report-change"
    if re.search(r"依頼|お願い|頼む", text):
        return "request"
    return "none"


def _stage_reading(raw: Mapping[str, object]) -> StageReading:
    stages = tuple(Stage(str(s["condition"]), str(s["head"]), str(s["fragment"]),
                         (int(s["span"][0]), int(s["span"][1])))
                   for s in raw.get("stages", ()) if isinstance(s, dict))
    return StageReading(
        verdict=str(raw.get("verdict", "UNKNOWN_UNSEGMENTED")),
        stages=stages,
        chain=str(raw.get("chain", "")),
        cuts=tuple(int(n) for n in raw.get("cuts", ())),
        stage_terms=tuple(tuple(str(term) for term in terms)
                          for terms in raw.get("stage_terms", ())),
        tokenizer=str(raw.get("tokenizer", "")),
        text=str(raw.get("text", "")),
        reason=str(raw.get("reason", "")),
    )


def _terms(text: str) -> tuple[str, ...]:
    rx = _JA_TERM if re.search(r"[぀-ヿ一-鿿]", text) else _EN_TERM
    return tuple(dict.fromkeys(m.group(0) for m in rx.finditer(text)))


def _typo_assets() -> tuple[object, object] | None:
    if not (Path(meaning_assets.BUILD) / "writer.json").exists():
        return None
    return meaning_assets.lattice(), meaning_assets.vocab()


def _typo_reading(text: str) -> TypoReading:
    assets = _typo_assets()
    if assets is None:
        return TypoReading("LACK_OF_ASSET", missing_assets=("writer.json",))
    lattice, vocab = assets
    checks: list[TypoCheck] = []
    candidates: list[TypoCandidate] = []
    for term in _terms(text):
        raw = typo_recovery.recover(term, lattice=lattice, vocab=vocab)
        checks.append(TypoCheck(term, str(raw["verdict"])))
        for item in raw.get("candidates", ()):
            candidates.append(TypoCandidate(term, str(item["word"]),
                                            int(item["overlap_units"]), int(item["edit_distance"])))
    verdict = ("TYPO_CANDIDATE" if candidates else
               "IN_VOCABULARY" if checks and all(c.verdict == "IN_VOCABULARY" for c in checks)
               else "UNKNOWN_NO_CANDIDATE")
    return TypoReading(verdict, tuple(checks), tuple(candidates))


def _sense_assets() -> tuple[Mapping, Mapping] | None:
    build = Path(meaning_assets.BUILD)
    if not ((build / "meaning_index.db").exists() or
            ((build / "jawiki_senses.json").exists() and (build / "jawiki_aliases.json").exists())):
        return None
    return meaning_assets.senses(), meaning_assets.aliases()


def _missing_sense_assets() -> tuple[str, ...]:
    build = Path(meaning_assets.BUILD)
    if (build / "meaning_index.db").exists():
        return ()
    return tuple(name for name, path in (
        ("jawiki_senses", build / "jawiki_senses.json"),
        ("jawiki_aliases", build / "jawiki_aliases.json"),
    ) if not path.exists())


def _sense_reading(text: str) -> SenseReading:
    terms = _terms(text)
    surface = terms[0] if terms else ""
    assets = _sense_assets()
    if assets is None:
        return SenseReading("LACK_OF_ASSET", surface, missing_assets=_missing_sense_assets())
    senses, aliases = assets
    raw = sense_split.resolve(surface, terms[1:], senses=senses, aliases=aliases)
    others = raw.get("other_senses", raw.get("senses", ()))
    return SenseReading(
        verdict=str(raw["verdict"]), surface=surface, core=raw.get("core"),
        lead_tokens=tuple(str(x) for x in raw.get("lead_tokens", ())),
        alternatives=tuple(str(x["core"]) for x in others
                           if isinstance(x, dict) and x.get("core")),
    )


def read(question: str) -> Query:
    """Return a typed reading with the producing part on every field."""
    surface = (question or "").strip()
    staged = _stage_reading(stage_split.split(surface))
    act, reason = intent.act_by_form(surface)
    kind = _kind(surface, act, staged)
    if kind == "instruction":
        parsed = intent_frames.parse(surface)
        op = parsed.get("op")
        args = parsed.get("args")
        framed = IntentReading(str(parsed["verdict"]), tuple(op) if isinstance(op, list) else op,
                               tuple(args) if isinstance(args, list) else args)
    else:
        framed = IntentReading("NOT_APPLICABLE")
    typo = _typo_reading(surface)
    sense = _sense_reading(surface)
    return Query(
        surface=Sourced(surface, "question.read"),
        kind=Sourced(kind, "question.kind"),
        asked_slot=Sourced(_slot(surface, kind), "question.asked_slot"),
        stages=Sourced(staged, "stage_split.split"),
        typo=Sourced(typo, "question.assets" if typo.verdict == "LACK_OF_ASSET" else
                     "typo_recovery.recover" if typo.checks else "question.term_selection"),
        sense=Sourced(sense, "question.assets" if sense.verdict == "LACK_OF_ASSET" else "sense_split.resolve"),
        polarity=Sourced(polarity.observe_negation(surface), "polarity.observe_negation"),
        intent_op=Sourced(framed, "intent_frames.parse" if kind == "instruction" else "question.instruction_gate"),
        speech_act=Sourced(SpeechAct(act, reason), "intent.act_by_form"),
        requested_speech_act=Sourced(_requested_speech_act(surface), "question.requested_speech_act"),
        case_frame=Sourced(read_slot(surface, _slot(surface, kind) or "what"), "answer_slots.read_slot"),
    )
