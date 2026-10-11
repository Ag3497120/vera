from calc.ops import add


class Counter:
    def __init__(self, start):
        self.value = start

    def bump(self, step):
        self.value = add(self.value, step)
        return self.value
