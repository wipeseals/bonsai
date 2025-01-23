from typing import List
from amaranth import Assert, Format, Module, Shape
from amaranth.lib import wiring, memory
from amaranth.lib.memory import WritePort, ReadPort
from amaranth.lib.wiring import In

import config
import util
from format import MemoryAccessReqSignature, MemoryOperationType


class SingleCycleMemory(wiring.Component):
    """
    低Latencyでアクセス可能な小容量のメモリ。Cache関連の命令は無視して取り扱う
    """

    # Memory Access Port
    req: In(
        MemoryAccessReqSignature(
            addr_shape=config.ADDR_SHAPE, data_shape=config.DATA_SHAPE
        )
    )

    def __init__(
        self,
        data_shape: Shape = config.DATA_SHAPE,
        depth: int = 4096 // config.DATA_WIDTH,
        init_data: List[int] = [],
    ):
        self._data_shape = data_shape
        self._depth = depth
        self._init_data = init_data
        super().__init__()

    def elaborate(self, platform):
        m = Module()
        m.submodules.mem = mem = memory.Memory(
            shape=self._data_shape, depth=self._depth, init=self._init_data
        )
        wr_port: WritePort = mem.write_port()
        rd_port: ReadPort = mem.read_port(domain="comb")

        # 直結
        m.d.comb += [
            # rd_port.en.eq(0),# combの場合はConst(1)
            rd_port.addr.eq(self.req.addr_in),
            self.req.data_out.eq(rd_port.data),
            # default write port setting
            wr_port.addr.eq(self.req.addr_in),
            wr_port.data.eq(self.req.data_in),
        ]
        # default state
        m.d.sync += [
            # not busy
            self.req.busy.eq(0),
            # write disable
            wr_port.en.eq(0),
        ]

        with m.FSM(init="READY", domain="sync"):
            with m.State("READY"):
                with m.Switch(self.req.op_type):
                    with m.Case(
                        MemoryOperationType.READ_CACHE,
                        MemoryOperationType.READ_NON_CACHE,
                    ):
                        # NOP (Read Always Enable)
                        pass
                    with m.Case(
                        MemoryOperationType.WRITE_CACHE,
                        MemoryOperationType.WRITE_THROUGH,
                        MemoryOperationType.WRITE_NON_CACHE,
                    ):
                        # Write Enable
                        m.d.sync += [
                            wr_port.en.eq(1),
                        ]
                        pass
                    with m.Case(MemoryOperationType.NOP):
                        # NOP. keep READY state
                        pass
                    with m.Case(
                        MemoryOperationType.MANAGE_INVALIDATE,
                        MemoryOperationType.MANAGE_CLEAN,
                        MemoryOperationType.MANAGE_FLUSH,
                        MemoryOperationType.MANAGE_ZERO_FILL,
                        MemoryOperationType.MANAGE_PREFETCH,
                    ):
                        # Cache Management対応不要。NOPと同様
                        pass
                    with m.Default():
                        # 未実装
                        m.d.sync += Assert(
                            0,
                            Format(
                                "Unsupported Operation Type: {:d}",
                                self.req.op_type,
                            ),
                        )
                        m.next = "ABORT"
            with m.State("ABORT"):
                # keep ABORT state
                m.d.sync += self.req.busy.eq(1)

        return m


if __name__ == "__main__":
    stages = [
        SingleCycleMemory(),
    ]
    for stage in stages:
        util.export_verilog_file(stage, f"{stage.__class__.__name__}")
