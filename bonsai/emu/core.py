import enum
import logging
from ctypes import LittleEndianStructure, LittleEndianUnion, c_uint
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

from emu.mem import BusSlave, SysAddr


class CoreException(enum.Enum):
    """
    CPU例外の種類
    """

    # 命令アクセス例外
    INST_ACCESS = enum.auto()
    # 命令デコード例外
    INST_DECODE = enum.auto()
    # 命令実行例外
    INST_EXECUTE = enum.auto()
    # データアクセス例外
    DATA_ACCESS = enum.auto()
    # ecall
    ENV_CALL = enum.auto()
    # ebreak
    ENV_BREAK = enum.auto()
    # 割り込み
    INTERRUPT = enum.auto()
    # トラップ
    TRAP = enum.auto()


@dataclass
class CoreConfig:
    """
    Core configuration
    """

    # Memory space
    space: SysAddr
    # 初期化時点でのPC
    init_pc: int


@dataclass
class RegFile:
    """
    Register file
    """

    # 汎用レジスタ32本
    regs: List[SysAddr.AddrU32] = field(default_factory=lambda: [0] * 32)

    # register本数
    num_regs_nax: int = 32
    # E Extensionの場合、レジスタ本数制限が入る
    num_regs_current: int = 32

    def clear(self) -> None:
        """
        Clear all registers
        """
        self.regs = [0] * 32

    def read(
        self, addr: SysAddr.AddrU32
    ) -> Tuple[SysAddr.DataU32, CoreException | None]:
        """
        Read a register
        """
        assert 0 <= addr < 32, f"Invalid register address: {addr=}"
        # zero register
        if addr == 0:
            return 0
        # invalid register address
        if addr >= self.num_regs_current:
            logging.warning(f"Invalid register address: {addr=}")
            return 0, CoreException.REG_ACCESS
        return self.regs[addr], None

    def write(
        self, addr: SysAddr.AddrU32, data: SysAddr.DataU32
    ) -> CoreException | None:
        """
        Write a register
        """
        assert 0 <= addr < 32, f"Invalid register address: {addr=}"
        # zero register
        if addr == 0:
            return
        # invalid register address
        if addr >= self.num_regs_current:
            logging.warning(f"Invalid register address: {addr=}")
            return CoreException.REG_ACCESS
        self.regs[addr] = data
        return None


class InstFetch:
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
    ) -> Tuple["InstFetch.Result", CoreException | None]:
        exception: CoreException | None = None
        # 命令データ取得
        inst_data, access_ret = slave.read(pc)
        if access_ret is not None:
            logging.warning(f"Failed to read instruction: {pc=}, {access_ret=}")
            exception = CoreException.INST_ACCESS
        return InstFetch.Result(pc, inst_data), exception


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
        ("reserved", c_uint, 25),
        ("opcode", c_uint, 7),
    ]


class InstRType(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("funct7", c_uint, 7),
        ("rs2", c_uint, 5),
        ("rs1", c_uint, 5),
        ("funct3", c_uint, 3),
        ("rd", c_uint, 5),
        ("opcode", c_uint, 7),
    ]


class InstIType(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("imm_11_0", c_uint, 12),
        ("rs1", c_uint, 5),
        ("funct3", c_uint, 3),
        ("rd", c_uint, 5),
        ("opcode", c_uint, 7),
    ]

    @property
    def imm(self) -> int:
        return self.imm_11_0


class InstSType(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("imm_11_5", c_uint, 7),
        ("rs2", c_uint, 5),
        ("rs1", c_uint, 5),
        ("funct3", c_uint, 3),
        ("imm_4_0", c_uint, 5),
        ("opcode", c_uint, 7),
    ]

    @property
    def imm(self) -> int:
        return (self.imm_11_5 << 5) | self.imm_4_0


