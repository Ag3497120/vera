# Audit of bank 5 (bank5.jsonl, multi-session work memory)

Auditor: Claude (Opus 5.5), 2026-10-13. Inputs: `bank2-author/PROMPT5.md` (the brief), `bank2-author/out/bank5.jsonl` (6 tasks
MEM-T01..T06 by codex gpt-6-luna, which never saw Vera code), the author's `check5.py` / `check5.txt` (PASS) / `README5.md`.
No Vera reader, loom, session store, model or other Vera system has read the bank; `vera-impl/hidden` was not opened; no network.
Message refs are `[session, message]`, both 0-based (author's convention, kept).

Rules applied to every plant and question (the request): (1) a contradiction is genuine — no update/scope marker anywhere that could
be read as replacing, not reconcilable as two different facts, both values about exactly the same fact; (2) an update carries an
explicit marker and the gold is truly the latest value; (3) a list trap is really non-conflicting (different subjects/facts) but looks
alike; (4) a repeat is the identical fact; (5) a reversal states the same pair in opposite order; (6) a question is natural Japanese,
answerable only from sessions 1–2, its gold is correct, and session 3 does not restate the fact; (7) the surface form of every fact is
recorded (share of 「XのYはA」 vs other forms) but **not changed** — the model under test must do that normalisation itself. Minor
wording is fixed in place and every fix is logged below; each kind must keep ≥ 80 % of the brief.

## Counts (6 tasks; brief = per-task count × 6)

| kind | brief (6 tasks) | valid | fixed | dropped | kept |
|---|---|---|---|---|---|
| contradiction | 36 | 23 | 13 | 0 | 36 |
| update | 18 | 18 | 0 | 0 | 18 |
| list_trap | 24 | 18 | 6 | 0 | 24 |
| repeat | 12 | 9 | 3 | 0 | 12 |
| reversal | 12 | 0 | 12 | 0 | 12 |
| Q-contradiction | 24 | 0 | 24 | 0 | 24 |
| Q-update | 18 | 0 | 18 | 0 | 18 |
| Q-plain | 18 | 6 | 12 | 0 | 18 |
Totals: plants 102 → valid 68, fixed 34, dropped 0; questions 60 → valid 6, fixed 54, dropped 0. Every kind keeps 100 % of the brief
(17 plants and 10 questions per task, as authored).

## Main findings

1. **The author's checker rule shaped the bank.** `check5.py` demanded that *every* referenced message contain *every* value string of
   its plant. To pass it the author (a) gave each contradiction message a second clause carrying the other value, and (b) wrote every
   reversal message with both directions, the opposite one quoted as 「比較用の例文」「参照図には…ともあります」. Both had side effects:
2. **Nine unplanted contradictions** (fixed). In 9 message pairs the second clause swapped the value of *another slot of the same
   subject* between the two messages (T01 文言確認, T03 冷蔵庫の保管温度, T03 予備ラベル, T04 負荷試験用ホスト, T04 倉庫説明会, T05 救護講習の
   場所, T05 通訳者の到着予定, T05 飲料の単価, T06 閲覧用見本形式) — real contradictions with no plant and no question, so a system that
   flagged them would have been scored as hallucinating. A tenth (T05 一般席 120 vs 参加者用椅子 140席分) is the same swap across two
   names for the same seats. T03's list trap [1,6] 「培養器は37℃」 was a third statement of the contradicted 培養器設定温度 (and put a
   freezer at 4℃). Each fix renames only the subject of the extra clause (value and form kept), so the look-alike value stays.
3. **All 12 reversals were self-defeating** (fixed). Each message asserted one direction and quoted the other as an example, and the
   first carried a scope qualifier (今回の設計では / この計画では / 別工程表では), so the pair was reconcilable as two plans and each single
   message already contained the "reversal". Each message now states only its own direction; the source asides of the second message
   (工程メモでは, 契約確認表では, …) are kept; 「別工程表」 → 「工程表」.
4. **Every question announced its kind** (fixed, 42). Contradiction questions asked for 「二つの記録値」「食い違い」「記録された二人」; update
   questions said 変更後 / 延期後 / 更新後 / 最新. The bank tests whether the assistant *notices* conflicts and *applies* update markers,
   so all were reworded to the neutral form (「認証モジュールの担当者は誰ですか？」, 「QA締切はいつですか？」). Golds unchanged.
5. **Session 3 restated questioned facts** (fixed). In every task the two plain questions Q8/Q9 asked the two *repeat* facts, which by
   construction are restated verbatim in session 3 — answerable from session 3 alone (12 questions; replaced by unrepeated,
   unconflicted session-2 facts, each next to a look-alike value: 障害訓練→大阪, APIタイムアウト値→30秒 beside TTL 30秒, …). In T03/T04/
   T05/T06 the session-3 list trap restated the updated artefact (実験手順書 revD, 本番アプリ = 配布ビルド rc2, 案内チラシ v6, 取込マニフェスト
   v0.9) and T04 [2,6] restated 月額クラウド上限 20万円: artefacts renamed in the message (values kept), so the update questions now need
   the session-1/2 memory.
6. **Reconcilable contradictions** (fixed, 3). 「今回の発表会場」 (T01 [2,1]) and 「今回のシーケンス実行ID」 (T03 [2,0]) read as "this time's"
   — scope markers; dropped. T06 [0,5] said オブジェクト保存リージョン without 本番 while [2,0] named the other region 複製先, so the two
   could be read as replica vs primary; [0,5] now says 本番. T03 シーケンス実行ID stays the weakest contradiction (a run ID can be
   reissued); T02 参加者上限 280 vs 320 also coexists with 一般参加枠 280 (a reader may guess a slot mix-up) — both kept, same slot name.
7. **Repeats** used decision verbs (「共有ドライブは/release/testにしました」, 「…にします」) restated three times, which reads as re-deciding
   (an update-like cue on a fact that must not count as anything): plain copula. Three repeats occur three times; refs completed.
8. **Updates are all valid but all self-contained.** All 18 have an explicit marker in one message (「AからBに変更/延期/更新/改訂」) and the
   gold is B; nothing later contradicts them. But the old value never appears as a stored fact *before* the change — every update
   tests reading one 「AからB」 sentence, not superseding a value already in memory. Changing that means authoring new messages (out of
   audit scope); flagged for the owner.
9. **Template regularity (not fixed).** All six tasks use identical positions: contradictions at [0,0]/[0,1], [0,2]/[0,3], [0,4]/[1,0],
   [0,5]/[2,0], [1,1]/[1,2], [1,3]/[2,1]; updates at [0,7], [1,4], [1,5]; repeats [1,7]/[2,4] and [0,6]/[2,7]; reversals [2,2]/[2,8],
   [2,3]/[2,9]; questions always in the order 4 contradiction / 3 update / 3 plain, and the questioned contradictions are always the
   four that lie in sessions 1–2. Distances match the brief (3 same-session, 2 next-session, 1 two apart per task). Shuffle question
   order at run time and never show more than one task per context. The brief's "table row" surface form does not occur: tables
   appear only as source asides on prose (「担当表では」「予算表では」).
10. **Updates read off their fact as answer, not as contradiction.** A system that stores both values of an update sentence without
    the marker would answer 「矛盾: 6/12 と 6/14」 — that is wrong by design (gold = latest).

## Fact surface forms (rule 7; measured on the audited bank, not changed)

Clause-level classification (`。`/`、` split; a leading source aside 「〜では」「表の」「〜: 」 is stripped before classifying):
**XのYはA** = the topic before は contains の (「試験用APIの監視担当は井上です」); **slot** = topic without の, the entity and attribute fused
or the attribute implicit (「認証モジュール担当は田中です」「救護テントは駅前広場です」); **subjectless/list** = no topic (「配信費2万円です」,
「東京で切替リハーサルを行い」); **change** = 「XはAからBに変更…」; **relation** = 「AはBの前提」. "with source aside" and "verb predicate"
(ends in ます/ました instead of です) overlap the five columns. The audit changed no fact's form: it removed the 24 quoted reversal
clauses and one clause (T03 予備ラベル), renamed the subject of 18 non-question clauses within the same form, dropped 「今回の」 twice
and added 「本番」 once (T06, slot form kept).

ALL fact clauses
| task | facts | XのYはA | slot | subjectless/list | change | relation | with source aside | verb predicate |
|---|---|---|---|---|---|---|---|---|
| MEM-T01 | 45 | 2 (4 %) | 34 (76 %) | 2 (4 %) | 3 (7 %) | 4 (9 %) | 8 (18 %) | 1 (2 %) |
| MEM-T02 | 46 | 16 (35 %) | 23 (50 %) | 0 (0 %) | 3 (7 %) | 4 (9 %) | 4 (9 %) | 4 (9 %) |
| MEM-T03 | 47 | 12 (26 %) | 28 (60 %) | 0 (0 %) | 3 (6 %) | 4 (9 %) | 3 (6 %) | 3 (6 %) |
| MEM-T04 | 45 | 5 (11 %) | 31 (69 %) | 2 (4 %) | 3 (7 %) | 4 (9 %) | 4 (9 %) | 1 (2 %) |
| MEM-T05 | 45 | 16 (36 %) | 22 (49 %) | 0 (0 %) | 3 (7 %) | 4 (9 %) | 3 (7 %) | 0 (0 %) |
| MEM-T06 | 46 | 10 (22 %) | 29 (63 %) | 0 (0 %) | 3 (7 %) | 4 (9 %) | 3 (7 %) | 1 (2 %) |
| all | 274 | 61 (22 %) | 167 (61 %) | 4 (1 %) | 18 (7 %) | 24 (9 %) | 25 (9 %) | 10 (4 %) |

