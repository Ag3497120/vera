"""wheel の全 member path を並べる。"""
from __future__ import annotations

from pathlib import Path
import sys
import zipfile


def main(argv):
    wheel, output = map(Path, argv[1:])
    with zipfile.ZipFile(wheel) as archive:
        names = sorted(name for name in archive.namelist() if not name.endswith("/"))
    output.write_text("".join(name + "\n" for name in names), encoding="utf-8")
    print("wheel member 数: {}".format(len(names)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
