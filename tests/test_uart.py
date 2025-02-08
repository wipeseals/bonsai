import logging
import math
from typing import List

import pytest
from amaranth import ClockDomain, Module
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
def test_uart_loopback(config: UartConfig):
    dut = Module()
    dut.domains.sync = cd_sync = ClockDomain()
    dut.submodules.uart_rx = uart_rx = UartRx(config=config)
    dut.submodules.uart_tx = uart_tx = UartTx(config=config)
    dut.d.comb += [
        # enable
        uart_rx.en.eq(1),
        uart_tx.en.eq(1),
        # RX -> TX
        uart_tx.stream.valid.eq(uart_rx.stream.valid),
        uart_tx.stream.payload.eq(uart_rx.stream.payload),
        uart_rx.stream.ready.eq(uart_tx.stream.ready),
    ]

    send_datas = list(
        [x & ((1 << config.num_data_bit) - 1) for x in [0xFE, 0x01, 0xA5, 0x3C]]
    )
    period = 1 / config.baud_rate
    period_count = int(period / config.clk_period)

    async def test_miso(ctx: SimulatorContext):
        cyc_counter = 0
        recv_state = "IDLE"
        recv_period_counter = 0
        recv_bit_idx = 0
        recv_data = 0
        recv_data_idx = 0
        async for clk_edge, rst_value, tx_value in ctx.tick().sample(uart_tx.tx):
            cyc_counter += 1
            if cyc_counter < period_count:
                continue
            elif rst_value:
                recv_state = "IDLE"
                recv_period_counter = 0
                recv_bit_idx = 0
                recv_data = 0
                recv_data_idx = 0
                continue
            elif clk_edge:
                # 1周期ごとにカウントダウン
                if recv_period_counter > 0:
                    recv_period_counter -= 1
                    continue

                # 一定周期経過後はイベント発火
                if recv_state == "IDLE":
                    if tx_value == 1:
                        # NOP
                        pass
                    else:
                        # start bit検出. 1/2周期待ってからサンプリング
                        recv_state = "START_BIT"
                        recv_period_counter = period_count // 2
                        logging.debug(f"[DUT_TX][{cyc_counter}] start bit detected")
                elif recv_state == "START_BIT":
                    assert tx_value == 0, f"[DUT_TX][{cyc_counter}] start bit error"
                    # 以後データサンプリング
                    recv_state = "DATA"
                    recv_period_counter = period_count
                elif recv_state == "DATA":
                    recv_data |= tx_value << recv_bit_idx
                    logging.debug(
                        f"[DUT_TX][{cyc_counter}] recv data[{recv_data_idx}]: {recv_data:08b} (expect {send_datas[recv_data_idx]:08b})"
                    )
                    recv_bit_idx += 1
                    if recv_bit_idx < config.num_data_bit:
                        # データビット受信中
                        recv_period_counter = period_count
                    else:
                        logging.debug(
                            f"[DUT_TX][{cyc_counter}] data received. expect {send_datas[recv_data_idx]:02x}, actual {recv_data:02x}"
                        )
                        assert recv_data == send_datas[recv_data_idx], (
                            f"[DUT_TX][{cyc_counter}] data error: expect {send_datas[recv_data_idx]:02x}, actual {recv_data:02x}"
                        )
                        recv_state = (
                            "PARITY" if config.parity != UartParity.NONE else "STOP_BIT"
                        )
                        recv_period_counter = period_count
                elif recv_state == "PARITY":
                    expect_parity = (
                        odd_parity(recv_data, config.num_data_bit)
                        if config.parity == UartParity.ODD
                        else even_parity(recv_data, config.num_data_bit)
                    )
                    logging.debug(
                        f"[DUT_TX][{cyc_counter}] parity bit: {expect_parity} (expect {tx_value})"
                    )
                    assert tx_value == expect_parity, (
                        f"[DUT_TX][{cyc_counter}] parity error"
                    )
                    recv_state = "STOP_BIT"
                    recv_period_counter = period_count
                elif recv_state == "STOP_BIT":
                    if tx_value == 0:
                        # 待機
                        pass
                    else:
                        logging.debug(f"[DUT_TX][{cyc_counter}] stop bit detected")
                        recv_state = "IDLE"
                        recv_period_counter = (
                            period_count // 2
                        )  # stopbit抜けるまでは待たせる。現在位置がsample pointなので1/2周期待つ
                        recv_bit_idx = 0
                        recv_data = 0
                        recv_data_idx += 1
                        if recv_data_idx == len(send_datas):
                            break

    async def bench_mosi(ctx: SimulatorContext):
        ctx.set(uart_rx.rx, 1)
        await ctx.tick().repeat(period_count * 3)  # init state
        for data_idx, expect_data in enumerate(send_datas):
            assert ctx.get(uart_rx.stream.valid) == 0, "[DUT_RX] idle state error"
            logging.debug(f"[DUT_RX] send data[{data_idx}]: {expect_data:02x}")
            # start bit
            ctx.set(uart_rx.rx, 0)
            await ctx.tick().repeat(period_count)
            # データビット送信
            for i in range(config.num_data_bit):
                current_bit = (expect_data >> i) & 1
                ctx.set(uart_rx.rx, current_bit)
                logging.debug(
                    f"[DUT_RX] [{i:02d}] send progress data:{expect_data:08b} rx:{current_bit}"
                )
                assert ctx.get(uart_rx.busy) == 1, "[DUT_RX] busy state error"
                await ctx.tick().repeat(period_count)
            # パリティビット送信
            if config.parity != UartParity.NONE:
                expect_parity = (
                    odd_parity(expect_data, config.num_data_bit)
                    if config.parity == UartParity.ODD
                    else even_parity(expect_data, config.num_data_bit)
                )
                ctx.set(uart_rx.rx, expect_parity)
                logging.debug(f"[DUT_RX] parity bit: {expect_parity}")
                await ctx.tick().repeat(period_count)
            assert ctx.get(uart_rx.parity_err) == 0, "[DUT_RX] parity error state error"
            # stop bit
            for i in range(config.num_stop_bit):
                ctx.set(uart_rx.rx, 1)
                await ctx.tick().repeat(period_count)
                logging.debug("[DUT_RX] stop bit: 1")
                assert ctx.get(uart_rx.ovf_err) == 0, (
                    "[DUT_RX] parity error state error"
                )

    Simulation.run(
        name=f"{test_uart_loopback.__name__}_baudrate{config.baud_rate}_num_data_bit{config.num_data_bit}_num_stop_bit{config.num_stop_bit}_parity{config.parity}",
        dut=dut,
        testbench=bench_mosi,
        clock=config.clk_freq,
        setup_f=lambda sim: sim.add_process(test_miso),
    )


@pytest.mark.parametrize("config", MIN_TEST_CASE)
def test_uart_rx(config: UartConfig):
    dut = UartRx(config=config)
    send_datas = list(
        [x & ((1 << config.num_data_bit) - 1) for x in [0xFE, 0x01, 0xA5, 0x3C]]
    )

    # データ更新周期
    period = 1 / config.baud_rate
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
        name=f"{test_uart_rx.__name__}_baudrate{config.baud_rate}_num_data_bit{config.num_data_bit}_num_stop_bit{config.num_stop_bit}_parity{config.parity}",
        dut=dut,
        testbench=bench,
        clock=config.clk_freq,
    )


@pytest.mark.parametrize("config", MIN_TEST_CASE)
def test_uart_tx(config: UartConfig):
    dut = UartTx(config=config)
    send_datas = list(
        [x & ((1 << config.num_data_bit) - 1) for x in [0xFE, 0x01, 0xA5, 0x3C]]
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
        name=f"{test_uart_tx.__name__}_baudrate{config.baud_rate}_num_data_bit{config.num_data_bit}_num_stop_bit{config.num_stop_bit}_parity{config.parity}",
        dut=dut,
        testbench=bench,
        clock=config.clk_freq,
    )
