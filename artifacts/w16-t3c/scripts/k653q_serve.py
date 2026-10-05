"""P1 (K287): `vera serve` (fusion_turn) in both layers over the 120 questions of artifacts/w10-f01/data (documents F01..F05) and the public copy of B7 (each item's human_sources as the documents), with a
deterministic fake LLM. Only arguments that exist in the base tree are used, so the same script runs on the base and on the new tree; the output (timing removed) must be byte-identical.
Usage: python k287_serve.py --out FILE   (cwd = the tree; VERA_PLACEMENT set)"""
import argparse, glob, json, os, re, sys, tempfile
from pathlib import Path
from verantyx import vera_server as VS, coarse_place

ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
ap.add_argument('--docs-dir', default='/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W10-f05-impl/b7docs')
a = ap.parse_args()


def fresh():
    for key in list(coarse_place._CACHE):
        try: coarse_place._CACHE.pop(key).con.close()
        except Exception: pass


class Fake:
    """W16-t3c 版: k287 の偽の LLM に、quote_mode の呼び出し（fmt に quotes がある）だけ引用つきの答えを返す枝を足した。
    奇数回目の quote_mode 呼び出し: system の最初の [source:line] 行の本文を answer とし、その行を逐語で quotes に入れる（錨ありになりうる）。
    偶数回目: 同じ answer で quotes を空にする（錨なし）。呼び出しの順は決定的。それ以外の呼び出しは k287 と同じ。"""
    n = 0
    def __call__(self, model, messages, fmt):
        if fmt is not None and 'quotes' in fmt.get('properties', {}):
            Fake.n += 1
            sys_msg = messages[0]['content'] if messages and messages[0].get('role') == 'system' else ''
            m = re.search(r'^\[(.+?):(\d+)\] (.*)$', sys_msg, re.M)
            if not m: return {'ok': True, 'content': json.dumps({'answer': '分かりません', 'quotes': []}, ensure_ascii=False), 'error': None, 'usage': {}}
            src, ln, body = m.group(1), int(m.group(2)), m.group(3)
            quotes = [{'source': src, 'line': ln, 'text': body}] if Fake.n % 2 == 1 else []
            return {'ok': True, 'content': json.dumps({'answer': body, 'quotes': quotes}, ensure_ascii=False), 'error': None, 'usage': {}}
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
fresh(); cfg = VS.FusionConfig.load(model='fake-model', documents=docs, llm_chat=Fake())
for l in open('artifacts/w10-f01/data/questions.jsonl'):
    r = json.loads(l); rows += run(cfg, r['id'], r['question'], r['request_kind'], r['human_present'])
tmp = Path(a.docs_dir); tmp.mkdir(parents=True, exist_ok=True)       # a fixed directory: the path is part of the output (sources)
for l in open('tests/bank_score/fixtures/B7/items.jsonl'):
    r = json.loads(l)
    p = tmp / (r['id'] + '.txt'); p.write_text('\n'.join(r['human_sources']) + '\n', encoding='utf-8')
    fresh(); cfg = VS.FusionConfig.load(model='fake-model', documents=[str(p)], llm_chat=Fake())
    rows += run(cfg, r['id'], r['request'], r['request_kind'], bool(r['human_present']))
with open(a.out, 'w', encoding='utf-8') as f:
    for r in rows: f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n')
print('rows', len(rows))
