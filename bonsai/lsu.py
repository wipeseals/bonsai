from operator import is_
from typing import List
from amaranth import Assert, Const, Format, Module, Mux, Shape, Signal, unsigned
from amaranth.lib import wiring, memory
from amaranth.lib.memory import WritePort, ReadPort
from amaranth.lib.wiring import In
from amaranth.utils import exact_log2

import config
import util
from datatype import AbortType, CoreBusReqSignature, LsuOperationType


class SingleCycleMemory(wiring.Component):
    """
    低Latencyでアクセス可能な小容量のメモリ。Cache関連の命令は無視して取り扱う
    Cache Missしてほしくないデータ置き場、もしくはSimulation時のProgram置き場を想定
    """

    # Memory Access Port
    primary_req_in: In(
        CoreBusReqSignature(addr_shape=config.ADDR_SHAPE, data_shape=config.DATA_SHAPE)
    )
    secondary_req_in: In(
        CoreBusReqSignature(addr_shape=config.ADDR_SHAPE, data_shape=config.DATA_SHAPE)
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

        # byte enable用の設定
        BITS_PER_BYTEMASK_BIT = 8  # byte enable granularity
        WREN_BIT_WIDTH = self._data_shape.width // BITS_PER_BYTEMASK_BIT
        assert (
            WREN_BIT_WIDTH == len(self.primary_req_in.bytemask)
            and WREN_BIT_WIDTH == len(self.secondary_req_in.bytemask)
        ), f"Byte Mask Width Error. Expected: {WREN_BIT_WIDTH}, Actual: {len(self.primary_req_in.bytemask)}, {len(self.secondary_req_in.bytemask)}"

        # Memory Instance
        m.submodules.mem = mem = memory.Memory(
            shape=self._data_shape, depth=self._depth, init=self._init_data
        )
        # posedgeで更新。wr_port.en が1bitではなく data_width // granularity になる
        wr_port: WritePort = mem.write_port(
            domain="sync", granularity=BITS_PER_BYTEMASK_BIT
        )
        rd_port: ReadPort = mem.read_port(domain="comb")

        # Primary Port > Secondary Portの優先度で動く
        is_primary_req = (self.primary_req_in.en) & (
            self.primary_req_in.op_type != LsuOperationType.NOP
        )
        is_secondary_req = (self.secondary_req_in.en) & (
            self.secondary_req_in.op_type != LsuOperationType.NOP
        )
        op_type = Mux(
            is_primary_req, self.primary_req_in.op_type, self.secondary_req_in.op_type
        )
        addr_in = Mux(
            is_primary_req, self.primary_req_in.addr_in, self.secondary_req_in.addr_in
        )
        data_in = Mux(
            is_primary_req, self.primary_req_in.data_in, self.secondary_req_in.data_in
        )
        bytemask = Mux(
            is_primary_req, self.primary_req_in.bytemask, self.secondary_req_in.bytemask
        )

        # addr_in の非アライン分とbytemaskを許容するため、mem上のインデックスとその中のオフセットに変換
        # e.g. addr=0x0009, bytemask=0b0010
        #       word_idx        = 0x0009 // 4 = 0x0002
        #       byte_offset     = 0x0009  % 4 = 0x0001
        mem_word_idx = addr_in >> self._addr_offset_bits  # offset切り捨て
        mem_byte_offset = addr_in.bit_select(0, self._addr_offset_bits)  # offset部分

        # bytemask有効 & byte_offset + bitpos がbytenableのpos byte以上の場合は次のワードにまたがっている
        # e.g. addr=0x0009, bytemask=0b1000
        is_aligned = Signal(1, init=1)
        for i in range(WREN_BIT_WIDTH):
            with m.If(bytemask[i] & (mem_byte_offset + i >= self._data_bytes)):
                m.d.comb += is_aligned.eq(0)

        # bytemask は1bit=8byteを示すデータなので実際のマスクを作成
        # e.g. bytemask=0b0010 -> datamask=0b00000000_00000000_11111111_00000000
        datamask = Signal(self._data_shape)
        m.d.comb += [
            datamask.eq(Const(0)),
        ]
        for i in range(WREN_BIT_WIDTH):
            m.d.comb += [
                datamask.bit_select(
                    i * BITS_PER_BYTEMASK_BIT, BITS_PER_BYTEMASK_BIT
                ).eq(Mux(bytemask[i], Const(0xFF), Const(0x00))),
            ]

        # data_in のオフセット・バイトマスクを考慮。先にdatamask適用してからword内オフセットをずらす
        data_in_masked = (data_in & datamask) << (
            mem_byte_offset * BITS_PER_BYTEMASK_BIT
        ).bit_select(0, self._data_shape.width)

        # data_out のオフセット・バイトマスクを考慮. 動かす方向がWriteと逆. datamaskはオフセット取り除いた後に適用
        data_out_masked = (
            rd_port.data >> (mem_byte_offset * BITS_PER_BYTEMASK_BIT)
        ).bit_select(0, self._data_shape.width) & datamask

        # Abort
        # Abort要因は制御元stageで使用するので返すが、勝手に再開できないようにAbort状態は継続
        abort_type = Signal(AbortType, init=AbortType.NONE)

        # Write Enable
        # bytemask自体はdata_in/out形式での位置を示しているため、word単位でenable制御する場合はoffsetに応じたシフトが必要
        # e.g. addr=0x0009, bytemask=0b0001, data=0x0000abcd
        #      data_in       = (0x0000abcd & 0x000000ff) << 8 = 0x0000ab00
        #      write_en_bits = 0b0001 << 1 = 0b0010            (0x0000ff00相当)
        write_en_bits = (bytemask << mem_byte_offset).bit_select(0, WREN_BIT_WIDTH)
        # Abortしていないかつalignに問題がなくWrite要求の場合のみ許可。1cycで済むのでbusy不要でwrenは遅延させたくないのでcomb
        write_en = Signal(unsigned(WREN_BIT_WIDTH), init=0)
        with m.If((abort_type == AbortType.NONE) & is_aligned):
            with m.Switch(op_type):
                with m.Case(
                    LsuOperationType.WRITE_CACHE,
                    LsuOperationType.WRITE_THROUGH,
                    LsuOperationType.WRITE_NON_CACHE,
                ):
                    # enable (w/ bytemask)
                    m.d.comb += write_en.eq(write_en_bits)
                with m.Default():
                    # disable
                    m.d.comb += write_en.eq(0)

        # 直結
        m.d.comb += [
            # rd_port.en.eq(0),# combの場合はConst(1)
            rd_port.addr.eq(mem_word_idx),
            self.primary_req_in.data_out.eq(data_out_masked),
            self.secondary_req_in.data_out.eq(data_out_masked),
            # default write port setting
            wr_port.addr.eq(mem_word_idx),
            wr_port.data.eq(data_in_masked),
            # default abort
            self.primary_req_in.abort_type.eq(abort_type),
            self.secondary_req_in.abort_type.eq(abort_type),
            # write enable
            wr_port.en.eq(write_en),
        ]

        # default state
        # 要求が来ている方はdefault not busy, 他方はdefault busy固定
        with m.If(is_primary_req):
            m.d.sync += [
                self.primary_req_in.busy.eq(0),
                self.secondary_req_in.busy.eq(1),
            ]
        with m.Elif(is_secondary_req):
            m.d.sync += [
                self.primary_req_in.busy.eq(1),
                self.secondary_req_in.busy.eq(0),
            ]
        with m.Else():
            # NOP = not busy
            m.d.sync += [
                self.primary_req_in.busy.eq(0),
                self.secondary_req_in.busy.eq(0),
            ]

        # Abort Control
        with m.FSM(init="READY", domain="sync"):
            with m.State("ABORT"):
                # (default) keep ABORT state
                m.d.sync += [
                    self.primary_req_in.busy.eq(1),
                    self.secondary_req_in.busy.eq(1),
                ]

                # Abort Clearが来ていた場合は解除
                with m.Switch(op_type):
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
                with m.If(is_aligned):
                    pass
                with m.Else():
                    # misaligned access
                    m.d.sync += [
                        self.primary_req_in.busy.eq(1),
                        self.secondary_req_in.busy.eq(1),
                        abort_type.eq(AbortType.MISALIGNED_MEM_ACCESS),
                    ]
                    m.next = "ABORT"

                    if self._use_strict_assert:
                        m.d.sync += [
                            Assert(
                                0,
                                Format(
                                    "Misaligned Access Error. addr:{:016x}", addr_in
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
