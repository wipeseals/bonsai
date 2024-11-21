from amaranth import Module, Signal
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.sim import Simulator


class Counter(wiring.Component):
    en: In(1)
    ovf: Out(1)

    def __init__(self, limit: int):
        self.limit = limit
        self.count = Signal(16)
        super().__init__()

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.ovf.eq(self.count == self.limit)

        with m.If(self.en):
            with m.If(self.ovf):
                m.d.sync += self.count.eq(0)
            with m.Else():
                m.d.sync += self.count.eq(self.count + 1)

        return m


def test_counter():
    counter = Counter(16)

    async def bench(ctx):
        # disable counter
        ctx.set(counter.en, 0)
        for _ in range(16):
            await ctx.tick()
            assert not ctx.get(counter.ovf)

        # enable counter
        ctx.set(counter.en, 1)
        for _ in range(15):
            await ctx.tick()
            assert not ctx.get(counter.ovf)
        await ctx.tick()
        assert ctx.get(counter.ovf)

        # overflowed counter
        await ctx.tick()
        assert not ctx.get(counter.ovf)

    sim = Simulator(counter)
    sim.add_clock(1)
    sim.add_testbench(bench)
    with sim.write_vcd("counter.vcd"):
        sim.run()


if __name__ == "__main__":
    test_counter()
