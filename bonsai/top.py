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
from amaranth.build.plat import Platform
from amaranth.hdl import IOBufferInstance, IOPort
from amaranth.lib import cdc, data, enum, io, stream, wiring
from amaranth.lib.cdc import ResetSynchronizer
from amaranth.lib.wiring import In, Out
from amaranth.utils import ceil_log2
from amaranth_boards.tang_nano_9k import TangNano9kPlatform
from periph.timer import Timer, TimerMode
from periph.uart import UartConfig, UartRx, UartTx
from periph.video import VgaConfig, VgaOut


class Top(Elaboratable):
    def elaborate(self, platform: Platform) -> Module:
        # TODO: other platform specific logic
        assert isinstance(platform, TangNano9kPlatform), (
            f"Unsupported platform: {platform}"
        )
        periph_clk_freq: float = 27e6

        m = Module()
        m.submodules.timer = timer = Timer(
            clk_freq=periph_clk_freq, default_period_seconds=1.0
        )
        m.submodules.uart_tx = uart_tx = UartTx(
            config=UartConfig.from_freq(clk_freq=periph_clk_freq)
        )
        m.submodules.uart_rx = uart_rx = UartRx(
            config=UartConfig.from_freq(clk_freq=periph_clk_freq)
        )

        ##################################################################
        # Clock Setup

        m.domains += [
            ClockDomain("sync"),
            ClockDomain("core_sync"),
            ClockDomain("video_sync"),
        ]

        # plat.Platform.create_missing_domainで再requestされる暫定対策 TODO: 良い方法あれば置き換え
        platform.default_clk = None
        platform.default_rst = None

        # 内蔵発振器からのクロックをPLLで増幅
        clk27 = platform.request("clk27", 0, dir="-")
        m.submodules.clk27_ibuf = clk27_ibuf = io.Buffer("i", clk27)
        platform.add_file(
            "gowin_rpll.v",
            Path(r"eda/bonsai_tangnano9k/src/gowin_rpll/gowin_rpll.v").read_text(),
        )

        # 132MHz
        o_clkout = Signal(1)
        # 33.333MHz
        o_clkoutd = Signal(1)
        pll_lock = Signal(1)

        m.submodules.rpll = rpll = Instance(
            "Gowin_rPLL",
            i_clkin=ClockSignal("sync"),
            o_clkout=o_clkout,
            o_clkoutd=o_clkoutd,
            o_lock=pll_lock,
        )
        m.d.comb += [
            ClockSignal("sync").eq(clk27_ibuf.i),
            ClockSignal("core_sync").eq(o_clkout),
            ClockSignal("video_sync").eq(o_clkoutd),
        ]
        ##################################################################
        # Timer
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
        # PSRAM W955D8MBYA6I

        # command
        class Cmd(enum.Enum, shape=1):
            WRITE = 0
            READ = 1

        class AddrSpace(enum.Enum, shape=1):
            MEMORY = 0
            REGISTER = 1

        class BurstType(enum.Enum, shape=1):
            WRAP = 0
            REGISTER = 1

        class CommandAddressData(data.Struct):
            def __init__(self):
                super().__init__(
                    {
                        "cmd": Cmd,
                        "addr_space": AddrSpace,
                        "burst_type": BurstType,
                        "row_addr": unsigned(13),
                        "upper_col_addr": unsigned(6),
                        "reserved": unsigned(13),
                        "lower_col_addr": unsigned(3),
                    }
                )

        # PSRAM W955D8MBYA6I が 2つある
        # Chip Select#
        mem_cs_n_0 = Signal(1)
        mem_cs_n_1 = Signal(1)
        # Differential Clock
        mem_clk_0 = o_clkout
        mem_clk_n_0 = ~o_clkout
        mem_clk_1 = o_clkout
        mem_clk_n_1 = ~o_clkout
        # Data Input/Output
        mem_dq_o_0 = Signal(8)
        mem_dq_i_0 = Signal(8)
        mem_dq_oe_0 = Signal(1)
        mem_dq_o_1 = Signal(8)
        mem_dq_i_1 = Signal(8)
        mem_dq_oe_1 = Signal(1)
        # Read Write Data Strobe
        mem_rwds_o_0 = Signal(1)
        mem_rwds_i_0 = Signal(1)
        mem_rwds_en_0 = Signal(1)
        mem_rwds_o_1 = Signal(1)
        mem_rwds_i_1 = Signal(1)
        mem_rwds_en_1 = Signal(1)
        # Hardware Reset#
        mem_reset_n_0 = Signal(1)
        mem_reset_n_1 = Signal(1)

        # mem_ca_data = Signal(CommandAddressData)
        # mem_cmd_0 = mem_ca_data.bit_select(40, 8)
        # mem_cmd_1 = mem_ca_data.bit_select(32, 8)
        # mem_cmd_2 = mem_ca_data.bit_select(24, 8)
        # mem_cmd_3 = mem_ca_data.bit_select(16, 8)
        # mem_cmd_4 = mem_ca_data.bit_select(8, 8)
        # mem_cmd_5 = mem_ca_data.bit_select(0, 8)

        # for GN1NR-9C internal PSRAM
        # 規定の名前でTopに出しておくと合成されるらしい

        # output [1:0] O_psram_cs_n
        m.submodules.O_psram_cs_n = O_psram_cs_n = io.Buffer(
            "o",
            io.SingleEndedPort(
                IOPort(2, name="O_psram_cs_n"), direction=io.Direction.Output
            ),
        )
        # # output [1:0] O_psram_ck
        # # output [1:0] O_psram_ck_n
        # m.submodules.O_psram_ck = O_psram_ck = io.Buffer(
        #     "o",
        #     io.DifferentialPort(
        #         p=IOPort(2, name="O_psram_ck"),
        #         n=IOPort(2, name="O_psram_ck_n"),
        #         direction=io.Direction.Output,
        #     ),
        # )
        # # inout [15:0] IO_psram_dq
        # m.submodules.IO_psram_dq = IO_psram_dq = io.Buffer(
        #     "io",
        #     io.SingleEndedPort(
        #         IOPort(16, name="IO_psram_dq"), direction=io.Direction.Bidir
        #     ),
        # )
        # # inout [1:0] IO_psram_rwds
        # m.submodules.IO_psram_rwds = IO_psram_rwds = io.Buffer(
        #     "io",
        #     io.SingleEndedPort(
        #         IOPort(2, name="IO_psram_rwds"), direction=io.Direction.Bidir
        #     ),
        # )
        # # output [1:0] O_psram_reset_n
        # m.submodules.O_psram_reset_n = O_psram_reset_n = io.Buffer(
        #     "o",
        #     io.SingleEndedPort(
        #         IOPort(2, name="O_psram_reset_n"), direction=io.Direction.Output
        #     ),
        # )

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
            lcd_clk.o.eq(ClockSignal("video_sync")),
            lcd_hs.o.eq(vga.hsync),
            lcd_vs.o.eq(vga.vsync),
            lcd_de.o.eq(vga.de),
            lcd_r_signals.eq(vga.pixel.r),
            lcd_g_signals.eq(vga.pixel.g),
            lcd_b_signals.eq(vga.pixel.b),
            lcd_backlight.o.eq(vga.backlight),
        ]

        ##################################################################
        # LED/Button
        NUM_LED = 6
        leds = [
            io.Buffer("o", platform.request("led", i, dir="-")) for i in range(NUM_LED)
        ]
        NUM_BUTTON = 2
        buttons = [
            io.Buffer("i", platform.request("button", i, dir="-"))
            for i in range(NUM_BUTTON)
        ]
        button_data = Cat([button.i for button in buttons])
        m.submodules += leds + buttons

        # Status
        m.d.comb += [
            leds[0].o.eq(timer_toggle_sig),
            leds[1].o.eq(~timer_toggle_sig),
            leds[2].o.eq(Const(0)),
            leds[3].o.eq(Const(1)),
            leds[4].o.eq(button_data[0]),
            leds[5].o.eq(button_data[1]),
        ]

        return m
