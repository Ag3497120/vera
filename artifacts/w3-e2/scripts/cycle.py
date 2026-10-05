"""W3-e2 V4 (not a product file): the loop assumption -> ledger -> `vera ledger confirm` -> `vera ledger promote` -> `vera read --layer` with the real CLI and the real back end.
Case H (hole path, P3): an unplaced noun whose position the placement decides; case S (stand-in path, P1): a name's type the reader's surface rules need. Every call is printed."""
import argparse, json, os, subprocess, sys
from pathlib import Path
TREE = Path(__file__).resolve().parents[3]
ap = argparse.ArgumentParser(); ap.add_argument('--placement', required=True); ap.add_argument('--workdir', required=True); ap.add_argument('--out', required=True)
ap.add_argument('--model', default='qwen3.5:4b')
a = ap.parse_args()
work = Path(a.workdir); work.mkdir(parents=True, exist_ok=True)
log = []
def P(*x):
    s = ' '.join(str(i) for i in x); print(s); log.append(s)
def vera(*args):
    e = dict(os.environ, PYTHONPATH=str(TREE), PYTHONDONTWRITEBYTECODE='1'); e.pop('VERA_READ_MODE', None)
    p = subprocess.run([sys.executable, '-m', 'verantyx.cli', *args], capture_output=True, text=True, env=e, cwd=str(TREE))
    return p.returncode, p.stdout.strip()
def j(s):
    try: return json.loads(s)
    except Exception: return {'raw': s}
def case(name, sentences, placement, base):
    P('=== case', name)
    led, lay = str(work / ('%s_led.jsonl' % name)), str(work / ('%s_lay.sqlite' % name))
    for f in (led, led + '.manifest.json', lay):
        if os.path.exists(f): P('(a leftover file exists, using a fresh name)'); return
    # r1 review 5: the layer must EXIST before the measured word is promoted, or `growth` before promote is only LAYER_UNAVAILABLE. So the first assumed word is a seed (confirm, promote: the layer is
    # made), the second assumed word is the measured one: `assumption_rate` before its promotion and after, from the same layer and the same ledger.
    found = []
    for text in sentences:
        args = ['read', '--text', text, '--ledger-file', led, '--backend', 'ollama', '--model', a.model]
        if placement: args += ['--placement', placement]
        code, out = vera(*args); d = j(out)
        P('read', text, '-> read_mode', d.get('read_mode'), 'assumptions', d.get('assumptions'), 'reasons', (d.get('abstain') or {}).get('reasons'))
        if d.get('read_mode') == 'assumed' and d['assumptions'][0].get('ledger_id') and d['assumptions'][0]['word'] not in [f[1]['assumptions'][0]['word'] for f in found]:
            found.append((text, d))
        if len(found) == 2: break
    if len(found) < 2: P('RESULT %s: the real back end gave fewer than two assumptions (seed + measured): no loop' % name); return
    def promote(d):
        a0 = d['assumptions'][0]
        code, out = vera('ledger', 'confirm', a0['ledger_id'], '--ledger-file', led); P('confirm', a0['word'], '->', code, j(out).get('kind'))
        code, out = vera('ledger', 'promote', '--layer', lay, '--ledger-file', led, '--placement', base); P('promote', a0['word'], '->', code, json.dumps(j(out).get('written')))
    seed_text, seed = found[0]
    P('seed assumption', seed['assumptions'][0]['word'], seed['assumptions'][0]['assumed'], seed['assumptions'][0]['source'])
    promote(seed)
    text, d = found[1]; a0 = d['assumptions'][0]
    P('measured assumption', a0['word'], a0['assumed'], a0['source'], 'ledger_id', a0['ledger_id'])
    code, out = vera('placement', 'growth', '--layer', lay, '--ledger-file', led, '--placement', base)
    g = j(out); P('growth before promote: assumption', g.get('assumption'), g.get('verdict'))
    promote(d)
    args = ['read', '--text', text, '--layer', lay, '--ledger-file', led] + (['--placement', placement] if placement else [])
    code, out = vera(*args); d2 = j(out)
    P('read after promote -> read_mode', d2.get('read_mode'), 'readable', d2.get('readable'), 'assumptions', d2.get('assumptions'), 'reasons', (d2.get('abstain') or {}).get('reasons'))
    code, out = vera('placement', 'growth', '--layer', lay, '--ledger-file', led, '--placement', base)
    g = j(out); P('growth after promote: assumption', g.get('assumption'))
    P('RESULT %s: next read has read_mode=%s (a strict reading has none)' % (name, d2.get('read_mode')))
case('H', ['兄が土間で歩いた。', '母が広間で名乗った。', '祖父が座敷で断った。', '妹が屋根裏で歩いた。'], a.placement, a.placement)
case('S', ['ハルはミナへ荷物を運んだ。', 'ハルはリクへ荷物を運んだ。', 'ハルはナナへ荷物を運んだ。'], None, a.placement)
Path(a.out).write_text('\n'.join(log) + '\n', encoding='utf-8')
