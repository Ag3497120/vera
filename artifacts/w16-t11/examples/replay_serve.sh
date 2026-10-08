#!/usr/bin/env bash
# W16-t11 (C): vera serve の層 0（文書を LLM に渡し、逐語の引用を照合する）の実例。
# **監査役が dev の木で、sandbox の外で流す**（Ollama とローカルのソケットが要る）。実装役の sandbox では流していない。
# 使い方: bash replay_serve.sh <出力先> [--model qwen3.5:4b] [--port 11500]
#   環境変数 VERA_PLACEMENT_ARG='--placement /path/to/placement' で配置を足せる（W14 の走行は配置あり）。
# 要求の形は benchmarks/public_v1/run.py の run_vera_row と docs/FUSION.md の K652 に合わせた。
set -euo pipefail
OUT="${1:?usage: replay_serve.sh <output-dir> [--model M] [--port P]}"; shift || true
MODEL="qwen3.5:4b"; PORT=11500
while [ $# -gt 0 ]; do case "$1" in --model) MODEL="$2"; shift 2;; --port) PORT="$2"; shift 2;; *) echo "unknown: $1" >&2; exit 2;; esac; done
HERE="$(cd "$(dirname "$0")" && pwd)"
TREE="$(cd "$HERE/../../.." && pwd)"
PY="${VERA_PYTHON:-python3.11}"
export PYTHONPATH="$TREE" PYTHONDONTWRITEBYTECODE=1
mkdir -p "$OUT/rec"; cd "$OUT"
cat > guide.txt <<'EOF'
貸出は一人5冊までで、期間は2週間です。
延滞した場合は、返却するまで新しく借りることはできません。
EOF
vera_argv=("$PY" -P -m verantyx.cli --store "$OUT/store.json" serve --backend ollama --model "$MODEL" --port "$PORT" --document guide.txt)
# shellcheck disable=SC2086
"${vera_argv[@]}" ${VERA_PLACEMENT_ARG:-} > server.log 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null || true' EXIT
for _ in $(seq 1 120); do curl -sf "http://127.0.0.1:$PORT/v1/models" >/dev/null && break; sleep 1; done
printf '%s\n' "vera serve --backend ollama --model $MODEL --document guide.txt --port $PORT" > rec/c_serve.cmd
curl -s "http://127.0.0.1:$PORT/v1/chat/completions" -H 'Content-Type: application/json' -d @- > rec/c_serve.response.json <<EOF
{"model": "$MODEL", "messages": [{"role": "user", "content": "一人で何冊まで借りられますか。"}], "max_tokens": 256,
 "vera": {"request_kind": "factual", "human_present": false}}
EOF
"$PY" - <<'PYEOF' > rec/c_serve.stdout
import json
r = json.load(open("rec/c_serve.response.json", encoding="utf-8"))
print(r["choices"][0]["message"]["content"])
qc = (r.get("vera") or {}).get("quote_check") or {}
print(json.dumps({"verdict": qc.get("verdict"), "quotes": qc.get("quotes"), "outcome": (r.get("vera") or {}).get("outcome")}, ensure_ascii=False, sort_keys=True))
PYEOF
echo 0 > rec/c_serve.exit
cat rec/c_serve.stdout
