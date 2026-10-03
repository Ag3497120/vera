import sys
from verantyx import conduct_ask as ca
A = sys.argv[1]
for q in ["What's the report archive's language?", "What is the report archive's language?",
          "Tell me the language of the report archive.", "What language suits the report archive?",
          "What language fits the report archive best?", "The report archive's language?",
          "Name the language of the report archive.", "What language is used for the report archive?"]:
    r = ca.answer_question(A + "/frame_a.md", q, ["English", "Japanese"], vocab_llm="fake", map_fake=A + "/map_false_report.json")
    print(repr(q), r["decision"], r["answer"], r["escalate_reason"], r["escalate_detail"])
for q in ["Could someone delete an archive?", "Would it be possible to delete an archive?",
          "Would it be possible for you to delete an archive?", "アーカイブを削除してもらうことはできますか？",
          "アーカイブを削除してもらってもいいですか？", "アーカイブの削除をお願いしたいのですが。"]:
    r = ca.answer_question(A + "/frame_a.md", q, None, vocab_llm="fake", map_fake=A + "/map_empty.json")
    print(repr(q), r["decision"], r["answer"], r["escalate_reason"], r["escalate_detail"])
