"""One model-free entry for documents, the federation, and conversation.

The three evidence spaces stay separate.  A document answer must pass the
sentence/slot gate in :mod:`answer`; corpus and conversation proposals never
fill a missing document slot.  Trace entries describe calls or explicit
abstentions, rather than treating an imported module as a run stage.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import question


_REFUSAL_KINDS = {"unknown", "not_yet", "cannot", "unreadable"}
_REFUSAL_PREFIXES = ("UNKNOWN", "ABSTAIN", "AMBIGUOUS", "NOT_IN_DOCS",
                     "UNCONFIRMED", "TIED", "UNGROUNDED", "DOCUMENT_NOT_SPECIFIED")
_SECTION_REQUEST = re.compile(r"第[0-9０-９一二三四五六七八九十百]+[条項章節]|見出し|提出期限|必要書類|必須要件|項目一覧")


def _step(part: str, status: str, **details: Any) -> dict:
    return {"part": part, "status": status, **details}


def _reading_trace(reading: question.Query) -> list[dict]:
    """Expose the reader's actual typed handoffs, including absent assets."""
    typo = reading.typo.value
    sense = reading.sense.value
    op = reading.intent_op.value
    return [
        _step("question.read", "ran", kind=reading.kind.value,
              asked_slot=reading.asked_slot.value,
              case_frame=reading.case_frame.value.as_dict() if reading.case_frame else None),
        _step("stage_split.split", "ran", verdict=reading.stages.value.verdict),
        _step("typo_recovery.recover", "ran" if typo.checks else "abstained",
              verdict=typo.verdict),
        _step("meaning_assets.lattice", "abstained" if typo.missing_assets else "ran",
              reason=", ".join(typo.missing_assets)),
        _step("sense_split.resolve", "abstained" if sense.verdict == "LACK_OF_ASSET" else "ran",
              verdict=sense.verdict),
        _step("polarity.observe_negation", "ran", count=reading.polarity.value.count),
        _step("intent.act_by_form", "ran", act=reading.speech_act.value.act),
        _step("intent_frames.parse", "ran" if reading.kind.value == "instruction" else "abstained",
              verdict=op.verdict, reason="question is not an instruction" if reading.kind.value != "instruction" else ""),
        _step("arm_schema.classify_intent", "ran", arm=reading.requested_arm.value)
        if hasattr(reading, "requested_arm") else _arm_step(reading.surface.value),
    ]


def _arm_step(text: str) -> dict:
    from .arm_schema import classify_intent
    return _step("arm_schema.classify_intent", "ran", arm=classify_intent(text))


