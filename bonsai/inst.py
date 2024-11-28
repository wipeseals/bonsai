from typing import Callable, Optional
from amaranth import Cat, Format, Print, unsigned
from amaranth.lib import data, wiring, enum

from pydantic import BaseModel


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


class ExArgsR(data.Struct):
    """
    R-Type Operand
    """

    rs1: unsigned(32)
    rs2: unsigned(32)


class ExRetR(data.Struct):
    """
    R-Type Result
    """

    rd: unsigned(32)


class InstDef(BaseModel):
    """
    Instruction
    """

    # 表示名
    inst: str
    # 概要
    name: str
    # 命令形式
    fmt: InstFormat
    # 命令コード
    opcode: unsigned(7)
    # 機能コード3
    funct3: Optional[unsigned(3)]
    # 機能コード7
    funct7: Optional[unsigned(7)]
    # 処理概要
    desc: str

    # R-Typeの場合の演算 rd = func(rs1, rs2)
    funcR: Optional[Callable[[unsigned(32), unsigned(32)], unsigned(32)]] = None
    # I-Typeの場合の演算 rd = func(rs1, imm)
    funcI: Optional[Callable[[unsigned(32), unsigned(32)], unsigned(32)]] = None
    # S-Typeの場合の演算 data, mask = func(rs1, imm)
    funcS: Optional[
        Callable[[unsigned(32), unsigned(32)], (unsigned(32), unsigned(32))]
    ] = None
    # B-Typeの場合の演算 need_branch, new_pc = func(rs1, rs2, imm)
    funcB: Optional[
        Callable[
            [unsigned(32), unsigned(32), unsigned(32)], (unsigned(1), unsigned(32))
        ]
    ] = None
    # U-Typeの場合の演算 rd = func(imm, pc)
    funcU: Optional[Callable[[unsigned(32), unsigned(32)], unsigned(32)]] = None
    # J-Typeの場合の演算 rd, new_pc = func(imm, pc)
    funcJ: Optional[
        Callable[[unsigned(32), unsigned(32)], (unsigned(32), unsigned(32))]
    ] = None
