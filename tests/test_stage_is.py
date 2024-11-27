from operator import is_
from amaranth import Const
from bonsai import config
from bonsai.stage import IsStage

from tests.testutil import run_sim


def generate_test_data():
    """
    Generate test data for instruction fetch second stage.
    """
    return [Const(~x, config.INST_SHAPE) for x in range(config.L1_CACHE_DEPTH)]


def test_is_flush():
    dut = IsStage()

    async def bench(ctx):
        # initial
        addr = 0xAA
        ctx.set(dut.input.ctrl.en, 1)
        ctx.set(dut.side_ctrl.clr, 0)
        ctx.set(dut.input.addr, addr)
        await ctx.tick()
        assert ctx.get(dut.output.addr) == addr
        assert ctx.get(dut.output.ctrl.en) == 1
        # flush
        addr = 0x55
        ctx.set(dut.input.ctrl.en, 1)
        ctx.set(dut.side_ctrl.clr, 1)
        ctx.set(dut.input.addr, addr)
        await ctx.tick()
        assert ctx.get(dut.output.addr) == 0
        assert ctx.get(dut.output.ctrl.en) == 0

    run_sim(f"{test_is_flush.__name__}", dut=dut, testbench=bench)


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


def test_is_stall():
    inst_test_data = generate_test_data()
    dut = IsStage(init_data=inst_test_data)

    async def bench(ctx):
        stall_start_cyc = 10
        stall_end_cyc = 20
        for i in range(config.L1_CACHE_DEPTH):
            is_stall = stall_start_cyc <= i < stall_end_cyc
            addr = i * 4
            if is_stall:
                ctx.set(dut.input.ctrl.en, 0)
            else:
                ctx.set(dut.input.ctrl.en, 1)
            ctx.set(dut.input.addr, addr)
            ctx.set(dut.input.ctrl.debug.cyc, i)
            ctx.set(dut.input.ctrl.debug.seqno, i)
            ctx.set(dut.side_ctrl.clr, 0)
            await ctx.tick()
            if is_stall:
                # assert ctx.get(dut.output.addr) == 0 # Don't care
                # assert ctx.get(dut.output.inst) == 0 # Don't care
                assert ctx.get(dut.output.ctrl.en) == 0
            else:
                assert ctx.get(dut.output.addr) == addr
                assert ctx.get(dut.output.inst) == inst_test_data[i].value
                assert ctx.get(dut.output.ctrl.en) == 1
                assert ctx.get(dut.output.ctrl.debug.seqno) == i

    run_sim(f"{test_is_stall.__name__}", dut=dut, testbench=bench)


def test_is_flush_when_stall():
    inst_test_data = generate_test_data()
    dut = IsStage(init_data=inst_test_data)

    async def bench(ctx):
        stall_start_cyc = 10
        stall_end_cyc = 20
        flush_cyc = 15

        for i in range(config.L1_CACHE_DEPTH):
            is_stall = stall_start_cyc <= i < stall_end_cyc
            is_flush = i == flush_cyc
            addr = i * 4
            if is_stall:
                ctx.set(dut.input.ctrl.en, 0)
            else:
                ctx.set(dut.input.ctrl.en, 1)
            ctx.set(dut.input.addr, addr)
            ctx.set(dut.input.ctrl.debug.cyc, i)
            ctx.set(dut.input.ctrl.debug.seqno, i)
            if is_flush:
                ctx.set(dut.side_ctrl.clr, 1)
            else:
                ctx.set(dut.side_ctrl.clr, 0)

            await ctx.tick()
            if is_flush:
                assert ctx.get(dut.output.addr) == 0
                assert ctx.get(dut.output.inst) == 0
                assert ctx.get(dut.output.ctrl.en) == 0
            elif is_stall:
                # assert ctx.get(dut.output.addr) == 0 # Don't care
                # assert ctx.get(dut.output.inst) == 0 # Don't care
                assert ctx.get(dut.output.ctrl.en) == 0
            else:
                assert ctx.get(dut.output.addr) == addr
                assert ctx.get(dut.output.inst) == inst_test_data[i].value
                assert ctx.get(dut.output.ctrl.en) == 1
                assert ctx.get(dut.output.ctrl.debug.seqno) == i

    run_sim(f"{test_is_flush_when_stall.__name__}", dut=dut, testbench=bench)
