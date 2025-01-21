from bonsai.pipeline_stage import InstSelectStage

from tests.testutil import run_sim

INITIAL_PC: int = 0x1000
INITIAL_UNIQ_ID: int = 0x1234
LANE_ID: int = 0


def test_is_increment():
    dut = InstSelectStage(
        initial_pc=INITIAL_PC,
        initial_uniq_id=INITIAL_UNIQ_ID,
        lane_id=LANE_ID,
    )

    async def bench(ctx):
        # enable & no flush/stall
        ctx.set(dut.prev_req.en, 1)
        ctx.set(dut.prev_req.ctrl.stall, 0)
        ctx.set(dut.prev_req.ctrl.flush, 0)
        # no branch
        ctx.set(dut.prev_req.branch_req.en, 0)
        ctx.set(dut.prev_req.branch_req.next_pc, 0)
        # 4byte inst
        ctx.set(dut.prev_req.num_inst_bytes, 4)

        for cyc in range(30):
            await ctx.tick()
            # check enable
            assert ctx.get(dut.next_req.en) == 1
            assert ctx.get(dut.next_req.ctrl.stall) == 0
            assert ctx.get(dut.next_req.ctrl.flush) == 0
            # check pc
            assert ctx.get(dut.next_req.locate.pc) == INITIAL_PC + 4 * cyc
            assert ctx.get(dut.next_req.locate.uniq_id) == INITIAL_UNIQ_ID + cyc
            assert ctx.get(dut.next_req.locate.num_inst_bytes) == 4

    run_sim(f"{test_is_increment.__name__}", dut=dut, testbench=bench)
