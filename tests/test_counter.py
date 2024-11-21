from amaranth.sim import Simulator

from rusk.counter import Counter


def test_counter():
    counter = Counter(16)

    async def bench(ctx):
        # disable counter
        ctx.set(counter.clr, 0)
        ctx.set(counter.en, 0)
        for _ in range(16):
            await ctx.tick()
            assert not ctx.get(counter.ovf)

        # enable counter
        ctx.set(counter.clr, 0)
        ctx.set(counter.en, 1)
        for _ in range(15):
            await ctx.tick()
            assert not ctx.get(counter.ovf)
        await ctx.tick()
        assert ctx.get(counter.ovf)

        # overflowed counter
        await ctx.tick()
        assert not ctx.get(counter.ovf)

        # clear counter
        ctx.set(counter.clr, 0)
        ctx.set(counter.en, 1)
        for _ in range(10):
            await ctx.tick()
            assert not ctx.get(counter.ovf)

        ctx.set(counter.clr, 1)
        ctx.set(counter.en, 1)
        await ctx.tick()
        assert not ctx.get(counter.ovf)

        ctx.set(counter.clr, 0)
        ctx.set(counter.en, 1)
        for _ in range(15):
            await ctx.tick()
            assert not ctx.get(counter.ovf)
        await ctx.tick()
        assert ctx.get(counter.ovf)

    sim = Simulator(counter)
    sim.add_clock(1)
    sim.add_testbench(bench)
    with sim.write_vcd("counter.vcd"):
        sim.run()
