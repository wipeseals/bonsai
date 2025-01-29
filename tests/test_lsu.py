from typing import List
import pytest

from bonsai.lsu import SingleCycleMemory
from bonsai.datatype import AbortType, LsuOperationType
from tests.util import run_sim


def expect_data(seed: int = 0, step: int = 1, depth: int = 128) -> List[int]:
    """
    Generate expected data
    """
    return list([((seed + i) * step) & 0xFFFFFFFF for i in range(depth)])


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


@pytest.mark.parametrize("is_primary", [True, False])
@pytest.mark.parametrize(
    "addr_in,bytemask_wr,data_in,bytemask_rd,data_out_expect",
    [
        # Write w/ bytemask, aligned
        (
            0x00000000,
            0b1111,
            0xFE_DC_BA_98,
            0b1111,
            0xFE_DC_BA_98,
        ),
        (
            0x00000000,
            0b0111,
            0xFE_DC_BA_98,
            0b1111,
            0x00_DC_BA_98,
        ),
        (
            0x00000000,
            0b0101,
            0xFE_DC_BA_98,
            0b1111,
            0x00_DC_00_98,
        ),
        (
            0x00000000,
            0b0001,
            0xFE_DC_BA_98,
            0b1111,
            0x00_00_00_98,
        ),
        # Write w/ bytemask, unaligned
        (
            0x00000001,
            0b0101,
            0xFE_DC_BA_98,
            0b0111,
            0x00_DC_00_98,
        ),
        (
            0x00000002,
            0b0010,
            0xFE_DC_BA_98,
            0b0011,
            0x00_00_BA_00,
        ),
        (
            0x00000003,
            0b0001,
            0xFE_DC_BA_98,
            0b0001,
            0x00_00_00_98,
        ),
        # Read w/ bytemask, aligned
        (
            0x00000000,
            0b1111,
            0xFE_DC_BA_98,
            0b1111,
            0xFE_DC_BA_98,
        ),
        (
            0x00000000,
            0b1111,
            0xFE_DC_BA_98,
            0b0111,
            0x00_DC_BA_98,
        ),
        (
            0x00000000,
            0b1111,
            0xFE_DC_BA_98,
            0b0101,
            0x00_DC_00_98,
        ),
        (
            0x00000000,
            0b1111,
            0xFE_DC_BA_98,
            0b0001,
            0x00_00_00_98,
        ),
        # Read w/ bytemask, unaligned
        (
            0x00000001,
            0b0111,
            0xFE_DC_BA_98,
            0b0101,
            0x00_DC_00_98,
        ),
        (
            0x00000002,
            0b0011,
            0xFE_DC_BA_98,
            0b0010,
            0x00_00_BA_00,
        ),
        (
            0x00000003,
            0b0001,
            0xFE_DC_BA_98,
            0b0001,
            0x00_00_00_98,
        ),
    ],
)
def test_ssm_write_read_with_bytemask(
    is_primary: bool,
    addr_in: int,
    bytemask_wr: int,
    data_in: int,
    bytemask_rd: int,
    data_out_expect: int,
):
    init_data = expect_data(seed=0x0, step=0)  # All Zero
    dut = SingleCycleMemory(init_data=init_data, use_strict_assert=True)
    active_req_in = dut.primary_req_in if is_primary else dut.secondary_req_in
    inactive_req_in = dut.secondary_req_in if is_primary else dut.primary_req_in

    async def bench(ctx):
        # disable
        ctx.set(active_req_in.op_type, LsuOperationType.NOP.value)
        ctx.set(active_req_in.bytemask, 0b1111)
        ctx.set(active_req_in.en, 0)
        ctx.set(active_req_in.addr_in, 0)
        ctx.set(active_req_in.data_in, 0)
        nop_cyc = 1
        for _ in range(nop_cyc):
            await ctx.tick()
            assert ctx.get(active_req_in.busy) == 0
            assert ctx.get(inactive_req_in.busy) == 0

        # write w/ bytemask
        ctx.set(active_req_in.op_type, LsuOperationType.WRITE_CACHE.value)
        ctx.set(active_req_in.en, 1)
        ctx.set(active_req_in.addr_in, addr_in)
        ctx.set(active_req_in.bytemask, bytemask_wr)
        ctx.set(active_req_in.data_in, data_in)
        await ctx.tick()
        assert ctx.get(active_req_in.busy) == 0
        assert ctx.get(inactive_req_in.busy) == 1

        # read verify w/ bytemask
        ctx.set(active_req_in.op_type, LsuOperationType.READ_CACHE.value)
        ctx.set(active_req_in.en, 1)
        ctx.set(active_req_in.bytemask, bytemask_rd)
        await ctx.tick()
        assert ctx.get(active_req_in.busy) == 0
        assert ctx.get(active_req_in.data_out) == data_out_expect
        assert ctx.get(inactive_req_in.busy) == 1

    run_sim(f"{test_ssm_write_read_with_bytemask.__name__}", dut=dut, testbench=bench)


