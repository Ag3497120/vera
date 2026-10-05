"""Small closed-vocabulary demo with its own constructed frame and shelf.

The LLM chooser used here is the real ``verantyx.llm_choice.LLMChooser`` (prompt,
reply parsing, two independent asks, ledger); only the *provider* underneath it
is a local fake that answers from the prompt's candidate lines.  No model is
contacted and no file is written.
"""
from __future__ import annotations

import json
import re

from verantyx.conductor import ProjectFrame
from verantyx.conductor_vocab import ConductorVocabulary
from verantyx.llm_choice import ChoiceLedger, LLMChooser, ProviderReply
from verantyx.memory_frame import Memory, Resolver


_checks = 0


def check(condition: bool, message: str) -> None:
    global _checks
    _checks += 1
    if not condition:
        raise AssertionError(message)


class ScratchMemory(Memory):
    """Memory-compatible event store that does not create a file."""

    def __init__(self, asker=None):
        self.path = None
        self.now = lambda: "2026-10-02T00:00:00"
        self.resolver = Resolver(asker) if asker else None
        self.records = {}
        self.superseded = {}
        self.aliases = {}
        self._view = None

    def _append(self, event):
        self._apply(event)


_LINE = re.compile(r"^(\d+): (.*)$")


class DemoProvider:
    """Local fake provider: reads the prompt's candidate lines and names the target's number."""

    name = "demo-fake"

    def __init__(self, target: str):
        self.target = target
        self.prompts = []
        self.options_seen = []

    def ask(self, prompt: str) -> ProviderReply:
        self.prompts.append(prompt)
        rows = [json.loads(m.group(2)) for m in (_LINE.match(line) for line in prompt.split("\n")) if m]
        options = [row["term"] for row in rows]
        self.options_seen.append(tuple(options))
        choice = options.index(self.target) if self.target in options else None
        return ProviderReply.success(json.dumps({"choice": choice}), self.name, "demo-model", "none")


def build_frame(asker=None) -> ProjectFrame:
    frame = ProjectFrame(ScratchMemory(asker))
    frame.add_decision("公開工程", "公開")
    frame.add_decision("保管工程", "保管")
    frame.add_decision("確認工程", "点検")
    return frame


