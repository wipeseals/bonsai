from typing import List
from amaranth import Assert, Format, Module, Shape, Signal
from amaranth.lib import wiring, memory
from amaranth.lib.memory import WritePort, ReadPort
from amaranth.lib.wiring import In

import config
import util
from format import AbortType, MemoryAccessReqSignature, MemoryOperationType


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
        # 特定データのStorage運用は考えていないので、2^nの形状しか許容しない
        assert util.is_power_of_2(data_shape.width), "Data width must be power of 2"

        # depthの指定がinit_dataのサイズを超えていた場合の対応
        if len(init_data) > depth:
            depth = len(init_data)

        self._data_shape = data_shape
        self._depth = depth
        self._init_data = init_data
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        # Memory Instance
        m.submodules.mem = mem = memory.Memory(
            shape=self._data_shape, depth=self._depth, init=self._init_data
        )
        wr_port: WritePort = mem.write_port()
        rd_port: ReadPort = mem.read_port(domain="comb")

        # addr != memory indexのため変換
        byte_width = util.byte_width(self._data_shape.width)
        req_in_mem_idx = self.req_in.addr_in >> byte_width
        # misaligned data accessは現状非サポート
        is_missaligned = self.req_in.addr_in.bit_select(0, byte_width * 8 - 1) != 0

        # Abort
        # Abort要因は制御元stageで使用するので返すが、勝手に再開できないようにAbort状態は継続
        abort_type = Signal(AbortType, init=AbortType.NONE)

        # 直結
        m.d.comb += [
            # rd_port.en.eq(0),# combの場合はConst(1)
            rd_port.addr.eq(req_in_mem_idx),
            self.req_in.data_out.eq(rd_port.data),  # W/R同時利用しないので透過不要
            # default write port setting
            wr_port.addr.eq(req_in_mem_idx),
            wr_port.data.eq(self.req_in.data_in),
            # default abort
            self.req_in.abort_type.eq(abort_type),
        ]
        # default state
        m.d.sync += [
            # not busy
            self.req_in.busy.eq(0),
            # write disable
            wr_port.en.eq(0),
        ]

        with m.FSM(init="READY", domain="sync"):
            with m.State("READY"):
                # misaligned data accessは現状非サポート
                with m.If(is_missaligned):
                    m.d.sync += [
                        abort_type.eq(AbortType.MISALIGNED_FETCH),
                        Assert(
                            0,
                            Format("Misaligned Access: {:016x}", self.req_in.addr_in),
                        ),
                    ]
                    m.next = "ABORT"
                with m.Else():
                    # Read/Write Enable
                    with m.Switch(self.req_in.op_type):
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
                            m.d.sync += [
                                abort_type.eq(AbortType.ILLEGAL_MEM_OP),
                                Assert(
                                    0,
                                    Format(
                                        "Unsupported Operation Type: {:d}",
                                        self.req_in.op_type,
                                    ),
                                ),
                            ]
                            m.next = "ABORT"
            with m.State("ABORT"):
                # (default) keep ABORT state
                m.d.sync += [
                    self.req_in.busy.eq(1),
                ]

                # Abort Clearが来ていた場合は解除
                with m.Switch(self.req_in.op_type):
                    with m.Case(
                        MemoryOperationType.MANAGE_CLEAR_ABORT,
                    ):
                        # Abort Clear
                        m.d.sync += [
                            abort_type.eq(AbortType.NONE),
                        ]
                        m.next = "READY"
                    with m.Default():
                        pass

        return m


if __name__ == "__main__":
    stages = [
        SingleCycleMemory(),
    ]
    for stage in stages:
        util.export_verilog_file(stage, f"{stage.__class__.__name__}")
