"""W3-b2: shared helpers of the w3b2_*.py scripts and tests (no rule of the reader is here). Nothing in this file decides what is read."""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parent.parent
PLACEMENT_R6 = '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r6/run1'
DATA = ('frame', 'multiple', 'determiner', 'no')


def isolation(exit_on_fail=True):
    """The loaded verantyx* modules must all be under the first entry of PYTHONPATH (the venv has an editable copy of another verantyx)."""
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.'))
               and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign and exit_on_fail:
        print('ISOLATION FAILED', foreign); sys.exit(2)
    return root, foreign


def data_path(name):
    return HERE / ('w3b2_%s.jsonl' % name)


def load_data(name):
    return [dict(r, _data=name) for r in (json.loads(l) for l in data_path(name).read_text(encoding='utf-8').splitlines() if l.strip())]


def load_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding='utf-8').splitlines() if l.strip()]


# ---------------------------------------------------------------------------------------------------------------------------------
# declared exceptions: rows of the frozen data whose registered expectation the entry does not meet because of a fact about the READER of the base commit
# ---------------------------------------------------------------------------------------------------------------------------------
EXCEPTION_KINDS = ('reader_gives_no_predicate_clause', 'reader_reads_a_second_clause', 'reader_reads_the_phrase_as_two_roles', 'reader_reads_it_alone',
                   'reader_unsupported_beyond_the_registered_set')


def exception_kind(text):
    """The fact about the reader (base commit, no placement) that explains a declared row, one of EXCEPTION_KINDS, else 'UNEXPLAINED'. It looks at the reader only:
    nothing of the placement or of the new paths. Checked in this order."""
    from verantyx import semantic_read as SR, semantic_reader as R
    alone = SR.read(text, placement=None)
    if alone['readable']: return 'reader_reads_it_alone'
    if alone['abstain']['reasons'][0] == 'NO_PREDICATE_TOKEN': return 'reader_gives_no_predicate_clause'
    view = R.document_view({'d': text})
    if len(view.clauses) >= 2: return 'reader_reads_a_second_clause'
    for c in view.clauses:
        by = {}
        for r in c.roles: by.setdefault(r.name, []).append(r.span)
        if 'recipient' in by and 'direction' in by and any(i.start >= o.start and i.end <= o.end and (i.start, i.end) != (o.start, o.end) for i in by['recipient'] for o in by['direction']):
            return 'reader_reads_the_phrase_as_two_roles'
    if view.clauses and not (R.typed_trigger_ja(text, view) or R.typed_trigger_w3b2_ja(text, view)): return 'reader_unsupported_beyond_the_registered_set'
    return 'UNEXPLAINED'
