from amaranth import Module, Signal
from amaranth.lib import wiring, memory
from amaranth.lib.memory import WritePort, ReadPort
from amaranth.lib.wiring import In, Out

from bonsai import config


class CacheAccessReqSignature(wiring.Signature):
    """
    Cache Access Request
    """

    def __init__(self):
        super().__init__(
            {
                "addr_in": In(config.ADDR_SHAPE),
                "data_in": In(config.DATA_SHAPE),
                "we": In(1),
                "data_out": Out(config.DATA_SHAPE),
                "rd_valid": Out(1),
                "wr_accept": Out(1),
            }
        )


class FixedMemory(wiring.Component):
    """
    Fixed Memory for Debug and Test
    """

    req: In(CacheAccessReqSignature)

    def __init__(self, depth: int, init_data: list = [], domain: str = "comb"):
        self._depth = depth
        self._init_data = init_data
        self._domain = domain
        super().__init__()

    def elaborate(self, platform):
        m = Module()
        m.submodules.mem = mem = memory.Memory(
            shape=config.DATA_SHAPE, depth=self._depth, init=self._init_data
        )
        # 1cyc遅延してほしくないのでそのまま透過して出す想定
        rd_port: ReadPort = mem.read_port(domain=self._domain)
        wr_port: WritePort = mem.write_port(domain=self._domain)

        with m.If(self.req.we):
            # Write to memory
            m.d[self._domain] += [
                # WritePort: enable
                wr_port.en.eq(1),
                wr_port.addr.eq(self.req.addr_in),
                wr_port.data.eq(self.req.data_in),
                # Read Port: disable
                rd_port.en.eq(0),
                rd_port.addr.eq(self.req.addr_in),
                # Write Accept: ok
                self.req.wr_accept.eq(1),
                # Read Valid: disable
                self.req.rd_valid.eq(0),
                self.req.data_out.eq(self.req.data_in),  # data_inをそのまま出力
            ]
        with m.Else():
            # Read from memory
            m.d[self._domain] += [
                # WritePort: disable
                wr_port.en.eq(0),
                wr_port.addr.eq(self.req.addr_in),
                wr_port.data.eq(self.req.data_in),
                # Read Port: enable
                rd_port.en.eq(1),
                rd_port.addr.eq(self.req.addr_in),
                # Write Accept: disable
                self.req.wr_accept.eq(0),
                # Read Valid: enable
                self.req.rd_valid.eq(1),
                self.req.data_out.eq(rd_port.data),
            ]

        return m
