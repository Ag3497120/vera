"""W5-d step 9.3: one line per failure that is not in the baseline, with the declared conflict (K1..K5) or the environment cause it belongs to.
Reads new_failures.txt; writes new_failures_explained.txt ("<id>\\t<label>: <reason>"). A failure that fits none gets the label 'UNEXPLAINED' (then the code, not the test, must be fixed)."""
import sys
from pathlib import Path

A = Path(__file__).resolve().parent.parent
rows = [l.strip() for l in (A / "new_failures.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
K3_FORM = ("test_a_document_answer_gets_a_borrowed_form_and_keeps_its_text_and_sources", "test_a_failed_borrowing_leaves_the_human_answer_as_it_was",
           "test_the_borrowing_takes_no_role_from_the_generated_sentence_end_to_end")


def label(i):
    f = i.split("::")[0]
    name = i.split("::")[1] if "::" in i else ""
    if f == "tests/test_question_cross_observe.py":
        return "K1", "W3-c2: a filler whose type was not checked is not a candidate; this old test expects FILLED/TIE without a type-giving placement"
    if f == "tests/attack/w3c2/test_attack_w3c2_question_cross.py":
        return "K1", "attack copy: expects TIE/FILLED of fillers that no placement types (K1's two misses)"
    if f.startswith("tests/test_routing_from_text") or f == "tests/attack/test_attack_w5b_wave2.py":
        return "K2", "R1: a Japanese name with no placement answer and no naming sentence is NAME_UNVERIFIED; this old test gives the name no placement (or, for the attack copy of R2, the name has none)"
    if f == "tests/test_basis_policy_form.py" and name in K3_FORM:
        return "K3", "A1: the source text must be in a document that was really handed over; this old test hands over a memo.txt that does not exist"
    if f == "tests/test_basis_policy_w5c_r3.py" and "recorded_yes_still_lifts_a_generated_answer" in name:
        return "K4", "D1: a recorded yes lifts only the very sentence now generated; this old test confirms another sentence (OTHER_CLAIM)"
    if f == "tests/test_basis_policy_w5c_r3.py":
        return "K3", "A1: the source text must be in a document that was really handed over; this old test hands over a memo.txt that does not exist"
    if f == "tests/attack/w3a3/test_attack_w3a3_r6.py":
        return "K5", "W3-a3 A1: the 48 generated-frame upgrades are not all CONFIRMED any more (13 are NOT_CONFIRMED); the attack copy states the old invariant"
    if "test_bs_end_to_end" in f and "test_s6" in name:
        return "環境由来", "the ticket says: fails while verantyx/ has uncommitted changes (checks the clean tree)"
    if "test_p4_abilities" in f and "test_speech_act_drafts" in name:
        return "環境由来", "named as environment-caused in the ticket"
    if "test_one_trace" in f or "test_one_trace" in name:
        return "環境由来", "named as environment-caused in the ticket"
    return "UNEXPLAINED", "no declared conflict or environment cause fits"


out = []
for i in rows:
    lab, why = label(i)
    out.append("%s\t%s: %s" % (i, lab, why))
(A / "new_failures_explained.txt").write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")
from collections import Counter
print(dict(Counter(l.split("\t")[1].split(":")[0] for l in out)))
sys.exit(1 if any("\tUNEXPLAINED" in l for l in out) else 0)
