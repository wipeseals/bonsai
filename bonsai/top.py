import logging

from amaranth import Cat, Elaboratable, Module, Signal
from amaranth.build.plat import Platform
from amaranth.lib import enum, io, stream, wiring
from amaranth.lib.wiring import In, Out
from amaranth.utils import ceil_log2
from amaranth_boards.arty_a7 import ArtyA7_35Platform
from amaranth_boards.tang_nano_9k import TangNano9kPlatform
from periph.timer import Timer, TimerMode
from periph.uart import UartTx


class Top(wiring.Component):
    def __init__(
        self, clk_freq: float, period_sec: float = 1.0, baud_rate: int = 115200
    ):
        self.timer = Timer(clk_freq=clk_freq, default_period_seconds=period_sec)
        self.uart_tx = UartTx(clk_freq=clk_freq, baud_rate=baud_rate)

        super().__init__(
            {
                "ovf": Out(1),
                "tx": Out(1),
            }
        )

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        m.submodules.timer = self.timer
        m.submodules.uart_tx = self.uart_tx

        # Timer
        m.d.comb += [
            # External
            self.ovf.eq(self.timer.ovf),
            # Internal
            self.timer.en.eq(1),
            self.timer.clr.eq(0),
            self.timer.trig.eq(0),
            self.timer.cmp_count_wr.eq(0),
            self.timer.mode.eq(TimerMode.FREERUN_WITH_CLEAR),
        ]

        # uart_tx test
        char_start = ord(" ")
        char_end = ord("~")
        tx_data = Signal(8, reset=0)
        with m.If(self.uart_tx.stream.ready):
            with m.If(tx_data < char_end):
                m.d.sync += tx_data.eq(tx_data + 1)
            with m.Else():
                m.d.sync += tx_data.eq(char_start)
        m.d.comb += [
            # External
            self.tx.eq(self.uart_tx.tx),
            # Internal
            self.uart_tx.stream.valid.eq(1),
            self.uart_tx.stream.payload.eq(tx_data),
            self.uart_tx.en.eq(1),
        ]

        return m


class PlatformTop(Elaboratable):
    def _elaborate_arty_a7_35(self, m: Module, platform: Platform):
        NUM_LED = 4
        leds = [
            io.Buffer("o", platform.request("led", i, dir="-")) for i in range(NUM_LED)
        ]
        # use color leds
        NUM_RGB_LED = 4
        rgb_leds = [platform.request("rgb_led", i, dir="-") for i in range(NUM_RGB_LED)]
        leds.extend([io.Buffer("o", led.r) for led in rgb_leds])
        leds.extend([io.Buffer("o", led.g) for led in rgb_leds])
        leds.extend([io.Buffer("o", led.b) for led in rgb_leds])

        NUM_BUTTON = 4
        buttons = [
            io.Buffer("i", platform.request("button", i, dir="-"))
            for i in range(NUM_BUTTON)
        ]
        button_data = Cat([button.i for button in buttons])
        NUM_SWITCH = 4
        switches = [
            io.Buffer("i", platform.request("switch", i, dir="-"))
            for i in range(NUM_SWITCH)
        ]
        switch_data = Cat([switch.i for switch in switches])

        m.submodules += leds + buttons + switches
        top: Top = m.submodules.top

        COUNTER_WIDTH = NUM_LED + NUM_RGB_LED * 3
        counter = Signal(COUNTER_WIDTH)
        with m.If(top.ovf):
            m.d.sync += counter.eq(counter + 1 + button_data + switch_data)
        # 各bitをLEDに割当
        for i, led in enumerate(leds):
            m.d.comb += [led.o.eq(counter[i])]

        uart = platform.request("uart", 0, dir="-")
        uart_tx = io.Buffer("o", uart.tx)
        m.submodules += [uart_tx]
        m.d.comb += [
            uart_tx.o.eq(top.tx),
        ]

    def _elabolate_tangnano_9k(self, m: Module, platform: Platform):
        NUM_LED = 6
        leds = [
            io.Buffer("o", platform.request("led", i, dir="-")) for i in range(NUM_LED)
        ]

        NUM_BUTTON = 2
        buttons = [
            io.Buffer("i", platform.request("button", i, dir="-"))
            for i in range(NUM_BUTTON)
        ]
        button_data = Cat([button.i for button in buttons])

        m.submodules += leds + buttons
        top: Top = m.submodules.top

        COUNTER_WIDTH = NUM_LED
        counter = Signal(COUNTER_WIDTH)
        with m.If(top.ovf):
            m.d.sync += counter.eq(counter + 1 + button_data)
        # 各bitをLEDに割当
        for i, led in enumerate(leds):
            m.d.comb += [led.o.eq(counter[i])]

        uart = platform.request("uart", 0, dir="-")
        uart_tx = io.Buffer("o", uart.tx)
        m.submodules += [uart_tx]
        m.d.comb += [
            uart_tx.o.eq(top.tx),
        ]

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        m.submodules.top = Top(platform.default_clk_frequency, period_sec=1.0)

        # Platform specific elaboration
        if isinstance(platform, ArtyA7_35Platform):
            self._elaborate_arty_a7_35(m, platform)
        elif isinstance(platform, TangNano9kPlatform):
            self._elabolate_tangnano_9k(m, platform)
        else:
            logging.warning(f"Unsupported platform: {platform}")

        return m
