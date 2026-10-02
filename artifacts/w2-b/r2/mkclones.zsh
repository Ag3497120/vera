#!/bin/zsh
# Make two clones of the work tree: base (dev f6085ff) and cand (base + the work tree's uncommitted files, committed).
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W2-b-S
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W2-b/impl-r2
D=$(mktemp -d "$S/clones.XXXXXX")
echo $D > $S/clones_dir.txt
git clone -q $W $D/base
git clone -q $W $D/cand
git -C $W status --porcelain=v1 --untracked-files=all | awk '{print $2}' | grep -v '^artifacts/' > $D/files.txt
while read p; do mkdir -p $D/cand/${p:h}; cp $W/$p $D/cand/$p; done < $D/files.txt
git -C $D/cand add -A
git -C $D/cand -c user.email=t@t -c user.name=t commit -q -m candidate
echo "clones in $D"; wc -l $D/files.txt
git -C $D/base log --oneline -1; git -C $D/cand log --oneline -2
