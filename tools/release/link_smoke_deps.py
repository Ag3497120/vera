"""新規 smoke venv に既存の日本語 tokenizer/dictionary だけを露出する。"""
from __future__ import annotations

import importlib.metadata
import importlib.util
import os
from pathlib import Path
import sys


def main(argv):
    site_packages = Path(argv[1]).resolve()
    names = ("fugashi", "unidic_lite")
    for name in names:
        spec = importlib.util.find_spec(name)
        if spec is None or not spec.origin:
            raise SystemExit("smoke に必要な既存依存がありません: " + name)
        source = Path(spec.origin).resolve().parent
        target = site_packages / name
        if not source.is_dir() or target.exists() or target.is_symlink():
            raise SystemExit("smoke 依存を隔離 venv に接続できません: " + name)
        os.symlink(str(source), str(target), target_is_directory=True)
        distribution_name = "unidic-lite" if name == "unidic_lite" else name
        distribution = importlib.metadata.distribution(distribution_name)
        dist_target = site_packages / Path(distribution._path).name
        if dist_target.exists() or dist_target.is_symlink():
            raise SystemExit("smoke 依存 metadata が既にあります: " + distribution_name)
        os.symlink(str(distribution._path), str(dist_target), target_is_directory=True)
        print("smoke 依存を接続しました: {} {}".format(name, distribution.version))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
