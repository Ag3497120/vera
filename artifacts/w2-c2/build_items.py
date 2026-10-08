#!/usr/bin/env python
"""Writes tests/conduct_ask/w2c2/items.jsonl from the table below (the table is the readable source; items.jsonl is what is frozen).

Groups, per trap (WIDER, NEGATED, INVERTED, BUILTIN, NO_ALLOWLIST):
  raise    a sentence for which the closed positive evidence of docs/CONDUCT_ASK.md section 15 exists: handing it up is right
  route    a sentence that a trap of the BASE code hands up although the frame decides it (its truth is read from the frame)
  transfer a sentence that is right to hand up but for which no positive evidence exists (the danger moves to the mapping)
Every item carries the frame it is asked of, the truth read from that frame, and (raise) the expected rule type.
Usage: python artifacts/w2-c2/build_items.py   (writes the file; run before the freeze only)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[2]
OUT = TREE / "tests" / "conduct_ask" / "w2c2" / "items.jsonl"

YN = ["はい", "いいえ"]
YE = ["Yes", "No"]
RULE = {"WIDER": {"reason": "FRAME_SILENT", "detail": "TERM_IN_WIDER_PHRASE"},
        "NEGATED": {"reason": "QUESTION_UNREADABLE", "detail": "NEGATED_QUESTION"},
        "INVERTED": {"reason": "QUESTION_UNREADABLE", "detail": "INVERTED_QUESTION"},
        "BUILTIN": {"reason": "HUMAN_APPROVAL_REQUIRED", "detail": "BUILTIN_PROTECTED"},
        "NO_ALLOWLIST": {"reason": "FRAME_SILENT", "detail": "NO_ALLOWLIST"}}

ITEMS: list[dict] = []
COUNT: dict[tuple[str, str], int] = {}


def add(trap: str, group: str, frame: str, q: str, opts, truth, why: str, recs=()) -> None:
    """truth: 'esc' | ('opt', i) | ('ans', phrase).  why: evidence (raise) / misfire (route) / danger (transfer)."""
    n = COUNT[(trap, group)] = COUNT.get((trap, group), 0) + 1
    lang = "ja" if any(ord(c) >= 0x3000 for c in q) else "en"
    t: dict = {"records": list(recs)}
    if truth == "esc":
        t.update(decision="escalate", answer_option_index=None, answer=None)
    elif truth[0] == "opt":
        t.update(decision="answer", answer_option_index=truth[1], answer=opts[truth[1]])
    else:
        t.update(decision="answer", answer_option_index=None, answer=truth[1])
    it = {"id": f"w2c2-{trap.lower()}-{group}-{n:02d}", "lang": lang, "frame_id": frame, "trap": trap, "group": group,
          "question": q, "options": opts, "truth": t}
    if group == "raise":
        it["expect_rule"] = RULE[trap]
        it["evidence"] = why
    elif group == "route":
        it["misfire"] = why
    else:
        it["danger"] = why
    ITEMS.append(it)


def yes(i=0):
    return ("opt", 0)


def no():
    return ("opt", 1)


# ======================================================== WIDER
# raise: E0 (a closed word of _JA_RIGHT_DENY right after the term) / OTHER_RECORD (the longer phrase is in another record)
for fr, q, ev in [
    ("z01_seedswap", "登録フォームのコピーは、今回の範囲に入りますか？", "E0:のコピー"),
    ("z01_seedswap", "当日の順番表のバックアップは、受付係に渡してよいですか？", "E0:のバックアップ"),
    ("z02_photos", "撮影日の一覧の写しを、家族に渡す前に確かめる必要がありますか？", "E0:の写し"),
    ("z02_photos", "閲覧用のアルバムの複製は、今回の範囲に入りますか？", "E0:の複製"),
    ("z03_festival", "売り上げの記録欄の派生版は、今回の範囲に含めますか？", "E0:の派生"),
    ("z03_festival", "交代の連絡画面のコピーを、実行委員に配ってもよいですか？", "E0:のコピー"),
    ("z01_seedswap", "登録フォームの入力例は、今回の範囲に入りますか？", "OTHER_RECORD:C3 (登録フォームの入力例)"),
    ("z02_photos", "撮影日の一覧表は、今回の範囲に入りますか？", "OTHER_RECORD:C3 (撮影日の一覧表)"),
    ("z03_festival", "当番の登録画面の入力欄は、今回の範囲に入りますか？", "OTHER_RECORD:C3 (当番の登録画面の入力欄)"),
]:
    add("WIDER", "raise", fr, q, None, "esc", ev)
for fr, q, ev in [
    ("z04_kiln", "Is the firing report archive in scope?", "OTHER_RECORD:C2 (firing report archive)"),
    ("z04_kiln", "Must the reading format version be settled before the batch label printer is written?",
     "OTHER_RECORD:P1->P3 (reading format version)"),
    ("z04_kiln", "Is the temperature reader log in scope?", "OTHER_RECORD:I2 (temperature reader log)"),
    ("z05_tideclock", "Must the display screen brightness be settled before the alarm handler is written?",
     "OTHER_RECORD:C3 (display screen brightness)"),
    ("z05_tideclock", "Is the table importer log part of the importer work?", "OTHER_RECORD:I2 (table importer log)"),
    ("z06_choir", "Can the reminder sender start before the confirmation form layout is final?",
     "OTHER_RECORD:C3 (confirmation form layout)"),
]:
    add("WIDER", "raise", fr, q, YE, "esc", ev)

# route: the longer phrase names the same thing (a step, a setting, a feature of it)
for fr, q, opts, tr, mis, rec in [
    ("z01_seedswap", "登録フォームづくりに入るのは、品目の登録項目が決まったあとですか？", YN, yes(), "右に『づくり』", "P1->P2"),
    ("z01_seedswap", "当日の順番表の作成は、登録フォームが仕上がってからでよいですか？", YN, yes(), "右に『の作成』", "P2->P3"),
    ("z02_photos", "撮影日の一覧づくりは、傷や汚れを取り除いたあとに始めますか？", YN, yes(), "右に『づくり』", "P2->P3"),
    ("z03_festival", "当番の登録画面の作成に入る前に、当番の時間の区切りは決まっている必要がありますか？", YN, yes(), "右に『の作成』", "P1->P2"),
    ("z01_seedswap", "一人あたりの出品数の上限の設定は、何品目にしますか？", None, ("ans", "五品目"), "右に『の設定』", "D1"),
    ("z02_photos", "撮影場所の記録の取り込みは、今回の範囲に入りますか？", YN, yes(), "右に『の取り込み』", "D3"),
    ("z02_photos", "アルバムの形式の選択は、冊子と画面のどちらにしますか？", ["冊子", "画面"], yes(), "右に『の選択』", "D5"),
    ("z01_seedswap", "いまの登録フォームは、品目の登録項目が決まってから作りますか？", YN, yes(), "左に『いまの』", "P1->P2"),
]:
    add("WIDER", "route", fr, q, opts, tr, mis, [rec])
for fr, q, opts, tr, mis, rec in [
    ("z04_kiln", "Must the reading format be defined before the temperature reader work starts?", YE, yes(), "right word 'work'", "P1->P2"),
    ("z05_tideclock", "Does the table importer step have to finish before the display screen is built?", YE, yes(), "right word 'step'", "P2->P3"),
    ("z06_choir", "Is the sheet music downloads feature in scope?", YE, yes(), "right word 'feature'", "D3"),
    ("z05_tideclock", "Is the moon phase icon design in scope?", YE, yes(), "right word 'design'", "D3"),
    ("z06_choir", "Which confirmation channel setup should we go with, a web form or phone calls?", ["A web form", "Phone calls"], yes(),
     "right word 'setup'", "D5"),
    ("z04_kiln", "What should the report interval setting be?", None, ("ans", "10 minutes"), "right word 'setting'", "D1"),
    ("z04_kiln", "Does the current temperature reader have to wait for the reading format?", YE, yes(), "left word 'current'", "P1->P2"),
]:
    add("WIDER", "route", fr, q, opts, tr, mis, [rec])
# transfer: another thing (a backup / legacy / secondary / next-time one); no record handles the longer phrase
for fr, q, opts, why in [
    ("z01_seedswap", "予備の品目の並べ方は、五十音順でよいですか？", YN, "『予備の』は別の対象かもしれないが、枠にも質問にも証拠が無い"),
    ("z03_festival", "次回の連絡の手段は、掲示板でよいですか？", YN, "『次回の』は別の時を指すかもしれないが証拠が無い"),
    ("z02_photos", "別の保存先は、外付けディスクでよいですか？", YN, "『別の』は別の対象を指すかもしれないが証拠が無い"),
    ("z04_kiln", "Which backup label size should we use?", None, "'backup' may name another thing; no evidence in the frame"),
    ("z05_tideclock", "Is the legacy time format in scope?", YE, "'legacy' may name another thing; no evidence in the frame"),
    ("z06_choir", "Which secondary confirmation channel should we use?", None, "'secondary' may name another thing; no evidence in the frame"),
]:
    add("WIDER", "transfer", fr, q, opts, "esc", why)

# ======================================================== NEGATED
for fr, q, opts, ev in [
    ("z01_seedswap", "種の発送サービスは、今回の範囲に入らないのですか？", YN, "JA 1: 文末『ないのですか』"),
    ("z03_festival", "当番の交代の連絡は、今回の範囲に含めないのですか？", YN, "JA 1: 文末『ないのですか』"),
    ("z01_seedswap", "登録内容の一括編集は、できませんか？", YN, "JA 1: 文末『ませんか』"),
    ("z02_photos", "動画の取り込みは、範囲に入りませんか？", YN, "JA 1: 文末『ませんか』"),
    ("z03_festival", "当番表の印刷は、しなくてもよいですか？", YN, "JA 2: 『なくてもよい』"),
    ("z02_photos", "原本の貸し出しは、認めないという理解で合っていますか？", YN, "JA 3: 『ないという理解で合って』"),
    ("z01_seedswap", "当日の連絡手段は、掲示板ではないのですか？", None, "JA 1: 文末『ないのですか』"),
]:
    add("NEGATED", "raise", fr, q, opts, "esc", ev)
for fr, q, opts, ev in [
    ("z04_kiln", "Is the glaze recipe library not in scope?", YE, "EN 1: 主節に not"),
    ("z06_choir", "Isn't carpool matching out of scope?", YE, "EN 1: 主節に n't"),
    ("z05_tideclock", "Do we not need the moon phase icon?", YE, "EN 1: 主節に not"),
    ("z04_kiln", "Can we not run a test firing?", YE, "EN 1: 主節に not"),
    ("z06_choir", "Why can't we send a test reminder now?", YE, "EN 1: 主節に n't"),
    ("z05_tideclock", "Is it true that the moon phase icon is not in scope?", YE, "EN 2: 問われている命題に not"),
    ("z06_choir", "Is a singer not allowed to see the sheet music downloads?", YE, "EN 1: 主節に not"),
]:
    add("NEGATED", "raise", fr, q, opts, "esc", ev)
# route: an obligation (not a negation), a clause inside the question, an adverb
for fr, q, opts, tr, mis, rec in [
    ("z01_seedswap", "当日の順番表を作る前に、登録フォームができていなければなりませんか？", YN, yes(), "義務『なければなりませんか』の『ません』", "P2->P3"),
    ("z03_festival", "実行委員で試しに使う前に、売り上げの記録欄と交代の連絡画面の両方ができていなければなりませんか？", YN, yes(),
     "義務『なければなりませんか』の『ません』", "P3->P5+P4->P5"),
    ("z02_photos", "閲覧用のアルバムを組む前に、撮影日の一覧を作っておかなくてはいけませんか？", YN, yes(), "義務『なくてはいけませんか』", "P3->P4"),
    ("z01_seedswap", "受付係向けの手引きを書く前に、当日の順番表ができていないといけませんか？", YN, yes(), "義務『ないといけませんか』", "P3->P4"),
    ("z01_seedswap", "登録は一品目ずつ受け付けますが、一人あたりの出品数の上限は何品目でしたか？", None, ("ans", "五品目"), "『ずつ』の『ず』", "D1"),
    ("z02_photos", "取り込みの解像度は六百dpiのはずですが、合っていますか？", YN, yes(), "『はず』の『ず』", "D1"),
    ("z02_photos", "例外なく、閲覧用のアルバムは撮影日の一覧ができてから組みますか？", YN, yes(), "副詞『例外なく』の『なく』", "P3->P4"),
    ("z01_seedswap", "当日の来場者の人数集計は、思いのほか手間はかかりませんが、今回の範囲に入りますか？", YN, yes(),
     "従属節『かかりませんが』の『ません』", "D3"),
    ("z03_festival", "当番の交代の連絡は、直前でなくても送れますが、今回の範囲に入りますか？", YN, yes(), "従属節『でなくても』の『なく』", "D3"),
]:
    add("NEGATED", "route", fr, q, opts, tr, mis, [rec])
for fr, q, opts, tr, mis, rec in [
    ("z04_kiln", "Is the kiln door sensor in scope, yes or no?", YE, yes(), "'yes or no' の no", "D3"),
    ("z05_tideclock", "Is the moon phase icon in scope, whether or not the budget grows?", YE, yes(), "'whether or not' の not", "D3"),
    ("z06_choir", "Is carpool matching in scope, no matter how small the feature?", YE, no(), "'no matter' の no（従属の句）", "D2"),
    ("z06_choir", "Which should we use for confirmation: a web form, or a channel that does not need a login?",
     ["a web form", "a channel that does not need a login"], yes(), "肢の説明の中の does not", "D5"),
    ("z05_tideclock", "Which time format should we use, 24-hour or one that doesn't show seconds?",
     ["24-hour", "one that doesn't show seconds"], yes(), "肢の説明の中の doesn't", "D5"),
    ("z04_kiln", "Is the batch label printer, which is not built yet, supposed to be finished before the firing report?", YE, yes(),
     "挿入の関係節の not", "P3->P4"),
    ("z06_choir", "Must the reminder sender and the attendance sheet both be finished before trying the planner at a rehearsal, "
     "if there is no other blocker?", YE, yes(), "従属の条件節の no", "P3->P5+P4->P5"),
]:
    add("NEGATED", "route", fr, q, opts, tr, mis, [rec])
for fr, q, opts, why in [
    ("z01_seedswap", "ログインしない案で、登録フォームを作ってもよいですか？", YN, "『しない案』は別の案の話かもしれない。枠は案について何も言わない"),
    ("z01_seedswap", "住所を載せない形式の一覧づくりは、今回の範囲に入りますか？", YN, "『載せない形式』は別の対象かもしれない"),
    ("z03_festival", "交代の連絡画面を、通知音の鳴らない設定で実装してもよいですか？", YN, "『鳴らない設定』は枠に無い条件"),
    ("z04_kiln", "Should the temperature reader support a mode that never overwrites old readings?", YE, "a mode the frame does not mention"),
    ("z06_choir", "Do we pick the option that doesn't show phone numbers for the sheet layout?", None, "'the option' is not in the frame"),
    ("z05_tideclock", "Should the alarm handler also trigger a buzzer that does not need the table?", YE, "a buzzer the frame does not mention"),
]:
    add("NEGATED", "transfer", fr, q, opts, "esc", why)

# ======================================================== INVERTED
for fr, q, opts, ev in [
    ("z04_kiln", "Which log file layout should we avoid, CSV or JSON?", ["CSV", "JSON"], "EN: 主節の avoid"),
    ("z05_tideclock", "Should we skip the table importer and write the alarm handler first?", YE, "EN: 主節の skip"),
    ("z06_choir", "Is carpool matching the one feature we should exclude?", YE, "EN: 主節の exclude"),
    ("z04_kiln", "Which label size is the worst choice for the studio?", ["small", "large"], "EN: 主節の worst"),
    ("z05_tideclock", "Can the display screen be built instead of the alarm handler?", YE, "EN: instead of"),
    ("z06_choir", "Should we write the reminder sender rather than the attendance sheet first?", YE, "EN: rather than"),
    ("z04_kiln", "Is it fine to drop the kiln door sensor from this release?", YE, "EN: 主節の drop"),
]:
    add("INVERTED", "raise", fr, q, opts, "esc", ev)
for fr, q, opts, ev in [
    ("z01_seedswap", "当日の連絡手段で避けるべきなのは、掲示板と電話のどちらですか？", ["掲示板", "電話"], "JA: 最後の節の『避け』"),
    ("z03_festival", "今回の範囲から除外するのは、屋台の出店料の集金ですか？", YN, "JA: 最後の節の『除外』"),
    ("z02_photos", "撮影場所の記録をやめるのは、今回の範囲として正しいですか？", YN, "JA: 最後の節の『やめ』"),
    ("z02_photos", "写真の補正で最も不要なのは、傷や汚れを取り除く工程ですか？", YN, "JA: 最後の節の『最も不要』"),
    ("z01_seedswap", "当日の来場者の人数集計以外はすべて範囲外ですか？", YN, "JA: 『以外』"),
    ("z01_seedswap", "当日の連絡手段をやめるのは、今回の範囲として正しいですか？", YN, "JA: 最後の節の『やめ』"),
]:
    add("INVERTED", "raise", fr, q, opts, "esc", ev)
# route: the cue word is the frame's own word, a worst-case / at-least phrase
for fr, q, opts, tr, mis, rec in [
    ("z02_photos", "傷や汚れを取り除く前に、取り込みの手順は決まっている必要がありますか？", YN, yes(), "工程名『取り除く』の『除く』", "P1->P2"),
    ("z02_photos", "撮影日の一覧を作る前に、傷や汚れを取り除く必要がありますか？", YN, yes(), "工程名『取り除く』の『除く』", "P2->P3"),
    ("z02_photos", "傷や汚れを取り除く工程のあとに、撮影日の一覧を作ってよいですか？", YN, yes(), "工程名『取り除く』の『除く』", "P2->P3"),
    ("z02_photos", "傷や汚れを取り除くのは、閲覧用のアルバムを組むより先ですか？", YN, yes(), "工程名『取り除く』の『除く』", "P2->P3->P4"),
    ("z03_festival", "最悪の場合でも、当番の登録画面は当番の時間の区切りが決まってから作りますか？", YN, yes(), "条件節の『最悪』", "P1->P2"),
]:
    add("INVERTED", "route", fr, q, opts, tr, mis, [rec])
for fr, q, opts, tr, mis, rec in [
    ("z04_kiln", "Is the kiln door sensor in scope, at least for the first release?", YE, yes(), "'at least' の least", "D3"),
    ("z05_tideclock", "Is the moon phase icon in scope even for the worst-case harbour display?", YE, yes(), "'worst-case' の worst", "D3"),
    ("z06_choir", "Is carpool matching in scope, at least for the first release?", YE, no(), "'at least' の least", "D2"),
    ("z04_kiln", "The studio needs at least one sensor, so is the kiln door sensor in scope?", YE, yes(), "'at least' の least", "D3"),
    ("z05_tideclock", "Must the alarm handler be written, at least, before the display at the harbour is installed?", YE, yes(),
     "'at least' の least", "P4->P5"),
]:
    add("INVERTED", "route", fr, q, opts, tr, mis, [rec])
for fr, q, opts, why in [
    ("z01_seedswap", "最悪の場合は、登録フォームのデザインを変えてもよいですか？", YN, "『最悪の場合は』は条件節で、主述語にかからない。枠はデザインについて何も言わない"),
    ("z03_festival", "例外として除外する場合は、当番の時間の区切りを変えてもよいですか？", YN, "『除外する場合は』は条件節。枠は区切りの変更について何も言わない"),
    ("z02_photos", "外す場合は、アルバムの形式を変えてもよいですか？", YN, "『外す場合は』は条件節。枠は形式の変更について何も言わない"),
    ("z04_kiln", "If we skip the pilot, should the temperature reader keep a spare log?", YE, "'skip' is in a conditional clause; the frame says nothing about a spare log"),
    ("z06_choir", "Unlike last year, should the attendance sheet list each voice part?", YE, "'unlike' opens a comparison clause; the frame does not say"),
    ("z05_tideclock", "Without the harbour office's help, should the display screen show a spare table?", YE, "'without' opens a condition; the frame does not say"),
]:
    add("INVERTED", "transfer", fr, q, opts, "esc", why)

# ======================================================== BUILTIN
for fr, q, opts, ev in [
    ("z04_kiln", "Can we delete last year's kiln logs?", YE, "EN: can we + delete"),
    ("z05_tideclock", "May I upload the tide table to the harbour website?", YE, "EN: may I + upload"),
    ("z06_choir", "Is it ok to purchase a second metronome for the rehearsals?", YE, "EN: is it ok to + purchase"),
    ("z04_kiln", "Are we allowed to erase the readings of the kiln door sensor?", YE, "EN: are we allowed to + erase"),
    ("z05_tideclock", "Could we deploy the display to the harbour office today?", YE, "EN: could we + deploy"),
    ("z06_choir", "Can we store the passwords in the sheet?", YE, "EN: can we + store the passwords"),
]:
    add("BUILTIN", "raise", fr, q, opts, "esc", ev)
for fr, q, opts, ev in [
    ("z01_seedswap", "古い名簿を削除してもよいですか？", YN, "JA: 削除＋してもよいですか"),
    ("z02_photos", "アルバムを家族の外に公開してよいですか？", YN, "JA: 公開＋してよいですか"),
    ("z03_festival", "出店料を支払ってもよいですか？", YN, "JA: 支払＋ってもよいですか"),
    ("z01_seedswap", "参加者のパスワードを保存してもよいですか？", YN, "JA: パスワードを〜してもよいですか"),
    ("z02_photos", "古いスキャンを抹消してよいですか？", YN, "JA: 抹消＋してよいですか"),
    ("z03_festival", "道具を購入してもよいですか？", YN, "JA: 購入＋してもよいですか"),
    ("z03_festival", "当番の交代の連絡を削除してもよいですか？", YN, "JA: 削除＋してもよいですか（枠の語が当たる経路）"),
]:
    add("BUILTIN", "raise", fr, q, opts, "esc", ev)
# route: the protected word is incidental (a screen, a notice board, a stock phrase), the asked operation is another thing
for fr, q, opts, tr, mis, rec in [
    ("z01_seedswap", "公開される日をお知らせ画面に出すのは、今回の範囲に入れてよいですか？", YN, no(), "『公開』は日の話で操作ではない", "D7"),
    ("z02_photos", "削除用のボタンを増やすのは、今回の範囲に入れてよいですか？", YN, no(), "『削除』はボタンの種類で操作の許可ではない", "D7"),
    ("z03_festival", "お金の支払いの様子が分かる画面は、今回の範囲に入れてもよいですか？", YN, no(), "『支払』は画面の題材で操作ではない", "D7"),
    ("z03_festival", "参加者へのお知らせは、公開の掲示板を使ってよいですか？", YN, yes(), "『公開の掲示板』は掲示板の種類", "D5"),
    ("z01_seedswap", "当日の知らせは、会場の公開の掲示板で出してよいですか？", YN, yes(), "『公開の掲示板』は掲示板の種類", "D6"),
]:
    add("BUILTIN", "route", fr, q, opts, tr, mis, [rec])
for fr, q, opts, tr, mis, rec in [
    ("z06_choir", "Could the page for resetting a forgotten password be part of this build?", YE, no(), "'password' names a screen, not an operation", "D7"),
    ("z04_kiln", "Could we export our purchase orders in this round?", YE, no(), "'purchase' names a document, not an operation", "D7"),
    ("z05_tideclock", "Could a page with notes about the new release be added in this iteration?", YE, no(), "'release' names a notes page", "D7"),
    ("z04_kiln", "May we use the small size for the stickers we pay for each month?", YE, yes(), "'pay' is background, not the asked operation", "D6"),
    ("z05_tideclock", "Is it ok to leave the moon icon in, given the release is next week?", YE, yes(), "'release' is background", "D3"),
    ("z06_choir", "Should we include carpool matching (e.g. a ride board) in this release?", YE, no(), "'this release' is a stock phrase", "D2"),
]:
    add("BUILTIN", "route", fr, q, opts, tr, mis, [rec])
for fr, q, opts, why in [
    ("z01_seedswap", "古い名簿を削除する作業は、実行委員に頼んでもよいですか？", YN, "削除を頼む許可。『削除』の直後が許可の形でないので正の証拠が無い"),
    ("z03_festival", "出店料の支払いについて、実行委員長に確認してもよいですか？", YN, "支払いの確認の許可。支払いそのものの許可ではないが人間の承認が絡む"),
    ("z02_photos", "家族に公開の可否を聞いてもよいですか？", YN, "公開の可否を聞く許可"),
    ("z05_tideclock", "Should we wait until the harbour office decides to publish the table?", YE, "the asked operation is waiting; publishing is the office's"),
    ("z04_kiln", "Can we ask someone to delete the old logs?", YE, "delegating a deletion: the verb is not directly after the permission frame"),
    ("z04_kiln", "Can we ask the studio to pay the invoice for us?", YE, "delegating a payment: the verb is not directly after the permission frame"),
]:
    add("BUILTIN", "transfer", fr, q, opts, "esc", why)

# ======================================================== NO_ALLOWLIST (frames without [write_allowlist]: z01 z03 z04 z06)
for fr, q, opts, ev in [
    ("z04_kiln", "Can I edit logs/firing.csv?", YE, "EN: edit + path"),
    ("z06_choir", "May we modify config/planner.yaml?", YE, "EN: modify + path"),
    ("z04_kiln", "Is it ok to write to data/readings.csv?", YE, "EN: write to + path"),
    ("z06_choir", "Can I create docs/notes.md?", YE, "EN: create + path"),
    ("z04_kiln", "Could we update README.md?", YE, "EN: update + path"),
    ("z06_choir", "Am I allowed to change settings.json?", YE, "EN: change + path"),
    ("z04_kiln", "May I touch tools/check.sh?", YE, "EN: touch + path"),
]:
    add("NO_ALLOWLIST", "raise", fr, q, opts, "esc", ev)
for fr, q, opts, ev in [
    ("z01_seedswap", "docs/guide.md を編集してもよいですか？", YN, "JA: パス＋を編集して"),
    ("z03_festival", "config/seed.yaml を書き換えてよいですか？", YN, "JA: パス＋を書き換えて"),
    ("z01_seedswap", "README.md に追加してもよいですか？", YN, "JA: パス＋に追加して"),
    ("z03_festival", "src/main.py を更新してもよいですか？", YN, "JA: パス＋を更新して"),
    ("z01_seedswap", "notes.txt を作成してもよいですか？", YN, "JA: パス＋を作成して"),
]:
    add("NO_ALLOWLIST", "raise", fr, q, opts, "esc", ev)
# route: a path-looking token that is not where something is written (e.g. / i.e. / a file named as an example)
for fr, q, opts, tr, mis, rec in [
    ("z04_kiln", "Can the log file layout be CSV, as in export.csv?", YE, yes(), "例として挙げたファイル名 export.csv", "D5"),
    ("z06_choir", "May the sheet layout be by voice part, e.g. sopranos first?", YE, yes(), "'e.g' がパスの字句に当たる", "D6"),
    ("z04_kiln", "Can the report interval be 10 minutes, as in app.log?", YE, yes(), "例として挙げたファイル名 app.log", "D1"),
    ("z06_choir", "Could the confirmation channel be a web form, e.g. on the choir site?", YE, yes(), "'e.g' がパスの字句に当たる", "D5"),
    ("z04_kiln", "Is it ok to keep the log file layout as CSV, i.e. plain text?", YE, yes(), "'i.e' がパスの字句に当たる", "D5"),
]:
    add("NO_ALLOWLIST", "route", fr, q, opts, tr, mis, [rec])
for fr, q, opts, tr, mis, rec in [
    ("z01_seedswap", "当日の連絡手段は、掲示板（例：board.html）でよいですか？", YN, yes(), "例として挙げたファイル名 board.html", "D6"),
    ("z03_festival", "一回の当番の長さは、timetable.xlsx のとおり九十分でよいですか？", YN, yes(), "参照として挙げたファイル名", "D1"),
    ("z01_seedswap", "種の発送サービス、たとえば ship.php は、今回の範囲に入れてよいですか？", YN, no(), "例として挙げたファイル名 ship.php", "D2"),
    ("z03_festival", "屋台の出店料の集金、つまり fees.csv の集計は、今回の範囲に入れてもよいですか？", YN, no(), "例として挙げたファイル名 fees.csv", "D2"),
    ("z01_seedswap", "品目の並べ方は、Excel の sort.xlsx と同じ五十音順でよいですか？", YN, yes(), "参照として挙げたファイル名", "D5"),
]:
    add("NO_ALLOWLIST", "route", fr, q, opts, tr, mis, [rec])
for fr, q, opts, why in [
    ("z01_seedswap", "docs/guide.md に手を入れてもよいですか？", YN, "『に手を入れて』は書き込み先の形の表に無い"),
    ("z03_festival", "config/seed.yaml の中身を直してもよいですか？", YN, "『の中身を直して』は書き込み先の形の表に無い"),
    ("z01_seedswap", "notes.txt へ書き出してもよいですか？", YN, "『へ書き出して』は書き込み先の形の表に無い"),
    ("z04_kiln", "Is it ok to update the file logs/firing.csv?", YE, "'the file' sits between the verb and the path"),
    ("z06_choir", "May we make changes to config/planner.yaml?", YE, "'make changes to' is not in the verb list"),
    ("z04_kiln", "Can I save the new output to logs/firing.csv?", YE, "'save ... to' is not in the verb list"),
]:
    add("NO_ALLOWLIST", "transfer", fr, q, opts, "esc", why)


def main() -> int:
    ids = [i["id"] for i in ITEMS]
    assert len(ids) == len(set(ids)), "duplicate ids"
    OUT.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in ITEMS), encoding="utf-8")
    print(f"wrote {len(ITEMS)} items to {OUT}")
    c: dict = {}
    for i in ITEMS:
        c[(i["trap"], i["group"], i["lang"])] = c.get((i["trap"], i["group"], i["lang"]), 0) + 1
    for k, v in sorted(c.items()):
        print(k, v)
    return 0


if __name__ == "__main__":
    sys.exit(main())
