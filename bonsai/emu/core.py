import enum
import logging
from ctypes import LittleEndianStructure, Union, c_uint32
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from emu.mem import BusError, BusSlave, SysAddr

from bonsai.emu.calc import Calc


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

        def __repr__(self) -> str:
            return f"[IF ](pc: 0x{self.pc:016x}, raw: 0x{self.raw:08x})"

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
class InstGroup(enum.Enum):
    """
    Instruction Group
    format別機能別に分割
    """

    # 0 => ADDI 0 0 にしておく
    NOP = 0

    # Register:
    # - Arithmetic/Logical (ADD, SUB, XOR, OR, AND, SLL, SRL, SRA, SLT, SLTU)
    # - Multiply (MUL, MULH, MULHSU, MULU, DIV, DIVU, REM, REMU)
    R_ARITHMETIC_LOGICAL_MULTIPLY = 0b0110011
    # Immediate:
    # - Arithmetic/Logical (ADDI, XORI, ORI, ANDI, SLLI, SRLI, SRAI)
    I_ARITHMETIC_LOGICAL = 0b0010011
    # Immediate:
    # - Load (LB, LH, LW, LBU, LHU)
    I_LOAD = 0b0000011
    # Store(SB, SH, SW)
    S_STORE = 0b0100011
    # Branch(BEQ, BNE, BLT, BGE, BLTU, BGEU)
    B_BRANCH = 0b1100011
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

    @property
    def imm_sext(self) -> int:
        return Calc.sign_extend(data=self.imm, num_bit_width=12)


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

    @property
    def imm_sext(self) -> int:
        return Calc.sign_extend(data=self.imm, num_bit_width=12)


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

    @property
    def imm_sext(self) -> int:
        return Calc.sign_extend(data=self.imm, num_bit_width=13)


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

    @property
    def imm_sext(self) -> int:
        return Calc.sign_extend(data=self.imm, num_bit_width=20)


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

    @property
    def imm_sext(self) -> int:
        return Calc.sign_extend(data=self.imm, num_bit_width=21)


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


