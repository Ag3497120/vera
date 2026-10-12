"""Where the L2 driver's credential comes from.  The key is resolved at call time and handed to the SDK client
only; it is never placed in a run folder, a ledger row, a result file or a log.

Order: the environment variable ANTHROPIC_API_KEY, then the macOS Keychain item written by
tools/vera_api_key.py (service "vera-loom", account "anthropic").  Returns None when neither holds a key.
"""
import os
import subprocess

SERVICE = "vera-loom"
ACCOUNT = "anthropic"


def resolve_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    try:
        r = subprocess.run(["security", "find-generic-password", "-s", SERVICE, "-a", ACCOUNT, "-w"],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() or None if r.returncode == 0 else None


def key_source():
    """'environment' | 'keychain' | None — safe to record (no value)."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "environment"
    return "keychain" if resolve_api_key() else None
