"""The scripted weaver (docs/LINE3_LOOM_DESIGN.md 9.3): a deterministic fake model that issues operations.

A script is a list of steps `(tool, args)` or `(tool, args, name)` (the result's uid / cid is bound to `name`, and a later argument
"$name" is replaced by it), or a Python function of a `ScriptedWeaver` (a function of the previous results).  The weaver talks to a
`LoomServer` exactly as a model through MCP would: every call is one ledger row.  `say(text)` is the weaver "answering in free text":
the harness side records only the sha256 and the length (`free_text_dropped`), never the text (design 7.2), and nothing of it is
ever output.

`weave_tokyo` is the worked example of design 3.5, 「東京は日本の首都です」, as the exact operation list of the design (row i = op i).
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Sequence, Tuple

from verantyx.loom.mcp import LoomServer


class ScriptedWeaver:
    def __init__(self, server: LoomServer, task_id: str, model: str = "scripted-weaver", run_id: Optional[str] = None) -> None:
        self.server = server
        self.task_id = task_id
        self.model = model
        self.run_id: Optional[str] = None
        self.bound: Dict[str, str] = {}
        self.log: List[Tuple[str, dict, dict]] = []
        self._want_id = run_id

    # -- the model's side --------------------------------------------------------------------------------------------
    def begin(self) -> dict:
        res = self.server.begin(self.task_id, self.model, self._want_id)
        if res.get("ok"):
            self.run_id = res["run_id"]
        self.log.append(("begin", {"task_id": self.task_id, "model": self.model}, res))
        return res

    def call(self, tool: str, **args: Any) -> dict:
        res = self.server.call(tool, dict(args, run_id=self.run_id))
        self.log.append((tool, args, res))
        return res

    def say(self, text: str) -> None:
        """Answer in plain text.  Only the sha256 and the length reach the ledger; the text is dropped."""
        self.server.harness(self.run_id, "free_text_dropped", {"sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "chars": len(text)})

    def done(self) -> None:
        """The model stops.  If it has not closed the run, the harness appends `abandoned` (design 6.1)."""
        if self.server.closed(self.run_id) is None:
            self.server.harness(self.run_id, "abandoned", {"reason": "no_close"})

    # -- data scripts --------------------------------------------------------------------------------------------------------
    def run(self, steps: Sequence[tuple]) -> dict:
        last: dict = {}
        for st in steps:
            tool, args = st[0], dict(st[1])
            name = st[2] if len(st) > 2 else None
            for k, v in list(args.items()):
                if isinstance(v, str) and v.startswith("$"):
                    args[k] = self.bound[v[1:]]
            last = self.call(tool, **args)
            if name is not None and last.get("ok"):
                self.bound[name] = last.get("uid") or last.get("cid")
        return last


def weave_tokyo(w: ScriptedWeaver) -> dict:
    """Design 3.5, op for op: the three WORD crosses of 「東京は日本の首都です」.  In `record_only` the add of です is refused
    (`constructed_forbidden`) and the weaver, as a function of that result, leaves the third cross out: 「東京は日本の首都」."""
    w.begin()                                                                                   # row 0
    u1 = w.call("add", text="東京", kind="record", tier="WORD")["uid"]                           # 1
    u2 = w.call("add", text="日本", kind="record", tier="WORD")["uid"]                           # 2
    u3 = w.call("add", text="首都", kind="record", tier="WORD")["uid"]                           # 3
    r4 = w.call("add", text="です", kind="constructed")                                          # 4
    c1 = w.call("open_cross", tier="WORD", L=1)["cid"]                                           # 5
    w.call("seat", cid=c1, seat="centre", uid=u1)                                                # 6
    w.call("topic", cid=c1, on=True)                                                             # 7
    c2 = w.call("open_cross", tier="WORD", L=2)["cid"]                                           # 8
    w.call("seat", cid=c2, seat="+x:0", uid=u2)                                                  # 9   日本 on the の arm
    w.call("seat", cid=c2, seat="centre", uid=u3)                                                # 10
    cids = [c1, c2]
    if r4.get("ok"):
        c3 = w.call("open_cross", tier="WORD", L=1)["cid"]                                       # 11
        w.call("seat", cid=c3, seat="centre", uid=r4["uid"])                                     # 12
        cids.append(c3)
    for pos, cid in enumerate(cids):                                                             # 13-15
        w.call("link", cid=cid, pos=pos)
    return w.call("emit")                                                                        # 16


def say_only(w: ScriptedWeaver, text: str = "答えは東京です") -> None:
    """The enforcement control (T-LOOM-30): a weaver that begins, answers in free text, and stops."""
    w.begin()
    w.say(text)
    w.done()
