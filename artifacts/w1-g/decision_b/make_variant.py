"""Structural-check variant for decision B (NOT in the tree; measured on a throwaway copy).

Non-operative supersede events (replacement record present, pointer absent or different) also take part in the
cycle check and in active_records' dangling check, but still retire nothing. Writes structural_variant.diff.
Usage: python make_variant.py <copy_dir>
"""
import difflib, pathlib, sys

W = pathlib.Path('/Users/motonisihikoudai/Projects/vera-impl/wt/W1-g-S')
T = pathlib.Path(sys.argv[1])
rel = 'verantyx/memory_merge.py'
src = (W / rel).read_text(encoding='utf-8')
dst = src


def sub(old, new):
    global dst
    assert dst.count(old) == 1, old
    dst = dst.replace(old, new)


sub("    declared_payloads: frozenset\n", "    declared_payloads: frozenset\n    checked_links: set\n")
sub("""    analysis = _analyze(events)
    return analysis.records, analysis.links, analysis.canonical
""", """    analysis = _analyze(events)
    return analysis.records, analysis.links, analysis.canonical
""")
# cycle check and the dangling check see the non-operative relations too
sub("""    graph: dict[str, set[str]] = {}
    for old, new in links:
""", """    checked_links = set(links) | {pair for pair, (status, _r, _d) in status_of.items() if status == 'NONOPERATIVE'}
    graph: dict[str, set[str]] = {}
    for old, new in checked_links:
""")
sub("    return _Analysis(records, links, canonical, statuses, declared_payloads)\n",
    "    return _Analysis(records, links, canonical, statuses, declared_payloads, checked_links)\n")
sub("""    records, links, _ = _state(_read_events(events))
    for old, new in links:
        if old not in records or new not in records:""", """    analysis = _analyze(_read_events(events))
    records, links = analysis.records, analysis.links
    for old, new in analysis.checked_links:
        if old not in records or new not in records:""")
(T / rel).write_text(dst, encoding='utf-8')
(W / 'artifacts/w1-g/decision_b/structural_variant.diff').write_text(
    ''.join(difflib.unified_diff(src.splitlines(True), dst.splitlines(True), f'a/{rel}', f'b/{rel}')), encoding='utf-8')
