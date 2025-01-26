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
    req_in: In(
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
            rd_port.addr.eq(self.req_in.addr_in),
            self.req_in.data_out.eq(rd_port.data),  # W/R同時利用しないので透過不要
            # default write port setting
            wr_port.addr.eq(self.req_in.addr_in),
            wr_port.data.eq(self.req_in.data_in),
        ]
        # default state
        m.d.sync += [
            # not busy
            self.req_in.busy.eq(0),
            # write disable
            wr_port.en.eq(0),
        ]

        with m.FSM(init="READY, domain='sync'"):
            with m.State("READY"):
                with m.If(self.req_in.op_type.is_read()):
                    # NOP (Read Always Enable)
                    pass
                with m.Elif(self.req_in.op_type.is_write()):
                    # Write Enable
                    m.d.sync += [
                        wr_port.en.eq(1),
                    ]
                    pass
                with m.Elif(self.req_in.op_type.is_manage()):
                    # Cache Management対応不要。NOPと同様
                    pass
                with m.Else():
                    # NOP
                    pass

        return m


if __name__ == "__main__":
    stages = [
        SingleCycleMemory(),
    ]
    for stage in stages:
        util.export_verilog_file(stage, f"{stage.__class__.__name__}")
