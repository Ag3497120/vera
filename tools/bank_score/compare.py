"""python -m tools.bank_score.compare <outA> <outB>: 所要時間以外の出力が一致するかを調べる（S6）。

除く欄は下の明示リストだけ。リスト外の違いは不一致として報告する。
リストは「同じ入力で 2 回走らせて実測で違った欄」から決めた（docs/BANK_SCORE.md に実測の手順を書いた）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# results.jsonl の行の所要時間
ROW_VOLATILE = ("elapsed_ms",)
# raw/*.json の中（Vera の生出力の中を含め、再帰して除く）の所要時間の欄
RAW_VOLATILE = ("elapsed_ms", "ingest_ms", "ms")
# run_meta.json の所要時間は "timing" の下にまとめてある
META_VOLATILE = ("timing",)


def strip_keys(o: object, keys: tuple[str, ...]) -> object:
    if isinstance(o, dict):
        return {k: strip_keys(v, keys) for k, v in o.items() if k not in keys}
    if isinstance(o, list):
        return [strip_keys(v, keys) for v in o]
    return o


def _load_jsonl(p: Path, keys: tuple[str, ...]) -> list:
    return [strip_keys(json.loads(ln), keys) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _files(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def compare(a: Path, b: Path) -> list[str]:
    diffs: list[str] = []
    fa, fb = _files(a), _files(b)
    for f in sorted(set(fa) - set(fb)):
        diffs.append(f"{f}: A にだけ有る")
    for f in sorted(set(fb) - set(fa)):
        diffs.append(f"{f}: B にだけ有る")
    for f in sorted(set(fa) & set(fb)):
        pa, pb = a / f, b / f
        if f == "run_meta.json":
            va = strip_keys(json.loads(pa.read_text(encoding="utf-8")), META_VOLATILE)
            vb = strip_keys(json.loads(pb.read_text(encoding="utf-8")), META_VOLATILE)
        elif f.endswith("results.jsonl"):
            va, vb = _load_jsonl(pa, ROW_VOLATILE), _load_jsonl(pb, ROW_VOLATILE)
        elif f.startswith("raw/") and f.endswith(".json"):
            va = strip_keys(json.loads(pa.read_text(encoding="utf-8")), RAW_VOLATILE)
            vb = strip_keys(json.loads(pb.read_text(encoding="utf-8")), RAW_VOLATILE)
        elif f.endswith(".json"):
            va, vb = json.loads(pa.read_text(encoding="utf-8")), json.loads(pb.read_text(encoding="utf-8"))
        else:
            va, vb = pa.read_text(encoding="utf-8"), pb.read_text(encoding="utf-8")
        if va != vb:
            diffs.append(f"{f}: 不一致")
    return diffs


def measure(a: Path, b: Path) -> dict[str, int]:
    """raw/*.json を何も除かずに比べ、値が違った欄の経路ごとの件数を返す（除く欄のリストを実測で決めるため）。"""
    diffs: dict[str, int] = {}

    def walk(x: object, y: object, path: str) -> None:
        if isinstance(x, dict) and isinstance(y, dict):
            for k in sorted(set(x) | set(y)):
                if k not in x or k not in y:
                    diffs[f"{path}/{k}(片方に無い)"] = diffs.get(f"{path}/{k}(片方に無い)", 0) + 1
                else:
                    walk(x[k], y[k], f"{path}/{k}")
        elif isinstance(x, list) and isinstance(y, list) and len(x) == len(y):
            for i, (p, q) in enumerate(zip(x, y)):
                walk(p, q, f"{path}[]")
        elif x != y:
            diffs[path] = diffs.get(path, 0) + 1

    for f in sorted((a / "raw").glob("*.json")):
        g = b / "raw" / f.name
        if g.is_file():
            walk(json.loads(f.read_text(encoding="utf-8")), json.loads(g.read_text(encoding="utf-8")), "")
    return diffs


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) == 3 and argv[2] == "--measure":
        d = measure(Path(argv[0]), Path(argv[1]))
        for k, v in sorted(d.items()):
            print(f"{v}\t{k}")
        print(f"違った経路: {len(d)} 種")
        return 0
    if len(argv) != 2:
        print("使い方: python -m tools.bank_score.compare <outA> <outB> [--measure]", file=sys.stderr)
        return 2
    a, b = Path(argv[0]), Path(argv[1])
    if not (a.is_dir() and b.is_dir()):
        print("ディレクトリでない", file=sys.stderr)
        return 2
    diffs = compare(a, b)
    nfiles = len(_files(a))
    if diffs:
        print(f"不一致 {len(diffs)} 件 ({a} と {b})")
        for d in diffs:
            print("  " + d)
        return 1
    print(f"一致: {nfiles} ファイル（除いた欄: results {list(ROW_VOLATILE)}, raw {list(RAW_VOLATILE)}, "
          f"run_meta {list(META_VOLATILE)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