@pytest.mark.parametrize("is_primary", [True, False])
def test_ssm_write_bytemask(
    is_primary: bool,
):
    init_data = expect_data(seed=0x0, step=0)  # All Zero
    dut = SingleCycleMemory(init_data=init_data, use_strict_assert=True)
    active_req_in = dut.primary_req_in if is_primary else dut.secondary_req_in
    inactive_req_in = dut.secondary_req_in if is_primary else dut.primary_req_in

    async def bench(ctx):
        # disable
        ctx.set(active_req_in.op_type, LsuOperationType.NOP.value)
        ctx.set(active_req_in.bytemask, 0b1111)
        ctx.set(active_req_in.en, 0)
        ctx.set(active_req_in.addr_in, 0)
        ctx.set(active_req_in.data_in, 0)
        nop_cyc = 1
        for _ in range(nop_cyc):
            await ctx.tick()
            assert ctx.get(active_req_in.busy) == 0
            assert ctx.get(inactive_req_in.busy) == 0

        # read word
        ctx.set(active_req_in.op_type, LsuOperationType.READ_CACHE.value)
        ctx.set(active_req_in.en, 1)
        ctx.set(active_req_in.addr_in, 0)
        ctx.set(active_req_in.bytemask, 0b1111)
        await ctx.tick()
        assert ctx.get(active_req_in.busy) == 0
        assert ctx.get(active_req_in.data_out) == 0x00_00_00_00
        assert ctx.get(inactive_req_in.busy) == 1

        # write w/ bytemask
        # bytemaskを1bitずつ変えて書き込み、読み出しを確認
        write_data = 0x89_AB_CD_EF
        for byte_enable_pos in range(4):
            # write byte
            bytemask_wr = 0b0001 << byte_enable_pos

            ctx.set(active_req_in.op_type, LsuOperationType.WRITE_CACHE.value)
            ctx.set(active_req_in.en, 1)
            ctx.set(active_req_in.addr_in, 0)
            ctx.set(active_req_in.bytemask, bytemask_wr)
            ctx.set(active_req_in.data_in, write_data)
            await ctx.tick()
            assert ctx.get(active_req_in.busy) == 0
            assert ctx.get(inactive_req_in.busy) == 1

            # read word
            read_expect = write_data & ~(0xFFFFFFFF << ((byte_enable_pos + 1) * 8))

            ctx.set(active_req_in.op_type, LsuOperationType.READ_CACHE.value)
            ctx.set(active_req_in.en, 1)
            ctx.set(active_req_in.addr_in, 0)
            ctx.set(active_req_in.bytemask, 0b1111)
            await ctx.tick()
            assert ctx.get(active_req_in.busy) == 0
            assert ctx.get(active_req_in.data_out) == read_expect
            assert ctx.get(inactive_req_in.busy) == 1

    run_sim(f"{test_ssm_write_bytemask.__name__}", dut=dut, testbench=bench)


