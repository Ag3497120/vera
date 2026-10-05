#!/usr/bin/env bash
# W16-t11: README の 3 つの実例のうち (A) attest と (B) 記録の再生。使い方: bash replay.sh <出力先（空か未作成）>
# README では `vera ...` と書く。ここでは同じ引数で `<python> -P -m verantyx.cli ...` を流し、.cmd には README の書き方を残す。
set -euo pipefail
OUT="${1:?usage: replay.sh <output-dir>}"
HERE="$(cd "$(dirname "$0")" && pwd)"
TREE="$(cd "$HERE/../../.." && pwd)"
PY="${VERA_PYTHON:-/Users/motonisihikoudai/vera-wiring/env/bin/python}"
export PYTHONPATH="$TREE" PYTHONDONTWRITEBYTECODE=1
mkdir -p "$OUT/demo/tests" "$OUT/rec"
cd "$OUT"

# ---- 例の入力（ヒアドキュメント。test_*.py を artifacts に置かないため、ここで作る）
cat > demo/calc.py <<'EOF'
def add(a, b):
    return a + b


def sub(a, b):
    return a - b
EOF
cat > demo/tests/test_calc.py <<'EOF'
from calc import add, sub


def test_add():
    assert add(2, 3) == 5


def test_sub():
    assert sub(5, 3) == 2
EOF
cat > demo/tests/test_extra.py <<'EOF'
from calc import add


def test_add_zero():
    assert add(0, 0) == 0
EOF
# calc.py の中身は固定。sha256 は固定の値を書き、下で一致を確かめる（ここで求めた値を報告に書かない）
CALC_SHA=af626eb7a9c3d865bc4d7d84f96982d7349f4931c403286d23603d85e6552442
test "$(shasum -a 256 demo/calc.py | cut -d' ' -f1)" = "$CALC_SHA" || { echo "calc.py の sha が固定値と違う" >&2; exit 3; }
cat > report.md <<EOF
# 作業報告

足し算と引き算を実装し、テストを足しました。

完了:
- 変更: calc.py（sha256 ${CALC_SHA}）。
- 追加したテスト: tests/test_calc.py の 2 件が通った。
- 追加したテスト: tests/test_extra.py の 4 件が通った。
- 受入 A-1: \`make deploy\` を実行し、終了コード 0。
EOF

vera() { "$PY" -P -m verantyx.cli "$@"; }
# rec <name> <README に書く形> -- <引数...>
rec() {
  local name="$1" shown="$2"; shift 3
  printf '%s\n' "$shown" > "rec/$name.cmd"
  set +e
  vera "$@" > "rec/$name.stdout" 2> "rec/$name.stderr"
  echo $? > "rec/$name.exit"
  set -e
  echo "$name exit=$(cat rec/$name.exit) stdout_bytes=$(wc -c < rec/$name.stdout)"
}

# (A) attest
rec a_attest 'vera attest report.md --tree demo --rerun' -- attest report.md --tree demo --rerun

# (B) 記録
rec b_run 'vera run --ledger-dir .vera/ledger -- python3 -c "print(2+3)"' -- run --ledger-dir .vera/ledger -- python3 -c "print(2+3)"
rec b_verify 'vera events --ledger-dir .vera/ledger verify' -- events --ledger-dir .vera/ledger verify
# 台帳の 2 行目の終了コードを書き換えたコピーを検証する（sha は直さない）
mkdir -p .vera/ledger_tampered
cp .vera/ledger/events.jsonl .vera/ledger/HEAD .vera/ledger_tampered/
sed 's/"exit_code":0/"exit_code":7/' .vera/ledger/events.jsonl > .vera/ledger_tampered/events.jsonl
rec b_verify_tampered 'vera events --ledger-dir .vera/ledger_tampered verify' -- events --ledger-dir .vera/ledger_tampered verify
rec b_hooks 'vera hooks print --claude-code --vera-cmd vera' -- hooks print --claude-code --vera-cmd vera
