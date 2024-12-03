from typing import Any
from amaranth import Module, Signal
from amaranth.lib import wiring, memory
from amaranth.lib.wiring import In, Out

import pipeline_reg
import config
import util


class IfStage(wiring.Component):
    """
    Instruction Fetch First Stage
    """

    input: In(pipeline_reg.IfReg)
    output: Out(pipeline_reg.IfIsReg)
    side: In(pipeline_reg.FlushCtrl)

    def elaborate(self, platform):
        m = Module()

        # 型定義得るために一時変数追加
        input: pipeline_reg.IfReg = self.input
        output: pipeline_reg.IfIsReg = self.output
        side: pipeline_reg.FlushCtrl = self.side

        # Debug cyc/sequence counter
        debug = Signal(pipeline_reg.FetchInfo)

        # デバッグ記録するcycleは、global cycle counterを使用
        m.d.sync += debug.cyc.eq(side.cyc)

        with m.If(side.en):
            # stall中にflushがかかった場合は、flushを優先する
            output.flush(m=m, domain="sync")
        with m.Else():
            with m.If(input.stall.en):
                # IF stageではPC決定のみ。Is/If regの値を下に次サイクルでIs stageが読み出し
                output.push(m=m, addr=input.pc, debug=debug, domain="sync")
                # デバッグ記録用のfetch sequence number更新
                m.d.sync += debug.seqno.eq(debug.seqno + 1)
            with m.Else():
                output.stall(m=m, domain="sync")

        return m


class IsStage(wiring.Component):
    """
    Instruction Fetch Second Stage
    """

    input: In(pipeline_reg.IfIsReg)
    output: Out(pipeline_reg.IsIdReg)
    side: In(pipeline_reg.FlushCtrl)

    def __init__(self, init_data: Any = []):
        self._init_data = init_data
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        # 型定義得るために一時変数追加
        input: pipeline_reg.IfIsReg = self.input
        output: pipeline_reg.IsIdReg = self.output
        side: pipeline_reg.FlushCtrl = self.side

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

        with m.If(side.en):
            # stall中にflushがかかった場合は、flushを優先する
            output.flush(m=m, domain="sync")
        with m.Else():
            with m.If(input.ctrl.en):
                # TODO: CacheMiss時の処理を追加

                # メモリから出力されている命令を次のステージに渡す
                output.push(
                    m=m,
                    domain="sync",
                    addr=input.addr,
                    inst=rd_port.data,
                    debug=input.ctrl.debug,
                )
            with m.Else():
                output.stall(
                    m=m,
                    domain="sync",
                )

        return m


class IdStage(wiring.Component):
    """
    Instruction Decode Stage
    """

    input: In(pipeline_reg.IsIdReg)
    output: Out(pipeline_reg.IdExReg)
    side: In(pipeline_reg.FlushCtrl)
    wb: In(pipeline_reg.WriteBackCtrl)

    def elaborate(self, platform):
        m = Module()

        # 型定義得るために一時変数追加
        input: pipeline_reg.IsIdReg = self.input
        output: pipeline_reg.IdExReg = self.output
        side: pipeline_reg.FlushCtrl = self.side
        wb: pipeline_reg.WriteBackCtrl = self.wb

        # inst分解: 共通部分
        with m.If(side.en):
            output.flush(m=m, domain="sync")
        with m.Else():
            with m.If(input.ctrl.en):
                # inst分解: 共通部分
                output.push(
                    m=m,
                    domain="sync",
                    addr=input.addr,
                    inst=input.inst,
                    debug=input.ctrl.debug,
                )
            with m.Else():
                pass  #: TODO

        return m


if __name__ == "__main__":
    stages = [IfStage(), IsStage()]
    for stage in stages:
        util.export_verilog_file(stage, f"{stage.__class__.__name__}")
