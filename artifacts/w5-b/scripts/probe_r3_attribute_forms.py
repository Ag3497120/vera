import sys
from verantyx import conduct_ask as ca
A = sys.argv[1]
qs = ["Which language do we use for the report archive?","Which language is best for the report archive?",
 "Please state the language of the report archive.","Language of the report archive?","The language used by the report archive?",
 "What language will the report archive be in?","Report archive language?","Give me the report archive's language.",
 "What would be the ideal language for the report archive?","In which language should the report archive be written?",
 "What's the report archive written in?","Is the report archive in English?","What should we use for the report archive?",
 "The report archive: which language?","What does the report archive use for language?","Is English the language of the report archive?",
 "報告書アーカイブの言語は何ですか？","報告書アーカイブの言語を教えてください。","報告書アーカイブはどの言語ですか？","報告書アーカイブの言語は英語ですか？"]
for q in qs:
    r = ca.answer_question(A + "/frame_a.md", q, ["English", "Japanese"], vocab_llm="fake", map_fake=A + "/map_false_report.json")
    print(repr(q), r["decision"], r["answer"], r["escalate_reason"], r["escalate_detail"], (r.get("trace") or {}).get("resolver_outcomes",{}).get("wider_phrase"))
