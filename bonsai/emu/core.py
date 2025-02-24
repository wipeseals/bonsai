import enum
import logging
from ctypes import LittleEndianStructure, Union, c_uint32
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from emu.mem import BusError, BusSlave, SysAddr


@enum.unique
class ExceptionCode(enum.Enum):
    """
    CPU例外の種類
    """

    INST_ADDR_MISALIGN = 0
    INST_ACCESS_FAILT = enum.auto()
    ILLEGAL_INST = enum.auto()
    BREAKPOINT = enum.auto()
    LOAD_ACCESS_MISALIGN = enum.auto()
    LOAD_ACCESS_FAULT = enum.auto()
    STORE_AMO_ADDR_MISALIGN = enum.auto()
    STORE_AMO_ACCESS_FAULT = enum.auto()
    ENV_CALL_U = enum.auto()
    ENV_CALL_S = enum.auto()
    ENV_CALL_H = enum.auto()
    ENV_CALL_M = enum.auto()

    @classmethod
    def from_buserr(cls, bus_err: BusError) -> "ExceptionCode":
        if bus_err == BusError.ERROR_MISALIGN:
            return cls.INST_ADDR_MISALIGN
        else:
            return cls.INST_ACCESS_FAILT


@enum.unique
class InterruptCode(enum.Enum):
    """
    CPU割り込みの種類
    """

    SOFTWARE = 0
    TIMER = enum.auto()


@dataclass
class RegFile:
    """
    Register file
    """

    # 汎用レジスタ32本
    regs: List[SysAddr.AddrU32] = field(default_factory=lambda: [0] * 32)

    def clear(self) -> None:
        """
        Clear all registers
        """
        self.regs = [0] * 32

    def read(
        self, addr: SysAddr.AddrU32
    ) -> Tuple[SysAddr.DataU32, ExceptionCode | None]:
        """
        Read a register
        """
        assert 0 <= addr < 32, f"Invalid register address: {addr=}"
        # zero register
        if addr == 0:
            return 0
        return self.regs[addr], None

    def write(
        self, addr: SysAddr.AddrU32, data: SysAddr.DataU32
    ) -> ExceptionCode | None:
        """
        Write a register
        """
        assert 0 <= addr < 32, f"Invalid register address: {addr=}"
        # zero register
        if addr == 0:
            return
        self.regs[addr] = data
        return None


class IfStage:
    """
    命令フェッチを実行する
    """

    @dataclass
    class Result:
        # PC
        pc: SysAddr.AddrU32
        # 命令データ
        raw: SysAddr.DataU32

    @staticmethod
    def run(
        pc: SysAddr.AddrU32, slave: BusSlave
    ) -> Tuple[Optional["IfStage.Result"], ExceptionCode | None]:
        exception: ExceptionCode | None = None
        # 命令データ取得
        inst_data, access_ret = slave.read(pc)
        if access_ret is not None:
            logging.warning(f"Failed to read instruction: {pc=}, {access_ret=}")
            exception = ExceptionCode.from_buserr(bus_err=access_ret)
        return IfStage.Result(pc, inst_data), exception


@enum.unique
class InstFmt(enum.IntEnum):
    """
    Instruction format
    """

    # Register:
    # - Arithmetic (ADD, SUB, XOR, OR, AND, SLL, SRL, SRA, SLT, SLTU)
    # - Multiply (MUL, MULH, MULHSU, MULU, DIV, DIVU, REM, REMU)
    R = 0b0110011
    # Immediate:
    # - Arithmetic (ADDI, XORI, ORI, ANDI, SLLI, SRLI, SRAI)
    # - Load (LB, LH, LW, LBU, LHU)
    I = 0b0010011
    # Store(SB, SH, SW)
    S = 0b0100011
    # Branch(BEQ, BNE, BLT, BGE, BLTU, BGEU)
    B = 0b1100011
    # Load Upper Immediate
    U_LUI = 0b0110111
    # Add Upper Immediate to PC
    U_AUIPC = 0b0010111
    # Jump And Link
    J_JAL = 0b1101111
    # Jump And Link Register
    J_JALR = 0b1100111
    # Environment Call/Break
    I_ENV = 0b1110011
    # Atomic Extension
    R_ATOMIC = 0b0101111


