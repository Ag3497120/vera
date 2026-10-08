"""Oracle helper for the frozen test data (W10-f04, K280 step 4): the types the reader's TABLES allow for a particle of a predicate type.
It reads the tables of semantic_reader (a data import, the tables are not copied) and does NOT import anything from fill/holes code."""
from verantyx import semantic_reader as R


def table_types(predicate_answer, particle):
    ptype, why = R.placement_type(predicate_answer)
    if why: return ptype, frozenset()
    types = set()
    for (t, role, parts, exp, kind, lic) in R.typed_frames_w3b5_rows():
        if t == ptype and particle in parts: types |= set(exp)
    rk, rinfo = R.predicate_role_frame(predicate_answer)
    if rk == 'confirmed' and particle in rinfo:
        for role, ts in rinfo[particle]: types |= set(ts)
    fk, finfo = R.predicate_frame(predicate_answer)
    if fk == 'confirmed':
        types &= set(finfo.get(particle, ()))
    return ptype, frozenset(types)
