"""Small closed-vocabulary demo with its own constructed frame and shelf."""
from __future__ import annotations

import json

from verantyx.conductor import ProjectFrame
from verantyx.conductor_vocab import ConductorVocabulary
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


class ClosedChoice:
    """Test asker that can return only the index of a supplied option."""

    def __init__(self, target: str):
        self.target = target
        self.prompts = []
        self.options_seen = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        block = prompt.split("候補:\n", 1)[1].split("\n答え", 1)[0]
        options = [line.split(": ", 1)[1] for line in block.splitlines()]
        self.options_seen.append(tuple(options))
        choice = options.index(self.target) if self.target in options else None
        return json.dumps({"choice": choice}, ensure_ascii=False)


def main() -> None:
    asker = ClosedChoice("公開")
    frame = ProjectFrame(ScratchMemory(asker))
    frame.add_decision("公開工程", "公開")
    frame.add_decision("保管工程", "保管")
    frame.add_decision("確認工程", "点検")

    # Both indexes are constructed from the demo inputs.  The redirect and
    # homonym rows can expose frame candidates but cannot become aliases by
    # themselves.
    vocabulary = ConductorVocabulary(
        frame,
        aliases={"辞書別名": "公開"},
        senses={"出版工程": [
            {"core": "公開", "domain_tag": "publication"},
            {"core": "保管", "domain_tag": "storage"},
        ]},
    )
    allowed = set(vocabulary.frame_terms())

    exact = vocabulary.resolve("公開")
    check(exact.status == "EXACT" and exact.canonical == "公開", "exact frame match")
    check(not asker.prompts, "exact match must precede the asker")
    check(set(exact.record_ids), "exact match carries frame record provenance")
    lazy_exact = ConductorVocabulary(frame).resolve("公開")
    check(lazy_exact.asset_status == ("aliases:NOT_LOADED", "senses:NOT_LOADED"),
          "exact match does not load lexical sidecars")

    indexed_alias_candidates = vocabulary.candidates("辞書別名")
    check(tuple(item.term for item in indexed_alias_candidates) == ("公開",), "redirect narrows only to a frame term")
    check(all(item.term in allowed for item in indexed_alias_candidates), "redirect cannot invent a frame term")
    one_redirect = vocabulary.resolve("辞書別名")
    check(one_redirect.status == "ESCALATE", "a shelf redirect alone cannot be adopted")
    check(not asker.prompts, "single lexical candidate does not trigger a choice")
    check(not any((record.get("witness") or {}).get("word") == "辞書別名"
                   for record in frame._active() if record.get("kind") == "ALIAS"),
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
    check(not asker.prompts, "adopted alias precedes the asker")

    choices = vocabulary.candidates("出版工程")
    check({item.term for item in choices} == {"公開", "保管"}, "all attested senses remain in the closed list")
    check(all(item.term in allowed for item in choices), "senses cannot add frame terms")
    check({tag for item in choices for tag in item.domain_tags} == {"publication", "storage"},
          "sense domain tags stay attached as annotations")
    closed = vocabulary.resolve("出版工程", "工程の候補名を照合する")
    check(closed.status == "ADOPTED" and closed.canonical == "公開", "two closed asks adopt one frame term")
    check(len(asker.prompts) == 2, "closed choice makes exactly two asks")
    check(asker.options_seen[0] == tuple(item.term for item in choices), "first ask receives the closed candidate list")
    check(asker.options_seen[1] == tuple(reversed(asker.options_seen[0])), "second ask changes candidate order")
    check(set(asker.options_seen[0]) == {"公開", "保管"}, "asker sees no term outside the attested frame candidates")
    adopted_record = frame.memory.records[closed.record_ids[0]]
    witness = adopted_record["witness"]
    check(witness["kind"] == "testimony" and witness["by"] == "llm-closed-choice",
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

    vocabulary.memory.resolver = None
    unknown = vocabulary.resolve("未登録語")
    check(unknown.status == "ESCALATE" and unknown.canonical is None, "missing asker escalates")
    check(all(item.term in allowed for item in unknown.candidates), "fallback list remains inside frame vocabulary")
    check(unknown.reason == "no closed-choice asker is configured", "escalation names its missing resolver")
    check(_checks == 31, "all expected demo checks ran")
    print("DEMO OK")


if __name__ == "__main__":
    main()
