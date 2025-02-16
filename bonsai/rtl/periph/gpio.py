from amaranth import Module, Signal
from amaranth.build.plat import Platform
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out


class Gpo(wiring.Component):
    def __init__(self, *, width: int, init_data: int, src_loc_at=0):
        self._width = width
        self._init_data = init_data
        super().__init__(
            {
                "datain": In(width),
                "req": In(1),
                "pinout": Out(width),
            },
            src_loc_at=src_loc_at,
        )

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        data = Signal(self._width, init=self._init_data)
        m.d.comb += self.pinout.eq(data)
        # req assert時のみ更新
        with m.If(self.req):
            m.d.sync += data.eq(self.datain)
        return m


class Gpi(wiring.Component):
    def __init__(self, *, width: int, src_loc_at=0):
        self._width = width
        super().__init__(
            {
                "dataout": Out(width),
                "req": In(1),
                "pinin": In(width),
            },
            src_loc_at=src_loc_at,
        )

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        data = Signal(self._width, init=0)
        m.d.comb += self.dataout.eq(data)
        with m.If(self.req):
            m.d.sync += data.eq(self.pinin)
        return m
