import pytest

from bonsai.emu.mem import BusArbiter, BusArbiterEntry, MemSpace, UartModule


@pytest.mark.parametrize(
    "space",
    [
        MemSpace(addr_bits=32, data_bits=16),
        MemSpace(addr_bits=32, data_bits=32),
        MemSpace(addr_bits=64, data_bits=32),
        MemSpace(addr_bits=64, data_bits=64),
    ],
)
def test_uart(
    space: MemSpace,
    stdin: str = "Hello  World!",
):
    dut = UartModule(space=space, name=f"{test_uart}_dut")
    for c in stdin:
        dut.write8(UartModule.RegIdx.TX_DATA * space.num_data_bytes, ord(c))
    assert dut.stdout == stdin


@pytest.mark.parametrize(
    "space, base_addr",
    [
        (MemSpace(addr_bits=32, data_bits=16), 0x1000_0000),
        (MemSpace(addr_bits=32, data_bits=32), 0x2000_0000),
        (MemSpace(addr_bits=64, data_bits=32), 0x3000_0000),
        (MemSpace(addr_bits=64, data_bits=64), 0x4000_0000),
    ],
)
def test_arbitor(
    space: MemSpace,
    base_addr: int,
    stdin: str = "Hello World!",
):
    dut_uart = UartModule(space=space, name=f"{test_uart}_{base_addr:016x}_dut")
    dut_bus = BusArbiter(
        space=space,
        name=f"{test_uart}_{base_addr:016x}_bus",
        entries=[BusArbiterEntry(slave=dut_uart, start_addr=base_addr)],
    )
    for c in stdin:
        dut_bus.write8(
            base_addr + UartModule.RegIdx.TX_DATA * space.num_data_bytes, ord(c)
        )
    assert dut_uart.stdout == stdin