class InstBType(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("imm_12", c_uint, 1),
        ("imm_10_5", c_uint, 6),
        ("rs2", c_uint, 5),
        ("rs1", c_uint, 5),
        ("funct3", c_uint, 3),
        ("imm_4_1", c_uint, 4),
        ("imm_11", c_uint, 1),
        ("opcode", c_uint, 7),
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
        ("imm_31_12", c_uint, 20),
        ("rd", c_uint, 5),
        ("opcode", c_uint, 7),
    ]

    @property
    def imm(self) -> int:
        return self.imm_31_12 << 12


class InstJType(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("imm_20", c_uint, 1),
        ("imm_10_1", c_uint, 10),
        ("imm_11", c_uint, 1),
        ("imm_19_12", c_uint, 8),
        ("rd", c_uint, 5),
        ("opcode", c_uint, 7),
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
        ("funct5", c_uint, 5),
        ("aq", c_uint, 1),
        ("rl", c_uint, 1),
        ("rs2", c_uint, 5),
        ("rs1", c_uint, 5),
        ("funct3", c_uint, 3),
        ("rd", c_uint, 5),
        ("opcode", c_uint, 7),
    ]


class DecodedInst(LittleEndianUnion):
    _pack_ = 1
    _fields_ = [
        ("raw", c_uint),
        ("common", InstCommon),
        ("r", InstRType),
        ("i", InstIType),
        ("s", InstSType),
        ("b", InstBType),
        ("u", InstUType),
        ("j", InstJType),
        ("atomic", InstAtomicType),
    ]


class InstDecode:
    """
    命令デコードを実行する
    """

    @dataclass
    class Result:
        # 命令配置場所
        pc: SysAddr.AddrU32
        # 命令生データ
        raw: SysAddr.DataU32
        # 命令フォーマット
        i_fmt: InstFmt
        # 命令タイプ
        i_type: InstType
        # 命令データ
        i_data: DecodedInst

    @classmethod
    def decode(
        cls, if_ret: InstFetch.Result
    ) -> Tuple["InstDecode.Result" | None, CoreException | None]:
        # 命令デコード
        i_data = DecodedInst()
        i_data.raw = if_ret.raw
        # 命令フォーマット/タイプ
        try:
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
                i_type = table[i_data.r.funct3][i_data.r.funct7]
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
                i_type = table[i_data.i.funct3]()
            elif i_fmt == InstFmt.S:
                # funct3 -> type
                table: Dict[int, InstType] = {
                    0b000: InstType.SB,
                    0b001: InstType.SH,
                    0b010: InstType.SW,
                }
                i_type = table[i_data.s.funct3]
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
                i_type = table[i_data.b.funct3]
            elif i_fmt in [InstFmt.U_LUI, InstFmt.U_AUIPC]:
                # opcode -> type
                table: Dict[int, InstType] = {
                    InstFmt.U_LUI: InstType.LUI,
                    InstFmt.U_AUIPC: InstType.AUIPC,
                }
                i_type = table[i_fmt]
            elif i_fmt in [InstFmt.J_JAL, InstFmt.J_JALR]:
                # opcode -> type
                table: Dict[int, InstType] = {
                    InstFmt.J_JAL: InstType.JAL,
                    InstFmt.J_JALR: InstType.JALR,
                }
                i_type = table[i_fmt]
            elif i_fmt == InstFmt.I_ENV:
                # imm -> type
                table: Dict[int, InstType] = {
                    0b000: InstType.ECALL,
                    0b001: InstType.EBREAK,
                }
                i_type = table[i_data.i.imm]
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
                i_type = table[i_data.atomic.funct5]
            else:
                logging.warning(f"Unknown instruction format: {i_fmt=}")
                return None, CoreException.INST_DECODE

            if i_type is None or i_type not in InstType:
                logging.warning(f"Unknown instruction type: {i_type=}")
                return None, CoreException.INST_DECODE

            return cls.Result(
                pc=if_ret.pc,
                raw=if_ret.raw,
                i_fmt=i_fmt,
                i_type=i_type,
                i_data=i_data,
            ), None

        except ValueError as e:
            logging.warning(f"Unknown instruction: {if_ret.raw=:08x}")
            return None, CoreException.INST_DECODE


