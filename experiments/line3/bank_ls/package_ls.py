#!/usr/bin/env python3
"""Package the long-story banks from the codex author directories into the three splits of bank_ls/.

  python3 package_ls.py            # writes dev/, heldout_1/, heldout_2/ (stories.jsonl + MANIFEST.json)

Input: vera-impl/bank7-author/ls/<key>/out/story.jsonl (one JSON line per story, written by codex gpt-6-luna from
vera-impl/bank2-author/PROMPT_LS_<key>.md).  The only change made to an author's story is mechanical and recorded in the manifest: the
`refs` of an `absent` question is set to [] (the author sometimes repeated `subject_refs` there, or left the key out), so that `refs`
always means 'the messages that state the gold'.  Nothing else is edited.  Prints counts only.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUTH = Path("/Users/motonisihikoudai/Projects/vera-impl/bank7-author/ls")
SPLITS = {
    "dev": ["dev1", "dev2"],
    "heldout_1": ["h1_1", "h1_2", "h1_3", "h1_4", "h1_5", "h1_6"],
    "heldout_2": ["h2_1", "h2_2", "h2_3", "h2_4", "h2_5", "h2_6"],
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    for split, keys in SPLITS.items():
        out = HERE / split
        out.mkdir(exist_ok=True)
        lines, man = [], []
        for k in keys:
            src = AUTH / k / "out" / "story.jsonl"
            raw = src.read_bytes()
            r = json.loads(raw.decode("utf-8"))
            fixed = 0
            for q in r["questions"]:
                if q["kind"] == "absent" and q.get("refs") != []:
                    q["refs"] = []
                    fixed += 1
            lines.append(json.dumps(r, ensure_ascii=False, separators=(",", ":")))
            man.append({"id": r["id"], "author_dir": f"bank7-author/ls/{k}", "author_story_sha256": sha(raw), "absent_refs_normalised": fixed,
                        "prompt": f"bank2-author/PROMPT_LS_{k}.md",
                        "sessions": len(r["sessions"]), "messages": sum(len(s) for s in r["sessions"]),
                        "sentences": sum(len([x for x in m["text"].split("。") if x.strip()]) for s in r["sessions"] for m in s),
                        "questions": len(r["questions"])})
        data = ("\n".join(lines) + "\n").encode("utf-8")
        (out / "stories.jsonl").write_bytes(data)
        (out / "MANIFEST.json").write_text(json.dumps({"split": split, "stories": man, "stories_jsonl_sha256": sha(data)}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(split, len(keys), "stories", sha(data)[:16])


if __name__ == "__main__":
    sys.exit(main())
