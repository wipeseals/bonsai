import stat
from typing import Callable, Optional
from amaranth import Assert, Cat, Format, Module, Print, Signal, unsigned
from amaranth.lib import data, wiring, enum

from pydantic import BaseModel

from bonsai import config


class InstFormat(enum.IntEnum):
    """
    RISC-V Instruction Format
    """

    R = 0
    I = 1  # noqa: E741
    S = 2
    B = 3
    U = 4
    J = 5


class Opcode(enum.IntEnum, shape=7):
    """
    Instruction Opcode
    """

    LUI = 0b0110111
    AUIPC = 0b0010111
    JAL = 0b1101111
    JALR = 0b1100111
    BRANCH = 0b1100011
    LOAD = 0b0000011
    STORE = 0b0100011
    OP_IMM = 0b0010011
    OP = 0b0110011
    MISC_MEM = 0b0001111
    SYSTEM = 0b1110011

    @classmethod
    def inst_format(
        cls, m: Module, opcode: Signal, format: Signal, domain: str = "comb"
    ) -> Callable:
        """
        Get the instruction format from the opcode
        """

        with m.Switch(opcode):
            with m.Case(cls.LUI, cls.AUIPC):
                m.d[domain] += format.eq(InstFormat.U)
            with m.Case(cls.JAL, cls.JALR):
                m.d[domain] += format.eq(InstFormat.J)
            with m.Case(cls.BRANCH):
                m.d[domain] += format.eq(InstFormat.B)
            with m.Case(cls.LOAD, cls.STORE, cls.OP_IMM, cls.OP):
                m.d[domain] += format.eq(InstFormat.I)
            with m.Case(cls.MISC_MEM, cls.SYSTEM):
                m.d[domain] += format.eq(InstFormat.I)
            with m.Default():
                Assert(0, Format("invalid opcode: {:07b}", opcode))
                # add 0 = 0 + 0 流す?
                m.d[domain] += format.eq(InstFormat.R)
