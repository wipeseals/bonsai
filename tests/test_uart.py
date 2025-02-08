import logging
import math
from typing import List

import pytest
from amaranth.sim import SimulatorContext

from bonsai.periph.uart import UartConfig, UartParity, UartRx, UartTx
from bonsai.util import Simulation, even_parity, odd_parity

MIN_TEST_CASE: List[UartConfig] = [
    UartConfig(
        clk_freq=10e6,
        baud_rate=115200,
        num_data_bit=8,
        num_stop_bit=1,
        parity=UartParity.NONE,
    ),
    UartConfig(
        clk_freq=100e6,
        baud_rate=115200,
        num_data_bit=8,
        num_stop_bit=1,
        parity=UartParity.ODD,
    ),
    UartConfig(
        clk_freq=100e6,
        baud_rate=921600,
        num_data_bit=8,
        num_stop_bit=1,
        parity=UartParity.EVEN,
    ),
]


@pytest.mark.parametrize("config", MIN_TEST_CASE)
def test_uart_rx_recv_short(config: UartConfig):
    run_uart_rx_recv(config)


def run_uart_rx_recv(config: UartConfig):
    dut = UartRx(config=config)
    send_datas = list(
        [
            x & ((1 << config.num_data_bit) - 1)
            for x in [0xFF, 0x00, 0xA5, 0x3C, 0xEF, 0x12]
        ]
    )

    # データ更新周期
    period = 1 / config.baud_rate
    # 1ビットあたりのクロック数
    period_count = int(period / config.clk_period)
    # start bit検出した後、1/2周期待った地点をサンプリングポイントとする
    sample_point = math.ceil(period_count / 2)

    async def bench(ctx: SimulatorContext):
        ctx.set(dut.en, 1)
        ctx.set(dut.rx, 1)
        ctx.set(dut.stream.ready, 0)
        await ctx.tick().repeat(10)
        assert ctx.get(dut.stream.valid) == 0, "idle state error"

        for data_idx, expect_data in enumerate(send_datas):
            assert ctx.get(dut.stream.valid) == 0, "stream valid state error"
            logging.debug(f"send data[{data_idx}]: {expect_data:02x}")
            # start bit
            ctx.set(dut.rx, 0)
            await ctx.tick().repeat(period_count)
            # データビット送信
            for i in range(config.num_data_bit):
                current_bit = (expect_data >> i) & 1
                ctx.set(dut.rx, current_bit)
                logging.debug(
                    f"[{i:02d}] send progress data:{expect_data:08b} rx:{current_bit}"
                )
                assert ctx.get(dut.busy) == 1, "busy state error"
                await ctx.tick().repeat(period_count)
            # パリティビット送信
            if config.parity != UartParity.NONE:
                expect_parity = (
                    odd_parity(expect_data, config.num_data_bit)
                    if config.parity == UartParity.ODD
                    else even_parity(expect_data, config.num_data_bit)
                )
                ctx.set(dut.rx, expect_parity)
                logging.debug(f"parity bit: {expect_parity}")
                await ctx.tick().repeat(period_count)
            assert ctx.get(dut.parity_err) == 0, "parity error state error"
            # stop bit
            for i in range(config.num_stop_bit):
                ctx.set(dut.rx, 1)
                await ctx.tick().repeat(period_count)
                logging.debug("stop bit: 1")
                assert ctx.get(dut.ovf_err) == 0, "parity error state error"
            # validになるのを待って受信
            ctx.set(dut.stream.ready, 1)
            while ctx.get(dut.stream.valid) == 0:
                await ctx.tick()
            actual_data = ctx.get(dut.stream.payload)
            logging.debug(
                f"stream payload {actual_data:02x} is captured (expect {expect_data:02x})"
            )
            assert actual_data == expect_data, (
                f"recv data error: expect {expect_data:02x}, actual {actual_data:02x}"
            )
            # Captureされたらreadyを下げ, validもないはず
            await ctx.tick()
            assert ctx.get(dut.stream.valid) == 0, "stream valid state error"
            ctx.set(dut.stream.ready, 0)

    Simulation.run(
        name=f"{run_uart_rx_recv.__name__}_baudrate{config.baud_rate}_num_data_bit{config.num_data_bit}_num_stop_bit{config.num_stop_bit}_parity{config.parity}",
        dut=dut,
        testbench=bench,
        clock=config.clk_freq,
    )


