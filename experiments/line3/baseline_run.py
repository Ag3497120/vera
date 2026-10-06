"""T0 baselines (docs/LINE3_DESIGN.md 7.1).  Usage: baseline_run.py COND   (COND in 0 300 300full 3000 30000 100000 269710)

Paths (one result row per question per path):
  a1  consensus_store.ja_consensus_ask(store, q)            (A report's A_core)
  a2  vera.Vera().add('ja', store).ask(q minus trailing 'か')  (A report's B2; the
      A report's B_census = same Vera with the question unchanged is also kept as a2raw)
  a3  CLI cmd_ask, legacy mode, question unchanged, store passed in memory
      (cli._load patched to return the in-memory store; stdout captured and parsed)
  b1  round5, document = the whole condition text (S300 only)
  b2  round5, document = only the sentences of the article whose title == subject
      in THIS condition's data (empty = no document); upper bound, not a fair comparison.
Run from anywhere with PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<clone> venv python.
"""
import contextlib, io, json, os, re, sys, time, types

HERE = os.path.dirname(os.path.abspath(__file__))
CLONE = os.path.abspath(os.path.join(HERE, '..', '..'))
SCRATCH = ('/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/'
           'd52dc51d-8cb5-4487-931c-cc143bce928f/scratchpad/line3')
sys.path.insert(0, HERE)
import grade as G

cond = sys.argv[1]
from verantyx import lang, cross_store, consensus_store, vera as vmod, cli, doc_answer
from verantyx.basis_policy import AskPolicy
bad = [m.__file__ for n, m in sys.modules.items()
       if n.startswith('verantyx') and getattr(m, '__file__', None) and not m.__file__.startswith(CLONE + '/')]
assert not bad, bad

man = json.load(open(os.path.join(HERE, 'data_manifest.json')))['files']
Q = G.load_questions(os.path.join(HERE, 'questions.tsv'))


def path_of(c):
    return man[c if c == 'S0' else 'S' + c]['path']


def articles():
    """title -> list of sentences (this condition's data)."""
    out = {}
    if cond == '0':
        return out
    for l in open(path_of(cond), encoding='utf-8'):
        j = json.loads(l)
        if cond == '300full':
            out[j['title']] = [s + '。' for s in j['text'].split('。') if s.strip()]
        else:
            out[j['title']] = [j['sent']]
    return out


ART = articles()
S = [s for ss in ART.values() for s in ss] if cond != '0' else []
st = cross_store.CrossStore()
nocore = 0
t0 = time.time()
for s in S:
    if lang.ja_ingest_sentence(st, s) is None:
        nocore += 1
V = vmod.Vera().add('ja', st)
orig_load = cli._load
cli._load = lambda path, **kw: st
docdir = os.path.join(SCRATCH, 'docs')
os.makedirs(docdir, exist_ok=True)
pol = AskPolicy.from_args(types.SimpleNamespace())


def a3(q):
    ns = types.SimpleNamespace(query=q, store='(memory)', mode=None, document=None, engine=False)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cli.cmd_ask(ns)
    return json.loads(buf.getvalue())


def round5(q, docs):
    out, rc = cli._round5_answer(q, doc_answer.prepare(docs), pol, docs)
    return out


def docfile(name, sents):
    p = os.path.join(docdir, name)
    with open(p, 'w', encoding='utf-8') as f:
        f.write('\n'.join(sents) + ('\n' if sents else ''))
    return p


b1doc = docfile(f'b1_{cond}.txt', S) if cond == '300' else None
noka = lambda q: re.sub(r'(です|ます|ました)?か$', '', q)
paths = ['a1', 'a2', 'a2raw', 'a3', 'b2'] + (['b1'] if cond == '300' else [])
rows = []
tp = {p: 0.0 for p in paths}
for qid, kind, subj, q, gold in Q:
    sj = subj.casefold()
    for p in paths:
        t0 = time.time()
        try:
            if p == 'a1':
                r = consensus_store.ja_consensus_ask(st, q)
            elif p == 'a2':
                r = V.ask(noka(q))
            elif p == 'a2raw':
                r = V.ask(q)
            elif p == 'a3':
                r = a3(q)
            elif p == 'b1':
                r = round5(q, [b1doc])
            else:
                ss = ART.get(subj)
                r = round5(q, [docfile(f'b2_{cond}_{qid}.txt', ss)] if ss else [])
        except Exception as e:
            r = {'verdict': 'ERROR:' + type(e).__name__, 'text': str(e)[:160]}
        tp[p] += time.time() - t0
        v, core, text = G.extract(r)
        c = G.classify(v)
        g, gold_hit, subj_ok = G.grade(c, core, text, subj, gold)
        golds = [x.casefold() for x in gold.split('|') if x]
        held = bool(golds) and any(any(x in f.casefold() for f in st.crosses.get(k, {}))
                                   for x in golds for k in st.crosses if k in sj)
        rows.append(dict(cond=cond, qid=qid, kind=kind, path=p, verdict=v, cls=c, core=str(core),
                         text=text[:160], grade=g, gold_hit=gold_hit, subj_ok=subj_ok, gold_held=held))
cli._load = orig_load
res = dict(cond=cond, n_sent=len(S), nocore=nocore, n_cores=len(st.crosses),
           seconds={k: round(v, 1) for k, v in tp.items()},
           loaded_verantyx_modules=sorted(n for n in sys.modules if n.startswith('verantyx')).__len__(), rows=rows)
out = os.path.join(HERE, 'results', f'base_{cond}.json')
json.dump(res, open(out, 'w'), ensure_ascii=False, indent=0)
print(cond, len(S), 'cores', len(st.crosses), tp)