class Operand(Union):
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
        fetch_data: IfStage.Result
        # 命令フォーマット
        inst_fmt: InstGroup
        # 命令タイプ
        inst_type: InstType
        # 命令データ
        operand: Operand

        def __repr__(self) -> str:
            if self.inst_fmt in [
                InstGroup.NOP,
                InstGroup.R_ARITHMETIC_LOGICAL_MULTIPLY,
            ]:
                return f"[ID ](fmt: {self.inst_fmt}, type: {self.inst_type}, rd: {self.operand.r.rd}, rs1: {self.operand.r.rs1}, rs2: {self.operand.r.rs2})"
            elif self.inst_fmt == InstGroup.I_ARITHMETIC_LOGICAL:
                return f"[ID ](fmt: {self.inst_fmt}, type: {self.inst_type}, rd: {self.operand.i.rd}, rs1: {self.operand.i.rs1}, imm: {self.operand.i.imm:08x})"
            elif self.inst_fmt == InstGroup.S_STORE:
                return f"[ID ](fmt: {self.inst_fmt}, type: {self.inst_type}, rs1: {self.operand.s.rs1}, rs2: {self.operand.s.rs2}, imm: {self.operand.s.imm:08x})"
            elif self.inst_fmt == InstGroup.B_BRANCH:
                return f"[ID ](fmt: {self.inst_fmt}, type: {self.inst_type}, rs1: {self.operand.b.rs1}, rs2: {self.operand.b.rs2}, imm: {self.operand.b.imm:08x})"
            elif self.inst_fmt in [InstGroup.U_LUI, InstGroup.U_AUIPC]:
                return f"[ID ](fmt: {self.inst_fmt}, type: {self.inst_type}, rd: {self.operand.u.rd}, imm: {self.operand.u.imm:08x})"
            elif self.inst_fmt in [InstGroup.J_JAL, InstGroup.J_JALR]:
                return f"[ID ](fmt: {self.inst_fmt}, type: {self.inst_type}, rd: {self.operand.j.rd}, imm: {self.operand.j.imm:08x})"
            elif self.inst_fmt == InstGroup.I_ENV:
                return f"[ID ](fmt: {self.inst_fmt}, type: {self.inst_type}, imm: {self.operand.i.imm:08x})"
            elif self.inst_fmt == InstGroup.R_ATOMIC:
                return f"[ID ](fmt: {self.inst_fmt}, type: {self.inst_type}, rd: {self.operand.atomic.rd}, rs1: {self.operand.atomic.rs1}, rs2: {self.operand.atomic.rs2})"
            else:
                return f"[ID ](fmt: {self.inst_fmt}, type: {self.inst_type})"

    @classmethod
    def run(
        cls, fetch_data: IfStage.Result
    ) -> Tuple[Optional["IdStage.Result"], ExceptionCode | None]:
        # 命令デコード
        decode_data = Operand()
        decode_data.raw = fetch_data.raw
        # 命令フォーマット/タイプ
        inst_type: InstType | None = None
        inst_fmt = InstGroup(decode_data.common.opcode)
        if inst_fmt in [
            InstGroup.NOP,
            InstGroup.R_ARITHMETIC_LOGICAL_MULTIPLY,
        ]:  # NOP=ADDI 0,0,0
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
            inst_type = table.get(decode_data.r.funct3, {}).get(
                decode_data.r.funct7, None
            )
        elif inst_fmt == InstGroup.I_ARITHMETIC_LOGICAL:
            # funct3 -> (imm[11:5] -> type)
            imm_11_5 = decode_data.i.imm_11_0 >> 5
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
            inst_type = table.get(decode_data.i.funct3, lambda x: None)()
        elif inst_fmt == InstGroup.S_STORE:
            # funct3 -> type
            table: Dict[int, InstType] = {
                0b000: InstType.SB,
                0b001: InstType.SH,
                0b010: InstType.SW,
            }
            inst_type = table.get(decode_data.s.funct3, None)
        elif inst_fmt == InstGroup.B_BRANCH:
            # funct3 -> type
            table: Dict[int, InstType] = {
                0b000: InstType.BEQ,
                0b001: InstType.BNE,
                0b100: InstType.BLT,
                0b101: InstType.BGE,
                0b110: InstType.BLTU,
                0b111: InstType.BGEU,
            }
            inst_type = table.get(decode_data.b.funct3, None)
        elif inst_fmt in [InstGroup.U_LUI, InstGroup.U_AUIPC]:
            # opcode -> type
            table: Dict[int, InstType] = {
                InstGroup.U_LUI: InstType.LUI,
                InstGroup.U_AUIPC: InstType.AUIPC,
            }
            inst_type = table.get(inst_fmt, None)
        elif inst_fmt in [InstGroup.J_JAL, InstGroup.J_JALR]:
            # opcode -> type
            table: Dict[int, InstType] = {
                InstGroup.J_JAL: InstType.JAL,
                InstGroup.J_JALR: InstType.JALR,
            }
            inst_type = table.get(inst_fmt, None)
        elif inst_fmt == InstGroup.I_ENV:
            # imm -> type
            table: Dict[int, InstType] = {
                0b000: InstType.ECALL,
                0b001: InstType.EBREAK,
            }
            inst_type = table.get(decode_data.i.imm)
        elif inst_fmt == InstGroup.R_ATOMIC:
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
            inst_type = table.get(decode_data.atomic.funct5, None)
        else:
            logging.warning(f"Unknown instruction format: {inst_fmt=}")
            return None, ExceptionCode.ILLEGAL_INST

        if inst_type is None or inst_type not in InstType:
            logging.warning(f"Unknown instruction type: {inst_type=}")
            return None, ExceptionCode.ILLEGAL_INST

        return cls.Result(
            fetch_data=fetch_data,
            inst_fmt=inst_fmt,
            inst_type=inst_type,
            operand=decode_data,
        ), None


@dataclass
class ReadRegResult:
    rs1: int
    rs2: int
    rs1_sext: int
    rs2_sext: int


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
            return 0, None
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
            return None
        self.regs[addr] = data
        return None

    def read_srcregs(
        self, rs1_idx: int, rs2_idx: int
    ) -> Tuple[ReadRegResult | None, ExceptionCode | None]:
        # read rs1, rs2
        rs1, rs1_ex = self.read(rs1_idx)
        if rs1_ex is not None:
            logging.warning(f"Failed to read rs1: {rs1_ex=}")
            return None, rs1_ex
        rs2, rs2_ex = self.read(rs2_idx)
        if rs2_ex is not None:
            logging.warning(f"Failed to read rs2: {rs2_ex=}")
            return None, rs2_ex
        # sign extend rs1/rs2
        rs1 = Calc.sign_extend(data=rs1, num_bit_width=32)
        rs2 = Calc.sign_extend(data=rs2, num_bit_width=32)

        return ReadRegResult(
            rs1=rs1,
            rs2=rs2,
            rs1_sext=rs1,
            rs2_sext=rs2,
        ), None


