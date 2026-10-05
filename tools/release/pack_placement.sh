#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    printf '使い方: %s <placement_dir> <out>\n' "$0" >&2
    exit 2
fi

placement_dir=$1
out=$2
if [[ ! -d "$placement_dir" ]]; then
    printf '配置 directory がありません\n' >&2
    exit 2
fi
placement_dir=$(cd "$placement_dir" && pwd -P)
for name in manifest.json placement.sqlite; do
    item="$placement_dir/$name"
    if [[ ! -f "$item" || -L "$item" ]]; then
        printf '通常ファイルが必要です: %s\n' "$name" >&2
        exit 2
    fi
done
if [[ -e "$placement_dir/placement.sqlite-wal" || -e "$placement_dir/placement.sqlite-shm" ]]; then
    printf 'SQLite の WAL/SHM sidecar が残っています。checkpoint 後の配置を指定してください\n' >&2
    exit 2
fi

out_parent=$(dirname "$out")
out_name=$(basename "$out")
mkdir -p "$out_parent"
out_parent=$(cd "$out_parent" && pwd -P)
out="$out_parent/$out_name"
sha_file="$out.sha256"
if [[ "$out" == "$placement_dir"/* ]]; then
    printf '出力先は配置 directory の外にしてください\n' >&2
    exit 2
fi
if [[ -e "$out" || -L "$out" || -e "$sha_file" || -L "$sha_file" ]]; then
    printf 'tar または SHA-256 sidecar が既にあります。別の出力先を指定してください\n' >&2
    exit 2
fi

python=${VERA_PYTHON:-python3}
"$python" - "$placement_dir/manifest.json" "$placement_dir/placement.sqlite" <<'PY'
import json
import pathlib
import re
import sqlite3
import sys

manifest_path, database_path = map(pathlib.Path, sys.argv[1:])
with manifest_path.open("r", encoding="utf-8") as stream:
    value = json.load(stream)
if not isinstance(value, dict):
    raise SystemExit("manifest.json の最上位は object である必要があります")
tables = value.get("outputs", {}).get("tables") if isinstance(value.get("outputs"), dict) else None
if not isinstance(tables, dict) or not tables:
    raise SystemExit("manifest.json の outputs.tables が空か不正です")
connection = sqlite3.connect(database_path.resolve().as_uri() + "?mode=ro", uri=True)
try:
    present = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for name, expected in tables.items():
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise SystemExit("manifest.json に不正な table 名があります")
        if type(expected) is not int or expected < 0 or name not in present:
            raise SystemExit("manifest.json の table count が不正です: " + name)
        actual = connection.execute('SELECT COUNT(*) FROM "' + name + '"').fetchone()[0]
        if actual != expected:
            raise SystemExit("manifest.json と SQLite の row count が一致しません: " + name)
finally:
    connection.close()
PY

# macOS bsdtar may add AppleDouble `._*` metadata even though these files are
# not part of the placement. Disable that behavior so the archive stays exact.
COPYFILE_DISABLE=1 tar -cf "$out" -C "$placement_dir" manifest.json placement.sqlite
digest=$(shasum -a 256 "$out" | awk '{print $1}')
printf '%s  %s\n' "$digest" "$out_name" > "$sha_file"
printf 'archive=%s\nsha256_file=%s\nsha256=%s\n' "$out_name" "$(basename "$sha_file")" "$digest"
