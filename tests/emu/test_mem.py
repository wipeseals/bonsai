import pytest

from bonsai.emu.mem import AccessType, BusArbiter, BusArbiterEntry, UartModule


def test_uart(
    stdin: str = "Hello  World!",
):
    dut = UartModule(name=f"{test_uart}_dut")
    for c in stdin:
        dut.write_reg(UartModule.RegIdx.TX_DATA.value, ord(c), AccessType.NORMAL)
    assert dut.stdout == stdin


@pytest.mark.parametrize(
    "base_addr",
    [
        0x1000_0000,
        0x2000_0000,
        0x3000_0000,
        0x4000_0000,
    ],
)
def test_arbitor(
    base_addr: int,
    stdin: str = "Hello World!",
):
    dut_uart = UartModule(name=f"{test_uart}_{base_addr:016x}_dut")
    dut_bus = BusArbiter(
        name=f"{test_uart}_{base_addr:016x}_bus",
        entries=[BusArbiterEntry(slave=dut_uart, start_addr=base_addr)],
    )
    for c in stdin:
        dut_bus.write(
            base_addr + UartModule.RegIdx.TX_DATA.value * 4, ord(c), AccessType.NORMAL
        )
    assert dut_uart.stdout == stdin
