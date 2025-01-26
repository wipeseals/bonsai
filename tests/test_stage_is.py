from bonsai import config
from bonsai.format import AbortType
from bonsai.stage import InstSelectStage

from tests.testutil import run_sim
import pytest

INITIAL_PC: int = 0x1000
INITIAL_UNIQ_ID: int = 1000
LANE_ID: int = 0


def test_is_increment(test_cycles: int = 30):
    dut = InstSelectStage(
        initial_pc=INITIAL_PC,
        initial_uniq_id=INITIAL_UNIQ_ID,
        lane_id=LANE_ID,
    )

    async def bench(ctx):
        # enable & no flush/stall
        ctx.set(dut.req_in.en, 1)
        ctx.set(dut.ctrl_req_in.stall, 0)
        ctx.set(dut.ctrl_req_in.flush, 0)
        # no branch
        ctx.set(dut.req_in.branch_req.en, 0)
        ctx.set(dut.req_in.branch_req.next_pc, 0)

        for cyc in range(test_cycles):
            await ctx.tick()
            # check enable
            assert ctx.get(dut.req_out.en) == 1
            # check pc
            assert (
                ctx.get(dut.req_out.locate.pc)
                == INITIAL_PC + config.NUM_INST_BYTE * cyc
            )
            assert ctx.get(dut.req_out.locate.uniq_id) == INITIAL_UNIQ_ID + cyc
            # check branch
            assert ctx.get(dut.branch_strobe) == 0

    run_sim(f"{test_is_increment.__name__}", dut=dut, testbench=bench)


@pytest.mark.parametrize("stall_cyc", [1, 3, 5])
def test_is_stall(stall_cyc: int):
    dut = InstSelectStage(
        initial_pc=INITIAL_PC,
        initial_uniq_id=INITIAL_UNIQ_ID,
        lane_id=LANE_ID,
    )

    async def bench(ctx):
        # enable & no flush/stall
        ctx.set(dut.req_in.en, 1)
        ctx.set(dut.ctrl_req_in.stall, 0)
        ctx.set(dut.ctrl_req_in.flush, 0)
        # no branch
        ctx.set(dut.req_in.branch_req.en, 0)
        ctx.set(dut.req_in.branch_req.next_pc, 0)

        pre_cyc = 3
        for cyc in range(pre_cyc):
            await ctx.tick()
            # check enable
            assert ctx.get(dut.req_out.en) == 1
            # check pc
            assert (
                ctx.get(dut.req_out.locate.pc)
                == INITIAL_PC + config.NUM_INST_BYTE * cyc
            )
            assert ctx.get(dut.req_out.locate.uniq_id) == INITIAL_UNIQ_ID + cyc

        # stall
        ctx.set(dut.ctrl_req_in.stall, 1)
        for cyc in range(stall_cyc):
            await ctx.tick()
            # check enable
            assert ctx.get(dut.req_out.en) == 0

        # release stall
        ctx.set(dut.ctrl_req_in.stall, 0)

        post_cyc = 3
        for cyc in range(post_cyc):
            await ctx.tick()
            # check enable
            assert ctx.get(dut.req_out.en) == 1
            # check pc
            assert ctx.get(
                dut.req_out.locate.pc
            ) == INITIAL_PC + config.NUM_INST_BYTE * (pre_cyc + cyc)
            assert (
                ctx.get(dut.req_out.locate.uniq_id) == INITIAL_UNIQ_ID + pre_cyc + cyc
            )

            # check branch
            assert ctx.get(dut.branch_strobe) == 0

    run_sim(f"{test_is_stall.__name__}", dut=dut, testbench=bench)


def test_is_flush():
    dut = InstSelectStage(
        initial_pc=INITIAL_PC,
        initial_uniq_id=INITIAL_UNIQ_ID,
        lane_id=LANE_ID,
    )

    async def bench(ctx):
        # enable & no flush/stall
        ctx.set(dut.req_in.en, 1)
        ctx.set(dut.ctrl_req_in.stall, 0)
        ctx.set(dut.ctrl_req_in.flush, 0)
        # no branch
        ctx.set(dut.req_in.branch_req.en, 0)
        ctx.set(dut.req_in.branch_req.next_pc, 0)

        pre_cyc = 3
        for cyc in range(pre_cyc):
            await ctx.tick()
            # check enable
            assert ctx.get(dut.req_out.en) == 1
            # check pc
            assert (
                ctx.get(dut.req_out.locate.pc)
                == INITIAL_PC + config.NUM_INST_BYTE * cyc
            )
            assert ctx.get(dut.req_out.locate.uniq_id) == INITIAL_UNIQ_ID + cyc

            # check branch
            assert ctx.get(dut.branch_strobe) == 0

        # flush
        ctx.set(dut.ctrl_req_in.flush, 1)
        await ctx.tick()
        # check enable
        assert ctx.get(dut.req_out.en) == 0

        ctx.set(dut.ctrl_req_in.flush, 0)
        post_cyc = 3
        for cyc in range(post_cyc):
            await ctx.tick()
            # check enable
            assert ctx.get(dut.req_out.en) == 1
            # check pc (keep pc/uniq_id)
            assert ctx.get(
                dut.req_out.locate.pc
            ) == INITIAL_PC + config.NUM_INST_BYTE * (cyc + pre_cyc)
            assert (
                ctx.get(dut.req_out.locate.uniq_id) == INITIAL_UNIQ_ID + cyc + pre_cyc
            )

            # check branch
            assert ctx.get(dut.branch_strobe) == 0

    run_sim(f"{test_is_flush.__name__}", dut=dut, testbench=bench)


