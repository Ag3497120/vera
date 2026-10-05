#!/usr/bin/env bash
set -euo pipefail

mode=release
if [[ ${1:-} == --baseline ]]; then
    mode=baseline
    shift
fi
if [[ $# -gt 1 ]]; then
    printf '使い方: %s [--baseline] [output_dir]\n' "$0" >&2
    exit 2
fi

root=$(cd "$(dirname "$0")/../.." && pwd -P)
python=${VERA_PYTHON:-python3}
scratch_root=${VERA_SMOKE_SCRATCH_ROOT:-${TMPDIR:-/tmp}}
unset PYTHONPATH VERA_OPEN_TRACE_FILE
mkdir -p "$scratch_root"
stamp=$(date '+%Y%m%dT%H%M%S')-$$
out=${1:-"$root/artifacts/w16-t10/$mode-$stamp"}
if [[ -e "$out" || -L "$out" ]]; then
    printf '出力先が既にあります: %s\n' "$out" >&2
    exit 2
fi
mkdir -p "$out/wheel"
scratch=$(mktemp -d "$scratch_root/w16t10-smoke.XXXXXX")
mkdir -p "$scratch/source" "$scratch/empty" "$scratch/trace" "$scratch/home"

if [[ "$mode" == baseline ]]; then
    git -C "$root" archive HEAD | tar -xf - -C "$scratch/source"
else
    cp "$root/pyproject.toml" "$root/README.md" "$scratch/source/"
    cp -R "$root/verantyx" "$scratch/source/"
fi

run_logged() {
    label=$1
    shift
    printf '%s\n' "$*" > "$scratch/$label.command"
    if (cd "$scratch/empty" && "$@") > "$scratch/$label.stdout" 2> "$scratch/$label.stderr"; then
        status=0
    else
        status=$?
    fi
    for suffix in command stdout stderr; do
        env PYTHONPATH= VERA_OPEN_TRACE_FILE= "$python" "$root/tools/release/redact_smoke_output.py" \
            "$scratch/$label.$suffix" "$out/$label.$suffix" "$scratch" "$root"
    done
    printf '%s\n' "$status" > "$out/$label.exit"
    printf '%s %s exit=%s\n' "$mode" "$label" "$status"
    return "$status"
}

if ! run_logged build "$python" -m pip wheel --no-index --no-deps --no-build-isolation \
    --wheel-dir "$out/wheel" "$scratch/source"; then
    printf 'wheel build が失敗しました。ログ: %s/build.stderr\n' "$out" >&2
    exit 1
fi
shopt -s nullglob
wheels=("$out"/wheel/*.whl)
if [[ ${#wheels[@]} -ne 1 ]]; then
    printf 'wheel は 1 個必要です。実測数: %s\n' "${#wheels[@]}" >&2
    exit 1
fi
wheel=${wheels[0]}
"$python" "$root/tools/release/list_wheel_members.py" "$wheel" "$out/wheel-members.txt"

venv="$scratch/venv"
if ! run_logged venv "$python" -m venv "$venv"; then
    printf 'venv 作成に失敗しました。\n' >&2
    exit 1
fi
site_packages=$("$venv/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
if ! run_logged smoke-deps "$python" "$root/tools/release/link_smoke_deps.py" "$site_packages"; then
    printf 'smoke の日本語 runtime dependency を用意できません。\n' >&2
    exit 1
fi
if ! run_logged install "$venv/bin/python" -m pip install --no-index --no-deps "$wheel"; then
    printf 'wheel install が失敗しました。\n' >&2
    exit 1
fi

cp "$root/tools/release/sitecustomize.py" "$scratch/trace/sitecustomize.py"
export HOME="$scratch/home"
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
export PIP_NO_INDEX=1
export PYTHONPATH="$scratch/trace"
export VERA_OPEN_TRACE_FILE="$scratch/open-trace.jsonl"
unset VERA_PLACEMENT VERA_PLACEMENT_LAYER VERA_READ_MODE

if ! run_logged wheel-import "$venv/bin/python" -c \
    'import pathlib, sysconfig, verantyx; p=pathlib.Path(verantyx.__file__).resolve(); root=pathlib.Path(sysconfig.get_paths()["purelib"]).resolve(); assert p.is_relative_to(root), p; pathlib.Path(__import__("sys").argv[1]).write_text(str(p.parent), encoding="utf-8"); print("origin=installed-wheel")' \
    "$scratch/package-root.txt"; then
    printf '新規 venv が wheel 由来の verantyx を読み込めません。\n' >&2
    exit 1
fi

shasum -a 256 "$root/tests/test_semantic_reader.py" | awk '{print $1}' > "$out/smoke-document-source.sha256"
if ! run_logged document-fixture "$python" "$root/tools/release/load_smoke_document.py" \
    "$root/tests/test_semantic_reader.py" "$scratch/document.txt"; then
    printf '既存 smoke document fixture を読めません。\n' >&2
    exit 1
fi
vera="$venv/bin/vera"
run_logged help "$vera" --help || :
run_logged read "$vera" --store "$scratch/read-store.json" read --text 'ハルはミナに本を渡した。' || :
run_logged ask "$vera" --store "$scratch/ask-store.json" ask '誰が肥料を運んだ？' \
    --mode round5 --document "$scratch/document.txt" || :
run_logged serve env PYTHONPATH= VERA_OPEN_TRACE_FILE= "$python" \
    "$root/tools/release/probe_serve.py" "$vera" "$scratch/serve-store.json" \
    "$scratch/empty" "$out/serve.log" "$out/serve-response.json" \
    "$scratch/trace" "$scratch/open-trace.jsonl" || :

env PYTHONPATH= VERA_OPEN_TRACE_FILE= "$python" "$root/tools/release/check_smoke.py" \
    "$mode" "$out" > "$out/p1-check.stdout" 2> "$out/p1-check.stderr" || :
package_root=$(cat "$scratch/package-root.txt")
env PYTHONPATH= VERA_OPEN_TRACE_FILE= "$python" "$root/tools/release/collect_open_paths.py" "$scratch/open-trace.jsonl" \
    "$package_root" "$scratch" "$root" "$out" > "$out/p2-check.stdout" 2> "$out/p2-check.stderr" || :

if [[ "$mode" == release ]]; then
    if ! grep -q '"all_smoke_checks_pass": true' "$out/p1-verification.json"; then
        printf 'P1 smoke に失敗しました。確認先: %s\n' "$out" >&2
        exit 1
    fi
    if ! grep -q '"missing_opened_wheel_member_count": 0' "$out/p2-verification.json" \
       || ! grep -q '"constructions_present": true' "$out/p2-verification.json" \
       || ! grep -q '"data_present": true' "$out/p2-verification.json"; then
        printf 'P2 wheel 内容または open path の照合に失敗しました。確認先: %s\n' "$out" >&2
        exit 1
    fi
fi
printf '結果ディレクトリ: %s\n' "$out"
