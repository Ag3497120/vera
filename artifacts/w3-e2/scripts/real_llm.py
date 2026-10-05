import sys, json, os
from verantyx import semantic_read as SR, semantic_reader as R, constructions, llm_backend
constructions.discover()
pl = sys.argv[1]
q = None if pl == 'none' else R.CoarseQuery(os.environ['R9'])
chat = llm_backend.make_chat('ollama', timeout=180) if hasattr(llm_backend,'make_chat') else None
cfg = SR.AssumeConfig(chat=chat, model='qwen3.5:4b', backend_name='ollama')
for t in sys.argv[2:]:
    for i in (1, 2):
        e = SR.assumption_explain_ja(t, q, cfg)
        srcs = e.get('trace', {}).get('sources')
        print(pl, t, 'run%d' % i, e['status'], e.get('assumptions') and [(a['word'], a['assumed'], a['alternatives'], a['source']) for a in e['assumptions']], 'readable', e.get('trace', {}).get('readable'), 'pred', e.get('trace', {}).get('predicate'), 'sources', srcs, e.get('added'))
