from typing import Any
from amaranth import Const, Format, Module, Mux, Print, Shape, Signal, unsigned
from amaranth.lib import wiring, enum, data, memory, stream
from amaranth.lib.wiring import In, Out
from amaranth.cli import main
from amaranth.back import verilog

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

        # Debug cycle/sequence counter
        counter = Signal(config.REG_SHAPE)
        seq_no = Signal(config.REG_SHAPE)

        m.d.sync += counter.eq(counter + 1)
        with m.If(self.input.ctrl.en):
            m.d.sync += seq_no.eq(seq_no + 1)
        m.d.sync += self.output.ctrl.debug.counter.eq(counter + 1)
        m.d.sync += self.output.ctrl.debug.seq_no.eq(seq_no)

        # Push Instruction fetch address
        with m.If(self.side_ctrl.clr):
            # stall中にflushがかかった場合は、flushを優先する
            m.d.sync += self.output.flush()
        with m.Else():
            with m.If(self.input.ctrl.en):
                m.d.sync += self.output.push(self.input.pc)
            with m.Else():
                m.d.sync += self.output.stall()

        return m


if __name__ == "__main__":
    util.export_verilog_file(IfStage(), f"{IfStage.__name__}")
