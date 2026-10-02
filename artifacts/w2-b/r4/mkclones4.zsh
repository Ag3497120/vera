#!/bin/zsh
# W2-b2 round 2: base (dev f6085ff) and cand (base + the work tree's 16 non-artifact files, committed) for the B8 re-measurement.
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W2-b-S
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W2-b2/impl-r2
mkdir -p $S
D=$(mktemp -d "$S/clones.XXXXXX")
echo $D > $S/clones_dir.txt
git clone -q $W $D/base
git clone -q $W $D/cand
git -C $W status --porcelain=v1 --untracked-files=all | awk '{print $2}' | grep -v '^artifacts/' > $D/files.txt
while read p; do mkdir -p $D/cand/${p:h}; cp $W/$p $D/cand/$p; done < $D/files.txt
git -C $D/cand add -A
git -C $D/cand -c user.email=t@t -c user.name=t commit -q -m candidate-r4
while read p; do cmp -s $W/$p $D/cand/$p || echo "MISMATCH $p"; done < $D/files.txt
echo "clones in $D"; wc -l < $D/files.txt
git -C $D/base log --oneline -1; git -C $D/cand log --oneline -2
git -C $D/base status --short | wc -l; git -C $D/cand status --short | wc -l
