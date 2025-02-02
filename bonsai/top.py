import logging

from amaranth import Elaboratable, Module, Signal
from amaranth.build.plat import Platform
from amaranth.lib import wiring
from amaranth.lib.wiring import Out
from amaranth.utils import ceil_log2
from amaranth_boards.arty_a7 import ArtyA7_35Platform


class Top(wiring.Component):
    def __init__(self, clk_freq: int, period_sec: float = 1.0):
        self._freq = clk_freq
        self._coutner_width = ceil_log2(self._freq)
        self._blink_count = int(period_sec / (1 / float(clk_freq))) // 2
        super().__init__(
            {
                "counter": Out(self._coutner_width),
            }
        )

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        # test counter
        m.d.sync += self.counter.eq(self.counter + 1)
        with m.If(self.counter == self._blink_count - 1):
            m.d.sync += self.counter.eq(0)
        return m


class PlatformTop(Elaboratable):
    def _elaborate_arty_a7_35(self, m: Module, platform: Platform, top: Top):
        num_led = 4
        leds = [platform.request("led", 0, dir="-") for i in range(num_led)]
        buttons = [platform.request("button", i, dir="-") for i in range(num_led)]
        switches = [platform.request("switch", i, dir="-") for i in range(num_led)]

        m.submodules += leds + buttons + switches
        for i in range(num_led):
            m.d.comb += [leds[i].o.eq(top.counter[-i] ^ buttons[i].i ^ switches[i].i)]

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        m.submodules.top = top = Top(platform.default_clk_frequency, period_sec=1.0)

        # Platform specific elaboration
        if isinstance(platform, ArtyA7_35Platform):
            self._elaborate_arty_a7_35(m, platform, top)
        else:
            logging.warning(f"Unsupported platform: {platform}")

        return m
