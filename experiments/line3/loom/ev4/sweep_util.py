import unicodedata


def norm(x):
    return "".join(ch for ch in unicodedata.normalize("NFKC", x).casefold() if not ch.isspace() and ch != "・")
