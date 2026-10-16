"""Helpers of the geometry-ablation tests (ticket C): the inputs and the fingerprints whose GOLDEN values (tests/line3/golden_geometry.json) were recorded on the tree BEFORE the geometry profile existed
(line3 a8296ae4), for the default crosses (A3) and for the flat table (A3f).  Pure; no network."""
import glob
import hashlib
import json
import os

from verantyx.loom import memcross as mx
from verantyx.loom import memdoor as md
from verantyx.loom import memory as mem
from verantyx.loom import memview as mv
from verantyx.loom.corpus import Corpus
from verantyx.loom.memguard import make_source

RICH = ["認証の決済は金曜", "認証の期限は金曜", "決済の認証は月曜", "広報の担当は山本", "認証の期限は金曜から水曜に変更", "決済の期限は月曜", "認証の期限は木曜", "資料を送付した",
        "山本が議事録を作成した", "田中が議事録を作成した", "広報の担当は佐藤", "認証の担当は決済の担当", "決済の期限は火曜", "会議を東京で開く", "認証の期限は金曜", "山本が資料を送付した",
        "認証の担当は山本", "担当の認証は山本", "決済の担当は田中", "田中の決済は水曜"]
DECLS = [{"session": 1, "at": 3, "topic": "新製品"}, {"session": 2, "at": 12, "topic": "新製品の開発"}]


def rows(texts=RICH):
    out = []
    for i, t in enumerate(texts):
        out.append({"kind": "base", "sent": t, "source": make_source("t", 1 if i < 10 else 2, i)})
    return out


def index_prints(**kw):
    """sha of the full rebuild and of the incremental fold, plus the canonical JSON sha, for the RICH story."""
    rs = rows()
    ix = mx.build_index(rs, DECLS, **kw)
    b = mx.IndexBuilder(**kw) if "geometry" in kw or "flat" in kw else mx.IndexBuilder()
    prev = Corpus(b"")
    di = 0
    for t, r in enumerate(rs):
        while di < len(DECLS) and DECLS[di]["at"] <= t:
            b.declare(DECLS[di]["session"], DECLS[di]["at"], DECLS[di]["topic"])
            di += 1
        b.add_row(t, r, prev)
        b.index()
        prev = Corpus(mx._rows_bytes(rs[:t + 1]))
    return {"build": ix.index_sha, "incremental": b.index().index_sha, "obj": hashlib.sha256(json.dumps(ix.to_obj(), sort_keys=True, ensure_ascii=False).encode()).hexdigest()}


def session_prints(tmp_path, name, versions):
    """The ledger rows of a view session over RICH (store/model-facing results included) hashed; the model-facing results too."""
    door = md.StructureDoor(str(tmp_path / name), "notes", "test-model", profile=mem.PROFILE_V4, versions=versions, view=mv.make_view())
    door.set_turn("1-1")
    out = [door.call("declare_topic", {"text": "新製品"})]
    for t in RICH:
        out.append(door.call("write", {"text": t}))
    out.append(door.call("view", {"centre": "期限"}))
    out.append(door.call("view_nest", {"topic": "新製品"}))
    out.append(door.call("recall", {"question": "認証の期限は何ですか"}) if "recall" in door.tool_names else None)
    rows_ = door.session.rows()
    sha = door.session.run.builder.index().index_sha
    door.commit()
    door.close()
    h = hashlib.sha256(json.dumps(rows_, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    h2 = hashlib.sha256(json.dumps(out, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {"rows": h, "door": h2, "index": sha}
