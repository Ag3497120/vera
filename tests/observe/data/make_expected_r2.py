"""Round 2 expectations (docs change record 3: an utterance equal to the anchor sentence is skipped when stage ii picks the latest utterance).
Writes expected_r2.jsonl BY HAND-RULE, BEFORE the observer ran under the new rule: every value is derived from the registered rules (docs/OBSERVATION.md P1-P11 with
the P8 definition of U as changed in change record 3), the frozen inputs (placement.json neighbours, ledgers L01 L03 L04 L05 L07 L08 L11 L12, seeds_ja.jsonl) and the
way the six O4 rows and three new cases step through the stages. Nothing here imports verantyx and nothing is copied from an observer output.

Derivation (agent swap on J01; cells A=教授 B=事務員 C=犬; neighbours: 教授->[司書], 事務員->[司書,教授], 犬->[猫,子犬]; stages i, ii-a, ii-b, iii recency, iv decided):
  U is the latest utterance that is not the anchor sentence. recency is None for a cell that no `observed_cell` names (None is on top, then older first).
  O4-a  L03 = 3 decisions (A,A,B), no utterance. Turn 1: U empty; recency None for all; decided A=2 B=1 C=0 -> A | B | C, focus A.
        Turn 1 appends seq 4 (utterance = anchor sentence) and seq 5 (observation, observed_cell A). Turn 2: seq 4 is skipped, U empty; recency: A=5, B,C None;
        decided B=1 C=0 -> B | C | A, focus B. Alternative (equal on i, ii-a, ii-b) exists: B, C. Turn 2 differs. First stage that separates A from B: recency, A's seq 5.
  O4-b  L04 = utterance (anchor sentence of this case) + observation. One candidate (車掌). U empty in both turns. Single cell: FOCUS D6 both turns. No alternative: same output.
  O4-c  L05 = utterance seq 1 "教授にも聞いてみて". Turn 1: U = seq 1; ii-a A=1 B=0 C=0; ii-b B=1 (教授 is a neighbour of 事務員 and occurs in U) C=0 A=0 -> A | B | C, focus A.
        Turn 2: seq 3 (anchor sentence) is skipped, U = seq 1 again; ii-a and ii-b are unchanged, so the order is unchanged: A | B | C, focus A. No alternative (A, B and C
        have three different (ii-a, ii-b) pairs: (1,0) (0,1) (0,0)): same output.
  O4-d  L01 empty. Turn 1: all stages equal -> TIE A,B,C. TIE writes no observed_cell. Turn 2: seq 1 is skipped, U empty, recency None for all -> TIE A,B,C again. Same output.
  O4-e  L07 = decision C. Turn 1: decided C=1 -> C | A,B, focus C. Turn 1 appends seq 2 (utterance = anchor sentence) and seq 3 (observation, observed_cell C).
        Turn 2: seq 2 skipped, U empty; recency: C=3, A and B None; recency (iii) comes before decided (iv): A,B | C, so TIE A,B. Alternative (equal on i..ii-b): A, B. Turn 2 differs.
        First stage that separates C from A (and from B): recency, C's seq 3.
  O4-f  L08 = decision B, utterance seq 2 "別の話", observation seq 3 (observed_cell B). Turn 1: U = seq 2; ii all 0; recency: B=3, A,C None; -> A,C | B (TIE A,C).
        Turn 1 is a TIE: appends seq 4 and seq 5 (tie_cells, no observed_cell). Turn 2: seq 4 skipped, U = seq 2; recency unchanged -> TIE A,C | B. Same output.
  LG11  L11 = utterance seq 1 "教授にも聞いてみて", utterance seq 2 = the anchor sentence. U = seq 1: A | B | C (as LG05 on L05), A's ii-a seq [1], B's ii-b seq [1].
  LG12  as LG11 with the anchor given as the record J01 (its sentence in seeds_ja.jsonl is the anchor sentence).
  LG13  L12 = utterance seq 1 = the anchor sentence. U empty: TIE A,B,C, no ledger seq cited (as LG01 on an empty ledger).
"""
import json
from pathlib import Path

ORDER = ['agent', 'patient', 'recipient', 'goal', 'result', 'source', 'place', 'time', 'instrument']


