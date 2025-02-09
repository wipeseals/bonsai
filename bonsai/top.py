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
from amaranth.lib import cdc, data, enum, io, stream, wiring
from amaranth.lib.cdc import ResetSynchronizer
from amaranth.lib.wiring import In, Out
from amaranth.utils import ceil_log2
from amaranth_boards.arty_a7 import ArtyA7_35Platform
from amaranth_boards.tang_nano_9k import TangNano9kPlatform
from periph.timer import Timer, TimerMode
from periph.uart import UartConfig, UartRx, UartTx
from periph.video import VgaConfig, VgaOut


class PsramCmd(enum.IntEnum):
    READ = 0
    WRITE = 1


class PsramPortSignature(wiring.Signature):
    def __init__(self, data_width: int, addr_width: int, burst_num: int, port_num: int):
        self._data_width = data_width
        self._data_mask_width = data_width // 8
        self._addr_width = addr_width
        self._burst_num = burst_num
        self._port_num = port_num
        assert 0 < port_num <= 2, "port_num must be 1 or 2"
        members: Dict[str, Any] = {}
        for port_idx in range(port_num):
            members[f"addr{port_idx}"] = Out(data_width)
            members[f"cmd{port_idx}"] = Out(PsramCmd)
            members[f"cmd_en{port_idx}"] = Out(1)
            members[f"rd_data{port_idx}"] = In(data_width)
            members[f"rd_data_valid{port_idx}"] = In(1)
            members[f"wr_data{port_idx}"] = Out(data_width)
            members[f"data_mask{port_idx}"] = Out(self._data_mask_width)
            members[f"init_calib{port_idx}"] = In(1)

        super().__init__(members)


