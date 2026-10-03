"""reader_probe_more.py <placement>: more sentences (verbal-noun predicates) to see which terms the reader asks the placement.
The reader is not changed."""
import contextlib, io, json, sys
import verantyx
from verantyx import coarse_place as cp
import verantyx.semantic_read as sr
assert verantyx.__file__.startswith('/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a4-S/')
log = []
orig = cp.query
def q(term, **kw):
    log.append(term); return orig(term, **kw)
cp.query = q
for text in ['担当者が資料をレビューした。', '先生が学生に結果を連絡した。', '部長が会議に参加した。', '客が駅から空港へ移動した。',
             '係が書類を提出した。', '彼女は書類を確認した。', '会社が新製品を発売した。']:
    log.clear(); buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            rc = sr.main(['--text', text, '--placement', sys.argv[1]])
        except SystemExit as e:
            rc = e.code
    j = json.loads(buf.getvalue())
    print(text, '| queried:', log, '| readable:', j.get('readable'), '| predicate:', [c.get('predicate') for c in j.get('clauses', [])],
          '| abstain:', (j.get('abstain') or {}).get('reasons'), '| basis:', [m.get('rule') for m in j.get('clause_meta', [])])
