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
        uart = platform.request("uart", 0, dir="-")
        m.submodules.uart_tx_pin = uart_tx_pin = io.Buffer("o", uart.tx)
        m.submodules.uart_rx_pin = uart_rx_pin = io.Buffer("i", uart.rx)
        m.d.comb += [
            # External pins
            uart_tx_pin.o.eq(uart_tx.tx),
            uart_rx.rx.eq(uart_rx_pin.i),
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
        lcd = platform.request("lcd", 0, dir="-")
        m.submodules.lcd_clk = lcd_clk = io.Buffer("o", lcd.clk)
        m.submodules.lcd_hs = lcd_hs = io.Buffer("o", lcd.hs)
        m.submodules.lcd_vs = lcd_vs = io.Buffer("o", lcd.vs)
        m.submodules.lcd_de = lcd_de = io.Buffer("o", lcd.de)
        m.submodules.lcd_backlight = lcd_backlight = io.Buffer(
            "o", platform.request("lcd_backlight", 0, dir="-")
        )

        lcd_r = [io.Buffer("o", r) for r in lcd.r]
        lcd_g = [io.Buffer("o", g) for g in lcd.g]
        lcd_b = [io.Buffer("o", b) for b in lcd.b]
        m.submodules += lcd_r
        m.submodules += lcd_g
        m.submodules += lcd_b
        lcd_r_signals = Cat([r.o for r in lcd_r])
        lcd_g_signals = Cat([g.o for g in lcd_g])
        lcd_b_signals = Cat([b.o for b in lcd_b])
        m.d.comb += [
            vga.en.eq(Const(1)),
            lcd_clk.o.eq(ClockSignal("sync")),
            lcd_hs.o.eq(vga.hsync),
            lcd_vs.o.eq(vga.vsync),
            lcd_de.o.eq(vga.de),
            lcd_r_signals.eq(vga.pixel.r),
            lcd_g_signals.eq(vga.pixel.g),
            lcd_b_signals.eq(vga.pixel.b),
            lcd_backlight.o.eq(vga.backlight),
        ]

        ##################################################################
        # SDCard(SPI Master)

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

        # TODO: SCLK 400kHz以下にする

        sdcard_cs = Signal(1, init=1)
        m.submodules.sdcard = sdcard = platform.request("sd_card_spi", 0, dir="-")
        m.submodules.sdcard_spim = sdcard_spim = SpiMaster(SpiConfig(data_width=8))
        m.d.comb += [
            # External pins (SPI mode: DAT1=NC/DAT2=NC)
            sdcard.dat3.eq(sdcard_cs),  # DAT3/CS
            sdcard.cmd.eq(sdcard_spim.mosi),  # CMD/DMOSI
            sdcard.clk.eq(sdcard_spim.sclk),  # CLK
            sdcard.dat0.eq(sdcard_spim.miso),  # DAT0/MISO
        ]
        sdcard_counter = Signal(SDCARD_CLOCK_CYCLE_WIDTH, reset=0)
        with m.FSM(init="DUMMY_CLK") as sd_fsm:
            with m.State("DUMMY_CLK"):
                with m.If(sdcard_spim.busy):
                    # Wait for 8 dummy clocks
                    m.d.sync += [
                        sdcard_spim.trigger.eq(0),  # trig deassert
                    ]
                with m.Else():
                    with m.If(sdcard_counter < SDCARD_DUMMY_CLOCK_CYCLES):
                        m.d.sync += [
                            # Dummy cyc中は CS=H, MOSI=H 維持
                            sdcard_cs.eq(1),
                            sdcard_spim.din.eq(0xFF),
                            sdcard_spim.trigger.eq(1),
                            # increment counter
                            sdcard_counter.eq(sdcard_counter + 1),
                        ]
                    with m.Else():
                        m.d.sync += [
                            sdcard_counter.eq(0),
                        ]
                        m.next = "CMD0"
            with m.State("CMD0"):
                # TODO: CMD0 GO_IDLE_STATE -> CMD8_SEND_IF_COND -> ACMD41_SEND_OP_COND
                # CMD58 READ OCR
                # CMD16 SET_BLOCKLEN
                # CMD17 READ_SINGLE_BLOCK
                pass

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
