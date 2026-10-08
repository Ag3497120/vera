"""What the policy does with the result product code builds in round3's rule-made social frame
(``GeneralRouter._social_frame``: a fixed reply, ``family: conversation`` without an ``origin``).
Run once per tree (PYTHONPATH=<tree>); the first line prints the module path that was loaded."""
import json, sys
from types import SimpleNamespace
from verantyx import basis_policy as bp, round3

print("basis_policy loaded from:", bp.__file__)
for act, text in (("greeting", "こんにちは"), ("thanks", "ありがとう。"), ("farewell", "さようなら")):
    reading = SimpleNamespace(speech_act=SimpleNamespace(value=SimpleNamespace(act=act)), case_frame=None)
    framed = round3.GeneralRouter._social_frame(text, reading)
    for human in (False, True):
        out, rc = bp.apply_to_ask(framed, bp.AskPolicy(human_present=human), query=text, mode="round5",
                                  documents=[])
        n = out["basis_policy"]
        print(json.dumps({"input": text, "human_present": human, "kind": out["kind"], "verdict": out["verdict"],
                          "outcome": n["outcome"], "basis": n["basis"], "source_families": [
                              s.get("family") for s in framed["sources"]]}, ensure_ascii=False))
