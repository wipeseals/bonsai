from typing import List
import pytest

from bonsai.lsu import SingleCycleMemory
from bonsai.datatype import AbortType, LsuOperationType
from tests.util import run_sim


def expect_data(seed: int = 0, depth: int = 128) -> List[int]:
    """
    Generate expected data
    """
    return list([(seed + i) & 0xFFFFFFFF for i in range(depth)])


@pytest.mark.parametrize("is_primary", [True, False])
def test_ssm_read_seq(is_primary: bool):
    init_data = expect_data(seed=0x12345678)
    dut = SingleCycleMemory(init_data=init_data)
    active_req_in = dut.primary_req_in if is_primary else dut.secondary_req_in
    inactive_req_in = dut.secondary_req_in if is_primary else dut.primary_req_in

    async def bench(ctx):
        # disable
        ctx.set(active_req_in.op_type, LsuOperationType.NOP.value)
        ctx.set(active_req_in.bytemask, 0b1111)
        ctx.set(active_req_in.en, 0)
        ctx.set(active_req_in.addr_in, 0)
        ctx.set(active_req_in.data_in, 0)
        nop_cyc = 3
        for _ in range(nop_cyc):
            await ctx.tick()
            assert ctx.get(active_req_in.busy) == 0
            assert ctx.get(inactive_req_in.busy) == 0

        # read incremental
        ctx.set(active_req_in.op_type, LsuOperationType.READ_CACHE.value)
        ctx.set(active_req_in.en, 1)
        for data_idx, exp_data in enumerate(init_data):
            read_addr = data_idx * 4
            ctx.set(active_req_in.addr_in, read_addr)
            await ctx.tick()
            assert ctx.get(active_req_in.busy) == 0
            assert ctx.get(active_req_in.data_out) == exp_data
            assert ctx.get(inactive_req_in.busy) == 1

    run_sim(f"{test_ssm_read_seq.__name__}", dut=dut, testbench=bench)


@pytest.mark.parametrize("is_primary", [True, False])
def test_ssm_read_random(is_primary: bool):
    init_data = expect_data(seed=0x12345678)
    dut = SingleCycleMemory(init_data=init_data)
    active_req_in = dut.primary_req_in if is_primary else dut.secondary_req_in
    inactive_req_in = dut.secondary_req_in if is_primary else dut.primary_req_in

    random_access_address_list = [0, 4, 16, 4, 32, 8, 128, 64, 120, 32, 64]

    async def bench(ctx):
        # disable
        ctx.set(active_req_in.op_type, LsuOperationType.NOP.value)
        ctx.set(active_req_in.bytemask, 0b1111)
        ctx.set(active_req_in.en, 0)
        ctx.set(active_req_in.addr_in, 0)
        ctx.set(active_req_in.data_in, 0)
        nop_cyc = 3
        for _ in range(nop_cyc):
            await ctx.tick()
            assert ctx.get(active_req_in.busy) == 0
            assert ctx.get(inactive_req_in.busy) == 0

        # read random
        ctx.set(active_req_in.op_type, LsuOperationType.READ_CACHE.value)
        ctx.set(active_req_in.en, 1)
        for read_addr in random_access_address_list:
            data_idx = read_addr // 4
            exp_data = init_data[data_idx]

            ctx.set(active_req_in.addr_in, read_addr)
            await ctx.tick()
            assert ctx.get(active_req_in.busy) == 0
            assert ctx.get(active_req_in.data_out) == exp_data
            assert ctx.get(inactive_req_in.busy) == 1

    run_sim(f"{test_ssm_read_random.__name__}", dut=dut, testbench=bench)


@pytest.mark.parametrize("is_primary", [True, False])
def test_ssm_write_seq(is_primary: bool):
    init_data = expect_data(seed=0x0)
    dut = SingleCycleMemory(init_data=init_data)
    active_req_in = dut.primary_req_in if is_primary else dut.secondary_req_in
    inactive_req_in = dut.secondary_req_in if is_primary else dut.primary_req_in

    async def bench(ctx):
        # disable
        ctx.set(active_req_in.op_type, LsuOperationType.NOP.value)
        ctx.set(active_req_in.bytemask, 0b1111)
        ctx.set(active_req_in.en, 0)
        ctx.set(active_req_in.addr_in, 0)
        ctx.set(active_req_in.data_in, 0)
        nop_cyc = 3
        for _ in range(nop_cyc):
            await ctx.tick()
            assert ctx.get(active_req_in.busy) == 0
            assert ctx.get(inactive_req_in.busy) == 0

        # write incremental
        def process_data(data: int) -> int:
            return 0xFFFFFFFF - data

        ctx.set(active_req_in.op_type, LsuOperationType.WRITE_CACHE.value)
        ctx.set(active_req_in.en, 1)
        for data_idx, exp_data in enumerate(init_data):
            write_addr = data_idx * 4
            write_data = process_data(exp_data)
            ctx.set(active_req_in.addr_in, write_addr)
            ctx.set(active_req_in.data_in, write_data)
            await ctx.tick()
            assert ctx.get(active_req_in.busy) == 0
            # 設計上はRead portはcombなのでWrite data貫通して出てくる
            assert ctx.get(active_req_in.data_out) == write_data
            assert ctx.get(inactive_req_in.busy) == 1

        # read verify
        ctx.set(active_req_in.op_type, LsuOperationType.READ_CACHE.value)
        ctx.set(active_req_in.en, 1)
        for data_idx, exp_data in enumerate(init_data):
            read_addr = data_idx * 4
            ctx.set(active_req_in.addr_in, read_addr)
            await ctx.tick()
            assert ctx.get(active_req_in.busy) == 0
            assert ctx.get(inactive_req_in.busy) == 1

    run_sim(f"{test_ssm_write_seq.__name__}", dut=dut, testbench=bench)


