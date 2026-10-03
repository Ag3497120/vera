#!/bin/zsh
# Round 2: the acceptance commands of the ticket, run one after another; outputs in this directory.
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W2-h-S; PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
A=$W/artifacts/w2-h/r2
vpy() { env PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1 $PY "$@"; }
cd $W
run() { name=$1; shift; { echo "\$ $*"; "$@"; echo "exit=$?"; } > $A/$name.txt 2>&1; tail -3 $A/$name.txt; }
run C0 vpy -c "import sys, verantyx.agent_routing, verantyx.project_frame, verantyx.conductor_run, verantyx.cli, verantyx.llm_choice; bad=[m.__file__ for n,m in sys.modules.items() if n.startswith('verantyx') and getattr(m,'__file__',None) and not m.__file__.startswith('$W/')]; print('outside:', bad); assert not bad"
run R0_import vpy -c "import sys, verantyx.agent_routing as r; print([m for m in ('verantyx.project_frame','verantyx.conductor_run','verantyx.cli') if m in sys.modules]); print(r.BASIS_KINDS)"
run R0 vpy -m pytest -q -p no:cacheprovider tests/test_agent_routing.py -k "R0 or producer or basis or order or fallback or essence or unsaid"
run R1 vpy -m pytest -q -p no:cacheprovider tests/test_agent_routing.py tests/test_agent_routing_dsl.py -k "R1 or UNKNOWN or DUPLICATE or DEFAULT or CYCLE"
run R2 vpy -m pytest -q -p no:cacheprovider tests/test_agent_routing.py -k "R2"
run R3 vpy -m pytest -q -p no:cacheprovider tests/test_agent_routing.py tests/test_conduct_routing.py -k "R3"
run R4 vpy -m pytest -q -p no:cacheprovider tests/test_agent_routing.py -k "R4"
run R6 vpy -m pytest -q -p no:cacheprovider tests/test_agent_routing.py tests/test_conduct_routing.py -k "R6"
run R5_legacy vpy -m pytest -q -p no:cacheprovider tests/test_conduct_routing.py -k "R5 or legacy"
run new_tests vpy -m pytest -q -p no:cacheprovider tests/test_agent_routing.py tests/test_agent_routing_dsl.py tests/test_conduct_routing.py
