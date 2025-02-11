import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from turtle import reset
from typing import Any, Dict

from amaranth import (
    Cat,
    ClockDomain,
    ClockSignal,
    Const,
    Elaboratable,
    Instance,
    Module,
    Mux,
    Signal,
    unsigned,
)
from amaranth.build import Resource
from amaranth.build.dsl import Attrs, Pins, Subsignal
from amaranth.build.plat import Platform
from amaranth.hdl import IOBufferInstance, IOPort
from amaranth.lib import cdc, data, enum, io, stream, wiring
from amaranth.lib.cdc import ResetSynchronizer
from amaranth.lib.fifo import SyncFIFO
from amaranth.lib.wiring import In, Out
from amaranth.utils import ceil_log2
from amaranth_boards.tang_nano_9k import TangNano9kPlatform
from periph.gpio import Gpi, Gpo
from periph.spi import SpiConfig, SpiMaster
from periph.timer import Timer, TimerMode
from periph.uart import UartConfig, UartRx, UartTx
from periph.video import VgaConfig, VgaOut


class Top(wiring.Component):
    def __init__(self):
        super().__init__(
            {
                # magic wire names for Internal PSRAM
                "O_psram_cs_n": Out(2),
                "O_psram_ck": Out(2),
                "O_psram_ck_n": Out(2),
                "IO_psram_dq": In(16),
                "IO_psram_rwds": In(2),
                "O_psram_reset_n": Out(2),
            }
        )

    def elaborate(self, platform: Platform) -> Module:
        # TODO: other platform specific logic
        assert isinstance(platform, TangNano9kPlatform), (
            f"Unsupported platform: {platform}"
        )

        # TODO: PLL使うときに調整・取得
        DEFAULT_CLK_FREQ: float = 27e6
        NUM_LED = 6
        NUM_BUTTON = 2

        m = Module()

        ##################################################################
        # Timer
        m.submodules.timer = timer = Timer(
            clk_freq=DEFAULT_CLK_FREQ, default_period_seconds=1.0
        )
        timer_toggle_sig = Signal(1, 0)
        with m.If(timer.ovf):
            m.d.sync += timer_toggle_sig.eq(~timer_toggle_sig)
        m.d.comb += [
            # Internal
            timer.en.eq(1),
            timer.clr.eq(0),
            timer.trig.eq(0),
            timer.cmp_count_wr.eq(0),
            timer.mode.eq(TimerMode.FREERUN_WITH_CLEAR),
        ]

        ##################################################################
        # uart loopback
        m.submodules.uart_tx = uart_tx = UartTx(
            config=UartConfig.from_freq(clk_freq=DEFAULT_CLK_FREQ)
        )
        m.submodules.uart_rx = uart_rx = UartRx(
            config=UartConfig.from_freq(clk_freq=DEFAULT_CLK_FREQ)
        )
        uart_pins = platform.request("uart", 0, dir="-")
        m.submodules.uart_pin_tx = uart_pin_buf_tx = io.Buffer("o", uart_pins.tx)
        m.submodules.uart_pin_rx = uart_pin_buf_rx = io.Buffer("i", uart_pins.rx)
        m.d.comb += [
            # External pins
            uart_pin_buf_tx.o.eq(uart_tx.tx),
            uart_rx.rx.eq(uart_pin_buf_rx.i),
            # Internal RX
            uart_rx.en.eq(1),
            # Internal TX
            uart_tx.en.eq(1),
            # RX->TX Loopback
            uart_tx.stream.payload.eq(uart_rx.stream.payload),
            uart_tx.stream.valid.eq(uart_rx.stream.valid),
            uart_rx.stream.ready.eq(uart_tx.stream.ready),
        ]

        ##################################################################
        # VGA
        # https://wiki.sipeed.com/hardware/en/tang/Tang-Nano-9K/examples/rgb_screen.html
        # https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/204/104990583_Web.pdf
        vga_config = VgaConfig.preset_tangnano9k_800x480()
        m.submodules.vga = vga = VgaOut(config=vga_config)
        lcd_pins = platform.request("lcd", 0, dir="-")
        m.submodules.lcd_pin_buf_clk = lcd_pin_buf_clk = io.Buffer("o", lcd_pins.clk)
        m.submodules.lcd_pin_buf_hs = lcd_pin_buf_hs = io.Buffer("o", lcd_pins.hs)
        m.submodules.lcd_pin_buf_vs = lcd_pin_buf_vs = io.Buffer("o", lcd_pins.vs)
        m.submodules.lcd_pin_buf_de = lcd_pin_buf_de = io.Buffer("o", lcd_pins.de)
        m.submodules.lcd_pin_buf_backlight = lcd_pin_buf_backlight = io.Buffer(
            "o", platform.request("lcd_backlight", 0, dir="-")
        )

        lcd_pin_r = [io.Buffer("o", r) for r in lcd_pins.r]
        lcd_pin_g = [io.Buffer("o", g) for g in lcd_pins.g]
        lcd_pin_b = [io.Buffer("o", b) for b in lcd_pins.b]
        m.submodules += lcd_pin_r
        m.submodules += lcd_pin_g
        m.submodules += lcd_pin_b
        lcd_r_signals = Cat([r.o for r in lcd_pin_r])
        lcd_g_signals = Cat([g.o for g in lcd_pin_g])
        lcd_b_signals = Cat([b.o for b in lcd_pin_b])
        m.d.comb += [
            vga.en.eq(Const(1)),
            lcd_pin_buf_clk.o.eq(ClockSignal("sync")),
            lcd_pin_buf_hs.o.eq(vga.hsync),
            lcd_pin_buf_vs.o.eq(vga.vsync),
            lcd_pin_buf_de.o.eq(vga.de),
            lcd_r_signals.eq(vga.pixel.r),
            lcd_g_signals.eq(vga.pixel.g),
            lcd_b_signals.eq(vga.pixel.b),
            lcd_pin_buf_backlight.o.eq(vga.backlight),
        ]

        ##################################################################
        # SDCard(SPI Master)

        # SPI Modeの1トランザクションあたりのビット幅
        SDCARD_SPI_DATA_WIDTH = 8
        # ひとまず最低速度
        SDCARD_SPI_SCLK_FREQ = 400e3
        # N_cr (Command+Argument+CRC)送信後、応答待ちのbyte数 (可変)
        SDCARD_SPI_RX_PAYLOAD_MAX_WORD = 8
        # min 74 clk + wait 1ms. 1あたり8bit転送待つので十分なはず
        SDCARD_DUMMY_CLOCK_CYCLES = 500
        SDCARD_CLOCK_CYCLE_WIDTH = ceil_log2(SDCARD_DUMMY_CLOCK_CYCLES)
        # TX Payload = 6byte {2'b01, cmd[5:0], arg[31:0], crc[6:0], 1'b1}
        SDCARD_SPI_TX_PAYLOAD_WORD = 6
        # RX Payload = 1byte (R1) { 1'b0, param_err, addr_err, erase_seq_err, com_crc_err, illegal_cmd, erase_state, in_idle_state }
        SDCARD_SPI_RX_R1_PAYLOAD_WORD = 1
        # RX Payload = 5byte (R3/R7) { R1, operation_condition[31:0] }
        SDCARD_SPI_RX_R3_PAYLOAD_WORD = 5

        class SDCardCommand(enum.Enum):
            CMD0_GO_IDLE_STATE = 0x40  # CRC need
            CMD1_RESET_STATE = 0x48
            CMD8_SEND_IF_COND = 0x48  # CRC need
            CMD16_SET_BLOCKLEN = 0x50
            CMD17_READ_SINGLE_BLOCK = 0x51
            CMD24_WRITE_SINGLE_BLOCK = 0x58
            CMD55_APP_CMD = 0x77
            CMD58_READ_OCR = 0x7A
            ACMD41_SEND_OP_COND = 0x69

        # SD Card pin resouces
        sdcard_cs = Signal(1, init=1)
        sdcard_pins = platform.request("sd_card_spi", 0, dir="-")
        m.submodules.sdcard_pin_buf_cs = sdcard_pin_buf_cs = io.Buffer(
            "o", sdcard_pins.cs
        )
        m.submodules.sdcard_pin_buf_clk = sdcard_pin_buf_clk = io.Buffer(
            "o", sdcard_pins.clk
        )
        m.submodules.sdcard_pin_buf_copi = sdcard_pin_buf_copi = io.Buffer(
            "o", sdcard_pins.copi
        )
        m.submodules.sdcard_pin_cipo = sdcard_pin_cipo = io.Buffer(
            "i", sdcard_pins.cipo
        )
        # HDL Module & Stream
        m.submodules.sdcard_spim = sdcard_spim = SpiMaster(
            SpiConfig(
                stream_clk_freq=DEFAULT_CLK_FREQ,
                sclk_freq=SDCARD_SPI_SCLK_FREQ,
                data_width=8,
            )
        )
        m.submodules.sdcard_mosi_fifo = sdcard_mosi_fifo = SyncFIFO(
            width=SDCARD_SPI_DATA_WIDTH, depth=SDCARD_SPI_TX_PAYLOAD_WORD
        )
        m.submodules.sdcard_miso_fifo = sdcard_miso_fifo = SyncFIFO(
            width=SDCARD_SPI_DATA_WIDTH, depth=SDCARD_SPI_TX_PAYLOAD_WORD
        )
        sdcard_mosi_fifo_empty = sdcard_mosi_fifo.w_level == 0  # Idle (next action)
        sdcard_miso_fifo_empty = sdcard_miso_fifo.r_level == 0  # need to wait
        # Connection
        m.d.comb += [
            # External pins (SPI mode: DAT1=NC/DAT2=NC)
            sdcard_pin_buf_cs.o.eq(sdcard_cs),  # DAT3/CS
            sdcard_pin_buf_clk.o.eq(sdcard_spim.sclk),  # CLK
            sdcard_pin_buf_copi.o.eq(sdcard_spim.mosi),  # CMD/DMOSI
            sdcard_spim.miso.eq(sdcard_pin_cipo.i),  # DAT0/MISO
            # Internal SPI Master
            sdcard_spim.en.eq(1),
            sdcard_spim.wr_cfg.eq(0),  # div_counter_th固定
        ]
        wiring.connect(sdcard_spim.stream_mosi, sdcard_mosi_fifo.r_stream)
        wiring.connect(sdcard_miso_fifo.w_stream, sdcard_spim.stream_miso)

        ##################################################################
        # GPIO (LED/Button)

        m.submodules.button_in = button_in = Gpi(width=NUM_BUTTON)
        buttons = [
            io.Buffer("i", platform.request("button", i, dir="-"))
            for i in range(NUM_BUTTON)
        ]
        m.submodules += buttons
        m.d.comb += [
            # enable
            button_in.req.eq(1),
            # Button -> GPI
            button_in.pinin[0].eq(buttons[0].i),
            button_in.pinin[1].eq(buttons[1].i),
        ]

        m.submodules.led_out = led_out = Gpo(width=NUM_LED, init_data=0x3F)
        leds = [
            io.Buffer("o", platform.request("led", i, dir="-")) for i in range(NUM_LED)
        ]
        m.submodules += leds
        m.d.comb += [
            # enable
            led_out.req.eq(1),
            # GPI -> GPO
            led_out.datain[0].eq(timer_toggle_sig),
            led_out.datain[1].eq(~timer_toggle_sig),
            led_out.datain[2].eq(Const(0)),
            led_out.datain[3].eq(Const(1)),
            led_out.datain[4].eq(button_in.dataout[0]),
            led_out.datain[5].eq(button_in.dataout[1]),
            # GPO -> LED
            leds[0].o.eq(led_out.pinout[0]),
            leds[1].o.eq(led_out.pinout[1]),
            leds[2].o.eq(led_out.pinout[2]),
            leds[3].o.eq(led_out.pinout[3]),
            leds[4].o.eq(led_out.pinout[4]),
            leds[5].o.eq(led_out.pinout[5]),
        ]

        return m