def test_is_branch_valid():
    dut = InstSelectStage(
        initial_pc=INITIAL_PC,
        initial_uniq_id=INITIAL_UNIQ_ID,
        lane_id=LANE_ID,
    )

    async def bench(ctx):
        # enable & no flush/stall
        ctx.set(dut.req_in.en, 1)
        ctx.set(dut.ctrl_req_in.stall, 0)
        ctx.set(dut.ctrl_req_in.flush, 0)
        # no branch
        ctx.set(dut.req_in.branch_req.en, 0)
        ctx.set(dut.req_in.branch_req.next_pc, 0)

        pre_cyc = 3
        for cyc in range(pre_cyc):
            await ctx.tick()
            # check enable
            assert ctx.get(dut.req_out.en) == 1
            # check pc
            assert (
                ctx.get(dut.req_out.locate.pc)
                == INITIAL_PC + config.NUM_INST_BYTE * cyc
            )
            assert ctx.get(dut.req_out.locate.uniq_id) == INITIAL_UNIQ_ID + cyc

        # branch
        branch_pc = 0x2000
        ctx.set(dut.req_in.branch_req.en, 1)
        ctx.set(dut.req_in.branch_req.next_pc, branch_pc)
        await ctx.tick()
        # check enable
        # note: 後段stageのflushはbranch入力時に並行してフィードバックかける想定
        assert ctx.get(dut.req_out.en) == 1
        # check pc
        assert ctx.get(dut.req_out.locate.pc) == branch_pc
        assert ctx.get(dut.req_out.locate.uniq_id) == INITIAL_UNIQ_ID + pre_cyc
        # check branch
        assert ctx.get(dut.branch_strobe) == 1
        assert (
            ctx.get(dut.branch_strobe_src_addr)
            == INITIAL_PC + config.NUM_INST_BYTE * pre_cyc
        )
        assert ctx.get(dut.branch_strobe_dst_addr) == branch_pc

        # increment
        ctx.set(dut.req_in.branch_req.en, 0)
        post_cyc = 3
        for cyc in range(post_cyc):
            await ctx.tick()
            # check enable
            assert ctx.get(dut.req_out.en) == 1
            # check pc
            assert ctx.get(
                dut.req_out.locate.pc
            ) == branch_pc + config.NUM_INST_BYTE * (cyc + 1)  # branch + post_cyc
            assert (
                ctx.get(dut.req_out.locate.uniq_id)
                == INITIAL_UNIQ_ID + pre_cyc + 1 + cyc  # pre_cyc + branch + post_cyc
            )

            # check branch
            assert ctx.get(dut.branch_strobe) == 0

    run_sim(f"{test_is_branch_valid.__name__}", dut=dut, testbench=bench)


def test_is_branch_misalign_assert():
    dut = InstSelectStage(
        initial_pc=INITIAL_PC,
        initial_uniq_id=INITIAL_UNIQ_ID,
        lane_id=LANE_ID,
    )

    async def bench(ctx):
        # enable & no flush/stall
        ctx.set(dut.req_in.en, 1)
        ctx.set(dut.ctrl_req_in.stall, 0)
        ctx.set(dut.ctrl_req_in.flush, 0)
        # no branch
        ctx.set(dut.req_in.branch_req.en, 0)
        ctx.set(dut.req_in.branch_req.next_pc, 0)

        pre_cyc = 3
        for cyc in range(pre_cyc):
            await ctx.tick()
            # check enable
            assert ctx.get(dut.req_out.en) == 1
            # check pc
            assert (
                ctx.get(dut.req_out.locate.pc)
                == INITIAL_PC + config.NUM_INST_BYTE * cyc
            )
            assert ctx.get(dut.req_out.locate.uniq_id) == INITIAL_UNIQ_ID + cyc

        # branch
        branch_pc = 0x2001  # misaligned
        ctx.set(dut.req_in.branch_req.en, 1)
        ctx.set(dut.req_in.branch_req.next_pc, branch_pc)
        await ctx.tick()

        # check enable
        assert ctx.get(dut.req_out.en) == 0
        # check abort
        assert ctx.get(dut.abort_type) == AbortType.MISALIGNED_FETCH

    with pytest.raises(AssertionError) as excinfo:
        run_sim(f"{test_is_branch_misalign.__name__}", dut=dut, testbench=bench)
    assert "Misaligned Access" in str(excinfo.value)
