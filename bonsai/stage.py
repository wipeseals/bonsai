from typing import Any
from amaranth import Const, Format, Module, Mux, Print, Shape, Signal, unsigned
from amaranth.lib import wiring, enum, data, memory, stream
from amaranth.lib.wiring import In, Out

import pipeline
import config
import util


class IfStage(wiring.Component):
    """
    Instruction Fetch Stage
    """

    input: In(pipeline.IfReg)
    output: Out(pipeline.IfIsReg)
    side_ctrl: In(pipeline.SideCtrl)

    def elaborate(self, platform):
        m = Module()
        input: pipeline.IfReg = self.input
        output: pipeline.IfIsReg = self.output
        side_ctrl: pipeline.SideCtrl = self.side_ctrl

        # Debug sequence counter
        debug = Signal(pipeline.StageCtrlDebug)
        m.d.sync += debug.cyc.eq(side_ctrl.cyc)

        # Push Instruction fetch address
        with m.If(side_ctrl.clr):
            # stall中にflushがかかった場合は、flushを優先する
            m.d.sync += output.flush()
        with m.Else():
            with m.If(input.ctrl.en):
                # pc
                m.d.sync += output.push(input.pc, debug)
                # debug info
                m.d.sync += debug.seqno.eq(debug.seqno + 1)
            with m.Else():
                m.d.sync += output.stall()

        return m


if __name__ == "__main__":
    util.export_verilog_file(IfStage(), f"{IfStage.__name__}")
