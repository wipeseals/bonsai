from amaranth import Module, Signal
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.cli import main


class Counter(wiring.Component):
    """
    Counter is a hardware component that counts up to a specified limit and then resets.
    Attributes:
        en (In): Input signal to enable the counter.
        ovf (Out): Output signal that indicates when the counter has overflowed.
        clr (In): Input signal to clear the counter. en and clr must be high to clear the counter.
        limit (int): The maximum value the counter will count to before resetting.
        count (Signal): The current count value, represented as a 16-bit signal.
    """

    en: In(1)
    clr: In(1)
    ovf: Out(1)

    def __init__(self, limit: int):
        self.limit = limit
        self.count = Signal(16)
        super().__init__()

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.ovf.eq(self.count == self.limit)

        with m.If(self.en):
            with m.If(self.clr):
                m.d.sync += self.count.eq(0)
            with m.Elif(self.ovf):
                m.d.sync += self.count.eq(0)
            with m.Else():
                m.d.sync += self.count.eq(self.count + 1)

        return m


if __name__ == "__main__":
    counter = Counter(16)
    main(counter)
