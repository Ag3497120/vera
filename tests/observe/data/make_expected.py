"""Writes expected.jsonl and expected_add1.jsonl BY HAND-RULE: every value below is typed from the registered rules (docs/OBSERVATION.md P1-P11),
the contents of the frozen inputs (placement.json, ledgers, corpus_root) and the reader's output on the seed sentences (artifacts/w3-c/reader_seed_obs.jsonl).
Nothing here imports verantyx and nothing is copied from an observer output. A realization text is the canonical form of semantic_realize._surface_text
(topic は, default role order recipient/goal/patient/origin/location, plain style) for the words of the cell.
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
NA = 'REFUSED:NOT_REALIZABLE'
rows = []


def add(case, outcome, **kw):
    row = {'case': case, 'outcome': outcome}
    row.update(kw)
    rows.append(row)


# ---- group S: a seed alone (range 0): the anchor cross is the focus, attested by its own reading; unreadable seeds are NO_ANCHOR
S_READ = {
    'J01': (give('司書', '学生'), say('司書', '学生', '辞書', '貸した')),
    'J02': (give('教授', '学生'), say('教授', '学生', '辞書', '貸した')),
    'J03': (give('司書', '部下'), say('司書', '部下', '辞書', '貸した')),
    'J04': (give('司書', '学生', pol='-'), say('司書', '学生', '辞書', '貸さなかった')),
    'J05': (give('駅員', '乗客', '切符', '渡す'), say('駅員', '乗客', '切符', '渡した')),
    'J06': (give('車掌', '乗客', '切符', '渡す'), say('車掌', '乗客', '切符', '渡した')),
    'J07': (give('受付', '客', '鍵', '渡す'), say('受付', '客', '鍵', '渡した')),
    'J09': (d('作る', '+', 'past', agent='祖母', patient='団子', place='台所'), '祖母は団子を台所で作った。'),
    'J13': (d('売る', '+', 'past', agent='農家', patient='果物', place='市場'), '農家は果物を市場で売った。'),
    'J14': (d('売る', '+', 'past', agent='漁師', patient='魚', place='市場'), '漁師は魚を市場で売った。'),
    'J15': (give('店員', '客', '傘', '売る'), say('店員', '客', '傘', '売った')),
    'J16': (d('描く', '+', 'past', agent='弟', patient='絵'), '弟は絵を描いた。'),
    'J17': (d('書く', '+', 'past', agent='姉', patient='手紙'), '姉は手紙を書いた。'),
    'J18': (d('運ぶ', '+', 'past', agent='兄', patient='荷物'), '兄は荷物を運んだ。'),
    'J19': (d('点検する', '+', 'past', agent='技師', patient='機械'), '技師は機械を点検した。'),
    'J20': (d('開ける', '-', 'past', agent='母', patient='窓'), '母は窓を開けなかった。'),
    'J21': (d('発行する', '-', 'past', agent='会計係', patient='領収書'), '会計係は領収書を発行しなかった。'),
    'J22': (d('帰る', '+', 'past', agent='兄', goal='家', source='駅'), '兄は家へ駅から帰った。'),
    'J23': (d('運ぶ', '+', 'past', agent='配達員', patient='荷物', goal='店', source='倉庫'), '配達員は店へ荷物を倉庫から運んだ。'),
}
S_EN_READ = {
    'E03': d('lend', '+', 'past', agent='librarian', patient='dictionary', recipient='student'),
    'E04': d('lend', '-', 'past', agent='librarian', patient='dictionary', recipient='student'),
    'E08': d('sell', '+', 'past', agent='painter', patient='picture', recipient='customer'),
    'E09': d('sell', '+', 'past', agent='sculptor', patient='picture', recipient='customer'),
    'E11': d('sing', '+', 'past', agent='pupils'),
    'E14': d('hand', '+', 'past', agent='clerk', patient='pass', recipient='visitor'),
    'E15': d('sign', '-', 'past', agent='banker', patient='contract'),
}
ALL_JA = ['J%02d' % i for i in range(1, 32)]
ALL_EN = ['E%02d' % i for i in range(1, 19)]
for sid in ALL_JA:
    if sid in S_READ:
        desc, text = S_READ[sid]
        add('S-' + sid, 'FOCUS', anchor=desc, anchor_realization=R(text), anchor_occupied='ATTESTED', observed=[], focus=desc, tie=None,
            occupied={desc: 'ATTESTED'}, realization={desc: R(text)}, claims={desc: 'OBSERVED_OCCUPIED'})
    else:
        add('S-' + sid, 'NO_ANCHOR', reason='READER_ABSTAINED')
for sid in ALL_EN:
    if sid in S_EN_READ:
        desc = S_EN_READ[sid]
        add('S-' + sid, 'FOCUS', anchor=desc, anchor_realization=NA, anchor_occupied='ATTESTED', observed=[], focus=desc, tie=None,
            occupied={desc: 'ATTESTED'}, realization={desc: NA}, claims={desc: 'OBSERVED_OCCUPIED'})
    else:
        add('S-' + sid, 'NO_ANCHOR', reason='READER_ABSTAINED')

# ---- moves on J01 (司書は学生に辞書を貸した。): agent neighbours of 司書 that AGREE: 教授 事務員 犬 (机 DISAGREE; 彼女 ESTIMATED_NEAR; 店主 ESTIMATED_GENERATED; 謎の人 UNPLACED; 銀行 MULTIPLE; 誰か UNKNOWN; 司書 itself skipped)
J01 = give('司書', '学生')
AG = ['教授', '事務員', '犬']
cellA, cellB, cellC = give('教授', '学生'), give('事務員', '学生'), give('犬', '学生')
txt = lambda a, r='学生': say(a, r, '辞書', '貸した')
FACE_J01_COUNTS = {'licensed': 3, 'candidates_tried': 9, 'candidates_skipped_same_as_original': 1,
                   'DISAGREE': 1, 'NOT_CHECKED:ESTIMATED_NEAR': 1, 'NOT_CHECKED:ESTIMATED_GENERATED': 1, 'NOT_CHECKED:UNPLACED': 1,
                   'NOT_CHECKED:MULTIPLE': 1, 'NOT_CHECKED:UNKNOWN': 1}


def swap_agent_expect(case, occ, claims=None, anchor_occ='ATTESTED', anchor=J01):
    cells = [cellA, cellB, cellC]
    real = {c: R(txt(a)) for c, a in zip(cells, AG)}
    cl = claims or {c: ('OBSERVED_OCCUPIED' if occ[c] == 'ATTESTED' else 'CONSTRUCTED_UNOCCUPIED' if occ[c] == 'UNOCCUPIED' else 'UNKNOWN_OCCUPANCY') for c in cells}
    add(case, 'TIE', anchor=anchor, anchor_realization=R(txt('司書')), anchor_occupied=anchor_occ, observed=sorted(cells), focus=None, tie=sorted(cells),
        occupied=occ, realization=real, claims=cl, distances={c: 1 for c in cells}, face_swap_counts=FACE_J01_COUNTS)


swap_agent_expect('M01-swap-agent-J01-noindex', {cellA: 'ATTESTED', cellB: 'UNKNOWN_NO_INDEX', cellC: 'UNKNOWN_NO_INDEX'})
swap_agent_expect('M02-swap-agent-J01-index', {cellA: 'ATTESTED', cellB: 'ATTESTED', cellC: 'UNKNOWN_WINDOW_SATURATED'})
swap_agent_expect('M14-record-J01', {cellA: 'ATTESTED', cellB: 'UNKNOWN_NO_INDEX', cellC: 'UNKNOWN_NO_INDEX'})
swap_agent_expect('M15-question-J01', {cellA: 'ATTESTED', cellB: 'UNKNOWN_NO_INDEX', cellC: 'UNKNOWN_NO_INDEX'})
# cell B is attested by an index row whose origin is generated
add_basis = {'M02-swap-agent-J01-index': {cellB: 'generated'}}
for r in rows:
    if r['case'] in add_basis: r['basis_origin'] = add_basis[r['case']]

# J04 (negation): the same swaps, polarity -, attested nowhere
n_cells = [give(a, '学生', pol='-') for a in AG]
add('M17-swap-agent-J04-negation', 'TIE', anchor=give('司書', '学生', pol='-'), anchor_realization=R(say('司書', '学生', '辞書', '貸さなかった')), anchor_occupied='ATTESTED',
    observed=sorted(n_cells), focus=None, tie=sorted(n_cells), occupied={c: 'UNKNOWN_NO_INDEX' for c in n_cells},
    realization={c: R(say(a, '学生', '辞書', '貸さなかった')) for c, a in zip(n_cells, AG)}, claims={c: 'UNKNOWN_OCCUPANCY' for c in n_cells},
    distances={c: 1 for c in n_cells}, face_swap_counts=FACE_J01_COUNTS)

# recipient swap: neighbours of 学生: 部下 客 (机 DISAGREE). 部下 is attested by J03.
rc = [give('司書', '部下'), give('司書', '客')]
add('M05-swap-recipient-J01', 'TIE', anchor=J01, anchor_realization=R(txt('司書')), anchor_occupied='ATTESTED', observed=sorted(rc), focus=None, tie=sorted(rc),
    occupied={rc[0]: 'ATTESTED', rc[1]: 'UNKNOWN_NO_INDEX'},
    realization={rc[0]: R(say('司書', '部下', '辞書', '貸した')), rc[1]: R(say('司書', '客', '辞書', '貸した'))},
    claims={rc[0]: 'OBSERVED_OCCUPIED', rc[1]: 'UNKNOWN_OCCUPANCY'}, distances={c: 1 for c in rc},
    face_swap_counts={'licensed': 2, 'candidates_tried': 3, 'candidates_skipped_same_as_original': 0, 'DISAGREE': 1})
add('M06-swap-patient-J01', 'NO_MOVE_LICENSED', reasons={'FACE_SWAP:ROLE_NOT_IN_TABLE': 1}, anchor=J01, anchor_realization=R(txt('司書')), anchor_occupied='ATTESTED', observed=[])
add('M07-swap-place-J01-noarm', 'NO_MOVE_LICENSED', reasons={'FACE_SWAP:NO_ARM': 1}, anchor=J01, anchor_realization=R(txt('司書')), anchor_occupied='ATTESTED', observed=[])
add('M08-stub-J01', 'NO_MOVE_LICENSED', reasons={'FACE_SWAP:NO_PLACEMENT': 1}, anchor=J01, anchor_realization=R(txt('司書')), anchor_occupied='ATTESTED', observed=[])
add('M09-edge-J01', 'NO_MOVE_LICENSED', reasons={'EDGE:NO_RELATION_IN_STRUCTURE': 1}, anchor=J01, anchor_realization=R(txt('司書')), anchor_occupied='ATTESTED', observed=[])

# two moves: 3 agent cells at distance 1, then each with 部下 / 客 as recipient: 6 cells at distance 2. Nothing is attested except the distance-1 cell 教授 (J02).
lvl2 = [give(a, r) for a in AG for r in ('部下', '客')]
two = sorted([cellA, cellB, cellC] + lvl2)
dist2 = {c: 1 for c in (cellA, cellB, cellC)}
dist2.update({c: 2 for c in lvl2})
occ2 = {c: 'UNKNOWN_NO_INDEX' for c in two}
occ2[cellA] = 'ATTESTED'
real2 = {c: R(txt(a)) for c, a in zip((cellA, cellB, cellC), AG)}
real2.update({give(a, r): R(say(a, r, '辞書', '貸した')) for a in AG for r in ('部下', '客')})
add('M10-two-moves-J01', 'TIE', anchor=J01, anchor_realization=R(txt('司書')), anchor_occupied='ATTESTED', observed=two, focus=None, tie=sorted([cellA, cellB, cellC]),
    occupied=occ2, realization=real2, claims={c: ('OBSERVED_OCCUPIED' if occ2[c] == 'ATTESTED' else 'UNKNOWN_OCCUPANCY') for c in two}, distances=dist2)
add('M21-two-moves-range1-J01', 'TIE', anchor=J01, anchor_realization=R(txt('司書')), anchor_occupied='ATTESTED', observed=sorted([cellA, cellB, cellC]), focus=None,
    tie=sorted([cellA, cellB, cellC]), occupied={cellA: 'ATTESTED', cellB: 'UNKNOWN_NO_INDEX', cellC: 'UNKNOWN_NO_INDEX'},
    realization={c: R(txt(a)) for c, a in zip((cellA, cellB, cellC), AG)}, claims={cellA: 'OBSERVED_OCCUPIED', cellB: 'UNKNOWN_OCCUPANCY', cellC: 'UNKNOWN_OCCUPANCY'},
    distances={c: 1 for c in (cellA, cellB, cellC)})
add('M11-range0-J01', 'FOCUS', anchor=J01, anchor_realization=R(txt('司書')), anchor_occupied='ATTESTED', observed=[], focus=J01, tie=None,
    occupied={J01: 'ATTESTED'}, realization={J01: R(txt('司書'))}, claims={J01: 'OBSERVED_OCCUPIED'})

# one neighbour only: J05 (駅員) -> 車掌 (attested by J06); J02 (教授) -> 司書 (the cell of J01, attested by J01)
D5 = give('駅員', '乗客', '切符', '渡す')
D6 = give('車掌', '乗客', '切符', '渡す')
add('M12-single-J05', 'FOCUS', anchor=D5, anchor_realization=R(say('駅員', '乗客', '切符', '渡した')), anchor_occupied='ATTESTED', observed=[D6], focus=D6, tie=None,
    occupied={D6: 'ATTESTED'}, realization={D6: R(say('車掌', '乗客', '切符', '渡した'))}, claims={D6: 'OBSERVED_OCCUPIED'}, distances={D6: 1})
add('M13-back-J02', 'FOCUS', anchor=cellA, anchor_realization=R(txt('教授')), anchor_occupied='ATTESTED', observed=[J01], focus=J01, tie=None,
    occupied={J01: 'ATTESTED'}, realization={J01: R(txt('司書'))}, claims={J01: 'OBSERVED_OCCUPIED'}, distances={J01: 1})
add('M25-swap-recipient-J05', 'NO_MOVE_LICENSED', reasons={'FACE_SWAP:UNKNOWN': 1}, anchor=D5, anchor_realization=R(say('駅員', '乗客', '切符', '渡した')), anchor_occupied='ATTESTED', observed=[])
add('M18-swap-agent-J22-unknown', 'NO_MOVE_LICENSED', reasons={'FACE_SWAP:UNKNOWN': 1}, anchor=d('帰る', '+', 'past', agent='兄', goal='家', source='駅'),
    anchor_realization=R('兄は家へ駅から帰った。'), anchor_occupied='ATTESTED', observed=[])

# unreadable anchors: J08 J10 J11 J12 J24 J25 J26 are not read (ambiguous で / ambiguous frame role / time phrase); E01 is not read (UNKNOWN_PREDICATE)
for case in ('M03-swap-agent-J08-index', 'M04-swap-place-J08', 'M20-swap-place-J25-nonpast', 'M22-swap-agent-J08-two-families', 'M16-en-swap-E01', 'M23-record-unreadable-J27'):
    add(case, 'NO_ANCHOR', reason='READER_ABSTAINED')
add('M24-record-missing', 'NO_ANCHOR', reason='RECORD_NOT_IN_STRUCTURE')

# English: E08 (painter) -> sculptor (E09 attests it); the swapped cell cannot be said (English)
E08 = S_EN_READ['E08']
E09 = S_EN_READ['E09']
add('M16b-en-swap-E08', 'FOCUS', anchor=E08, anchor_realization=NA, anchor_occupied='ATTESTED', observed=[E09], focus=E09, tie=None,
    occupied={E09: 'ATTESTED'}, realization={E09: NA}, claims={E09: 'OBSERVED_OCCUPIED'}, distances={E09: 1})

# ---- J09 (祖母は台所で団子を作った。; J08 and J10 are not read, so nothing in the structure attests the swapped cells)
J09 = d('作る', '+', 'past', agent='祖母', patient='団子', place='台所')
ag9 = [d('作る', '+', 'past', agent=a, patient='団子', place='台所') for a in ('叔父', '祖父', '叔母')]
t9 = {c: R('%sは団子を台所で作った。' % a) for c, a in zip(ag9, ('叔父', '祖父', '叔母'))}
add('M03b-swap-agent-J09-index', 'TIE', anchor=J09, anchor_realization=R('祖母は団子を台所で作った。'), anchor_occupied='ATTESTED', observed=sorted(ag9), focus=None, tie=sorted(ag9),
    occupied={c: 'UNOCCUPIED' for c in ag9}, realization=t9, claims={c: 'CONSTRUCTED_UNOCCUPIED' for c in ag9}, distances={c: 1 for c in ag9},
    unoccupied_marked=sorted(ag9))
add('M22b-swap-agent-J09-two-families', 'TIE', anchor=J09, anchor_realization=R('祖母は団子を台所で作った。'), anchor_occupied='ATTESTED', observed=sorted(ag9), focus=None, tie=sorted(ag9),
    occupied={c: 'UNKNOWN_FAMILY_DB_MISSING' for c in ag9}, realization=t9, claims={c: 'UNKNOWN_OCCUPANCY' for c in ag9}, distances={c: 1 for c in ag9})
pl9 = [d('作る', '+', 'past', agent='祖母', patient='団子', place=p) for p in ('縁側', '庭')]
tp9 = {c: R('祖母は団子を%sで作った。' % p) for c, p in zip(pl9, ('縁側', '庭'))}
add('M04b-swap-place-J09', 'TIE', anchor=J09, anchor_realization=R('祖母は団子を台所で作った。'), anchor_occupied='ATTESTED', observed=sorted(pl9), focus=None, tie=sorted(pl9),
    occupied={c: 'UNKNOWN_NO_INDEX' for c in pl9}, realization=tp9, claims={c: 'UNKNOWN_OCCUPANCY' for c in pl9}, distances={c: 1 for c in pl9})
add('M04c-swap-place-J09-index', 'TIE', anchor=J09, anchor_realization=R('祖母は団子を台所で作った。'), anchor_occupied='ATTESTED', observed=sorted(pl9), focus=None, tie=sorted(pl9),
    occupied={c: 'UNOCCUPIED' for c in pl9}, realization=tp9, claims={c: 'CONSTRUCTED_UNOCCUPIED' for c in pl9}, distances={c: 1 for c in pl9}, unoccupied_marked=sorted(pl9))

# ---- ledger cases LG01..LG10 on J01 with agent swaps: cells A=教授 B=事務員 C=犬 (ledger keys are those cells)
cA, cB, cC = cellA, cellB, cellC
LG = {
    'LG01': dict(outcome='TIE', ranks=[[cA, cB, cC]], trace_first_boundary=None),
    'LG02': dict(outcome='TIE', ranks=[[cA, cB, cC]], trace_first_boundary=None),
    'LG03': dict(outcome='FOCUS', focus=cA, ranks=[[cA], [cB], [cC]], decided_by=['decided', 'decided']),
    'LG04': dict(outcome='TIE', ranks=[[cA, cB, cC]], decided_by=[]),
    'LG05': dict(outcome='FOCUS', focus=cA, ranks=[[cA], [cB, cC]], decided_by=['utter_verbatim']),
    'LG06': dict(outcome='FOCUS', focus=cC, ranks=[[cC], [cA, cB]], decided_by=['utter_neighbor']),
    'LG07': dict(outcome='FOCUS', focus=cC, ranks=[[cC], [cA, cB]], decided_by=['decided']),
    'LG08': dict(outcome='TIE', ranks=[[cA, cC], [cB]], decided_by=['recency']),
    'LG09': dict(outcome='TIE', ranks=[[cB, cC], [cA]], decided_by=['recency'], recency_seq={cA: [2]}),
    'LG10': dict(outcome='FOCUS', focus=cA, ranks=[[cA], [cC], [cB]], decided_by=['decided', 'recency'], recency_seq={cB: [2]}),
}
for name, e in LG.items():
    cells = sorted([cA, cB, cC])
    focus = e.get('focus')
    tie = sorted(e['ranks'][0]) if e['outcome'] == 'TIE' else None
    ranks = [sorted(g) for g in e['ranks']]
    row = dict(anchor=J01, anchor_realization=R(txt('司書')), anchor_occupied='ATTESTED', observed=cells, focus=focus, tie=tie, ranks=ranks,
               occupied={cA: 'ATTESTED', cB: 'UNKNOWN_NO_INDEX', cC: 'UNKNOWN_NO_INDEX'}, distances={c: 1 for c in cells})
    if 'decided_by' in e: row['decided_by'] = e['decided_by']
    if 'recency_seq' in e: row['recency_seq'] = e['recency_seq']
    add(name, e['outcome'], **row)

# ---- two-turn cases. Turn 2 uses the ledger after turn 1: the utterance of turn 1 (the text of J01) is now the latest one, and 司書 (the anchor's own word)
# is a neighbour of 教授 and of 事務員 (not of 犬): stage ii-b gives 教授 and 事務員 1 and 犬 0.
O4 = {
    'O4-a-L03': dict(turn1=dict(focus=cA), turn2=dict(focus=cB, tie=None, ranks=[[cB], [cA], [cC]]), alt_exists=True, changed=True),
    'O4-b-L04': dict(turn1=dict(focus=D6), turn2=dict(focus=D6, tie=None, ranks=[[D6]]), alt_exists=False, changed=False),
    'O4-c-L05': dict(turn1=dict(focus=cA), turn2=dict(focus=cB, tie=None, ranks=[[cB], [cA], [cC]]), alt_exists=True, changed=True),
    'O4-d-L01': dict(turn1=dict(focus=None, tie=sorted([cA, cB, cC])), turn2=dict(focus=None, tie=sorted([cA, cB]), ranks=[sorted([cA, cB]), [cC]]), alt_exists=True, changed=True),
    'O4-e-L07': dict(turn1=dict(focus=cC), turn2=dict(focus=None, tie=sorted([cA, cB]), ranks=[sorted([cA, cB]), [cC]]), alt_exists=True, changed=True),
    'O4-f-L08': dict(turn1=dict(focus=None, tie=sorted([cA, cC])), turn2=dict(focus=cA, tie=None, ranks=[[cA], [cB], [cC]]), alt_exists=True, changed=True),
}
for name, e in O4.items():
    add(name, 'TURNS', o4=e)

# ---- write
here = Path(__file__).resolve().parent
S1 = {r['case'] for r in rows}
add1_cases = {'M03b-swap-agent-J09-index', 'M04b-swap-place-J09', 'M04c-swap-place-J09-index', 'M22b-swap-agent-J09-two-families', 'M16b-en-swap-E08', 'M25-swap-recipient-J05'}
main_rows = [r for r in rows if r['case'] not in add1_cases]
add_rows = [r for r in rows if r['case'] in add1_cases]
(here / 'expected.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in main_rows), encoding='utf-8')
(here / 'expected_add1.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in add_rows), encoding='utf-8')
print(len(main_rows), len(add_rows))
