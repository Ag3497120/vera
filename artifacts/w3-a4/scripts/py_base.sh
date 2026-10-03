#!/bin/sh
exec env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 LANG=en_US.UTF-8 \
  PYTHONPATH=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W3-a4-impl/base /Users/motonisihikoudai/vera-wiring/env/bin/python "$@"
