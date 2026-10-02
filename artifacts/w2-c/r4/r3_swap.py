# pytest plugin (-p r3_swap): run a test file against the round-3 code (artifacts/w2-c/r4/conduct_ask_r3.py.txt)
import importlib.machinery, importlib.util, os, sys
import verantyx
here = os.path.dirname(os.path.abspath(__file__))
loader = importlib.machinery.SourceFileLoader("verantyx.conduct_ask", os.path.join(here, "conduct_ask_r3.py.txt"))
spec = importlib.util.spec_from_loader("verantyx.conduct_ask", loader)
mod = importlib.util.module_from_spec(spec)
mod.__package__ = "verantyx"
sys.modules["verantyx.conduct_ask"] = mod
loader.exec_module(mod)
verantyx.conduct_ask = mod
