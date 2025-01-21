from bonsai.pipeline_stage import InstSelectStage

from tests.testutil import run_sim
import pytest

INITIAL_PC: int = 0x1000
INITIAL_UNIQ_ID: int = 1000
LANE_ID: int = 0


@pytest.mark.parametrize("num_inst_bytes", [2, 4, 8])
def test_is_increment(num_inst_bytes: int, test_cycles: int = 30):
    dut = InstSelectStage(
        initial_pc=INITIAL_PC,
        initial_uniq_id=INITIAL_UNIQ_ID,
        lane_id=LANE_ID,
    )

    async def bench(ctx):
        # enable & no flush/stall
        ctx.set(dut.prev_req.en, 1)
        ctx.set(dut.ctrl_req.stall, 0)
        ctx.set(dut.ctrl_req.flush, 0)
        # no branch
        ctx.set(dut.prev_req.branch_req.en, 0)
        ctx.set(dut.prev_req.branch_req.next_pc, 0)
        # set num_inst_bytes
        ctx.set(dut.prev_req.num_inst_bytes, num_inst_bytes)

        for cyc in range(test_cycles):
            await ctx.tick()
            # check enable
            assert ctx.get(dut.next_req.en) == 1
            # check pc
            assert ctx.get(dut.next_req.locate.pc) == INITIAL_PC + num_inst_bytes * cyc
            assert ctx.get(dut.next_req.locate.uniq_id) == INITIAL_UNIQ_ID + cyc
            assert ctx.get(dut.next_req.locate.num_inst_bytes) == num_inst_bytes

    run_sim(f"{test_is_increment.__name__}_{num_inst_bytes}", dut=dut, testbench=bench)


@pytest.mark.parametrize("stall_cyc", [1, 3, 5])
def test_is_stall(stall_cyc: int, num_inst_bytes: int = 4):
    dut = InstSelectStage(
        initial_pc=INITIAL_PC,
        initial_uniq_id=INITIAL_UNIQ_ID,
        lane_id=LANE_ID,
    )

    async def bench(ctx):
        # enable & no flush/stall
        ctx.set(dut.prev_req.en, 1)
        ctx.set(dut.ctrl_req.stall, 0)
        ctx.set(dut.ctrl_req.flush, 0)
        # no branch
        ctx.set(dut.prev_req.branch_req.en, 0)
        ctx.set(dut.prev_req.branch_req.next_pc, 0)
        # set num_inst_bytes
        ctx.set(dut.prev_req.num_inst_bytes, num_inst_bytes)

        pre_cyc = 3
        for cyc in range(pre_cyc):
            await ctx.tick()
            # check enable
            assert ctx.get(dut.next_req.en) == 1
            # check pc
            assert ctx.get(dut.next_req.locate.pc) == INITIAL_PC + num_inst_bytes * cyc
            assert ctx.get(dut.next_req.locate.uniq_id) == INITIAL_UNIQ_ID + cyc
            assert ctx.get(dut.next_req.locate.num_inst_bytes) == num_inst_bytes

        # stall
        ctx.set(dut.ctrl_req.stall, 1)
        for cyc in range(stall_cyc):
            await ctx.tick()
            # check enable
            assert ctx.get(dut.next_req.en) == 0

        # release stall
        ctx.set(dut.ctrl_req.stall, 0)

        post_cyc = 3
        for cyc in range(post_cyc):
            await ctx.tick()
            # check enable
            assert ctx.get(dut.next_req.en) == 1
            # check pc
            assert ctx.get(dut.next_req.locate.pc) == INITIAL_PC + num_inst_bytes * (
                pre_cyc + cyc
            )
            assert (
                ctx.get(dut.next_req.locate.uniq_id) == INITIAL_UNIQ_ID + pre_cyc + cyc
            )
            assert ctx.get(dut.next_req.locate.num_inst_bytes) == num_inst_bytes

    run_sim(f"{test_is_stall.__name__}", dut=dut, testbench=bench)


