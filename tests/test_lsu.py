from typing import Generator, List
import pytest

from bonsai.lsu import SingleCycleMemory
from bonsai.format import MemoryOperationType
from tests.testutil import run_sim


def expect_data(seed: int = 0, depth: int = 128) -> List[int]:
    """
    Generate expected data
    """
    return list([(~(seed + i)) & 0xFFFFFFFF for i in range(depth)])


def test_ssm_read_seq():
    init_data = expect_data(seed=0x12345678)
    dut = SingleCycleMemory(init_data=init_data)

    async def bench(ctx):
        # disable
        ctx.set(dut.req_in.op_type, MemoryOperationType.NOP.value)
        ctx.set(dut.req_in.addr_in, 0)
        ctx.set(dut.req_in.data_in, 0)

        nop_cyc = 3
        for _ in range(nop_cyc):
            await ctx.tick()
            assert ctx.get(dut.req_in.busy) == 0

        # read incremental
        ctx.set(dut.req_in.op_type, MemoryOperationType.READ_CACHE.value)
        for data_idx, exp_data in enumerate(init_data):
            read_addr = data_idx * 4
            ctx.set(dut.req_in.addr_in, read_addr)
            await ctx.tick()
            assert ctx.get(dut.req_in.busy) == 0
            assert ctx.get(dut.req_in.data_out) == exp_data

    run_sim(f"{test_ssm_read_seq.__name__}", dut=dut, testbench=bench)


def test_ssm_read_random():
    init_data = expect_data(seed=0x12345678)
    dut = SingleCycleMemory(init_data=init_data)

    random_access_address_list = [0, 4, 16, 4, 32, 8, 128, 64, 120, 32, 64]

    async def bench(ctx):
        # disable
        ctx.set(dut.req_in.op_type, MemoryOperationType.NOP.value)
        ctx.set(dut.req_in.addr_in, 0)
        ctx.set(dut.req_in.data_in, 0)

        nop_cyc = 3
        for _ in range(nop_cyc):
            await ctx.tick()
            assert ctx.get(dut.req_in.busy) == 0

        # read random
        ctx.set(dut.req_in.op_type, MemoryOperationType.READ_CACHE.value)
        for read_addr in random_access_address_list:
            data_idx = read_addr // 4
            exp_data = init_data[data_idx]

            ctx.set(dut.req_in.addr_in, read_addr)
            await ctx.tick()
            assert ctx.get(dut.req_in.busy) == 0
            assert ctx.get(dut.req_in.data_out) == exp_data

    run_sim(f"{test_ssm_read_seq.__name__}", dut=dut, testbench=bench)
