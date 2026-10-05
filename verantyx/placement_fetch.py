"""安全に配置 tar を取得し、sha256 を検証して展開する。"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
import tempfile
from typing import Any, Dict
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen


_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_FILES = ("manifest.json", "placement.sqlite")
_CHUNK = 1024 * 1024


class PlacementFetchError(Exception):
    """利用者へ返す型付きの取得失敗。"""

    def __init__(self, verdict: str, detail: str):
        super().__init__(detail)
        self.verdict = verdict
        self.detail = detail


def _validate_url(source: str) -> None:
    if not isinstance(source, str) or not source.strip():
        raise PlacementFetchError("UNKNOWN_BAD_SOURCE", "--from が空です")
    parsed = urlsplit(source)
    if parsed.scheme not in ("file", "http", "https") or parsed.query or parsed.fragment:
        raise PlacementFetchError(
            "UNKNOWN_BAD_SOURCE", "file://、http://、https:// の URL を指定してください"
        )
    if parsed.scheme == "file" and parsed.netloc not in ("", "localhost"):
        raise PlacementFetchError(
            "UNKNOWN_BAD_SOURCE", "file:// URL の host は空か localhost にしてください"
        )


def _read_digest(source: str) -> str:
    try:
        with urlopen(source + ".sha256", timeout=30) as response:
            raw = response.read(4096).decode("ascii").strip()
    except (OSError, URLError, UnicodeDecodeError) as exc:
        raise PlacementFetchError(
            "UNKNOWN_SHA256_UNAVAILABLE", "SHA-256 sidecar を読めません"
        ) from exc
    parts = raw.split()
    if len(parts) not in (1, 2) or not _SHA256.fullmatch(parts[0]):
        raise PlacementFetchError(
            "UNKNOWN_SHA256_INVALID", "SHA-256 sidecar の形式が不正です"
        )
    if len(parts) == 2 and parts[1].lstrip("*") in ("", ".", ".."):
        raise PlacementFetchError(
            "UNKNOWN_SHA256_INVALID", "SHA-256 sidecar の名前欄が不正です"
        )
    return parts[0].lower()


def _download(source: str, path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with urlopen(source, timeout=60) as response, path.open("xb") as output:
            while True:
                chunk = response.read(_CHUNK)
                if not chunk:
                    break
                digest.update(chunk)
                output.write(chunk)
    except (OSError, URLError) as exc:
        raise PlacementFetchError(
            "UNKNOWN_SOURCE_UNAVAILABLE", "配置 tar を読めません"
        ) from exc
    return digest.hexdigest()


def _validated_members(archive: tarfile.TarFile) -> Dict[str, tarfile.TarInfo]:
    members = archive.getmembers()
    if len(members) != len(_FILES):
        raise PlacementFetchError(
            "UNKNOWN_UNSAFE_ARCHIVE", "tar は manifest.json と placement.sqlite のみを含めてください"
        )
    by_name: Dict[str, tarfile.TarInfo] = {}
    for member in members:
        if member.name not in _FILES or member.name in by_name or not member.isfile():
            raise PlacementFetchError(
                "UNKNOWN_UNSAFE_ARCHIVE", "tar の path または entry 型が許可されていません"
            )
        by_name[member.name] = member
    if set(by_name) != set(_FILES):
        raise PlacementFetchError(
            "UNKNOWN_UNSAFE_ARCHIVE", "tar に必要な配置ファイルがありません"
        )
    return by_name


def _extract(archive_path: Path, staging: Path) -> None:
    try:
        with tarfile.open(archive_path, mode="r:") as archive:
            members = _validated_members(archive)
            for name in _FILES:
                source = archive.extractfile(members[name])
                if source is None:
                    raise PlacementFetchError(
                        "UNKNOWN_UNSAFE_ARCHIVE", "tar entry を読み出せません"
                    )
                target = staging / name
                with source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, length=_CHUNK)
    except PlacementFetchError:
        raise
    except (EOFError, OSError, tarfile.TarError) as exc:
        raise PlacementFetchError(
            "UNKNOWN_UNSAFE_ARCHIVE", "配置 tar を安全に展開できません"
        ) from exc
    try:
        with (staging / "manifest.json").open("r", encoding="utf-8") as stream:
            manifest: Any = json.load(stream)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PlacementFetchError(
            "UNKNOWN_BAD_MANIFEST", "manifest.json が有効な UTF-8 JSON ではありません"
        ) from exc
    if not isinstance(manifest, dict):
        raise PlacementFetchError(
            "UNKNOWN_BAD_MANIFEST", "manifest.json の最上位は object である必要があります"
        )
    if (staging / "placement.sqlite").stat().st_size == 0:
        raise PlacementFetchError(
            "UNKNOWN_EMPTY_DATABASE", "placement.sqlite が空です"
        )


def fetch(source: str, destination: str) -> Dict[str, str]:
    """取得元 tar と `.sha256` を照合し、新規 destination に展開する。"""
    _validate_url(source)
    expected = _read_digest(source)
    dest = Path(destination).expanduser().absolute()
    if dest.exists() or dest.is_symlink():
        raise PlacementFetchError(
            "UNKNOWN_DEST_EXISTS", "展開先は存在しない directory を指定してください"
        )
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PlacementFetchError(
            "UNKNOWN_DEST_UNWRITABLE", "展開先の親 directory を作成できません"
        ) from exc
    if not dest.parent.is_dir():
        raise PlacementFetchError(
            "UNKNOWN_DEST_UNWRITABLE", "展開先の親 path は directory ではありません"
        )

    with tempfile.TemporaryDirectory(prefix=".vera-placement-", dir=str(dest.parent)) as temp:
        temp_root = Path(temp)
        archive_path = temp_root / "placement.tar"
        got = _download(source, archive_path)
        if not hmac.compare_digest(expected, got):
            raise PlacementFetchError(
                "UNKNOWN_SHA256_MISMATCH", "配置 tar の SHA-256 が sidecar と一致しません"
            )
        staging = temp_root / "placement"
        staging.mkdir()
        _extract(archive_path, staging)
        try:
            os.rename(staging, dest)
        except OSError as exc:
            raise PlacementFetchError(
                "UNKNOWN_DEST_UNWRITABLE", "検証済み配置を展開先へ配置できません"
            ) from exc

    resolved = str(dest.resolve())
    return {
        "verdict": "PLACEMENT_FETCHED",
        "VERA_PLACEMENT": resolved,
        "archive_sha256": got,
    }


def cli(args: Any) -> int:
    """CLI entry: JSON で成功または型付き棄権を返す。"""
    try:
        result = fetch(args.source, args.dest)
        exit_code = 0
    except PlacementFetchError as exc:
        result = {"kind": "unknown", "verdict": exc.verdict, "reason": exc.detail}
        exit_code = 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return exit_code


def dispatch(args: Any) -> int:
    """既存 `vera placement STORE` と追加 `vera placement fetch` を振り分ける。"""
    if getattr(args, "store", None) == "fetch":
        if not getattr(args, "source", None) or not getattr(args, "dest", None):
            result = {
                "kind": "unknown",
                "verdict": "UNKNOWN_BAD_ARGUMENTS",
                "reason": "placement fetch には --from と --dest が必要です",
            }
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 2
        return cli(args)
    if getattr(args, "source", None) is not None or getattr(args, "dest", None) is not None:
        result = {
            "kind": "unknown",
            "verdict": "UNKNOWN_BAD_ARGUMENTS",
            "reason": "--from と --dest は `vera placement fetch` で使います",
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2
    from .cli import cmd_placement
    return cmd_placement(args)