@pytest.mark.parametrize("use_strict_assert", [True, False])
@pytest.mark.parametrize("is_primary", [True, False])
@pytest.mark.parametrize(
    "test_addr,bytemask",
    [
        # word access
        # (0x00000000, 0b0001),
        # (0x00000000, 0b0010),
        # (0x00000000, 0b0100),
        # (0x00000000, 0b1000),
        # 1byte offset
        # (0x00000001, 0b0001),
        # (0x00000001, 0b0010),
        # (0x00000001, 0b0100),
        (0x00000001, 0b1000),
        # 2byte offset
        # (0x00000002, 0b0001),
        # (0x00000002, 0b0010),
        (
            0x00000002,
            0b0100,
        ),
        (0x00000002, 0b1000),
        # 3byte offset
        # (0x00000003, 0b0001),
        (0x00000003, 0b0010),
        (0x00000003, 0b0100),
        (0x00000003, 0b1000),
    ],
)
def test_ssm_abort_misaligned(
    use_strict_assert: bool,
    is_primary: bool,
    test_addr: int,
    bytemask: int,
):
    init_data = expect_data(seed=0x12345678)
    dut = SingleCycleMemory(init_data=init_data, use_strict_assert=use_strict_assert)
    active_req_in = dut.primary_req_in if is_primary else dut.secondary_req_in
    inactive_req_in = dut.secondary_req_in if is_primary else dut.primary_req_in

    async def bench(ctx):
        # disable
        ctx.set(active_req_in.op_type, LsuOperationType.NOP.value)
        ctx.set(active_req_in.bytemask, 0b1111)
        ctx.set(active_req_in.en, 0)
        ctx.set(active_req_in.addr_in, 0)
        ctx.set(active_req_in.data_in, 0)
        nop_cyc = 3
        for _ in range(nop_cyc):
            await ctx.tick()
            assert ctx.get(active_req_in.busy) == 0
            assert ctx.get(inactive_req_in.busy) == 0

        # read misaligned
        ctx.set(active_req_in.op_type, LsuOperationType.READ_CACHE.value)
        ctx.set(active_req_in.en, 1)
        ctx.set(active_req_in.addr_in, test_addr)
        ctx.set(active_req_in.bytemask, bytemask)
        await ctx.tick()
        assert ctx.get(active_req_in.busy) == 1
        assert ctx.get(inactive_req_in.busy) == 1
        assert (
            ctx.get(active_req_in.abort_type) == AbortType.MISALIGNED_MEM_ACCESS.value
        )
        assert (
            ctx.get(inactive_req_in.abort_type) == AbortType.MISALIGNED_MEM_ACCESS.value
        )

        # read seq (aborted)
        read_addr = 0x00000004
        ctx.set(active_req_in.op_type, LsuOperationType.READ_CACHE.value)
        ctx.set(active_req_in.en, 1)
        ctx.set(active_req_in.addr_in, read_addr)
        ctx.set(active_req_in.bytemask, 0b1111)
        aborted_cyc = 3
        for _ in range(aborted_cyc):
            await ctx.tick()
            assert ctx.get(active_req_in.busy) == 1
            assert (
                ctx.get(active_req_in.abort_type)
                == AbortType.MISALIGNED_MEM_ACCESS.value
            )
            assert ctx.get(inactive_req_in.busy) == 1
            assert (
                ctx.get(inactive_req_in.abort_type)
                == AbortType.MISALIGNED_MEM_ACCESS.value
            )

        # abort clear
        read_addr = 0x00000004
        ctx.set(active_req_in.addr_in, read_addr)
        ctx.set(active_req_in.op_type, LsuOperationType.MANAGE_CLEAR_ABORT.value)
        ctx.set(active_req_in.en, 1)
        ctx.set(active_req_in.bytemask, 0b1111)
        await ctx.tick()
        assert ctx.get(active_req_in.busy) == 1
        assert ctx.get(inactive_req_in.busy) == 1

        # read
        ctx.set(active_req_in.op_type, LsuOperationType.READ_CACHE.value)
        ctx.set(active_req_in.en, 1)
        await ctx.tick()
        assert ctx.get(active_req_in.busy) == 0
        assert ctx.get(active_req_in.data_out) == init_data[1]
        assert ctx.get(inactive_req_in.busy) == 1

    if use_strict_assert:
        with pytest.raises(AssertionError) as excinfo:
            run_sim(
                f"{test_ssm_abort_misaligned.__name__}_assert", dut=dut, testbench=bench
            )
        assert "Misaligned Access" in str(excinfo.value)
    else:
        run_sim(
            f"{test_ssm_abort_misaligned.__name__}_noassert", dut=dut, testbench=bench
        )


