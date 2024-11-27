from bonsai.stage import IfStage

from tests.testutil import run_sim


def test_if_flush():
    dut = IfStage()

    async def bench(ctx):
        # initial
        addr = 0xAA
        ctx.set(dut.input.ctrl.en, 1)
        ctx.set(dut.side_ctrl.clr, 0)
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

    run_sim(f"{test_if_flush.__name__}", dut=dut, testbench=bench)


def test_if_freerun():
    dut = IfStage()

    async def bench(ctx):
        # initial
        addr = 0xAA
        ctx.set(dut.input.ctrl.en, 1)
        ctx.set(dut.input.pc, addr)
        await ctx.tick()
        assert ctx.get(dut.output.addr) == addr
        assert ctx.get(dut.output.ctrl.en) == 1
        assert ctx.get(dut.output.ctrl.debug.seqno) == 0
        # freerun
        for i in range(16):
            prev_addr = addr
            addr = i * 4
            ctx.set(dut.input.ctrl.en, 1)
            ctx.set(dut.input.pc, addr)

            # check previous addr before clock rising
            assert ctx.get(dut.output.addr) == prev_addr
            # clock rising & check addr
            await ctx.tick()
            assert ctx.get(dut.output.addr) == addr
            assert ctx.get(dut.output.ctrl.en) == 1
            assert ctx.get(dut.output.ctrl.debug.seqno) == i + 1

    run_sim(f"{test_if_freerun.__name__}", dut=dut, testbench=bench)


def test_if_stall():
    dut = IfStage()

    async def bench(ctx):
        # initial
        old_addr = 0xAA
        ctx.set(dut.input.ctrl.en, 1)
        ctx.set(dut.input.pc, old_addr)
        await ctx.tick()
        assert ctx.get(dut.output.addr) == old_addr
        assert ctx.get(dut.output.ctrl.en) == 1
        # test stall
        new_addr = 0x55
        ctx.set(dut.input.ctrl.en, 0)
        ctx.set(dut.input.pc, new_addr)
        await ctx.tick()
        # stall中のアドレスはDon't care
        assert ctx.get(dut.output.ctrl.en) == 0
        # allow fetch
        new_addr = 0x55
        ctx.set(dut.input.ctrl.en, 1)
        ctx.set(dut.input.pc, new_addr)
        await ctx.tick()
        assert ctx.get(dut.output.addr) == new_addr
        assert ctx.get(dut.output.ctrl.en) == 1

    run_sim(f"{test_if_stall.__name__}", dut=dut, testbench=bench)


def test_if_flush():
    dut = IfStage()

    async def bench(ctx):
        # initial
        old_addr = 0xAA
        ctx.set(dut.input.ctrl.en, 1)
        ctx.set(dut.input.pc, old_addr)
        await ctx.tick()
        assert ctx.get(dut.output.addr) == old_addr
        assert ctx.get(dut.output.ctrl.en) == 1
        # test flush
        new_addr = 0x55
        ctx.set(dut.input.ctrl.en, 1)
        ctx.set(dut.side_ctrl.clr, 1)
        ctx.set(dut.input.pc, new_addr)
        await ctx.tick()
        assert ctx.get(dut.output.addr) == 0
        assert ctx.get(dut.output.ctrl.en) == 0
        # finish flush
        ctx.set(dut.input.ctrl.en, 1)
        ctx.set(dut.side_ctrl.clr, 0)
        ctx.set(dut.input.pc, new_addr)
        await ctx.tick()
        assert ctx.get(dut.output.addr) == new_addr
        assert ctx.get(dut.output.ctrl.en) == 1

    run_sim(f"{test_if_flush.__name__}", dut=dut, testbench=bench)


def test_if_flush_when_stall():
    dut = IfStage()

    async def bench(ctx):
        # initial
        old_addr = 0xAA
        ctx.set(dut.input.ctrl.en, 1)
        ctx.set(dut.input.pc, old_addr)
        await ctx.tick()
        assert ctx.get(dut.output.addr) == old_addr
        assert ctx.get(dut.output.ctrl.en) == 1

        # test stall
        new_addr = 0x55
        ctx.set(dut.input.ctrl.en, 0)
        ctx.set(dut.input.pc, new_addr)
        await ctx.tick()
        # stall中のアドレスはDon't care
        assert ctx.get(dut.output.ctrl.en) == 0

        # test flush
        new_addr = 0x55
        ctx.set(dut.input.ctrl.en, 0)
        ctx.set(dut.side_ctrl.clr, 1)
        ctx.set(dut.input.pc, new_addr)
        await ctx.tick()
        assert ctx.get(dut.output.addr) == 0
        assert ctx.get(dut.output.ctrl.en) == 0

        # finish flush
        ctx.set(dut.input.ctrl.en, 1)
        ctx.set(dut.side_ctrl.clr, 0)
        ctx.set(dut.input.pc, new_addr)
        await ctx.tick()
        assert ctx.get(dut.output.addr) == new_addr
        assert ctx.get(dut.output.ctrl.en) == 1

    run_sim(f"{test_if_flush_when_stall.__name__}", dut=dut, testbench=bench)
