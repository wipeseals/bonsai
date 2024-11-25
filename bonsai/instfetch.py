from typing import Any
from amaranth import Module, Shape, Signal, unsigned
from amaranth.lib import wiring, enum, data, memory, stream
from amaranth.lib.wiring import In, Out
from amaranth.cli import main

import config


class InstFetchCtrl(enum.Enum):
    """
    Control signals for PC operation
    """

    # NOP: No operation
    NOP = 0
    # INC2: Increment by 2
    INC2 = 1
    # INC4: Increment by 4
    INC4 = 2
    # INC8: Increment by 8
    INC8 = 3
    # FLUSH: Flush the pipeline, reset the PC
    FLUSH = 4


class InstFetchDebug(data.Struct):
    """
    Debug information during instruction fetch
    """

    cyc: config.REG_SHAPE
    seq_no: config.REG_SHAPE


class InstFetchIn(data.Struct):
    """
    Data structure of IF input signals
    """

    next_pc: config.ADDR_SHAPE
    req: InstFetchCtrl


class InstFetchOut(data.Struct):
    """
    Data structure of the IF/ID pipeline register
    """

    inst: config.INST_SHAPE
    pc: config.ADDR_SHAPE
    flush: unsigned(1)
    debug: InstFetchDebug


class InstFetch(wiring.Component):
    """
    InstFetch is a hardware component that fetches instructions from memory.
    """

    pc: Signal(config.ADDR_SHAPE)
    mem_read_port: memory.ReadPort.Signature(
        addr_width=config.ADDR_WIDTH, shape=config.DATA_SHAPE
    )
    ctrl_in: In(stream.Signature(InstFetchIn))
    ctrl_out: Out(stream.Signature(InstFetchOut))
    debug: Signal(InstFetchDebug)

    def elaborate(self, platform):
        m = Module()
        return m


if __name__ == "__main__":
    instfetch = InstFetch()
    main(instfetch)
