import stat
from typing import Callable, Optional
from amaranth import Assert, Cat, Format, Module, Print, Signal, unsigned
from amaranth.lib import data, wiring, enum

from pydantic import BaseModel

import config


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

    # Load Upper Immediate
    LUI = 0b0110111
    # Add Upper Immediate to PC
    AUIPC = 0b0010111
    # Jump and Link
    JAL = 0b1101111
    # Jump and Link Register
    JALR = 0b1100111
    # Branch XXX
    BRANCH = 0b1100011
    # Load XXX
    LOAD = 0b0000011
    # Store XXX
    STORE = 0b0100011
    # XXX Immediate (Register Immediate operation)
    OP_IMM = 0b0010011
    # XXX (Register Register operation)
    OP = 0b0110011
    # Memory (fence, ...)
    MISC_MEM = 0b0001111
    # System (ecall, ebreak, ...)
    SYSTEM = 0b1110011
    # Atomic
    AMO = 0b0101111


class Operand(data.Struct):
    """
    Instruction Operand
    """

    # funct3
    funct3: unsigned(3)
    # funct5 (for atomic)
    funct5: unsigned(5)
    # funct7
    funct7: unsigned(7)

    # Source Register 1 Enable
    rs1_en: unsigned(1)
    # Source Register 1 index
    rs1_index: config.REGFILE_INDEX_SHAPE
    # Source Register 1
    rs1: config.REG_SHAPE

    # Source Register 2 Enable
    rs2_en: unsigned(1)
    # Source Register 2 index
    rs2_index: config.REGFILE_INDEX_SHAPE
    # Source Register 2
    rs2: config.REG_SHAPE

    # Destination Register Enable
    rd_en: unsigned(1)
    # Destination Register index
    rd_index: config.REGFILE_INDEX_SHAPE

    # Immediate Value enable
    imm_en: unsigned(1)
    # Immediate Value
    imm: config.REG_SHAPE
    # Immediate Value (sign extended)
    imm_sext: config.SREG_SHAPE_SIGNED

    def clear(self, m: Module, domain: str):
        """
        Clear Operand
        """
        m.d[domain] += [
            self.funct3.eq(0),
            self.funct5.eq(0),
            self.funct7.eq(0),
            self.rs1_en.eq(0),
            self.rs1_index.eq(0),
            self.rs1.eq(0),
            self.rs2_en.eq(0),
            self.rs2_index.eq(0),
            self.rs2.eq(0),
            self.rd_en.eq(0),
            self.rd_index.eq(0),
            self.imm_en.eq(0),
            self.imm.eq(0),
            self.imm_sext.eq(0),
        ]
