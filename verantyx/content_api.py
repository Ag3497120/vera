"""Round5-C adapter: ContentEngine.ask(brief, *, materials=()) -> JSON dict.

Integration contract (v1, provisional C0/C1):

* one.py may construct ContentEngine(material_source=reader) once and route
  explicit content requests to ask. The duck-typed local reader implements
  candidates(family, text, limit=64) -> {verdict, records, reason, trace} for
  narrative/paraphrase_entail. No import of its module is needed here.
* CREATED is licensed fiction, ANSWER is fully evidenced explanation. Typed
  UNKNOWN_CONTENT_* / CONTENT_* refuses the requested composition. A failed
  C result must not be overwritten by a legacy stored-answer fallback.
* Inputs are raw brief plus normal materials, never a gold ledger/plan. P/G/V
  diagnostic functions live in the separate modules. Runtime uses local
  Frame/grammar/rules only: no model, model training, network or execution.
* Source values or mappings {source/id,text,family,purpose,independent} can be
  supplied directly. purpose defaults to expression. Only explicitly marked
  non-narrative/non-paraphrase evidence can support an actual-world clause.
  Parsed expression events may enter a fiction plan only when the raw brief
  explicitly grants event and ordering choices; they remain nonfactual.
  Reusing a same-named participant across independent sources also requires
  AUTHOR_CHOICE(identity_recast), written as `別素材の同名要素は新しい創作内の要素として結び直してよい`,
  which binds a new fiction role rather than asserting that the source entities are identical.
* Retrieved records retain family,row_id,source,sha,payload,role,verified in
  material_records. Their purpose is always expression and verified stays
  False. Distinct sovereign traces are retained; scores never vote here.

This is an integration patch, not a claim that the preregistered C48/R/P/G/V/E
adoption or one.Vera evaluation has passed. A narrower morphology step counter
than the draft preregistration is declared in Budget; parent must reconcile
that contract before an adoption run. Literary quality, metaphor, humour,
haiku, long-distance anaphora and general commonsense are not yet evaluated.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import re
import time

from .content_ir import Budget, ContentError, Source, digest
from .content_planner import build_plan
from .content_reader import (is_event_set_request_attempt, outside_quotes,
                             read_brief_with_context)
from .content_realizer import realize_plan
from .content_verify import verify_content


def _outside_quotes(text: str) -> str:
    return outside_quotes(text)


def is_content_request(text: str) -> bool:
    """Router hint only; does not certify that a request can be fulfilled."""
    if is_event_set_request_attempt(text):
        return True
    text = _outside_quotes(text)
    if re.search(r"資料(?:に基づいて|から|に関する(?:(?:全|すべての)?イベントを)|の内容を).*?(?:説明|解説|まとめ|要約)", text):
        return True
    return bool(re.search(r"(?:物語|お話|ストーリー|俳句|詩|比喩|冗談).*(?:書いて|作って|作成|創作|生成|書く|作る)|創作", text))


def _as_source(value, index: int) -> Source:
    if isinstance(value, Source):
        source = value
    elif isinstance(value, dict) and isinstance(value.get("text"), str):
        source = Source(str(value.get("source") or value.get("id") or f"material:{index}"), value["text"],
                        str(value.get("family") or "provided"), str(value.get("purpose") or "expression"),
                        str(value.get("independent") or value.get("source") or ""))
    else:
        raise ContentError("UNKNOWN_CONTENT_MATERIAL", "materials require Source or a text/source mapping")
    if source.purpose not in ("expression", "evidence"):
        raise ContentError("UNKNOWN_CONTENT_MATERIAL", "external material cannot become instruction")
    if source.family in ("narrative", "paraphrase_entail"):
        source = replace(source, purpose="expression")
    return source


def _record_text(record: dict, budget: Budget) -> str:
    payload = record.get("payload")
    if not isinstance(payload, dict):
        raise ContentError("UNKNOWN_CONTENT_MATERIAL", "material payload must be a mapping")
    if record["family"] == "narrative":
        sentences = payload.get("sentences") or ()
        if not isinstance(sentences, (list, tuple)):
            raise ContentError("UNKNOWN_CONTENT_MATERIAL", "narrative sentences must be a sequence")
        values = []
        for item in sentences:
            budget.tick()
            values.append(item.get("text", "") if isinstance(item, dict) else item)
        if not values:
            values = payload.get("lines") or ()
    else:
        # who_did_what.question can be generic; its answer is not its premise.
        values = [payload.get("s1", ""), payload.get("s2", ""), payload.get("sentence", "")]
    if not isinstance(values, (list, tuple)):
        raise ContentError("UNKNOWN_CONTENT_MATERIAL", "material text fields must be strings")
    texts = []
    for value in values:
        budget.tick()
        if not isinstance(value, str):
            raise ContentError("UNKNOWN_CONTENT_MATERIAL", "material text fields must be strings")
        if value:
            texts.append(value)
    return "\n".join(texts)


class ContentEngine:
    contract = "vera.content.v1"

    def __init__(self, material_source=None, *, material_limit: int = 8):
        if not isinstance(material_limit, int) or not 1 <= material_limit <= 64:
            raise ValueError("material_limit must be in 1..64")
        self.material_source, self.material_limit = material_source, material_limit

    def _retrieve(self, brief: str, budget: Budget):
        records, sources, traces = [], [], []
        if self.material_source is None:
            return sources, records, traces
        for family in ("narrative", "paraphrase_entail"):
            budget.tick()
            result = self.material_source.candidates(family, brief, limit=self.material_limit)
            if not isinstance(result, dict) or not isinstance(result.get("records", []), (list, tuple)):
                raise ContentError("UNKNOWN_CONTENT_MATERIAL", "material reader violated its boundary")
            own = result.get("records", [])
            if len(own) > self.material_limit:
                raise ContentError("UNKNOWN_CONTENT_BUDGET", "reader returned more records than requested", counter="material_records")
            traces.append({"family": family, "verdict": result.get("verdict"),
                           "reason": result.get("reason"), "trace": result.get("trace"),
                           "role": "expression_only"})
            for record in own:
                budget.tick("candidates")
                budget.tick()
                if not isinstance(record, dict) or record.get("family") != family or not all(
                    key in record for key in ("row_id", "source", "sha", "payload", "role", "verified")
                ):
                    raise ContentError("UNKNOWN_CONTENT_MATERIAL", "material record lost identity or sovereign")
                # Neither the boundary's flag nor source counts prove facts.
                preserved = {key: record[key] for key in ("family", "row_id", "source", "sha", "payload", "role", "verified")}
                if preserved["verified"] is not False:
                    raise ContentError("UNKNOWN_CONTENT_MATERIAL", "material record must remain verified=False")
                text = _record_text(record, budget)
                source_id = family + ":" + digest((record["row_id"], record["source"], record["sha"]))[:24]
                sources.append(Source(source_id, text, family, "expression", str(record["source"])))
                records.append(preserved)
        return sources, records, traces

    def ask(self, brief: str, *, materials=()) -> dict:
        started, budget = time.perf_counter(), Budget()
        ledger = plan = realization = None
        request_goal_projection = source_event_binding = None
        event_set_attempt = False
        records, traces = [], []
        result = {"contract": self.contract, "family": "content", "path": "constraint_plan_realize_verify",
                  "created": False, "material_records": records, "material_trace": traces}
        try:
            if not isinstance(brief, str):
                raise ContentError("UNKNOWN_CONTENT_UNREAD", "brief must be a string")
            event_set_attempt = is_event_set_request_attempt(brief)
            budget.size("brief_chars", len(brief))
            if re.search(r"俳句|五七五|五・七・五", _outside_quotes(brief)):
                raise ContentError("UNKNOWN_CONTENT_FORM", "haiku joint meaning/mora search is not implemented in C1")
            if not isinstance(materials, (tuple, list)):
                raise ContentError("UNKNOWN_CONTENT_MATERIAL", "materials must be a finite sequence")
            direct, direct_chars = [], 0
            for index, value in enumerate(materials):
                budget.tick("candidates")
                budget.tick()
                source = _as_source(value, index)
                direct.append(source)
                direct_chars += len(source.text)
                budget.size("material_chars", direct_chars)
            if event_set_attempt:
                # This Goal is source-bound from caller-supplied evidence. The
                # expression retriever has no authority in this path.
                retrieved, records, traces = [], [], []
            else:
                retrieved, records, traces = self._retrieve(brief, budget)
            all_sources = tuple(sorted(direct + retrieved, key=lambda s: (s.id, s.sha256)))
            budget.size("material_chars", sum(len(s.text) for s in all_sources))
            if len({s.id for s in all_sources}) != len(all_sources) or any(s.id == "brief" for s in all_sources):
                raise ContentError("UNKNOWN_CONTENT_MATERIAL", "material source IDs must be distinct from brief")
            ledger, request_goal_projection, source_event_binding = read_brief_with_context(
                brief, all_sources, budget)
            plan = build_plan(ledger, budget)
            realization = realize_plan(plan, expression_materials=all_sources, budget=budget)
            verification = verify_content(ledger, plan, realization, budget)
            created = ledger.mode == "fiction"
            result.update(kind="created" if created else "answer", verdict="CREATED" if created else "ANSWER",
                          created=created, text=realization.text, verification=verification,
                          generation="semantic_plan_composition", novelty_verified=False,
                          scope="finite_C1", quality="unassessed")
            if event_set_attempt:
                result.update(
                    status="PARTIAL_COMPLETENESS_UNVERIFIED",
                    response_notice="本文は検証済みですが、依頼された出典イベント全体の網羅性は未確認です。",
                    raw_goal_projection=request_goal_projection,
                    source_event_binding=source_event_binding,
                    goal_projection_rederived=True,
                    source_event_binding_rederived=True,
                    represented_projection_verified=verification.get("passed") is True,
                    source_truth_status="UNCLASSIFIED",
                    source_identity_status="source_id_and_hash_only",
                    independent_source_count=None,
                    semantic_event_set_complete=None,
                    goal_satisfied=None,
                    success_count_eligible=False,
                    event_set_status="PARTIAL",
                )
        except ContentError as error:
            conflict = "CONFLICT" in error.verdict
            violation = "VIOLATION" in error.verdict
            result.update(kind="conflict" if conflict else "violation" if violation else "unknown",
                          verdict=error.verdict, text="この条件では構成を確定できません。",
                          reason=error.reason, details=error.details,
                          verification={"passed": False, "reason": error.reason, "details": error.details})
            if event_set_attempt or error.details.get("request_goal_projection") is not None:
                result.update(
                    status="HOLD",
                    response_notice="依頼全体の充足を確認できないため、結果を確定しません。",
                    raw_goal_projection=(request_goal_projection
                                         or error.details.get("request_goal_projection")),
                    source_event_binding=(source_event_binding
                                          or error.details.get("source_event_binding")),
                    goal_projection_rederived=False,
                    source_event_binding_rederived=False,
                    represented_projection_verified=False,
                    source_truth_status="UNCLASSIFIED",
                    source_identity_status="unverified",
                    independent_source_count=None,
                    semantic_event_set_complete=None,
                    goal_satisfied=None,
                    success_count_eligible=False,
                    event_set_status="HOLD",
                )
        result.update(material_records=records, material_trace=traces, budget=budget.as_dict(),
                      ms=round((time.perf_counter() - started) * 1000, 3))
        # Diagnostic contracts cannot be used as public success flags.
        if ledger is not None:
            result["ledger"] = asdict(ledger)
            result["ledger_hash"] = ledger.hash
        if plan is not None:
            result["plan"] = asdict(plan)
            result["plan_hash"] = plan.hash
        if realization is not None and result["verification"]["passed"]:
            result["realization"] = asdict(realization)
        result["sources"] = [asdict(s) for s in ledger.materials] if ledger else []
        result["evidence"] = [p["occurrence_evidence"] for p in result.get("verification", {}).get("provenance", [])]
        result["trace"] = [{"part": "content_reader", "ledger_hash": result.get("ledger_hash")},
                           {"part": "content_planner", "plan_hash": result.get("plan_hash")},
                           {"part": "content_realizer", "surfaces": budget.counts.get("surfaces", 0)},
                           {"part": "content_verify", "passed": result["verification"]["passed"]}]
        return result


def answer(brief: str, *, materials=(), material_source=None) -> dict:
    return ContentEngine(material_source).ask(brief, materials=materials)
