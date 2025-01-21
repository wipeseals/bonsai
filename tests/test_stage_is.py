from bonsai.pipeline_stage import InstFetchStage

from tests.testutil import run_sim


def test_is_increment():
    dut = InstFetchStage()

    async def bench(ctx):
        # initial
        addr = 0xAA
        ctx.set(dut.input.ctrl.en, 1)
        ctx.set(dut.side.clr, 0)
        ctx.set(dut.input.pc, addr)
        await ctx.tick()
        assert ctx.get(dut.output.addr) == addr
        assert ctx.get(dut.output.ctrl.en) == 1
        # jump
        addr = 0x55
        ctx.set(dut.input.ctrl.en, 1)
        ctx.set(dut.input.pc, addr)
        await ctx.tick()
        assert ctx.get(dut.output.addr) == addr
        assert ctx.get(dut.output.ctrl.en) == 1

    run_sim(f"{test_if_jump.__name__}", dut=dut, testbench=bench)
