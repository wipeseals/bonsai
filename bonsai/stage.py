from typing import Any
from amaranth import Const, Format, Module, Mux, Print, Shape, Signal, unsigned
from amaranth.lib import wiring, enum, data, memory, stream
from amaranth.lib.wiring import In, Out
from amaranth.cli import main

import pipeline
import config


class IfStage(wiring.Component):
    """
    Instruction Fetch Stage
    """

    input: In(pipeline.IfReg)
    output: Out(pipeline.IfIsReg)

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
        with m.If(self.input.ctrl.en):
            # push
            m.d.sync += self.output.ctrl.en.eq(1)
            m.d.sync += self.output.addr.eq(self.input.pc)
        with m.Else():
            # stall
            m.d.sync += self.output.ctrl.en.eq(0)
            m.d.sync += self.output.addr.eq(0)

        return m


if __name__ == "__main__":
    ifs = IfStage()
    main(ifs)