def main() -> None:
    provider = DemoProvider("公開")
    ledger = ChoiceLedger(None)                       # in-memory chain: the demo writes no file
    chooser = LLMChooser(provider, ledger)            # default order source: random, never sorted
    frame = build_frame()
    shelf = dict(
        aliases={"辞書別名": "公開"},
        senses={"出版工程": [
            {"core": "公開", "domain_tag": "publication"},
            {"core": "保管", "domain_tag": "storage"},
        ]},
    )

    # Both indexes are constructed from the demo inputs.  The redirect and
    # homonym rows can expose frame candidates but cannot become aliases by
    # themselves.
    vocabulary = ConductorVocabulary(frame, chooser=chooser, **shelf)
    allowed = set(vocabulary.frame_terms())

    exact = vocabulary.resolve("公開")
    check(exact.status == "EXACT" and exact.canonical == "公開", "exact frame match")
    check(not provider.prompts, "exact match must precede the asker")
    check(set(exact.record_ids), "exact match carries frame record provenance")
    lazy_exact = ConductorVocabulary(frame).resolve("公開")
    check(lazy_exact.asset_status == ("aliases:NOT_LOADED", "senses:NOT_LOADED"),
          "exact match does not load lexical sidecars")

    indexed_alias_candidates = vocabulary.candidates("辞書別名")
    check(tuple(item.term for item in indexed_alias_candidates) == ("公開",), "redirect narrows only to a frame term")
    check(all(item.term in allowed for item in indexed_alias_candidates), "redirect cannot invent a frame term")

    # Default (no chooser) behaviour is unchanged: a legacy frame whose memory has an asker
    # and a chooser-less vocabulary still refuses to adopt a lone shelf redirect.
    legacy_prompts = []

    def legacy_asker(prompt: str) -> str:
        legacy_prompts.append(prompt)
        return '{"choice": null}'

    legacy_frame = build_frame(legacy_asker)
    legacy = ConductorVocabulary(legacy_frame, **shelf)
    one_redirect = legacy.resolve("辞書別名")
    check(one_redirect.status == "ESCALATE", "a shelf redirect alone cannot be adopted")
    check(not legacy_prompts, "single lexical candidate does not trigger a choice")
    check(not any((record.get("witness") or {}).get("word") == "辞書別名"
                   for record in legacy_frame._active() if record.get("kind") == "ALIAS"),
          "shelf redirect does not write a conductor alias")

    adopted = vocabulary.adopt_alias(
        "公開名", "公開",
        witness={"kind": "testimony", "by": "human:demo-review", "source_ref": "demo:accepted-spelling"},
    )
    alias = vocabulary.resolve("公開名")
    check(alias.status == "ALIAS" and alias.canonical == "公開", "active testimony alias resolves second")
    check(alias.record_ids == (adopted["id"],), "alias cites its testimony record")
    check(frame.memory.records[adopted["id"]]["witness"]["support"] == "testimony",
          "adopted alias remains testimony")
    check(not provider.prompts, "adopted alias precedes the asker")

    choices = vocabulary.candidates("出版工程")
    check({item.term for item in choices} == {"公開", "保管"}, "all attested senses remain in the closed list")
    check(all(item.term in allowed for item in choices), "senses cannot add frame terms")
    check({tag for item in choices for tag in item.domain_tags} == {"publication", "storage"},
          "sense domain tags stay attached as annotations")
    closed = vocabulary.resolve("出版工程", "工程の候補名を照合する", question_kind="CHOICE")
    check(closed.status == "ADOPTED" and closed.canonical == "公開", "two closed asks adopt one frame term")
    check(len(provider.prompts) == 2, "closed choice makes exactly two asks")
    first_ask = [e for e in ledger.entries() if e["type"] == "ask"][0]
    check(provider.options_seen[0] == tuple(first_ask["shown"]) and
          set(provider.options_seen[0]) == {item.term for item in choices},
          "first ask receives the closed candidate list, in the order the ledger recorded")
    check(provider.options_seen[1] != provider.options_seen[0] and
          provider.options_seen[1] == tuple(reversed(provider.options_seen[0])),
          "second ask changes candidate order")
    check(set(provider.options_seen[0]) == {"公開", "保管"}, "asker sees no term outside the attested frame candidates")
    adopted_record = frame.memory.records[closed.record_ids[0]]
    witness = adopted_record["witness"]
    check(witness["kind"] == "testimony" and witness["by"] == "llm-choice",
          "closed-choice adoption records testimony provenance")
    check(len(witness["asks"]) == 2 and witness["support"] == "testimony",
          "both closed asks are retained as testimony")
    check(vocabulary.resolve("出版工程").status == "ALIAS", "adopted closed-choice alias is reusable")

    wrong = vocabulary.adopt_alias(
        "誤訳", "保管",
        witness={"kind": "testimony", "by": "human:initial-review", "source_ref": "demo:initial-label"},
    )
    check(vocabulary.resolve("誤訳").canonical == "保管", "initial alias testimony is active")
    corrected = vocabulary.adopt_alias(
        "誤訳", "公開", supersedes=wrong["id"],
        witness={"kind": "testimony", "by": "human:correction-review", "source_ref": "demo:corrected-label"},
    )
    check(frame.memory.superseded.get(wrong["id"]) == corrected["id"], "wrong alias is superseded")
    check(vocabulary.resolve("誤訳").canonical == "公開", "corrected alias is active")
    check(wrong["id"] not in {r["id"] for r in frame._active()}, "superseded alias leaves the active frame")

    plain = ConductorVocabulary(frame, **shelf)      # no chooser, no memory resolver: the default
    unknown = plain.resolve("未登録語")
    check(unknown.status == "ESCALATE" and unknown.canonical is None, "missing asker escalates")
    check(all(item.term in allowed for item in unknown.candidates), "fallback list remains inside frame vocabulary")
    check(unknown.reason == "no closed-choice asker is configured", "escalation names its missing resolver")

    # New with the real chooser: what the ticket changed on purpose.
    prompts_before = len(provider.prompts)
    single = vocabulary.resolve("辞書別名", "どれを選びますか？", question_kind="CHOICE")
    check(len(provider.prompts) == prompts_before + 2 and single.status == "ADOPTED" and single.canonical == "公開",
          "with a chooser a single candidate is still confirmed by two asks")
    check(single.support == "testimony" and single.outcome == "LLM_ADOPTED" and single.chooser_source == "argument",
          "the adopted mapping is typed as testimony and names where the chooser came from")
    single_witness = frame.memory.records[single.record_ids[0]]["witness"]
    check(single_witness["counts_as_evidence"] is False and single_witness["mapping_type"] == "LLM_TESTIMONY_MAPPING",
          "the adopted mapping is constructed testimony, not evidence")
    check(ledger.verify_adoption(single_witness["ledger_decision_id"], "辞書別名", "公開",
                                 single_witness["candidate_terms"]) is True,
          "the ledger vouches for the adoption, and only for it")
    prompts_before = len(provider.prompts)
    no_role = vocabulary.resolve("未登録語", "実行してよいですか？", question_kind="CONFIRM")
    check(no_role.status == "ESCALATE" and no_role.outcome == "NO_ROLE_CANDIDATES" and
          len(provider.prompts) == prompts_before, "a question kind without an option role asks nothing")
    check(ledger.verify()["lines"] == len(ledger.entries()) > 0, "every ask is in a verifiable ledger chain")
    check(_checks == 37, "all expected demo checks ran")
    print("DEMO OK")


if __name__ == "__main__":
    main()
