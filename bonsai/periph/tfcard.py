import cmd
import math
from dataclasses import dataclass
from pickle import STOP

from amaranth import Cat, Const, Module, Mux, Signal, unsigned
from amaranth.build.plat import Platform
from amaranth.hdl import Assert
from amaranth.lib import data, enum, stream, wiring
from amaranth.lib.fifo import SyncFIFO
from amaranth.lib.wiring import In, Out
from amaranth.utils import ceil_log2
from periph.spi import SpiConfig, SpiMaster

# TF Card Address Width
TF_ADDR_WIDTH: int = 32


@dataclass
class TfCardConfig:
    """
    TF Card Configuration
    """

    # System側のクロック周波数
    system_clk_freq: float
    # SPI SCLK 転送時周波数
    sclk_data_freq: float = 400e3  # TODO: 20MHz程度に高速化
    # SPI SCLK の リセット中周波数
    sclk_reset_freq: float = 400e3
    # setup時のRetry回数上限
    setup_retry_max: int = 100
    # setup時のDummy cycle数
    setup_dummy_cycles: int = 100
    # TfCardModule <-> SPI Master間のFIFO Depth
    data_stream_fifo_depth: int = 8
    # Command Frame後の待ちbyte最大
    ncr_max_word: int = 8 + 1

    @property
    def sclk_data_div_count(self) -> int:
        """
        SCLKのクロック分周比
        """
        return SpiConfig.sclk_div_count_from_freq(
            system_clk_freq=self.system_clk_freq,
            sclk_freq=self.sclk_data_freq,
        )

    @property
    def sclk_reset_div_count(self) -> int:
        """
        SCLKのクロック分周比
        """
        return SpiConfig.sclk_div_count_from_freq(
            system_clk_freq=self.system_clk_freq,
            sclk_freq=self.sclk_reset_freq,
        )

    @property
    def setup_dummy_bytes(self) -> int:
        """
        setup_dummy_cyclesに対応するbyte数
        """
        return math.ceil(self.setup_dummy_cycles / 8)

    def create_spi_config(self) -> SpiConfig:
        """
        SPI Configurationを生成
        """
        return SpiConfig(
            system_clk_freq=self.system_clk_freq,
            # 分周比がきつい遅い方に合わせておく
            sclk_freq=min(self.sclk_data_freq, self.sclk_reset_freq),
            data_width=8,
        )


class TfCardCommand(enum.Enum):
    """
    TF Card Command
    """

    CMD0_GO_IDLE_STATE = 0x40  # CRC need
    CMD1_SEND_OP_COND = 0x48
    ACMD41_SEND_OP_COND = 0x69
    CMD8_SEND_IF_COND = 0x48  # CRC need
    CMD9_SEND_CSD = 0x48
    CMD10_SEND_CID = 0x48
    CMD12_STOP_TRANSMISSION = 0x4C
    CMD13_SEND_STATUS = 0x4D
    CMD16_SET_BLOCKLEN = 0x50
    CMD17_READ_SINGLE_BLOCK = 0x51
    CMD18_READ_MULTIPLE_BLOCK = 0x52
    CMD23_SET_BLOCK_COUNT = 0x57
    ACMD23_SET_WR_BLK_ERASE_COUNT = 0x57
    CMD24_WRITE_SINGLE_BLOCK = 0x58
    CMD25_WRITE_MULTIPLE_BLOCK = 0x59
    CMD55_APP_CMD = 0x77
    CMD58_READ_OCR = 0x7A


class TfCardResponse(enum.Enum):
    """
    TF Card Response
    """

    R1 = 1
    R1b = 2
    R2 = 3
    R3 = 4
    R7 = 5


