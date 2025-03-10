from dataclasses import dataclass

from amaranth import (
    Module,
)
from amaranth.build.plat import Platform
from amaranth.lib import wiring
from bus import WbConfig


@dataclass
class CoreConfig:
    """
    RISC-V Core configuration
    """

    # 動作周波数
    clk_freq: float
    # Wishbone Busの設定
    wb_cfg: WbConfig = WbConfig(
        port_size=32,
        granularity=32,
        support_stall_i=True,
    )
    # ITCMサイズ
    itcm_size: int = 2048
    # DTCMサイズ
    dtcm_size: int = 2048
    # プロセッサID取得時に返す値
    cpu_id: int = 0xC0FF_EE00
    # Uart TX/RXのBaudRate
    uart_baudrate: int = 115200


class Core(wiring.Component):
    def __init__(self):
        super().__init__(
            {
                # Expansion Bus Master
            }
        )

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        # TODO:
        return m
