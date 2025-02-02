import logging

from amaranth import Cat, Elaboratable, Module, Signal
from amaranth.build.plat import Platform
from amaranth.lib import io, wiring
from amaranth.lib.wiring import Out
from amaranth.utils import ceil_log2
from amaranth_boards.arty_a7 import ArtyA7_35Platform


class Timer(wiring.Component):
    def __init__(self, clk_freq: float, period_sec: float = 1.0):
        self._freq = int(clk_freq)
        self._coutner_width = ceil_log2(self._freq)
        self._blink_count = int(period_sec / (1 / float(clk_freq))) // 2

        super().__init__(
            {
                "ovf": Out(1),
            }
        )

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        # test timer
        counter = Signal(self._coutner_width)
        m.d.sync += [
            counter.eq(counter + 1),
            self.ovf.eq(0),
        ]
        with m.If(counter == self._blink_count - 1):
            m.d.sync += [
                counter.eq(0),
                self.ovf.eq(1),
            ]

        return m


class Top(wiring.Component):
    def __init__(self, clk_freq: float, period_sec: float = 1.0):
        self.timer = Timer(clk_freq=clk_freq, period_sec=period_sec)

        super().__init__(
            {
                "ovf": Out(1),
            }
        )

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        m.submodules.timer = self.timer

        m.d.comb += self.ovf.eq(self.timer.ovf)

        return m


class PlatformTop(Elaboratable):
    def _elaborate_arty_a7_35(self, m: Module, platform: Platform):
        NUM_LED = 4
        leds = [
            io.Buffer("o", platform.request("led", i, dir="-")) for i in range(NUM_LED)
        ]
        # use color leds
        NUM_RGB_LED = 3
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

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        m.submodules.top = Top(platform.default_clk_frequency, period_sec=1.0)

        # Platform specific elaboration
        if isinstance(platform, ArtyA7_35Platform):
            self._elaborate_arty_a7_35(m, platform)
        else:
            logging.warning(f"Unsupported platform: {platform}")

        return m