@enum.unique
class AfterExAction(enum.Flag):
    """
    EX Stage後に実行するアクション
    """

    # Load
    LOAD = enum.auto()
    # Store
    STORE = enum.auto()
    # WriteBack
    WRITEBACK = enum.auto()
    # Branch
    BRANCH = enum.auto()

    @classmethod
    @property
    def NOP(cls) -> "ExStage.AfterExAction":
        return cls(0)


class ExStage:
    """
    命令実行
    """

    @dataclass
    class Result:
        # if/id result
        decode_data: IdStage.Result
        # next actions
        action_bits: AfterExAction
        # WB stage
        writeback_idx: Optional[int] = None
        writeback_data: Optional[int] = None
        # MEM stage
        mem_addr: Optional[int] = None
        mem_size: Optional[int] = None
        mem_data: Optional[int] = None
        # EX stage (BRANCH)
        branch_addr: Optional[int] = None
        branch_cond: Optional[bool] = None

        def __repr__(self) -> str:
            repr_str = f"[EX ](action: {self.action_bits}"
            if self.action_bits & AfterExAction.WRITEBACK:
                assert self.writeback_idx is not None
                assert self.writeback_data is not None
                repr_str += (
                    f", rd: {self.writeback_idx}, data: 0x{self.writeback_data:08x}"
                )
            if self.action_bits & AfterExAction.LOAD:
                assert self.writeback_idx is not None
                repr_str += f", rd: {self.writeback_idx}"
            if self.action_bits & AfterExAction.STORE:
                assert self.mem_addr is not None
                assert self.mem_size is not None
                assert self.mem_data is not None
                repr_str += f", mem_addr: 0x{self.mem_addr:08x}, mem_size: {self.mem_size}, mem_data: 0x{self.mem_data:08x}"
            if self.action_bits & AfterExAction.BRANCH:
                assert self.branch_addr is not None
                assert self.branch_cond is not None
                repr_str += f", branch_addr: 0x{self.branch_addr:08x}, branch_cond: {self.branch_cond}"
            repr_str += ")"
            return repr_str

    @dataclass
    class ArithmeticLogicalOp:
        # 計算結果を返す
        compute_result: Callable[[], SysAddr.DataU32]
        # 例外がある場合はそのコードを
        check_exception: Callable[[], ExceptionCode | None] = None

    @dataclass
    class LoadOp:
        # Load先
        mem_addr: Callable[[], SysAddr.DataU32]
        # Load Size
        mem_size: Callable[[], SysAddr.DataU32]

    @dataclass
    class StoreOp:
        # Store先
        mem_addr: Callable[[], SysAddr.DataU32]
        # Store Size
        mem_size: Callable[[], SysAddr.DataU32]
        # Store Data
        store_data: Callable[[], SysAddr.DataU32]

    @dataclass
    class BranchOp:
        # Branch先
        branch_addr: Callable[[], SysAddr.DataU32]
        # branch条件成立
        branch_cond: Callable[[], bool]

    @classmethod
    def _run_r_arithmetic(
        cls, decode_data: IdStage.Result, reg_file: RegFile
    ) -> Tuple[Optional["ExStage.Result"], ExceptionCode | None]:
        # read rs1, rs2
        src_regs, regs_ex = reg_file.read_srcregs(
            rs1_idx=decode_data.operand.r.rs1, rs2_idx=decode_data.operand.r.rs2
        )
        if regs_ex is not None:
            return None, regs_ex
        rd_data = 0
        # 命令ごと分岐: inst_type -> func[[] -> rd_data]
        table: Dict[InstType, ExStage.ArithmeticLogicalOp] = {
            # Base Integer
            InstType.ADD: ExStage.ArithmeticLogicalOp(
                compute_result=lambda: src_regs.rs1_sext + src_regs.rs2_sext,
            ),
            InstType.SUB: ExStage.ArithmeticLogicalOp(
                compute_result=lambda: src_regs.rs1_sext - src_regs.rs2_sext,
            ),
            InstType.XOR: ExStage.ArithmeticLogicalOp(
                compute_result=lambda: src_regs.rs1 ^ src_regs.rs2
            ),
            InstType.OR: ExStage.ArithmeticLogicalOp(
                compute_result=lambda: src_regs.rs1 | src_regs.rs2
            ),
            InstType.AND: ExStage.ArithmeticLogicalOp(
                compute_result=lambda: src_regs.rs1 & src_regs.rs2
            ),
            InstType.SLL: ExStage.ArithmeticLogicalOp(
                check_exception=lambda: None,
                compute_result=lambda: src_regs.rs1_sext << src_regs.rs2_sext,
            ),
            InstType.SRL: ExStage.ArithmeticLogicalOp(
                compute_result=lambda: src_regs.rs1 >> src_regs.rs2
            ),
            InstType.SRA: ExStage.ArithmeticLogicalOp(
                check_exception=lambda: None,
                compute_result=lambda: src_regs.rs1_sext >> src_regs.rs2,
            ),
            InstType.SLT: ExStage.ArithmeticLogicalOp(
                check_exception=lambda: None,
                compute_result=lambda: src_regs.rs1_sext < src_regs.rs2_sext,
            ),
            InstType.SLTU: ExStage.ArithmeticLogicalOp(
                compute_result=lambda: src_regs.rs1 < src_regs.rs2
            ),
            # Multiply Extension
            InstType.MUL: ExStage.ArithmeticLogicalOp(
                compute_result=lambda: src_regs.rs1_sext * src_regs.rs2_sext
            ),
            InstType.MULH: ExStage.ArithmeticLogicalOp(
                compute_result=lambda: (src_regs.rs1_sext * src_regs.rs2_sext)
                >> SysAddr.NUM_WORD_BITS,
            ),
            InstType.MULSU: ExStage.ArithmeticLogicalOp(
                compute_result=lambda: (src_regs.rs1 * src_regs.rs2_sext)
                >> SysAddr.NUM_WORD_BITS,
            ),
            InstType.MULU: ExStage.ArithmeticLogicalOp(
                compute_result=lambda: (src_regs.rs1 * src_regs.rs2)
                >> SysAddr.NUM_WORD_BITS,
            ),
            InstType.DIV: ExStage.ArithmeticLogicalOp(
                check_exception=None
                if src_regs.rs2_sext != 0
                else ExceptionCode.ILLEGAL_INST,
                compute_result=lambda: src_regs.rs1_sext // src_regs.rs2_sext
                if src_regs.rs2_sext != 0
                else 0xFFFFFFFF,
            ),
            InstType.DIVU: ExStage.ArithmeticLogicalOp(
                check_exception=None
                if src_regs.rs2 != 0
                else ExceptionCode.ILLEGAL_INST,
                compute_result=lambda: src_regs.rs1 // src_regs.rs2
                if src_regs.rs2 != 0
                else 0xFFFFFFFF,
            ),
            InstType.REM: ExStage.ArithmeticLogicalOp(
                check_exception=None
                if src_regs.rs2_sext != 0
                else ExceptionCode.ILLEGAL_INST,
                compute_result=lambda: src_regs.rs1_sext % src_regs.rs2_sext
                if src_regs.rs2_sext != 0
                else src_regs.rs1_sext,
            ),
            InstType.REMU: ExStage.ArithmeticLogicalOp(
                check_exception=None
                if src_regs.rs2 != 0
                else ExceptionCode.ILLEGAL_INST,
                compute_result=lambda: src_regs.rs1 % src_regs.rs2
                if src_regs.rs2 != 0
                else src_regs.rs1,
            ),
        }
        al_op = table.get(decode_data.inst_type, None)
        if al_op is None:
            # Decodeできていればここには来ないはず
            logging.warning(f"Unknown instruction type: {decode_data.r.funct3=}")
            return None, ExceptionCode.ILLEGAL_INST
        # shiftrやaddで超えるケースがあるのでmask
        rd_data &= (1 << SysAddr.NUM_WORD_BITS) - 1
        # WB stageでの書き戻しのみ指定
        return ExStage.Result(
            decode_data=decode_data.fetch_data,
            action_bits=AfterExAction.WRITEBACK,
            writeback_idx=decode_data.operand.r.rd,
            writeback_data=al_op.compute_result(),
        ), al_op.check_exception()

    @classmethod
    def _run_i_arithmetic(
        cls, decode_data: IdStage.Result, reg_file: RegFile
    ) -> Tuple[Optional["ExStage.Result"], ExceptionCode | None]:
        # read rs1
        src_regs, regs_ex = reg_file.read_srcregs(
            rs1_idx=decode_data.operand.i.rs1, rs2_idx=0
        )
        if regs_ex is not None:
            return None, regs_ex
        rd_data = 0
        # 命令ごと分岐: inst_type -> func[[] -> rd_data]
        table: Dict[InstType, ExStage.ArithmeticLogicalOp] = {
            # Base Integer
            InstType.ADDI: ExStage.ArithmeticLogicalOp(
                compute_result=lambda: src_regs.rs1_sext
                + decode_data.operand.i.imm_sext,
            ),
            InstType.SLLI: ExStage.ArithmeticLogicalOp(
                check_exception=lambda: None,
                compute_result=lambda: src_regs.rs1_sext << decode_data.operand.i.imm,
            ),
            InstType.SLTI: ExStage.ArithmeticLogicalOp(
                check_exception=lambda: None,
                compute_result=lambda: src_regs.rs1_sext
                < decode_data.operand.i.imm_sext,
            ),
            InstType.SLTIU: ExStage.ArithmeticLogicalOp(
                compute_result=lambda: src_regs.rs1 < decode_data.operand.i.imm,
            ),
            InstType.XORI: ExStage.ArithmeticLogicalOp(
                compute_result=lambda: src_regs.rs1 ^ decode_data.operand.i.imm,
            ),
            InstType.SRLI: ExStage.ArithmeticLogicalOp(
                compute_result=lambda: src_regs.rs1 >> decode_data.operand.i.imm,
            ),
            InstType.SRAI: ExStage.ArithmeticLogicalOp(
                check_exception=lambda: None,
                compute_result=lambda: src_regs.rs1_sext >> decode_data.operand.i.imm,
            ),
            InstType.ORI: ExStage.ArithmeticLogicalOp(
                compute_result=lambda: src_regs.rs1 | decode_data.operand.i.imm,
            ),
            InstType.ANDI: ExStage.ArithmeticLogicalOp(
                compute_result=lambda: src_regs.rs1 & decode_data.operand.i.imm,
            ),
        }
        al_op = table.get(decode_data.inst_type, None)
        if al_op is None:
            # Decodeできていればここには来ないはず
            logging.warning(f"Unknown instruction type: {decode_data.i.funct3=}")
            return None, ExceptionCode.ILLEGAL_INST
        # WB stageでの書き戻しのみ指定
        return ExStage.Result(
            decode_data=decode_data.fetch_data,
            action_bits=AfterExAction.WRITEBACK,
            writeback_idx=decode_data.operand.i.rd,
            writeback_data=al_op.compute_result(),
        ), al_op.check_exception()

    @classmethod
    def _run_i_load(
        cls, decode_data: IdStage.Result, reg_file: RegFile
    ) -> Tuple[Optional["ExStage.Result"], ExceptionCode | None]:
        # read rs1
        src_regs, regs_ex = reg_file.read_srcregs(
            rs1_idx=decode_data.operand.i.rs1, rs2_idx=0
        )
        if regs_ex is not None:
            # rs1 read error
            return None, regs_ex

        # mem sizeは命令で分岐
        table: Dict[InstType, ExStage.LoadOp] = {
            InstType.LB: ExStage.LoadOp(
                mem_addr=lambda: src_regs.rs1 + decode_data.operand.i.imm_sext,
                mem_size=lambda: 1,
            ),
            InstType.LH: ExStage.LoadOp(
                mem_addr=lambda: src_regs.rs1 + decode_data.operand.i.imm_sext,
                mem_size=lambda: 2,
            ),
            InstType.LW: ExStage.LoadOp(
                mem_addr=lambda: src_regs.rs1 + decode_data.operand.i.imm_sext,
                mem_size=lambda: 4,
            ),
            InstType.LBU: ExStage.LoadOp(
                mem_addr=lambda: src_regs.rs1 + decode_data.operand.i.imm_sext,
                mem_size=lambda: 1,
            ),
            InstType.LHU: ExStage.LoadOp(
                mem_addr=lambda: src_regs.rs1 + decode_data.operand.i.imm_sext,
                mem_size=lambda: 2,
            ),
        }
        load_op = table.get(decode_data.inst_type, None)
        if load_op is None:
            # Decodeできていればここには来ないはず
            logging.warning(f"Unknown instruction type: {decode_data.i.funct3=}")
            return None, ExceptionCode.ILLEGAL_INST
        # MEM stageでの読み出しを指定
        return ExStage.Result(
            decode_data=decode_data.fetch_data,
            action_bits=AfterExAction.LOAD | AfterExAction.WRITEBACK,
            mem_addr=load_op.mem_addr(),
            mem_size=load_op.mem_addr(),
            writeback_idx=decode_data.operand.i.rd,
            writeback_data=None,  # MEM stageで決定
        ), None

    def _run_s_store(
        cls, decode_data: IdStage.Result, reg_file: RegFile
    ) -> Tuple[Optional["ExStage.Result"], ExceptionCode | None]:
        # read rs1, rs2
        src_regs, regs_ex = reg_file.read_srcregs(
            rs1_idx=decode_data.operand.s.rs1, rs2_idx=decode_data.operand.s.rs2
        )
        if regs_ex is not None:
            return None, regs_ex
        # MEM stageで実行する内容を決定
        table: Dict[InstType, ExStage.StoreOp] = {
            InstType.SB: ExStage.StoreOp(
                mem_addr=lambda: src_regs.rs1 + decode_data.operand.s.imm_sext,
                mem_size=lambda: 1,
                store_data=lambda: src_regs.rs2 & 0xFF,
            ),
            InstType.SH: ExStage.StoreOp(
                mem_addr=lambda: src_regs.rs1 + decode_data.operand.s.imm_sext,
                mem_size=lambda: 2,
                store_data=lambda: src_regs.rs2 & 0xFFFF,
            ),
            InstType.SW: ExStage.StoreOp(
                mem_addr=lambda: src_regs.rs1 + decode_data.operand.s.imm_sext,
                mem_size=lambda: 4,
                store_data=lambda: src_regs.rs2 & 0xFFFFFFFF,
            ),
        }
        store_op = table.get(decode_data.inst_type, None)
        if store_op is None:
            # Decodeできていればここには来ないはず
            logging.warning(f"Unknown instruction type: {decode_data.s.funct3=}")
            return None, ExceptionCode.ILLEGAL_INST
        # MEM stageでの書き込みを指定
        return ExStage.Result(
            decode_data=decode_data.fetch_data,
            action_bits=AfterExAction.STORE,
            mem_addr=store_op.mem_addr(),
            mem_size=store_op.mem_size(),
            mem_data=store_op.store_data(),
        ), None

    @classmethod
    def _run_b_branch(
        cls, decode_data: IdStage.Result, reg_file: RegFile
    ) -> Tuple[Optional["ExStage.Result"], ExceptionCode | None]:
        # read rs1, rs2
        src_regs, regs_ex = reg_file.read_srcregs(
            rs1_idx=decode_data.operand.b.rs1, rs2_idx=decode_data.operand.b.rs2
        )
        if regs_ex is not None:
            return None, regs_ex
        # Branch条件成立
        table: Dict[InstType, ExStage.BranchOp] = {
            InstType.BEQ: ExStage.BranchOp(
                branch_addr=lambda: decode_data.fetch_data.pc
                + decode_data.operand.b.imm_sext,
                branch_cond=lambda: src_regs.rs1 == src_regs.rs2,
            ),
            InstType.BNE: ExStage.BranchOp(
                branch_addr=lambda: decode_data.fetch_data.pc
                + decode_data.operand.b.imm_sext,
                branch_cond=lambda: src_regs.rs1 != src_regs.rs2,
            ),
            InstType.BLT: ExStage.BranchOp(
                branch_addr=lambda: decode_data.fetch_data.pc
                + decode_data.operand.b.imm_sext,
                branch_cond=lambda: src_regs.rs1 < src_regs.rs2,
            ),
            InstType.BGE: ExStage.BranchOp(
                branch_addr=lambda: decode_data.fetch_data.pc
                + decode_data.operand.b.imm_sext,
                branch_cond=lambda: src_regs.rs1 >= src_regs.rs2,
            ),
            InstType.BLTU: ExStage.BranchOp(
                branch_addr=lambda: decode_data.fetch_data.pc
                + decode_data.operand.b.imm,
                branch_cond=lambda: src_regs.rs1 < src_regs.rs2,
            ),
            InstType.BGEU: ExStage.BranchOp(
                branch_addr=lambda: decode_data.fetch_data.pc
                + decode_data.operand.b.imm,
                branch_cond=lambda: src_regs.rs1 >= src_regs.rs2,
            ),
        }
        branch_op = table.get(decode_data.inst_type, None)
        if branch_op is None:
            # Decodeできていればここには来ないはず
            logging.warning(f"Unknown instruction type: {decode_data.b.funct3=}")
            return None, ExceptionCode.ILLEGAL_INST

        # Branch条件成立有無と次のPCを返す
        return ExStage.Result(
            decode_data=decode_data.fetch_data,
            action_bits=AfterExAction.BRANCH,
            branch_addr=branch_op.branch_addr(),
            branch_cond=branch_op.branch_cond(),
        ), None

    @classmethod
    def _run_u_lui(
        cls, decode_data: IdStage.Result, reg_file: RegFile
    ) -> Tuple[Optional["ExStage.Result"], ExceptionCode | None]:
        # LUI: rd = imm[31:12]
        imm = decode_data.operand.u.imm << 12
        return ExStage.Result(
            decode_data=decode_data.fetch_data,
            action_bits=AfterExAction.WRITEBACK,
            writeback_idx=decode_data.operand.u.rd,
            writeback_data=imm,
        ), None

    @classmethod
    def _run_u_auipc(
        cls, decode_data: IdStage.Result, reg_file: RegFile
    ) -> Tuple[Optional["ExStage.Result"], ExceptionCode | None]:
        # AUIPC: rd = pc + imm[31:12]
        imm = decode_data.operand.u.imm << 12
        return ExStage.Result(
            decode_data=decode_data.fetch_data,
            action_bits=AfterExAction.WRITEBACK,
            writeback_idx=decode_data.operand.u.rd,
            writeback_data=decode_data.fetch_data.pc + imm,
        ), None

    @classmethod
    def _run_j_jal(
        cls, decode_data: IdStage.Result, reg_file: RegFile
    ) -> Tuple[Optional["ExStage.Result"], ExceptionCode | None]:
        # JAL: rd = pc + 4, pc = pc + imm
        imm = decode_data.operand.j.imm << 1
        return ExStage.Result(
            decode_data=decode_data.fetch_data,
            action_bits=AfterExAction.BRANCH | AfterExAction.WRITEBACK,
            writeback_idx=decode_data.operand.j.rd,
            writeback_data=decode_data.fetch_data.pc + SysAddr.NUM_WORD_BYTES,
            branch_addr=decode_data.fetch_data.pc + imm,
            branch_cond=True,
        ), None

    @classmethod
    def _run_i_jalr(
        cls, decode_data: IdStage.Result, reg_file: RegFile
    ) -> Tuple[Optional["ExStage.Result"], ExceptionCode | None]:
        # JALR: rd = pc + 4, pc = rs1 + imm
        src_regs, regs_ex = reg_file.read_srcregs(
            rs1_idx=decode_data.operand.i.rs1, rs2_idx=0
        )
        if regs_ex is not None:
            return None, regs_ex
        return ExStage.Result(
            decode_data=decode_data.fetch_data,
            action_bits=AfterExAction.BRANCH | AfterExAction.WRITEBACK,
            writeback_idx=decode_data.operand.i.rd,
            writeback_data=decode_data.fetch_data.pc + SysAddr.NUM_WORD_BYTES,
            branch_addr=src_regs.rs1 + decode_data.operand.i.imm_sext,
            branch_cond=True,
        ), None

    @classmethod
    def _run_r_atomic(
        cls, decode_data: IdStage.Result, reg_file: RegFile
    ) -> Tuple[Optional["ExStage.Result"], ExceptionCode | None]:
        # TODO: implement
        # - Aquire memory,  Release memory fieldの命令保証するためには Pipelineの状態確認が必要
        # - LR/SCのためにメモリ予約とその確認が必要
        # - Swap/Atomic XXX のために、MEM stageで読み出した値をWB stageまでに変更する必要がある
        return None, ExceptionCode.ILLEGAL_INST

    @classmethod
    def run(
        cls,
        decode_data: IdStage.Result,
        reg_file: RegFile,
    ) -> Tuple[Optional["ExStage.Result"], ExceptionCode | None]:
        table: Dict[
            InstGroup, Callable[[IdStage.Result, RegFile], ExceptionCode | None]
        ] = {
            InstGroup.NOP: cls._run_r_arithmetic,  # ADDI 0,0,0
            InstGroup.R_ARITHMETIC_LOGICAL_MULTIPLY: cls._run_r_arithmetic,
            InstGroup.I_ARITHMETIC_LOGICAL: cls._run_i_arithmetic,
            InstGroup.S_STORE: cls._run_s_store,
            InstGroup.B_BRANCH: cls._run_b_branch,
            InstGroup.U_LUI: cls._run_u_lui,
            InstGroup.U_AUIPC: cls._run_u_auipc,
            InstGroup.J_JAL: cls._run_j_jal,
            InstGroup.J_JALR: cls._run_i_jalr,
            InstGroup.R_ATOMIC: cls._run_r_atomic,
            # InstFmt.I_ENV: cls._run_itype,
        }
        execution_function = table.get(decode_data.inst_fmt, None)
        # 未定義命令
        if execution_function is None:
            logging.warning(f"Unknown instruction format: {decode_data.inst_fmt=}")
            return None, ExceptionCode.ILLEGAL_INST
        # 命令実行
        return execution_function(decode_data, reg_file)