@enum.unique
class InstType(enum.Enum):
    """
    Instruction Names
    """

    # Base Integer R-Type Integer Arithmetic Instructions
    ADD = enum.auto()
    SUB = enum.auto()
    XOR = enum.auto()
    OR = enum.auto()
    AND = enum.auto()
    SLL = enum.auto()
    SRL = enum.auto()
    SRA = enum.auto()
    SLT = enum.auto()
    SLTU = enum.auto()
    # Base Integer I-Type Integer Arithmetic Instructions
    ADDI = enum.auto()
    XORI = enum.auto()
    ORI = enum.auto()
    ANDI = enum.auto()
    SLLI = enum.auto()
    SRLI = enum.auto()
    SRAI = enum.auto()
    SLTI = enum.auto()
    SLTIU = enum.auto()
    # Base Integer I-Type Load Instructions
    LB = enum.auto()
    LH = enum.auto()
    LW = enum.auto()
    LBU = enum.auto()
    LHU = enum.auto()
    # Base Integer S-Type Store Instructions
    SB = enum.auto()
    SH = enum.auto()
    SW = enum.auto()
    # Base Integer B-Type Branch Instructions
    BEQ = enum.auto()
    BNE = enum.auto()
    BLT = enum.auto()
    BGE = enum.auto()
    BLTU = enum.auto()
    BGEU = enum.auto()
    # Base Integer J-Type Jump Instructions
    JAL = enum.auto()
    # Base Integer I-Type Jump Instructions
    JALR = enum.auto()
    # Base Integer U-Type Instructions
    LUI = enum.auto()
    AUIPC = enum.auto()
    # Base Integer I-type Control Transfer Instructions
    ECALL = enum.auto()
    EBREAK = enum.auto()
    # Multiply Extension R-Type Instructions
    MUL = enum.auto()
    MULH = enum.auto()
    MULSU = enum.auto()
    MULU = enum.auto()
    DIV = enum.auto()
    DIVU = enum.auto()
    REM = enum.auto()
    REMU = enum.auto()
    # Atomic Extension R-Type Instructions
    LR_W = enum.auto()
    SC_W = enum.auto()
    AMOSWAP_W = enum.auto()
    AMOADD_W = enum.auto()
    AMOAND_W = enum.auto()
    AMOOR_W = enum.auto()
    AMOXOR_W = enum.auto()
    AMOMAX_W = enum.auto()
    AMOMIN_W = enum.auto()


class InstCommon(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("opcode", c_uint32, 7),
        ("reserved", c_uint32, 25),
    ]


class InstRType(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("opcode", c_uint32, 7),
        ("rd", c_uint32, 5),
        ("funct3", c_uint32, 3),
        ("rs1", c_uint32, 5),
        ("rs2", c_uint32, 5),
        ("funct7", c_uint32, 7),
    ]


class InstIType(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("opcode", c_uint32, 7),
        ("rd", c_uint32, 5),
        ("funct3", c_uint32, 3),
        ("rs1", c_uint32, 5),
        ("imm_11_0", c_uint32, 12),
    ]

    @property
    def imm(self) -> int:
        return self.imm_11_0


class InstSType(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("opcode", c_uint32, 7),
        ("imm_4_0", c_uint32, 5),
        ("funct3", c_uint32, 3),
        ("rs1", c_uint32, 5),
        ("rs2", c_uint32, 5),
        ("imm_11_5", c_uint32, 7),
    ]

    @property
    def imm(self) -> int:
        return (self.imm_11_5 << 5) | self.imm_4_0


class InstBType(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("opcode", c_uint32, 7),
        ("imm_11", c_uint32, 1),
        ("imm_4_1", c_uint32, 4),
        ("funct3", c_uint32, 3),
        ("rs1", c_uint32, 5),
        ("rs2", c_uint32, 5),
        ("imm_10_5", c_uint32, 6),
        ("imm_12", c_uint32, 1),
    ]

    @property
    def imm(self) -> int:
        return (
            (self.imm_12 << 12)
            | (self.imm_11 << 11)
            | (self.imm_10_5 << 5)
            | (self.imm_4_1 << 1)
        )


class InstUType(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("opcode", c_uint32, 7),
        ("rd", c_uint32, 5),
        ("imm_31_12", c_uint32, 20),
    ]

    @property
    def imm(self) -> int:
        return self.imm_31_12 << 12


class InstJType(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("opcode", c_uint32, 7),
        ("rd", c_uint32, 5),
        ("imm_19_12", c_uint32, 8),
        ("imm_11", c_uint32, 1),
        ("imm_10_1", c_uint32, 10),
        ("imm_20", c_uint32, 1),
    ]

    @property
    def imm(self) -> int:
        return (
            (self.imm_20 << 20)
            | (self.imm_19_12 << 12)
            | (self.imm_11 << 11)
            | (self.imm_10_1 << 1)
        )


