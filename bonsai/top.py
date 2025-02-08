import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from turtle import reset

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
from amaranth.lib import cdc, data, enum, io, stream, wiring
from amaranth.lib.cdc import ResetSynchronizer
from amaranth.lib.wiring import In, Out
from amaranth.utils import ceil_log2
from amaranth_boards.arty_a7 import ArtyA7_35Platform
from amaranth_boards.tang_nano_9k import TangNano9kPlatform
from periph.timer import Timer, TimerMode
from periph.uart import UartConfig, UartRx, UartTx
from periph.video import VgaConfig, VgaOut


class VideoPixelLayout(data.StructLayout):
    def __init__(self, r_width: int, g_width: int, b_width: int):
        super().__init__(
            {
                "r": unsigned(r_width),
                "g": unsigned(g_width),
                "b": unsigned(b_width),
            }
        )


class Top(wiring.Component):
    def __init__(
        self,
        periph_clk_freq: float,
        *,
        src_loc_at=0,
    ):
        self.timer = Timer(clk_freq=periph_clk_freq, default_period_seconds=1.0)
        self.uart_tx = UartTx(config=UartConfig.from_freq(clk_freq=periph_clk_freq))
        self.uart_rx = UartRx(config=UartConfig.from_freq(clk_freq=periph_clk_freq))

        super().__init__(
            {
                "ovf": Out(1),
                "tx": Out(1),
                "rx": In(1),
                "tx_busy": Out(1),
                "rx_busy": Out(1),
            },
            src_loc_at=src_loc_at,
        )

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        m.submodules.timer = self.timer
        m.submodules.uart_tx = self.uart_tx
        m.submodules.uart_rx = self.uart_rx

        # Timer
        m.d.comb += [
            # External
            self.ovf.eq(self.timer.ovf),
            # Internal
            self.timer.en.eq(1),
            self.timer.clr.eq(0),
            self.timer.trig.eq(0),
            self.timer.cmp_count_wr.eq(0),
            self.timer.mode.eq(TimerMode.FREERUN_WITH_CLEAR),
        ]

        # uart loopback
        m.d.comb += [
            # External
            self.uart_rx.rx.eq(self.rx),
            self.tx.eq(self.uart_tx.tx),
            self.tx_busy.eq(self.uart_tx.busy),
            self.rx_busy.eq(self.uart_rx.busy),
            # Internal RX
            self.uart_rx.en.eq(1),
            # Internal TX
            self.uart_tx.en.eq(1),
            # RX->TX Loopback
            self.uart_tx.stream.payload.eq(self.uart_rx.stream.payload),
            self.uart_tx.stream.valid.eq(self.uart_rx.stream.valid),
            self.uart_rx.stream.ready.eq(self.uart_tx.stream.ready),
        ]

        return m


class PlatformTop(Elaboratable):
    def _elabolate_tangnano_9k(self, platform: Platform) -> Module:
        m = Module()

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
            Path("eda/bonsai_tangnano9k/src/gowin_rpll/gowin_rpll.v").read_text(),
        )

        o_clkout = Signal(1)
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
        # Top
        periph_clk_freq = 27e6
        m.submodules.top = Top(
            periph_clk_freq=periph_clk_freq,
        )

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
        top: Top = m.submodules.top

        tx_busy_status = Signal(1)
        rx_busy_status = Signal(1)
        with m.If(top.tx_busy):
            m.d.sync += tx_busy_status.eq(~tx_busy_status)
        with m.If(top.rx_busy):
            m.d.sync += rx_busy_status.eq(~rx_busy_status)

        # Status
        m.d.comb += [
            leds[0].o.eq(top.ovf),
            leds[1].o.eq(tx_busy_status),
            leds[2].o.eq(rx_busy_status),
            leds[3].o.eq(Const(1)),
            leds[4].o.eq(button_data[0]),
            leds[5].o.eq(button_data[1]),
        ]

        uart = platform.request("uart", 0, dir="-")
        uart_tx = io.Buffer("o", uart.tx)
        uart_rx = io.Buffer("i", uart.rx)
        m.submodules += [uart_tx, uart_rx]
        m.d.comb += [
            uart_tx.o.eq(top.tx),
            top.rx.eq(uart_rx.i),
        ]

        return m

    def elaborate(self, platform: Platform) -> Module:
        # Platform specific elaboration
        if isinstance(platform, ArtyA7_35Platform):
            return self._elaborate_arty_a7_35(platform)
        elif isinstance(platform, TangNano9kPlatform):
            return self._elabolate_tangnano_9k(platform)
        else:
            logging.warning(f"Unsupported platform: {platform}")
