from typing import Callable
from amaranth.sim import Simulator

from bonsai.counter import Counter
from tests.common import run


def test_disable_counter():
    counter = Counter(16)

    async def bench(ctx):
        ctx.set(counter.clr, 0)
        ctx.set(counter.en, 0)
        for _ in range(16):
            await ctx.tick()
            assert not ctx.get(counter.ovf)

    run(f"{test_disable_counter.__name__}", dut=counter, testbench=bench)


def test_enable_counter():
    counter = Counter(16)

    async def bench(ctx):
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

    run(f"{test_enable_counter.__name__}", dut=counter, testbench=bench)


def test_disable_when_overflow():
    counter = Counter(16)

    async def bench(ctx):
        ctx.set(counter.clr, 0)
        ctx.set(counter.en, 1)
        for _ in range(15):
            await ctx.tick()
            assert not ctx.get(counter.ovf)
        await ctx.tick()
        assert ctx.get(counter.ovf)

        ctx.set(counter.clr, 0)
        ctx.set(counter.en, 0)
        for _ in range(10):
            await ctx.tick()
            assert ctx.get(counter.ovf)

        # overflowed counter
        ctx.set(counter.clr, 0)
        ctx.set(counter.en, 1)
        await ctx.tick()
        assert not ctx.get(counter.ovf)

    run(f"{test_disable_when_overflow.__name__}", dut=counter, testbench=bench)


def test_clear_counter():
    counter = Counter(16)

    async def bench(ctx):
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

    run(f"{test_clear_counter.__name__}", dut=counter, testbench=bench)
