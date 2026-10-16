"""The wrappers `verantyx.accel.install` puts in place of the plain functions (see verantyx/accel/__init__.py)."""
from __future__ import annotations

from typing import Any

from verantyx import accel


def install(memory: Any) -> None:
    from verantyx.accel import inc
    from verantyx.loom import memcross as mx
    from verantyx.loom import state as lstate
    from verantyx.loom.corpus import Corpus

    plain_build_corpus = memory.build_corpus
    plain_rows_bytes = memory.rows_bytes
    plain_state_sha = memory.MemRun.mem_state_sha
    plain_mx_rows_bytes = mx._rows_bytes
    plain_mx_corpus = mx.Corpus
    row_line = memory.row_line
    canonical = memory.canonical
    sha256_text = memory.sha256_text
    check_memory_rows = memory.check_memory_rows

    plains = {"memory.build_corpus": plain_build_corpus, "memory.rows_bytes": plain_rows_bytes, "memory.MemRun.mem_state_sha": plain_state_sha, "memcross._rows_bytes": plain_mx_rows_bytes}
    state = {"checked": False}

    def pins_ok() -> None:
        """First use of an accelerated path: the references must be the functions the wrappers were written against (sha256 of their source, accel.PINS)."""
        if state["checked"]:
            return
        for key, fn in plains.items():
            got = accel.src_pin(fn)
            if got != accel.PINS[key]:
                raise accel.AccelDrift("%s changed (source sha %s, pinned %s): re-read verantyx/accel/_wrap.py against it, then re-pin (verantyx/accel/__init__.py PINS)" % (key, got, accel.PINS[key]))
        state["checked"] = True

    memory._ACCEL_PINS = lambda: {k: accel.src_pin(f) for k, f in plains.items()}

    def rows_bytes(rows):
        if accel.mode() == "py":
            return plain_rows_bytes(rows)
        pins_ok()
        out = inc.rows_bytes(rows, row_line)
        if accel.check():
            accel._same("rows_bytes", out, plain_rows_bytes(rows))
        return out

    def build_corpus(rows):
        if accel.mode() == "py":
            return plain_build_corpus(rows)
        pins_ok()
        check_memory_rows(rows)
        c = inc.corpus_of_rows(rows, inc.row_lines(rows, row_line))
        if accel.check():
            _same_corpus(c, Corpus(plain_rows_bytes(rows)))
        return c

    def mem_state_sha(self):
        if accel.mode() == "py":
            return plain_state_sha(self)
        pins_ok()
        mem = {"sentences": len(self.rows), "memory_sha": memory.mem_sha(self.rows), "writes": self.counts["writes"], "recalls": self.counts["recalls"]}
        if self.v2plus:
            mem["v2"] = {"topic": self.topic, **self.counts2}
        if self.superseded:
            mem["superseded"] = [[k, v["by"], v["session"], v["reason"]] for k, v in sorted(self.superseded.items())]
        if self.v4:
            mem["v4"] = {"index": self.builder.index().index_sha, "bridges": self.counts4["bridges"]}
            if self.view is not None:
                mem["v4"]["views"] = self.counts4["views"]
        lj = inc.loom_json(self.state, canonical, lstate.LoomState)
        if lj is None:
            return plain_state_sha(self)
        out = sha256_text('{"loom":' + lj + ',"mem":' + canonical(mem) + "}")
        if accel.check():
            accel._same("mem_state_sha", out, plain_state_sha(self))
        return out

    def mx_rows_bytes(rows):
        if accel.mode() == "py":
            return plain_mx_rows_bytes(rows)
        pins_ok()
        return inc.mx_rows_bytes(rows)

    def mx_corpus(data):
        if accel.mode() == "py":
            return plain_mx_corpus(data)
        pins_ok()
        return inc.corpus_of(data)

    memory.build_corpus = build_corpus
    memory.rows_bytes = rows_bytes
    memory.MemRun.mem_state_sha = mem_state_sha
    mx._rows_bytes = mx_rows_bytes
    mx.Corpus = mx_corpus


def _same_corpus(a: Any, b: Any) -> None:
    """The check mode's comparison of an IncCorpus with the plain Corpus of the same bytes: every object the corpus holds."""
    from verantyx.accel.compare import check_corpora
    check_corpora(a, b)
