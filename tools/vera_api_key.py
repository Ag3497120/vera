#!/usr/bin/env python3
"""vera_api_key.py — put the Anthropic API key where the loom's L2 driver can find it, without ever
printing it or writing it into the repository.

    python tools/vera_api_key.py set      prompt for the key (hidden input), store it in the macOS Keychain,
                                          install the `anthropic` SDK into this interpreter if missing,
                                          and make one minimal API call to confirm the key works
    python tools/vera_api_key.py check    say whether a key is reachable (env or Keychain) and whether it works
    python tools/vera_api_key.py clear    remove the Keychain entry

Resolution order used by the harness (verantyx/loom/keyring.py): the environment variable ANTHROPIC_API_KEY,
then the Keychain item service="vera-loom" account="anthropic".  The key value is never echoed, logged or
stored in the ledger; only "a key was present" and the model id (testimony) are recorded by a run.
"""
import getpass
import importlib
import os
import subprocess
import sys

SERVICE = "vera-loom"
ACCOUNT = "anthropic"
PROBE_MODEL = "claude-haiku-4-5-20251001"


def keychain_get():
    r = subprocess.run(["security", "find-generic-password", "-s", SERVICE, "-a", ACCOUNT, "-w"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def keychain_set(value):
    subprocess.run(["security", "add-generic-password", "-U", "-s", SERVICE, "-a", ACCOUNT, "-w", value],
                   check=True, capture_output=True)


def keychain_clear():
    subprocess.run(["security", "delete-generic-password", "-s", SERVICE, "-a", ACCOUNT], capture_output=True)


def ensure_sdk():
    try:
        importlib.import_module("anthropic")
        return True
    except ImportError:
        print("installing the anthropic SDK into", sys.executable)
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "anthropic"])
        if r.returncode != 0:
            print("pip install anthropic failed")
            return False
        importlib.invalidate_caches()
        importlib.import_module("anthropic")
        return True


def probe(key):
    """One minimal call.  Returns (ok, message).  Never prints the key."""
    import anthropic
    try:
        c = anthropic.Anthropic(api_key=key)
        m = c.messages.create(model=PROBE_MODEL, max_tokens=1, messages=[{"role": "user", "content": "x"}])
        return True, "ok (model %s, %d input tokens billed)" % (m.model, m.usage.input_tokens)
    except anthropic.AuthenticationError:
        return False, "the key was rejected (AuthenticationError)"
    except Exception as e:  # network, rate limit, etc.
        return False, "call failed: %s" % type(e).__name__


def masked(key):
    return key[:7] + "…" + key[-4:] if len(key) > 14 else "(short)"


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "check"
    if cmd == "set":
        key = getpass.getpass("Anthropic API key (input is hidden): ").strip()
        if not key.startswith("sk-ant-"):
            print("that does not look like an Anthropic key (expected sk-ant-…); nothing stored")
            return 2
        keychain_set(key)
        print("stored in the macOS Keychain as service=%s account=%s (%s)" % (SERVICE, ACCOUNT, masked(key)))
        if not ensure_sdk():
            return 3
        ok, msg = probe(key)
        print("validation:", msg)
        return 0 if ok else 4
    if cmd == "clear":
        keychain_clear()
        print("Keychain entry removed")
        return 0
    if cmd == "check":
        src, key = None, os.environ.get("ANTHROPIC_API_KEY")
        if key:
            src = "environment"
        else:
            key = keychain_get()
            src = "keychain" if key else None
        if not key:
            print("no key: set ANTHROPIC_API_KEY or run `python tools/vera_api_key.py set`")
            return 1
        print("key found in the %s (%s)" % (src, masked(key)))
        if not ensure_sdk():
            return 3
        ok, msg = probe(key)
        print("validation:", msg)
        return 0 if ok else 4
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
