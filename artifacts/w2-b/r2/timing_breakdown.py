"""B8 timing summary: reads the four full-suite runs (base, cand, cand, base) and prints the pytest summary line,
the increase of each pair, and where the increase is (the shared pool of scripted runs is paid by the first test
that needs it, test_conduct_run::test_r1_...; the rest is my own test items).  Usage: python timing_breakdown.py"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

here = Path(__file__).resolve().parent


def summary(name):
    line = (here / f"{name}_pytest.txt").read_text().strip().splitlines()[-1]
    seconds = float(re.search(r" in ([0-9.]+)s", line).group(1))
    return line, seconds


def junit(name):
    out = {}
    for tc in ET.parse(here / f"{name}_junit.xml").getroot().iter("testcase"):
        out[tc.get("classname") + "::" + tc.get("name")] = float(tc.get("time") or 0)
    return out


runs = {n: (summary(n), junit(n)) for n in ("base1", "cand1", "cand2", "base2")}
for n, ((line, secs), _) in runs.items():
    print(f"{n}: {line}")
print()
d1 = runs["cand1"][0][1] - runs["base1"][0][1]
d2 = runs["cand2"][0][1] - runs["base2"][0][1]
print(f"pair 1 (base1 -> cand1): {runs['base1'][0][1]:.2f}s -> {runs['cand1'][0][1]:.2f}s = +{d1:.2f}s")
print(f"pair 2 (cand2 -> base2): {runs['cand2'][0][1]:.2f}s vs {runs['base2'][0][1]:.2f}s = +{d2:.2f}s")
print()
for n, (_, data) in runs.items():
    first = [k for k in data if "test_r1_a_five_second_agent" in k][0]
    mine = sum(v for k, v in data.items() if "test_conduct_verify" in k)
    n_mine = sum(1 for k in data if "test_conduct_verify" in k)
    print(f"{n}: pool (first test that needs it) {data[first]:6.2f}s | my {n_mine} test items {mine:5.2f}s | all other items {sum(data.values()) - data[first] - mine:7.2f}s")
