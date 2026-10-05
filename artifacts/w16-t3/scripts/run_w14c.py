"""W14 の runner（読み取り・実行だけ）を、vera serve の cwd・PYTHONPATH が W16-t3 の木になるように包む。W14 の木の verantyx は読み込まない。"""
import sys

CWD = "/Users/motonisihikoudai/Projects/vera-impl/wt/W16-t3-S"
W14 = "/Users/motonisihikoudai/Projects/vera-impl/wt/W14-bench-S"
sys.path.append(W14)                      # 末尾に足す（先頭に入れると W14 の verantyx が先に読まれる）
from benchmarks.public_v1 import run as R  # noqa: E402

R.REPO = CWD
assert all(m.__file__.startswith(CWD + "/") for n, m in sys.modules.items() if n.startswith("verantyx") and getattr(m, "__file__", None))
assert R.__file__.startswith(W14 + "/")
sys.exit(R.main(sys.argv[1:]))
