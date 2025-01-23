from typing import List, Optional
from amaranth import Assert, Module, Shape, Signal, unsigned
from amaranth.lib import wiring, memory
from amaranth.lib.memory import WritePort, ReadPort
from amaranth.lib.wiring import In, Out

import config
import util
from format import MemoryAccessSignature, MemoryOperationType


class SingleCycleMemory(wiring.Component):
    """
    低Latencyでアクセス可能な小容量のメモリ。Cache関連の命令は無視して取り扱う
    """

    # Memory Access Port
    port: Out(
        MemoryAccessSignature(
            addr_shape=config.ADDR_SHAPE, data_shape=config.DATA_SHAPE
        ).flip()
    )

    def __init__(
        self,
        data_shape: Shape = config.DATA_SHAPE,
        depth: int = 4096 // config.DATA_WIDTH,
        init_data: Optional[List[int]] = None,
    ):
        # generate initial data
        if init_data is None:
            init_data = [0] * depth

        self._data_shape = data_shape
        self._depth = depth
        self._init_data = init_data
        super().__init__()

    def elaborate(self, platform):
        m = Module()
        m.submodules.mem = mem = memory.Memory(
            shape=self._data_shape, depth=self._depth, init=self._init_data
        )
        wr_port: WritePort = mem.write_port(domain="sync")
        rd_port: ReadPort = mem.read_port(domain="sync")

        # default state
        m.d.sync += [
            # not busy
            self.port.busy.eq(0),
            # default read port setting
            rd_port.en.eq(0),
            rd_port.addr.eq(self.port.addr_in),
            self.port.data_out.eq(rd_port.data),
            # default write port setting
            wr_port.en.eq(0),
            wr_port.addr.eq(self.port.addr_in),
            wr_port.data.eq(self.port.data_in),
        ]

        with m.Switch(self.port.op_type):
            with m.Case(
                MemoryOperationType.READ_CACHE,
                MemoryOperationType.READ_NON_CACHE,
            ):
                # Read Enable
                m.d.sync += [
                    rd_port.en.eq(1),
                ]
            with m.Case(
                MemoryOperationType.WRITE_CACHE,
                MemoryOperationType.WRITE_THROUGH,
                MemoryOperationType.WRITE_NON_CACHE,
            ):
                # Write Enable
                m.d.sync += [
                    wr_port.en.eq(1),
                ]
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
                # Cache Management対象外。NOPと同様
                pass
            with m.Default():
                # 未実装。NOPと同様
                pass

        return m


if __name__ == "__main__":
    stages = [
        SingleCycleMemory(),
    ]
    for stage in stages:
        util.export_verilog_file(stage, f"{stage.__class__.__name__}")