class TfCardMasterCmd(enum.Enum):
    """
    TfCardMaster制御用コマンド (内部独自)

    コマンドシーケンス例:
    - Single Block Read
        1. SINGLE_BLOCK_READ
    - Single Block Write
        1. SINGLE_BLOCK_WRITE
    - Multi Block Read
        1. MULTI_BLOCK_READ
        2. STOP
    - Multi Block Write
        1. MULTI_BLOCK_WRITE
        2. STOP
    """

    IDLE = 0
    RESET = 1
    STOP_MULTI_CMD = 2
    SINGLE_BLOCK_READ = 3
    SINGLE_BLOCK_WRITE = 4
    MULTI_BLOCK_READ = 5
    MULTI_BLOCK_WRITE = 6
    READ_CSD = 7
    READ_CID = 8


class TfCardMasterReqSignature(wiring.Signature):
    """
    TfCardMaster Request Signature
    """

    def __init__(self):
        super().__init__(
            {
                "cmd": Out(TfCardMasterCmd),
                "addr": Out(TF_ADDR_WIDTH),
                "len": Out(TF_ADDR_WIDTH),
            }
        )


class TfCardMaster(wiring.Component):
    def __init__(self, config: TfCardConfig, *, src_loc_at=0):
        self._config = config
        self._spi_config = config.create_spi_config()
        super().__init__(
            {
                # internal control
                "en": In(1),
                "start": In(1),
                "abort": In(1),
                "req": In(TfCardMasterReqSignature()),
                # internal response/status
                "setup_done": Out(1),
                "setup_error": Out(1),
                "idle": Out(1),
                "busy": Out(1),
                "done": Out(1),
                "wait_data_or_abort": Out(1),
                "error": Out(1),
                "latest_resp": Out(8),  # for check error
                # datain/dataout stream
                "wr_stream": In(stream.Signature(8)),
                "rd_stream": Out(stream.Signature(8)),
                # for TF Card
                "cs": Out(1),  # only support single device
                "mosi": Out(1),
                "miso": In(1),
                "sclk": Out(1),
            },
            src_loc_at=src_loc_at,
        )

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        ##################################################################
        # control signals
        spi_cs = Signal(1, init=1)
        setup_done = Signal(1, init=0)
        setup_error = Signal(1, init=0)
        done = Signal(1, init=0)
        wait_data_or_abort = Signal(1, init=0)
        error = Signal(1, init=0)
        latest_resp = Signal(8, init=0xFF)

        ##################################################################
        # setup submodules
        m.submodules.spim = spim = SpiMaster(self._spi_config)
        m.submodules.mosi_fifo = mosi_fifo = SyncFIFO(
            width=8, depth=self._config.data_stream_fifo_depth
        )
        m.submodules.miso_fifo = miso_fifo = SyncFIFO(
            width=8, depth=self._config.data_stream_fifo_depth
        )
        # TfCardMaster -> [[FIFO -> SPI Master]]
        wiring.connect(m, mosi_fifo.r_stream, spim.stream_mosi)
        # TfCardMaster <- [[FIFO <- SPI Master]]
        wiring.connect(m, miso_fifo.w_stream, spim.stream_miso)
        m.d.comb += [
            # External TfCard/SPI
            self.cs.eq(spi_cs),
            self.sclk.eq(spim.sclk),
            self.mosi.eq(spim.mosi),
            spim.miso.eq(self.miso),
            # SPI Master:  setup完了まではsclk低速(for dummycyc)
            spim.en.eq(1),
            spim.wr_cfg.eq(1),
            spim.cfg_div_counter_th.eq(
                Mux(
                    setup_done,
                    self._config.sclk_data_div_count,
                    self._config.sclk_reset_div_count,
                )
            ),
            # Internal Status
            self.setup_done.eq(setup_done),
            self.setup_error.eq(setup_error),
            self.idle.eq(spi_cs),
            self.busy.eq(~spi_cs),
            self.done.eq(done),
            self.wait_data_or_abort.eq(wait_data_or_abort),
            self.error.eq(error),
            self.latest_resp.eq(latest_resp),
        ]

        ##################################################################
        # Dummy Cycle (DC) Driver
        req_dc = Signal(1, reset=0)
        done_dc = Signal(1, reset=0)
        counter_dc = Signal(TF_ADDR_WIDTH, reset=0)
        # req_dcがなければ完全無効とし、別driverがfifo操作できるようにする
        # 完了時に自発クリアされる
        with m.If(req_dc):
            with m.FSM(init="IDLE") as fsm:
                with m.State("IDLE"):
                    # Initial State
                    m.d.sync += [
                        # FSM control signal
                        # (同一domain上位ブロックからの制御待ち)
                        # counter: reset
                        counter_dc.eq(0),
                        # cs: deassert
                        spi_cs.eq(1),
                        # tx: disable
                        mosi_fifo.w_en.eq(0),
                        mosi_fifo.w_data.eq(0xFF),
                        # rx: disable
                        miso_fifo.r_en.eq(0),
                    ]
                    # 要求が来てかつ完了レジスタクリアされていなければ開始
                    with m.If(req_dc & ~done_dc):
                        m.next = "START"
                with m.State("START"):
                    # 0xffを送信し続け、全データを読み捨て
                    m.d.sync += [
                        # counter: reset
                        counter_dc.eq(0),
                        # cs: deassert (dummy cycではassertしない)
                        spi_cs.eq(1),
                        # tx: send 0xFF
                        mosi_fifo.w_en.eq(1),
                        mosi_fifo.w_data.eq(0xFF),
                        # rx: read and discard
                        miso_fifo.r_en.eq(1),
                    ]
                    m.next = "XFER"
                with m.State("XFER"):
                    # tx: 規定回数送る
                    with m.If(
                        mosi_fifo.w_rdy
                        & (counter_dc < self._config.setup_dummy_bytes - 1)
                    ):
                        m.d.sync += [
                            counter_dc.eq(counter_dc + 1),
                        ]

                    # rx: Dummy Send & Flushチェック
                    #  - 送りきった & TX FIFOが空 & spimがbusyでない & RX FIFOが空
                    is_sending = counter_dc < self._config.setup_dummy_bytes - 1
                    is_busy_mosi_fifo = mosi_fifo.w_level > 0
                    is_busy_spim = spim.busy
                    is_busy_miso_fifo = miso_fifo.r_level > 0
                    with m.If(
                        ~is_sending
                        & ~is_busy_mosi_fifo
                        & ~is_busy_spim
                        & ~is_busy_miso_fifo
                    ):
                        # 完了レジスタを立てて終わり
                        m.d.sync += [
                            # FSM control signal
                            req_dc.eq(0),  # 次cycではFSMごと無効化される
                            done_dc.eq(1),
                            # counter: reset
                            counter_dc.eq(0),
                            # cs: deassert
                            spi_cs.eq(1),
                            # tx: disable
                            mosi_fifo.w_en.eq(0),
                            mosi_fifo.w_data.eq(0xFF),
                            # rx: disable
                            miso_fifo.r_en.eq(0),
                        ]
                        m.next = "IDLE"

        ##################################################################
        # Command Transfer Logic

        # MOSIへのデータ転送をCommand Frame単位でまとめて行う向け
        # - Command Frame: [CMD, ARG, CRC]
        CMD_FRAME_BYTES = 6
        cmd_data = Signal(6, init=0)
        cmd_args = Signal(4 * 8, init=0)
        cmd_crc = Signal(7, init=0)
        cmd_frame_data = Cat(
            Const(0b01, shape=2), cmd_data, cmd_args, cmd_crc, Const(1, shape=1)
        )
        assert cmd_frame_data.shape().width == 8 * CMD_FRAME_BYTES, (
            "Invalid CMD_FRAME_BYTES"
        )
        cmd_tx_counter = Signal(ceil_log2(8), init=0)
        tx_data_cmd_frame = cmd_frame_data.word_select(cmd_tx_counter, width=8)

        return m