class MemStage:
    @dataclass
    class Result:
        # ex result
        exec_data: ExStage.Result

        def __repr__(self) -> str:
            return "[MEM](TODO)"

    @classmethod
    def run(
        cls,
        exec_data: ExStage.Result,
        slave: BusSlave,
    ) -> Tuple[Optional["MemStage.Result"], ExceptionCode | None]:
        # TODO: implement
        return MemStage.Result(exec_data=exec_data), None


class WbStage:
    """
    WriteBack
    """

    @dataclass
    class Result:
        # mem result
        mem_data: MemStage.Result

        def __repr__(self) -> str:
            return "[WB ](TODO)"

    @classmethod
    def run(
        cls, mem_data: MemStage.Result
    ) -> Tuple[Optional["WbStage.Result"], ExceptionCode | None]:
        # TODO: implement
        return WbStage.Result(mem_data=mem_data), None


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
        """
        Execute one cycle
        非pipeline single cycle processor想定
        """
        logging.debug(
            "###################################################################################################################################"
        )

        # IF: Instruction Fetch
        if_data, if_ex = IfStage.run(pc=self.pc, slave=self.slave)
        logging.debug(f"[{self.cycles}]{if_data}")
        if if_ex is not None:
            logging.warning(f"Fetch Error: {if_ex=}")
            raise RuntimeError(f"TODO: impl Exception Handler: {if_ex=}")
        assert if_data is not None

        # ID: Instruction Decode
        id_data, id_ex = IdStage.run(fetch_data=if_data)
        logging.debug(f"[{self.cycles}]{id_data}")
        if id_ex is not None:
            logging.warning(f"Decode Error: {id_ex=}")
            raise RuntimeError(f"TODO: impl Exception Handler: {id_ex=}")
        assert id_data is not None

        # EX: Execute
        ex_data, ex_ex = ExStage.run(decode_data=id_data, reg_file=self.regs)
        logging.debug(f"[{self.cycles}]{ex_data}")
        if ex_ex is not None:
            logging.warning(f"Execute Error: {ex_ex=}")
            raise RuntimeError(f"TODO: impl Exception Handler: {ex_ex=}")
        assert ex_data is not None

        # MEM: Memory Access
        mem_data, mem_ex = MemStage.run(exec_data=ex_data, slave=self.slave)
        logging.debug(f"[{self.cycles}]{mem_data}")
        if mem_ex is not None:
            logging.warning(f"Memory Access Error: {mem_ex=}")
            raise RuntimeError(f"TODO: impl Exception Handler: {mem_ex=}")
        assert mem_data is not None

        # WB: WriteBack
        wb_data, wb_ex = WbStage.run(mem_data=mem_data)
        logging.debug(f"[{self.cycles}]{wb_data}")
        if wb_ex is not None:
            logging.warning(f"WriteBack Error: {wb_ex=}")
            raise RuntimeError(f"TODO: impl Exception Handler: {wb_ex=}")
        assert wb_data is not None

        # Next PC/cycles
        self.pc += SysAddr.NUM_WORD_BYTES  # TODO: branch
        self.cycles += 1

        # TODO: Exception, Interrupt, Debug, etc...
