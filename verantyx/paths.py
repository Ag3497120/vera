"""コーパスの根の一元化 — 移植の前提修理(2026-08-19)。

20ファイルが `Path.home() / "Projects" / "vera-corpus"` を直書きしていた。
macOS のこの機体でしか成立しないパスで、Windows/Linux 移植の即死点。
環境変数 VERA_CORPUS_ROOT が根を差し替え、無指定なら従来の場所 — 挙動は
この機体では一切変わらない。
"""
from __future__ import annotations

import os
from pathlib import Path


def corpus_root() -> Path:
    """コーパスの根。

    優先順:
      1. `$VERA_CORPUS_ROOT`(明示指定が常に最優先)
      2. **同梱コーパス** — パッケージの隣に `vera-corpus/build/vera.db` が
         あればそれ。配布フォルダを展開しただけで動くようにするため
         (2026-08-19、U-22 提出用)。審査する人に環境変数を設定させない。
      3. 従来の `~/Projects/vera-corpus`
    """
    env = os.environ.get("VERA_CORPUS_ROOT")
    if env:
        return Path(env)
    bundled = Path(__file__).resolve().parent.parent / "vera-corpus"
    if (bundled / "build" / "vera.db").is_file():
        return bundled
    return Path.home() / "Projects" / "vera-corpus"
