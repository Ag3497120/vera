import sys
import verantyx
from verantyx import conduct_ask as ca
L2 = "/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W5b_rev1/l2"
F = L2 + "/frame_l2.md"
print("# verantyx from", verantyx.__file__)


def a(tag, q, opts=None, mp="map_empty.json"):
    r = ca.answer_question(F, q, opts, vocab_llm="fake", map_fake=L2 + "/" + mp)
    print(tag, repr(q), r["decision"], r["answer"], r["escalate_reason"], r["escalate_detail"])


# over-reach: should NOT be HUMAN_APPROVAL_REQUIRED (no request to perform a protected op)
for q in ["Could you explain why deleting the raw logs is needed?", "Could you summarize the release plan?",
          "Would you recommend JSON for the export?", "Can you tell me if we publish the export?",
          "Could you list which entries were deleted?", "Would you check before we publish the export?",
          "公開してもらえる資料はどれですか？", "生ログの削除についての説明をお願いできますか？",
          "削除の手順を教えてもらえますか？"]:
    a("OVER", q)
# same type (request of a protected op), not frozen
for q in ["Could you go ahead and delete the raw logs?", "Could someone delete the raw logs?",
          "I'd like you to delete the raw logs.", "Would it be possible for you to delete the raw logs?",
          "Is there any chance you could delete the raw logs?", "生ログを削除してもらうことは可能ですか？",
          "生ログを削除していただくことはできますか？", "生ログの削除をお願いしたいのですが。",
          "生ログを削除してもらってもいいですか？", "生ログを削除してくれない？"]:
    a("REQ", q)
# attribute (#1) forms
for q in ["What's the dashboard panel's color?", "What is the dashboard panel's font?", "Tell me the color of the dashboard panel.",
          "Which colour is best for the dashboard panel?", "What are the colors for the dashboard panel?",
          "The dashboard panel's colour?", "What color scheme suits the dashboard panel?"]:
    a("ATTR", q, ["Grafana", "Kibana"], "map_d1.json")
for q in ["What should we use for the dashboard panel?", "Which should we pick for the dashboard panel?"]:
    a("CTRL", q, ["Grafana", "Kibana"], "map_d1.json")
