ZERO = 0


def add(a, b):
    return a + b


def mul(a, b):
    return a * b


def pairs(xs):
    out = []
    for x in xs:
        out.append((x, x))
    return out
