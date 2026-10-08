#!/usr/bin/env python
"""Record prompt/schema hashes for all generator forms."""
from tools import gen_coarse_evidence as gce


for kind in ("noun", "pred", "ntype", "role"):
    spec = gce.KINDS[kind]
    print(kind,
          "template_sha256", spec["template_sha"](),
          "schema_sha256", gce.schema_sha256(spec["schema"]))
