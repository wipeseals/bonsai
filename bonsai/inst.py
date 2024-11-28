from amaranth import Cat, Format, Print, unsigned
from amaranth.lib import data, wiring, enum


class RegFormat(enum.IntEnum):
    """
    RISC-V Instruction Format
    """

    R = 0
    I = 1  # noqa: E741
    S = 2
    B = 3
    U = 4
    J = 5


class BaseIntOpcode(enum.IntEnum, shape=7):
    """
    Base Integer Instruction Set
    """

    # add, sub, xor, or, and, sll, srl, sra, slt, sltu
    REG_REG = 0b0110011
    # addi, xori, ori, andi, slli, srli, srai, slti, sltiu
    REG_IMM = 0b0010011
    # lb, lh, lw, lbu, lhu
    LOAD = 0b0000011
    # sb, sh, sw
    STORE = 0b0100011
    # beq, bne, blt, bge, bltu, bgeu
    BRANCH = 0b1100011
    # jal
    JAL = 0b1101111
    # jalr
    JALR = 0b1100111
    # lui
    LUI = 0b0110111
    # auipc
    AUIPC = 0b0010111
    # fence, fence.i
    FENCE = 0b0001111
    # ecall, ebreak, csrrw, csrrs, csrrc, csrrwi, csrrsi, csrrci
    ECALL = 0b1110011


class RegRegFunc3(enum.IntEnum, shape=3):
    """
    Base Integer Register-Register Instruction Set Func3
    """

    # add, sub
    ADD_SUB = 0x0
    # sll
    SLL = 0x1
    # slt
    SLT = 0x2
    # sltu
    SLTU = 0x3
    # xor
    XOR = 0x4
    # srl, sra
    SRL_SRA = 0x5
    # or
    OR = 0x6
    # and
    AND = 0x7


class RegRegFunc7(enum.IntEnum, shape=7):
    """
    Base Integer Register-Register Instruction Set Func7
    """

    # sll, slt, sltu, xor, or, and
    ZERO = 0x00
    # add
    ADD = 0x00
    # sub, sra
    SUB = 0x20
    # srl
    SRL = 0x00
    # sra
    SRA = 0x20