@pytest.mark.parametrize("is_primary", [True, False])
def test_ssm_read_bytemask(
    is_primary: bool,
):
    init_data = expect_data(seed=0x0, step=0)  # All Zero
    dut = SingleCycleMemory(init_data=init_data, use_strict_assert=True)
    active_req_in = dut.primary_req_in if is_primary else dut.secondary_req_in
    inactive_req_in = dut.secondary_req_in if is_primary else dut.primary_req_in

    async def bench(ctx):
        # disable
        ctx.set(active_req_in.op_type, LsuOperationType.NOP.value)
        ctx.set(active_req_in.bytemask, 0b1111)
        ctx.set(active_req_in.en, 0)
        ctx.set(active_req_in.addr_in, 0)
        ctx.set(active_req_in.data_in, 0)
        nop_cyc = 1
        for _ in range(nop_cyc):
            await ctx.tick()
            assert ctx.get(active_req_in.busy) == 0
            assert ctx.get(inactive_req_in.busy) == 0

        # write word
        write_data = 0x89_AB_CD_EF
        ctx.set(active_req_in.op_type, LsuOperationType.WRITE_CACHE.value)
        ctx.set(active_req_in.en, 1)
        ctx.set(active_req_in.addr_in, 0)
        ctx.set(active_req_in.bytemask, 0b1111)
        ctx.set(active_req_in.data_in, write_data)
        await ctx.tick()
        assert ctx.get(active_req_in.busy) == 0
        assert ctx.get(inactive_req_in.busy) == 1

        # read w/ bytemask
        # bytemaskを1bitずつ変えて読み出し、読み出しを確認
        for byte_enable_pos in reversed(range(4)):
            bytemask_rd = 0b0001 << byte_enable_pos
            read_expect = write_data & (0xFF << (byte_enable_pos * 8))
            ctx.set(active_req_in.op_type, LsuOperationType.READ_CACHE)
            ctx.set(active_req_in.en, 1)
            ctx.set(active_req_in.addr_in, 0)
            ctx.set(active_req_in.bytemask, bytemask_rd)
            await ctx.tick()
            assert ctx.get(active_req_in.busy) == 0
            assert ctx.get(active_req_in.data_out) == read_expect
            assert ctx.get(inactive_req_in.busy) == 1

    run_sim(f"{test_ssm_read_bytemask.__name__}", dut=dut, testbench=bench)


