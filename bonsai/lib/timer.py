from typing import Optional

from amaranth import Module, Signal
from amaranth.build.plat import Platform
from amaranth.lib import enum, wiring
from amaranth.lib.wiring import In, Out
from amaranth.utils import ceil_log2


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
