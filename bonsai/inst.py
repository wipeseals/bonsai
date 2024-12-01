import stat
from typing import Callable, Optional
from amaranth import Assert, Cat, Format, Module, Mux, Print, Signal, unsigned
from amaranth.lib import data, wiring, enum

from pydantic import BaseModel

from regfile import RegFile
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

    # funct2 enable
    funct2_en: unsigned(1)
    # funct2
    funct2: unsigned(2)
    # funct3 enable
    funct3_en: unsigned(1)
    # funct3
    funct3: unsigned(3)
    # funct5 enable (for atomic)
    funct5_en: unsigned(1)
    # funct5 (for atomic)
    funct5: unsigned(5)
    # funct7 enable
    funct7_en: unsigned(1)
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

    # Source Register 3 Enable
    rs3_en: unsigned(1)
    # Source Register 3 index
    rs3_index: config.REGFILE_INDEX_SHAPE
    # Source Register 3
    rs3: config.REG_SHAPE

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
            self.funct2_en.eq(0),
            self.funct2.eq(0),
            self.funct3_en.eq(0),
            self.funct3.eq(0),
            self.funct5_en.eq(0),
            self.funct5.eq(0),
            self.funct7_en.eq(0),
            self.funct7.eq(0),
            self.rs1_en.eq(0),
            self.rs1_index.eq(0),
            self.rs1.eq(0),
            self.rs2_en.eq(0),
            self.rs2_index.eq(0),
            self.rs2.eq(0),
            self.rs3_en.eq(0),
            self.rs3_index.eq(0),
            self.rs3.eq(0),
            self.rd_en.eq(0),
            self.rd_index.eq(0),
            self.imm_en.eq(0),
            self.imm.eq(0),
            self.imm_sext.eq(0),
        ]

    def update(
        self,
        m: Module,
        domain: str,
        regfile: RegFile,
        funct2: Optional[unsigned(2)] = None,
        funct3: Optional[unsigned(3)] = None,
        funct5: Optional[unsigned(5)] = None,
        funct7: Optional[unsigned(7)] = None,
        rs1_index: Optional[config.REGFILE_INDEX_SHAPE] = None,
        rs2_index: Optional[config.REGFILE_INDEX_SHAPE] = None,
        rs3_index: Optional[config.REGFILE_INDEX_SHAPE] = None,
        rd_index: Optional[config.REGFILE_INDEX_SHAPE] = None,
        imm: Optional[config.REG_SHAPE] = None,
        # for WB/EX forwarding
        fwd_rd_index: Optional[config.REGFILE_INDEX_SHAPE] = None,
        fwd_rd: Optional[config.REG_SHAPE] = None,
    ):
        """
        Update Parsed Operand
        """

        # 事前に値クリアのアサインをセットして、値がある場合のみアサインする
        self.clear(m=m, domain=domain)

        # 値がある場合、値とenableをセット
        if funct2 is not None:
            m.d[domain] += [
                self.funct2_en.eq(1),
                self.funct2.eq(funct2),
            ]
        if funct3 is not None:
            m.d[domain] += [
                self.funct3_en.eq(1),
                self.funct3.eq(funct3),
            ]
        if funct5 is not None:
            m.d[domain] += [
                self.funct5_en.eq(1),
                self.funct5.eq(funct5),
            ]
        if funct7 is not None:
            m.d[domain] += [
                self.funct7_en.eq(1),
                self.funct7.eq(funct7),
            ]

        if rs1_index is not None:
            m.d[domain] += [
                self.rs1_en.eq(1),
                self.rs1_index.eq(rs1_index),
            ]
            # Register Forwarding
            if fwd_rd_index is not None:
                assert fwd_rd is not None, "fwd_rd is required"
                self.rs1.eq(
                    Mux(fwd_rd_index == rs1_index, fwd_rd, regfile.get_gpr(rs1_index))
                )
        if rs2_index is not None:
            m.d[domain] += [
                self.rs2_en.eq(1),
                self.rs2_index.eq(rs2_index),
            ]
            # Register Forwarding
            if fwd_rd_index is not None:
                assert fwd_rd is not None, "fwd_rd is required"
                self.rs2.eq(
                    Mux(fwd_rd_index == rs2_index, fwd_rd, regfile.get_gpr(rs2_index))
                )
        if rs3_index is not None:
            m.d[domain] += [
                self.rs3_en.eq(1),
                self.rs3_index.eq(rs3_index),
            ]
            # Register Forwarding
            if fwd_rd_index is not None:
                assert fwd_rd is not None, "fwd_rd is required"
                self.rs3.eq(
                    Mux(fwd_rd_index == rs3_index, fwd_rd, regfile.get_gpr(rs3_index))
                )
        if rd_index is not None:
            m.d[domain] += [
                self.rd_en.eq(1),
                self.rd_index.eq(rd_index),
            ]

        if imm is not None:
            m.d[domain] += [
                self.imm_en.eq(1),
                self.imm.eq(imm),
                # TODO: IMMのビット幅と符号拡張が正しくないように思えるので、修正が必要
                self.imm_sext.eq(imm.as_signed()),
            ]