QUESTIONED fact clauses (contradiction questions count both statements)
| task | facts | XのYはA | slot | subjectless/list | change | relation | with source aside | verb predicate |
|---|---|---|---|---|---|---|---|---|
| MEM-T01 | 14 | 0 (0 %) | 11 (79 %) | 0 (0 %) | 3 (21 %) | 0 (0 %) | 4 (29 %) | 1 (7 %) |
| MEM-T02 | 14 | 1 (7 %) | 10 (71 %) | 0 (0 %) | 3 (21 %) | 0 (0 %) | 2 (14 %) | 2 (14 %) |
| MEM-T03 | 14 | 3 (21 %) | 8 (57 %) | 0 (0 %) | 3 (21 %) | 0 (0 %) | 1 (7 %) | 0 (0 %) |
| MEM-T04 | 14 | 2 (14 %) | 8 (57 %) | 1 (7 %) | 3 (21 %) | 0 (0 %) | 2 (14 %) | 1 (7 %) |
| MEM-T05 | 14 | 4 (29 %) | 7 (50 %) | 0 (0 %) | 3 (21 %) | 0 (0 %) | 1 (7 %) | 0 (0 %) |
| MEM-T06 | 14 | 5 (36 %) | 6 (43 %) | 0 (0 %) | 3 (21 %) | 0 (0 %) | 1 (7 %) | 0 (0 %) |
| all | 84 | 15 (18 %) | 50 (60 %) | 1 (1 %) | 18 (21 %) | 0 (0 %) | 11 (13 %) | 4 (5 %) |

Reading: only ~22 % of all facts and ~18 % of the questioned facts are in the 「XのYはA」 form; the majority (60 %) are fused-slot
statements (「認証モジュール担当は田中」) where X and Y must be split by the model, T01 and T04 almost entirely so. Every update is a
change sentence (21 % of questioned facts). For the meter, a structure that only stores literal 「XのYはA」 would see 15 of the 84
questioned statements as written.

## Re-check