def d(pred, pol, tense, **arms):
    parts = ';'.join('%s=%s' % (r, arms[r]) for r in ORDER if r in arms)
    return '%s|%s|%s|%s' % (pred, pol, tense, parts)


def give(agent, recipient, patient='辞書', pred='貸す', pol='+'):
    return d(pred, pol, 'past', agent=agent, patient=patient, recipient=recipient)


def say(agent, recipient, patient, verb_past):
    return '%sは%sに%sを%s。' % (agent, recipient, patient, verb_past)


R = lambda t: 'REALIZED:' + t
J01 = give('司書', '学生')
cA, cB, cC = give('教授', '学生'), give('事務員', '学生'), give('犬', '学生')
D6 = give('車掌', '乗客', '切符', '渡す')
rows = []

# ---- the six two-turn rows, replaced under the changed definition of U (they supersede the TURNS rows of expected.jsonl, which stays as it was)
O4 = {
    'O4-a-L03': dict(turn1=dict(focus=cA), turn2=dict(focus=cB, tie=None, ranks=[[cB], [cC], [cA]]), alt_exists=True, changed=True, trace=dict(stage='recency', seq=5)),
    'O4-b-L04': dict(turn1=dict(focus=D6), turn2=dict(focus=D6, tie=None, ranks=[[D6]]), alt_exists=False, changed=False, trace=None),
    'O4-c-L05': dict(turn1=dict(focus=cA), turn2=dict(focus=cA, tie=None, ranks=[[cA], [cB], [cC]]), alt_exists=False, changed=False, trace=None),
    'O4-d-L01': dict(turn1=dict(focus=None, tie=sorted([cA, cB, cC])), turn2=dict(focus=None, tie=sorted([cA, cB, cC]), ranks=[sorted([cA, cB, cC])]), alt_exists=None, changed=False, trace=None),
    'O4-e-L07': dict(turn1=dict(focus=cC), turn2=dict(focus=None, tie=sorted([cA, cB]), ranks=[sorted([cA, cB]), [cC]]), alt_exists=True, changed=True, trace=dict(stage='recency', seq=3)),
    'O4-f-L08': dict(turn1=dict(focus=None, tie=sorted([cA, cC])), turn2=dict(focus=None, tie=sorted([cA, cC]), ranks=[sorted([cA, cC]), [cB]]), alt_exists=None, changed=False, trace=None),
}
for name, e in O4.items():
    rows.append({'case': name, 'outcome': 'TURNS', 'supersedes': 'expected.jsonl', 'o4': e})

# ---- the three new one-turn cases
cells = sorted([cA, cB, cC])
occ = {cA: 'ATTESTED', cB: 'UNKNOWN_NO_INDEX', cC: 'UNKNOWN_NO_INDEX'}
ZERO = {'distance': [], 'utter_verbatim': [], 'utter_neighbor': [], 'recency': [], 'decided': []}


def seqs(**kw):
    s = {k: list(v) for k, v in ZERO.items()}
    s.update(kw)
    return s


def one(case, outcome, focus, tie, ranks, decided_by, ledger_seqs):
    rows.append({'case': case, 'outcome': outcome, 'anchor': J01, 'anchor_realization': R(say('司書', '学生', '辞書', '貸した')), 'anchor_occupied': 'ATTESTED',
                 'observed': cells, 'focus': focus, 'tie': tie, 'ranks': [sorted(g) for g in ranks], 'occupied': occ, 'distances': {c: 1 for c in cells},
                 'decided_by': decided_by, 'ledger_seqs': ledger_seqs})


ls11 = {cA: seqs(utter_verbatim=[1]), cB: seqs(utter_neighbor=[1]), cC: seqs()}
one('LG11', 'FOCUS', cA, None, [[cA], [cB], [cC]], ['utter_verbatim', 'utter_neighbor'], ls11)
one('LG12', 'FOCUS', cA, None, [[cA], [cB], [cC]], ['utter_verbatim', 'utter_neighbor'], ls11)
one('LG13', 'TIE', None, cells, [cells], [], {cA: seqs(), cB: seqs(), cC: seqs()})

here = Path(__file__).resolve().parent
(here / 'expected_r2.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
print(len(rows))
