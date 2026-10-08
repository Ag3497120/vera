# 事前登録 — junk 門の配線を、未見の探針で判定する(2026-09-02、実行前に凍結)

## なぜ再登録か
PREREG_WIRE の HARNESS_MATCH は、治具が配線と別の操作をしていたため外れた(RESULTS_WIRE.md)。
配線ありの数値(14/212/74)は既に見てしまったので、**seed 42 の探針は判定に使えない**。

## 治具(本番を編集しない)
`store.has` を包み、`is_junk_core(v)` が真なら False を返す。`variants()` は store.has で引くので、
junk は直接ヒット経路に入らず、全部 junk なら `if not seen` の facet 補完が正しく発火する
—— これは配線の効果と同一で、かつ本番のソースを触らない。

## 探針: **seed 4242**(未見)。populationも mid_facets も 42→4242、他は run_reach と同一。
腕: baseline(現行) / gated(上の包み)。両腕とも appended 候補、mass は raw。

## 判定線(凍結)
    WRONG_DOWN         gated の誤答 < baseline の誤答
    CORRECT_NOT_WORSE  gated の正答 ≥ baseline の正答
    JUNK_TOP1_ZERO     gated で top1 が junk の探針 = 0
参考として seed 42 も両腕で出すが、**判定は 4242 のみ**。
3本とも通れば配線を提案する(配線後は再度 FORKS_ALL と GUARD を掛ける)。落ちたら配線しない。

## 予想
JUNK_TOP1_ZERO は構成上通る。WRONG_DOWN は通ると予想する。
CORRECT_NOT_WORSE は持たない —— 一文字核の門は 国・心・生 のような内容語も落とすため。
