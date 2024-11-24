from amaranth import unsigned

from bonsai.instfetch import InstFetch
from tests.common import run


def test_fetch_incremental():
    init_data = list([x for x in range(256)])
    dut = InstFetch(data_shape=unsigned(32), inst_mem_init_data=init_data)

    async def bench(ctx):
        
        for i in len(init_data):
            ctx.set(dut.next_pc, i)
            await ctx.tick()
            assert ctx.get(dut.valid)

        ctx.set(dut.clr, 1)
        ctx.set(dut.en, 1)
        await ctx.tick()
        assert not ctx.get(dut.ovf)

        ctx.set(dut.clr, 0)
        ctx.set(dut.en, 1)
        for _ in range(15):
            await ctx.tick()
            assert not ctx.get(dut.ovf)
        await ctx.tick()
        assert ctx.get(dut.ovf)

    run(f"{test_fetch_incremental.__name__}", dut=dut, testbench=bench)
