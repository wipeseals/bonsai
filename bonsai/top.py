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
from periph.uart import UartConfig, UartTx


class VideoPixelLayout(data.StructLayout):
    def __init__(self, r_width: int, g_width: int, b_width: int):
        super().__init__(
            {
                "r": unsigned(r_width),
                "g": unsigned(g_width),
                "b": unsigned(b_width),
            }
        )


@dataclass
class VgaConfig:
    """
    VGA timing parameters
    """

    # pixel width
    width: int
    # pixel height
    height: int

    # pixel data format
    pixel_layout: VideoPixelLayout

    # front porch (horizontal)
    h_front_porch: int
    # pulse width (horizontal sync)
    h_pulse: int
    # back porch (horizontal)
    h_back_porch: int

    # front porch (vertical)
    v_front_porch: int
    # pulse width (vertical sync)
    v_pulse: int
    # back porch (vertical)
    v_back_porch: int

    @property
    def hsync_start(self) -> int:
        """
        HSYNC start offset
        """
        return self.h_front_porch

    @property
    def hsync_end(self) -> int:
        """
        HSYNC end offset
        """
        return self.h_front_porch + self.h_pulse

    @property
    def vsync_start(self) -> int:
        """
        VSYNC start offset
        """
        return self.v_front_porch

    @property
    def vsync_end(self) -> int:
        """
        VSYNC end offset
        """
        return self.v_front_porch + self.v_pulse

    @property
    def hdata_start(self) -> int:
        """
        データの開始位置 (水平方向)
        """
        return self.h_front_porch + self.h_pulse + self.h_back_porch

    @property
    def vdata_start(self) -> int:
        """
        データの開始位置 (垂直方向)
        """
        return self.v_front_porch + self.v_pulse + self.v_back_porch

    @property
    def hdata_end(self) -> int:
        """
        幅方向の合計ピクセル数 (フロントポーチ、バックポーチ、同期パルスを含む)
        """
        return self.width + self.h_front_porch + self.h_back_porch + self.h_pulse

    @property
    def vdata_end(self) -> int:
        """
        高さ方向の合計ピクセル数 (フロントポーチ、バックポーチ、同期パルスを含む)
        """
        return self.height + self.v_front_porch + self.v_back_porch + self.v_pulse

    @property
    def h_counter_width(self) -> int:
        """
        水平カウンタのビット幅
        """
        return int(ceil_log2(self.hdata_end))

    @property
    def v_counter_width(self) -> int:
        """
        垂直カウンタのビット幅
        """
        return int(ceil_log2(self.vdata_end))


class VgaOut(wiring.Component):
    def __init__(self, config: VgaConfig, domain: str = "video_sync", *, src_loc_at=0):
        self.config = config
        super().__init__(
            {
                "en": In(1),
                "de": Out(1),
                "hsync": Out(1),
                "vsync": Out(1),
                "pixel": Out(config.pixel_layout),
                "pos_x": Out(config.h_counter_width),
                "pos_y": Out(config.v_counter_width),
                "backlight": Out(1),
            },
            src_loc_at=src_loc_at,
        )

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        # 現在位置 (VGA信号中のcyc)
        h_counter = Signal(self.config.h_counter_width)
        # 現在位置Y (VGA信号中のline)
        v_counter = Signal(self.config.v_counter_width)
        # 現在位置が有効な描画範囲なら1
        data_valid = Signal(1, reset=0)
        # 有効なデータ範囲であれば、そのX座標
        pos_x = Signal(self.config.h_counter_width, reset=0)
        # 有効なデータ範囲であれば、そのY座標
        pos_y = Signal(self.config.v_counter_width, reset=0)

        # 現在のカウントから有効な信号を生成
        m.d.comb += [
            # 水平垂直同期
            # [front-porch, pulse, back-porch] の範囲で有効。負論理
            self.hsync.eq(
                ~(
                    (self.config.hsync_start <= h_counter)
                    & (h_counter < self.config.hsync_end)
                )
            ),
            self.vsync.eq(
                ~(
                    (self.config.vsync_start <= v_counter)
                    & (v_counter < self.config.vsync_end)
                )
            ),
            # データ有効範囲
            # [back-porch, data, (next)front-porch] の範囲で有効
            data_valid.eq(
                (self.config.hdata_start <= h_counter)
                & (h_counter < self.config.hdata_end)
                & (self.config.vdata_start <= v_counter)
                & (v_counter < self.config.vdata_end)
            ),
            self.de.eq(data_valid),
            # データ位置
            pos_x.eq(Mux(data_valid, h_counter - self.config.hdata_start, 0)),
            pos_y.eq(Mux(data_valid, v_counter - self.config.vdata_start, 0)),
            self.pos_x.eq(pos_x),
            self.pos_y.eq(pos_y),
            # enならBacklight on (調光ができるならあってもいいかも)
            self.backlight.eq(self.en),
        ]

        # test data pattern
        m.d.comb += [
            self.pixel.r.eq(pos_x),
            self.pixel.g.eq(pos_y),
            self.pixel.b.eq(pos_x + pos_y),
        ]

        # for vertical { for horizontal }
        with m.If(self.en):
            # Horizontal counter
            with m.If(h_counter < self.config.hdata_end - 1):
                m.d.video_sync += h_counter.eq(h_counter + 1)
            with m.Else():
                m.d.video_sync += h_counter.eq(0)
                # Vertical counter
                with m.If(v_counter < self.config.vdata_end - 1):
                    m.d.video_sync += v_counter.eq(v_counter + 1)
                with m.Else():
                    m.d.video_sync += v_counter.eq(0)
        with m.Else():
            # Reset counter & sync invalid
            m.d.video_sync += [h_counter.eq(0), v_counter.eq(0)]

        return m


