# 配線の試行と撤回 (2026-09-02、PREREG_WIRE.md どおり)

`is_junk_core` を `candidates_for_query` の直接ヒット経路に配線し、凍結した3門で判定した。

    FORKS_ALL        PASS  178/178、skipped 0、落ちた fork なし
    GUARD_UNCHANGED  PASS  forks 89/89 / 測定 48/50(落ちる2件は凍結バイナリ不在で配線前と同一)
    HARNESS_MATCH    **FAIL**  raw 腕 14/212/74、登録した期待は 36/224/40

**登録どおり `git checkout` で撤回した。** 本番は無変更。

## なぜ外れたか — 治具が、測る対象と別の操作をしていた

    A2 の治具   cores = candidates_appended(...)  の**出力**から junk を除く
                → 候補列が短くなるだけ。空いた枠は埋まらない
    実際の配線   candidates_for_query の variants ループの**中**で junk を弾く
                → base が短くなり、candidates_appended が空き枠を facet 重なりで**埋め直す**
                → 候補列の中身が別物になる

同じ「junk を落とす」でも、落とす位置が違えば別の実験だった。
**「治具は測るものと同じ経路で作る」を破った4度目。** 門はそれを捕まえた。

## 配線そのものの実測値(門が落ちたので採用しないが、観測として)

同一治具・同一 seed で、配線の有無だけが違う2実行:

    配線なし  正答 13  誤答 231  棄権 56
    配線あり  正答 14  誤答 212  棄権 74      (誤答 −19、棄権 +18、正答 +1)

Vera の価値では誤答→棄権の移動は望ましい。**しかしこの数値は seen なので、
これを根拠に新しい判定線を書くことはしない。** 未見の探針で測り直す(PREREG_WIRE2.md)。

---

# WIRE2 (PREREG_WIRE2.md) — 未見 seed 4242。2本通り、1本落ちた

    seed 4242(未見)  baseline 正17 誤248 棄35 junk_top1 57
                     gated    正18 誤239 棄43 junk_top1 29
    seed 42(既見)    baseline 正13 誤231 棄56 junk_top1 50
                     gated    正14 誤219 棄67 junk_top1 24

    WRONG_DOWN         PASS (239 < 248)
    CORRECT_NOT_WORSE  PASS (18 ≥ 17)
    JUNK_TOP1_ZERO     **FAIL** (29 残る)

両 seed で向きは同じ: **誤答 −9〜−12、棄権 +8〜+11、正答 +1**。未見データで再現した。

## JUNK_TOP1_ZERO が落ちた理由 — 治具ではなく本番の構造

`candidates_for_query` は核を足す経路を**3つ**持つ(52-188行を読んで確認):

    ① 直接ヒット     store.has(v) で引く            (76, 83, 112行)  門なし
    ② 補完           if not seen and qset:          (120行)  store.crosses を直接走査、門なし
    ③ 末尾の残枠追記  if len(out) < k and qset:      (167行)  _word_index を走査、門なし

`is_junk_core` の門があるのは **別関数**(ja_consensus_ask の 730行) だけ。
WIRE2 の治具は `store.has` を包んだので①しか塞げず、junk は②③から入り直していた。

**つまり「junk が候補の先頭に座る」は、本番に実在する穴で、入口が3つある。**
①だけの配線(PREREG_WIRE)では JUNK_TOP1_ZERO は原理的に通らなかった。

---

# WIRE3 (PREREG_WIRE3.md) — 3経路すべてを塞ぐと、junk は消えるが誤答が増える

junk 核を除いた store 複製(89,273核 → junk 除去後)で3経路を同時に塞いだ。

    seed  777(未見) baseline 正15 誤235 棄44 junk55 到達285  gated 正17 誤242 棄42 junk0 到達285
    seed 4242(参考) baseline 正17 誤248 棄35 junk57 到達289  gated 正18 誤248 棄28 junk0 到達288
    seed   42(参考) baseline 正13 誤231 棄56 junk50 到達293  gated 正19 誤233 棄42 junk0 到達286

    WRONG_DOWN        **FAIL** (242 > 235)
    CORRECT_NOT_WORSE PASS (17 ≥ 15)
    JUNK_TOP1_ZERO    PASS (0)
    REACH_NOT_WORSE   PASS

**配線しない。** 登録どおり WRONG_DOWN が落ちた時点で提案を取り下げる。

## 三つの腕を並べると、両立していないことが見える

    seed 42        正答  誤答  棄権  junk先頭
    現行            13   231   56     50
    ①だけ塞ぐ        14   219   67     24     誤答 −12、棄権 +11、junk 半減
    ①②③全部塞ぐ     19   233   42      0     正答 +6、**誤答 +2、棄権 −14**

三つの seed すべてで同じ形:
    ①だけ    → 誤答が減り棄権が増える (Vera の価値に沿う)、しかし junk は先頭に残る
    全部     → junk は消え正答も増える、しかし **棄権が誤答に変わる**

## 機構 — junk_gate B の再現、より強い形で

junk_gate の実測は「帯から junk を抜くと、割れていた帯が唯一になり、正直な棄権4件が誤答4件に
化けた」だった。今回は**候補列そのものから抜いた**ので、同じ機構が10倍の規模で出た
(棄権 56→42、35→28、44→42)。

**junk 核は「余計なもの」であると同時に、shell を割り続けるおもりとして働いている。**
それが無くなると、正解が届いていない問いでも六断面が一致してしまい、自信のある誤答になる。

## 帰結 — 門だけでは解けない
「junk が候補の先頭に座る」(実在の穴、300探針中50-57件)と「誤答を減らす」は、
**門の強さを上げるだけでは両立しない**。junk を消すなら、junk が代行していた棄権を
別の構造で出す必要がある —— 問いが核を特定できているかの裁定(A2 で見た法令条文20件と同じ穴)。
これは門ではなく**特定性**の仕事で、別の登録になる。
