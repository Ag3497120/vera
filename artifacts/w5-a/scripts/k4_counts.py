# prints how many asks the fake provider received in each scenario (K4). usage: k4_counts.py <tree> <scratch_dir>   (tree = the directory that holds tests/attack)
import importlib.util, sys, tempfile, pathlib
tree = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location('k4', tree / 'tests/attack/test_w5a_testimony_reuse_key.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
from verantyx.agent_routing import route
from verantyx.llm_choice import ChoiceCandidate
def go(label, steps):
    d = pathlib.Path(tempfile.mkdtemp(prefix='k4_', dir=sys.argv[2]))
    p = m.ByContext(); c = m._chooser(p, d)
    for name, fn in steps:
        r = fn(c); print('%-34s %-34s asks_so_far=%d cached=%s' % (label, name, p.calls, r))
T = m._table
rt = lambda t: (lambda c: route(t, m.REQUEST, chooser_factory=lambda: c).testimony['cached'])
go('same table twice', [('route 1', rt(T('A is the clear best fit.', 'B is less suitable.'))), ('route 2 (same)', rt(T('A is the clear best fit.', 'B is less suitable.')))])
go('reasons flipped', [('route 1', rt(T('A is the clear best fit.', 'B is less suitable.'))), ('route 2 (reasons changed)', rt(T('A is less suitable.', 'B is the clear best fit.')))])
go('model only', [('route 1 (model-one)', rt(T('A is the clear best fit.', 'B is less suitable.', 'model-one'))), ('route 2 (model-two)', rt(T('A is the clear best fit.', 'B is less suitable.', 'model-two'))), ('route 3 (model-two again)', rt(T('A is the clear best fit.', 'B is less suitable.', 'model-two')))])
a, b = ChoiceCandidate('A', ('A is the one MARK',)), ChoiceCandidate('B', ('B is other',))
ch = lambda cands, q='': (lambda c: c.choose('w', cands, q).cached)
m.ByContext.__init__.__defaults__ = ('MARK',)
go('chooser direct', [('first', ch([a, b])), ('order reversed, same context', ch([b, a])), ('A context changed', ch([ChoiceCandidate('A', ('A is something else',)), ChoiceCandidate('B', ('B is other MARK',))])), ('B gets one more line', ch([a, ChoiceCandidate('B', ('B is other', 'B has one more line'))])), ('question changed only', ch([a, b], 'other question'))])