def test_is_flush(num_inst_bytes: int = 4):
    dut = InstSelectStage(
        initial_pc=INITIAL_PC,
        initial_uniq_id=INITIAL_UNIQ_ID,
        lane_id=LANE_ID,
    )

    async def bench(ctx):
        # enable & no flush/stall
        ctx.set(dut.prev_req.en, 1)
        ctx.set(dut.ctrl_req.stall, 0)
        ctx.set(dut.ctrl_req.flush, 0)
        # no branch
        ctx.set(dut.prev_req.branch_req.en, 0)
        ctx.set(dut.prev_req.branch_req.next_pc, 0)
        # set num_inst_bytes
        ctx.set(dut.prev_req.num_inst_bytes, num_inst_bytes)

        pre_cyc = 3
        for cyc in range(pre_cyc):
            await ctx.tick()
            # check enable
            assert ctx.get(dut.next_req.en) == 1
            # check pc
            assert ctx.get(dut.next_req.locate.pc) == INITIAL_PC + num_inst_bytes * cyc
            assert ctx.get(dut.next_req.locate.uniq_id) == INITIAL_UNIQ_ID + cyc
            assert ctx.get(dut.next_req.locate.num_inst_bytes) == num_inst_bytes

        # flush
        ctx.set(dut.ctrl_req.flush, 1)
        await ctx.tick()
        # check enable
        assert ctx.get(dut.next_req.en) == 0

        ctx.set(dut.ctrl_req.flush, 0)
        post_cyc = 3
        for cyc in range(post_cyc):
            await ctx.tick()
            # check enable
            assert ctx.get(dut.next_req.en) == 1
            # check pc (keep pc/uniq_id)
            assert ctx.get(dut.next_req.locate.pc) == INITIAL_PC + num_inst_bytes * (
                cyc + pre_cyc
            )
            assert (
                ctx.get(dut.next_req.locate.uniq_id) == INITIAL_UNIQ_ID + cyc + pre_cyc
            )
            assert ctx.get(dut.next_req.locate.num_inst_bytes) == num_inst_bytes

    run_sim(f"{test_is_flush.__name__}", dut=dut, testbench=bench)


@pytest.mark.parametrize("num_inst_bytes", [2, 4, 8])
def test_is_branch_target(num_inst_bytes: int):
    dut = InstSelectStage(
        initial_pc=INITIAL_PC,
        initial_uniq_id=INITIAL_UNIQ_ID,
        lane_id=LANE_ID,
    )

    async def bench(ctx):
        # enable & no flush/stall
        ctx.set(dut.prev_req.en, 1)
        ctx.set(dut.ctrl_req.stall, 0)
        ctx.set(dut.ctrl_req.flush, 0)
        # no branch
        ctx.set(dut.prev_req.branch_req.en, 0)
        ctx.set(dut.prev_req.branch_req.next_pc, 0)
        # set num_inst_bytes
        ctx.set(dut.prev_req.num_inst_bytes, num_inst_bytes)

        pre_cyc = 3
        for cyc in range(pre_cyc):
            await ctx.tick()
            # check enable
            assert ctx.get(dut.next_req.en) == 1
            # check pc
            assert ctx.get(dut.next_req.locate.pc) == INITIAL_PC + num_inst_bytes * cyc
            assert ctx.get(dut.next_req.locate.uniq_id) == INITIAL_UNIQ_ID + cyc
            assert ctx.get(dut.next_req.locate.num_inst_bytes) == num_inst_bytes

        # branch
        branch_pc = 0x2000
        ctx.set(dut.prev_req.branch_req.en, 1)
        ctx.set(dut.prev_req.branch_req.next_pc, branch_pc)
        await ctx.tick()
        # check enable
        # note: 後段stageのflushはbranch入力時に並行してフィードバックかける想定
        assert ctx.get(dut.next_req.en) == 1
        # check pc
        assert ctx.get(dut.next_req.locate.pc) == branch_pc
        assert ctx.get(dut.next_req.locate.uniq_id) == INITIAL_UNIQ_ID + pre_cyc

        # increment
        ctx.set(dut.prev_req.branch_req.en, 0)
        post_cyc = 3
        for cyc in range(post_cyc):
            await ctx.tick()
            # check enable
            assert ctx.get(dut.next_req.en) == 1
            # check pc
            assert ctx.get(dut.next_req.locate.pc) == branch_pc + num_inst_bytes * (
                cyc + 1
            )  # branch + post_cyc
            assert (
                ctx.get(dut.next_req.locate.uniq_id)
                == INITIAL_UNIQ_ID + pre_cyc + 1 + cyc  # pre_cyc + branch + post_cyc
            )
            assert ctx.get(dut.next_req.locate.num_inst_bytes) == num_inst_bytes

    run_sim(
        f"{test_is_branch_target.__name__}_{num_inst_bytes}", dut=dut, testbench=bench
    )
