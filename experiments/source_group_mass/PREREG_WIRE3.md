# 事前登録 — junk 門を3経路すべてに。未見 seed 777 で判定(2026-09-02、実行前に凍結)

## 直す対象(WIRE2 で読んで特定した本番の構造)
`candidates_for_query` の核の入口3つ(直接ヒット / not seen 補完 / 末尾残枠追記)は
どれも junk を通す。①だけ塞ぐ配線では JUNK_TOP1_ZERO は原理的に通らない。

## 治具(本番を編集しない)
junk 核を除いた **CrossStore の複製**(crosses と core_count から is_junk_core の核を除く)を作り、
その store で `candidates_for_query` を通す。3経路とも store.crosses / _word_index を見るので、
複製を渡せば**3経路すべてが同時に塞がる**。本番のソースは触らない。

## 探針: seed 777(未見)。判定は 777 のみ。4242 と 42 は参考として併記。
腕: baseline(現行store) / gated(複製store)。mass は raw、他は run_reach と同一。

## 判定線(凍結)
    WRONG_DOWN         gated の誤答 < baseline の誤答
    CORRECT_NOT_WORSE  gated の正答 ≥ baseline の正答
    JUNK_TOP1_ZERO     gated で top1 が junk の探針 = 0
    REACH_NOT_WORSE    gated の到達 ≥ baseline の到達 − 10(junk が gold の探針で落ちる分の許容)

## 予想
JUNK_TOP1_ZERO は構成上通る(store から消えているので入りようがない)。
WRONG_DOWN は通ると予想(WIRE2 が両 seed で −9〜−12)。
CORRECT_NOT_WORSE と REACH_NOT_WORSE は持たない —— 一文字核の門は 国・心・生 も落とし、
junk 核自身が gold の探針(seed42 では 6件)は必ず到達を失う。
