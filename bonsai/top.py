import logging
from typing import Optional

from amaranth import Assert, Cat, Elaboratable, Format, Module, Signal
from amaranth.build.plat import Platform
from amaranth.lib import enum, io, wiring
from amaranth.lib.wiring import In, Out
from amaranth.utils import ceil_log2
from amaranth_boards.arty_a7 import ArtyA7_35Platform


@enum.unique
class TimerMode(enum.IntEnum):
    # 指定したカウントに達してもカウントクリアせずに継続 (e.g. PWM)
    FREERUN = 0
    # 指定したカウントに達したらしたらカウントクリアしたうえで継続 (e.g. Cyclic timer)
    FREERUN_WITH_CLEAR = 1
    # Overflowしたら停止。再開にはtrigger信号が必要 (e.g. One-shot timer)
    ONESHOT = 2


class Timer(wiring.Component):
    def __init__(
        self,
        clk_freq: float,
        bit_width: Optional[int] = None,
        default_period_seconds: Optional[float] = None,
    ):
        self._clk_freq = int(clk_freq)
        self._bit_width = 0 if bit_width is None else bit_width
        self._default_cmp_count = 0

        # default_period_sec に必要なビット数を計算してbit_widthを設定
        if default_period_seconds is not None:
            self._default_cmp_count = int(
                default_period_seconds / (1 / float(clk_freq))
            )
            need_bit_width = ceil_log2(self._default_cmp_count)
            if self._bit_width < need_bit_width:
                self._bit_width = need_bit_width
        assert self._bit_width > 0, "bit_width must be positive"

        super().__init__(
            {
                "clr": In(1),
                "en": In(1),
                "trig": In(1),
                "mode": In(TimerMode),
                "cmp_count_in": In(self._bit_width),
                "cmp_count_wr": In(1),
                "ovf": Out(1),
            }
        )

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        counter_reg = Signal(self._bit_width)
        cmp_count_reg = Signal(self._bit_width, reset=self._default_cmp_count)

        # cmp_count_wr 有効時のみ cmp_count_in に書き換え
        with m.If(self.cmp_count_wr):
            m.d.sync += cmp_count_reg.eq(self.cmp_count_in)

        # カウンター制御
        with m.If(~self.clr & self.en):
            with m.Switch(self.mode):
                with m.Case(TimerMode.FREERUN):
                    # カウントして、既定値超えていたらovfを立てる
                    m.d.sync += [
                        counter_reg.eq(counter_reg + 1),
                        self.ovf.eq(counter_reg >= cmp_count_reg),
                    ]
                with m.Case(TimerMode.FREERUN_WITH_CLEAR):
                    # カウントして、既定値超えていたらovfを立てつつカウントをクリア
                    m.d.sync += [
                        counter_reg.eq(counter_reg + 1),
                        self.ovf.eq(counter_reg >= cmp_count_reg),
                    ]
                    with m.If(self.ovf):
                        m.d.sync += [
                            counter_reg.eq(0),
                            self.ovf.eq(0),
                        ]
                with m.Case(TimerMode.ONESHOT):
                    # 0/ovf時かつtrigが立っている場合にカウント開始。ovf立つまではカウント
                    is_restart = ((counter_reg == 0) | self.ovf) & self.trig
                    with m.If(is_restart):
                        m.d.sync += [
                            counter_reg.eq(0),
                            self.ovf.eq(0),
                        ]
                    with m.Elif(~self.ovf):
                        m.d.sync += [
                            counter_reg.eq(counter_reg + 1),
                            self.ovf.eq(counter_reg >= cmp_count_reg),
                        ]

        # clearはen貫通してクリアできる
        with m.If(self.clr):
            m.d.sync += [
                counter_reg.eq(0),
                self.ovf.eq(0),
            ]

        return m


class Top(wiring.Component):
    def __init__(self, clk_freq: float, period_sec: float = 1.0):
        self.timer = Timer(clk_freq=clk_freq, default_period_seconds=period_sec)

        super().__init__(
            {
                "ovf": Out(1),
            }
        )

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        m.submodules.timer = self.timer

        m.d.comb += [
            self.ovf.eq(self.timer.ovf),
            # timer constant
            self.timer.en.eq(1),
            self.timer.clr.eq(0),
            self.timer.trig.eq(0),
            self.timer.cmp_count_wr.eq(0),
            self.timer.mode.eq(TimerMode.FREERUN_WITH_CLEAR),
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

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        m.submodules.top = Top(platform.default_clk_frequency, period_sec=1.0)

        # Platform specific elaboration
        if isinstance(platform, ArtyA7_35Platform):
            self._elaborate_arty_a7_35(m, platform)
        else:
            logging.warning(f"Unsupported platform: {platform}")

        return m
