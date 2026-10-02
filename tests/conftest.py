"""Suite-wide environment classification.

* ``@pytest.mark.needs_resource("node")`` skips a test with a reason that starts
  ``ENV_MISSING[node]`` when that resource is absent.
* A missing tokenizer stops the session with an explicit ENV_MISSING message
  rather than hundreds of unexplained failures.
* The summary lists every skip by resource and flags any skip that did not name one.
"""
from __future__ import annotations

import re
from collections import defaultdict

import pytest

import _vera_env


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "needs_resource(name): skip as ENV_MISSING[name] when the named external resource is absent "
        "(names are the keys of tests/_vera_env.RESOURCES)",
    )


def pytest_sessionstart(session):
    if not _vera_env.available("fugashi"):
        pytest.exit(_vera_env.reason("fugashi")
                    + " - every semantic test needs it; install `fugashi` and `unidic-lite`", returncode=4)


def pytest_collection_modifyitems(config, items):
    for item in items:
        for mark in item.iter_markers("needs_resource"):
            name = mark.args[0]
            if not _vera_env.available(name):
                item.add_marker(pytest.mark.skip(reason=_vera_env.reason(name)))


_SKIP_RE = re.compile(r"^" + _vera_env.PREFIX + r"\[([^\]]+)\]")


def pytest_terminal_summary(terminalreporter):
    by_resource = defaultdict(list)
    unclassified = []
    for report in terminalreporter.stats.get("skipped", []):
        longrepr = report.longrepr
        text = longrepr[2] if isinstance(longrepr, tuple) else str(longrepr)
        text = re.sub(r"^Skipped: ", "", text)
        match = _SKIP_RE.match(text)
        (by_resource[match[1]] if match else unclassified).append(report.nodeid)
    if not by_resource and not unclassified:
        return
    terminalreporter.section("environment classification of skips")
    for name in sorted(by_resource):
        terminalreporter.write_line(f"ENV_MISSING[{name}]: {len(by_resource[name])} skipped")
    for nodeid in unclassified:
        terminalreporter.write_line(f"UNCLASSIFIED_SKIP: {nodeid}")
