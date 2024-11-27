from amaranth import Const
from bonsai import config
from bonsai.stage import IsStage

from tests.testutil import run_sim


def generate_test_data():
    """
    Generate test data for instruction fetch second stage.
    """
    return [Const(~x, config.INST_SHAPE) for x in range(config.L1_CACHE_DEPTH)]


def test_is_freerun():
    inst_test_data = generate_test_data()
    dut = IsStage(init_data=inst_test_data)

    async def bench(ctx):
        for i in range(config.L1_CACHE_DEPTH):
            addr = i * 4
            ctx.set(dut.input.ctrl.en, 1)
            ctx.set(dut.input.addr, addr)
            ctx.set(dut.input.ctrl.debug.cyc, i)
            ctx.set(dut.input.ctrl.debug.seqno, i)
            ctx.set(dut.side_ctrl.clr, 0)
            await ctx.tick()
            assert ctx.get(dut.output.addr) == addr
            assert ctx.get(dut.output.inst) == inst_test_data[i].value
            assert ctx.get(dut.output.ctrl.en) == 1
            assert ctx.get(dut.output.ctrl.debug.seqno) == i

    run_sim(f"{test_is_freerun.__name__}", dut=dut, testbench=bench)