`check5.py` (the audited checker, replaces the author's for this bank) → `check5.txt`: **PASS, 0 errors** — counts per kind and ≥ 80 %;
refs resolve; contradiction/reversal value i in ref i with no update/scope marker; reversal refs state one direction each and the values
are the same pair reversed; update = one ref with 「old から new + marker」; list trap values in the ref; repeat = one identical sentence in
≥ 2 sessions with all occurrences listed; question refs in sessions 1–2; contradiction gold = 「矛盾: X と Y」 of the plant on the same refs;
update gold = latest value of the plant on the same refs; plain gold in its ref and not a contradicted/updated value; no gold value and no
kind-announcing word (二つ/食い違/矛盾/異なる/変更後/最新/…) in the question; each question's subject key (audit table in the checker) occurs
in its ref and in **no** session-3 message; a lint for same-subject 「…はV」 with differing values outside the plants (0 hits; on the
original bank it lists the 9 unplanted contradictions of finding 2). The same checker on the author's original reports 103 errors
(24 both-direction reversal refs, 8 scope markers, 3 incomplete repeat refs, 42 kind-announcing questions, 4 session-3 restatements,
11 questions ending in 「。」, and 12 key mismatches that only reflect the replaced plain questions). The author's own `check5.py`
on the audited bank fails by design (its every-value-in-every-ref rule rejects the de-duplicated reversals and T05 [2,1]); its
sha256 and its original PASS output are recorded in MANIFEST.json.

## Per-item decisions

### MEM-T01 在庫管理アプリの小規模リリース

| item | kind | fact | decision | reason |
|---|---|---|---|---|
| P0 | contradiction | 認証モジュール担当 | valid | same slot named identically on both sides, two sources, no marker; the other clauses of the two messages are different slots |
| P1 | contradiction | リリース窓口担当 | valid | 「今朝の一覧では」 / 「表の」 are source asides, not time or correction markers |
| P2 | contradiction | 端末テスト責任者 | fixed | plant genuine; but the same message pair also swapped 文言確認 高橋 [0,4] / 森 [1,0] — an unplanted contradiction; [1,0]'s clause now names a different role |
| P3 | contradiction | 本番監視ポート | valid | two sessions apart; the other ports (検証ログ受信 8088, QA集計用 8443) are differently named ports — look-alike, no conflict |
| P4 | contradiction | CDNキャッシュTTL | valid | same slot named identically on both sides, two sources, no marker; the other clauses of the two messages are different slots |
| P5 | contradiction | 発表会場 | fixed | 「今回の発表会場」 in [2,1] reads as a scope/time marker (this time's venue) that makes the venues reconcilable; dropped |
| P6 | update | QA締切 | valid | explicit 「…から…へ/に…」 + marker in one message; gold = the new value; no later statement contradicts it |
| P7 | update | 会場費上限 | valid | explicit 「…から…へ/に…」 + marker in one message; gold = the new value; no later statement contradicts it |
| P8 | update | デモ用イメージ版 | valid | explicit 「…から…へ/に…」 + marker in one message; gold = the new value; no later statement contradicts it |
| P9 | list_trap | レビュー締切は対象ごとに異なる | valid | two differently named subjects in one message; neither value is stated for the other subject anywhere |
| P10 | list_trap | 会議・訓練の開催地 | valid | two differently named subjects in one message; neither value is stated for the other subject anywhere |
| P11 | list_trap | 会場費と配信費 | valid | 会場費 9万円 vs 配信費 2万円; 会場費 9万円 also agrees with the updated 上限 (cross-message look-alike) |
| P12 | list_trap | 本番配布版と利用ガイド版 | valid | two differently named subjects in one message; neither value is stated for the other subject anywhere |
| P13 | repeat | 試験用APIの監視担当 | valid | identical sentence in two sessions; no other value anywhere |
| P14 | repeat | 共有ドライブ | fixed | 「…にしました」 (decision/change verb) restated three times reads as re-deciding; plain copula; the [1,7] occurrence was missing from refs |
| P15 | reversal | フロント統合とAPI凍結の依存順 | fixed | both messages stated BOTH directions (the opposite one as a quoted 例文/比較/参照図 aside, i.e. framed as a non-assertion), and the first carried a scope qualifier (今回の…/この計画では/別工程表) that makes two directions reconcilable as two plans; each message now states only its own direction |
| P16 | reversal | 顧客受入テストと契約テストの依存順 | fixed | both messages stated BOTH directions (the opposite one as a quoted 例文/比較/参照図 aside, i.e. framed as a non-assertion), and the first carried a scope qualifier (今回の…/この計画では/別工程表) that makes two directions reconcilable as two plans; each message now states only its own direction |
| Q0 | Q-contradiction | 認証モジュールの担当者は誰ですか？ → 矛盾: 田中 と 佐藤 | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q1 | Q-contradiction | リリース窓口の担当者は誰ですか？ → 矛盾: 小林 と 渡辺 | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q2 | Q-contradiction | 端末テストの責任者は誰ですか？ → 矛盾: 森 と 高橋 | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q3 | Q-contradiction | CDNキャッシュTTLは何秒ですか？ → 矛盾: 120秒 と 30秒 | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q4 | Q-update | QA締切はいつですか？ → 6/14 | fixed | the question announced the update (変更後/延期後/更新後/最新); neutral wording — applying the marker is what is tested |
| Q5 | Q-update | 会場費の上限はいくらですか？ → 9万円 | fixed | the question announced the update (変更後/延期後/更新後/最新); neutral wording — applying the marker is what is tested |
| Q6 | Q-update | デモ用イメージのバージョンは何ですか？ → v2.4 | fixed | the question announced the update (変更後/延期後/更新後/最新); neutral wording — applying the marker is what is tested |
| Q7 | Q-plain | 認証レビューの締切はいつでしたか？ → 金曜 | valid | list-trap fact from session 1, not restated later; natural question |
| Q8 | Q-plain | 障害訓練はどこで行いますか？ → 大阪 | fixed | asked a repeat fact that session 3 restates verbatim (answerable from s3 alone); replaced by an unrepeated, unconflicted s1/s2 fact next to a look-alike value (was 「試験用APIの監視担当は誰ですか？」 → 井上) |
| Q9 | Q-plain | APIタイムアウト値は何秒ですか？ → 30秒 | fixed | asked a repeat fact that session 3 restates verbatim (answerable from s3 alone); replaced by an unrepeated, unconflicted s1/s2 fact next to a look-alike value (was 「共有ドライブのパスは何ですか？」 → /release/test) |

### MEM-T02 町なか映画祭の運営準備

| item | kind | fact | decision | reason |
|---|---|---|---|---|
| P0 | contradiction | 安全統括 | valid | same slot named identically on both sides, two sources, no marker; the other clauses of the two messages are different slots |
| P1 | contradiction | 舞台進行責任者 | valid | same slot named identically on both sides, two sources, no marker; the other clauses of the two messages are different slots |
| P2 | contradiction | 救護テントの設置場所 | valid | same slot named identically on both sides, two sources, no marker; the other clauses of the two messages are different slots |
| P3 | contradiction | 消防確認申請の締切 | valid | same slot named identically on both sides, two sources, no marker; the other clauses of the two messages are different slots |
| P4 | contradiction | 舞台音響チェック所要時間 | valid | same slot named identically on both sides, two sources, no marker; the other clauses of the two messages are different slots |
| P5 | contradiction | 参加者上限 | valid | s2 also gives 一般参加枠 280人, so a reader may guess s3 mixed up slots — but both statements name 参加者上限: genuine contradiction |
| P6 | update | 受付開始 | valid | explicit 「…から…へ/に…」 + marker in one message; gold = the new value; no later statement contradicts it |
| P7 | update | 会場利用料 | valid | explicit 「…から…へ/に…」 + marker in one message; gold = the new value; no later statement contradicts it |
| P8 | update | ポスター版 | valid | explicit 「…から…へ/に…」 + marker in one message; gold = the new value; no later statement contradicts it |
| P9 | list_trap | 受付と飲食ブースの終了時刻 | valid | two differently named subjects in one message; neither value is stated for the other subject anywhere |
| P10 | list_trap | 説明会と交流会の会場 | valid | two differently named subjects in one message; neither value is stated for the other subject anywhere |
| P11 | list_trap | 食事費と照明費 | valid | two differently named subjects in one message; neither value is stated for the other subject anywhere |
| P12 | list_trap | 進行表と安全チラシの版 | valid | two differently named subjects in one message; neither value is stated for the other subject anywhere |
| P13 | repeat | 救護班の無線チャンネル | valid | identical sentence in two sessions; no other value anywhere |
| P14 | repeat | 会場図の原本 | valid | identical sentence in two sessions; no other value anywhere |
| P15 | reversal | 字幕チェックと試写会の依存順 | fixed | both messages stated BOTH directions (the opposite one as a quoted 例文/比較/参照図 aside, i.e. framed as a non-assertion), and the first carried a scope qualifier (今回の…/この計画では/別工程表) that makes two directions reconcilable as two plans; each message now states only its own direction |
| P16 | reversal | 消防確認と屋台営業許可の依存順 | fixed | both messages stated BOTH directions (the opposite one as a quoted 例文/比較/参照図 aside, i.e. framed as a non-assertion), and the first carried a scope qualifier (今回の…/この計画では/別工程表) that makes two directions reconcilable as two plans; each message now states only its own direction |
| Q0 | Q-contradiction | 安全統括の担当者は誰ですか？ → 矛盾: 山田 と 西村 | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q1 | Q-contradiction | 舞台進行責任者は誰ですか？ → 矛盾: 吉岡 と 藤井 | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q2 | Q-contradiction | 救護テントはどこに設置しますか？ → 矛盾: 北広場 と 駅前広場 | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q3 | Q-contradiction | 舞台音響チェックの所要時間は何分ですか？ → 矛盾: 45分 と 60分 | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q4 | Q-update | 受付開始は何時ですか？ → 9:30 | fixed | the question announced the update (変更後/延期後/更新後/最新); neutral wording — applying the marker is what is tested |
| Q5 | Q-update | 会場利用料はいくらですか？ → 13万円 | fixed | the question announced the update (変更後/延期後/更新後/最新); neutral wording — applying the marker is what is tested |
| Q6 | Q-update | ポスターの版は何ですか？ → v1.2 | fixed | the question announced the update (変更後/延期後/更新後/最新); neutral wording — applying the marker is what is tested |
| Q7 | Q-plain | 入場券受付の終了時刻は何時ですか？ → 14:00 | valid | list-trap fact from session 1, not restated later; natural question |
| Q8 | Q-plain | 上映後交流会の会場はどこですか？ → 神戸文化室 | fixed | asked a repeat fact that session 3 restates verbatim (answerable from s3 alone); replaced by an unrepeated, unconflicted s1/s2 fact next to a look-alike value (was 「救護班の無線チャンネル番号はいくつですか？」 → 6) |
| Q9 | Q-plain | プログラムは何部印刷しますか？ → 450部 | fixed | asked a repeat fact that session 3 restates verbatim (answerable from s3 alone); replaced by an unrepeated, unconflicted s1/s2 fact next to a look-alike value (was 「会場図原本のファイルパスは何ですか？」 → /festival/map-v3.pdf) |

### MEM-T03 培養条件の共同実験

| item | kind | fact | decision | reason |
|---|---|---|---|---|
| P0 | contradiction | 冷凍庫鍵の管理者 | valid | same slot named identically on both sides, two sources, no marker; the other clauses of the two messages are different slots |
| P1 | contradiction | 試薬調製担当 | valid | same slot named identically on both sides, two sources, no marker; the other clauses of the two messages are different slots |
| P2 | contradiction | 培養器設定温度 | fixed | plant genuine; but [0,4]/[1,0] also swapped 冷蔵庫の保管温度 36.5/37.0℃ (unplanted contradiction, and physically impossible), and list trap [1,6] said 培養器は37℃ — a third statement of this very fact; second clauses now name other devices, [1,6] rewritten (see plant 10) |
| P3 | contradiction | シーケンス実行ID | fixed | 「今回のシーケンス実行ID」 in [2,0] marks a new run (a run ID is per run) → reconcilable; 「今回の」 dropped. Weakest contradiction of the bank (an ID could legitimately be reissued); kept |
| P4 | contradiction | 試料抽出時間 | valid | same slot named identically on both sides, two sources, no marker; the other clauses of the two messages are different slots |
| P5 | contradiction | 本試験の試料数 | fixed | plant genuine; but 予備ラベル 52枚 [1,3] / 48枚 [2,1] was an unplanted contradiction; clause removed from [2,1] |
| P6 | update | 採取日 | valid | explicit 「…から…へ/に…」 + marker in one message; gold = the new value; no later statement contradicts it |
| P7 | update | 試薬費上限 | valid | explicit 「…から…へ/に…」 + marker in one message; gold = the new value; no later statement contradicts it |
| P8 | update | 実験手順書版 | valid | explicit 「…から…へ/に…」 + marker in one message; gold = the new value; no later statement contradicts it (session 3 restated it through list trap 11/12 — fixed there) |
| P9 | list_trap | 清掃と校正の締切 | valid | two differently named subjects in one message; neither value is stated for the other subject anywhere |
| P10 | list_trap | 冷凍庫と培養器の設定温度 | fixed | not conflict-free: 培養器は37℃ restated the contradicted 培養器設定温度 (conflicts with [1,0]); 冷凍庫 at 4℃ is physically wrong. Now 冷凍庫1 -80℃ / 冷蔵庫2 4℃ (values changed) |
| P11 | list_trap | 試薬費と出張費 | valid | 試薬予算 6.5万円 vs 出張予算 2万円; 6.5万円 agrees with the updated 上限 |
| P12 | list_trap | 手順書版と集計スクリプト版 | fixed | [2,5] 「実験手順書はrevD」 restated the updated fact in session 3 (update question answerable from s3 alone); artefact renamed 測定テンプレート, values kept |
| P13 | repeat | 陰性対照ラベル | valid | identical sentence in two sessions; no other value anywhere |
| P14 | repeat | 生データ共有先 | fixed | 「…にします」 (decision verb) restated three times; plain copula; [1,7] occurrence added to refs |
| P15 | reversal | 試料抽出と蛍光測定の依存順 | fixed | both messages stated BOTH directions (the opposite one as a quoted 例文/比較/参照図 aside, i.e. framed as a non-assertion), and the first carried a scope qualifier (今回の…/この計画では/別工程表) that makes two directions reconcilable as two plans; each message now states only its own direction |
| P16 | reversal | 品質判定とシーケンス解析の依存順 | fixed | both messages stated BOTH directions (the opposite one as a quoted 例文/比較/参照図 aside, i.e. framed as a non-assertion), and the first carried a scope qualifier (今回の…/この計画では/別工程表) that makes two directions reconcilable as two plans; each message now states only its own direction |
| Q0 | Q-contradiction | 冷凍庫鍵の管理者は誰ですか？ → 矛盾: 小林 と 中村 | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q1 | Q-contradiction | 試薬調製の担当者は誰ですか？ → 矛盾: 柴田 と 岡本 | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q2 | Q-contradiction | 培養器の設定温度は何℃ですか？ → 矛盾: 37.0℃ と 36.5℃ | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q3 | Q-contradiction | 試料抽出時間は何分ですか？ → 矛盾: 8分 と 12分 | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q4 | Q-update | 採取日はいつですか？ → 11/04 | fixed | the question announced the update (変更後/延期後/更新後/最新); neutral wording — applying the marker is what is tested |
| Q5 | Q-update | 試薬費の上限はいくらですか？ → 6.5万円 | fixed | the question announced the update (変更後/延期後/更新後/最新); neutral wording — applying the marker is what is tested |
| Q6 | Q-update | 実験手順書のリビジョンは何ですか？ → revD | fixed | the question announced the update (変更後/延期後/更新後/最新); neutral wording — applying the marker is what is tested; session 3 had also restated the fact (fixed in the message, see the list trap) |
| Q7 | Q-plain | 抽出室清掃の締切は何曜日ですか？ → 火曜 | valid | list-trap fact from session 1, not restated later; natural question |
| Q8 | Q-plain | 遠心待機時間は何分ですか？ → 4分 | fixed | asked a repeat fact that session 3 restates verbatim (answerable from s3 alone); replaced by an unrepeated, unconflicted s1/s2 fact next to a look-alike value (was 「陰性対照ラベルの値は何ですか？」 → NC-04) |
| Q9 | Q-plain | 出張予算はいくらですか？ → 2万円 | fixed | asked a repeat fact that session 3 restates verbatim (answerable from s3 alone); replaced by an unrepeated, unconflicted s1/s2 fact next to a look-alike value (was 「生データの共有先パスを答えてください。」 → /lab/share/run) |

### MEM-T04 倉庫在庫アプリ3.2のリリース

| item | kind | fact | decision | reason |
|---|---|---|---|---|
| P0 | contradiction | トークン更新担当 | valid | same slot named identically on both sides, two sources, no marker; the other clauses of the two messages are different slots |
| P1 | contradiction | ストア申請者 | valid | same slot named identically on both sides, two sources, no marker; the other clauses of the two messages are different slots |
| P2 | contradiction | ステージングホスト | fixed | plant genuine; but 負荷試験用ホスト stg-b [0,4] / stg-a [1,0] was an unplanted contradiction; [1,0]'s clause now names 障害再現用ホスト |
| P3 | contradiction | 本番APIポート | valid | same slot named identically on both sides, two sources, no marker; the other clauses of the two messages are different slots |
| P4 | contradiction | 通信再試行回数 | valid | same slot named identically on both sides, two sources, no marker; the other clauses of the two messages are different slots |
| P5 | contradiction | 本番切替日 | fixed | plant genuine; but 倉庫説明会 11/20 [1,3] / 11/18 [2,1] was an unplanted contradiction; [2,1]'s clause now names 在庫棚卸し |
| P6 | update | 承認会議日 | valid | explicit 「…から…へ/に…」 + marker in one message; gold = the new value; no later statement contradicts it |
| P7 | update | 月額クラウド上限 | valid | explicit 「…から…へ/に…」 + marker in one message; gold = the new value; no later statement contradicts it (session 3 restated it through list trap 11/12 — fixed there) |
| P8 | update | 配布ビルド | valid | explicit 「…から…へ/に…」 + marker in one message; gold = the new value; no later statement contradicts it (session 3 restated it through list trap 11/12 — fixed there) |
| P9 | list_trap | 認証試験と在庫取込確認の締切 | valid | two differently named subjects in one message; neither value is stated for the other subject anywhere |
| P10 | list_trap | 切替リハーサルと利用者説明の都市 | valid | two differently named subjects in one message; neither value is stated for the other subject anywhere |
| P11 | list_trap | クラウド上限と端末試験予算 | fixed | rested on the update message [1,4] plus [2,6], which restated 月額クラウド上限 20万円 in session 3 (update question answerable from s3) and repeated 端末試験用予算 7万円 (unplanted repeat); [2,6] now 保守契約費 20万円 / 端末追加購入費 7万円 (same values, different lines), refs [[2,6]] |
| P12 | list_trap | 本番アプリと管理コンソールの版 | fixed | [2,5] 「本番アプリは3.2.0-rc2」 is the 配布ビルド again (update restated in s3); now 帳票モジュール |
| P13 | repeat | ログダッシュボード担当 | valid | identical sentence in two sessions; no other value anywhere |
| P14 | repeat | リリースブランチ | valid | identical sentence in two sessions; no other value anywhere |
| P15 | reversal | 移行ドライランとDB切替の依存順 | fixed | both messages stated BOTH directions (the opposite one as a quoted 例文/比較/参照図 aside, i.e. framed as a non-assertion), and the first carried a scope qualifier (今回の…/この計画では/別工程表) that makes two directions reconcilable as two plans; each message now states only its own direction |
| P16 | reversal | 脆弱性承認とアプリ申請の依存順 | fixed | both messages stated BOTH directions (the opposite one as a quoted 例文/比較/参照図 aside, i.e. framed as a non-assertion), and the first carried a scope qualifier (今回の…/この計画では/別工程表) that makes two directions reconcilable as two plans; each message now states only its own direction |
| Q0 | Q-contradiction | トークン更新の担当者は誰ですか？ → 矛盾: 平井 と 松本 | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q1 | Q-contradiction | ストア申請者は誰ですか？ → 矛盾: 石田 と 安藤 | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q2 | Q-contradiction | ステージングホストのホスト名は何ですか？ → 矛盾: stg-a.internal と stg-b.internal | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q3 | Q-contradiction | 通信再試行は何回までですか？ → 矛盾: 3回 と 5回 | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q4 | Q-update | 承認会議はいつですか？ → 11/10 | fixed | the question announced the update (変更後/延期後/更新後/最新); neutral wording — applying the marker is what is tested |
| Q5 | Q-update | 月額クラウド費の上限はいくらですか？ → 20万円 | fixed | the question announced the update (変更後/延期後/更新後/最新); neutral wording — applying the marker is what is tested; session 3 had also restated the fact (fixed in the message, see the list trap) |
| Q6 | Q-update | 配布ビルドのバージョンは何ですか？ → 3.2.0-rc2 | fixed | the question announced the update (変更後/延期後/更新後/最新); neutral wording — applying the marker is what is tested; session 3 had also restated the fact (fixed in the message, see the list trap) |
| Q7 | Q-plain | 認証試験の締切は何曜日ですか？ → 木曜 | valid | list-trap fact from session 1, not restated later; natural question |
| Q8 | Q-plain | 利用者説明はどこで行いますか？ → 名古屋 | fixed | asked a repeat fact that session 3 restates verbatim (answerable from s3 alone); replaced by an unrepeated, unconflicted s1/s2 fact next to a look-alike value (was 「ログダッシュボードの担当者は誰ですか？」 → 西田) |
| Q9 | Q-plain | 手動同期の上限は何回ですか？ → 5回 | fixed | asked a repeat fact that session 3 restates verbatim (answerable from s3 alone); replaced by an unrepeated, unconflicted s1/s2 fact next to a look-alike value (was 「リリースブランチ名を答えてください。」 → release/inventory-3.2) |

### MEM-T05 地域防災フォーラム

| item | kind | fact | decision | reason |
|---|---|---|---|---|
| P0 | contradiction | 司会担当 | valid | same slot named identically on both sides, two sources, no marker; the other clauses of the two messages are different slots |
| P1 | contradiction | 登壇者紹介担当 | valid | same slot named identically on both sides, two sources, no marker; the other clauses of the two messages are different slots |
| P2 | contradiction | 避難訓練場所 | fixed | plant genuine; but 救護講習の場所 中央公園 [0,4] / 南運動場 [1,0] was an unplanted contradiction; [1,0]'s clause now 炊き出し体験 |
| P3 | contradiction | 基調講演者の到着予定 | fixed | plant genuine; but 通訳者の到着予定 8:40 [0,5] / 8:10 [2,0] was an unplanted contradiction; [2,0]'s clause now 受付スタッフの集合 |
| P4 | contradiction | 弁当の単価 | fixed | plant genuine; but 飲料の単価 950円 [1,1] / 850円 [1,2] was an unplanted contradiction; [1,2]'s clause now 記念品 |
| P5 | contradiction | 来賓席数 | fixed | plant genuine; but [2,1] 「一般席は120席」 reads as the same seats as 参加者用椅子 140席分 [1,6] (unplanted contradiction); now 立ち見枠 120人 |
| P6 | update | 入場開始時刻 | valid | explicit 「…から…へ/に…」 + marker in one message; gold = the new value; no later statement contradicts it |
| P7 | update | 会場保険上限 | valid | explicit 「…から…へ/に…」 + marker in one message; gold = the new value; no later statement contradicts it |
| P8 | update | 案内チラシ版 | valid | explicit 「…から…へ/に…」 + marker in one message; gold = the new value; no later statement contradicts it (session 3 restated it through list trap 11/12 — fixed there) |
| P9 | list_trap | 救護班説明と通訳ブリーフィングの締切 | valid | two differently named subjects in one message; neither value is stated for the other subject anywhere |
| P10 | list_trap | 会場と展示見学の場所 | valid | two differently named subjects in one message; neither value is stated for the other subject anywhere |
| P11 | list_trap | 椅子と舞台の定員 | valid | two differently named subjects in one message; neither value is stated for the other subject anywhere |
| P12 | list_trap | 案内チラシと当日配布資料の版 | fixed | [2,5] 「案内チラシはv6」 restated the update in session 3; now 会場案内図 |
| P13 | repeat | 連絡用無線 | valid | identical sentence in two sessions; no other value anywhere |
| P14 | repeat | 共有ルート図 | valid | identical sentence in two sessions; no other value anywhere |
| P15 | reversal | 会場図作成と経路確認の依存順 | fixed | both messages stated BOTH directions (the opposite one as a quoted 例文/比較/参照図 aside, i.e. framed as a non-assertion), and the first carried a scope qualifier (今回の…/この計画では/別工程表) that makes two directions reconcilable as two plans; each message now states only its own direction |
| P16 | reversal | 警備配置確認と避難訓練実施の依存順 | fixed | both messages stated BOTH directions (the opposite one as a quoted 例文/比較/参照図 aside, i.e. framed as a non-assertion), and the first carried a scope qualifier (今回の…/この計画では/別工程表) that makes two directions reconcilable as two plans; each message now states only its own direction |
| Q0 | Q-contradiction | 司会担当は誰ですか？ → 矛盾: 藤田 と 野口 | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q1 | Q-contradiction | 登壇者紹介の担当者は誰ですか？ → 矛盾: 宮本 と 黒田 | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q2 | Q-contradiction | 避難訓練の場所はどこですか？ → 矛盾: 南運動場 と 中央公園 | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q3 | Q-contradiction | 弁当の単価はいくらですか？ → 矛盾: 850円 と 950円 | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q4 | Q-update | 入場開始は何時ですか？ → 13:30 | fixed | the question announced the update (変更後/延期後/更新後/最新); neutral wording — applying the marker is what is tested |
| Q5 | Q-update | 会場保険の上限はいくらですか？ → 5万円 | fixed | the question announced the update (変更後/延期後/更新後/最新); neutral wording — applying the marker is what is tested |
| Q6 | Q-update | 案内チラシの版は何ですか？ → v6 | fixed | the question announced the update (変更後/延期後/更新後/最新); neutral wording — applying the marker is what is tested; session 3 had also restated the fact (fixed in the message, see the list trap) |
| Q7 | Q-plain | 救護班説明の締切は何曜日ですか？ → 火曜 | valid | list-trap fact from session 1, not restated later; natural question |
| Q8 | Q-plain | 展示見学の場所はどこですか？ → 大阪市民ギャラリー | fixed | asked a repeat fact that session 3 restates verbatim (answerable from s3 alone); replaced by an unrepeated, unconflicted s1/s2 fact next to a look-alike value (was 「連絡用無線のチャンネルは何ですか？」 → ch3) |
| Q9 | Q-plain | 資料袋の単価はいくらですか？ → 500円 | fixed | asked a repeat fact that session 3 restates verbatim (answerable from s3 alone); replaced by an unrepeated, unconflicted s1/s2 fact next to a look-alike value (was 「共有ルート図の保存先パスは何ですか？」 → /forum/route-final.pdf) |

### MEM-T06 市史写真アーカイブの移行

| item | kind | fact | decision | reason |
|---|---|---|---|---|
| P0 | contradiction | 権利確認担当 | valid | same slot named identically on both sides, two sources, no marker; the other clauses of the two messages are different slots |
| P1 | contradiction | スキャン卓Aの担当 | valid | same slot named identically on both sides, two sources, no marker; the other clauses of the two messages are different slots |
| P2 | contradiction | マスター画像形式 | fixed | plant genuine; but 閲覧用見本形式 PNG [0,4] / TIFF [1,0] was an unplanted contradiction; [1,0]'s clause now 研究者向け提供形式 |
| P3 | contradiction | 本番オブジェクト保存リージョン | fixed | reconcilable: [0,5] said オブジェクト保存リージョン (no 本番) while [2,0] names ap-northeast-1 as 複製先, so ap-northeast-1 could be the replica region; [0,5] now says 本番 (slot form kept) |
| P4 | contradiction | チェックサムのブロックサイズ | valid | same slot named identically on both sides, two sources, no marker; the other clauses of the two messages are different slots |
| P5 | contradiction | 公開カタログ件数 | valid | same slot named identically on both sides, two sources, no marker; the other clauses of the two messages are different slots |
| P6 | update | スキャン締切 | valid | explicit 「…から…へ/に…」 + marker in one message; gold = the new value; no later statement contradicts it |
| P7 | update | 保存費上限 | valid | explicit 「…から…へ/に…」 + marker in one message; gold = the new value; no later statement contradicts it |
| P8 | update | 取込マニフェスト版 | valid | explicit 「…から…へ/に…」 + marker in one message; gold = the new value; no later statement contradicts it (session 3 restated it through list trap 11/12 — fixed there) |
| P9 | list_trap | スキャン机点検と権利確認の期限 | valid | two differently named subjects in one message; neither value is stated for the other subject anywhere |
| P10 | list_trap | 保存ディスクと作業SSD | valid | two differently named subjects in one message; neither value is stated for the other subject anywhere |
| P11 | list_trap | 保存費とOCR外注費 | valid | 保存費 24万円 vs OCR外注費 3万円; 24万円 agrees with the updated 上限 |
| P12 | list_trap | 取込マニフェストと目録スキーマの版 | fixed | [2,5] 「取込マニフェストはv0.9」 restated the update in session 3; now 取込スクリプト |
| P13 | repeat | 原本フォルダ | fixed | stated three times; [1,7] occurrence added to refs |
| P14 | repeat | チェックサム責任者 | valid | identical sentence in two sessions; no other value anywhere |
| P15 | reversal | OCR処理とメタデータ確認の依存順 | fixed | both messages stated BOTH directions (the opposite one as a quoted 例文/比較/参照図 aside, i.e. framed as a non-assertion), and the first carried a scope qualifier (今回の…/この計画では/別工程表) that makes two directions reconcilable as two plans; each message now states only its own direction |
| P16 | reversal | 権利確認とカタログ公開の依存順 | fixed | both messages stated BOTH directions (the opposite one as a quoted 例文/比較/参照図 aside, i.e. framed as a non-assertion), and the first carried a scope qualifier (今回の…/この計画では/別工程表) that makes two directions reconcilable as two plans; each message now states only its own direction |
| Q0 | Q-contradiction | 権利確認の担当者は誰ですか？ → 矛盾: 前田 と 大谷 | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q1 | Q-contradiction | スキャン卓Aの担当者は誰ですか？ → 矛盾: 長谷川 と 三浦 | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q2 | Q-contradiction | マスター画像の形式は何ですか？ → 矛盾: TIFF と PNG | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q3 | Q-contradiction | チェックサムのブロックサイズはいくつですか？ → 矛盾: 4MB と 8MB | fixed | the question announced the contradiction (二つ/食い違い/記録された二人), giving the kind away; neutral wording |
| Q4 | Q-update | スキャン締切はいつですか？ → 12/05 | fixed | the question announced the update (変更後/延期後/更新後/最新); neutral wording — applying the marker is what is tested |
| Q5 | Q-update | 保存費の上限はいくらですか？ → 24万円 | fixed | the question announced the update (変更後/延期後/更新後/最新); neutral wording — applying the marker is what is tested |
| Q6 | Q-update | 取込マニフェストのバージョンは何ですか？ → v0.9 | fixed | the question announced the update (変更後/延期後/更新後/最新); neutral wording — applying the marker is what is tested; session 3 had also restated the fact (fixed in the message, see the list trap) |
| Q7 | Q-plain | スキャン机点検の期限は何曜日ですか？ → 月曜 | valid | list-trap fact from session 1, not restated later; natural question |
| Q8 | Q-plain | 作業用SSDの容量はどれだけですか？ → 2TB | fixed | asked a repeat fact that session 3 restates verbatim (answerable from s3 alone); replaced by an unrepeated, unconflicted s1/s2 fact next to a look-alike value (was 「チェックサム責任者は誰ですか？」 → 河合さん) |
| Q9 | Q-plain | OCR外注費はいくらですか？ → 3万円 | fixed | asked a repeat fact that session 3 restates verbatim (answerable from s3 alone); replaced by an unrepeated, unconflicted s1/s2 fact next to a look-alike value (was 「原本フォルダのパスは何ですか？」 → /archive/raw/1950s) |

## Fixes (old → new)

Every edit asserted the old text before replacing it (`apply.py` in the audit scratchpad). Message texts are quoted whole.

**MEM-T01**

- msg [2,2]: `今回の設計ではフロント統合はAPI凍結の前提です。比較用の例文「API凍結はフロント統合の前提」もメモに載っています。` → `フロント統合はAPI凍結の前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- msg [2,3]: `今回の運用順では顧客受入テストは契約テストの前提です。比較用の例文「契約テストは顧客受入テストの前提」も資料にあります。` → `顧客受入テストは契約テストの前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- msg [2,8]: `工程メモではAPI凍結はフロント統合の前提です。比較図には「フロント統合はAPI凍結の前提」とも記されています。` → `工程メモではAPI凍結はフロント統合の前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- msg [2,9]: `契約確認表では契約テストは顧客受入テストの前提です。参照手順には「顧客受入テストは契約テストの前提」ともあります。` → `契約確認表では契約テストは顧客受入テストの前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- plant 15 (reversal): `{"note": "主張する依存方向と比較例の方向が逆。"}` → `{"note": "二つの発言が同じ工程の組の依存方向を逆向きに述べる（どちらにも訂正の印はない）。"}` — note described the both-directions-in-one-message construction
- plant 16 (reversal): `{"note": "依存の向きが逆の記述を同じ工程組について併記。"}` → `{"note": "二つの発言が同じ工程の組の依存方向を逆向きに述べる（どちらにも訂正の印はない）。"}` — note described the both-directions-in-one-message construction

**MEM-T02**

- msg [2,2]: `今回の段取りでは字幕チェックは試写会の前提です。比較例「試写会は字幕チェックの前提」も手順書にあります。` → `字幕チェックは試写会の前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- msg [2,3]: `今回の段取りでは消防確認は屋台営業許可の前提です。比較例「屋台営業許可は消防確認の前提」も資料に載っています。` → `消防確認は屋台営業許可の前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- msg [2,8]: `上映準備表では試写会は字幕チェックの前提です。関連図には「字幕チェックは試写会の前提」とも記載されています。` → `上映準備表では試写会は字幕チェックの前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- msg [2,9]: `出店手順では屋台営業許可は消防確認の前提です。参考図には「消防確認は屋台営業許可の前提」とあります。` → `出店手順では屋台営業許可は消防確認の前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- plant 15 (reversal): `{"note": "二方向の依存文を併記。"}` → `{"note": "二つの発言が同じ工程の組の依存方向を逆向きに述べる（どちらにも訂正の印はない）。"}` — note described the both-directions-in-one-message construction
- plant 16 (reversal): `{"note": "二方向の依存文を併記。"}` → `{"note": "二つの発言が同じ工程の組の依存方向を逆向きに述べる（どちらにも訂正の印はない）。"}` — note described the both-directions-in-one-message construction

**MEM-T03**

- msg [2,2]: `今回の手順では試料抽出は蛍光測定の前提です。比較用の例文「蛍光測定は試料抽出の前提」も記録にあります。` → `試料抽出は蛍光測定の前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- msg [2,3]: `今回の手順では品質判定はシーケンス解析の前提です。例文「シーケンス解析は品質判定の前提」も資料に記載されています。` → `品質判定はシーケンス解析の前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- msg [2,8]: `別工程表では蛍光測定は試料抽出の前提です。参照手順には「試料抽出は蛍光測定の前提」とも記載されています。` → `工程表では蛍光測定は試料抽出の前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- msg [2,9]: `解析メモではシーケンス解析は品質判定の前提です。比較図には「品質判定はシーケンス解析の前提」とあります。` → `解析メモではシーケンス解析は品質判定の前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- plant 15 (reversal): `{"note": "工程の依存方向が逆の記述。"}` → `{"note": "二つの発言が同じ工程の組の依存方向を逆向きに述べる（どちらにも訂正の印はない）。"}` — note described the both-directions-in-one-message construction
- plant 16 (reversal): `{"note": "工程の依存方向が逆の記述。"}` → `{"note": "二つの発言が同じ工程の組の依存方向を逆向きに述べる（どちらにも訂正の印はない）。"}` — note described the both-directions-in-one-message construction

**MEM-T04**

- msg [2,2]: `この計画では移行ドライランはDB切替の前提です。例として「DB切替は移行ドライランの前提」という文も手順にあります。` → `移行ドライランはDB切替の前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- msg [2,3]: `この計画では脆弱性承認はアプリ申請の前提です。比較文「アプリ申請は脆弱性承認の前提」も記録されています。` → `脆弱性承認はアプリ申請の前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- msg [2,8]: `切替手順ではDB切替は移行ドライランの前提です。参照図には「移行ドライランはDB切替の前提」ともあります。` → `切替手順ではDB切替は移行ドライランの前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- msg [2,9]: `提出チェック表ではアプリ申請は脆弱性承認の前提です。比較資料には「脆弱性承認はアプリ申請の前提」と記されています。` → `提出チェック表ではアプリ申請は脆弱性承認の前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- plant 15 (reversal): `{"note": "同じ作業ペアの依存方向が逆。"}` → `{"note": "二つの発言が同じ工程の組の依存方向を逆向きに述べる（どちらにも訂正の印はない）。"}` — note described the both-directions-in-one-message construction
- plant 16 (reversal): `{"note": "同じ作業ペアの依存方向が逆。"}` → `{"note": "二つの発言が同じ工程の組の依存方向を逆向きに述べる（どちらにも訂正の印はない）。"}` — note described the both-directions-in-one-message construction

**MEM-T05**

- msg [2,2]: `この工程では会場図作成はバリアフリー経路確認の前提です。例文「バリアフリー経路確認は会場図作成の前提」も資料に載っています。` → `会場図作成はバリアフリー経路確認の前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- msg [2,3]: `この工程では警備配置確認は避難訓練実施の前提です。比較用に「避難訓練実施は警備配置確認の前提」という文もあります。` → `警備配置確認は避難訓練実施の前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- msg [2,8]: `現場準備表ではバリアフリー経路確認は会場図作成の前提です。参照図には「会場図作成はバリアフリー経路確認の前提」ともあります。` → `現場準備表ではバリアフリー経路確認は会場図作成の前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- msg [2,9]: `実施段取りでは避難訓練実施は警備配置確認の前提です。比較手順には「警備配置確認は避難訓練実施の前提」とあります。` → `実施段取りでは避難訓練実施は警備配置確認の前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- plant 15 (reversal): `{"note": "同一二作業の依存方向が逆。"}` → `{"note": "二つの発言が同じ工程の組の依存方向を逆向きに述べる（どちらにも訂正の印はない）。"}` — note described the both-directions-in-one-message construction
- plant 16 (reversal): `{"note": "同一二作業の依存方向が逆。"}` → `{"note": "二つの発言が同じ工程の組の依存方向を逆向きに述べる（どちらにも訂正の印はない）。"}` — note described the both-directions-in-one-message construction

**MEM-T06**

- msg [2,2]: `この移行ではOCR処理はメタデータ確認の前提です。例文「メタデータ確認はOCR処理の前提」も資料にあります。` → `OCR処理はメタデータ確認の前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- msg [2,3]: `この手順では権利確認はカタログ公開の前提です。比較文「カタログ公開は権利確認の前提」も記録されています。` → `権利確認はカタログ公開の前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- msg [2,8]: `取込手順ではメタデータ確認はOCR処理の前提です。参照工程図には「OCR処理はメタデータ確認の前提」ともあります。` → `取込手順ではメタデータ確認はOCR処理の前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- msg [2,9]: `公開チェック表ではカタログ公開は権利確認の前提です。比較図には「権利確認はカタログ公開の前提」と記されています。` → `公開チェック表ではカタログ公開は権利確認の前提です。` — the message stated BOTH directions (the opposite one as a quoted 「例文/比較/参照図」 aside, i.e. framed as a non-assertion) and carried a scope qualifier (今回の/この計画では/別工程表) that makes the two directions reconcilable as two plans; only its own direction kept
- plant 15 (reversal): `{"note": "同じ工程ペアの依存方向が逆。"}` → `{"note": "二つの発言が同じ工程の組の依存方向を逆向きに述べる（どちらにも訂正の印はない）。"}` — note described the both-directions-in-one-message construction
- plant 16 (reversal): `{"note": "同じ工程ペアの依存方向が逆。"}` → `{"note": "二つの発言が同じ工程の組の依存方向を逆向きに述べる（どちらにも訂正の印はない）。"}` — note described the both-directions-in-one-message construction

**MEM-T01**

- msg [1,0]: `端末テスト責任者は高橋です。文言確認は森です。` → `端末テスト責任者は高橋です。スクリーンショット撮影は森です。` — unplanted contradiction: the second clause swapped the value of another slot of the same subject between the two messages (made only to satisfy the checker's every-value-in-every-ref rule); subject replaced, value kept (文言確認 高橋 [0,4] vs 森 [1,0])
- msg [2,1]: `今回の発表会場は港ラウンジです。資料搬入先は青葉ホールです。` → `発表会場は港ラウンジです。資料搬入先は青葉ホールです。` — 「今回の」 reads as a scope/time marker (this time's venue) that could make the two venues reconcilable; dropped

**MEM-T03**

- msg [0,4]: `培養器設定温度は37.0℃です。冷蔵庫の保管温度は36.5℃です。` → `培養器設定温度は37.0℃です。試薬保温器の設定温度は36.5℃です。` — unplanted contradiction: the second clause swapped the value of another slot of the same subject between the two messages (made only to satisfy the checker's every-value-in-every-ref rule); subject replaced, value kept (冷蔵庫 36.5/37.0℃, also physically impossible)
- msg [1,0]: `培養器設定温度は36.5℃です。冷蔵庫の保管温度は37.0℃です。` → `培養器設定温度は36.5℃です。培地予熱槽の設定温度は37.0℃です。` — unplanted contradiction: the second clause swapped the value of another slot of the same subject between the two messages (made only to satisfy the checker's every-value-in-every-ref rule); subject replaced, value kept (冷蔵庫 36.5/37.0℃)
- msg [1,6]: `冷凍庫1は4℃、培養器は37℃に設定しています。` → `冷凍庫1は-80℃、冷蔵庫2は4℃に設定しています。` — list trap was not conflict-free: 培養器は37℃ is a third statement of the contradicted 培養器設定温度 (agrees with [0,4], conflicts with [1,0]); and a freezer at 4℃ is physically wrong. Two different cold-storage devices instead
- plant 10 (list_trap): `{"fact": "冷凍庫と培養器の設定温度", "values": ["4℃", "37℃"], "note": "機器ごとの設定値。"}` → `{"fact": "冷凍庫1と冷蔵庫2の設定温度", "values": ["-80℃", "4℃"], "note": "別機器の設定値（どちらも冷却機器で似ている）。"}` — see msg [1,6]
- msg [2,0]: `今回のシーケンス実行IDはRUN-17です。受付検体バッチIDはRUN-71です。` → `シーケンス実行IDはRUN-17です。受付検体バッチIDはRUN-71です。` — 「今回の」 marks a new run (a run ID is per run), making RUN-71 / RUN-17 reconcilable as two runs; dropped (the form stays a slot statement, not rewritten to 「本試験の…」)
- msg [2,1]: `本試験の試料数は52本です。廃液ボトルは48本です。予備ラベルは48枚です。` → `本試験の試料数は52本です。廃液ボトルは48本です。` — unplanted contradiction: 予備ラベル 52枚 [1,3] vs 48枚 [2,1]; clause removed

**MEM-T04**

- msg [1,0]: `ステージングホストはstg-b.internalです。負荷試験用ホストはstg-a.internalです。` → `ステージングホストはstg-b.internalです。障害再現用ホストはstg-a.internalです。` — unplanted contradiction: the second clause swapped the value of another slot of the same subject between the two messages (made only to satisfy the checker's every-value-in-every-ref rule); subject replaced, value kept (負荷試験用ホスト stg-b [0,4] vs stg-a [1,0])
- msg [2,1]: `本番切替日は11月20日です。倉庫説明会は11月18日です。` → `本番切替日は11月20日です。在庫棚卸しは11月18日です。` — unplanted contradiction: the second clause swapped the value of another slot of the same subject between the two messages (made only to satisfy the checker's every-value-in-every-ref rule); subject replaced, value kept (倉庫説明会 11/20 [1,3] vs 11/18 [2,1])

**MEM-T05**

- msg [1,0]: `避難訓練場所は中央公園です。救護講習の場所は南運動場です。` → `避難訓練場所は中央公園です。炊き出し体験の場所は南運動場です。` — unplanted contradiction: the second clause swapped the value of another slot of the same subject between the two messages (made only to satisfy the checker's every-value-in-every-ref rule); subject replaced, value kept (救護講習 中央公園 [0,4] vs 南運動場 [1,0])
- msg [2,0]: `基調講演者の到着予定は8:40です。通訳者の到着予定は8:10です。` → `基調講演者の到着予定は8:40です。受付スタッフの集合は8:10です。` — unplanted contradiction: the second clause swapped the value of another slot of the same subject between the two messages (made only to satisfy the checker's every-value-in-every-ref rule); subject replaced, value kept (通訳者 8:40 [0,5] vs 8:10 [2,0])
- msg [1,2]: `弁当の単価は950円です。飲料の単価は850円です。` → `弁当の単価は950円です。記念品の単価は850円です。` — unplanted contradiction: the second clause swapped the value of another slot of the same subject between the two messages (made only to satisfy the checker's every-value-in-every-ref rule); subject replaced, value kept (飲料 950円 [1,1] vs 850円 [1,2])
- msg [2,1]: `来賓席は140席です。一般席は120席です。` → `来賓席は140席です。立ち見枠は120人です。` — unplanted contradiction: 一般席 120 [2,1] reads as the same seats as 参加者用椅子 140席分 [1,6] (the two messages swap 120/140 between 来賓席 and the general seats); replaced by a clearly different quantity

**MEM-T06**

- msg [1,0]: `マスター画像形式はPNGです。閲覧用見本形式はTIFFです。` → `マスター画像形式はPNGです。研究者向け提供形式はTIFFです。` — unplanted contradiction: the second clause swapped the value of another slot of the same subject between the two messages (made only to satisfy the checker's every-value-in-every-ref rule); subject replaced, value kept (閲覧用見本形式 PNG [0,4] vs TIFF [1,0])
- msg [0,5]: `オブジェクト保存リージョンはap-northeast-1です。検証用バケットはap-northeast-3です。` → `本番オブジェクト保存リージョンはap-northeast-1です。検証用バケットはap-northeast-3です。` — reconcilable: [0,5] did not say 本番 while [2,0] names ap-northeast-1 as 複製先, so ap-northeast-1 could be read as the replica region; both now state the 本番 region

**MEM-T03**

- msg [2,5]: `実験手順書はrevD、集計スクリプトはrevCです。` → `測定テンプレートはrevD、集計スクリプトはrevCです。` — session 3 restated the updated fact (same artefact, latest value), so the update question was answerable from session 3 alone; artefact renamed, values kept as a look-alike trap
- plant 12 (list_trap): `{"fact": "手順書版と集計スクリプト版", "note": "成果物ごとに版が違う。"}` → `{"fact": "測定テンプレートと集計スクリプトの版", "note": "別成果物の版（更新された実験手順書と同じ版名）。"}` — see msg [2,5]

**MEM-T04**

- msg [2,5]: `本番アプリは3.2.0-rc2、管理コンソールは3.1.8です。` → `帳票モジュールは3.2.0-rc2、管理コンソールは3.1.8です。` — session 3 restated the updated fact (same artefact, latest value), so the update question was answerable from session 3 alone; artefact renamed, values kept as a look-alike trap (本番アプリ 3.2.0-rc2 = the 配布ビルド)
- plant 12 (list_trap): `{"fact": "本番アプリと管理コンソールの版", "note": "別製品のバージョン。"}` → `{"fact": "帳票モジュールと管理コンソールの版", "note": "別コンポーネントの版（配布ビルドと同じ版名を含む）。"}` — see msg [2,5]
- msg [2,6]: `月額クラウド上限は20万円です。端末試験用予算は7万円です。` → `保守契約費は20万円です。端末追加購入費は7万円です。` — session 3 restated the updated fact (same artefact, latest value), so the update question was answerable from session 3 alone; artefact renamed, values kept as a look-alike trap (月額クラウド上限 20万円); also an unplanted repeat of 端末試験用予算 7万円 ([1,4])
- plant 11 (list_trap): `{"fact": "クラウド上限と端末試験予算", "message_refs": [[1, 4], [2, 6]], "note": "異なる費目の額。"}` → `{"fact": "保守契約費と端末追加購入費", "message_refs": [[2, 6]], "note": "別費目の額。値は更新後の月額クラウド上限・端末試験用予算と同じだが別の事実。"}` — list trap rested on the update message [1,4] plus the restating [2,6]; now the [2,6] pair (same values as the updated 上限 and 端末試験用予算, different budget lines)

**MEM-T05**

- msg [2,5]: `案内チラシはv6、当日配布資料はv5です。` → `会場案内図はv6、当日配布資料はv5です。` — session 3 restated the updated fact (same artefact, latest value), so the update question was answerable from session 3 alone; artefact renamed, values kept as a look-alike trap
- plant 12 (list_trap): `{"fact": "案内チラシと当日配布資料の版", "note": "異なる印刷物の版番号。"}` → `{"fact": "会場案内図と当日配布資料の版", "note": "別印刷物の版（改訂後の案内チラシと同じ版名）。"}` — see msg [2,5]

**MEM-T06**

- msg [2,5]: `取込マニフェストはv0.9、目録スキーマはv0.8です。` → `取込スクリプトはv0.9、目録スキーマはv0.8です。` — session 3 restated the updated fact (same artefact, latest value), so the update question was answerable from session 3 alone; artefact renamed, values kept as a look-alike trap
- plant 12 (list_trap): `{"fact": "取込マニフェストと目録スキーマの版", "note": "別成果物の版。"}` → `{"fact": "取込スクリプトと目録スキーマの版", "note": "別成果物の版（更新後の取込マニフェストと同じ版名）。"}` — see msg [2,5]

**MEM-T01**

- msg [0,6]: `認証レビュー期限は金曜、決済レビュー期限は月曜です。共有ドライブは/release/testにしました。` → `認証レビュー期限は金曜、決済レビュー期限は月曜です。共有ドライブは/release/testです。` — 「にしました」 is a decision/change verb; repeated three times it reads as re-deciding (an update-like marker on a repeat); plain copula
- msg [1,7]: `予算表では会場費9万円、配信費2万円です。試験用APIの監視担当は井上です。共有ドライブは/release/testにしました。` → `予算表では会場費9万円、配信費2万円です。試験用APIの監視担当は井上です。共有ドライブは/release/testです。` — 「にしました」 is a decision/change verb; repeated three times it reads as re-deciding (an update-like marker on a repeat); plain copula
- msg [2,7]: `共有ドライブは/release/testにしました。` → `共有ドライブは/release/testです。` — 「にしました」 is a decision/change verb; repeated three times it reads as re-deciding (an update-like marker on a repeat); plain copula

**MEM-T03**

- msg [0,6]: `抽出室清掃の締切は火曜、顕微鏡校正の締切は水曜です。生データ共有先は/lab/share/runにします。` → `抽出室清掃の締切は火曜、顕微鏡校正の締切は水曜です。生データ共有先は/lab/share/runです。` — 「にします」 is a decision/change verb; repeated three times it reads as re-deciding (an update-like marker on a repeat); plain copula
- msg [1,7]: `試薬予算は6.5万円、出張予算は2万円です。陰性対照ラベルはNC-04です。生データ共有先は/lab/share/runにします。` → `試薬予算は6.5万円、出張予算は2万円です。陰性対照ラベルはNC-04です。生データ共有先は/lab/share/runです。` — 「にします」 is a decision/change verb; repeated three times it reads as re-deciding (an update-like marker on a repeat); plain copula
- msg [2,7]: `生データ共有先は/lab/share/runにします。` → `生データ共有先は/lab/share/runです。` — 「にします」 is a decision/change verb; repeated three times it reads as re-deciding (an update-like marker on a repeat); plain copula

**MEM-T01**

- plant 14 (repeat): `{"message_refs": [[0, 6], [2, 7]]}` → `{"message_refs": [[0, 6], [1, 7], [2, 7]]}` — the fact is stated three times; [1,7] was missing

**MEM-T03**

- plant 14 (repeat): `{"message_refs": [[0, 6], [2, 7]]}` → `{"message_refs": [[0, 6], [1, 7], [2, 7]]}` — the fact is stated three times; [1,7] was missing

**MEM-T06**

- plant 13 (repeat): `{"message_refs": [[0, 6], [2, 7]]}` → `{"message_refs": [[0, 6], [1, 7], [2, 7]]}` — the fact is stated three times; [1,7] was missing

**MEM-T01**

- Q0 (contradiction): `{"q": "認証モジュールの担当者について、記録された二つの値は何ですか？"}` → `{"q": "認証モジュールの担当者は誰ですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q1 (contradiction): `{"q": "リリース窓口の担当者について、食い違う二つの記録を答えてください。"}` → `{"q": "リリース窓口の担当者は誰ですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q2 (contradiction): `{"q": "端末テストの責任者として記録された二人は誰ですか？"}` → `{"q": "端末テストの責任者は誰ですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q3 (contradiction): `{"q": "CDNキャッシュTTLについて、二つの記録値は何秒ですか？"}` → `{"q": "CDNキャッシュTTLは何秒ですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q4 (update): `{"q": "変更後のQA締切はいつですか？"}` → `{"q": "QA締切はいつですか？"}` — question announced the update (変更後/延期後/更新後/最新), giving away the kind; neutral wording — applying the marker is what is tested
- Q5 (update): `{"q": "変更後の会場費上限はいくらですか？"}` → `{"q": "会場費の上限はいくらですか？"}` — question announced the update (変更後/延期後/更新後/最新), giving away the kind; neutral wording — applying the marker is what is tested
- Q6 (update): `{"q": "デモ用イメージの最新バージョンは何ですか？"}` → `{"q": "デモ用イメージのバージョンは何ですか？"}` — question announced the update (変更後/延期後/更新後/最新), giving away the kind; neutral wording — applying the marker is what is tested
- Q8 (plain): `{"q": "試験用APIの監視担当は誰ですか？", "gold": "井上", "refs": [[1, 7]]}` → `{"q": "障害訓練はどこで行いますか？", "gold": "大阪", "refs": [[1, 6]]}` — plain question asked a repeat fact that session 3 restates verbatim (answerable from session 3 alone); replaced by an unrepeated, unconflicted session-1/2 fact next to a look-alike value
- Q9 (plain): `{"q": "共有ドライブのパスは何ですか？", "gold": "/release/test", "refs": [[0, 6]]}` → `{"q": "APIタイムアウト値は何秒ですか？", "gold": "30秒", "refs": [[1, 1]]}` — plain question asked a repeat fact that session 3 restates verbatim (answerable from session 3 alone); replaced by an unrepeated, unconflicted session-1/2 fact next to a look-alike value

**MEM-T02**

- Q0 (contradiction): `{"q": "安全統括の担当者について、異なる記録にある二人は誰ですか？"}` → `{"q": "安全統括の担当者は誰ですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q1 (contradiction): `{"q": "舞台進行責任者として書かれた二つの名前を答えてください。"}` → `{"q": "舞台進行責任者は誰ですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q2 (contradiction): `{"q": "救護テントの設置先として記録された二か所はどこですか？"}` → `{"q": "救護テントはどこに設置しますか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q3 (contradiction): `{"q": "舞台音響チェックの所要時間について、記録の食い違いは何分と何分ですか？"}` → `{"q": "舞台音響チェックの所要時間は何分ですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q4 (update): `{"q": "変更後の受付開始時刻は何時ですか？"}` → `{"q": "受付開始は何時ですか？"}` — question announced the update (変更後/延期後/更新後/最新), giving away the kind; neutral wording — applying the marker is what is tested
- Q5 (update): `{"q": "変更後の会場利用料はいくらですか？"}` → `{"q": "会場利用料はいくらですか？"}` — question announced the update (変更後/延期後/更新後/最新), giving away the kind; neutral wording — applying the marker is what is tested
- Q6 (update): `{"q": "ポスターの最新バージョンは何ですか？"}` → `{"q": "ポスターの版は何ですか？"}` — question announced the update (変更後/延期後/更新後/最新), giving away the kind; neutral wording — applying the marker is what is tested
- Q8 (plain): `{"q": "救護班の無線チャンネル番号はいくつですか？", "gold": "6", "refs": [[1, 7]]}` → `{"q": "上映後交流会の会場はどこですか？", "gold": "神戸文化室", "refs": [[1, 3]]}` — plain question asked a repeat fact that session 3 restates verbatim (answerable from session 3 alone); replaced by an unrepeated, unconflicted session-1/2 fact next to a look-alike value
- Q9 (plain): `{"q": "会場図原本のファイルパスは何ですか？", "gold": "/festival/map-v3.pdf", "refs": [[0, 6]]}` → `{"q": "プログラムは何部印刷しますか？", "gold": "450部", "refs": [[1, 6]]}` — plain question asked a repeat fact that session 3 restates verbatim (answerable from session 3 alone); replaced by an unrepeated, unconflicted session-1/2 fact next to a look-alike value

**MEM-T03**

- Q0 (contradiction): `{"q": "冷凍庫鍵の管理者について、二つの記録にある名前は何ですか？"}` → `{"q": "冷凍庫鍵の管理者は誰ですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q1 (contradiction): `{"q": "試薬調製担当として記録された二人を答えてください。"}` → `{"q": "試薬調製の担当者は誰ですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q2 (contradiction): `{"q": "培養器の設定温度について、異なる記録値を両方答えてください。"}` → `{"q": "培養器の設定温度は何℃ですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q3 (contradiction): `{"q": "試料抽出の所要時間として書かれていた値は何分と何分ですか？"}` → `{"q": "試料抽出時間は何分ですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q4 (update): `{"q": "延期後の採取日はいつですか？"}` → `{"q": "採取日はいつですか？"}` — question announced the update (変更後/延期後/更新後/最新), giving away the kind; neutral wording — applying the marker is what is tested
- Q5 (update): `{"q": "変更後の試薬費上限はいくらですか？"}` → `{"q": "試薬費の上限はいくらですか？"}` — question announced the update (変更後/延期後/更新後/最新), giving away the kind; neutral wording — applying the marker is what is tested
- Q6 (update): `{"q": "実験手順書の最新リビジョンは何ですか？"}` → `{"q": "実験手順書のリビジョンは何ですか？"}` — question announced the update (変更後/延期後/更新後/最新), giving away the kind; neutral wording — applying the marker is what is tested
- Q8 (plain): `{"q": "陰性対照ラベルの値は何ですか？", "gold": "NC-04", "refs": [[1, 7]]}` → `{"q": "遠心待機時間は何分ですか？", "gold": "4分", "refs": [[1, 1]]}` — plain question asked a repeat fact that session 3 restates verbatim (answerable from session 3 alone); replaced by an unrepeated, unconflicted session-1/2 fact next to a look-alike value
- Q9 (plain): `{"q": "生データの共有先パスを答えてください。", "gold": "/lab/share/run", "refs": [[0, 6]]}` → `{"q": "出張予算はいくらですか？", "gold": "2万円", "refs": [[1, 7]]}` — plain question asked a repeat fact that session 3 restates verbatim (answerable from session 3 alone); replaced by an unrepeated, unconflicted session-1/2 fact next to a look-alike value

**MEM-T04**

- Q0 (contradiction): `{"q": "トークン更新担当について、記録された二人の名前は何ですか？"}` → `{"q": "トークン更新の担当者は誰ですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q1 (contradiction): `{"q": "ストア申請者として書かれた二つの名前を答えてください。"}` → `{"q": "ストア申請者は誰ですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q2 (contradiction): `{"q": "ステージングホストについて、異なる二つの値は何ですか？"}` → `{"q": "ステージングホストのホスト名は何ですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q3 (contradiction): `{"q": "通信再試行回数について、記録の食い違いを答えてください。"}` → `{"q": "通信再試行は何回までですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q4 (update): `{"q": "延期後の承認会議日はいつですか？"}` → `{"q": "承認会議はいつですか？"}` — question announced the update (変更後/延期後/更新後/最新), giving away the kind; neutral wording — applying the marker is what is tested
- Q5 (update): `{"q": "変更後の月額クラウド上限はいくらですか？"}` → `{"q": "月額クラウド費の上限はいくらですか？"}` — question announced the update (変更後/延期後/更新後/最新), giving away the kind; neutral wording — applying the marker is what is tested
- Q6 (update): `{"q": "更新後の配布ビルド名は何ですか？"}` → `{"q": "配布ビルドのバージョンは何ですか？"}` — question announced the update (変更後/延期後/更新後/最新), giving away the kind; neutral wording — applying the marker is what is tested
- Q8 (plain): `{"q": "ログダッシュボードの担当者は誰ですか？", "gold": "西田", "refs": [[1, 7]]}` → `{"q": "利用者説明はどこで行いますか？", "gold": "名古屋", "refs": [[1, 6]]}` — plain question asked a repeat fact that session 3 restates verbatim (answerable from session 3 alone); replaced by an unrepeated, unconflicted session-1/2 fact next to a look-alike value
- Q9 (plain): `{"q": "リリースブランチ名を答えてください。", "gold": "release/inventory-3.2", "refs": [[0, 6]]}` → `{"q": "手動同期の上限は何回ですか？", "gold": "5回", "refs": [[1, 1]]}` — plain question asked a repeat fact that session 3 restates verbatim (answerable from session 3 alone); replaced by an unrepeated, unconflicted session-1/2 fact next to a look-alike value

**MEM-T05**

- Q0 (contradiction): `{"q": "司会担当について、異なる記録にある二人は誰ですか？"}` → `{"q": "司会担当は誰ですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q1 (contradiction): `{"q": "登壇者紹介の担当者として書かれた二つの名前を答えてください。"}` → `{"q": "登壇者紹介の担当者は誰ですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q2 (contradiction): `{"q": "避難訓練場所として記録されている二か所はどこですか？"}` → `{"q": "避難訓練の場所はどこですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q3 (contradiction): `{"q": "弁当単価について、記録にある二つの金額を答えてください。"}` → `{"q": "弁当の単価はいくらですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q4 (update): `{"q": "変更後の入場開始時刻は何時ですか？"}` → `{"q": "入場開始は何時ですか？"}` — question announced the update (変更後/延期後/更新後/最新), giving away the kind; neutral wording — applying the marker is what is tested
- Q5 (update): `{"q": "変更後の会場保険上限はいくらですか？"}` → `{"q": "会場保険の上限はいくらですか？"}` — question announced the update (変更後/延期後/更新後/最新), giving away the kind; neutral wording — applying the marker is what is tested
- Q6 (update): `{"q": "案内チラシの最新バージョンは何ですか？"}` → `{"q": "案内チラシの版は何ですか？"}` — question announced the update (変更後/延期後/更新後/最新), giving away the kind; neutral wording — applying the marker is what is tested
- Q8 (plain): `{"q": "連絡用無線のチャンネルは何ですか？", "gold": "ch3", "refs": [[1, 7]]}` → `{"q": "展示見学の場所はどこですか？", "gold": "大阪市民ギャラリー", "refs": [[1, 3]]}` — plain question asked a repeat fact that session 3 restates verbatim (answerable from session 3 alone); replaced by an unrepeated, unconflicted session-1/2 fact next to a look-alike value
- Q9 (plain): `{"q": "共有ルート図の保存先パスは何ですか？", "gold": "/forum/route-final.pdf", "refs": [[0, 6]]}` → `{"q": "資料袋の単価はいくらですか？", "gold": "500円", "refs": [[1, 1]]}` — plain question asked a repeat fact that session 3 restates verbatim (answerable from session 3 alone); replaced by an unrepeated, unconflicted session-1/2 fact next to a look-alike value

**MEM-T06**

- Q0 (contradiction): `{"q": "権利確認担当について、異なる記録にある二人の名前は何ですか？"}` → `{"q": "権利確認の担当者は誰ですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q1 (contradiction): `{"q": "スキャン卓Aの担当として記された二つの名前を答えてください。"}` → `{"q": "スキャン卓Aの担当者は誰ですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q2 (contradiction): `{"q": "マスター画像形式について、記録された二つの値は何ですか？"}` → `{"q": "マスター画像の形式は何ですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q3 (contradiction): `{"q": "チェックサムのブロックサイズについて、二つの記録値は何ですか？"}` → `{"q": "チェックサムのブロックサイズはいくつですか？"}` — question announced the contradiction (二つ/食い違い/記録された二人), giving away the kind; neutral wording — detecting the conflict is what is tested
- Q4 (update): `{"q": "延期後のスキャン締切はいつですか？"}` → `{"q": "スキャン締切はいつですか？"}` — question announced the update (変更後/延期後/更新後/最新), giving away the kind; neutral wording — applying the marker is what is tested
- Q5 (update): `{"q": "変更後の保存費上限はいくらですか？"}` → `{"q": "保存費の上限はいくらですか？"}` — question announced the update (変更後/延期後/更新後/最新), giving away the kind; neutral wording — applying the marker is what is tested
- Q6 (update): `{"q": "取込マニフェストの最新バージョンは何ですか？"}` → `{"q": "取込マニフェストのバージョンは何ですか？"}` — question announced the update (変更後/延期後/更新後/最新), giving away the kind; neutral wording — applying the marker is what is tested
- Q8 (plain): `{"q": "チェックサム責任者は誰ですか？", "gold": "河合さん", "refs": [[1, 7]]}` → `{"q": "作業用SSDの容量はどれだけですか？", "gold": "2TB", "refs": [[1, 6]]}` — plain question asked a repeat fact that session 3 restates verbatim (answerable from session 3 alone); replaced by an unrepeated, unconflicted session-1/2 fact next to a look-alike value
- Q9 (plain): `{"q": "原本フォルダのパスは何ですか？", "gold": "/archive/raw/1950s", "refs": [[0, 6]]}` → `{"q": "OCR外注費はいくらですか？", "gold": "3万円", "refs": [[1, 7]]}` — plain question asked a repeat fact that session 3 restates verbatim (answerable from session 3 alone); replaced by an unrepeated, unconflicted session-1/2 fact next to a look-alike value