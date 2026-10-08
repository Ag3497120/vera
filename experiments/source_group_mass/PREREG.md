# 事前登録 — 出典グループで mass を数え直す(2026-09-02、実行前に凍結)
本体は ~/Projects/Vera/experiments/stereo_cross_neural/PREREG5.md §A。索引 `UNKNOWN_NOT_FOUND`(未実装)。
現在の mass = CrossStore.core_count = add() の回数(= 出現行数、leaf を跨いで合算)。
group mass  = vera.db `cores` の distinct leaf 数(同じ文書の反復は一票)。
治具は retrieval_reach/run_reach.py と同一経路(同じ300探針・seed 42/100/999・K・appended候補・run_consensus)。
腕: raw(現行) / group(store.mass を差し替え)。_MassView は 1+log1p(mass) のまま。
判定線: GROUP_CHANGES_TOP1  候補top1が腕間で異なる探針 ≥ 5% of asked
        GROUP_NOT_WORSE     group の正答 ≥ raw の正答
記述量: raw と group の順位相関、上位leaf占有率(既に 上位3000核で中央値0.32・≥0.9 が386核)。
予想: top1 は動く(1文書で数百面を持つ核がある)。正答が増えるかは持たない。誤答→棄権の移動を主に見る。
