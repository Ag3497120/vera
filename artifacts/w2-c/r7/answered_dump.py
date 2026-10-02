# pytest -p answered_dump : records every conduct_ask call (frame content hash, question, options, result, calling test file)
import hashlib, json, os
import verantyx.conduct_ask as ca
_orig = ca._answer_question
def _wrapped(frame_path, question, options=None, **kw):
    r = _orig(frame_path, question, options, **kw)
    try:
        fh = hashlib.sha256(open(frame_path, "rb").read()).hexdigest()[:12]
    except OSError:
        fh = None
    test = os.environ.get("PYTEST_CURRENT_TEST", "").split("::")[0]
    with open(os.environ["CA_LOG"], "a", encoding="utf-8") as f:
        f.write(json.dumps({"frame": os.path.basename(str(frame_path)), "fsha": fh, "test": os.path.basename(test), "q": question,
                            "opts": list(options) if options else None,
                            "decision": r.get("decision"), "index": r.get("answer_option_index"), "answer": r.get("answer"),
                            "kind": r.get("kind"), "reason": r.get("escalate_reason"), "detail": r.get("escalate_detail")},
                           ensure_ascii=False) + "\n")
    return r
ca._answer_question = _wrapped
