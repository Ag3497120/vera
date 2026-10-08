"""W4-m test helper: an in-memory reference `Ledger` (a list of dicts) and a deterministic clock.

It satisfies the same four-function contract as `verantyx.sovereign.SovereignLedger`
(and as the in-memory ledger W3-c keeps for its own tests); the two do not depend on each other.
Ids are `<store_id>:<seq>` exactly as in the persistent one.
"""
from datetime import datetime, timedelta, timezone


class FakeClock:
    """Each call returns the next instant: start, start+step, ... (timezone-aware, UTC)."""

    def __init__(self, start=None, step=timedelta(seconds=1)):
        self.t = start or datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
        self.step = step
        self._first = True

    def __call__(self):
        if self._first:
            self._first = False
        else:
            self.t = self.t + self.step
        return self.t


def day(n, hour=0, minute=0):
    """The n-th UTC day after 2026-10-01, as an aware datetime (n = 0 is 2026-10-01)."""
    return datetime(2026, 10, 1, hour, minute, 0, tzinfo=timezone.utc) + timedelta(days=n)


class MemoryLedger:
    def __init__(self, store_id, now=None):
        self.store_id = store_id
        self._now = now or FakeClock()
        self._rows = []

    def append(self, event):
        assert set(event) == {"kind", "payload"}
        seq = len(self._rows) + 1
        self._rows.append({"id": f"{self.store_id}:{seq}", "seq": seq,
                           "ts": self._now().astimezone(timezone.utc).isoformat(timespec="seconds"),
                           "kind": event["kind"], "payload": dict(event["payload"])})
        return f"{self.store_id}:{seq}"

    def events(self, since=None):
        rows = [dict(r, payload=dict(r["payload"])) for r in self._rows]
        if since is None:
            return rows
        ids = [r["id"] for r in rows]
        if since not in ids:
            raise LookupError(since)
        return rows[ids.index(since) + 1:]

    def _matching(self, key, value):
        return [r for r in self._rows if key in r["payload"]
                and type(r["payload"][key]) is type(value) and r["payload"][key] == value]

    def count(self, key, value):
        return len(self._matching(key, value))

    def last_seq(self, key, value):
        m = self._matching(key, value)
        return max(r["seq"] for r in m) if m else None
