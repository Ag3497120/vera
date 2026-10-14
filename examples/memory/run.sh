#!/bin/sh
# One session of three facts (one fact per line, one sentence each), then two questions.  Needs a model: set ANTHROPIC_API_KEY (default backend), or add
#   --backend openai --model <id> --base-url http://127.0.0.1:11434/v1        (Ollama), see ../../README.md
# The store is created if missing; the same folder is the same memory next time.
set -e
STORE="${1:-./memory-store}"
vera mem --store "$STORE" \
  --say "広報の担当は山本" --say "会議の場所は東京" --say "広報の担当は田中" \
  --ask "広報の担当は何ですか" --ask "会議の場所は何ですか" || true     # exit status 1 = at least one question came back 「分かりません」, which is expected here
vera verify "$STORE"
