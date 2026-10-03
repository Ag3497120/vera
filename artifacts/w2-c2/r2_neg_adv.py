from verantyx import conduct_ask as c
must = """寄贈本を範囲に含めなくても大丈夫ですか？
寄贈本は範囲に含めずに進めてよいですか？
寄贈本を入れないで進めても差し支えないですか？
寄贈本はなくても問題ないですか？
寄贈本は範囲に入らないのですか？
寄贈本は範囲に入らないという理解で合っていますか？
寄贈本は範囲に含めない、で合っていますか？
寄贈本を扱わなくてもよいですか？
寄贈本を扱わなくても構いませんか？
寄贈本を扱わなくてもかまわないでしょうか？
寄贈本を省いても大丈夫ですか？
寄贈本は不要ではないですか？
寄贈本は範囲に入らないのでしょうか？
寄贈本を範囲に入れなくてよいですか？
寄贈本を範囲に入れなくていいですか？
寄贈本は対象外ではないですか？
寄贈本を入れずにリリースしてもよいですか？
寄贈本を使わずに済ませてもよいですか？
寄贈本は含まれないと考えてよいですか？
寄贈本を除外せずにおいてもよいですか？
Is the donated books shelf not in scope?
Isn't the donated books shelf in scope?
Do we really not need the donated books shelf?
Do we not need the donated books shelf?
Is it OK if we don't include the donated books shelf?
Is it alright if we do not cover the donated books shelf?
Is it fine if the donated books shelf isn't part of this?
Would it be a problem if we didn't cover the donated books shelf?
Would it be OK if we never cover the donated books shelf?
We don't need the donated books shelf, right?
The donated books shelf isn't in scope, is it?
The donated books shelf is not in scope, correct?
The donated books shelf is out of scope, isn't it?
We won't need the donated books shelf, will we?
Is it okay to not include the donated books shelf?
Can we leave the donated books shelf out? We don't need it, do we?
Can't we skip the donated books shelf?
Shouldn't the donated books shelf be left out?
Is it true that the donated books shelf is not in scope?
Do we agree that the donated books shelf is not needed?
Is there no need for the donated books shelf?
Why isn't the donated books shelf in scope?
Can we do without the donated books shelf?
Do you mind if we don't include the donated books shelf?
Is it ok if the shelf never gets built?
Would it hurt if we didn't build the donated books shelf?
Are we not including the donated books shelf?
Aren't we including the donated books shelf?
Is the donated books shelf no longer needed?
Is the donated books shelf unnecessary?""".splitlines()
mustnot = """寄贈本は、範囲に入りますか？ 手間はかかりませんが。
寄贈本を、必ず範囲に入れなければなりませんか？
寄贈本は、例外なく範囲に入りますか？
寄贈本は範囲に含めますか？
寄贈本の件は、問題ないですか？
Is the donated books shelf in scope, even though we haven't budgeted for it?
Since we won't open before spring, is the donated books shelf in scope?
Is it OK to include the donated books shelf?
Should the donated books shelf be in scope, whether or not we have volunteers?
Which is better, yes or no: is the donated books shelf in scope?""".splitlines()
for grp, xs in (("MUST", must), ("MUSTNOT", mustnot)):
    for x in xs:
        t = c.nz(x)
        ev = c._negation_evidence(t) or c._inversion_evidence(t)
        flag = "" if ev == (grp == "MUST") else "   <== WRONG"
        print(grp, ev, x, flag)
