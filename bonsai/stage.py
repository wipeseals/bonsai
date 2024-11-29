from ast import mod
from typing import Any
from amaranth import Const, Format, Module, Mux, Print, Shape, Signal, unsigned
from amaranth.lib import wiring, enum, data, memory, stream
from amaranth.lib.wiring import In, Out

from inst import InstFormat, Opcode
import pipeline
import config
import util


class IfStage(wiring.Component):
    """
    Instruction Fetch First Stage
    """

    input: In(pipeline.IfReg)
    output: Out(pipeline.IfIsReg)
    side_ctrl: In(pipeline.SideCtrl)

    def elaborate(self, platform):
        m = Module()

        # 型定義得るために追加
        input: pipeline.IfReg = self.input
        output: pipeline.IfIsReg = self.output
        side_ctrl: pipeline.SideCtrl = self.side_ctrl

        # Debug sequence counter
        debug = Signal(pipeline.StageCtrlDebug)
        m.d.sync += debug.cyc.eq(side_ctrl.cyc)

        with m.If(side_ctrl.clr):
            # stall中にflushがかかった場合は、flushを優先する
            output.flush(module=m, domain="sync")
        with m.Else():
            with m.If(input.ctrl.en):
                output.push(module=m, addr=input.pc, debug=debug, domain="sync")
                # fetch sequence number更新
                m.d.sync += debug.seqno.eq(debug.seqno + 1)
            with m.Else():
                output.stall(module=m, domain="sync")

        return m


class IsStage(wiring.Component):
    """
    Instruction Fetch Second Stage
    """

    input: In(pipeline.IfIsReg)
    output: Out(pipeline.IsIdReg)
    side_ctrl: In(pipeline.SideCtrl)

    def __init__(self, init_data: Any = []):
        self._init_data = init_data
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        # 型定義得るために追加
        input: pipeline.IfIsReg = self.input
        output: pipeline.IsIdReg = self.output
        side_ctrl: pipeline.SideCtrl = self.side_ctrl

        # L1 Cache Body
        m.submodules.mem = mem = memory.Memory(
            shape=config.INST_SHAPE, depth=config.L1_CACHE_DEPTH, init=self._init_data
        )

        # TODO: 外部ポートを追加し、キャッシュできるようにする
        # wr_port = mem.write_port()

        # Pipeline Register間にFF挟む必要ないので、直接接続かつ非同期で構成
        rd_port = mem.read_port(domain="comb")
        m.d.comb += [
            # memはINST_SHAPEの配列で確保してあるので、下位ビットを落とす
            rd_port.addr.eq(input.addr.shift_right(config.INST_ADDR_SHIFT)),
        ]

        with m.If(side_ctrl.clr):
            # stall中にflushがかかった場合は、flushを優先する
            output.flush(module=m, domain="sync")
        with m.Else():
            with m.If(input.ctrl.en):
                # TODO: CacheMiss時の処理を追加

                # メモリから出力されている命令を次のステージに渡す
                output.push(
                    module=m,
                    domain="sync",
                    addr=input.addr,
                    inst=rd_port.data,
                    debug=input.ctrl.debug,
                )
            with m.Else():
                output.stall(
                    module=m,
                    domain="sync",
                )

        return m


class IdStage(wiring.Component):
    """
    Instruction Decode Stage
    """

    input: In(pipeline.IsIdReg)
    output: Out(pipeline.IdExReg)
    side_ctrl: In(pipeline.SideCtrl)

    def elaborate(self, platform):
        m = Module()

        # 型定義得るために追加
        input: pipeline.IsIdReg = self.input
        output: pipeline.IdExReg = self.output
        side_ctrl: pipeline.SideCtrl = self.side_ctrl

        # inst分解: 共通部分
        addr = Signal(config.ADDR_SHAPE)
        inst = Signal(config.INST_SHAPE)
        opcode = Signal(Opcode)
        fmt = Signal(InstFormat)

        m.d.comb += [
            addr.eq(input.addr),
            inst.eq(input.inst),
            opcode.eq(input.inst[6:0]),
            fmt.eq(opcode.inst_format()),
        ]

        with m.If(side_ctrl.clr):
            pass  #: TODO
        with m.Else():
            with m.If(input.ctrl.en):
                pass  #: TODO
            with m.Else():
                pass  #: TODO

        return m


if __name__ == "__main__":
    stages = [IfStage(), IsStage()]
    for stage in stages:
        util.export_verilog_file(stage, f"{stage.__class__.__name__}")
