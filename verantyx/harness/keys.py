"""Where the credentials come from.  A key is resolved at call time and handed to the SDK client only; it is never printed, never placed in a run
folder, a ledger row, a result file, a log or an error message (`redact` removes every key this process knows from any text it is asked to clean).

Order, per provider:
  anthropic   env ANTHROPIC_API_KEY, then the macOS Keychain item (service "vera-harness", account "anthropic"; the research tree's
              the research tree's ("vera-loom", "anthropic") item is NOT read: copy it yourself if you want it).
  openai      env VERA_OPENAI_API_KEY, then OPENAI_API_KEY, then the Keychain item ("vera-harness", "openai").
              A local OpenAI-compatible server (Ollama, LM Studio, vLLM, an MLX server) needs no key: with a base URL and no key the placeholder
              "not-needed" is sent.
`--api-key-env NAME` names another environment variable.

Store a key in the Keychain without it entering shell history or `ps`:  security add-generic-password -s vera-harness -a anthropic -w
(the command prompts for the value).
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

KEYCHAIN_SERVICE = "vera-harness"
ENV_ORDER: Dict[str, Tuple[str, ...]] = {
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openai": ("VERA_OPENAI_API_KEY", "OPENAI_API_KEY"),
}
KEYCHAIN_ITEMS: Dict[str, Tuple[Tuple[str, str], ...]] = {
    "anthropic": ((KEYCHAIN_SERVICE, "anthropic"),),
    "openai": ((KEYCHAIN_SERVICE, "openai"),),
}
LOCAL_PLACEHOLDER = "not-needed"
_KNOWN: List[str] = []                       # secrets this process has resolved (for `redact`); never written anywhere


def _remember(key: str) -> None:
    if key and key not in _KNOWN:
        _KNOWN.append(key)


def _keychain(service: str, account: str) -> Optional[str]:
    if sys.platform != "darwin":
        return None
    try:
        r = subprocess.run(["security", "find-generic-password", "-s", service, "-a", account, "-w"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (r.stdout.strip() or None) if r.returncode == 0 else None


def resolve_api_key(provider: str, env_name: Optional[str] = None) -> Optional[str]:
    names = (env_name,) if env_name else ENV_ORDER[provider]
    for n in names:
        v = os.environ.get(n)
        if v:
            _remember(v)
            return v
    if env_name:
        return None
    for service, account in KEYCHAIN_ITEMS[provider]:
        v = _keychain(service, account)
        if v:
            _remember(v)
            return v
    return None


def key_source(provider: str, env_name: Optional[str] = None) -> Optional[str]:
    """'environment' | 'keychain' | None: safe to record (no value)."""
    names = (env_name,) if env_name else ENV_ORDER[provider]
    if any(os.environ.get(n) for n in names):
        return "environment"
    if env_name:
        return None
    return "keychain" if any(_keychain(s, a) for s, a in KEYCHAIN_ITEMS[provider]) else None


def known_secrets() -> List[str]:
    """Every secret value this process can know: the ones resolved so far plus the provider variables of the environment."""
    vals = list(_KNOWN)
    for names in ENV_ORDER.values():
        for n in names:
            v = os.environ.get(n)
            if v and v not in vals:
                vals.append(v)
    return vals


def redact(text: object) -> str:
    """`text` with every known secret replaced by [redacted] (error messages of an SDK may echo a key)."""
    s = str(text)
    for k in sorted(known_secrets(), key=len, reverse=True):
        if len(k) >= 6:
            s = s.replace(k, "[redacted]")
    return s
