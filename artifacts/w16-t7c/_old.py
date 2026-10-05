"""修正前（ecde332）の ledger_events を git show から exec して得る。ファイルに写さない。"""
import subprocess
import types


def load_old(tree):
    src = subprocess.run(["git", "-C", tree, "show", "ecde332:verantyx/ledger_events.py"], capture_output=True, text=True, check=True).stdout
    m = types.ModuleType("ledger_events_old")
    m.__file__ = "ecde332:verantyx/ledger_events.py"
    exec(compile(src, m.__file__, "exec"), m.__dict__)
    return m
