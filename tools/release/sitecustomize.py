"""`smoke_wheel.sh` 用。Python 層の file open 試行を別 JSONL に採る。"""
from __future__ import annotations

import builtins
import io
import json
import os
from pathlib import Path
import sqlite3
import threading
from urllib.parse import unquote


_trace_path = os.environ.get("VERA_OPEN_TRACE_FILE")
_guard = threading.Lock()
_trace_fd = None
if _trace_path:
    _trace_fd = os.open(_trace_path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)


def _absolute(path):
    try:
        value = os.fsdecode(os.fspath(path))
    except (TypeError, ValueError):
        return None
    if value.startswith("file:"):
        value = unquote(value[5:].split("?", 1)[0])
    if not value or value == ":memory:":
        return None
    return str(Path(value).expanduser().absolute())


def _record(operation, path, status):
    if _trace_fd is None:
        return
    absolute = _absolute(path)
    if absolute is None or absolute == _trace_path:
        return
    row = json.dumps(
        {"operation": operation, "path": absolute, "status": status},
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8") + b"\n"
    with _guard:
        os.write(_trace_fd, row)


def _reads(mode):
    return isinstance(mode, str) and ("r" in mode or "+" in mode) and not any(
        flag in mode for flag in ("w", "a", "x")
    )


_builtin_open = builtins.open


def _tracked_builtin_open(file, mode="r", *args, **kwargs):
    if not _reads(mode):
        return _builtin_open(file, mode, *args, **kwargs)
    try:
        result = _builtin_open(file, mode, *args, **kwargs)
    except Exception:
        _record("builtins.open", file, "failed")
        raise
    _record("builtins.open", file, "opened")
    return result


builtins.open = _tracked_builtin_open

_io_open = io.open


def _tracked_io_open(file, mode="r", *args, **kwargs):
    if not _reads(mode):
        return _io_open(file, mode, *args, **kwargs)
    try:
        result = _io_open(file, mode, *args, **kwargs)
    except Exception:
        _record("io.open", file, "failed")
        raise
    _record("io.open", file, "opened")
    return result


io.open = _tracked_io_open

_os_open = os.open
_read_access = {os.O_RDONLY, os.O_RDWR}


def _tracked_os_open(file, flags, *args, **kwargs):
    access = flags & os.O_ACCMODE
    if access not in _read_access:
        return _os_open(file, flags, *args, **kwargs)
    try:
        result = _os_open(file, flags, *args, **kwargs)
    except Exception:
        _record("os.open", file, "failed")
        raise
    _record("os.open", file, "opened")
    return result


os.open = _tracked_os_open

_sqlite_connect = sqlite3.connect


def _tracked_sqlite_connect(database, *args, **kwargs):
    try:
        result = _sqlite_connect(database, *args, **kwargs)
    except Exception:
        _record("sqlite3.connect", database, "failed")
        raise
    _record("sqlite3.connect", database, "opened")
    return result


sqlite3.connect = _tracked_sqlite_connect
