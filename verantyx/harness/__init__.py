"""Vera Harness: the product layer around the loom (backends, runner, CLI).

Everything a model says reaches the user only as (a) a quote that the loom's emit gate passed, or (b) an abstention with a typed reason.
The core (verantyx.loom, verantyx.line3) is exact, deterministic and imports no SDK and no network module; the SDKs are imported here, lazily,
and only by the backends.
"""
