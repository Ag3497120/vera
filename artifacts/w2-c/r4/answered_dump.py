# pytest -p answered_dump で読み込む。conduct_ask の呼び出しを 1 行ずつ記録するだけ
import json, os
import verantyx.conduct_ask as ca
_orig = ca._answer_question
def _wrapped(frame_path, question, options=None, **kw):
    r = _orig(frame_path, question, options, **kw)
    with open(os.environ["CA_LOG"], "a", encoding="utf-8") as f:
        f.write(json.dumps({"frame": os.path.basename(str(frame_path)), "q": question, "opts": list(options) if options else None,
                            "decision": r.get("decision"), "index": r.get("answer_option_index"), "answer": r.get("answer"),
                            "kind": r.get("kind"), "reason": r.get("escalate_reason"), "detail": r.get("escalate_detail")},
                           ensure_ascii=False) + "\n")
    return r
ca._answer_question = _wrapped
