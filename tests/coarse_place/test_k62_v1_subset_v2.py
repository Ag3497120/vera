"""W3-b4: the table the placement looks backwards through (`coarse_types.K62_FRAMES`, v1: 9 rows) stays as it was, and every row of it is a row of the table the reader
reads with (`semantic_reader.typed_frames_v2()`, v2) and of the table in docs/READING_SOUNDNESS.md section 10D (`w3b4_frames`): v1 is a subset of v2, row by row.
The reverse lookup of the placement and the promotion of a predicate (W3-a3) are NOT moved to v2 by W3-b4 (docs/COARSE_PLACEMENT.md 12.2): this test is the guard of that.
No word appears below."""
import ast
import re
import subprocess
from pathlib import Path

from verantyx import coarse_types as ct
from verantyx import semantic_reader as R

TREE = Path(__file__).resolve().parents[2]
BASE_COMMIT = 'c875ed3'
DOCS = (TREE / 'docs' / 'READING_SOUNDNESS.md').read_text(encoding='utf-8')
KIND = {'項': 'arg', '付加': 'adjunct'}


def docs_rows(name):
    m = re.search(r'<!-- BEGIN table:%s -->\n(.*?)<!-- END table:%s -->' % (name, name), DOCS, re.S)
    assert m, name
    lines = [l for l in m.group(1).splitlines() if l.startswith('|') and not set(l) <= set('|- ')][1:]
    out = []
    for line in lines:
        c = [x.strip().strip('`') for x in line.strip().strip('|').split('|')]
        out.append((c[0], c[1], c[2], tuple(sorted(c[3].split())), KIND[c[4]]))
    return out


def code_rows_v2():
    return [(t, role, '/'.join(parts), tuple(sorted(exp)), kind) for t, rows in R.typed_frames_v2().items() for (role, parts, exp, kind) in rows]


def k62_rows():
    return [(t, role, part, tuple(sorted(types)), kind) for t, role, part, types, kind in ct.K62_FRAMES]


def test_k62_frames_is_still_the_nine_rows_of_the_base_commit():
    src = subprocess.run(['git', '-C', str(TREE), 'show', '%s:verantyx/coarse_types.py' % BASE_COMMIT], capture_output=True, check=True).stdout.decode('utf-8')
    base_assign = next(n for n in ast.parse(src).body if isinstance(n, ast.AnnAssign) and getattr(n.target, 'id', None) == 'K62_FRAMES')
    now_assign = next(n for n in ast.parse((TREE / 'verantyx' / 'coarse_types.py').read_text(encoding='utf-8')).body
                      if isinstance(n, ast.AnnAssign) and getattr(n.target, 'id', None) == 'K62_FRAMES')
    assert ast.dump(base_assign.value) == ast.dump(now_assign.value)
    assert len(ct.K62_FRAMES) == 9


def test_every_row_of_v1_is_a_row_of_the_table_the_reader_reads_with():
    v2 = set(code_rows_v2())
    for row in k62_rows():
        assert row in v2, row
    assert len(set(k62_rows())) == 9 and len(v2) > 9


def test_every_row_of_v1_is_a_row_of_the_docs_table_of_the_second_table():
    docs = set(docs_rows('w3b4_frames'))
    for row in k62_rows():
        assert row in docs, row
    # and the docs table is the table of the code, row for row
    assert docs_rows('w3b4_frames') == code_rows_v2()


def test_the_nine_rows_come_first_in_the_second_table_in_the_same_order_as_in_the_first_table():
    assert docs_rows('w3b4_frames')[:9] == docs_rows('w3b1_frames') == k62_rows()


def test_the_placement_side_reads_only_the_two_types_of_v1():
    assert {t for t, *_ in ct.K62_FRAMES} == {'P_MOVE', 'P_COMMUNICATE'}
    assert set(R.typed_frames_v2()) > {t for t, *_ in ct.K62_FRAMES}
