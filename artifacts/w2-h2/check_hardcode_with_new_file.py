import subprocess, sys, runpy
W = '/Users/motonisihikoudai/Projects/vera-impl/wt/W2-h2-S'
real = subprocess.run
def fake(cmd, *a, **k):
    r = real(cmd, *a, **k)
    if isinstance(cmd, list) and 'diff' in cmd:
        extra = ''.join('+' + l + '\n' for l in open(W + '/verantyx/routing_from_text.py', encoding='utf-8').read().split('\n')[:-1])
        r.stdout = r.stdout + extra
    return r
subprocess.run = fake
sys.argv = ['check_hardcode.py', '--base', 'e96a0cb']
runpy.run_path(W + '/tests/reading_soundness/check_hardcode.py', run_name='__main__')