class Top(wiring.Component):
    def __init__(
        self,
        *,
        src_loc_at=0,
    ):
        periph_clk_freq: float = 27e6
        self.timer = Timer(clk_freq=periph_clk_freq, default_period_seconds=1.0)
        self.uart_tx = UartTx(config=UartConfig.from_freq(clk_freq=periph_clk_freq))
        self.uart_rx = UartRx(config=UartConfig.from_freq(clk_freq=periph_clk_freq))

        super().__init__(
            {
                # for GN1NR-9C internal PSRAM
                "O_psram_ck": Out(2),  # output [1:0] O_psram_ck
                "O_psram_ck_n": Out(2),  # output [1:0] O_psram_ck_n
                "IO_psram_rwds": In(2),  # inout [1:0] IO_psram_rwds
                "O_psram_reset_n": Out(2),  # output [1:0] O_psram_reset_n
                "IO_psram_dq": In(16),  # inout [15:0] IO_psram_dq
                "O_psram_cs_n": Out(2),  # output [1:0] O_psram_cs_n
            },
            src_loc_at=src_loc_at,
        )

    def elaborate(self, platform: Platform) -> Module:
        # TODO: other platform specific logic
        assert isinstance(platform, TangNano9kPlatform), (
            f"Unsupported platform: {platform}"
        )

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
        m.submodules.timer = self.timer
        timer_toggle_sig = Signal(1, 0)
        with m.If(self.timer.ovf):
            m.d.sync += timer_toggle_sig.eq(~timer_toggle_sig)
        m.d.comb += [
            # Internal
            self.timer.en.eq(1),
            self.timer.clr.eq(0),
            self.timer.trig.eq(0),
            self.timer.cmp_count_wr.eq(0),
            self.timer.mode.eq(TimerMode.FREERUN_WITH_CLEAR),
        ]

        ##################################################################
        # uart loopback
        m.submodules.uart_tx = self.uart_tx
        m.submodules.uart_rx = self.uart_rx
        uart = platform.request("uart", 0, dir="-")
        m.submodules.uart_tx_pin = uart_tx_pin = io.Buffer("o", uart.tx)
        m.submodules.uart_rx_pin = uart_rx_pin = io.Buffer("i", uart.rx)
        m.d.comb += [
            # External pins
            uart_tx_pin.o.eq(self.uart_tx.tx),
            self.uart_rx.rx.eq(uart_rx_pin.i),
            # Internal RX
            self.uart_rx.en.eq(1),
            # Internal TX
            self.uart_tx.en.eq(1),
            # RX->TX Loopback
            self.uart_tx.stream.payload.eq(self.uart_rx.stream.payload),
            self.uart_tx.stream.valid.eq(self.uart_rx.stream.valid),
            self.uart_rx.stream.ready.eq(self.uart_tx.stream.ready),
        ]

        ##################################################################
        # PSRAM
        platform.add_file(
            "psram_memory_interface_hs_2ch.v",
            Path(
                r"eda/bonsai_tangnano9k/src/psram_memory_interface_hs_2ch/psram_memory_interface_hs_2ch.v"
            ).read_text(),
        )

        psram_clkout = Signal(1)
        psramc_signals = PsramPortSignature(
            data_width=32, addr_width=21, burst_num=4, port_num=2
        ).create()
        # test pattern
        with m.If(psramc_signals.init_calib0):
            m.d.core_sync += [
                psramc_signals.addr0.eq(psramc_signals.addr0 + 1),
                psramc_signals.cmd0.eq(PsramCmd.READ),
                psramc_signals.cmd_en0.eq(1),
            ]

        m.submodules.psramc = psramc = Instance(
            "PSRAM_Memory_Interface_HS_2CH_Top",
            i_clk=ClockSignal("sync"),  # input clk
            i_rst_n=Const(1),  # input rst_n
            i_memory_clk=ClockSignal("core_sync"),  # input memory_clk
            i_pll_lock=pll_lock,  # input pll_lock
            # Topに出しておくと合成されるらしい...
            o_O_psram_ck=self.O_psram_ck,  # output [1:0] O_psram_ck
            o_O_psram_ck_n=self.O_psram_ck_n,  # output [1:0] O_psram_ck_n
            i_IO_psram_rwds=self.IO_psram_rwds,  # inout [1:0] IO_psram_rwds
            o_O_psram_reset_n=self.O_psram_reset_n,  # output [1:0] O_psram_reset_n
            i_IO_psram_dq=self.IO_psram_dq,  # inout [15:0] IO_psram_dq
            o_O_psram_cs_n=self.O_psram_cs_n,  # output [1:0] O_psram_cs_n
            # 制御用Port0/1
            o_init_calib0=psramc_signals.init_calib0,  # output init_calib0
            o_init_calib1=psramc_signals.init_calib1,  # output init_calib1
            # PSRAMC制御ロジック向け
            o_clk_out=psram_clkout,  # output clk_out
            # 制御用Port0/1
            i_cmd0=psramc_signals.cmd0,  # input cmd0
            i_cmd1=psramc_signals.cmd1,  # input cmd1
            i_cmd_en0=psramc_signals.cmd_en0,  # input cmd_en0
            i_cmd_en1=psramc_signals.cmd_en1,  # input cmd_en1
            i_addr0=psramc_signals.addr0,  # input [20:0] addr0
            i_addr1=psramc_signals.addr1,  # input [20:0] addr1
            i_wr_data0=psramc_signals.wr_data0,  # input [31:0] wr_data0
            i_wr_data1=psramc_signals.wr_data1,  # input [31:0] wr_data1
            o_rd_data0=psramc_signals.rd_data0,  # output [31:0] rd_data0
            o_rd_data1=psramc_signals.rd_data1,  # output [31:0] rd_data1
            o_rd_data_valid0=psramc_signals.rd_data_valid0,  # output rd_data_valid0
            o_rd_data_valid1=psramc_signals.rd_data_valid1,  # output rd_data_valid1
            i_data_mask0=psramc_signals.data_mask0,  # input [3:0] data_mask0
            i_data_mask1=psramc_signals.data_mask1,  # input [3:0] data_mask1
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
