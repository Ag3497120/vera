"""E6 evidence: does round3._conversation_supply have anything to find after the heldout-overlap rule?

For each of the 8 fixed social sentences that round3._social_frame can produce (read from its code path by the
list below, which is the list the planner gave) this prints, on the rebuilt conversation.db:
  like_hits            rows the SQL LIKE finds (all of them, no limit)
  norm_equal_total     of those, rows whose _norm equals _norm(spoken) (what _conversation_supply accepts)
  window60_norm_equal  the same count inside the first 60 rows, via Corpus.search(..., limit=60) itself
  train_rows_removed_by_heldout_rule   train rows (read from the corpus files with classify_line, i.e. before the rule)
                       whose _norm equals _norm(spoken) and whose body sha is in the conversation heldout set
  train_rows_kept      the same, not in the heldout set (these are in the index)
The search, the limit (60) and _norm are the real ones; nothing here changes them.
Read-only on the corpus and the index.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CORPUS, HERE, IDX, dump  # noqa: E402
from tools import build_p4_corpus_index as bi  # noqa: E402
from verantyx.ability_corpus import Corpus  # noqa: E402
from verantyx.family_library import _norm  # noqa: E402

FORMS = ["こんにちは。", "どういたしまして。", "お話を聞きます。", "また、お話ししましょう。", "気持ちを聞かせてください。",
         "おはようございます。", "こんばんは。", "はじめまして。"]


def scan(job: tuple) -> dict:
    rel, held, targets = job
    held, spec = set(held), bi.SOURCES["conversation"]
    removed = {t: 0 for t in targets}
    kept = {t: 0 for t in targets}
    want = {_norm(t.strip("。！？!? \n")): t for t in targets}
    for _n, raw, nl in bi.read_lines(CORPUS / rel, hashlib.sha256(), {}):
        reason, row = bi.classify_line(raw, nl, "conversation", spec)
        if reason is not None:
            continue
        key = _norm(row["text"])
        if key in want:
            (removed if row["body_sha"] in held else kept)[want[key]] += 1
    return dict(path=rel, removed=removed, kept=kept)


def main() -> int:
    t0 = time.perf_counter()
    held = bi.heldout_bodies(CORPUS, "conversation")[0]
    corpus = Corpus(IDX)
    con = corpus.connection("conversation")
    rows = []
    with ProcessPoolExecutor(max_workers=2) as pool:
        scans = list(pool.map(scan, [(rel, sorted(held), FORMS) for rel in bi.SOURCES["conversation"]["files"]]))
    for form in FORMS:
        spoken = form.strip("。！？!? \n")
        like = con.execute("SELECT r.id, r.text FROM search f JOIN rows r ON r.id=f.rowid WHERE f.text LIKE ?",
                           ("%" + spoken + "%",)).fetchall()
        exact = [r for r in like if _norm(r[1]) == _norm(spoken)]
        window = [r for r in corpus.search(spoken, family="conversation", limit=60) if _norm(r.text) == _norm(spoken)]
        rows.append(dict(
            sentence=form, spoken=spoken, like_hits=len(like), norm_equal_total=len(exact),
            window60_norm_equal=len(window),
            train_rows_removed_by_heldout_rule=sum(s["removed"][form] for s in scans),
            train_rows_kept=sum(s["kept"][form] for s in scans),
            removed_by_file={s["path"]: s["removed"][form] for s in scans},
            kept_by_file={s["path"]: s["kept"][form] for s in scans},
            reaches_supply=bool(window), index_state=corpus.status("conversation")))
    result = dict(index=str(IDX), limit_used=60, rows=rows,
                  any_sentence_reaches_supply=any(r["reaches_supply"] for r in rows),
                  note=("reaches_supply is true when Corpus.search(spoken, 'conversation', limit=60) holds a row whose "
                        "_norm equals _norm(spoken), which is exactly what round3._conversation_supply requires"),
                  elapsed_seconds=round(time.perf_counter() - t0, 3))
    dump(HERE / "c5r2_conversation_supply.json", result)
    for r in rows:
        print(r["sentence"], "like", r["like_hits"], "norm_equal", r["norm_equal_total"], "window60", r["window60_norm_equal"],
              "removed_by_rule", r["train_rows_removed_by_heldout_rule"], "kept", r["train_rows_kept"])
    print("any sentence reaches the supply:", result["any_sentence_reaches_supply"], "| elapsed", result["elapsed_seconds"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
