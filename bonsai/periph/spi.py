from dataclasses import dataclass

from amaranth import Module, Signal
from amaranth.build.plat import Platform
from amaranth.lib import wiring, stream
from amaranth.lib.wiring import In, Out
from amaranth.utils import ceil_log2


@dataclass
class SpiConfig:
    """
    SPI Configuration
    当初 ClockPhase, ClockPolarity, ClockDivider, DataOrderの設定を作っていたが、実際使わなそうなので簡略化
    """

    # Data Width
    data_width: int = 8

    def __post_init__(self):
        assert self.data_width > 0, "data_width must be positive"

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
                # for internal
                "en": In(1),
                "din": In(stream.Signature(config.data_width)),
                "dout": Out(stream.Signature(config.data_width)),
                "busy": Out(1),  # status
                "done": Out(1),  # status
                # for external
                "sclk": Out(1),
                "mosi": Out(1),
                "miso": In(1),
            },
            src_loc_at=src_loc_at,
        )

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        # SCLK (SYSCLK/2)
        sclk_cpol0 = Signal(1, init=0)
        sclk_cpol0_riging = Signal(1, init=0)
        sclk_cpol0_falling = Signal(1, init=0)

        sclk_en = Signal(1, init=0)
        with m.If(sclk_en):
            m.d.sync += [
                # Edge detect
                sclk_cpol0_riging.eq(sclk_cpol0 == 0),  # (Current)Low -> High
                sclk_cpol0_falling.eq(sclk_cpol0 == 1),  # (Current)High -> Low
                # Next SCLK
                sclk_cpol0.eq(~sclk_cpol0),
            ]
        with m.Else():
            m.d.sync += [
                # Disable Edge
                sclk_cpol0_riging.eq(0),
                sclk_cpol0_falling.eq(0),
                # Disable SCLK
                sclk_cpol0.eq(0),  # CPOL0: Normally low
            ]
        # MOSI/MISO
        mosi_reg = Signal(self._config.data_width, reset=0)
        miso_reg = Signal(self._config.data_width, reset=0)

        # Transfer FSM
        transfer_counter = Signal(self._config.transfer_counter_width, init=0)
        with m.FSM(init="IDLE") as fsm:
            with m.State("IDLE"):
                # Default
                m.d.sync += [
                    mosi_reg.eq(0),
                    miso_reg.eq(0),
                    transfer_counter.eq(0),
                    sclk_en.eq(0),
                    self.busy.eq(0),
                    self.done.eq(0),
                ]

                # enable & din=valid で開始
                with m.If(self.en & self.din.valid):
                    m.d.sync += [
                        # Stream In: Capture
                        self.din.ready.eq(1),
                        # Stream Out: N/C
                        self.dout.valid.eq(0),
                        # Data Reg: Capture din -> mosi_reg
                        mosi_reg.eq(self.din.payload),
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
                with m.If(sclk_cpol0_riging):
                    # SCLK Rising Edge: サンプリング
                    m.d.sync += [
                        miso_reg.eq(miso_reg << 1 | self.miso),
                    ]
                with m.If(sclk_cpol0_falling):
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
                    # Data Reg: Capture miso_reg -> dout
                    self.dout.eq(miso_reg),
                    # Flags: Done
                    self.busy.eq(0),
                    self.done.eq(1),
                ]
                m.next = "IDLE"

        return m
