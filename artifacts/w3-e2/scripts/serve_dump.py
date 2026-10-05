"""P1 (K287): `vera serve` (fusion_turn) in both layers over the 120 questions of artifacts/w10-f01/data (documents F01..F05) and the public copy of B7 (each item's human_sources as the documents), with a
deterministic fake LLM. Only arguments that exist in the base tree are used, so the same script runs on the base and on the new tree; the output (timing removed) must be byte-identical.
Usage: python k287_serve.py --out FILE   (cwd = the tree; VERA_PLACEMENT set)"""
import argparse, glob, json, os, sys, tempfile
from pathlib import Path
from verantyx import vera_server as VS, coarse_place

ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--read-mode", default="absent", choices=["absent","strict","assume"])
ap.add_argument('--docs-dir', default='/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W3-e2-impl/b7docs')
a = ap.parse_args()
KW = {} if a.read_mode == 'absent' else {'read_mode': a.read_mode}


def fresh():
    for key in list(coarse_place._CACHE):
        try: coarse_place._CACHE.pop(key).con.close()
        except Exception: pass


class Fake:
    """Deterministic: layer 0 says one fixed line; layer 1 answers with the first alternative of its own enum (so the grammar path is exercised)."""
    def __call__(self, model, messages, fmt):
        if fmt is not None:
            enum = fmt['properties']['answer'].get('enum')
            if enum: return {'ok': True, 'content': json.dumps({'answer': enum[0]}, ensure_ascii=False), 'error': None, 'usage': {}}
            return {'ok': True, 'content': json.dumps({'answer': ['x']}), 'error': None, 'usage': {}}
        return {'ok': True, 'content': '分かりません。母が部屋で手紙を読んだ。', 'error': None, 'usage': {}}


def run(cfg, rid, q, rk, human):
    out = []
    for strict in (False, True):
        cfg.strict = strict
        try:
            res = VS.fusion_turn([{'role': 'user', 'content': q}], {'request_kind': rk, 'human_present': human}, cfg)
            res['vera'].pop('timing', None)
            out.append({'id': rid, 'layer': 1 if strict else 0, 'res': res})
        except VS.FusionBadRequest as exc:
            out.append({'id': rid, 'layer': 1 if strict else 0, 'bad_request': exc.error})
    return out


rows = []
docs = sorted(glob.glob('artifacts/w10-f01/data/docs/*.txt'))
fresh(); cfg = VS.FusionConfig.load(model='fake-model', documents=docs, llm_chat=Fake(), **KW)
for l in open('artifacts/w10-f01/data/questions.jsonl'):
    r = json.loads(l); rows += run(cfg, r['id'], r['question'], r['request_kind'], r['human_present'])
tmp = Path(a.docs_dir); tmp.mkdir(parents=True, exist_ok=True)       # a fixed directory: the path is part of the output (sources)
for l in open('tests/bank_score/fixtures/B7/items.jsonl'):
    r = json.loads(l)
    p = tmp / (r['id'] + '.txt'); p.write_text('\n'.join(r['human_sources']) + '\n', encoding='utf-8')
    fresh(); cfg = VS.FusionConfig.load(model='fake-model', documents=[str(p)], llm_chat=Fake(), **KW)
    rows += run(cfg, r['id'], r['request'], r['request_kind'], bool(r['human_present']))
with open(a.out, 'w', encoding='utf-8') as f:
    for r in rows: f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n')
print('rows', len(rows))
