from dataclasses import dataclass

from amaranth import (
    Module,
    Mux,
    Signal,
    unsigned,
)
from amaranth.build.plat import Platform
from amaranth.lib import data, wiring
from amaranth.lib.wiring import In, Out
from amaranth.utils import ceil_log2


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

    @classmethod
    def preset_tangnano9k_800x480(cls):
        return cls(
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


class VgaOut(wiring.Component):
    def __init__(self, config: VgaConfig, video_domain: str = "sync", *, src_loc_at=0):
        self._video_domain = video_domain
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
                m.d[self._video_domain] += h_counter.eq(h_counter + 1)
            with m.Else():
                m.d[self._video_domain] += h_counter.eq(0)
                # Vertical counter
                with m.If(v_counter < self.config.vdata_end - 1):
                    m.d[self._video_domain] += v_counter.eq(v_counter + 1)
                with m.Else():
                    m.d[self._video_domain] += v_counter.eq(0)
        with m.Else():
            # Reset counter & sync invalid
            m.d[self._video_domain] += [h_counter.eq(0), v_counter.eq(0)]

        return m
