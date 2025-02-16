from dataclasses import dataclass

from amaranth import Module, Signal
from amaranth.build.plat import Platform
from amaranth.lib import stream, wiring
from amaranth.lib.wiring import In, Out
from amaranth.utils import ceil_log2


@dataclass
class SpiConfig:
    """
    SPI Configuration
    当初 ClockPhase, ClockPolarity, DataOrderの設定を作っていたが、実際使わなそうなので簡略化
    """

    # Stream Clock
    system_clk_freq: float
    # Transfer Clock
    sclk_freq: float
    # Data Width
    data_width: int = 8

    def __post_init__(self):
        assert self.system_clk_freq > 0, "system_clk_freq must be positive"
        assert self.sclk_freq > 0, "sclk_freq must be positive"
        assert (self.system_clk_freq // 2) >= self.sclk_freq, (
            "sclk_freq must be less than or equal to system_clk_freq/2"
        )
        assert self.data_width > 0, "data_width must be positive"

    @staticmethod
    def sclk_div_count_from_freq(system_clk_freq: float, sclk_freq: float) -> int:
        """
        SCLKのクロック分周比を計算
        system_clk_freq / 2 にしているのは、stream_clkのSDR駆動なのでイベント自体が更に1/2になるため
        """
        assert system_clk_freq > 0, "system_clk_freq must be positive"
        assert sclk_freq > 0, "sclk_freq must be positive"
        assert (system_clk_freq // 2) >= sclk_freq, (
            "sclk_freq must be less than or equal to system_clk_freq/2"
        )

        n = int((system_clk_freq // 2) // sclk_freq)
        assert n > 0, (
            f"sclk_clock_div_ratio must be positive. {n=} {system_clk_freq=} {sclk_freq=}"
        )
        return n

    @staticmethod
    def sclk_div_count_width_from_freq(system_clk_freq: float, sclk_freq: float) -> int:
        """
        sclk_clock_div_countに必要なビット数
        """
        div_count: int = SpiConfig.sclk_div_count_from_freq(system_clk_freq, sclk_freq)
        # div_count=1の場合にカウンタビット幅が0扱いになる。性格にはlog2(divCount) + 1がカウントできる必要がある
        n = int(ceil_log2(div_count)) + 1
        assert n > 0, (
            f"sclk_clock_div_count_width must be positive. {n=} {div_count=} {system_clk_freq=} {sclk_freq=}"
        )
        return n

    @property
    def sclk_div_count(self) -> int:
        """
        SCLKのクロック分周比
        """
        return self.sclk_div_count_from_freq(
            system_clk_freq=self.system_clk_freq,
            sclk_freq=self.sclk_freq,
        )

    @property
    def sclk_div_count_width(self) -> int:
        """
        sclk_clock_div_countに必要なビット数
        """
        return self.sclk_div_count_width_from_freq(
            system_clk_freq=self.system_clk_freq,
            sclk_freq=self.sclk_freq,
        )

    @property
    def transfer_counter_width(self) -> int:
        """
        transfer_counterに必要なビット数
        """
        n = int(ceil_log2(self.data_width))
        assert n > 0, "transfer_counter_width must be positive"
        return n


class SpiMaster(wiring.Component):
    """
    SPI Master
    入力Clockに同期してデータを送受信するSPI Master。標準ではsclk=clk/2
    MSB First & Mode=0 のみ対応 (CPOL=0, CPHA=0: SCK is low when idle, data is captured on the rising edge of SCK)
    """

    def __init__(self, config: SpiConfig, *, src_loc_at=0):
        self._config = config
        super().__init__(
            {
                # internal control
                "en": In(1),
                "busy": Out(1),  # status
                "done": Out(1),  # status
                # internal config
                "wr_cfg": In(1),  # config update
                "cfg_div_counter_th": In(config.sclk_div_count_width),
                # internal stream
                "stream_mosi": In(stream.Signature(config.data_width)),
                "stream_miso": Out(stream.Signature(config.data_width)),
                # for external
                "sclk": Out(1),
                "mosi": Out(1),
                "miso": In(1),
            },
            src_loc_at=src_loc_at,
        )

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        # Clock Divider
        div_counter = Signal(self._config.sclk_div_count_width, init=0)
        div_counter_th = Signal(
            self._config.sclk_div_count_width,
            init=self._config.sclk_div_count - 1,
        )
        div_counter_event = Signal(1, init=0)
        with m.If(div_counter < div_counter_th):
            m.d.sync += [
                div_counter.eq(div_counter + 1),
                div_counter_event.eq(0),
            ]
        with m.Else():
            m.d.sync += [
                div_counter.eq(0),
                div_counter_event.eq(1),
            ]

        # SCLK. 分周のために div_counter_event で駆動。rise/fallはFSM中でのイベント制御用
        sclk_is_rising = Signal(1, init=0)
        sclk_is_falling = Signal(1, init=0)

        sclk_en = Signal(1, init=0)
        with m.If(sclk_en & div_counter_event):
            m.d.sync += [
                # Edge detect
                sclk_is_rising.eq(self.sclk == 0),  # (Current)Low -> High
                sclk_is_falling.eq(self.sclk == 1),  # (Current)High -> Low
                # Next SCLK
                self.sclk.eq(~self.sclk),
            ]
        with m.Else():
            m.d.sync += [
                # Disable Edge
                sclk_is_rising.eq(0),
                sclk_is_falling.eq(0),
                # Disable SCLK
                self.sclk.eq(0),  # CPOL0: Normally low
            ]
        # MOSI/MISO
        mosi_reg = Signal(self._config.data_width, reset=0)
        miso_reg = Signal(self._config.data_width, reset=0)
        m.d.comb += [
            self.mosi.eq(mosi_reg[-1]),
            # miso_reg は rising edgeで更新
        ]

        # Transfer FSM
        transfer_counter = Signal(self._config.transfer_counter_width, init=0)
        with m.FSM(init="IDLE") as fsm:
            with m.State("IDLE"):
                # Default
                m.d.sync += [
                    # transfer regs clear
                    mosi_reg.eq(0),
                    miso_reg.eq(0),
                    transfer_counter.eq(0),
                    # disable SCLK
                    sclk_en.eq(0),
                    # flag clear
                    self.busy.eq(0),
                    self.done.eq(0),
                ]

                # 前回送信したデータの受取確認
                with m.If(self.stream_miso.valid):
                    with m.If(self.stream_miso.ready):
                        # Data captureされるので無効データ化
                        m.d.sync += [
                            # Stream In: Allow
                            self.stream_mosi.ready.eq(1),
                            # Stream Out: Valid->Invalid
                            self.stream_miso.valid.eq(0),
                        ]
                    with m.Else():
                        # 受け取れていないので待機
                        m.d.sync += [
                            # Stream In: Keep Deny
                            self.stream_mosi.ready.eq(0),
                            # Stream Out: keep Valid
                            self.stream_miso.valid.eq(1),
                        ]
                with m.Else():
                    # 受取済 or 1度も送信していない
                    m.d.sync += [
                        # Stream In: Allow
                        self.stream_mosi.ready.eq(1),
                        # Stream Out: Invalid
                        self.stream_miso.valid.eq(0),
                    ]

                # enable かつ mosi のデータ転送タイミング(ready/valid)が合致したら送信開始
                # enable はここでしか見ない。転送途中でのstallはStreamのvalid/ready下げ忘れ事故がおきる
                with m.If(self.en & self.stream_mosi.valid & self.stream_mosi.ready):
                    m.d.sync += [
                        # Stream In: Captured
                        self.stream_mosi.ready.eq(0),
                        # Stream Out: keep Disable
                        self.stream_miso.valid.eq(0),
                        # Data Reg: Capture stream_mosi -> mosi_reg
                        mosi_reg.eq(self.stream_mosi.payload),  # MSBが次cycそのまま出力
                        miso_reg.eq(0),
                        # Transfer Counter: Initial state + Enable SCLK
                        transfer_counter.eq(0),
                        sclk_en.eq(1),
                        # Flags: Busy
                        self.busy.eq(1),
                        self.done.eq(0),
                    ]
                    m.next = "XFER"
            with m.State("XFER"):
                # Rise -> Fall -> Rise -> Fall -> ... -> Fall(last) -> Done
                with m.If(sclk_is_rising):
                    # SCLK Rising Edge: サンプリング
                    m.d.sync += [
                        miso_reg.eq(miso_reg << 1 | self.miso),
                    ]
                with m.If(sclk_is_falling):
                    # SCLK Falling Edge: データシフト
                    m.d.sync += [
                        mosi_reg.eq(mosi_reg << 1),
                    ]
                    # 転送回数更新
                    with m.If(transfer_counter < self._config.data_width - 1):
                        m.d.sync += [
                            transfer_counter.eq(transfer_counter + 1),
                        ]
                    with m.Else():
                        # 完了
                        m.d.sync += [
                            # Transfer Counter: Disable SCLK
                            transfer_counter.eq(0),
                            sclk_en.eq(0),
                        ]
                        m.next = "DONE"
            with m.State("DONE"):
                # データ出力+フラグ更新
                m.d.sync += [
                    # Stream In: Keep Deny
                    self.stream_mosi.ready.eq(0),
                    # Stream Out: Valid
                    self.stream_miso.valid.eq(1),
                    # Data Reg: Capture miso_reg -> stream_miso
                    self.stream_miso.payload.eq(miso_reg),
                    # Flags: Done
                    self.busy.eq(0),
                    self.done.eq(1),
                ]
                m.next = "IDLE"

        # config
        with m.If(self.wr_cfg):
            m.d.sync += [
                div_counter_th.eq(self.cfg_div_counter_th),
            ]
        return m
