from amaranth import Module, Signal, unsigned
from amaranth.lib import wiring, enum, data
from amaranth.lib.wiring import In, Out
from amaranth.cli import main

from counter import Counter


class InstType(enum.Enum):
    # R-type
    R = 0
    # I-type
    I = 1  # noqa: E741
    # S-type
    S = 2
    # B-type
    B = 3
    # U-type
    U = 4
    # J-type
    J = 5


class RegLayout(data.StructLayout):
    """
    x0 - x31 + pc までのレジスタ
    """

    def __init__(self, width=32, xlen=32):
        self.width = width
        self.xlen = xlen

        super().__init__(
            {
                "x": data.ArrayLayout(unsigned(width), xlen),
                "pc": unsigned(width),
            }
        )

    def __call__(self, target):
        return RegView(self, target)


class RegView(data.View):
    def x(self, index):
        return self["x"][index]


class Top(wiring.Component):
    def __init__(self):
        self.counter = Counter(16)
        super().__init__()

    def elaborate(self, platform):
        m = Module()
        m.submodules.counter = self.counter

        return m


if __name__ == "__main__":
    top = Top()
    main(top)