@dataclass
class ExStage:
    """
    EX stageの結果
    """

    # rdへの書き戻しがあれば値をいれる
    write_rd_from_alu: SysAddr.DataU32 | None = None
    # メモリからデータ取得が必要であればアドレスをいれる
    # addr -> reg_addr
    write_rd_from_mem: Tuple[SysAddr.AddrU32, int] | None = None
    # メモリへの書き込みが必要であればアドレスとデータをいれる
    # addr -> data
    write_mem_from_alu: Tuple[SysAddr.AddrU32, SysAddr.DataU32] | None = None
    # PCの更新が必要であればアドレスをいれる
    write_pc: SysAddr.AddrU32 | None = None
    # TODO: ecall/ebreakなどの例外が発生した場合の処理を追加

    @classmethod
    def _execute_r(
        cls,
        inst_data: IdStage,
        regs: RegFile,
        reg_bit_width: int,
    ) -> Tuple["ExStage", CoreException | None]:
        """
        Execute R-Type instruction
        """
        exception: CoreException | None = None
        # resouce
        rs1_data, rs1_ex = regs.read(inst_data.rs1)
        rs2_data, rs2_ex = regs.read(inst_data.rs2)
        rs1_data_se = inst_data.sign_ext(rs1_data, reg_bit_width)
        rs2_data_se = inst_data.sign_ext(rs2_data, reg_bit_width)
        rd_data = 0
        # 命令ごと分岐: inst_type -> func[[] -> rd_data]
        table: Dict[
            InstType,
            Callable[SysAddr.DataU32],
        ] = {
            # Base Integer
            InstType.ADD: lambda: rs1_data_se + rs2_data_se,
            InstType.SUB: lambda: rs1_data_se - rs2_data_se,
            InstType.XOR: lambda: rs1_data ^ rs2_data,
            InstType.OR: lambda: rs1_data | rs2_data,
            InstType.AND: lambda: rs1_data & rs2_data,
            InstType.SLL: lambda: rs1_data_se << rs2_data_se,
            InstType.SRL: lambda: rs1_data >> rs2_data,
            InstType.SRA: lambda: rs1_data_se >> rs2_data,
            InstType.SLT: lambda: rs1_data_se < rs2_data_se,
            InstType.SLTU: lambda: rs1_data < rs2_data,
            # Multiply Extension
            InstType.MUL: lambda: rs1_data_se * rs2_data_se,
            InstType.MULH: lambda: rs1_data_se * rs2_data_se >> reg_bit_width,
            InstType.MULSU: lambda: (rs1_data * rs2_data_se) >> reg_bit_width,
            InstType.MULU: lambda: (rs1_data * rs2_data) >> reg_bit_width,
            InstType.DIV: lambda: rs1_data_se // rs2_data_se,
            InstType.DIVU: lambda: rs1_data // rs2_data,
            InstType.REM: lambda: rs1_data_se % rs2_data_se,
            InstType.REMU: lambda: rs1_data % rs2_data,
        }
        # Decodeできていればここには来ないはず
        if inst_data.type not in table:
            raise NotImplementedError(f"Unknown instruction: {inst_data.type=}")

        # TODO: 実行時例外の対応
        rd_data = table[inst_data.type]()
        # shiftrやaddで超えるケースがあるのでmask
        rd_data &= (1 << reg_bit_width) - 1
        return rd_data

    def _execute_i(
        cls,
        inst_data: IdStage,
        regs: RegFile,
        reg_bit_width: int,
    ) -> SysAddr.DataU32:
        """
        Execute I-Type instruction
        """
        exception: CoreException | None = None
        # resouce
        rs1_data, rs1_ex = regs.read(inst_data.rs1)
        rs1_data_se = inst_data.sign_ext(rs1_data, reg_bit_width)
        rd_data = 0
        # 命令ごと分岐: inst_type -> func[[] -> rd_data]
        table: Dict[
            InstType,
            Callable[SysAddr.DataU32],
        ] = {
            InstType.ADDI: lambda: rs1_data_se + inst_data.imm_se,
            InstType.XORI: lambda: rs1_data ^ inst_data.imm,
            InstType.ORI: lambda: rs1_data | inst_data.imm,
            InstType.ANDI: lambda: rs1_data & inst_data.imm,
            InstType.SLLI: lambda: rs1_data_se << inst_data.imm_lower,
            InstType.SRLI: lambda: rs1_data >> inst_data.imm_lower,
            InstType.SRAI: lambda: rs1_data_se >> inst_data.imm_lower,
            InstType.SLTI: lambda: rs1_data_se < inst_data.imm_se,
            InstType.SLTIU: lambda: rs1_data < inst_data.imm,
        }
        # Decodeできていればここには来ないはず
        if inst_data.type not in table:
            raise NotImplementedError(f"Unknown instruction: {inst_data.type=}")

        # TODO: 実行時例外の対応
        rd_data = table[inst_data.type]()
        # shiftrやaddで超えるケースがあるのでmask
        rd_data &= (1 << reg_bit_width) - 1
        return rd_data

    @classmethod
    def execute(
        cls, inst_data: IdStage, regs: RegFile, reg_bit_width: int
    ) -> Tuple["ExStage", CoreException | None]:
        """
        execute stage: Decodeした結果とPC(inst_dataに内包)/Reg値から命令を実行
        Reg/Memの書き戻しは現時点ではせず、MEM/WBへの指示として返す
        """
        # 命令タイプ: inst_fmt -> func
        table: Dict[
            InstFmt,
            Callable[[IdStage, RegFile, int], "ExStage"],
        ] = {
            InstFmt.R: cls._execute_r,
            InstFmt.I: cls._execute_i,
            # InstFmt.I: cls._decode_i,
            # InstFmt.S: cls._decode_s,
            # InstFmt.B: cls._decode_b,
            # InstFmt.U_LUI: cls._decode_u,
            # InstFmt.U_AUIPC: cls._decode_u,
            # InstFmt.J_JAL: cls._decode_j,
            # InstFmt.R_ATOMIC: cls._decode_r_atomic,
        }
        dst = table.get(inst_data.fmt, None)

        # TODO: exのArithmetic ExやEcallなどもあるので例外処理いれる
        # if dst is None:
        #     # Decodeできていればここには来ないはず
        #     raise NotImplementedError(
        #         f"Unknown instruction format: {inst_data.inst_fmt=}"
        #     )

        # reg_bit_width は Compressed Extension がある場合に動的に切り替わるのでMemSpace直参照せず、引数で受ける
        return dst(inst_data, regs, reg_bit_width)


