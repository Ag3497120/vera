"""A small typed conductor built on :mod:`memory_frame`.

The conductor answers only from active records.  Its language classifier is a
closed structural pattern set; unknown requests are escalated.  A closed-choice
asker is used only by ``Memory.resolver`` for terms that are outside the frame.
Its two-ask result is persisted as testimony and is never promoted to a fact.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Optional

from . import memory_frame
from .memory_frame import Memory, WriteRejected, check_witness, normalize_np
from .question import is_content_request


QuestionKind = Literal["ORDER", "CHOICE", "CONFIRM", "SCOPE", "STATUS", "OTHER"]
ReplyKind = Literal["ANSWER", "ESCALATE", "ASK_VERIFIER"]
QUESTION_KINDS: tuple[str, ...] = ("ORDER", "CHOICE", "CONFIRM", "SCOPE", "STATUS", "OTHER")


# All Memory extensions go through this closed table and installer.  These
# records use the two-slot property shape that Memory already round-trips.
_CONDUCTOR_KINDS = {
    "GOAL": (("subject", "value"), "完成条件"),
    "ACCEPTANCE": (("subject", "check"), "確認方法"),
    "ORDER": (("subject", "target"), "先行タスク"),
    "POLICY": (("subject", "answer"), "許可回答"),
    "ESCALATE": (("subject", "target"), "人への引継ぎ"),
    "ALIAS": (("subject", "value"), "語義対応"),
    "VERIFICATION": (("subject", "result"), "独立確認"),
}


def install_conductor_kinds() -> None:
    """Install the fixed conductor record kinds without replacing existing ones."""
    for kind, definition in _CONDUCTOR_KINDS.items():
        prior = memory_frame.KINDS.get(kind)
        if prior is not None and prior != definition:
            raise RuntimeError(f"Memory kind {kind} is already defined differently")
        memory_frame.KINDS.setdefault(kind, definition)


@dataclass(frozen=True)
class AgentQuestion:
    id: str
    text: str
    options: Optional[list[str]] = None
    claimed_state: Any = None


@dataclass(frozen=True)
class Reply:
    kind: ReplyKind
    answer: Optional[str] = None
    record_ids: tuple[str, ...] = ()
    why: str = ""
    reason: str = ""
    missing: Optional[str] = None
    question_kind: Optional[str] = None
    template_id: Optional[str] = None
    target: Optional[str] = None
    spec: Optional[Mapping[str, Any]] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "answer": self.answer,
            "record_ids": list(self.record_ids),
            "why": self.why,
            "reason": self.reason,
            "missing": self.missing,
            "question_kind": self.question_kind,
            "template_id": self.template_id,
            "target": self.target,
            "spec": dict(self.spec) if self.spec is not None else None,
        }


# Patterns classify the outer speech act.  They intentionally do not try to
# extract an answer or to understand arbitrary prose.
_ORDER_CUES = re.compile(
    r"\b(next|follow(?:s|ing)?|upcoming|sequence|priority|proceed|order of work)\b|"
    r"次|順番|先行|後続|優先順位|どこから進め|何から進め",
    re.I,
)
_CONFIRM_CUES = re.compile(
    r"\b(may i|can i|could i|should i|is it (?:okay|acceptable)|do i have permission)\b|"
    r"\bwould\b.{0,120}\b(?:okay|acceptable)\b|"
    r"してよい|してもよい|してもいい|して(?:も)?大丈夫|許可(?:され|が)|実行可能",
    re.I,
)
_SCOPE_CUES = re.compile(
    r"\b(scope|in scope|out of scope|within scope|included in)\b|"
    r"対象(?:内|外)?|範囲(?:内|外)?|含まれ(?:る|ます)?|スコープ",
    re.I,
)
_STATUS_CUES = re.compile(
    r"\b(done|complete|completed|finished|status|progress)\b|"
    r"完了|終わ(?:っ|り)|済ん|進捗|状態",
    re.I,
)
_CHOICE_CUES = re.compile(
    r"\b(choose|select|pick|which|decide between)\b|"
    r"選んで|選択|どれを|どちらを|どの案",
    re.I,
)


def classify_question(text: str, options: Optional[list[str]] = None) -> QuestionKind:
    """Classify a supported agent question using only closed surface patterns."""
    raw = (text or "").strip()
    if not raw:
        return "OTHER"
    if is_content_request(raw):
        return "OTHER"
    if _ORDER_CUES.search(raw):
        return "ORDER"
    if _SCOPE_CUES.search(raw):
        return "SCOPE"
    if _CHOICE_CUES.search(raw) and re.search(r"\bwhich\b|選んで|選択|どれ|どちら", raw, re.I):
        return "CHOICE"
    if _CONFIRM_CUES.search(raw):
        return "CONFIRM"
    if _STATUS_CUES.search(raw):
        return "STATUS"
    if _CHOICE_CUES.search(raw):
        return "CHOICE"
    # An explicit option list is useful structure only when the sentence asks
    # an interrogative or contains a closed selection cue.
    if options is not None and re.search(r"[?？]$", raw.strip()) and re.search(r"\b(which|what)\b|どれ|どちら", raw, re.I):
        return "CHOICE"
    return "OTHER"


_DELETE_ACTION = re.compile(
    r"\b(delete|deleting|erase|remove|destroy|drop\s+(?:table|database|branch)|rm\s+-)\b|"
    r"削除|消去|消す|消して|抹消",
    re.I,
)
_PUBLISH_ACTION = re.compile(
    r"\b(publish|publishing|release|release publicly|post publicly|push\s+(?:to\s+)?(?:origin|remote)|"
    r"push|deploy|upload|send externally|share externally)\b|公開|配信|外部送信|公表",
    re.I,
)
_SPEND_ACTION = re.compile(
    r"\b(spend(?:ing)?|purchase|buy|buying|pay(?:ing)?|charge(?:d)?)\b|支出|支払|購入|課金",
    re.I,
)
_CREDENTIAL_ACTION = re.compile(
    r"\b(?:enter|type|paste|submit|provide|input)\b.{0,40}\b(?:credentials?|passwords?|tokens?|secrets?|api\s+keys?)\b|"
    r"\b(?:credentials?|passwords?|tokens?|secrets?|api\s+keys?)\b.{0,40}\b(?:enter|type|paste|submit|provide|input)\b|"
    r"認証情報.{0,12}(?:入力|入力し)|(?:入力|入力し).{0,12}認証情報",
    re.I,
)
_SEALED_ACTION = re.compile(
    r"\b(?:sealed|held[- ]?out|holdout|held[- ]?back|restricted dataset)\b|"
    r"封印|封緘|非公開データ|封印データ",
    re.I,
)
_PROTECTED_PATTERNS = (
    ("delete", _DELETE_ACTION),
    ("outward publishing", _PUBLISH_ACTION),
    ("spending money", _SPEND_ACTION),
    ("credential entry", _CREDENTIAL_ACTION),
    ("sealed or held-out data", _SEALED_ACTION),
)
# A recipient with an explicit public/external scope is an outward transfer
# target, regardless of which communication verb occupies the action slot.
# This is a case-frame check (destination + scope), not an action-word list.
_OUTWARD_RECIPIENT = re.compile(
    r"\b(?:to|onto|via)\s+(?:(?:an?|the)\s+)?"
    r"(?:external|public|outside|third[ -]party)\b",
    re.I,
)
_ALLOW_WORDS = frozenset(("yes", "allow", "allowed", "approve", "approved", "in scope", "true", "許可", "可", "対象内", "範囲内"))
_DENY_WORDS = frozenset(("no", "deny", "denied", "disallow", "forbidden", "out of scope", "false", "不許可", "不可", "対象外", "範囲外"))


def _term_key(value: str) -> str:
    return normalize_np(unicodedata.normalize("NFKC", value).strip()).casefold()


def _text_key(value: str) -> str:
    return _term_key(value)


_POLICY_TOKEN = re.compile(r"[a-z0-9]+|[\u3040-\u30ff\u3400-\u9fff]+", re.I)
_POLICY_BOUNDARY = re.compile(r"[.!?。！？\r\n]+")
_POLICY_NEGATION = re.compile(
    r"^(?:not|never|no|cannot|can't|won't|don't|doesn't|didn't|isn't|aren't|"
    r"shouldn't|wouldn't|couldn't|ない|ません|ず)$",
    re.I,
)


def _policy_token_clauses(value: str) -> list[list[str]]:
    normalized = _text_key(value)
    return [tokens for piece in _POLICY_BOUNDARY.split(normalized)
            if (tokens := _POLICY_TOKEN.findall(piece))]


def _policy_tokens(value: str) -> list[str]:
    return [token for clause in _policy_token_clauses(value) for token in clause]


def _same_policy_token(expected: str, actual: str, *, predicate: bool) -> bool:
    if expected == actual:
        return True
    if (re.fullmatch(r"[\u3040-\u30ff\u3400-\u9fff]+", expected) and
            actual.startswith(expected)):
        # Japanese particles attach to noun phrases without whitespace.
        return True
    if not predicate:
        return False
    # Normalize regular English predicate inflections only. Noun arguments
    # stay exact, so draft and drafts remain different entities.
    if expected.endswith("e"):
        forms = {expected[:-1] + "ing", expected + "d", expected + "s"}
    else:
        forms = {expected + "ing", expected + "ed", expected + "s"}
        if expected.endswith(("s", "x", "z", "ch", "sh", "o")):
            forms.add(expected + "es")
    return actual in forms


def _policy_phrase_matches(condition: str, question: str) -> bool:
    """Match a policy condition as an ordered, bounded case-frame phrase."""
    expected = _policy_tokens(condition)
    question_clauses = _policy_token_clauses(question)
    if not expected:
        return False
    expected_negative = any(_POLICY_NEGATION.fullmatch(token) for token in expected)
    width = len(expected)
    for actual in question_clauses:
        for start in range(len(actual) - width + 1):
            if not all(_same_policy_token(word, actual[start + offset], predicate=(offset == 0))
                       for offset, word in enumerate(expected)):
                continue
            # Include a negator near the predicate, or between a broad modal
            # condition and its action, in the local polarity frame.
            frame_start = max(0, start - 3)
            frame_end = min(len(actual), start + width + 4)
            actual_negative = any(_POLICY_NEGATION.fullmatch(token)
                                  for token in actual[frame_start:frame_end])
            if expected_negative == actual_negative:
                return True
    return False


def _unique(ids: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(x) for x in ids if x))


def _is_done(value: Any) -> bool:
    return _text_key(str(value or "")) in {"done", "complete", "completed", "finished", "完了", "済", "済み"}


class ProjectFrame:
    """Typed frame and deterministic conductor over one append-only ``Memory``."""

    def __init__(
        self,
        memory: Memory | str | Path,
        *,
        asker: Optional[Callable[[str], str]] = None,
        command_runner: Optional[Callable[[Mapping[str, Any]], Any]] = None,
    ):
        install_conductor_kinds()
        self.memory = memory if isinstance(memory, Memory) else Memory(str(memory), asker=asker)
        self.command_runner = command_runner

    # ---- typed writes -------------------------------------------------
    def _write(self, kind: str, slots: dict[str, str], witness: dict, *, supersedes: Optional[str] = None) -> dict:
        return self.memory.write(kind, "conductor", witness=witness, supersedes=supersedes, **slots)

    def add_goal(self, project: str, acceptance_item: str) -> dict:
        item = self._active_acceptance_by_name(acceptance_item)
        item_task = str(item.get("witness", {}).get("acceptance", {}).get("task_id", "")) if item else ""
        if item is None or _term_key(item_task) != _term_key(project):
            raise WriteRejected("GOAL must point to an active ACCEPTANCE item for the same project")
        existing = [r for r in self._active() if r["kind"] == "GOAL" and
                    _term_key(r["slots"]["subject"]) == _term_key(project) and
                    _term_key(r["slots"]["value"]) == _term_key(acceptance_item)]
        if len(existing) == 1:
            return existing[0]
        return self._write("GOAL", {"subject": project, "value": acceptance_item},
                           {"kind": "testimony", "by": "frame author", "completion_shape": "acceptance item"})

    def add_acceptance(
        self,
        task_id: str,
        item: str,
        *,
        witness_kind: Optional[str] = None,
        target: Optional[Mapping[str, Any]] = None,
        human_judged: bool = False,
        independent: bool = False,
    ) -> dict:
        if human_judged:
            if witness_kind is not None or target is not None:
                raise WriteRejected("human-judged acceptance cannot also specify a machine witness")
            check = "human judged"
            witness_spec: dict[str, Any] = {"kind": "human-judged"}
        else:
            if witness_kind not in {"file_sha256", "text_in_file", "git_commit", "command_exit"}:
                raise WriteRejected("acceptance needs a supported machine witness or human_judged=True")
            if not isinstance(target, Mapping):
                raise WriteRejected("machine witness needs a structured target")
            witness_spec = self._validate_acceptance_target(witness_kind, target)
            check = {"file_sha256": "file sha256", "text_in_file": "text in file",
                     "git_commit": "git commit", "command_exit": "command exit"}[witness_kind]
            witness_spec["kind"] = witness_kind
        spec = {"task_id": task_id, "item": item, "witness": witness_spec,
                "human_judged": bool(human_judged), "independent": bool(independent)}
        return self._write("ACCEPTANCE", {"subject": item, "check": check},
                           {"kind": "testimony", "by": "frame author", "acceptance": spec})

    @staticmethod
    def _validate_acceptance_target(kind: str, target: Mapping[str, Any]) -> dict[str, Any]:
        value = dict(target)
        if kind == "file_sha256":
            if not isinstance(value.get("path"), str) or not isinstance(value.get("sha256"), str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value["sha256"]):
                raise WriteRejected("file_sha256 target requires path and a 64-digit digest")
            return {"path": value["path"], "sha256": value["sha256"].lower()}
        if kind == "text_in_file":
            if not isinstance(value.get("path"), str) or not value.get("path") or not isinstance(value.get("needle"), str) or not value["needle"]:
                raise WriteRejected("text_in_file target requires path and needle")
            return {"path": value["path"], "needle": value["needle"]}
        if kind == "git_commit":
            if not isinstance(value.get("repo"), str) or not isinstance(value.get("commit"), str) or not re.fullmatch(r"[0-9a-fA-F]{40,64}", value["commit"]):
                raise WriteRejected("git_commit target requires repo and a full commit id")
            return {"repo": value["repo"], "commit": value["commit"].lower()}
        if kind == "command_exit":
            command = value.get("command")
            exit_code = value.get("expected_exit", 0)
            if (not isinstance(command, (str, list, tuple)) or
                    (isinstance(command, (list, tuple)) and (not command or not all(isinstance(x, str) and x for x in command))) or
                    isinstance(command, str) and not command.strip() or
                    isinstance(exit_code, bool) or not isinstance(exit_code, int)):
                raise WriteRejected("command_exit target requires a command and integer expected_exit")
            return {"command": list(command) if isinstance(command, (list, tuple)) else command,
                    "expected_exit": exit_code}
        raise WriteRejected("unsupported acceptance witness")

    def add_order(self, phase_a: str, phase_b: str, reason_record_id: str) -> dict:
        reason = self._active_record(reason_record_id)
        if reason is None or reason.get("kind") not in {"DECISION", "INVARIANT"} or not self._authority_unconflicted(reason):
            raise WriteRejected("ORDER must cite an active DECISION or INVARIANT record")
        return self._write("ORDER", {"subject": phase_a, "target": phase_b},
                           {"kind": "testimony", "by": "frame author", "reason_record_id": reason_record_id})

    def add_policy(self, question_kind: str, condition: str, allowed_answer: str, authority_record_id: str) -> dict:
        if question_kind not in QUESTION_KINDS:
            raise WriteRejected("POLICY question_kind is outside the closed question set")
        authority = self._active_record(authority_record_id)
        if authority is None or authority.get("kind") not in {"DECISION", "INVARIANT"} or not self._authority_unconflicted(authority):
            raise WriteRejected("POLICY must cite an active DECISION or INVARIANT record")
        return self._write("POLICY", {"subject": condition, "answer": allowed_answer},
                           {"kind": "testimony", "by": "frame author", "question_kind": question_kind,
                            "condition": condition, "authority_record_id": authority_record_id})

    def add_escalation(
        self,
        condition: str,
        reason: str,
        missing: str,
        *,
        question_kind: Optional[str] = None,
    ) -> dict:
        if question_kind is not None and question_kind not in QUESTION_KINDS:
            raise WriteRejected("ESCALATE question_kind is outside the closed question set")
        if not reason.strip() or not missing.strip():
            raise WriteRejected("ESCALATE needs a reason and missing record kind")
        return self._write("ESCALATE", {"subject": condition, "target": "human"},
                           {"kind": "testimony", "by": "frame author", "condition": condition,
                            "reason": reason, "missing": missing, "question_kind": question_kind})

    def add_decision(self, subject: str, choice: str, *, supersedes: Optional[str] = None) -> dict:
        return self.memory.write("DECISION", "frame author", supersedes=supersedes, subject=subject, choice=choice)

    def add_invariant(self, subject: str, rule: str, *, authority_boundary: bool = False,
                      witness: Optional[Mapping[str, Any]] = None) -> dict:
        support = dict(witness or {"kind": "testimony", "by": "frame author"})
        if authority_boundary:
            support["authority_boundary"] = True
        return self.memory.write("INVARIANT", "frame author", witness=support, subject=subject, rule=rule)

    def add_task(self, task_id: str, state: str) -> dict:
        current = [r for r in self._active() if r["kind"] == "TASK" and
                   _term_key(r["slots"]["subject"]) == _term_key(task_id)]
        if len(current) > 1:
            raise WriteRejected("TASK update needs one active state record to supersede")
        if current and current[0]["slots"]["state"] == state:
            return current[0]
        return self.memory.write("TASK", "frame author", supersedes=current[0]["id"] if current else None,
                                 subject=task_id, state=state)

    def record_verification(
        self,
        acceptance_id: str,
        result: str,
        *,
        verifier_id: str,
        claimant_id: str,
        evidence_ref: str = "",
        template_id: Optional[str] = None,
        supersedes: Optional[str] = None,
    ) -> dict:
        acceptance = self._active_record(acceptance_id)
        if acceptance is None or acceptance.get("kind") != "ACCEPTANCE":
            raise WriteRejected("verification must name an active ACCEPTANCE record")
        spec = acceptance.get("witness", {}).get("acceptance", {})
        if result not in {"PASS", "FAIL"}:
            raise WriteRejected("verification result must be PASS or FAIL")
        if not verifier_id or not claimant_id or verifier_id == claimant_id:
            raise WriteRejected("the verifier must be identified and differ from the claimant")
        if spec.get("independent"):
            if verifier_id.startswith("human:"):
                raise WriteRejected("an independent agent result needs an agent verifier id")
            if template_id != "acceptance_independent_v1":
                raise WriteRejected("independent result must cite the returned verifier template")
        elif spec.get("human_judged"):
            if not verifier_id.startswith("human:"):
                raise WriteRejected("human-judged acceptance needs a human verifier id")
        else:
            raise WriteRejected("this acceptance does not require a separate verification record")
        prior = self._active_verifications(acceptance_id, claimant_id)
        if prior and supersedes != prior[-1]["id"]:
            raise WriteRejected("a new verification must supersede the current active verification")
        if supersedes and (not prior or prior[-1]["id"] != supersedes):
            raise WriteRejected("verification supersession target is not the active verification")
        return self._write("VERIFICATION", {"subject": acceptance["slots"]["subject"], "result": result},
                           {"kind": "testimony", "by": verifier_id, "verifier_id": verifier_id,
                            "claimant_id": claimant_id, "acceptance_id": acceptance_id,
                            "evidence_ref": evidence_ref, "independent": bool(spec.get("independent")),
                            "human_judged": bool(spec.get("human_judged")), "template_id": template_id},
                           supersedes=supersedes)

    # ---- answer path --------------------------------------------------
    def answer(self, question: AgentQuestion) -> Reply:
        if not isinstance(question, AgentQuestion) or not isinstance(question.text, str) or not question.text.strip():
            return self._escalate("OTHER", "question is missing or malformed", "agent question")
        if question.options is not None and (not isinstance(question.options, list) or
                                             not all(isinstance(x, str) and x.strip() for x in question.options)):
            return self._escalate("OTHER", "option list is malformed", "closed option list")
        kind = classify_question(question.text, question.options)

        protected = self._protected_action(question.text, *(question.options or []))
        if protected:
            ids = self._authority_record_ids()
            explicit = self._matching_escalation(question.text, kind)
            if isinstance(explicit, Reply):
                ids.extend(explicit.record_ids)
            elif explicit:
                ids.extend([explicit["id"]])
            return self._escalate(kind, f"outside frame authority: {protected}", "human", ids)

        explicit = self._matching_escalation(question.text, kind)
        if isinstance(explicit, Reply):
            return explicit
        if explicit:
            return self._escalate(kind, explicit.get("witness", {}).get("reason", "frame escalation condition"),
                                  explicit.get("witness", {}).get("missing", "human"), [explicit["id"]])

        if kind == "ORDER":
            return self._answer_order()
        if kind == "CHOICE":
            return self._answer_choice(question)
        if kind in {"CONFIRM", "SCOPE"}:
            return self._answer_policy(question, kind)
        if kind == "STATUS":
            return self._answer_status(question)
        return self._escalate(kind, "question is outside the closed question set", "typed frame record",
                              self._no_guess_record_ids())

    def _answer_order(self) -> Reply:
        active = self._active()
        task_groups: dict[str, list[dict]] = {}
        for record in active:
            if record["kind"] == "TASK":
                task_groups.setdefault(_term_key(record["slots"]["subject"]), []).append(record)
        conflicted = [record for group in task_groups.values() if len(group) > 1 for record in group]
        if conflicted:
            conflict_keys = {_term_key(record["slots"]["subject"]) for record in conflicted}
            edge_ids = [record["id"] for record in active if record["kind"] == "ORDER" and
                        (_term_key(record["slots"]["subject"]) in conflict_keys or
                         _term_key(record["slots"]["target"]) in conflict_keys)]
            return self._escalate("ORDER", "multiple active TASK records share a task identity", "TASK supersession",
                                  [record["id"] for record in conflicted] + edge_ids)
        tasks = {_term_key(r["slots"]["subject"]): r for r in active if r["kind"] == "TASK"}
        edges = []
        missing_reason = []
        for edge in active:
            if edge["kind"] != "ORDER":
                continue
            witness = edge.get("witness") or {}
            reason = self._active_record(witness.get("reason_record_id", ""))
            if reason is None or reason.get("kind") not in {"DECISION", "INVARIANT"} or not self._authority_unconflicted(reason):
                continue
            before = _term_key(edge["slots"]["subject"])
            after = _term_key(edge["slots"]["target"])
            task = tasks.get(before)
            if task is None:
                missing_reason.append(edge["id"])
                continue
            if task["slots"]["state"] != "完了":
                continue
            after_task = tasks.get(after)
            if after_task is None:
                missing_reason.append(edge["id"])
                continue
            if after_task["slots"]["state"] == "完了":
                continue
            edges.append((after, edge, task, after_task, reason))
        targets = {entry[0] for entry in edges}
        if len(targets) == 1:
            target = next(iter(targets))
            chosen = [entry for entry in edges if entry[0] == target]
            ids = [item[1]["id"] for item in chosen]
            ids.extend(item[2]["id"] for item in chosen)
            ids.extend(item[3]["id"] for item in chosen)
            ids.extend(item[4]["id"] for item in chosen)
            canonical_target = chosen[0][3]["slots"]["subject"]
            return Reply("ANSWER", canonical_target, _unique(ids), "the active ORDER and TASK records identify one ready successor")
        if len(targets) > 1:
            return self._escalate("ORDER", "more than one successor is ready; ties abstain", "ORDER priority", 
                                  [entry[1]["id"] for entry in edges] + [entry[4]["id"] for entry in edges])
        order_ids = [r["id"] for r in active if r["kind"] == "ORDER"]
        if not order_ids:
            return self._escalate("ORDER", "no active phase ordering determines the next item", "ORDER", self._no_guess_record_ids())
        return self._escalate("ORDER", "predecessor or successor task state is missing", "TASK state",
                              order_ids + missing_reason)

    def _answer_choice(self, question: AgentQuestion) -> Reply:
        if not question.options:
            return self._escalate("CHOICE", "choice question has no closed option list", "vocabulary")
        policy = self._matching_policy(question.text, "CHOICE")
        if isinstance(policy, Reply):
            return policy
        if policy is None:
            return self._escalate("CHOICE", "no active cited POLICY determines this choice", "POLICY",
                                  self._no_guess_record_ids())
        target = policy["answer"]
        mapped: list[tuple[str, str, tuple[str, ...]]] = []
        unresolved: list[Reply] = []
        for option in question.options:
            resolved = self._resolve_option(option, question.text)
            if isinstance(resolved, Reply):
                unresolved.append(resolved)
                continue
            canonical, ids = resolved
            mapped.append((option, canonical, ids))
        if unresolved:
            return self._escalate("CHOICE", unresolved[0].reason, "vocabulary",
                                  list(policy["record_ids"]) + [rid for _, _, ids in mapped for rid in ids] +
                                  [rid for result in unresolved for rid in result.record_ids])
        matching = [item for item in mapped if _term_key(item[1]) == _term_key(target)]
        if len(matching) != 1:
            why = "no listed option matches the policy answer" if not matching else "multiple listed options normalize to the same policy answer"
            return self._escalate("CHOICE", why, "unique option mapping", list(policy["record_ids"]))
        option, canonical, term_ids = matching[0]
        all_option_ids = [record_id for _, _, ids in mapped for record_id in ids]
        if self._protected_action(option):
            return self._escalate("CHOICE", "the selected option invokes an outside-authority action", "human",
                                  list(policy["record_ids"]) + all_option_ids + list(self._authority_record_ids()))
        return Reply("ANSWER", option, _unique(list(policy["record_ids"]) + all_option_ids),
                     f"the active POLICY selects the unique option mapped to {canonical!r}")

    def _answer_policy(self, question: AgentQuestion, kind: str) -> Reply:
        policy = self._matching_policy(question.text, kind)
        if isinstance(policy, Reply):
            return policy
        if policy is None:
            return self._escalate(kind, "no active cited POLICY covers this condition", "POLICY",
                                  self._no_guess_record_ids())
        value = policy["answer"]
        if self._protected_action(value):
            return self._escalate(kind, "the POLICY answer names an outside-authority action", "human",
                                  list(policy["record_ids"]) + list(self._authority_record_ids()))
        return Reply("ANSWER", value, _unique(list(policy["record_ids"])),
                     "the active POLICY is tied to an active DECISION or INVARIANT record")

    def _answer_status(self, question: AgentQuestion) -> Reply:
        claim = question.claimed_state
        task_id = claim.get("task_id") if isinstance(claim, Mapping) else None
        claimed = claim.get("state") if isinstance(claim, Mapping) else claim
        if not task_id:
            mentioned = [r["slots"]["subject"] for r in self._active()
                         if r["kind"] == "GOAL" and _text_key(r["slots"]["subject"]) in _text_key(question.text)]
            mentioned = list(dict.fromkeys(mentioned))
            if len(mentioned) == 1:
                task_id = mentioned[0]
        if not task_id:
            return self._escalate("STATUS", "the task identity is not explicit", "task_id", self._no_guess_record_ids())
        if _is_done(claimed):
            evidence = dict(claim) if isinstance(claim, Mapping) else {}
            return self.verify_claim(str(task_id), evidence)
        states = [r for r in self._active() if r["kind"] == "TASK" and
                  _term_key(r["slots"]["subject"]) == _term_key(str(task_id))]
        if len(states) == 1 and states[0]["slots"]["state"] != "完了":
            return Reply("ANSWER", states[0]["slots"]["state"], (states[0]["id"],),
                         "the active TASK record supplies the current non-complete state")
        if len(states) > 1:
            return self._escalate("STATUS", "multiple active TASK records conflict", "TASK supersession",
                                  [r["id"] for r in states])
        return self.verify_claim(str(task_id), dict(claim) if isinstance(claim, Mapping) else {})

    def verify_claim(self, task_id: str, evidence: Optional[Mapping[str, Any]]) -> Reply:
        """Check every acceptance witness; ask for a separate verifier when required.

        ``evidence`` may include ``claimant_id`` and a previously recorded
        verification record is read from the append-only Memory.  Commands are
        passed only to the injected runner; this module never launches them.
        """
        evidence = dict(evidence or {})
        goals = [r for r in self._active() if r["kind"] == "GOAL" and
                 _term_key(r["slots"]["subject"]) == _term_key(task_id)]
        if not goals:
            return self._escalate("STATUS", "the task has no active completion shape", "GOAL", self._no_guess_record_ids())
        item_names = list(dict.fromkeys(r["slots"]["value"] for r in goals))
        if not item_names:
            return self._escalate("STATUS", "the task has no acceptance items", "ACCEPTANCE", [r["id"] for r in goals])
        acceptance_by_name: dict[str, dict] = {}
        for item in item_names:
            records = [r for r in self._active() if r["kind"] == "ACCEPTANCE" and
                       _term_key(r["slots"]["subject"]) == _term_key(item) and
                       _term_key(str(r.get("witness", {}).get("acceptance", {}).get("task_id", ""))) == _term_key(task_id)]
            if len(records) != 1:
                return self._escalate("STATUS", f"acceptance item {item!r} is missing or conflicted", "ACCEPTANCE",
                                      [g["id"] for g in goals] + [r["id"] for r in records])
            acceptance_by_name[item] = records[0]
        claimant_id = evidence.get("claimant_id")
        evidence_ids: list[str] = [g["id"] for g in goals]
        for item in item_names:
            acceptance = acceptance_by_name[item]
            evidence_ids.append(acceptance["id"])
            spec = acceptance.get("witness", {}).get("acceptance", {})
            witness = spec.get("witness", {})
            if spec.get("human_judged"):
                machine_ok = True
            else:
                failure = self._check_acceptance_witness(witness)
                if failure:
                    missing = "human" if failure.startswith("acceptance target crosses the frame authority boundary") else witness.get("kind", "ACCEPTANCE witness")
                    return self._escalate("STATUS", f"acceptance witness failed for {item!r}: {failure}",
                                          missing, evidence_ids)
                machine_ok = True
            if not machine_ok:
                return self._escalate("STATUS", f"acceptance witness did not pass for {item!r}", "ACCEPTANCE witness", evidence_ids)
            if spec.get("independent") or spec.get("human_judged"):
                if spec.get("independent") and not claimant_id:
                    return self._escalate("STATUS", "independent verification needs a claimant identity", "claimant_id", evidence_ids)
                checks = [v for v in self._active_verifications(acceptance["id"], str(claimant_id or ""))
                          if self._valid_verification(v, spec, str(claimant_id or ""))]
                outcomes = {v["slots"].get("result") for v in checks}
                if len(outcomes) > 1:
                    return self._escalate("STATUS", f"verification records conflict for {item!r}",
                                          "VERIFICATION supersession", evidence_ids + [v["id"] for v in checks])
                passed = [v for v in checks if v["slots"].get("result") == "PASS"]
                if passed:
                    evidence_ids.append(passed[-1]["id"])
                    continue
                failed = [v for v in checks if v["slots"].get("result") == "FAIL"]
                if failed:
                    return self._escalate("STATUS", f"independent verification failed for {item!r}", "independent verifier", evidence_ids + [failed[-1]["id"]])
                if spec.get("independent"):
                    return self._ask_verifier(task_id, item, acceptance, claimant_id, evidence_ids)
                return self._escalate("STATUS", f"human judgment is required for {item!r}", "human verification", evidence_ids)
        return Reply("ANSWER", "done", _unique(evidence_ids),
                     "every active GOAL acceptance item has a passing machine or typed verification witness")

    def _check_acceptance_witness(self, witness: Mapping[str, Any]) -> Optional[str]:
        kind = witness.get("kind")
        target = {k: v for k, v in witness.items() if k != "kind"}
        inspect = str(target)
        if kind == "command_exit":
            command = target.get("command", "")
            inspect = " ".join(command) if isinstance(command, (list, tuple)) else str(command)
        if self._protected_action(inspect):
            return "acceptance target crosses the frame authority boundary"
        if kind in {"file_sha256", "text_in_file", "git_commit"}:
            state = check_witness({"kind": kind, **target})
            return None if state == "FRESH" else f"witness state is {state}"
        if kind == "command_exit":
            if self.command_runner is None:
                return "no injected command runner is available"
            try:
                outcome = self.command_runner(target)
            except Exception as exc:
                return f"injected runner failed: {type(exc).__name__}"
            if isinstance(outcome, Mapping):
                outcome = outcome.get("returncode", outcome.get("exit_code"))
            if isinstance(outcome, bool) or not isinstance(outcome, int):
                return "injected runner did not return an integer exit code"
            if outcome != target.get("expected_exit", 0):
                return f"command exit {outcome} did not equal expected {target.get('expected_exit', 0)}"
            return None
        return "unknown acceptance witness kind"

    def _ask_verifier(self, task_id: str, item: str, acceptance: dict, claimant_id: str,
                      evidence_ids: list[str]) -> Reply:
        template_id = "acceptance_independent_v1"
        spec = acceptance.get("witness", {}).get("acceptance", {})
        prompt = (
            f"Independently verify task {task_id!r}, acceptance item {item!r}. "
            f"The claimant is {claimant_id!r}; the acceptance record is {acceptance['id']}. "
            "You must be a different agent. Check the stated witness specification "
            f"{spec.get('witness')!r}; do not rely on the claimant's completion assertion. "
            "Return PASS or FAIL and identify the evidence inspected."
        )
        verifier_spec = {
            "template_id": template_id,
            "target": item,
            "acceptance_record_id": acceptance["id"],
            "claimant_id": claimant_id,
            "prompt": prompt,
            "result_schema": {"result": ["PASS", "FAIL"], "evidence_ref": "string"},
            "must_be_different_agent_from": claimant_id,
        }
        return Reply("ASK_VERIFIER", record_ids=_unique(evidence_ids),
                     why="the deterministic acceptance witness passed; an independent acceptance item needs another agent",
                     question_kind="STATUS", template_id=template_id, target=item, spec=verifier_spec)

    # ---- typed retrieval helpers -------------------------------------
    def _active(self) -> list[dict]:
        return self.memory.active(require_fresh=True)

    def _active_record(self, record_id: str) -> Optional[dict]:
        for record in self._active():
            if record["id"] == record_id:
                return record
        return None

    def _authority_unconflicted(self, record: dict) -> bool:
        if record.get("kind") not in {"DECISION", "INVARIANT"}:
            return False
        slot = "choice" if record["kind"] == "DECISION" else "rule"
        peers = [r for r in self._active() if r["kind"] == record["kind"] and
                 _term_key(r["slots"]["subject"]) == _term_key(record["slots"]["subject"])]
        values = {_term_key(r["slots"][slot]) for r in peers}
        return len(values) == 1

    def _active_acceptance_by_name(self, item: str) -> Optional[dict]:
        hits = [r for r in self._active() if r["kind"] == "ACCEPTANCE" and
                _term_key(r["slots"]["subject"]) == _term_key(item)]
        return hits[0] if len(hits) == 1 else None

    def _active_verifications(self, acceptance_id: str, claimant_id: str) -> list[dict]:
        return [r for r in self._active() if r["kind"] == "VERIFICATION" and
                r.get("witness", {}).get("acceptance_id") == acceptance_id and
                r.get("witness", {}).get("claimant_id") == claimant_id]

    @staticmethod
    def _valid_verification(record: dict, acceptance_spec: Mapping[str, Any], claimant_id: str) -> bool:
        witness = record.get("witness", {})
        verifier_id = witness.get("verifier_id")
        if record.get("slots", {}).get("result") not in {"PASS", "FAIL"} or not verifier_id or verifier_id == claimant_id:
            return False
        if acceptance_spec.get("independent"):
            return (bool(witness.get("independent")) and not str(verifier_id).startswith("human:") and
                    witness.get("template_id") == "acceptance_independent_v1" and
                    isinstance(witness.get("evidence_ref"), str) and bool(witness["evidence_ref"].strip()))
        if acceptance_spec.get("human_judged"):
            return bool(witness.get("human_judged")) and str(verifier_id).startswith("human:")
        return False

    def _matching_policy(self, text: str, question_kind: str) -> Optional[dict] | Reply:
        active = {r["id"]: r for r in self._active()}
        hits = []
        for record in active.values():
            if record["kind"] != "POLICY":
                continue
            witness = record.get("witness") or {}
            if witness.get("question_kind") != question_kind:
                continue
            authority = active.get(witness.get("authority_record_id", ""))
            if authority is None or authority.get("kind") not in {"DECISION", "INVARIANT"}:
                continue
            if not self._authority_unconflicted(authority):
                continue
            condition = str(witness.get("condition", record["slots"]["subject"]))
            key = _text_key(condition)
            if not key or not _policy_phrase_matches(condition, text):
                continue
            hits.append((len(key), record, authority))
        if not hits:
            return None
        longest = max(x[0] for x in hits)
        selected = [x for x in hits if x[0] == longest]
        answers = {_term_key(x[1]["slots"]["answer"]) for x in selected}
        if len(answers) != 1:
            return self._escalate(question_kind, "equally specific active POLICY records conflict", "POLICY supersession",
                                  [r["id"] for _, r, _ in selected] + [a["id"] for _, _, a in selected])
        return {"answer": selected[0][1]["slots"]["answer"],
                "record_ids": _unique([x[1]["id"] for x in selected] + [x[2]["id"] for x in selected])}

    def _matching_escalation(self, text: str, question_kind: str) -> Optional[dict] | Reply:
        query = _text_key(text)
        hits = []
        for record in self._active():
            if record["kind"] != "ESCALATE":
                continue
            witness = record.get("witness") or {}
            scope = witness.get("question_kind")
            if scope not in (None, question_kind):
                continue
            condition = _text_key(str(witness.get("condition", record["slots"]["subject"])))
            if condition and condition in query:
                hits.append((len(condition), record))
        if not hits:
            return None
        longest = max(length for length, _ in hits)
        best = [record for length, record in hits if length == longest]
        if len(best) == 1:
            return best[0]
        return self._escalate(question_kind, "equally specific ESCALATE records conflict", "ESCALATE supersession",
                              [record["id"] for record in best])

    def _frame_terms(self) -> dict[str, tuple[str, list[str]]]:
        """Normalized vocabulary term -> canonical spelling and supporting records."""
        terms: dict[str, tuple[str, list[str]]] = {}
        for record in self._active():
            slots = record.get("slots", {})
            for value in slots.values():
                if not isinstance(value, str) or not value.strip():
                    continue
                key = _term_key(value)
                if not key:
                    continue
                if key not in terms:
                    terms[key] = (value, [])
                terms[key][1].append(record["id"])
            if record["kind"] == "ALIAS":
                original = slots.get("subject")
                canonical = slots.get("value")
                if original and canonical:
                    terms[_term_key(original)] = (canonical, [record["id"]])
        return terms

    def _resolve_option(self, option: str, context: str) -> tuple[str, tuple[str, ...]] | Reply:
        key = _term_key(option)
        terms = self._frame_terms()
        if key in terms:
            canonical, ids = terms[key]
            # Existing testimony aliases are canonicalized by their ALIAS record.
            alias_ids = [r["id"] for r in self._active() if r["kind"] == "ALIAS" and
                         _term_key(r["slots"]["subject"]) == key]
            return canonical, _unique(list(ids) + alias_ids)
        active_aliases = [r for r in self._active() if r["kind"] == "ALIAS" and
                          r.get("witness", {}).get("scope") == "agent-option" and
                          r.get("witness", {}).get("word") == option]
        alias_values = {_term_key(r["slots"].get("value", "")) for r in active_aliases}
        if len(alias_values) > 1:
            return self._escalate("CHOICE", f"active testimony aliases conflict for {option!r}", "ALIAS supersession",
                                  [r["id"] for r in active_aliases])
        existing = self.memory.aliases.get(("agent-option", option))
        if existing:
            if existing.get("status") != "ADOPT" or not existing.get("choice"):
                return self._escalate("CHOICE", f"closed-choice resolution for {option!r} was {existing.get('status')}", "vocabulary")
            if not active_aliases:
                return self._escalate("CHOICE", "adopted alias has no typed testimony record", "alias record")
            if _term_key(str(existing["choice"])) != next(iter(alias_values)):
                return self._escalate("CHOICE", "alias event and typed testimony disagree", "ALIAS consistency",
                                      [r["id"] for r in active_aliases])
            return str(existing["choice"]), _unique([r["id"] for r in active_aliases])
        resolver = self.memory.resolver
        if resolver is None:
            return self._escalate("CHOICE", f"option {option!r} is outside the frame vocabulary", "vocabulary")
        frame_terms = sorted({canonical for canonical, _ in terms.values()}, key=lambda x: (_term_key(x), x))
        if not frame_terms:
            return self._escalate("CHOICE", "the frame has no canonical terms to resolve against", "vocabulary")
        result = resolver.resolve(option, frame_terms, context=context)
        alias_event = {"op": "alias", "scope": "agent-option", "word": option,
                       "choice": result.get("choice"), "status": result.get("status"),
                       "asks": result.get("asks", []), "by": "llm-closed-choice",
                       "support": "testimony", "ts": self.memory.now()}
        self.memory._append(alias_event)
        if result.get("status") != "ADOPT" or not result.get("choice"):
            return self._escalate("CHOICE", f"closed-choice resolution for {option!r} was {result.get('status')}", "vocabulary")
        alias_key = "term" + hashlib.sha256(option.encode("utf-8")).hexdigest()[:12]
        alias_record = self._write("ALIAS", {"subject": alias_key, "value": str(result["choice"])},
                                   {"kind": "testimony", "by": "llm-closed-choice", "scope": "agent-option",
                                    "word": option, "asks": result.get("asks", []), "support": "testimony"})
        return str(result["choice"]), (alias_record["id"],)

    def _protected_action(self, *parts: Any) -> Optional[str]:
        text = _text_key(" ".join(str(part) for part in parts if part is not None))
        for label, pattern in _PROTECTED_PATTERNS:
            if pattern.search(text):
                return label
        if _OUTWARD_RECIPIENT.search(text):
            return "outward sharing"
        return None

    def _authority_record_ids(self) -> list[str]:
        return [r["id"] for r in self._active() if r["kind"] == "INVARIANT" and
                r.get("witness", {}).get("authority_boundary")]

    def _no_guess_record_ids(self) -> list[str]:
        out = [r["id"] for r in self._active() if r["kind"] == "INVARIANT" and
               ("guess" in str(r["slots"].get("rule", "")).casefold() or "推測" in str(r["slots"].get("rule", "")) or
                "棄権" in str(r["slots"].get("rule", "")))]
        return out or self._authority_record_ids()

    @staticmethod
    def _escalate(question_kind: str, reason: str, missing: str,
                  record_ids: Optional[list[str] | tuple[str, ...]] = None) -> Reply:
        return Reply("ESCALATE", record_ids=_unique(record_ids or ()), reason=reason,
                     missing=missing, question_kind=question_kind)


__all__ = [
    "AgentQuestion", "ProjectFrame", "Reply", "QUESTION_KINDS", "classify_question",
    "install_conductor_kinds",
]