class InstAtomicType(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("opcode", c_uint32, 7),
        ("rd", c_uint32, 5),
        ("funct3", c_uint32, 3),
        ("rs1", c_uint32, 5),
        ("rs2", c_uint32, 5),
        ("rl", c_uint32, 1),
        ("aq", c_uint32, 1),
        ("funct5", c_uint32, 5),
    ]


class DecodedInst(Union):
    _pack_ = 1
    _fields_ = [
        ("raw", c_uint32),
        ("common", InstCommon),
        ("r", InstRType),
        ("i", InstIType),
        ("s", InstSType),
        ("b", InstBType),
        ("u", InstUType),
        ("j", InstJType),
        ("atomic", InstAtomicType),
    ]


class IdStage:
    """
    命令デコードを実行する
    """

    @dataclass
    class Result:
        # IF結果
        if_ret: IfStage.Result
        # 命令フォーマット
        i_fmt: InstFmt
        # 命令タイプ
        i_type: InstType
        # 命令データ
        i_data: DecodedInst

    @classmethod
    def run(
        cls, fetch_data: IfStage.Result
    ) -> Tuple[Optional["IdStage.Result"], ExceptionCode | None]:
        # 命令デコード
        i_data = DecodedInst()
        i_data.raw = fetch_data.raw
        # 命令フォーマット/タイプ
        i_fmt = InstFmt(i_data.common.opcode)
        if i_fmt == InstFmt.R:
            # funct3 -> (funct7 -> type)
            table: Dict[int, Dict[int, InstType]] = {
                0b000: {0b0000000: InstType.ADD, 0b0100000: InstType.SUB},
                0b001: {0b0000000: InstType.SLL},
                0b010: {0b0000000: InstType.SLT},
                0b011: {0b0000000: InstType.SLTU},
                0b100: {0b0000000: InstType.XOR},
                0b101: {0b0000000: InstType.SRL, 0b0100000: InstType.SRA},
                0b110: {0b0000000: InstType.OR},
                0b111: {0b0000000: InstType.AND},
            }
            i_type = table.get(i_data.r.funct3, {}).get(i_data.r.funct7, None)
        elif i_fmt == InstFmt.I:
            # funct3 -> (imm[11:5] -> type)
            imm_11_5 = i_data.i.imm_11_0 >> 5
            table: Dict[int, Callable[InstType]] = {
                0b000: lambda: InstType.ADDI,
                0b001: lambda: InstType.SLLI,
                0b010: lambda: InstType.SLTI,
                0b011: lambda: InstType.SLTIU,
                0b100: lambda: InstType.XORI,
                0b101: lambda: InstType.SRLI if imm_11_5 == 0 else InstType.SRAI,
                0b110: lambda: InstType.ORI,
                0b111: lambda: InstType.ANDI,
            }
            i_type = table.get(i_data.i.funct3, lambda x: None)()
        elif i_fmt == InstFmt.S:
            # funct3 -> type
            table: Dict[int, InstType] = {
                0b000: InstType.SB,
                0b001: InstType.SH,
                0b010: InstType.SW,
            }
            i_type = table.get(i_data.s.funct3, None)
        elif i_fmt == InstFmt.B:
            # funct3 -> type
            table: Dict[int, InstType] = {
                0b000: InstType.BEQ,
                0b001: InstType.BNE,
                0b100: InstType.BLT,
                0b101: InstType.BGE,
                0b110: InstType.BLTU,
                0b111: InstType.BGEU,
            }
            i_type = table.get(i_data.b.funct3, None)
        elif i_fmt in [InstFmt.U_LUI, InstFmt.U_AUIPC]:
            # opcode -> type
            table: Dict[int, InstType] = {
                InstFmt.U_LUI: InstType.LUI,
                InstFmt.U_AUIPC: InstType.AUIPC,
            }
            i_type = table.get(i_fmt, None)
        elif i_fmt in [InstFmt.J_JAL, InstFmt.J_JALR]:
            # opcode -> type
            table: Dict[int, InstType] = {
                InstFmt.J_JAL: InstType.JAL,
                InstFmt.J_JALR: InstType.JALR,
            }
            i_type = table.get(i_fmt, None)
        elif i_fmt == InstFmt.I_ENV:
            # imm -> type
            table: Dict[int, InstType] = {
                0b000: InstType.ECALL,
                0b001: InstType.EBREAK,
            }
            i_type = table.get(i_data.i.imm)
        elif i_fmt == InstFmt.R_ATOMIC:
            # funct5 -> type
            table: Dict[int, InstType] = {
                0b00000: InstType.LR_W,
                0b00001: InstType.SC_W,
                0b00010: InstType.AMOSWAP_W,
                0b00011: InstType.AMOADD_W,
                0b00100: InstType.AMOAND_W,
                0b00101: InstType.AMOOR_W,
                0b00110: InstType.AMOXOR_W,
                0b00111: InstType.AMOMAX_W,
                0b01000: InstType.AMOMIN_W,
            }
            i_type = table.get(i_data.atomic.funct5, None)
        else:
            logging.warning(f"Unknown instruction format: {i_fmt=}")
            return None, ExceptionCode.ILLEGAL_INST

        if i_type is None or i_type not in InstType:
            logging.warning(f"Unknown instruction type: {i_type=}")
            return None, ExceptionCode.ILLEGAL_INST

        return cls.Result(
            if_ret=fetch_data,
            i_fmt=i_fmt,
            i_type=i_type,
            i_data=i_data,
        ), None


