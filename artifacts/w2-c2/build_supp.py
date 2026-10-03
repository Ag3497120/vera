import json
out = []
def add(trap, grp, lang, frame, q, truth, note, rule=None, ev=None):
    n = sum(1 for x in out if x["trap"] == trap and x["group"] == grp) + 1
    d = {"id": f"supp-{trap.lower()}-{grp}-{n:02d}", "lang": lang, "frame_id": frame, "trap": trap, "group": grp,
         "question": q, "options": None, "truth": truth, "note": note}
    if rule: d["expect_rule"] = {"reason": rule[0], "detail": rule[1]}
    if ev: d["evidence"] = ev
    out.append(d)
Y = lambda rec: {"records": rec, "decision": "answer", "answer_option_index": 0, "answer": "Yes"}
N = lambda rec: {"records": rec, "decision": "answer", "answer_option_index": 1, "answer": "No"}
HY = lambda rec: {"records": rec, "decision": "answer", "answer_option_index": 0, "answer": "はい"}
HN = lambda rec: {"records": rec, "decision": "answer", "answer_option_index": 1, "answer": "いいえ"}
E = {"records": [], "decision": "escalate", "answer_option_index": None, "answer": None}
s1, s2 = "s01_toylibrary", "s02_bosai"
# NO_ALLOWLIST route: a scope question whose path-looking word (e.g. "e.g.", a file name) is not where anything is written
NA = "path-looking word is not a write target; the scope record decides"
for q, t in [("May we include the borrower sign-up desk, e.g. desk.html, in this project?", Y(["D3"])),
             ("Is it ok to take on the borrower sign-up desk, such as signup.php?", Y(["D3"])),
             ("Are we allowed to cover the borrower sign-up desk, e.g. in desk.csv?", Y(["D3"])),
             ("May we include the borrower sign-up desk, i.e. the desk in front.jpg?", Y(["D3"])),
             ("May we include repair workshop booking, e.g. booking.html, in this project?", N(["D2"])),
             ("Are we allowed to add the parent newsletter, e.g. news.pdf, to the scope?", N(["D7"])),
             ("Is it ok to include repair workshop booking, e.g. through app.js?", N(["D2"])),
             ("Can we include repair workshop booking, as in plan.md, in the project?", N(["D2"]))]:
    add("NO_ALLOWLIST", "route", "en", s1, q, t, NA)
for q, t in [("炊き出しの手配は、たとえば meal.xlsx のような表も含めて、範囲に入れてよいですか？", HN(["D2"])),
             ("当日の安否の確認は、例えば check.html の画面を含めて、範囲に入れてもよいですか？", HY(["D3"])),
             ("炊き出しの手配は、つまり menu.csv の取りまとめですが、今回の範囲に入れてよいですか？", HN(["D2"])),
             ("当日の安否の確認は、board.php を使うものとして、範囲に入れてよいですか？", HY(["D3"])),
             ("炊き出しの手配を、plan.md の項目として扱うことは、範囲に含めてよいですか？", HN(["D2"])),
             ("当日の安否の確認は、map.pdf の番号に沿って範囲に入れてもよいですか？", HY(["D3"])),
             ("当日の安否の確認は、sheet.xlsx の欄を使うとして、範囲に含めてよいですか？", HY(["D3"]))]:
    add("NO_ALLOWLIST", "route", "ja", s2, q, t, NA)
# NEGATED route: a negation word in a subordinate clause; the asked predicate is "in scope?"
NG = "negation word only in a subordinate clause (concession / reason / condition); the asked predicate is not negated"
for q, t in [("Even though the volunteers have not met yet, is the borrower sign-up desk in scope?", Y(["D3"])),
             ("Since we won't open before spring, is repair workshop booking in scope?", N(["D2"])),
             ("Is the borrower sign-up desk in scope, even though nobody has set it up and we can't test it yet?", Y(["D3"])),
             ("Is repair workshop booking in scope, given that we haven't asked anyone about it?", N(["D2"])),
             ("Although no budget has been agreed, is the parent newsletter in scope?", N(["D7"]))]:
    add("NEGATED", "route", "en", s1, q, t, NG)
