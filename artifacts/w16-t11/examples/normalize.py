#!/usr/bin/env python3
"""W16-t11: 再生の出力の正規化。規則は次の 2 つだけ（README の例の下にも書く）。
 (a) attest の 1 行目の `tree=<出力先の絶対パス>/` を `tree=./` に置き換える。
 (b) `events verify` の `"head": "<64 桁の 16 進>"` を `"head": "<sha256>"` に置き換える。
件数・状態・型・終了コード・problems は置き換えない。

使い方:
  normalize.py <再生の出力先> <書き出し先>   正規化した <name>.cmd/.stdout/.stderr/.exit を書き出す
  normalize.py --print <再生の出力先>        正規化した全ファイルを連結して標準出力へ
"""
import os
import re
import sys

HEAD = re.compile(r'("head": ")[0-9a-f]{64}(")')


def normalize(name, text, out_dir):
    real = os.path.realpath(out_dir)
    if name.endswith(".stdout") and name.startswith("a_attest"):
        for root in {real, os.path.abspath(out_dir)}:
            text = text.replace("tree=" + root + "/", "tree=./")
    if name.endswith(".stdout") and "verify" in name:
        text = HEAD.sub(r"\1<sha256>\2", text)
    return text


def files(out_dir):
    rec = os.path.join(out_dir, "rec")
    return sorted(f for f in os.listdir(rec) if f.endswith((".cmd", ".stdout", ".stderr", ".exit")))


def main(argv):
    if len(argv) == 2 and argv[0] == "--print":
        out_dir = argv[1]
        for f in files(out_dir):
            text = open(os.path.join(out_dir, "rec", f), encoding="utf-8").read()
            sys.stdout.write("=== %s\n%s" % (f, normalize(f, text, out_dir)))
        return 0
    if len(argv) == 2:
        out_dir, dest = argv
        os.makedirs(dest, exist_ok=True)
        for f in files(out_dir):
            text = open(os.path.join(out_dir, "rec", f), encoding="utf-8").read()
            with open(os.path.join(dest, f), "w", encoding="utf-8") as fh:
                fh.write(normalize(f, text, out_dir))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
