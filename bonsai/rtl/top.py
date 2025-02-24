
from amaranth import (
    Cat,
    ClockSignal,
    Const,
    Module,
    Signal,
)
from amaranth.build.plat import Platform
from amaranth.lib import io, wiring
from amaranth.lib.wiring import In, Out
from amaranth_boards.tang_nano_9k import TangNano9kPlatform
from rtl.periph.gpio import Gpi, Gpo
from rtl.periph.spi import SpiConfig, SpiMaster
from rtl.periph.timer import Timer, TimerMode
from rtl.periph.uart import UartConfig, UartRx, UartTx
from rtl.periph.video import VgaConfig, VgaOut


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
        # TF Card(SPI Master)

        # pin resouces
        tfcard_pins = platform.request("sd_card_spi", 0, dir="-")
        m.submodules.tfcard_pin_buf_cs = tfcard_pin_buf_cs = io.Buffer(
            "o", tfcard_pins.cs
        )
        m.submodules.tfcard_pin_buf_clk = tfcard_pin_buf_clk = io.Buffer(
            "o", tfcard_pins.clk
        )
        m.submodules.tfcard_pin_buf_copi = tfcard_pin_buf_copi = io.Buffer(
            "o", tfcard_pins.copi
        )
        m.submodules.tfcard_pin_cipo = tfcard_pin_cipo = io.Buffer(
            "i", tfcard_pins.cipo
        )
        # SD Card SPI Master
        m.submodules.tfcard_spim = tfcard_spim = SpiMaster(
            SpiConfig(system_clk_freq=DEFAULT_CLK_FREQ, spi_clk_freq=400e3)
        )
        # Connection
        m.d.comb += [
            # External pins (SPI mode: DAT1=NC/DAT2=NC)
            tfcard_pin_buf_cs.o.eq(tfcard_spim.cs),  # DAT3/CS
            tfcard_pin_buf_clk.o.eq(tfcard_spim.sclk),  # CLK
            tfcard_pin_buf_copi.o.eq(tfcard_spim.mosi),  # CMD/DMOSI
            tfcard_spim.miso.eq(tfcard_pin_cipo.i),  # DAT0/MISO
            # Internal SDCard/SPI Master
            tfcard_spim.en.eq(1),
        ]

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
