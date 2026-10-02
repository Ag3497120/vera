# the 3 questions that only the "after" run asked (test_conduct_ask_provenance.py stops at its first failed assert with the
# round-6 code): ask them with the round-6 code (-p r6_swap style load) and with the current code
import importlib.machinery, importlib.util, os, sys
import verantyx
here = os.path.dirname(os.path.abspath(__file__))
def load(path):
    name = "verantyx.ca_probe_r6"
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader); mod = importlib.util.module_from_spec(spec); mod.__package__ = "verantyx"
    sys.modules[name] = mod
    loader.exec_module(mod); return mod
import verantyx.conduct_ask as new
old = load(os.path.join(here, "conduct_ask_r6.py.txt"))
F = "tests/conduct_ask/fixtures/frames/f01_loan.md"
for label, mod in (("round-6 code", old), ("round-7 code", new)):
    print(label)
    for fp, q, o in ((F, "", None), (F, "   ", None), (F.replace("f01_loan", "no_such_frame"), "何を先にしますか？", None)):
        r = mod.answer_question(fp, q, o)
        print("  ", repr(q), "->", r["decision"], r["answer_option_index"], r["answer"], r["escalate_reason"], r["escalate_detail"])