class Top(wiring.Component):
    def __init__(
        self,
        clk_freq: float,
        period_sec: float = 1.0,
        baud_rate: int = 115200,
        *,
        src_loc_at=0,
    ):
        self.timer = Timer(clk_freq=clk_freq, default_period_seconds=period_sec)
        uart_config = UartConfig(clk_freq=clk_freq, baud_rate=baud_rate)
        self.uart_tx = UartTx(config=uart_config)

        super().__init__(
            {
                "ovf": Out(1),
                "tx": Out(1),
            },
            src_loc_at=src_loc_at,
        )

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        m.submodules.timer = self.timer
        m.submodules.uart_tx = self.uart_tx

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

        # uart_tx test
        char_start = ord(" ")
        char_end = ord("~")
        tx_data = Signal(8, reset=0)
        with m.If(self.uart_tx.stream.ready):
            with m.If(tx_data < char_end):
                m.d.sync += tx_data.eq(tx_data + 1)
            with m.Else():
                m.d.sync += tx_data.eq(char_start)
        m.d.comb += [
            # External
            self.tx.eq(self.uart_tx.tx),
            # Internal
            self.uart_tx.stream.valid.eq(1),
            self.uart_tx.stream.payload.eq(tx_data),
            self.uart_tx.en.eq(1),
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

        uart = platform.request("uart", 0, dir="-")
        uart_tx = io.Buffer("o", uart.tx)
        m.submodules += [uart_tx]
        m.d.comb += [
            uart_tx.o.eq(top.tx),
        ]

    def _elabolate_tangnano_9k(self, m: Module, platform: Platform):
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
            ClockSignal("video_sync").eq(clk27_ibuf.i),  # .eq(o_clkoutd),
        ]

        ##################################################################
        # VGA
        # https://wiki.sipeed.com/hardware/en/tang/Tang-Nano-9K/examples/rgb_screen.html
        # https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/204/104990583_Web.pdf
        vga_config = VgaConfig(
            width=800,
            height=480,
            pixel_layout=VideoPixelLayout(5, 6, 5),
            h_front_porch=210,
            h_pulse=1,
            h_back_porch=182,
            v_front_porch=45,
            v_pulse=5,
            v_back_porch=0,
        )
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

        COUNTER_WIDTH = NUM_LED
        counter = Signal(COUNTER_WIDTH)
        with m.If(top.ovf):
            m.d.sync += counter.eq(counter + 1 + button_data)
        # 各bitをLEDに割当
        for i, led in enumerate(leds):
            m.d.comb += [led.o.eq(counter[i])]

        uart = platform.request("uart", 0, dir="-")
        uart_tx = io.Buffer("o", uart.tx)
        m.submodules += [uart_tx]
        m.d.comb += [
            uart_tx.o.eq(top.tx),
        ]

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        m.submodules.top = Top(platform.default_clk_frequency, period_sec=1.0)

        # Platform specific elaboration
        if isinstance(platform, ArtyA7_35Platform):
            self._elaborate_arty_a7_35(m, platform)
        elif isinstance(platform, TangNano9kPlatform):
            self._elabolate_tangnano_9k(m, platform)
        else:
            logging.warning(f"Unsupported platform: {platform}")

        return m
