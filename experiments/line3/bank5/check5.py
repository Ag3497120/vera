#!/usr/bin/env python3
"""Mechanical check of the AUDITED bank 5 (multi-session work memory).

Extends the author's check5.py (codex gpt-6-luna; its original output was PASS on the
original bank) with per-kind value rules and question rules introduced by the audit
(AUDIT5.md). Usage: python check5.py [bank5.jsonl]
"""
import json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

BANK = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "bank5.jsonl"
BRIEF_PLANTS = {"contradiction": 6, "update": 3, "list_trap": 4, "repeat": 2, "reversal": 2}
BRIEF_Q = {"contradiction": 4, "update": 3, "plain": 3}
MIN_SHARE = 0.8  # audit rule: kept count per kind >= 80 % of the brief (over the whole bank)
IDS = [f"MEM-T{i:02d}" for i in range(1, 7)]
UPDATE_MARK = re.compile(r"から.+?(へ|に).*?(変更|延期|更新|改訂|引き上げ)")
LEAK = re.compile(r"二つ|二人|二か所|食い違|矛盾|異なる|両方|変更後|延期後|更新後|最新|記録された")
# audit keys: the subject phrase of each question as it is written in the referenced
# message; it must occur there and in NO session-3 message (rule 6: not answerable from
# session 3 alone).
KEYS = {
 "MEM-T01": ["認証モジュール担当", "リリース窓口担当", "端末テスト責任者", "CDNキャッシュTTL", "QA締切", "会場費上限", "デモ用イメージ", "認証レビュー期限", "障害訓練", "APIタイムアウト値"],
 "MEM-T02": ["安全統括", "舞台進行責任者", "救護テント", "舞台音響チェック", "受付開始", "会場利用料", "ポスター", "入場券の受付終了", "上映後交流会", "プログラム"],
 "MEM-T03": ["冷凍庫鍵の管理者", "試薬調製担当", "培養器設定温度", "試料抽出時間", "採取日", "試薬費上限", "実験手順書", "抽出室清掃の締切", "遠心待機時間", "出張予算"],
 "MEM-T04": ["トークン更新担当", "ストア申請者", "ステージングホスト", "通信再試行", "承認会議", "月額クラウド上限", "配布ビルド", "認証試験の締切", "利用者説明", "手動同期の上限"],
 "MEM-T05": ["司会担当", "登壇者紹介担当", "避難訓練場所", "弁当の単価", "入場開始", "会場保険の上限", "案内チラシ", "救護班説明の締切", "展示見学", "資料袋の単価"],
 "MEM-T06": ["権利確認担当", "スキャン卓Aの担当", "マスター画像形式", "チェックサムのブロックサイズ", "スキャン締切", "保存費上限", "取込マニフェスト", "スキャン机の点検期限", "作業用SSD", "OCR外注費"],
}


def sentences(text):
    return [s for s in re.split(r"(?<=。)", text) if s.strip()]


