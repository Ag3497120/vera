# Makes a copy of the tree (argument 1 = a directory that already holds verantyx/ tools/ tests/ docs/ copied from W) behave like the END OF ROUND 2:
# it undoes, by text replacement, the changes of round 3 in the reader, the checker and the entry. Used only to measure what round 3 lost
# (artifacts/w1-a/r3_lost_vs_round2.tsv, r3_entry_changes_vs_round2.tsv). The expectation that the copy is right: tests/test_semantic_read.py and
# tests/test_semantic_read_r2.py pass in it (189 passed, the same number as the end of round 2).
import sys
root = sys.argv[1]
def patch(p, pairs):
    s = open(root + '/' + p).read()
    for old, new in pairs:
        assert old in s, (p, old[:70]); s = s.replace(old, new)
    open(root + '/' + p, 'w').write(s)
patch('verantyx/semantic_reader.py', [
 ("if object_person is None and predicate in _INTRANSITIVE_CHANGE_PREDICATES: return None", "if object_person is None: return None"),
 ("                if not (last[0] in _HOUSE_SUFFIX_TOKENS and before[1] == '名詞' and before[2] == '固有名詞'): return True", "                return True"),
 ("'露語','言語','方言'", "'露語','方言'")])
patch('verantyx/semantic_verify.py', [
 ("if object_person is None and predicate in _VT_INTRANSITIVE_CHANGE_VERBS: return None", "if object_person is None: return None"),
 ("""            if (final[1] == '接尾辞' and (final[0] in _VT_HONORIFIC_TOKENS or final[0] in _VT_GROUP_SUFFIXES or final[0] in _VT_ROLE_SUFFIXES)
                    and not (final[0] == '家' and prev[1] == '名詞' and prev[2] == '固有名詞')): return True""",
  """            if final[1] == '接尾辞' and (final[0] in _VT_HONORIFIC_TOKENS or final[0] in _VT_GROUP_SUFFIXES or final[0] in _VT_ROLE_SUFFIXES): return True"""),
 ("'露語', '言語', '方言'", "'露語', '方言'")])
s = open(root + '/verantyx/semantic_read.py').read()
i = s.index("def _person_en(value, text=None):"); j = s.index("def _clause_en(")
s = s[:i] + '''def _person_en(value, text):
    from . import en_frames as en
    head = value.split()[-1] if value else ''
    if value.lower() in _EN_PRONOUN_AGENTS or head.lower() in en.ANIMATE or head.lower().rstrip('s') in en.ANIMATE: return True
    words = _en_words(text)
    return head[:1].isupper() and any(w == head for w in words[1:])


''' + s[j:]
s = s.replace("elif _person_en(agent):", "elif _person_en(agent, text):")
s = s.replace("if not (_person_en(recipient) or _recipient_by_construction_en(text, recipient, patient)):", "if not _person_en(recipient, text):")
i = s.index("    if len(patients) == 1:\n        subject_marked = particle_after(patients[0])"); j = s.index("    _no('UNDETERMINED_VOICE:れる/られる')\n")
s = s[:i] + '''    if len(patients) == 1:
        subject_marked = particle_after(patients[0]) in ('が', 'は')
        if agent is not None:
            if subject_marked and particle_after(agent) in ('に', 'によって', 'から'): return 'passive'
            _no('UNDETERMINED_VOICE:れる/られる with an object')
        if subject_marked and transitivity(c.predicate) == 'trans': return 'passive'
''' + s[j:]
i = s.index("    # A verb of going through a space takes the path"); j = s.index("    # ---- roles ----")
s = s[:i] + s[j:]
open(root + '/verantyx/semantic_read.py', 'w').write(s)
