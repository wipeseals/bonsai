from amaranth import Module, Signal, unsigned
from amaranth.lib import wiring, enum, data
from amaranth.lib.wiring import In, Out
from amaranth.cli import main



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



class InstFetch(wiring.Component):
    """
    Instruction Fetch Unit
    Attributes:
        pc (In): Program Counter
        inst (Out): Instruction
    """

    def __init__(self, width: int = 32):
        self.pc = Signal(width)

        self.next_pc = In(width)
        self.pc_out = Out(width)
        self.inst_out = Out(width)

        super().__init__()

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.pc_out.eq(self.pc)

        return m


if __name__ == "__main__":
    instfetch = InstFetch(width=32)
    main(instfetch)