class Core:
    def __init__(self, config: CoreConfig, slave: BusSlave):
        self.slave = slave
        # 設定参照用にstore
        self.config = config
        # RegisterFile & PC
        self.regs = RegFile()
        self.pc: SysAddr.AddrU32 = 0

    def reset(self) -> None:
        """
        Reset the core
        """
        self.regs.clear()
        self.pc = self.config.init_pc

    def step_cyc(self) -> None:
        """
        1cyc分進める
        """
        # IF: Instruction Fetch
        if_data, if_ex = IfStage.run(pc=self.pc, slave=self.slave)
        if if_ex is not None:
            logging.warning(f"Fetch Error: {if_ex=}")
            raise RuntimeError(f"TODO: impl Exception Handler: {if_ex=}")

        # ID: Instruction Decode
        id_data, id_ex = IdStage.run(fetch_data=if_data)
        if id_ex is not None:
            logging.warning(f"Decode Error: {id_ex=}")
            raise RuntimeError(f"TODO: impl Exception Handler: {id_ex=}")

        # EX: Execute
        ex_data, ex_ex = ExStage.run(id_data, self.regs, self.config.reg_bit_width)
        if ex_ex is not None:
            logging.warning(f"Execute Error: {ex_ex=}")
            raise RuntimeError(f"TODO: impl Exception Handler: {ex_ex=}")
        # MEM
        # TODO: Implement MEM stage
        # WB
        # TODO: Implement WB stage

        # TODO: Exception, Interrupt, Debug, etc...