@pytest.mark.parametrize("is_primary", [True, False])
def test_ssm_write_byte_increment(
    is_primary: bool,
):
    init_data = expect_data(seed=0x0, step=0)  # All Zero
    dut = SingleCycleMemory(init_data=init_data, use_strict_assert=True)
    active_req_in = dut.primary_req_in if is_primary else dut.secondary_req_in
    inactive_req_in = dut.secondary_req_in if is_primary else dut.primary_req_in

    async def bench(ctx):
        # disable
        ctx.set(active_req_in.op_type, LsuOperationType.NOP.value)
        ctx.set(active_req_in.bytemask, 0b1111)
        ctx.set(active_req_in.en, 0)
        ctx.set(active_req_in.addr_in, 0)
        ctx.set(active_req_in.data_in, 0)
        nop_cyc = 1
        for _ in range(nop_cyc):
            await ctx.tick()
            assert ctx.get(active_req_in.busy) == 0
            assert ctx.get(inactive_req_in.busy) == 0

        # read word
        ctx.set(active_req_in.op_type, LsuOperationType.READ_CACHE.value)
        ctx.set(active_req_in.en, 1)
        ctx.set(active_req_in.addr_in, 0)
        ctx.set(active_req_in.bytemask, 0b1111)
        await ctx.tick()
        assert ctx.get(active_req_in.busy) == 0
        assert ctx.get(active_req_in.data_out) == 0x00_00_00_00
        assert ctx.get(inactive_req_in.busy) == 1

        # write w/ bytemask
        # bytemaskはそのままにアドレスインクリメントで書き込み、読み出しを確認
        write_data = 0x89_AB_CD_EF
        for addr_offset in range(4):
            # write byte
            bytemask_wr = 0b0001

            ctx.set(active_req_in.op_type, LsuOperationType.WRITE_CACHE.value)
            ctx.set(active_req_in.en, 1)
            ctx.set(active_req_in.addr_in, 0 + addr_offset)
            ctx.set(active_req_in.bytemask, bytemask_wr)
            ctx.set(
                active_req_in.data_in, write_data >> (addr_offset * 8)
            )  # 1byteずつ書き込み
            await ctx.tick()
            assert ctx.get(active_req_in.busy) == 0
            assert ctx.get(inactive_req_in.busy) == 1

            # read word
            read_expect = write_data & ~(0xFFFFFFFF << ((addr_offset + 1) * 8))

            ctx.set(active_req_in.op_type, LsuOperationType.READ_CACHE.value)
            ctx.set(active_req_in.en, 1)
            ctx.set(active_req_in.addr_in, 0)
            ctx.set(active_req_in.bytemask, 0b1111)
            await ctx.tick()
            assert ctx.get(active_req_in.busy) == 0
            assert ctx.get(active_req_in.data_out) == read_expect
            assert ctx.get(inactive_req_in.busy) == 1

    run_sim(f"{test_ssm_write_byte_increment.__name__}", dut=dut, testbench=bench)


@pytest.mark.parametrize("is_primary", [True, False])
def test_ssm_read_byte_increment(
    is_primary: bool,
):
    init_data = expect_data(seed=0x0, step=0)  # All Zero
    dut = SingleCycleMemory(init_data=init_data, use_strict_assert=True)
    active_req_in = dut.primary_req_in if is_primary else dut.secondary_req_in
    inactive_req_in = dut.secondary_req_in if is_primary else dut.primary_req_in

    async def bench(ctx):
        # disable
        ctx.set(active_req_in.op_type, LsuOperationType.NOP.value)
        ctx.set(active_req_in.bytemask, 0b1111)
        ctx.set(active_req_in.en, 0)
        ctx.set(active_req_in.addr_in, 0)
        ctx.set(active_req_in.data_in, 0)
        nop_cyc = 1
        for _ in range(nop_cyc):
            await ctx.tick()
            assert ctx.get(active_req_in.busy) == 0
            assert ctx.get(inactive_req_in.busy) == 0

        # write word
        write_data = 0x89_AB_CD_EF
        ctx.set(active_req_in.op_type, LsuOperationType.WRITE_CACHE.value)
        ctx.set(active_req_in.en, 1)
        ctx.set(active_req_in.addr_in, 0)
        ctx.set(active_req_in.bytemask, 0b1111)
        ctx.set(active_req_in.data_in, write_data)
        await ctx.tick()
        assert ctx.get(active_req_in.busy) == 0
        assert ctx.get(inactive_req_in.busy) == 1

        # read w/ bytemask
        # bytemaskを固定し、アドレスインクリメントで読み出し
        for addr_offset in reversed(range(4)):
            bytemask_rd = 0b0001
            read_expect = (write_data >> (addr_offset * 8)) & 0xFF
            ctx.set(active_req_in.op_type, LsuOperationType.READ_CACHE)
            ctx.set(active_req_in.en, 1)
            ctx.set(active_req_in.addr_in, addr_offset)
            ctx.set(active_req_in.bytemask, bytemask_rd)
            await ctx.tick()
            assert ctx.get(active_req_in.busy) == 0
            assert ctx.get(active_req_in.data_out) == read_expect
            assert ctx.get(inactive_req_in.busy) == 1

    run_sim(f"{test_ssm_read_byte_increment.__name__}", dut=dut, testbench=bench)


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