class Vera:
    """Load evidence once and answer through typed, source-bearing stages.

    ``bot`` and ``chat`` are accepted for the public compatibility adapters;
    ``general`` is the built legacy federation (or a CrossStore).  File loads
    use document_loaders.  A Library checkpoint and gap ledger are opt-in.
    """

    def __init__(self, *, bot: Any = None, chat: Any = None, general: Any = None,
                 library: Any = None, gap_path: str | Path | None = None,
                 engine_compat: bool = False, round3_root: str | Path | None = None,
                 mode: str = 'legacy', material_immutable: bool = False,
                 material_root: str | Path | None = None):
        if mode not in ('legacy', 'semantic', 'contract', 'content', 'round5'): raise ValueError('unknown Vera mode')
        if type(material_immutable) is not bool: raise ValueError('material_immutable must be a boolean')
        self.mode = mode
        self.material_immutable = material_immutable
        self.material_root = Path(material_root) if material_root is not None else None
        self._semantic_view = None
        self._semantic_retriever = None
        self._multigrain_constellation = None
        self._multigrain_generation = None
        self._multigrain_source_root = None
        self._multigrain_source_registry = None
        self._indexed_bot_generation = None
        self._material_source = None
        self._content_engine = None
        self.bot = bot
        self._chat = chat
        self.general = general
        self.library = library
        self.gap_path = Path(gap_path) if gap_path is not None else None
        self.engine_compat = engine_compat
        self.round3_root = Path(round3_root) if round3_root is not None else None
        self._round3_router: Any = None
        self.book: dict = {"documents": []}
        self.load_trace: list[dict] = []
        self.skipped: list[dict] = []
        if bot is not None:
            self._index_bot()
        elif mode == 'semantic':
            self._init_semantic_retriever()

    @classmethod
    def from_texts(cls, docs: Mapping[str, str], **kwargs: Any) -> "Vera":
        from .bot import Bot
        return cls(bot=Bot.from_texts(dict(docs)), **kwargs)

    @classmethod
    def from_dir(cls, directory: str | Path, **kwargs: Any) -> "Vera":
        vera = cls(**kwargs)
        vera.load_documents([directory])
        return vera

    def load_documents(self, paths: Iterable[str | Path]) -> dict:
        from .bot import Bot
        from .document_loaders import load_directory, load_paths

        files = [Path(p) for p in paths]
        loaded = []
        skipped = []
        for path in files:
            result = load_directory(str(path)) if path.is_dir() else load_paths([str(path)])
            loaded.extend(result["documents"])
            skipped.extend(result["skipped"])
        if self.bot is None:
            self.bot = Bot()
        for doc in loaded:
            self.bot.add(doc.source, doc.text)
        self.bot.build()
        self.skipped.extend(skipped)
        self._index_bot()
        self.load_trace.insert(0, _step("document_loaders.load_paths", "ran", loaded=len(loaded), skipped=skipped))
        return {"loaded": len(loaded), "skipped": skipped}

    def load_store(self, store: Any = None, *, library: str | Path | None = None) -> "Vera":
        """Accept a built federation/CrossStore or load the SQLite export."""
        if store is not None:
            if isinstance(store, (str, Path)):
                from .export_sqlite import vera as load_sqlite_vera
                self.general = load_sqlite_vera(Path(store))
            elif hasattr(store, "crosses"):
                from .vera import Vera as Federation
                self.general = Federation().add("ja", store)
            else:
                self.general = store
            self.load_trace.append(_step("vera.Vera.add", "ran", languages=sorted(self.general.stores)))
        if library is not None:
            from .library import Library
            self.library = Library.load(library)
            self.load_trace.append(_step("library.Library.load", "ran", checkpoint=str(library)))
        return self

    def _index_bot(self) -> None:
        """Build separate cross and verbatim indexes from injection-safe text."""
        if self.bot is None:
            return
        self._multigrain_constellation = None
        self._multigrain_generation = None
        self._semantic_view = None
        if self.mode in ('semantic', 'round5'): self._make_semantic_view()
        from .cross_store import CrossStore
        from .document_ingest import Document, ingest_documents
        from .document_structure import index

        docs = self.bot.base.docs
        safe_texts = getattr(self.bot, "safe_texts", {})
        self.book = {"documents": [index(safe_texts.get(name, d["text"]), name)
                                   for name, d in docs.items()]}
        self.doc_store = CrossStore()
        if docs:
            ingest_documents(self.doc_store, [Document(source=name, text=safe_texts.get(name, d["text"]))
                                              for name, d in docs.items()])
        self._multigrain_source_root = None
        self._multigrain_source_registry = None
        if self.mode == 'round5':
            originals = getattr(self.bot, "original_texts", {})
            navigation_root = getattr(getattr(self.bot, "base", None), "root", None)
            # A one-document Base intentionally has no hierarchy. Wrap its
            # already-indexed CrossStore in one source-ID leaf for navigation;
            # this does not build a second index or alter Base routing.
            if (navigation_root is None and type(originals) is dict and len(originals) == 1
                    and set(originals) == set(docs) and self.doc_store.crosses):
                from .hierarchy import Node
                source_id = next(iter(originals))
                navigation_root = Node(name=source_id, store=self.doc_store)
            self._multigrain_source_root = navigation_root
            from .multigrain_source_binding import capture_source_registry
            self._multigrain_source_registry = capture_source_registry(self.bot, navigation_root)
        self._indexed_bot_generation = getattr(self.bot, "_semantic_generation", 0)
        self.load_trace = [
            _step("document_ingest.ingest_documents", "ran" if docs else "abstained", documents=len(docs)),
            _step("document_structure.index", "ran" if docs else "abstained", documents=len(docs)),
            _step("frames.read_all", "ran" if self.bot.base.items else "abstained", documents=len(docs)),
            _step("verdict.read_records", "ran" if self.bot.base.items else "abstained",
                  documents=len(docs), exception_links=[]),
            _step("cross_store.CrossStore", "ran" if docs else "abstained", cores=len(self.doc_store.crosses)),
            _step("hierarchy.Node", "ran" if docs else "abstained", leaves=len(docs)),
            _step("sovereign.group_into_layers", "ran" if len(docs) > 1 else "abstained",
                  reason="single document" if len(docs) == 1 else ""),
            _step("hierarchy.federate", "ran" if len({d["sovereign"] for d in docs.values()}) > 1 else "abstained",
                  reason="one sovereign"),
            _step("conduct_tree.build", "ran" if self.bot.base.routing_root is not None else "abstained",
                  reason="one leaf has no descent" if len(docs) == 1 else ""),
            _step("surface.distinct_faces", "ran" if self.bot.base.routing_root is not None else "abstained",
                  reason="called by conduct_tree.build" if self.bot.base.routing_root is not None else "one leaf"),
        ]

    @property
    def chat_actor(self) -> Any:
        if self._chat is None:
            if self.bot is not None:
                self._chat = self.bot.chat
            else:
                from .chat import Chat
                self._chat = Chat([])
        return self._chat

    def _make_semantic_view(self) -> None:
        from .semantic_reader import document_view
        originals = getattr(self.bot, 'original_texts', {})
        if not originals:
            self._semantic_view = None
            return
        self._semantic_view = document_view(originals, sovereigns=getattr(self.bot, 'original_sovereigns', {}))
        self._semantic_generation = getattr(self.bot, '_semantic_generation', 0)

    def _routed_semantic_view(self, request, trace):
        """The semantic view, narrowed to the leaves the question can reach (stereo-cross tree), or the whole view."""
        from .semantic_route import LeafTree
        view = self._semantic_view
        tree = getattr(self, '_leaf_tree', None)
        if tree is None or tree.view is not view:
            tree = self._leaf_tree = LeafTree(view)
        routed, info = tree.restrict(request)
        info = dict(info); info['part'] = info.pop('part'); info.setdefault('status', 'ran')
        trace.append(info)
        return routed if routed is not None else view

    def _round5_multigrain_navigation(self, raw_question: str) -> dict | None:
        """Expose bounded structural candidates for a later source-span join.

        Candidate selection reuses FullConstellation/Ladder. The source leaf
        and Base surface route are not source identity or truth evidence. A
        separate binding step must rederive their document ID and raw span.
        """
        if self.bot is None or getattr(self, "doc_store", None) is None:
            return None
        if getattr(self.bot, "_semantic_generation", 0) != self._indexed_bot_generation:
            return None
        originals = getattr(self.bot, "original_texts", {}) or {}
        if len(originals) > 64 or len(self.doc_store.crosses) > 8000:
            return {
                "kind": "multigrain_candidates",
                "verdict": "UNKNOWN_RESOURCE_BOUND",
                "raw_question": raw_question,
                "selected_candidate": None,
                "candidates": [],
                "source_identity_status": "identity_unverified",
                "independent_source_count": None,
                "reason": "document navigation is capped at 64 original documents and 8000 CrossStore cores",
                "used_for_answer": False,
                "used_for_goal_realization": False,
                "authority": "navigation_only_unverified",
            }
        existing_tree = self._multigrain_source_root
        if existing_tree is None:
            return {
                "kind": "multigrain_candidates",
                "verdict": "UNKNOWN_NO_HIERARCHY",
                "raw_question": raw_question,
                "selected_candidate": None,
                "candidates": [],
                "source_identity_status": "identity_unverified",
                "independent_source_count": None,
                "reason": "no source-ID navigation leaves could be bound; no hierarchy was built",
                "used_for_answer": False,
                "used_for_goal_realization": False,
                "authority": "navigation_only_unverified",
            }
        if (self._multigrain_constellation is None
                or self._multigrain_generation != self._indexed_bot_generation):
            from .full_sovereign import FullConstellation
            from .resolution import DEFAULT_RUNGS

            settings = tuple(
                (name, {"rungs": ((name, size),), "grammar": "raw", "depth": 1})
                for name, size in DEFAULT_RUNGS
            )
            # No new hierarchy/placement is constructed here. Existing Base
            # leaves supply the path; FullConstellation builds its four
            # resolution views over the already-ingested CrossStore.
            constellation = FullConstellation().build(
                self.doc_store, settings=settings, with_tree=False,
            )
            if constellation.members:
                constellation.members[0].tree = existing_tree
            self._multigrain_constellation = constellation
            self._multigrain_generation = self._indexed_bot_generation

        from .request_goal_route import is_request_utterance
        if is_request_utterance(raw_question):
            from .multigrain_source_binding import retrieve_goal_candidate_navigation
            result = retrieve_goal_candidate_navigation(
                raw_question,
                self._multigrain_constellation,
                source_router=self.bot,
                limit=8,
            )
        else:
            from .multigrain_adapter import retrieve_multigrain_candidates
            result = retrieve_multigrain_candidates(
                raw_question,
                self._multigrain_constellation,
                source_router=self.bot,
                limit=8,
            )
        result["used_for_answer"] = False
        result["used_for_goal_realization"] = False
        result["authority"] = "source_location_hypothesis"
        result["independent_source_count"] = None
        result["truth_claim"] = False
        return result

    def _round5_bind_multigrain_source(self, raw_question: str,
                                       navigation: dict | None):
        """Rebind one adapter proposal to the exact original source and spans."""
        from .multigrain_source_binding import (
            SourceBindingResult, bind_multigrain_sources,
        )
        if (self.bot is None or type(navigation) is not dict
                or self._multigrain_source_root is None
                or self._multigrain_source_registry is None):
            return SourceBindingResult("HOLD", "navigation or source registry is unavailable")
        if (self._semantic_view is None
                or getattr(self, "_semantic_generation", None)
                != getattr(self.bot, "_semantic_generation", 0)):
            self._make_semantic_view()
        if self._semantic_view is None:
            return SourceBindingResult("HOLD", "original semantic View is unavailable")
        originals = getattr(self.bot, "original_texts", {})
        if type(originals) is not dict:
            return SourceBindingResult("HOLD", "Bot original-source mapping is invalid")
        return bind_multigrain_sources(
            raw_question, dict(originals), self.bot, self._multigrain_source_root,
            self._multigrain_source_registry, navigation, self._semantic_view,
        )

    def _init_semantic_retriever(self) -> None:
        if self._semantic_retriever is None:
            from .paths import corpus_root
            from .semantic_retrieve import Retriever
            self._semantic_retriever = Retriever(self.round3_root or corpus_root() / 'build/round3')

    def _ask_semantic(self, text: str, *, candidate_views=()) -> dict:
        from .semantic import answer, refusal
        from .semantic_ir import Limit, View, data
        request = question.read_semantic(text).value
        trace = [_step('question.read_semantic', 'ran', plans=len(request.plans),
                       obligations=len(request.obligations), unread=data(request.unread))]
        provenance = {}
        if self.bot is not None:
            if (self._semantic_view is None or self._semantic_generation != getattr(self.bot, '_semantic_generation', 0)):
                self._make_semantic_view()
            if self._semantic_view is None:
                result = refusal('UNKNOWN_SOURCE_ASSET', 'original document text is unavailable', phase='source', request=request)
            else:
                unread_all = self._semantic_view.unread
                # Serializing every unread span of the whole corpus on every ask made the answer time grow with the
                # corpus: keep the full list for small views, a bounded sample plus the count for large ones.
                trace.append(_step('semantic_reader.document_view', 'ran', clauses=len(self._semantic_view.clauses),
                                   source_unread=data(unread_all[:64]), source_unread_count=len(unread_all),
                                   source_unread_truncated=len(unread_all) > 64, ingest_ms=self._semantic_view.ingest_ms))
                if (type(candidate_views) in (tuple, list) and candidate_views
                        and all(type(view) is View for view in candidate_views)):
                    selected_trace = [*trace, _step(
                        'multigrain_source_binding', 'ran',
                        selected_source_views=len(candidate_views),
                        authority='original-source span location only',
                        full_original_view_required=True,
                    )]
                    # Candidate views can prioritize a bound source span, but
                    # the full original View remains in the same verification
                    # call so unseen contradictions/unread material still gate.
                    selected_result = answer(
                        request, [*candidate_views, self._semantic_view], trace=selected_trace,
                    )
                    if selected_result.get('verdict') == 'ANSWER':
                        result = selected_result
                        result['_round5_joint_view_answer'] = True
                    else:
                        fallback_trace = [*trace, _step(
                            'multigrain_source_binding', 'abstained',
                            reason='candidate-view pass did not return ANSWER',
                            candidate_verdict=selected_result.get('verdict'),
                            full_original_view_required=True,
                        )]
                        result = answer(request, [self._routed_semantic_view(request, fallback_trace)], trace=fallback_trace)
                        result['_round5_joint_view_answer'] = False
                else:
                    result = answer(request, [self._routed_semantic_view(request, trace)], trace=trace)
                    result['_round5_joint_view_answer'] = False
            door = 'semantic_document'
        else:
            self._init_semantic_retriever(); door = 'semantic_qa'
            if request.unread or not request.plans:
                result = answer(request, [], trace=trace)
            elif not self._semantic_retriever.libraries:
                result = refusal('UNKNOWN_SOURCE_ASSET', 'existing sentence evidence index is unavailable',
                                 phase='retrieval', request=request, trace=trace)
            else:
                try:
                    views, retrieval, provenance = self._semantic_retriever.retrieve(request)
                    result = answer(request, views, trace=trace+retrieval)
                except Limit as exc:
                    result = refusal('UNKNOWN_BUDGET', str(exc), phase='retrieval', request=request,
                                     trace=trace+getattr(exc,'trace',[]))
            for source in result.get('sources', []):
                origin = provenance.get(source['source'])
                if origin: source.update(view_source=source['source'], **origin)
        return self._finish(result, text, [], door)

    def close(self) -> None:
        """Release only this instance's read-only semantic index handles."""
        if self._semantic_retriever is not None: self._semantic_retriever.close()
        self._multigrain_constellation = None
        self._multigrain_generation = None
        self._material_source = None
        self._content_engine = None

    def material_candidates(self, family: str, text: str, *, limit: int = 64) -> dict:
        """Read source-bound structure/fiction materials, never an answer.

        This is the composition-reader boundary. Labels, retrieval ranks and
        story sentences do not become factual evidence or verified output.
        """
        from .material_source import MaterialSource
        from .paths import corpus_root
        if self._material_source is None:
            self._material_source = MaterialSource(self.material_root or self.round3_root or corpus_root() / 'build/round3',
                                                   immutable=self.material_immutable)
        return self._material_source.candidates(family, text, limit=limit)

    def _new_route_refusal(self, text: str, verdict: str, reason: str, *, route='round5') -> dict:
        return self._finish({'kind': 'unknown', 'verdict': verdict, 'text': '', 'values': [],
                             'reason': reason, 'verified': False, 'sources': [], 'evidence': []},
                            text, [_step('one.round5_route', 'abstained', reason=reason)], route)

    def _ask_contract(self, text: str, *, cancel=None) -> dict:
        from .contract_codegen import generate_code
        result = dict(generate_code(text, cancel=cancel))
        if result.get('verdict') == 'ANSWER':
            certificate = result.get('verification') or {}
            code = result.get('code')
            if (result.get('status') != 'verified' or not isinstance(code, str)
                    or not isinstance(certificate, dict)
                    or certificate.get('status') != 'finite_verified' or certificate.get('origin') != 'raw'
                    or certificate.get('artifact_sha256') != hashlib.sha256(code.encode('utf-8')).hexdigest()
                    or not isinstance(result.get('source'), dict)
                    or (result.get('source') or {}).get('raw') != text):
                result.update(kind='unknown', verdict='UNKNOWN_INVALID_RESULT', status='held', code=None,
                              created=False, text='', values=[], verified=False,
                              component_verification=certificate,
                              verification={'status': 'transport_rejected', 'passed': False},
                              reason='Code response does not match its raw-source verification certificate.')
                result.pop('realization', None)
        if isinstance(result.get('trace'), dict):
            result['contract_trace'] = result['trace']
            result['trace'] = [_step('contract_codegen.generate_code', 'ran', contract_trace=result['contract_trace'])]
        result.setdefault('kind', 'code' if result.get('verdict') == 'ANSWER' else 'unknown')
        result.setdefault('values', [])
        return self._finish(result, text, [], 'round5_contract')

    def _ask_content(self, text: str, *, materials=()) -> dict:
        from .content_api import ContentEngine
        from .material_source import MaterialSource
        from .paths import corpus_root
        if self._content_engine is None:
            if self._material_source is None:
                self._material_source = MaterialSource(self.material_root or self.round3_root or corpus_root() / 'build/round3',
                                                       immutable=self.material_immutable)
            self._content_engine = ContentEngine(material_source=self._material_source)
        if not isinstance(materials, (list, tuple)):
            raise ValueError('materials must be a finite list or tuple')
        provided = list(materials)
        if self.bot is not None:
            provided += [{'source': key, 'text': raw, 'family': 'document', 'purpose': 'evidence',
                          'independent': getattr(self.bot, 'original_sovereigns', {}).get(key, key)}
                         for key, raw in getattr(self.bot, 'original_texts', {}).items()]
        result = dict(self._content_engine.ask(text, materials=provided))
        if result.get('verdict') in ('ANSWER', 'CREATED'):
            realization = result.get('realization') or {}
            certificate = result.get('verification') or {}
            created = result.get('verdict') == 'CREATED'
            plan_hash = result.get('plan_hash')
            if (not isinstance(certificate, dict) or certificate.get('passed') is not True
                    or not isinstance(realization, dict)
                    or result.get('kind') != ('created' if created else 'answer')
                    or result.get('created') is not created
                    or not isinstance(result.get('text'), str) or not result['text']
                    or realization.get('text') != result['text']
                    or not isinstance(plan_hash, str) or re.fullmatch('[a-f0-9]{64}', plan_hash) is None
                    or realization.get('plan_hash') != plan_hash):
                result.update(kind='unknown', verdict='UNKNOWN_INVALID_RESULT', created=False,
                              code=None, text='', values=[], verified=False, component_verification=certificate,
                              verification={'passed': False, 'status': 'transport_rejected'},
                              reason='Content response does not match its verified realization.')
                result.pop('realization', None)
        # The realization certificate verifies this represented projection.
        # It does not verify that every event requested by the user was found.
        # Keep the verified component result visible, while the public verdict
        # says partial whenever event-set completeness is unknown.
        if (result.get('event_set_status') == 'PARTIAL'
                and result.get('semantic_event_set_complete') is None
                and result.get('goal_satisfied') is None
                and result.get('success_count_eligible') is False
                and result.get('verdict') == 'ANSWER'):
            result['component_verdict'] = 'ANSWER'
            result['verdict'] = 'PARTIAL'
            result['status'] = 'PARTIAL_COMPLETENESS_UNVERIFIED'
            result['response_notice'] = (
                '本文は検証済みですが、依頼された出典イベント全体の網羅性は未確認です。'
            )
        result.setdefault('values', [])
        # This remains an explicitly experimental API. The delivered C counter
        # excludes Frame/morphology and material-reader internals; it cannot
        # certify the preregistered whole-request 4096-operation budget.
        observed = result.get('budget') if isinstance(result.get('budget'), dict) else {}
        result['budget'] = {**observed, 'accounting_complete': False,
                            'steps_known': observed.get('counts', {}).get('steps'),
                            'steps_total': None,
                            'uncovered': ['Frame/morphology internals', 'material-reader internals',
                                          'unmetered C comparisons and inner loops']}
        result['experimental'] = True
        result['adoption_eligible'] = False
        # CREATED is fictional construction. Preserve it as distinct from a
        # factual ANSWER and retain the component's verification/provenance.
        return self._finish(result, text, [], 'round5_content')

    def _ask_round5(self, text: str, *, materials=(), cancel=None) -> dict:
        from .contract_codegen import is_code_request
        from .content_api import is_content_request
        code, content = bool(is_code_request(text)), bool(is_content_request(text))
        route = _step('one.round5_route', 'ran', code_intent=code, content_intent=content,
                      decision_input='raw_request', fallback=False)
        if code and content:
            return self._new_route_refusal(text, 'UNKNOWN_AMBIGUOUS_INTENT',
                                           'Code and content intentions overlap; no route was selected.')
        if cancel is not None and not code:
            return self._new_route_refusal(text, 'UNKNOWN_UNSUPPORTED_CANCELLATION',
                                           'Cancellation is supported by the code contract only in this prototype.')
        if code:
            if materials:
                return self._new_route_refusal(text, 'UNKNOWN_UNSUPPORTED_MATERIAL',
                                               'The code contract accepts requirements in the raw request only.')
            result = self._ask_contract(text, cancel=cancel)
        elif content:
            result = self._ask_content(text, materials=materials)
        else:
            if materials:
                return self._new_route_refusal(text, 'UNKNOWN_UNSUPPORTED_MATERIAL',
                                               'Use ordinary document inputs for semantic QA.')
            from .request_goal_route import is_request_utterance, route_request_goal
            navigation = self._round5_multigrain_navigation(text)
            binding = (self._round5_bind_multigrain_source(text, navigation)
                       if navigation is not None else None)
            candidate_goal_used = False
            candidate_answer_used = False
            candidate_answer_confirmed = False
            candidate_document_cited = False
            candidate_clause_span_cited = False
            candidate_clause_span_match_count = 0
            if is_request_utterance(text):
                # Request authority stays in raw text; only the original
                # source text is passed separately as evidence. A bound
                # candidate narrows only the source sentence; the Goal
                # consumer and the post-generation rebind both recheck it.
                originals = dict(getattr(self.bot, 'original_texts', {}) or {})
                if binding is not None and binding.status == 'BOUND':
                    from .multigrain_source_binding import route_goal_from_bound_source
                    candidate_goal_used = (
                        len(binding.selections) == 1
                        and len(binding.selections[0].clause_ids) == 1
                        and len(binding.views) == 1
                        and not binding.views[0].unread
                    )
                    if candidate_goal_used:
                        result = route_goal_from_bound_source(
                            text, originals, bot=self.bot,
                            navigation_root=self._multigrain_source_root,
                            snapshot=self._multigrain_source_registry,
                            constellation=self._multigrain_constellation,
                            initial_navigation=navigation,
                            initial_binding=binding,
                            semantic_view=self._semantic_view,
                        )
                    else:
                        result = {
                            'kind': 'unknown', 'verdict': 'UNKNOWN_REQUEST_GOAL_HOLD',
                            'status': 'HOLD', 'text': '', 'candidate_text': None,
                            'reason': 'candidate maps to multiple or incomplete source spans',
                            'verified': False, 'candidate_projection_verified': False,
                            'full_goal_verified': False, 'full_semantic_equivalent': None,
                            'goal_satisfied': None, 'success_count_eligible': False,
                            'adoption_eligible': False, 'world_assigned': False,
                            'independent_source_count': 0,
                        }
                elif (type(navigation) is dict
                      and navigation.get('selected_candidate') is not None):
                    # A proposed candidate that failed its source Frame/role
                    # rebind is a terminal HOLD. Do not let the independent
                    # one-document diagnostic route bypass a failed local
                    # patient, quote, polarity, or scope check.
                    binding_status = binding.status if binding is not None else 'UNAVAILABLE'
                    binding_reason = (binding.reason if binding is not None
                                      else 'no candidate source binding result')
                    result = {
                        'kind': 'unknown', 'verdict': 'UNKNOWN_REQUEST_GOAL_HOLD',
                        'status': 'HOLD', 'text': '', 'candidate_text': None,
                        'reason': binding_reason,
                        'verified': False, 'candidate_projection_verified': False,
                        'full_goal_verified': False, 'full_semantic_equivalent': None,
                        'goal_satisfied': None, 'success_count_eligible': False,
                        'adoption_eligible': False, 'world_assigned': False,
                        'independent_source_count': 0,
                        'goal_route': 'source_candidate_rejected_by_local_frame_binding',
                        'source_binding_success': False,
                        'source_binding_status': binding_status,
                        'source_binding_reason': binding_reason,
                        'source_binding': binding.as_dict() if binding is not None else None,
                        'trace': [_step(
                            'one.request_goal_source_route', 'held',
                            goal_route='source_candidate_rejected_by_local_frame_binding',
                            source_binding_success=False,
                            source_binding_status=binding_status,
                            reason=binding_reason,
                        )],
                    }
                elif (type(navigation) is dict
                      and isinstance(navigation.get('request_goal_selection'), dict)
                      and navigation['request_goal_selection'].get('status') != 'READY'):
                    projection_reason = navigation['request_goal_selection'].get(
                        'reason', 'raw Goal target projection held')
                    binding_status = binding.status if binding is not None else 'UNAVAILABLE'
                    binding_reason = (binding.reason if binding is not None
                                      else projection_reason)
                    result = {
                        'kind': 'unknown', 'verdict': 'UNKNOWN_REQUEST_GOAL_HOLD',
                        'status': 'HOLD', 'text': '', 'candidate_text': None,
                        'reason': projection_reason,
                        'verified': False, 'candidate_projection_verified': False,
                        'full_goal_verified': False, 'full_semantic_equivalent': None,
                        'goal_satisfied': None, 'success_count_eligible': False,
                        'adoption_eligible': False, 'world_assigned': False,
                        'independent_source_count': 0,
                        'goal_route': 'raw_request_projection_hold',
                        'source_binding_success': False,
                        'source_binding_status': binding_status,
                        'source_binding_reason': binding_reason,
                        'source_binding': binding.as_dict() if binding is not None else None,
                        'trace': [_step(
                            'one.request_goal_source_route', 'held',
                            goal_route='raw_request_projection_hold',
                            source_binding_success=False,
                            source_binding_status=binding_status,
                            reason=projection_reason,
                        )],
                    }
                else:
                    # The candidate did not bind. Preserve the earlier raw
                    # route for its explicitly supported one-document case,
                    # but label it as unbound so a legacy PARTIAL cannot be
                    # read as a source-span-bound Goal result.
                    result = route_request_goal(text, originals)
                    binding_status = binding.status if binding is not None else 'UNAVAILABLE'
                    binding_reason = (binding.reason if binding is not None
                                      else 'no candidate navigation/source binding')
                    result['goal_route'] = 'unbound_original_source_fallback'
                    result['source_binding_success'] = False
                    result['source_binding_status'] = binding_status
                    result['source_binding_reason'] = binding_reason
                    result.setdefault('trace', []).append(_step(
                        'one.request_goal_source_route', 'fallback',
                        goal_route='unbound_original_source_fallback',
                        source_binding_success=False,
                        source_binding_status=binding_status,
                        reason=binding_reason,
                    ))
                result = self._finish(result, text, [], 'round5_request_goal')
            else:
                candidate_views = (binding.views if binding is not None
                                   and binding.status == 'BOUND' else ())
                result = self._ask_semantic(text, candidate_views=candidate_views)
                candidate_answer_used = bool(candidate_views)
                candidate_answer_confirmed = bool(result.pop(
                    '_round5_joint_view_answer', False))
                candidate_source_ids = {
                    source_id for view in candidate_views for source_id in view.sources
                }
                candidate_clause_spans = set()
                for view in candidate_views:
                    for clause in view.clauses:
                        span = getattr(clause, 'span', None)
                        clause_id = getattr(clause, 'id', None)
                        source_id = getattr(span, 'source', None)
                        start = getattr(span, 'start', None)
                        end = getattr(span, 'end', None)
                        text_value = getattr(span, 'text', None)
                        if (type(clause_id) is str and type(source_id) is str
                                and type(start) is int and type(end) is int
                                and type(text_value) is str):
                            candidate_clause_spans.add(
                                (clause_id, source_id, start, end, text_value))
                candidate_document_cited = (
                    candidate_answer_confirmed
                    and any(type(source) is dict and source.get('source') in candidate_source_ids
                            for source in result.get('sources', []))
                )
                if candidate_answer_confirmed:
                    for source in result.get('sources', []):
                        if type(source) is not dict:
                            continue
                        span = source.get('span')
                        if type(span) is not dict:
                            continue
                        clause_id = source.get('clause')
                        source_id = source.get('source')
                        start = span.get('start')
                        end = span.get('end')
                        text_value = span.get('text')
                        if (type(clause_id) is not str or type(source_id) is not str
                                or type(start) is not int or type(end) is not int
                                or type(text_value) is not str):
                            continue
                        key = (clause_id, source_id, start, end, text_value)
                        if key in candidate_clause_spans:
                            candidate_clause_span_match_count += 1
                candidate_clause_span_cited = (
                    candidate_answer_confirmed and candidate_clause_span_match_count > 0
                )
            if navigation is not None:
                if binding is not None:
                    navigation['source_binding'] = binding.as_dict()
                navigation['authority'] = (
                    'source_location_hypothesis' if binding is not None and binding.status == 'BOUND'
                    else 'navigation_only_unverified'
                )
                navigation['candidate_views_supplied_to_answer_verifier'] = candidate_answer_used
                navigation['candidate_document_id_cited_after_full_view_check'] = candidate_document_cited
                navigation['candidate_sentence_span_cited_after_full_view_check'] = None
                navigation['candidate_clause_span_cited_after_full_view_check'] = candidate_clause_span_cited
                navigation['candidate_clause_span_match_count'] = candidate_clause_span_match_count
                navigation['candidate_clause_span_causal_influence_proven'] = False
                navigation['citation_granularity'] = 'source_id_and_exact_candidate_clause_span_match'
                navigation['used_for_goal_realization'] = candidate_goal_used
                navigation['candidate_goal_status'] = result.get('verdict') if candidate_goal_used else None
                result["multigrain_navigation"] = navigation
                result.setdefault("trace", []).append(_step(
                    "multigrain_adapter.retrieve_multigrain_candidates",
                    "ran" if navigation.get("trace", {}).get("calls", {}).get(
                        "FullConstellation.ask", 0) else "abstained",
                    verdict=navigation.get("verdict"),
                    selected_candidate=navigation.get("selected_candidate"),
                    source_identity_status=navigation.get("source_identity_status"),
                    independent_source_count=navigation.get("independent_source_count"),
                    source_binding_status=(binding.status if binding is not None else 'UNAVAILABLE'),
                    source_binding_reason=(binding.reason if binding is not None else 'no Bot source binding'),
                    candidate_views_supplied_to_answer_verifier=candidate_answer_used,
                    candidate_document_id_cited_after_full_view_check=candidate_document_cited,
                    candidate_sentence_span_cited_after_full_view_check=None,
                    candidate_clause_span_cited_after_full_view_check=candidate_clause_span_cited,
                    candidate_clause_span_match_count=candidate_clause_span_match_count,
                    candidate_clause_span_causal_influence_proven=False,
                    citation_granularity='source_id_and_exact_candidate_clause_span_match',
                    bound_source_supplied_to_goal_consumer=bool(candidate_goal_used),
                    licenses_goal_realization=False,
                ))
        result['trace'] = [route, *result.get('trace', [])]
        result['runtime_mode'] = 'round5'
        return result

    def ask(self, question_text: str, *, query: question.Query | None = None,
            mode: str | None = None, **engine_kwargs: Any) -> dict:
        chosen = mode or self.mode
        if chosen not in ('legacy', 'semantic', 'contract', 'content', 'round5'): raise ValueError('unknown Vera mode')
        if chosen == 'semantic':
            return self._ask_semantic(question_text)
        if chosen in ('contract', 'content', 'round5'):
            allowed = {'contract': {'cancel'}, 'content': {'materials'}, 'round5': {'materials', 'cancel'}}[chosen]
            if query is not None or engine_kwargs.keys() - allowed:
                raise ValueError('Round5 public routes accept raw requests, not prepared queries or profiles')
            if not isinstance(question_text, str): raise ValueError('request must be text')
            try:
                if chosen == 'contract': return self._ask_contract(question_text, **engine_kwargs)
                if chosen == 'content': return self._ask_content(question_text, **engine_kwargs)
                return self._ask_round5(question_text, **engine_kwargs)
            except ModuleNotFoundError as exc:
                if exc.name not in ('verantyx.contract_codegen', 'verantyx.content_api'): raise
                return self._new_route_refusal(question_text, 'UNKNOWN_ENGINE_UNAVAILABLE',
                                               'The selected Round5 runtime component is not installed.', route=chosen)
        reading = query if query is not None else question.read(question_text)
        text = reading.surface.value
        trace = _reading_trace(reading)
        if self.bot is None and reading.kind.value != "instruction":
            from .round3 import route
            if route(text, reading)[0] in ("code_qa", "live"):
                routed = self._round3_answer(text, reading, trace)
                if routed is not None:
                    return routed
        # A loaded personal document collection owns its answer scope. For
        # every other question, the five family sovereigns get a deterministic
        # typed handoff before the older general federation.
        if (not self.engine_compat and reading.kind.value != "instruction" and
                (self.general is None or self.round3_root is not None) and self.bot is None):
            routed = self._round3_answer(text, reading, trace)
            if routed is not None:
                return routed
        if self.bot is not None:
            from .skills import answer as skill
            from .chat import BYE, GREET

            exact = skill(text)
            trace.append(_step("skills.answer", "ran" if exact else "abstained",
                               kind=exact.get("kind") if exact else None))
            if exact:
                return self._finish(exact, text, trace, "skill")
            if GREET.search(text) or BYE.search(text) or reading.speech_act.value.act in ("thanks", "apology"):
                return self.chat(text, query=reading, _trace=trace)
            found = self.bot.find(text, query=reading)
            trace.append(_step("bot.Bot.find", "ran" if found is not None else "abstained",
                               reason="no documents" if found is None else ""))
            if found is not None:
                trace.extend(self.load_trace)
                quoted = self._document_annotations(text, reading, found, trace)
                if (found.get("verdict") == "NOT_IN_DOCS" and quoted is not None and
                        reading.kind.value not in ("count", "comparison", "why", "negation") and
                        quoted.get("verdict") in ("DOCUMENT_SECTION", "DOCUMENT_LABEL", "DOCUMENT_LINE")):
                    sentence = str(quoted["text"])
                    found = {"text": sentence, "kind": "answer", "verdict": "ANSWER",
                             "source": quoted.get("source"), "evidence": [sentence],
                             "trace": found.get("trace", []) +
                             [_step("document_structure.verify_quoted", "ran", source=quoted.get("source"))]}
                return self._finish(found, text, trace, "document")
            # An empty Bot is also a public chat surface.  Preserve the same
            # Query object for direct Chat callers and existing adapters.
            return self.chat_actor.reply(text, query=reading)
        if self.library is not None:
            proposal = self.library.ask(text)
            trace.append(_step("library.Library.ask", "ran", path=proposal["path"],
                               route=proposal.get("route_trace"), frames_touched=proposal["frames_touched"]))
            # A library hit is a retrieval proposal, not a document slot verdict.
            trace.append(_step("answer.slot", "abstained", reason="library has no loaded source documents"))
        if self.general is not None:
            from .chat import BYE, GREET
            if (not self.engine_compat and
                    (reading.kind.value == "instruction" or GREET.search(text) or BYE.search(text) or
                     reading.speech_act.value.act in ("thanks", "apology"))):
                return self.chat(text, query=reading, _trace=trace)
            if reading.kind.value == "definition":
                try:
                    from .meaning_assets import aliases, defs, lattice
                    from .meaning_descent import descend
                    term = text.split("とは", 1)[0].strip("？?。 ")
                    defined = descend(term, lattice=lattice(), defs=defs(), aliases=aliases())
                    trace.append(_step("meaning_descent.descend", "ran", verdict=defined.get("verdict")))
                    if str(defined.get("verdict", "")).startswith("EXPLAINED"):
                        return self._finish(defined, text, trace, "general")
                except (FileNotFoundError, OSError) as exc:
                    trace.append(_step("meaning_descent.descend", "abstained", reason=str(exc)))
            if not self.engine_compat:
                from .skills import answer as skill
                exact = skill(text)
                trace.append(_step("skills.answer", "ran" if exact else "abstained",
                                   kind=exact.get("kind") if exact else None))
                if exact:
                    return self._finish(exact, text, trace, "skill")
                from .abilities import Abilities
                actor = self.chat_actor
                if not hasattr(actor, "_abilities"):
                    actor._abilities = Abilities(general=Path(actor.general))
                ability = actor._abilities.answer(text, reading)
                trace.append(_step("abilities.Abilities.answer", "ran" if ability else "abstained",
                                   ability=ability.get("ability") if ability else None))
                if ability is not None:
                    return self._finish(ability, text, trace, "chat")
            return self._general(text, trace, engine_kwargs)
        if self.library is not None:
            return self._finish({"text": "文書には書かれていません。", "kind": "unknown",
                                 "verdict": "NOT_IN_DOCS", "evidence": [],
                                 "how_to_resolve": "出典文書を読み込み、質問された項目を検証してください。"},
                                text, trace, "library")
        return self.chat(text, query=reading, _trace=trace)

    def _round3_answer(self, text: str, reading: question.Query,
                       trace: list[dict]) -> dict | None:
        from .paths import corpus_root
        from .round3 import GeneralRouter

        if self._round3_router is None:
            self._round3_router = GeneralRouter(self.round3_root or corpus_root() / "build/round3")
        if not self._round3_router.available():
            from .round3 import route
            if route(text, reading)[0] not in ("code_qa", "live", "conversation"):
                return None
        from .abilities import Abilities
        actor = self.chat_actor
        if not hasattr(actor, "_abilities"):
            actor._abilities = Abilities(general=Path(actor.general))
        result, steps = self._round3_router.answer(text, reading, abilities=actor._abilities)
        if (steps and steps[0].get("family") == "conversation" and
                result.get("kind") in _REFUSAL_KINDS):
            social = actor._reply_impl(text, "", query=reading)
            if social.get("kind") == "social" and social.get("text"):
                spoken = str(social["text"])
                result = {"kind": "social", "verdict": "ANSWER", "text": spoken,
                          "evidence": [spoken],
                          "sources": [{"family": "conversation_form", "source": "chat.social", "text": spoken}]}
                steps.append(_step("chat.social", "ran", act=reading.speech_act.value.act))
        return self._finish(result, text, trace + steps, "round3")

    def _document_annotations(self, text: str, reading: question.Query,
                              result: dict, trace: list[dict]) -> dict | None:
        from .document_structure import lookup, verify_quoted

        candidate = None
        if _SECTION_REQUEST.search(text):
            candidate = lookup(text, self.book)
            source_text = getattr(self.bot, "safe_texts", {}).get(str(candidate.get("source")), "")
            if not source_text:
                source_text = self.bot.base.docs.get(str(candidate.get("source")), {}).get("text", "")
            quoted = bool(candidate.get("text") and source_text and verify_quoted(candidate, source_text))
            trace.append(_step("document_structure.lookup", "ran", verdict=candidate.get("verdict"),
                               quoted=quoted, source=candidate.get("source")))
            if not quoted:
                candidate = None
        else:
            trace.append(_step("document_structure.lookup", "abstained", reason="no heading or label request"))
        if self.library is not None:
            proposal = self.library.ask(text)
            trace.append(_step("library.Library.ask", "ran", path=proposal["path"],
                               route=proposal.get("route_trace"), frames_touched=proposal["frames_touched"],
                               role="retrieval proposal; P3 source/slot gate decides"))
        else:
            trace.append(_step("library.Library.ask", "abstained", reason="no optional checkpoint"))
        route = next((s for s in result.get("trace", []) if s.get("part") == "base.find"), {})
        trace.append(_step("base.Base.find", "ran", path=route.get("path"),
                           route=route.get("route"), fallback=route.get("fallback")))
        path = route.get("path")
        for part in ("conduct_tree.descend", "surface.route", "hierarchy.route"):
            ran = self.bot.base.routing_root is not None and part != "hierarchy.route"
            trace.append(_step(part, "ran" if ran else "abstained", path=path,
                               reason="replaced by conductive node" if part == "hierarchy.route"
                               else "one leaf has no descent" if not ran else ""))
        trace.append(_step("base.fallback_items", "ran" if path == "fallback_frames" else "abstained",
                           **route.get("fallback", {})))
        if reading.kind.value == "multi_hop" and result.get("evidence"):
            from .typed_edges import extract
            edge_counts = [len(extract(sentence)) for sentence in result["evidence"]]
            trace.append(_step("typed_edges.extract", "ran", edges=edge_counts,
                               role="same-document proposal only"))
        if reading.kind.value in ("multi_hop", "comparison", "condition", "negation"):
            from .stacked import ask as stacked_ask
            proposal = stacked_ask(self.doc_store, text)
            trace.append(_step("stacked.ask", "ran", verdict=proposal.get("verdict"),
                               role="proposal only; answer.compose binds document sentences"))
        else:
            trace.append(_step("stacked.ask", "abstained", reason="no staged/shape request"))
        if reading.kind.value == "comparison":
            # The document composer does the sourced arithmetic. Structural
            # diff requires profile/sense sidecars and cannot assert absence.
            from .meaning_assets import _indexed
            indexed = _indexed()
            trace.append(_step("meaning_index.maps", "ran" if indexed is not None else "abstained",
                               reason="index unavailable" if indexed is None else ""))
            trace.append(_step("structural_diff.diff", "abstained", reason="predicate profiles and sense index unavailable"
                               if indexed is None else "document comparison uses sourced slot arithmetic"))
        if reading.kind.value == "definition":
            from .meaning_assets import _indexed
            trace.append(_step("meaning_descent.descend", "abstained", reason="definition index unavailable"
                               if _indexed() is None else "document evidence takes precedence"))
        return candidate

    def _general(self, text: str, trace: list[dict], kwargs: dict) -> dict:
        from .polyglot import Polyglot
        stores = getattr(self.general, "stores", {})
        language = Polyglot(stores=stores).route(text)
        trace.append(_step("polyglot.Polyglot.route", "ran", language=language,
                           held=sorted(stores)))
        if self.engine_compat:
            # The old engine's specialist doors remain available behind this
            # adapter; its public function delegates here.
            from .engine import _ask_legacy
            result = _ask_legacy(text, self.general, **kwargs)
            trace.append(_step("engine.ask", "ran", door=result.get("door")))
            trace.append(_step("engine._ask_legacy", "ran", door=result.get("door")))
            trace.extend(_step("engine." + s["stage"], "ran" if s.get("fired") else "abstained",
                               note=s.get("note")) for s in result.get("stages", []))
        else:
            result = self.general.ask(text)
        trace.append(_step("vera.Vera.ask", "ran", verdict=result.get("verdict")))
        trace.append(_step("graded.GradedJudge.ask", "ran" if result.get("coverage") is not None else "abstained",
                           coverage=result.get("coverage")))
        trace.append(_step("resolution.Ladder", "ran" if result.get("coverage") is not None else "abstained",
                           reason="graded judge builds and reads its nested ladders"))
        trace.append(_step("stacked.ask", "ran" if result.get("coverage") is not None else "abstained",
                           verdict=result.get("verdict")))
        trace.append(_step("consensus_store.consensus_over_store",
                           "ran" if result.get("coverage") is not None else "abstained",
                           verdict=result.get("verdict")))
        if not result.get("text"):
            trace.append(_step("reach.reach", "ran", reached=result.get("reached", [])))
        else:
            trace.append(_step("reach.reach", "abstained", reason="core text is already held"))
        if result.get("reached"):
            if any(r.get("explained") for r in result["reached"]):
                trace.append(_step("explain.explain", "ran"))
            else:
                trace.append(_step("explain.explain", "abstained", reason="no supported unit explanation"))
        else:
            trace.append(_step("explain.explain", "abstained", reason="no writer or no supported unit landing"))
        if result.get("witnesses"):
            trace.append(_step("sovereign.witnesses", "ran", witnesses=result["witnesses"]))
        if result.get("written"):
            trace.append(_step("stacked.in_words", "ran", written=result["written"]))
        return self._finish(result, text, trace, "general")

    def judge(self, claim: str, *, query: question.Query | None = None,
              glossary: Mapping[str, str] | None = None) -> dict:
        if self.mode != 'legacy':
            return self._new_route_refusal(claim, 'UNKNOWN_UNSUPPORTED_OPERATION',
                                           'Round5 claim judging has not been wired; use an explicit question through ask.')
        reading = query if query is not None else question.read(claim)
        trace = _reading_trace(reading) + list(self.load_trace)
        if self.bot is None or not self.bot.sents:
            return self._finish({"verdict": "NOT_IN_DOCS", "kind": "unknown", "text": "文書には書かれていません。",
                                 "evidence": []}, claim, trace, "document")
        if glossary and any(s["lang"] == "ja" for s in self.bot.sents):
            from .crossverify import verify
            output = verify("".join(d["text"] for d in self.bot.base.docs.values()), dict(glossary), [claim])
            result = output[0] if isinstance(output, list) else output
            trace.append(_step("crossverify.verify", "ran", glossary=sorted(glossary)))
            trace.append(_step("en_frames.read", "ran", claim=claim))
        elif hasattr(self.bot, "_judge_impl"):
            result = self.bot._judge_impl(claim)
            trace.append(_step("base.judge" if any(s["lang"] == "ja" for s in self.bot.sents)
                               else "crossverify.judge", "ran", path=result.get("path"),
                               route=result.get("route_trace"), fallback=result.get("fallback_trace")))
            if all(s["lang"] == "en" for s in self.bot.sents):
                trace.append(_step("en_frames.read", "ran", claim=claim))
        else:
            result = self.bot.judge(claim)
        return self._finish(result, claim, trace, "document")

    def chat(self, utterance: str, *, query: question.Query | None = None,
             context: str = "", _trace: list[dict] | None = None) -> dict:
        if self.mode != 'legacy':
            if context or query is not None:
                return self._new_route_refusal(utterance, 'UNKNOWN_UNSUPPORTED_CONTEXT',
                                               'Round5 chat accepts the raw utterance and loaded original documents.')
            return self.ask(utterance)
        reading = query if query is not None else question.read(utterance)
        trace = list(_trace) if _trace is not None else _reading_trace(reading)
        if (self.bot is None or not self.bot.base.docs) and reading.kind.value != "instruction":
            from .round3 import route
            if route(utterance, reading)[0] in ("code_qa", "live"):
                routed = self._round3_answer(utterance, reading, trace)
                if routed is not None:
                    return routed
        use_round3 = (not self.engine_compat and reading.kind.value != "instruction" and
                      (self.general is None or self.round3_root is not None)
                      and (self.bot is None or not self.bot.base.docs))
        if use_round3:
            from .round3 import route as round3_route
            family, _, _ = round3_route(utterance, reading)
            if family in ("live", "code_qa") or self.round3_root is not None:
                routed = self._round3_answer(utterance, reading, trace)
                if routed is not None:
                    return routed
        result = self.chat_actor._reply_impl(utterance, context, query=reading)
        if (use_round3 and family == "general_qa" and
                (not result.get("ability") or
                 result.get("ability") == "commonsense" and reading.kind.value == "fact") and
                (result.get("kind") in ("unknown", "not_yet", "cannot", "unreadable") or
                 result.get("text") in ("", "そうなんですね。"))):
            routed_trace = list(trace)
            if reading.kind.value == "definition":
                from .chat import WHAT_IS
                routed_trace.append(_step("chat.Chat.reply", "ran", implementation="_reply_impl"))
                if WHAT_IS.match(utterance):
                    routed_trace.append(_step("say.say", "ran" if self.chat_actor.con is not None else "abstained",
                                              source="general.db"))
            routed = self._round3_answer(utterance, reading, routed_trace)
            if routed is not None:
                return routed
        trace.append(_step("chat.Chat.reply", "ran", implementation="_reply_impl"))
        ability = result.get("ability")
        trace.append(_step("abilities.Abilities.answer", "ran" if ability else "abstained",
                           ability=ability))
        if not ability:
            trace.append(_step("skills.answer", "ran" if result.get("source") == "skill" else "abstained",
                               reason="ability dispatcher yielded no answer"))
            trace.append(_step("core_abilities.answer", "ran" if result.get("source") == "core" else "abstained",
                               reason="exact legacy ability yielded no answer"))
        if ability:
            trace.append(_step("ability." + ability, "ran", verdict=result.get("verdict")))
        elif result.get("source") == "general":
            trace.append(_step("say.say", "ran" if any(s.get("part") == "say.say" for s in result.get("trace", []))
                               else "abstained", source="general.db"))
        else:
            from .chat import WHAT_IS
            if WHAT_IS.match(utterance):
                trace.append(_step("say.say", "ran" if self.chat_actor.con is not None else "abstained",
                                   reason="general.db unavailable" if self.chat_actor.con is None else "no attested event"))
            if result.get("kind") == "social":
                trace.append(_step("chat.social", "ran", act=reading.speech_act.value.act))
        return self._finish(result, utterance, trace, "chat")

    def _finish(self, result: dict, text: str, trace: list[dict], door: str) -> dict:
        from .remedy import remedy

        out = dict(result)
        out.setdefault("text", "")
        out["evidence"] = out.get("evidence") or []
        if isinstance(out["evidence"], str):
            out["evidence"] = [out["evidence"]] if out["evidence"] else []
        out["sources"] = out.get("sources") or []
        if door == "document" and self.bot is not None and not out["sources"]:
            cited = set(out["evidence"])
            out["sources"] = [{"family": "document", "source": sent["doc"], "text": sent["text"]}
                              for sent in self.bot.sents if not sent["injected"] and sent["text"] in cited]
            if not out["sources"] and out.get("source") in self.bot.base.docs:
                source = str(out["source"])
                original = getattr(self.bot, "safe_texts", {}).get(source, self.bot.base.docs[source]["text"])
                out["sources"] = [{"family": "document", "source": source, "text": evidence}
                                  for evidence in out["evidence"] if evidence in original]
        if door == "general" and not out["sources"]:
            origin = out.get("facet_origin") or {}
            if isinstance(origin, dict):
                out["sources"] = [{"family": "general", "source": str(label)}
                                  for labels in origin.values() if isinstance(labels, list)
                                  for label in labels]
            if not out["sources"]:
                out["sources"] = [{"family": "general", "source": str(label)}
                                  for store in getattr(self.general, "stores", {}).values()
                                  for label in getattr(store, "source_labels", set())]
        if (door == "chat" and out.get("source") == "general" and
                not out["sources"] and not out["evidence"] and out.get("kind") in ("answer", "compose")):
            out = {**out, "kind": "unknown", "verdict": "UNKNOWN_NO_CITATION",
                   "text": "出典文を確認できないため答えられません。",
                   "how_to_resolve": "出典文を含む general.db を指定してください。"}
        out["door"] = door
        prior = list(out.get("trace") or [])
        out["trace"] = trace + [({"status": "ran", **s} if "status" not in s else s) for s in prior]
        verdict = str(out.get("verdict") or "")
        refused = (verdict.startswith(_REFUSAL_PREFIXES) or
                   out.get("kind") in _REFUSAL_KINDS)
        if refused:
            if not verdict:
                verdict = "UNKNOWN_" + str(out.get("kind", "REFUSED")).upper()
                out["verdict"] = verdict
            info = remedy({**out, "verdict": verdict})
            if not info.get("register") and info.get("needs_registration") is None:
                info = {**info, "register": out.get("how_to_resolve") or (
                    "Add a document stating the requested fact." if door == "document" and not any("぀" <= c <= "龯" for c in text)
                    else "質問された事項を示す出典を追加してください。"), "needs_registration": True}
            out["remedy"] = info
            if not out.get("how_to_resolve"):
                out["how_to_resolve"] = str(info.get("register") or info.get("how") or info.get("note") or "根拠を追加してください。")
            out["trace"].append(_step("remedy.remedy", "ran", verdict=verdict,
                                       how_to_resolve=out["how_to_resolve"]))
            from .ask_back import question as ask_back_question
            askable = ask_back_question(text, verdict, candidates=out.get("candidates") or ())
            out["trace"].append(_step("ask_back.question", "ran" if askable else "abstained",
                                       reason="verdict has no human-answerable candidate" if not askable else "",
                                       asks=askable.asks if askable else ""))
            witnesses = getattr(self.general, "witnesses", {}) if self.general is not None else {}
            if witnesses and door == "general":
                from .coverage import document_needed
                hint = document_needed(witnesses, text, verdict)
                out["coverage_hint"] = hint
                out["trace"].append(_step("coverage.document_needed", "ran", hint=hint.get("document")))
            else:
                out["trace"].append(_step("coverage.document_needed", "abstained", reason="no domain witnesses"))
            if self.gap_path is not None:
                from .gap_graph import GapGraph, refusal_to_gap
                graph = GapGraph.load(self.gap_path)
                gap_id = refusal_to_gap(graph, text, verdict, branch="one.Vera", resolved=False,
                                        sources=[s.get("source", "") for s in out["sources"] if isinstance(s, dict)])
                graph.save(self.gap_path)
                out["gap_id"] = gap_id
                out["trace"].append(_step("gap_graph.refusal_to_gap", "ran", gap_id=gap_id))
            else:
                out["trace"].append(_step("gap_graph.refusal_to_gap", "abstained", reason="no opt-in gap_path"))
            import os
            if verdict == "UNKNOWN_NOT_PRESENT" and os.environ.get("VERA_QUEUE"):
                from .grow import log_refusal
                log_refusal(out)
                out["trace"].append(_step("grow.log_refusal", "ran", queue=os.environ["VERA_QUEUE"]))
            else:
                out["trace"].append(_step("grow.log_refusal", "abstained", reason="no queue opt-in or different verdict"))
        return out