def main():
    errors, info = [], []
    recs = [json.loads(l) for l in BANK.read_text(encoding="utf-8").splitlines() if l.strip()]
    ids = [r["id"] for r in recs]
    if ids != IDS:
        errors.append(f"ids/order {ids}")
    total_p, total_q = Counter(), Counter()
    nrefs = 0
    for r in recs:
        t, S = r["id"], r["sessions"]
        if len(S) != 3:
            errors.append(f"{t}: {len(S)} sessions")
        for si, s in enumerate(S):
            if not 8 <= len(s) <= 15:
                errors.append(f"{t}: session {si} has {len(s)} messages")
            for m in s:
                if set(m) != {"speaker", "text"} or not m["text"].strip():
                    errors.append(f"{t}: malformed message {m}")

        def txt(ref, label):
            s, i = ref
            if not (0 <= s < len(S) and 0 <= i < len(S[s])):
                errors.append(f"{t}: {label}: bad ref {ref}")
                return ""
            return S[s][i]["text"]

        pc = Counter(p["kind"] for p in r["plants"])
        total_p.update(pc)
        for j, p in enumerate(r["plants"]):
            k, v, refs, lab = p["kind"], p["values"], p["message_refs"], f"plant {j} ({p['kind']})"
            texts = [txt(x, lab) for x in refs]
            nrefs += len(refs)
            if k in ("contradiction", "reversal"):
                if len(v) != 2 or len(refs) != 2 or v[0] == v[1]:
                    errors.append(f"{t}: {lab}: needs 2 distinct values and 2 refs")
                    continue
                if refs[0] >= refs[1]:
                    errors.append(f"{t}: {lab}: refs not in message order")
                for i in (0, 1):
                    if v[i] not in texts[i]:
                        errors.append(f"{t}: {lab}: value {v[i]!r} not in ref {refs[i]}")
                    if UPDATE_MARK.search(texts[i]) or re.search(r"訂正|改めて|今回の|最新|変更", texts[i]):
                        errors.append(f"{t}: {lab}: ref {refs[i]} carries an update/scope marker")
                if k == "reversal":
                    for i in (0, 1):
                        if v[1 - i] in texts[i]:
                            errors.append(f"{t}: {lab}: ref {refs[i]} also states the opposite direction")
                    a, b = re.match(r"(.+)は(.+)の前提$", v[0]).groups()
                    if v[1] != f"{b}は{a}の前提":
                        errors.append(f"{t}: {lab}: values are not the same pair reversed")
            elif k == "update":
                if len(v) != 2 or len(refs) != 1:
                    errors.append(f"{t}: {lab}: needs old,new and 1 ref")
                elif not (v[0] in texts[0] and v[1] in texts[0] and UPDATE_MARK.search(texts[0])
                          and texts[0].index(v[0]) < texts[0].index(v[1])):
                    errors.append(f"{t}: {lab}: ref lacks 'old から new へ/に + marker'")
            elif k == "list_trap":
                for x, tx in zip(refs, texts):
                    for val in v:
                        if val not in tx:
                            errors.append(f"{t}: {lab}: {val!r} not in {x}")
            elif k == "repeat":
                if len(v) != 1 or len(refs) < 2 or len({x[0] for x in refs}) < 2:
                    errors.append(f"{t}: {lab}: needs 1 value restated across sessions")
                sents = set()
                for x, tx in zip(refs, texts):
                    hit = [s for s in sentences(tx) if v[0] in s]
                    if len(hit) != 1:
                        errors.append(f"{t}: {lab}: value not in exactly one sentence of {x}")
                    sents.update(hit)
                if len(sents) != 1:
                    errors.append(f"{t}: {lab}: restatements not identical: {sorted(sents)}")
                # every occurrence of the repeated sentence in the task must be listed
                occ = [[si, i] for si, s in enumerate(S) for i, m in enumerate(s) if sents and next(iter(sents)) in m["text"]]
                if occ != sorted(refs):
                    errors.append(f"{t}: {lab}: occurrences {occ} != refs {refs}")
            else:
                errors.append(f"{t}: {lab}: unknown kind")

        qc = Counter(q["kind"] for q in r["questions"])
        total_q.update(qc)
        if len(r["questions"]) != 10:
            errors.append(f"{t}: {len(r['questions'])} questions")
        for j, q in enumerate(r["questions"]):
            lab = f"Q{j} ({q['kind']})"
            qt, g, refs = q["q"], q["gold"], q["refs"]
            if not qt.endswith("？"):
                errors.append(f"{t}: {lab}: question does not end in ？")
            if LEAK.search(qt):
                errors.append(f"{t}: {lab}: question announces its kind: {qt}")
            if any(x[0] > 1 for x in refs):
                errors.append(f"{t}: {lab}: refs outside sessions 1-2")
            texts = [txt(x, lab) for x in refs]
            if q["kind"] == "contradiction":
                m = [p for p in r["plants"] if p["kind"] == "contradiction" and p["message_refs"] == refs]
                if len(m) != 1 or g != f"矛盾: {m[0]['values'][0]} と {m[0]['values'][1]}":
                    errors.append(f"{t}: {lab}: gold does not match a contradiction plant on the same refs")
                golds = m[0]["values"] if m else []
            elif q["kind"] == "update":
                m = [p for p in r["plants"] if p["kind"] == "update" and p["message_refs"] == refs]
                if len(m) != 1 or g != m[0]["values"][-1]:
                    errors.append(f"{t}: {lab}: gold is not the latest value of an update plant on the same refs")
                golds = m[0]["values"] if m else []
            else:
                if len(refs) != 1 or g not in texts[0]:
                    errors.append(f"{t}: {lab}: plain gold not in its ref")
                golds = [g]
                for p in r["plants"]:  # the plain fact must not itself be a planted contradicted/updated value
                    if p["kind"] in ("contradiction", "update"):
                        pv = dict(zip(map(tuple, p["message_refs"]), p["values"])) if p["kind"] == "contradiction" else {tuple(p["message_refs"][0]): p["values"][-1]}
                        if any(pv.get(tuple(x)) == g for x in refs):
                            errors.append(f"{t}: {lab}: plain gold is a contradicted/updated value")
            for gv in golds + [g]:
                if gv in qt:
                    errors.append(f"{t}: {lab}: gold value {gv!r} in the question")
            key = KEYS[t][j]
            if not all(key in tx for tx in texts):
                errors.append(f"{t}: {lab}: audit key {key!r} not in its ref(s)")
            for i, m in enumerate(S[2]):
                if key in m["text"]:
                    errors.append(f"{t}: {lab}: session 3 msg [2,{i}] restates {key!r}")

        # lint: same 「…はV」 subject with different values that no contradiction/update plant covers
        planted = {(tuple(x), v) for p in r["plants"] if p["kind"] in ("contradiction", "update") for x, v in zip(p["message_refs"], p["values"])}
        slot = defaultdict(set)
        for si, s in enumerate(S):
            for i, m in enumerate(s):
                for cl in re.split(r"[。、]", m["text"]):
                    cl = re.sub(r"^.*?(では|の一覧では|表の)", "", cl)
                    mm = re.match(r"^(.{2,20}?)は([^はの「」]{1,25}?)(です|に設置|まで|を|$)", cl)
                    if mm and "前提" not in cl and "から" not in cl:
                        slot[mm.group(1)].add((mm.group(2), si, i))
        for subj, vals in slot.items():
            vs = {v for v, _, _ in vals}
            if len(vs) > 1:
                unplanted = [(v, si, i) for v, si, i in vals if ((si, i), v) not in planted]
                if unplanted and len(vs) > 1:
                    info.append(f"{t}: subject {subj!r} has values {sorted(vals)}")
    for k, n in BRIEF_PLANTS.items():
        if total_p[k] < MIN_SHARE * n * 6:
            errors.append(f"plant kind {k}: {total_p[k]} < 80 % of {n*6}")
    for k, n in BRIEF_Q.items():
        if total_q[k] < MIN_SHARE * n * 6:
            errors.append(f"question kind {k}: {total_q[k]} < 80 % of {n*6}")

    print("Bank 5 (audited) mechanical check —", BANK.name)
    print(f"tasks {len(recs)}; plants {dict(total_p)}; questions {dict(total_q)}; plant refs checked {nrefs}")
    print("rules: contradiction/reversal value i in ref i, no update/scope marker; reversal refs state one direction each and")
    print("  the values are the same pair reversed; update = one ref 'old から new + marker'; list_trap values in ref;")
    print("  repeat = one identical sentence in >= 2 sessions, all occurrences listed; questions: refs in sessions 1-2,")
    print("  gold tied to the plant on the same refs (contradiction 「矛盾: X と Y」, update = latest), no gold value and no")
    print("  kind-announcing word in the question, audit subject key in the ref and in no session-3 message; per-kind >= 80 %")
    for x in info:
        print("INFO unplanted same-subject values:", x)
    if errors:
        print(f"FAIL ({len(errors)} errors)")
        for e in errors:
            print("-", e)
        return 1
    print("PASS (0 errors)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
