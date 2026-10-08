#!/bin/bash
# usage: py.sh <tree> args...   (clean env, the wiring venv, PYTHONPATH=<tree>)
T="$1"; shift
exec env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$T" /Users/motonisihikoudai/vera-wiring/env/bin/python "$@"