for q, t in [("炊き出しの手配は、まだ担当が決まっていませんが、今回の範囲に入りますか？", HN(["D2"])),
             ("当日の安否の確認は、まだ手順が決まっていませんが、今回の範囲に入りますか？", HY(["D3"])),
             ("当日の安否の確認は、連絡がつかない人が出ても、今回の範囲に入りますか？", HY(["D3"])),
             ("炊き出しの手配は、予算がないのですが、今回の範囲に入りますか？", HN(["D2"])),
             ("炊き出しの手配は、まだ誰にも頼んでいないのですが、今回の範囲に含まれますか？", HN(["D2"]))]:
    add("NEGATED", "route", "ja", s2, q, t, NG)
# raise: the question really is a negated question / a write question (these forms were missed by the round-1 detectors)
NEGR = ("QUESTION_UNREADABLE", "NEGATED_QUESTION")
PR = ("FRAME_SILENT", "NO_ALLOWLIST")
for q, f in [("炊き出しの手配は、今回の範囲に含めなくても大丈夫ですか？", "ja:neg-te-mo + daijoubu"),
             ("当日の安否の確認を、役割表に入れずに進めてよいですか？", "ja:zu-ni + may"),
             ("炊き出しの手配は、今回は扱わなくても差し支えないですか？", "ja:naku-te-mo + sashitsukae"),
             ("当日の安否の確認は、入れないで進めても OK ですか？", "ja:naide + verb-te-mo + OK"),
             ("名簿の持ち出しは、しなくても問題ないですか？", "ja:naku-te-mo + mondai")]:
    add("NEGATED", "raise", "ja", s2, q, E, "a negated action whose permission is asked", NEGR, f)
for q, f in [("Is it OK if we don't include the borrower sign-up desk?", "en:permission frame + if-clause"),
             ("Would it be a problem if we didn't cover repair workshop booking?", "en:evaluation frame + if-clause"),
             ("Is it fine if the parent newsletter isn't part of this project?", "en:permission frame + if-clause"),
             ("We don't need the borrower sign-up desk, right?", "en:tag question"),
             ("Repair workshop booking isn't in scope, is it?", "en:tag question"),
             ("The parent newsletter is not in scope, correct?", "en:tag question")]:
    add("NEGATED", "raise", "en", s1, q, E, "a negated statement or action whose permission / truth is asked", NEGR, f)
for q, f in [("data/toys.csv に追記してもよいですか？", "ja:path + tsuiki"), ("out/report.txt に保存してもよいですか？", "ja:path + hozon"),
             ("config/cards.yaml を上書きしてもよいですか？", "ja:path + uwagaki"), ("役割表を cards/out.pdf に出力してもよいですか？", "ja:path + shutsuryoku"),
             ("notes/log.txt へ書き出してもよいですか？", "ja:path + kakidashi")]:
    add("NO_ALLOWLIST", "raise", "ja", s2, q, E, "a path that is asked as a write target (no allowlist declared)", PR, f)
for q, f in [("May we modify the file src/loans.py?", "en:verb + noun phrase + path"),
             ("Can we save the loan report to out/report.txt?", "en:save + noun phrase + to + path"),
             ("Is it ok to append the new toys to data/toys.csv?", "en:append + noun phrase + to + path"),
             ("May we overwrite config/cards.yaml?", "en:overwrite + path"),
             ("Can we export the card list into exports/cards.csv?", "en:export + noun phrase + into + path")]:
    add("NO_ALLOWLIST", "raise", "en", s1, q, E, "a path that is asked as a write target (no allowlist declared)", PR, f)
import sys
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    for d in out:
        fh.write(json.dumps(d, ensure_ascii=False) + "\n")
import collections
print(collections.Counter((d["trap"], d["group"], d["lang"]) for d in out))