class ExStage:
    """
    命令実行
    """

    @dataclass
    class Result:
        # if/id result
        id_ret: IdStage.Result

    @classmethod
    def run(
        cls, decode_data: IdStage.Result
    ) -> Tuple[Optional["ExStage.Result"], ExceptionCode | None]:
        pass


class MemStage:
    """
    メモリアクセス
    """

    @dataclass
    class Result:
        # ex result
        ex_ret: ExStage.Result

    @classmethod
    def run(
        cls,
        exec_data: ExStage.Result,
        slave: BusSlave,
    ) -> Tuple[Optional["MemStage.Result"], ExceptionCode | None]:
        pass


class WbStage:
    """
    WriteBack
    """

    @dataclass
    class Result:
        # mem result
        mem_ret: MemStage.Result

    @classmethod
    def run(
        cls, mem_data: MemStage.Result
    ) -> Tuple[Optional["WbStage.Result"], ExceptionCode | None]:
        pass


@dataclass
class CoreConfig:
    # 初期化時点でのPC
    init_pc: int


class Core:
    def __init__(self, config: CoreConfig, slave: BusSlave):
        self.slave = slave
        # 設定参照用にstore
        self.config = config
        # RegisterFile & PC & cycles
        self.regs = RegFile()
        self.pc: SysAddr.AddrU32 = SysAddr.AddrU32(0)
        self.cycles = 0
        self.reset()

    def reset(self) -> None:
        self.regs.clear()
        self.pc = SysAddr.AddrU32(self.config.init_pc)
        self.cycles = 0

    def step(self) -> None:
        # IF: Instruction Fetch
        if_data, if_ex = IfStage.run(pc=self.pc, slave=self.slave)
        logging.debug(f"[{self.cycles}][IF] {if_data=} {if_ex=}")
        if if_ex is not None:
            logging.warning(f"Fetch Error: {if_ex=}")
            raise RuntimeError(f"TODO: impl Exception Handler: {if_ex=}")
        assert if_data is not None

        # ID: Instruction Decode
        id_data, id_ex = IdStage.run(fetch_data=if_data)
        logging.debug(f"[{self.cycles}][ID] {id_data=} {id_ex=}")
        if id_ex is not None:
            logging.warning(f"Decode Error: {id_ex=}")
            raise RuntimeError(f"TODO: impl Exception Handler: {id_ex=}")
        assert id_data is not None

        # EX: Execute
        ex_data, ex_ex = ExStage.run(decode_data=id_data)
        logging.debug(f"[{self.cycles}][EX] {ex_data=} {ex_ex=}")
        if ex_ex is not None:
            logging.warning(f"Execute Error: {ex_ex=}")
            raise RuntimeError(f"TODO: impl Exception Handler: {ex_ex=}")
        assert ex_data is not None

        # MEM: Memory Access
        mem_data, mem_ex = MemStage.run(exec_data=ex_data, slave=self.slave)
        logging.debug(f"[{self.cycles}][MEM] {mem_data=} {mem_ex=}")
        if mem_ex is not None:
            logging.warning(f"Memory Access Error: {mem_ex=}")
            raise RuntimeError(f"TODO: impl Exception Handler: {mem_ex=}")
        assert mem_data is not None

        # WB: WriteBack
        wb_data, wb_ex = WbStage.run(mem_data=mem_data)
        logging.debug(f"[{self.cycles}][WB] {wb_data=} {wb_ex=}")
        if wb_ex is not None:
            logging.warning(f"WriteBack Error: {wb_ex=}")
            raise RuntimeError(f"TODO: impl Exception Handler: {wb_ex=}")
        assert wb_data is not None

        # Next PC/cycles
        self.pc += SysAddr.NUM_WORD_BYTES  # TODO: branch
        self.cycles += 1

        # TODO: Exception, Interrupt, Debug, etc...
