#!/bin/zsh
# One live stage of W2-b (B7).  usage: live_stage.zsh NAME FRAME CODEX_BIN CLAUDE_BIN [extra conduct args...]
# The toy repository lives under $TMPDIR (never under the worktree), the state is the default <repo>/.verantyx-conduct;
# everything worth keeping is copied to artifacts/w2-b/live/NAME afterwards.
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W2-b-S
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
A=$W/artifacts/w2-b; LIVE=$A/live
NAME=$1; FRAME=$2; CODEX_BIN=$3; CLAUDE_BIN=$4; shift 4
T=$(cat $LIVE/toy_dir.txt)
D=$LIVE/$NAME; mkdir -p $D
REPO=$T/$NAME
git init -q $REPO && git -C $REPO -c user.email=toy@localhost -c user.name=toy commit -q --allow-empty -m "toy: empty" && echo ".verantyx-conduct/" >> $REPO/.git/info/exclude
git -C $REPO for-each-ref --format='%(refname) %(objectname)' > $D/refs_before.txt; git -C $REPO rev-parse HEAD > $D/head_before.txt
REALPATH="$(dirname $PY):${PATH#$A/guardbin:}"
echo "cd $T && env PATH=$REALPATH PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1 $PY -m verantyx.cli conduct --frame $FRAME --repo $REPO --adapter codex --codex-bin $CODEX_BIN --claude-bin $CLAUDE_BIN $@" > $D/command.txt
date -u +%Y-%m-%dT%H:%M:%SZ > $D/started_utc.txt
cd $T && env PATH="$REALPATH" PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1 $PY -m verantyx.cli conduct \
  --frame $FRAME --repo $REPO --adapter codex --codex-bin $CODEX_BIN --claude-bin $CLAUDE_BIN "$@" \
  > $D/stdout.json 2> $D/stderr.txt; echo $? > $D/exit.txt
date -u +%Y-%m-%dT%H:%M:%SZ > $D/finished_utc.txt
L=$REPO/.verantyx-conduct; RUN=$(ls -t $L/runs | head -1)
cp $L/ledger.jsonl $D/ledger.jsonl
rsync -a --exclude worktree $L/runs/$RUN/ $D/rundir/
WT=$(ls -d $L/runs/$RUN/runtime/sessions/*/worktree 2>/dev/null | head -1)
[ -n "$WT" ] && git -C $WT show --stat --patch HEAD > $D/commit.txt && git -C $WT rev-parse HEAD > $D/commit_sha.txt
git -C $REPO for-each-ref --format='%(refname) %(objectname)' > $D/refs_after.txt; git -C $REPO rev-parse HEAD > $D/head_after.txt
git -C $REPO worktree list > $D/worktrees_after.txt
grep -rnE 'sk-[A-Za-z0-9_-]{12,}|Bearer [A-Za-z0-9]|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}' $D > $D/secret_scan.txt && echo "SECRET-LIKE TEXT FOUND: redact before keeping" >> $D/secret_scan.txt || echo "no secret-like text" > $D/secret_scan.txt
cat $D/exit.txt
