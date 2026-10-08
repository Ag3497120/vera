#!/bin/bash
# Run line-3 builds, measurements and tests on the MacBook Air over Thunderbolt.
# The Pro keeps the git repository; the Air only receives the working tree and returns results.
#
#   tools/air.sh push                 # Pro worktree -> air:~/vera-impl/line3 (code + small data; results and raw are kept on the Air)
#   tools/air.sh run <cmd...>         # run <cmd...> on the Air inside the tree (PYTHONPATH set; python = /opt/homebrew/bin/python3.11)
#   tools/air.sh py <args...>         # same as run, but prefixed with the Air's python
#   tools/air.sh pytest <args...>     # run pytest on the Air (no cache provider)
#   tools/air.sh bg <name> <cmd...>   # start <cmd...> on the Air under nohup; log at air:~/vera-impl/logs/<name>.log; prints the pid
#   tools/air.sh pull <path>          # air:~/vera-impl/line3/<path> -> Pro worktree/<path>  (results back)
#   tools/air.sh load                 # Air's uptime
set -u
HOST="${AIR_HOST:-air-tb}"
REMOTE="~/vera-impl/line3"
PY="/opt/homebrew/bin/python3.11"
ENV="cd $REMOTE && export PATH=/opt/homebrew/bin:\$PATH PYTHONPATH=.:\$HOME/vera-impl/pylib PYTHONHASHSEED=\${PYTHONHASHSEED:-0}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

case "${1:-}" in
  push)
    rsync -a --delete -e ssh \
      --exclude '.git' --exclude '__pycache__' --exclude '.pytest_cache' \
      --exclude 'experiments/line3/*/raw' --exclude 'experiments/line3/*/results' --exclude 'experiments/line3/*/logs' \
      --exclude 'experiments/line3/t9/audit/raw' --exclude 'experiments/line3/remote' \
      --exclude 'artifacts' --exclude 'hidden' \
      "$HERE/" "$HOST:$REMOTE/"
    git -C "$HERE" rev-parse HEAD | ssh "$HOST" "cat > $REMOTE/PRO_HEAD"
    ssh "$HOST" "cat $REMOTE/PRO_HEAD; du -sh $REMOTE | cut -f1"
    ;;
  run)  shift; ssh "$HOST" "$ENV && $*" ;;
  py)   shift; ssh "$HOST" "$ENV && $PY $*" ;;
  pytest) shift; ssh "$HOST" "$ENV && $PY -m pytest -q -p no:cacheprovider $*" ;;
  bg)
    shift; name="$1"; shift
    ssh "$HOST" "mkdir -p ~/vera-impl/logs && $ENV && nohup sh -c '$*' > ~/vera-impl/logs/$name.log 2>&1 < /dev/null & echo \$!"
    ;;
  pull)
    shift; p="$1"
    mkdir -p "$HERE/$(dirname "$p")"
    rsync -a -e ssh "$HOST:$REMOTE/$p" "$HERE/$(dirname "$p")/"
    ;;
  load) ssh "$HOST" "uptime; pgrep -fl python3.11 | grep -v pgrep | wc -l" ;;
  *) sed -n 2,12p "$0"; exit 2 ;;
esac
