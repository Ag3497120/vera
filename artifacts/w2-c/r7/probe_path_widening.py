# widening check for S-C: for an allowlist with an upper-case entry and a lower-case one, does any path question answer
# differently (round-6 code vs round-7 code)?  Only answer -> escalate is allowed; escalate -> answer must not occur.
import importlib.machinery, importlib.util, os, sys, tempfile
from pathlib import Path
import verantyx
sys.path.insert(0, "tests")
import test_conduct_ask_traps6 as T
here = os.path.dirname(os.path.abspath(__file__))
name = "verantyx.ca_probe_r6"
loader = importlib.machinery.SourceFileLoader(name, os.path.join(here, "conduct_ask_r6.py.txt"))
spec = importlib.util.spec_from_loader(name, loader); old = importlib.util.module_from_spec(spec); old.__package__ = "verantyx"
sys.modules[name] = old; loader.exec_module(old)
import verantyx.conduct_ask as new
d = Path(tempfile.mkdtemp())
paths = ["App", "app", "APP", "aPp", "Kiosk", "kiosk", "KIOSK", "ＡＰＰ", "tests", "Tests"]
tails = ["/x.py", "/Sub/Y.py", "/sub/y.py", "", "/"]
n = chg = esc2ans = ans2esc = 0
for w1 in ("App", "app", "kiosk", "Kiosk"):
    p = d / f"{w1}.md"; p.write_text(T.FERRY.replace("W1: kiosk", f"W1: {w1}"), encoding="utf-8")
    for a in paths:
        for t in tails:
            q = f"Can I edit {a}{t}?"
            x, y = old.answer_question(str(p), q, ["Yes", "No"]), new.answer_question(str(p), q, ["Yes", "No"])
            sx, sy = (x["decision"], x["answer_option_index"], x["escalate_reason"], x["escalate_detail"]), (y["decision"], y["answer_option_index"], y["escalate_reason"], y["escalate_detail"])
            n += 1
            if sx != sy:
                chg += 1
                if sx[0] == "escalate" and sy[0] == "answer": esc2ans += 1
                if sx[0] == "answer" and sy[0] == "escalate": ans2esc += 1
                print("W1:", w1, "|", q, sx, "->", sy)
print("questions", n, "changed", chg, "escalate->answer", esc2ans, "answer->escalate", ans2esc)