@pytest.mark.parametrize("config", MIN_TEST_CASE)
def test_uart_tx_send_short(config: UartConfig):
    run_uart_tx_send(config)


def run_uart_tx_send(config: UartConfig):
    dut = UartTx(config=config)
    send_datas = list(
        [
            x & ((1 << config.num_data_bit) - 1)
            for x in [0xFF, 0x00, 0xA5, 0x3C, 0xEF, 0x12]
        ]
    )

    # データ更新周期
    period = 1 / config.baud_rate
    # 1ビットあたりのクロック数
    period_count = int(period / config.clk_period)
    # start bit検出した後、1/2周期待った地点をサンプリングポイントとする
    sample_point = math.ceil(period_count / 2)

    async def bench(ctx: SimulatorContext):
        ctx.set(dut.en, 1)
        ctx.set(dut.stream.valid, 0)
        await ctx.tick().repeat(10)
        assert ctx.get(dut.tx) == 1, "idle state error"
        # 本来なら別途readyまつのが良い気がするが、今回は取得して処理される前提でSimulationを進める

        for data_idx, data in enumerate(send_datas):
            logging.debug(f"send data[{data_idx}]: {data:02x}")
            ctx.set(dut.stream.valid, 1)
            ctx.set(dut.stream.payload, data)
            await ctx.tick()
            while ctx.get(dut.stream.ready) == 1:
                await ctx.tick()
            logging.debug(f"payload {data:02x} is captured")
            # 次のデータがキャプチャされないように一旦無効
            ctx.set(dut.stream.valid, 0)

            # start bitまで待ち
            while ctx.get(dut.tx) == 1:
                await ctx.tick()
            logging.debug("start bit detected")

            # start bitのsample pointまで1/2周期待ち
            await ctx.tick().repeat(sample_point)
            assert ctx.get(dut.busy) == 1, "busy state error"

            # start bit飛ばす
            await ctx.tick().repeat(period_count)
            assert ctx.get(dut.busy) == 1, "busy state error"
            # データビット読んでLSBから合成
            read_data = 0
            for i in range(config.num_data_bit):
                current_bit = ctx.get(dut.tx)
                read_data = read_data | (current_bit << i)
                logging.debug(f"[{i:02d}] read progress data: {read_data:08b}")
                await ctx.tick().repeat(period_count)
            logging.debug(f"read data: {read_data:02x}")
            assert read_data == data, (
                f"data bit error: expect {data:02x}, actual {read_data:02x}"
            )
            # パリティビット読んで合成
            if config.parity != UartParity.NONE:
                current_bit = ctx.get(dut.tx)
                expect_parity = (
                    odd_parity(read_data, config.num_data_bit)
                    if config.parity == UartParity.ODD
                    else even_parity(read_data, config.num_data_bit)
                )
                logging.debug(
                    f"parity bit: expect {expect_parity}, actual {current_bit}"
                )
                assert ctx.get(dut.busy) == 1, "busy state error"
                assert current_bit == expect_parity, (
                    f"parity bit error: expect {expect_parity}, actual {current_bit}"
                )
                await ctx.tick().repeat(period_count)
            # stop bit
            for i in range(config.num_stop_bit):
                logging.debug(f"[{i:02d}] stop bit: {ctx.get(dut.tx)}")
                assert ctx.get(dut.tx) == 1, "stop bit error"
                await ctx.tick().repeat(period_count)

    Simulation.run(
        name=f"{run_uart_tx_send.__name__}_baudrate{config.baud_rate}_num_data_bit{config.num_data_bit}_num_stop_bit{config.num_stop_bit}_parity{config.parity}",
        dut=dut,
        testbench=bench,
        clock=config.clk_freq,
    )
