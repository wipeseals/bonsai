from typing import List
from amaranth import Assert, Format, Module, Shape, Signal, unsigned
from amaranth.lib import wiring, memory
from amaranth.lib.memory import WritePort, ReadPort
from amaranth.lib.wiring import In
from amaranth.utils import exact_log2

import config
import util
from bonsai.datatype import AbortType, LsuReqSignature, LsuOperationType


class SingleCycleMemory(wiring.Component):
    """
    低Latencyでアクセス可能な小容量のメモリ。Cache関連の命令は無視して取り扱う
    """

    # Memory Access Port
    req_in: In(
        LsuReqSignature(addr_shape=config.ADDR_SHAPE, data_shape=config.DATA_SHAPE)
    )

    def __init__(
        self,
        data_shape: Shape = config.DATA_SHAPE,
        depth: int = 4096 // config.DATA_BIT_WIDTH,
        init_data: List[int] = [],
        use_strict_assert: bool = config.USE_STRICT_ASSERT,
    ):
        # 特定データのStorage運用は考えていないので、2^nの形状しか許容しない
        assert util.is_power_of_2(data_shape.width), "Data width must be power of 2"

        # depthの指定がinit_dataのサイズを超えていた場合の対応
        if len(init_data) > depth:
            depth = len(init_data)

        self._data_shape = data_shape
        self._depth = depth
        self._init_data = init_data
        self._use_strict_assert = use_strict_assert
        # ミスアライメント検出用
        self._data_bytes = util.byte_width(data_shape.width)
        self._addr_offset_bits = exact_log2(self._data_bytes)
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
        req_in_mem_idx = self.req_in.addr_in >> self._addr_offset_bits
        # misaligned data accessは現状非サポート
        is_misaligned = self.req_in.addr_in.bit_select(0, self._addr_offset_bits) != 0

        # Abort
        # Abort要因は制御元stageで使用するので返すが、勝手に再開できないようにAbort状態は継続
        abort_type = Signal(AbortType, init=AbortType.NONE)

        # Write Enable
        # AbortしていないかつWrite要求の場合のみ許可。1cycで済むのでbusy不要。wrenは遅延させたくないのでcomb
        write_en = Signal(unsigned(1), init=0)
        with m.If(abort_type == AbortType.NONE):
            with m.Switch(self.req_in.op_type):
                with m.Case(
                    LsuOperationType.WRITE_CACHE,
                    LsuOperationType.WRITE_THROUGH,
                    LsuOperationType.WRITE_NON_CACHE,
                ):
                    m.d.comb += write_en.eq(1)
                with m.Default():
                    m.d.comb += write_en.eq(0)

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
            # write enable
            wr_port.en.eq(write_en),
        ]
        # default state
        m.d.sync += [
            # not busy
            self.req_in.busy.eq(0),
        ]

        with m.FSM(init="READY", domain="sync"):
            with m.State("ABORT"):
                # (default) keep ABORT state
                m.d.sync += [
                    self.req_in.busy.eq(1),
                ]

                # Abort Clearが来ていた場合は解除
                with m.Switch(self.req_in.op_type):
                    with m.Case(
                        LsuOperationType.MANAGE_CLEAR_ABORT,
                    ):
                        # Abort Clear (この時点では読み出していないのでbusyは解除しない)
                        m.d.sync += [
                            abort_type.eq(AbortType.NONE),
                        ]
                        m.next = "READY"
                    with m.Default():
                        pass
            with m.State("READY"):
                # misaligned data accessは現状非サポート
                with m.If(is_misaligned):
                    m.d.sync += [
                        self.req_in.busy.eq(1),
                        abort_type.eq(AbortType.MISALIGNED_MEM_ACCESS),
                    ]
                    m.next = "ABORT"

                    if self._use_strict_assert:
                        m.d.sync += [
                            Assert(
                                0,
                                Format(
                                    "Misaligned Access: {:016x}", self.req_in.addr_in
                                ),
                            ),
                        ]

        return m


if __name__ == "__main__":
    stages = [
        SingleCycleMemory(),
    ]
    for stage in stages:
        util.export_verilog_file(stage, f"{stage.__class__.__name__}")
