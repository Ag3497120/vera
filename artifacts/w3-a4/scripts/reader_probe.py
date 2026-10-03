"""reader_probe.py <placement dir>: a copy of the middle-tier's probe.  Which terms does semantic_read send to
coarse_place.query for the sentence of the ticket (with and without the full stop) and for one control sentence?
The reader is not changed; this only wraps coarse_place.query in this process to log the terms."""
import contextlib, io, json, sys
import verantyx
from verantyx import coarse_place as cp
import verantyx.semantic_read as sr
assert verantyx.__file__.startswith('/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a4-S/')
log = []
orig = cp.query
def q(term, **kw):
    log.append(term)
    return orig(term, **kw)
cp.query = q
PL = sys.argv[1]
for text in ['係がデータを確認した', '係がデータを確認した。', '担当者が部長に結果を報告した。', '担当者がデータを確認した。']:
    log.clear()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            rc = sr.main(['--text', text, '--placement', PL])
        except SystemExit as e:
            rc = e.code
    out = buf.getvalue()
    print("TEXT:", text, "rc", rc, "queried", log)
    try:
        j = json.loads(out)
        print("  readable:", j.get("readable"), "abstain:", j.get("abstain"), "predicates:", [c.get("predicate") for c in j.get("clauses", [])])
    except ValueError:
        pass
    print(out[:700])
