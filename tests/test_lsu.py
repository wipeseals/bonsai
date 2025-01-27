from typing import Generator, List
import pytest

from bonsai.lsu import SingleCycleMemory
from bonsai.datatype import AbortType, LsuOperationType
from tests.testutil import run_sim


def expect_data(seed: int = 0, depth: int = 128) -> List[int]:
    """
    Generate expected data
    """
    return list([(seed + i) & 0xFFFFFFFF for i in range(depth)])


def test_ssm_read_seq():
    init_data = expect_data(seed=0x12345678)
    dut = SingleCycleMemory(init_data=init_data)

    async def bench(ctx):
        # disable
        ctx.set(dut.primary_req_in.op_type, LsuOperationType.NOP.value)
        ctx.set(dut.primary_req_in.addr_in, 0)
        ctx.set(dut.primary_req_in.data_in, 0)

        nop_cyc = 3
        for _ in range(nop_cyc):
            await ctx.tick()
            assert ctx.get(dut.primary_req_in.busy) == 0

        # read incremental
        ctx.set(dut.primary_req_in.op_type, LsuOperationType.READ_CACHE.value)
        for data_idx, exp_data in enumerate(init_data):
            read_addr = data_idx * 4
            ctx.set(dut.primary_req_in.addr_in, read_addr)
            await ctx.tick()
            assert ctx.get(dut.primary_req_in.busy) == 0
            assert ctx.get(dut.primary_req_in.data_out) == exp_data

    run_sim(f"{test_ssm_read_seq.__name__}", dut=dut, testbench=bench)


def test_ssm_read_random():
    init_data = expect_data(seed=0x12345678)
    dut = SingleCycleMemory(init_data=init_data)

    random_access_address_list = [0, 4, 16, 4, 32, 8, 128, 64, 120, 32, 64]

    async def bench(ctx):
        # disable
        ctx.set(dut.primary_req_in.op_type, LsuOperationType.NOP.value)
        ctx.set(dut.primary_req_in.addr_in, 0)
        ctx.set(dut.primary_req_in.data_in, 0)

        nop_cyc = 3
        for _ in range(nop_cyc):
            await ctx.tick()
            assert ctx.get(dut.primary_req_in.busy) == 0

        # read random
        ctx.set(dut.primary_req_in.op_type, LsuOperationType.READ_CACHE.value)
        for read_addr in random_access_address_list:
            data_idx = read_addr // 4
            exp_data = init_data[data_idx]

            ctx.set(dut.primary_req_in.addr_in, read_addr)
            await ctx.tick()
            assert ctx.get(dut.primary_req_in.busy) == 0
            assert ctx.get(dut.primary_req_in.data_out) == exp_data

    run_sim(f"{test_ssm_read_seq.__name__}", dut=dut, testbench=bench)


def test_ssm_write_seq():
    init_data = expect_data(seed=0x0)
    dut = SingleCycleMemory(init_data=init_data)

    async def bench(ctx):
        # disable
        ctx.set(dut.primary_req_in.op_type, LsuOperationType.NOP.value)
        ctx.set(dut.primary_req_in.addr_in, 0)
        ctx.set(dut.primary_req_in.data_in, 0)

        nop_cyc = 3
        for _ in range(nop_cyc):
            await ctx.tick()
            assert ctx.get(dut.primary_req_in.busy) == 0

        # write incremental
        def process_data(data: int) -> int:
            return 0xFFFFFFFF - data

        ctx.set(dut.primary_req_in.op_type, LsuOperationType.WRITE_CACHE.value)
        for data_idx, exp_data in enumerate(init_data):
            write_addr = data_idx * 4
            write_data = process_data(exp_data)
            ctx.set(dut.primary_req_in.addr_in, write_addr)
            ctx.set(dut.primary_req_in.data_in, write_data)
            await ctx.tick()
            assert ctx.get(dut.primary_req_in.busy) == 0
            # 設計上はRead portはcombなのでWrite data貫通して出てくる
            assert ctx.get(dut.primary_req_in.data_out) == write_data

        # read verify
        ctx.set(dut.primary_req_in.op_type, LsuOperationType.READ_CACHE.value)
        for data_idx, exp_data in enumerate(init_data):
            read_addr = data_idx * 4
            ctx.set(dut.primary_req_in.addr_in, read_addr)
            await ctx.tick()
            assert ctx.get(dut.primary_req_in.busy) == 0
            # assert ctx.get(dut.req_in.data_out) == process_data(exp_data)

    run_sim(f"{test_ssm_write_seq.__name__}", dut=dut, testbench=bench)


@pytest.mark.parametrize("use_strict_assert", [True, False])
def test_ssm_abort_misaligned(use_strict_assert: bool):
    init_data = expect_data(seed=0x12345678)
    dut = SingleCycleMemory(init_data=init_data, use_strict_assert=use_strict_assert)

    async def bench(ctx):
        # disable
        ctx.set(dut.primary_req_in.op_type, LsuOperationType.NOP.value)
        ctx.set(dut.primary_req_in.addr_in, 0)
        ctx.set(dut.primary_req_in.data_in, 0)

        nop_cyc = 3
        for _ in range(nop_cyc):
            await ctx.tick()
            assert ctx.get(dut.primary_req_in.busy) == 0

        # read misaligned
        read_addr = 0xFFFFFFF1
        ctx.set(dut.primary_req_in.op_type, LsuOperationType.READ_CACHE.value)
        ctx.set(dut.primary_req_in.addr_in, read_addr)
        await ctx.tick()
        assert ctx.get(dut.primary_req_in.busy) == 1
        assert (
            ctx.get(dut.primary_req_in.abort_type)
            == AbortType.MISALIGNED_MEM_ACCESS.value
        )

        # read seq (aborted)
        read_addr = 0x00000004
        ctx.set(dut.primary_req_in.op_type, LsuOperationType.READ_CACHE.value)
        ctx.set(dut.primary_req_in.addr_in, read_addr)

        aborted_cyc = 3
        for _ in range(aborted_cyc):
            await ctx.tick()
            assert ctx.get(dut.primary_req_in.busy) == 1
            assert (
                ctx.get(dut.primary_req_in.abort_type)
                == AbortType.MISALIGNED_MEM_ACCESS.value
            )

        # abort clear
        read_addr = 0x00000004
        ctx.set(dut.primary_req_in.addr_in, read_addr)
        ctx.set(dut.primary_req_in.op_type, LsuOperationType.MANAGE_CLEAR_ABORT.value)
        await ctx.tick()
        assert ctx.get(dut.primary_req_in.busy) == 1

        # read
        ctx.set(dut.primary_req_in.op_type, LsuOperationType.READ_CACHE.value)
        await ctx.tick()
        assert ctx.get(dut.primary_req_in.busy) == 0
        assert ctx.get(dut.primary_req_in.data_out) == init_data[1]

    if use_strict_assert:
        with pytest.raises(AssertionError) as excinfo:
            run_sim(f"{test_ssm_read_seq.__name__}_assert", dut=dut, testbench=bench)
        assert "Misaligned Access" in str(excinfo.value)
    else:
        run_sim(f"{test_ssm_read_seq.__name__}_noassert", dut=dut, testbench=bench)
