#!/bin/bash
# W0-1 measurement aid (not part of the product): run the real node unchanged, but drop exactly one
# stderr line, the node v22 warning "Warning: disabling flag --expose_wasm due to conflicting flags".
# Any other stderr line, the exit status and stdout pass through untouched.
exec /usr/local/bin/node "$@" 2> >(grep -v -x -F 'Warning: disabling flag --expose_wasm due to conflicting flags' >&2)
