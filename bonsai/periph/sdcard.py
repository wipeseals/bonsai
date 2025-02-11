import math
from dataclasses import dataclass
from pickle import STOP

from amaranth import Module, Mux, Signal, unsigned
from amaranth.build.plat import Platform
from amaranth.lib import data, enum, stream, wiring
from amaranth.lib.fifo import SyncFIFO
from amaranth.lib.wiring import In, Out
from amaranth.utils import ceil_log2
from periph.spi import SpiConfig, SpiMaster

# SD Cardのデータ幅
SD_DATA_WIDTH: int = 8
# SD Cardのアドレス(LBA)幅
SD_ADDR_WIDTH: int = 32


@dataclass
class SdCardConfig:
    """
    SD Card Configuration
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
    # SdCardModule <-> SPI Master間のFIFO Depth
    data_stream_fifo_depth: int = 8
    # Command Frame後の待ちbyte最大
    ncr_max_word: int = 8

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
            data_width=SD_DATA_WIDTH,
        )


class SDCardCommand(enum.Enum):
    """
    SD Card Command
    refer.
    - http://elm-chan.org/docs/mmc/mmc.html
    - https://memes.sakura.ne.jp/memes/?page_id=2225

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


class SdCardResponse(enum.Enum):
    """
    SD Card Response
    """

    R1 = 1
    R1b = 2
    R2 = 3
    R3 = 4
    R7 = 5


class SdCardMasterCmd(enum.Enum):
    """
    SdCardMaster制御用コマンド (内部独自)

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


class SdCardMasterReqSignature(wiring.Signature):
    """
    SdCardMaster Request Signature
    """

    def __init__(self):
        super().__init__(
            {
                "cmd": Out(SdCardMasterCmd),
                "addr": Out(unsigned(SD_ADDR_WIDTH)),
                "len": Out(unsigned(SD_ADDR_WIDTH)),
            }
        )


class SdCardMaster(wiring.Component):
    def __init__(self, config: SdCardConfig, *, src_loc_at=0):
        self._config = config
        self._spi_config = config.create_spi_config()
        super().__init__(
            {
                # internal control
                "en": In(1),
                "start": In(1),
                "abort": In(1),
                "req": In(SdCardMasterReqSignature()),
                # internal response/status
                "setup_done": Out(1),
                "setup_error": Out(1),
                "idle": Out(1),
                "busy": Out(1),
                "done": Out(1),
                "wait_data_or_abort": Out(1),
                "error": Out(1),
                # datain/dataout stream
                "wr_stream": In(stream.Signature(SD_DATA_WIDTH)),
                "rd_stream": Out(stream.Signature(SD_DATA_WIDTH)),
                # for SD Card
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
        setup_done = Signal(1, reset=0)

        ##################################################################
        # setup submodules
        spi_cs = Signal(1, init=1)
        m.submodules.spim = spim = SpiMaster(self._spi_config)
        m.submodules.mosi_fifo = mosi_fifo = SyncFIFO(
            width=SD_DATA_WIDTH, depth=self._config.data_stream_fifo_depth
        )
        m.submodules.miso_fifo = miso_fifo = SyncFIFO(
            width=SD_DATA_WIDTH, depth=self._config.data_stream_fifo_depth
        )
        # SdCardMaster -> [[FIFO -> SPI Master]]
        wiring.connect(m, mosi_fifo.r_stream, spim.stream_mosi)
        # SdCardMaster <- [[FIFO <- SPI Master]]
        wiring.connect(m, miso_fifo.w_stream, spim.stream_miso)
        m.d.comb += [
            # External SDCard/SPI
            self.cs.eq(spi_cs),
            self.sclk.eq(spim.sclk),
            self.mosi.eq(spim.mosi),
            spim.miso.eq(self.miso),
            # SPI Master
            spim.en.eq(1),
            spim.wr_cfg.eq(1),
            spim.cfg_div_counter_th.eq(
                Mux(
                    setup_done,
                    self._config.sclk_data_div_count,
                    self._config.sclk_reset_div_count,
                )
            ),
        ]

        return m
