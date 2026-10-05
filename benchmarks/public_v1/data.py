"""公開の比較プロトコル public_v1 のデータの読み込み（文書・問い・docset）。"""
import json
import os
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

# docset -> 文書ファイル名（docs/ か docs_unrelated/ にある）。ファイル名の昇順で使う。
MAIN_DOCS = {
    "D1": "D1_bihin_kitei.txt",
    "D2": "D2_shiryo_tejun.txt",
    "D3": "D3_gijiroku.txt",
    "D4v1": "D4_shiyou_v1.txt",
    "D4v2": "D4_shiyou_v2.txt",
}
UNRELATED = ["U%02d.txt" % i for i in range(1, 37)]

DOCSETS = {
    "S1": [MAIN_DOCS["D1"]],
    "S2": [MAIN_DOCS["D2"]],
    "S3": [MAIN_DOCS["D3"]],
    "S4": [MAIN_DOCS["D4v1"], MAIN_DOCS["D4v2"]],
    "SM": [MAIN_DOCS["D1"], MAIN_DOCS["D2"], MAIN_DOCS["D3"], MAIN_DOCS["D4v2"]] + UNRELATED,
}

ABSTAIN_TEXT = "文書に記載がありません"


def nfkc(s):
    return unicodedata.normalize("NFKC", s)


def doc_path(fname):
    p = os.path.join(DATA, "docs", fname)
    if os.path.exists(p):
        return p
    return os.path.join(DATA, "docs_unrelated", fname)


def read_lines(fname):
    with open(doc_path(fname), encoding="utf-8") as f:
        t = f.read()
    lines = t.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return lines


def docset_files(docset):
    """docset の文書ファイル名（ファイル名の昇順）。"""
    return sorted(DOCSETS[docset])


def docset_sentences(docset):
    """[(ファイル名, 行番号(1 始まり), 本文)] を、ファイル名の昇順・行番号順で。"""
    out = []
    for fn in docset_files(docset):
        for i, t in enumerate(read_lines(fn), 1):
            out.append((fn, i, t))
    return out


def load_questions(path=None):
    path = path or os.path.join(DATA, "questions.jsonl")
    out = []
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out


def reps_for(q):
    """PARA は 3 回、他は 1 回。"""
    return (0, 1, 2) if q["cat"] == "PARA" else (0,)