def test_ssm_two_port_priority():
    init_data = expect_data(seed=0x12345678)
    dut = SingleCycleMemory(init_data=init_data)

    async def bench(ctx):
        # disable -> check idle
        ctx.set(dut.primary_req_in.op_type, LsuOperationType.NOP.value)
        ctx.set(dut.secondary_req_in.op_type, LsuOperationType.NOP.value)
        ctx.set(dut.primary_req_in.bytemask, 0b1111)
        ctx.set(dut.secondary_req_in.bytemask, 0b1111)
        ctx.set(dut.primary_req_in.en, 0)
        ctx.set(dut.secondary_req_in.en, 0)
        ctx.set(dut.primary_req_in.addr_in, 0)
        ctx.set(dut.secondary_req_in.addr_in, 0)
        ctx.set(dut.primary_req_in.data_in, 0)
        ctx.set(dut.secondary_req_in.data_in, 0)
        await ctx.tick()
        assert ctx.get(dut.primary_req_in.busy) == 0
        assert ctx.get(dut.secondary_req_in.busy) == 0

        # Primary: Write 0xaaaaaaaa (accept)
        # Secondary: Write 0xbbbbbbbb (reject)
        ctx.set(dut.primary_req_in.op_type, LsuOperationType.WRITE_CACHE.value)
        ctx.set(dut.secondary_req_in.op_type, LsuOperationType.WRITE_CACHE.value)
        ctx.set(dut.primary_req_in.en, 1)
        ctx.set(dut.secondary_req_in.en, 1)
        ctx.set(dut.primary_req_in.addr_in, 0)
        ctx.set(dut.secondary_req_in.addr_in, 0)
        ctx.set(dut.primary_req_in.data_in, 0xAAAAAAAA)
        ctx.set(dut.secondary_req_in.data_in, 0xBBBBBBBB)
        await ctx.tick()
        assert ctx.get(dut.primary_req_in.busy) == 0
        assert ctx.get(dut.secondary_req_in.busy) == 1

        # Primary: Write(en=0) (reject)
        # Secondary: Write 0xcccccccc (accept)
        ctx.set(dut.primary_req_in.op_type, LsuOperationType.WRITE_CACHE.value)
        ctx.set(dut.secondary_req_in.op_type, LsuOperationType.WRITE_CACHE.value)
        ctx.set(dut.primary_req_in.en, 0)  # disable
        ctx.set(dut.secondary_req_in.en, 1)
        ctx.set(dut.primary_req_in.addr_in, 4)
        ctx.set(dut.secondary_req_in.addr_in, 4)
        ctx.set(dut.primary_req_in.data_in, 0xCCCCCCCC)
        ctx.set(dut.secondary_req_in.data_in, 0xDDDDDDDD)
        await ctx.tick()
        assert ctx.get(dut.primary_req_in.busy) == 1
        assert ctx.get(dut.secondary_req_in.busy) == 0
        assert ctx.get(dut.secondary_req_in.data_out) == 0xDDDDDDDD

        # Primary: Read 0x00000000 (accept)
        # Secondary: Read 0x00000000 (reject)
        ctx.set(dut.primary_req_in.op_type, LsuOperationType.READ_CACHE.value)
        ctx.set(dut.secondary_req_in.op_type, LsuOperationType.READ_CACHE.value)
        ctx.set(dut.primary_req_in.en, 1)
        ctx.set(dut.secondary_req_in.en, 1)
        ctx.set(dut.primary_req_in.addr_in, 0)
        ctx.set(dut.secondary_req_in.addr_in, 0)
        await ctx.tick()
        assert ctx.get(dut.primary_req_in.busy) == 0
        assert ctx.get(dut.primary_req_in.data_out) == 0xAAAAAAAA
        assert ctx.get(dut.secondary_req_in.busy) == 1

        # Primary: NOP
        # Secondary: Read 0x00000000 (accept)
        ctx.set(dut.primary_req_in.op_type, LsuOperationType.NOP.value)
        ctx.set(dut.secondary_req_in.op_type, LsuOperationType.READ_CACHE.value)
        ctx.set(dut.primary_req_in.en, 1)
        ctx.set(dut.secondary_req_in.en, 1)
        ctx.set(dut.secondary_req_in.addr_in, 4)
        await ctx.tick()
        assert ctx.get(dut.primary_req_in.busy) == 1
        assert ctx.get(dut.secondary_req_in.busy) == 0
        assert ctx.get(dut.secondary_req_in.data_out) == 0xDDDDDDDD

    run_sim(f"{test_ssm_two_port_priority.__name__}", dut=dut, testbench=bench)
