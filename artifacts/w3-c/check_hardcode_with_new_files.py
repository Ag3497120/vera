"""check_hardcode.py with the two new files' lines counted as added lines too (the checker reads only `git diff`, which does not show untracked files)."""
import subprocess, sys, runpy
W = '/Users/motonisihikoudai/Projects/vera-impl/wt/W3-c-S'
real = subprocess.run
def fake(cmd, *a, **k):
    r = real(cmd, *a, **k)
    if isinstance(cmd, list) and 'diff' in cmd:
        extra = ''
        for name in ('observe.py', 'salience.py'):
            extra += ''.join('+' + l + '\n' for l in open(W + '/verantyx/' + name, encoding='utf-8').read().split('\n')[:-1])
        r.stdout = r.stdout + extra
    return r
subprocess.run = fake
sys.argv = ['check_hardcode.py', '--base', '5cae978']
runpy.run_path(W + '/tests/reading_soundness/check_hardcode.py', run_name='__main__')
