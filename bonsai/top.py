import logging

from amaranth import Cat, Elaboratable, Module, Signal
from amaranth.build.plat import Platform
from amaranth.lib import enum, io, wiring, stream
from amaranth.lib.wiring import In, Out
from amaranth.utils import ceil_log2
from amaranth_boards.arty_a7 import ArtyA7_35Platform
from lib.timer import Timer, TimerMode


@enum.unique
class UartParity(enum.IntEnum):
    NONE = 0
    ODD = 1
    EVEN = 2


class UartTx(wiring.Component):
    def __init__(
        self,
        clk_freq: float,
        baud_rate: int = 115200,
        num_data_bit: int = 8,
        num_stop_bit: int = 1,
        parity: UartParity = UartParity.NONE,
    ):
        # Clock周期
        self._clk_period = 1 / clk_freq
        # 1ビットあたりの時間(sec)
        self._period = 1 / baud_rate
        # 1ビットあたりの必要クロック数
        self._period_count = int(self._period / self._clk_period)
        # クロック数覚える用のカウンタビット幅
        self._div_counter_width = ceil_log2(self._period_count)

        # データ転送カウンタ
        assert num_data_bit > 0, "num_data_bit must be positive"
        assert num_stop_bit > 0, "num_stop_bit must be positive"
        self._num_data_bit = num_data_bit
        self._num_stop_bit = num_stop_bit
        self._parity = parity
        self._transfer_count = (
            self._num_data_bit
            + self._num_stop_bit
            + (1 if self._parity != UartParity.NONE else 0)
        )
        self._transfer_counter_width = ceil_log2(self._transfer_count)

        super().__init__(
            {
                "stream": In(stream.Signature(8)),
                "en": In(1),
                "tx": Out(1),
            }
        )

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        # 分周カウンタ
        div_counter = Signal(self._div_counter_width, reset=0)
        event_tx = Signal(1, reset=0)
        with m.If(div_counter < self._period_count):
            m.d.sync += [
                div_counter.eq(div_counter + 1),
                event_tx.eq(0),
            ]
        with m.Else():
            m.d.sync += [
                div_counter.eq(0),
                event_tx.eq(1),
            ]

        # streamからのデータ受付
        # AmaranthのData streamにあるData transfer rulesではSlave側のreadyがvalidを待つことを禁止していないが
        # AXIに習って受付可能状態にreadyを返すようにしておく
        tx_data = Signal(self._num_data_bit)
        tx_data_valid = Signal(1, reset=0)
        # tx_dataにデータ格納してなければ取得OK
        m.d.comb += self.stream.ready.eq(~tx_data_valid)
        # ready & validで転送実行
        with m.If(self.stream.valid & self.stream.ready):
            m.d.sync += [
                tx_data.eq(self.stream.payload),
                tx_data_valid.eq(1),
            ]

        # 転送カウンタ+FSMで制御。enはいきなり反応しない
        tx_counter = Signal(self._transfer_counter_width, reset=0)
        with m.If(event_tx):
            with m.FSM(init="IDLE"):
                with m.State("IDLE"):
                    # 有効かつデータあれば転送開始 + StartBit
                    with m.If(self.en & tx_data_valid):
                        m.d.sync += [
                            tx_counter.eq(0),  # 転送ビット位置向けに初期化
                            self.tx.eq(0),  # StartBit
                        ]
                        m.next = "START_BIT"
                with m.State("START_BIT"):
                    # Databit送信
                    with m.If(tx_counter < self._num_data_bit - 1):
                        # data bit
                        m.d.sync += [
                            tx_counter.eq(tx_counter + 1),
                            self.tx.eq(tx_data.bit_select(tx_counter, 1)),
                        ]
                    with m.Elif(tx_counter == (self._num_data_bit - 1)):
                        # last data bit
                        m.d.sync += [
                            tx_counter.eq(0),  # Parity/StopBit送信向けに初期化
                            self.tx.eq(tx_data.bit_select(tx_counter, 1)),
                        ]
                        # parity bit or stop bit
                        if self._parity == UartParity.NONE:
                            m.next = "STOP_BIT"
                        elif self._parity == UartParity.ODD:
                            m.next = "PARITY"
                        elif self._parity == UartParity.EVEN:
                            m.next = "PARITY"
                with m.State("PARITY"):
                    odd_parity = tx_data.xor()
                    even_parity = ~odd_parity
                    send_parity = (
                        odd_parity if self._parity == UartParity.ODD else even_parity
                    )
                    m.d.sync += [
                        tx_counter.eq(0),  # StopBit送信向けに初期化
                        self.tx.eq(send_parity),
                    ]
                    m.next = "STOP_BIT"
                with m.State("STOP_BIT"):
                    # StopBit送信
                    with m.If(tx_counter < self._num_stop_bit - 1):
                        # stop bit
                        m.d.sync += [
                            tx_counter.eq(tx_counter + 1),
                            self.tx.eq(1),  # StopBit
                        ]
                    with m.Elif(tx_counter == (self._num_stop_bit - 1)):
                        # last stop bit
                        m.d.sync += [
                            tx_counter.eq(0),  # 転送終了
                            self.tx.eq(1),  # StopBit
                        ]
                        # Fetchしたデータ不要
                        m.d.sync += [
                            tx_data_valid.eq(0),
                        ]
                        m.next = "IDLE"
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
