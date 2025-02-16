import enum
from dataclasses import dataclass, field
from typing import Callable, Dict, List

from emu.mem import BusSlave, MemSpace


@dataclass
class CoreConfig:
    """
    Core configuration
    """

    # Memory space
    space: MemSpace
    # 初期化時点でのPC
    init_pc: int


@dataclass
class RegFile:
    """
    Register file
    """

    # 汎用レジスタ32本
    regs: List[MemSpace.AbstAddrType] = field(default_factory=lambda: [0] * 32)

    def clear(self) -> None:
        """
        Clear all registers
        """
        self.regs = [0] * 32

    def read(self, addr: MemSpace.AbstAddrType) -> MemSpace.AbstDataType:
        """
        Read a register
        """
        # zero register
        if addr == 0:
            return 0
        return self.regs[addr]

    def write(self, addr: MemSpace.AbstAddrType, data: MemSpace.AbstDataType) -> None:
        """
        Write a register
        """
        # zero register
        if addr == 0:
            return
        self.regs[addr] = data


@enum.unique
class InstFmt(enum.IntEnum):
    """
    Instruction format
    """

    # Emulator Only (Undefined)
    DEBUG_UNDEFINED = 0
    # opcodeごとかつ解釈が異なるタイプごとに定義
    R = 0b0110011
    I = 0b0010011
    S = 0b0100011
    B = 0b1100011
    U_LUI = 0b0110111
    U_AUIPC = 0b0010111
    J_JAL = 0b1101111
    J_JALR = 0b1100111
    R_ATOMIC = 0b0101111


@enum.unique
class InstType(enum.Enum):
    """
    Instruction Names
    """

    # Emulator Only (Undefined)
    DEBUG_UNDEFINED = enum.auto()
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
    MULHSU = enum.auto()
    MULHU = enum.auto()
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
    # Floating Point Extension
    # TODO: Implement the floating point extension


@dataclass
class InstData:
    """
    命令データ

    Core Instruction Formats:
        | R-Type (Register Type):  | funct7@31-25                 | rs2@24-20 | rs1@19-15 | funct3@14-12 | rd@11-7          | opcode@6-0 |
        | I-Type (Immediate Type): | imm[11:0]@31-20                          | rs1@19-15 | funct3@14-12 | rd@11-7          | opcode@6-0 |
        | S-Type (Store Type):     | imm[11:5]@31-25              | rs2@24-20 | rs1@19-15 | funct3@14-12 | imm[4:0]@11-7    | opcode@6-0 |
        | B-Type (Branch Type):    | imm[12|10:5]@31-25           | rs2@24-20 | rs1@19-15 | funct3@14-12 | imm[4:1|11]@11-7 | opcode@6-0 |
        | U-Type (Upper Type):     | imm[31:12]@31-12                                                    | rd@11-7          | opcode@6-0 |
        | J-Type (Jump Type):      | imm[20|10:1|11|19:12]@31-25                                         | rd@11-7          | opcode@6-0 |

    Atomic Extension Instruction Formats:
        | R-Type                   | funct5@31-27 | aq@26 | rl@25 | rs2@24-20 | rs1@19-15 | funct3@14-12 | rd@11-7          | opcode@6-0 |
    """

    #######################################
    # 共通要素
    # 命令配置場所
    inst_addr: MemSpace.AbstAddrType
    # 命令生データ
    inst_data: MemSpace.AbstDataType
    # 命令フォーマット
    inst_fmt: InstFmt
    # 命令タイプ
    inst_type: InstType
    #######################################
    # 命令データ
    # register souce 1
    rs1: MemSpace.AbstDataType | None = None
    # register souce 2
    rs2: MemSpace.AbstDataType | None = None
    # register destination
    rd: MemSpace.AbstDataType | None = None
    # immediate value
    imm: MemSpace.AbstDataType | None = None
    # immediate value sign extended (for B-Type)
    imm_se: MemSpace.AbstDataSignedType | None = None
    # funct3
    funct3: MemSpace.AbstDataType | None = None
    # funct7
    funct7: MemSpace.AbstDataType | None = None
    #######################################
    # for Atomic Extension
    # funct5
    func5: MemSpace.AbstDataType | None = None
    # acquire
    aq: MemSpace.AbstDataType | None = None
    # release
    rl: MemSpace.AbstDataType | None = None

    @classmethod
    def _decode_opcode(cls, inst_data: MemSpace.AbstDataType) -> InstFmt:
        try:
            return InstFmt(inst_data & 0x7F)
        except ValueError as e:
            assert False, f"Unknown opcode: {inst_data}, {e}"
            return InstFmt.DEBUG_UNDEFINED

    @classmethod
    def _sign_ext(
        cls, data: MemSpace.AbstDataType, bit_width: int
    ) -> MemSpace.AbstDataSignedType:
        """
        符号拡張
        """
        if data & (1 << (bit_width - 1)):
            return data - (1 << bit_width)
        return data

    @classmethod
    def _decode_r(
        cls, inst_addr: MemSpace.AbstAddrType, inst_data: MemSpace.AbstDataType
    ) -> "InstData":
        """
        R-Type (Register Type) Decoder
        | R-Type (Register Type):  | funct7@31-25       | rs2@24-20 | rs1@19-15 | funct3@14-12 | rd@11-7          | opcode@6-0 |
        """

        _opcode = inst_data & 0x7F  # Extract bits 6-0 for opcode
        rs1 = (inst_data >> 15) & 0x1F  # Extract bits 19-15 for rs1
        rs2 = (inst_data >> 20) & 0x1F  # Extract bits 24-20 for rs2
        rd = (inst_data >> 7) & 0x1F  # Extract bits 11-7 for rd
        funct3 = (inst_data >> 12) & 0x7  # Extract bits 14-12 for funct3
        funct7 = (inst_data >> 25) & 0x7F  # Extract bits 31-25 for funct7
        # funct3 -> (funct7 -> inst_type)
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
        inst_type = InstType.DEBUG_UNDEFINED
        if funct3 in table and funct7 in table[funct3]:
            inst_type = table[funct3][funct7]
        else:
            assert False, f"Unknown funct3/funct7: {funct3}/{funct7}"

        return cls(
            inst_addr=inst_addr,
            inst_data=inst_data,
            inst_fmt=InstFmt.R,
            inst_type=inst_type,
            rs1=rs1,
            rs2=rs2,
            rd=rd,
            funct3=funct3,
            funct7=funct7,
        )

    @classmethod
    def _decode_i(
        cls, inst_addr: MemSpace.AbstAddrType, inst_data: MemSpace.AbstDataType
    ) -> "InstData":
        """
        I-Type (Immediate Type) Decoder
        | I-Type (Immediate Type): | imm[11:0]@31-20                | rs1@19-15 | funct3@14-12 | rd@11-7          | opcode@6-0 |
        """
        _opcode = inst_data & 0x7F  # Extract bits 6-0 for opcode
        rs1 = (inst_data >> 15) & 0x1F  # Extract bits 19-15 for rs1
        rd = (inst_data >> 7) & 0x1F  # Extract bits 11-7 for rd
        funct3 = (inst_data >> 12) & 0x7  # Extract bits 14-12 for funct3
        imm = (inst_data >> 20) & 0xFFF  # Extract bits 31-20 for imm[11:0]
        imm_se = cls._sign_ext(imm, 12)  # Sign extend the immediate value to 12 bits
        # funct3 -> inst_type
        table: Dict[int, InstType] = {
            0b000: InstType.ADDI,
            0b001: InstType.SLLI,
            0b010: InstType.SLTI,
            0b011: InstType.SLTIU,
            0b100: InstType.XORI,
            0b110: InstType.ORI,
            0b111: InstType.ANDI,
        }
        inst_type = table[funct3]

        return cls(
            inst_addr=inst_addr,
            inst_data=inst_data,
            inst_fmt=InstFmt.I,
            inst_type=inst_type,
            rs1=rs1,
            rd=rd,
            funct3=funct3,
            imm=imm,
            imm_se=imm_se,
        )

    @classmethod
    def _decode_s(
        cls, inst_addr: MemSpace.AbstAddrType, inst_data: MemSpace.AbstDataType
    ) -> "InstData":
        """
        S-Type (Store Type) Decoder
        | S-Type (Store Type):     | imm[11:5]@31-25    | rs2@24-20 | rs1@19-15 | funct3@14-12 | imm[4:0]@11-7    | opcode@6-0 |
        """
        _opcode = inst_data & 0x7F  # Extract bits 6-0 for opcode
        rs1 = (inst_data >> 15) & 0x1F  # Extract bits 19-15 for rs1
        rs2 = (inst_data >> 20) & 0x1F  # Extract bits 24-20 for rs2
        funct3 = (inst_data >> 12) & 0x7  # Extract bits 14-12 for funct3
        imm = ((inst_data >> 25) & 0x7F) << 5 | (
            (inst_data >> 7) & 0x1F
        ) << 0  # Extract bits 31-25 and 11-7 for imm[11:0]
        imm_se = cls._sign_ext(imm, 12)  # Sign extend the immediate value to 12 bits
        # funct3 -> inst_type
        table: Dict[int, InstType] = {
            0b000: InstType.SB,
            0b001: InstType.SH,
            0b010: InstType.SW,
        }
        inst_type = table[funct3]

        return cls(
            inst_addr=inst_addr,
            inst_data=inst_data,
            inst_fmt=InstFmt.S,
            inst_type=inst_type,
            rs1=rs1,
            rs2=rs2,
            funct3=funct3,
            imm=imm,
            imm_se=imm_se,
        )

    def _decode_b(
        cls, inst_addr: MemSpace.AbstAddrType, inst_data: MemSpace.AbstDataType
    ) -> "InstData":
        """
        B-Type (Branch Type) Decoder
        | B-Type (Branch Type):    | imm[12|10:5]@31-25 | rs2@24-20 | rs1@19-15 | funct3@14-12 | imm[4:1|11]@11-7 | opcode@6-0 |
        """
        _opcode = inst_data & 0x7F  # Extract bits 6-0 for opcode
        rs1 = (inst_data >> 15) & 0x1F  # Extract bits 19-15 for rs1
        rs2 = (inst_data >> 20) & 0x1F  # Extract bits 24-20 for rs2
        funct3 = (inst_data >> 12) & 0x7  # Extract bits 14-12 for funct3
        imm = (
            ((inst_data >> 31) & 0x1) << 12  # Extract bit 31 for imm[12]
            | ((inst_data >> 7) & 0x1) << 11  # Extract bit 7 for imm[11]
            | ((inst_data >> 25) & 0x3F) << 5  # Extract bits 30-25 for imm[10:5]
            | ((inst_data >> 8) & 0xF) << 1  # Extract bits 11-8 for imm[4:1]
        )
        imm_se = cls._sign_ext(imm, 13)  # Sign extend the immediate value to 13 bits
        # funct3 -> inst_type
        table: Dict[int, InstType] = {
            0b000: InstType.BEQ,
            0b001: InstType.BNE,
            0b100: InstType.BLT,
            0b101: InstType.BGE,
            0b110: InstType.BLTU,
            0b111: InstType.BGEU,
        }
        inst_type = table[funct3]

        return cls(
            inst_addr=inst_addr,
            inst_data=inst_data,
            inst_fmt=InstFmt.B,
            inst_type=inst_type,
            rs1=rs1,
            rs2=rs2,
            funct3=funct3,
            imm=imm,
            imm_se=imm_se,
        )

    def _decode_u(
        cls, inst_addr: MemSpace.AbstAddrType, inst_data: MemSpace.AbstDataType
    ) -> "InstData":
        """
        U-Type (Upper Type) Decoder
        | U-Type (Upper Type):     | imm[31:12]@31-12                                          | rd@11-7          | opcode@6-0 |
        """
        opcode = inst_data & 0x7F  # Extract bits 6-0 for opcode
        rd = (inst_data >> 7) & 0x1F  # Extract bits 11-7 for rd
        imm = (inst_data >> 12) & 0xFFFFF  # Extract bits 31-12 for imm[31:12]
        imm_se = cls._sign_ext(imm, 20)  # Sign extend the immediate value to 20 bits
        # opcode -> inst_type
        table: Dict[int, InstType] = {
            0b0110111: InstType.LUI,
            0b0010111: InstType.AUIPC,
        }
        inst_type = table[opcode]

        return cls(
            inst_addr=inst_addr,
            inst_data=inst_data,
            inst_fmt=InstFmt.U_LUI,
            inst_type=inst_type,
            rd=rd,
            imm=imm,
            imm_se=imm_se,
        )

    def _decode_j(
        cls, inst_addr: MemSpace.AbstAddrType, inst_data: MemSpace.AbstDataType
    ) -> "InstData":
        """
        J-Type (Jump Type) Decoder
        | J-Type (Jump Type):      | imm[20|10:1|11|19:12]@31-25                               | rd@11-7          | opcode@6-0 |
        """
        opcode = inst_data & 0x7F  # Extract bits 6-0 for opcode
        rd = (inst_data >> 7) & 0x1F  # Extract bits 11-7 for rd
        imm = (
            ((inst_data >> 31) & 0x1) << 20  # Extract bit 31 for imm[20]
            | ((inst_data >> 12) & 0xFF) << 12  # Extract bits 19-12 for imm[19:12]
            | ((inst_data >> 20) & 0x1) << 11  # Extract bit 20 for imm[11]
            | ((inst_data >> 21) & 0x3FF) << 1  # Extract bits 30-21 for imm[10:1]
        )
        imm_se = cls._sign_ext(imm, 21)  # Sign extend the immediate value to 21 bits
        # opcode -> inst_type
        table: Dict[int, InstType] = {
            0b1101111: InstType.JAL,
        }
        inst_type = table[opcode]

        return cls(
            inst_addr=inst_addr,
            inst_data=inst_data,
            inst_fmt=InstFmt.J_JAL,
            inst_type=inst_type,
            rd=rd,
            imm=imm,
            imm_se=imm_se,
        )

    @classmethod
    def _decode_r_atomic(
        cls, inst_addr: MemSpace.AbstAddrType, inst_data: MemSpace.AbstDataType
    ) -> "InstData":
        """
        R-Type (Register Type) for Atomic Decoder
        | R-Type                   | funct5@31-27 | aq@26 | rl@25 | rs2@24-20 | rs1@19-15 | funct3@14-12 | rd@11-7          | opcode@6-0 |
        """

        _opcode = inst_data & 0x7F  # Extract bits 6-0 for opcode
        rs1 = (inst_data >> 15) & 0x1F  # Extract bits 19-15 for rs1
        rs2 = (inst_data >> 20) & 0x1F  # Extract bits 24-20 for rs2
        rd = (inst_data >> 7) & 0x1F  # Extract bits 11-7 for rd
        funct3 = (inst_data >> 12) & 0x7  # Extract bits 14-12 for funct3
        func5 = (inst_data >> 27) & 0x1F  # Extract bits 31-27 for func5
        aq = (inst_data >> 26) & 0x1  # Extract bit 26 for aq
        rl = (inst_data >> 25) & 0x1  # Extract bit 25 for rl
        # funct5 -> inst_type
        table: Dict[int, InstType] = {
            0x02: InstType.LR_W,
            0x03: InstType.SC_W,
            0x01: InstType.AMOSWAP_W,
            0x00: InstType.AMOADD_W,
            0x04: InstType.AMOAND_W,
            0x0C: InstType.AMOOR_W,
            0x08: InstType.AMOXOR_W,
            0x14: InstType.AMOMAX_W,
            0x10: InstType.AMOMIN_W,
        }
        inst_type = table[func5]

        return cls(
            inst_addr=inst_addr,
            inst_data=inst_data,
            inst_fmt=InstFmt.R_ATOMIC,
            inst_type=inst_type,
            rs1=rs1,
            rs2=rs2,
            rd=rd,
            funct3=funct3,
            func5=func5,
            aq=aq,
            rl=rl,
        )

    @classmethod
    def decode(
        cls, inst_addr: MemSpace.AbstAddrType, inst_data: MemSpace.AbstDataType
    ) -> "InstData" | None:
        """
        命令データをデコード
        """
        # 命令フォーマット
        inst_fmt = cls._decode_opcode(inst_data)
        # 命令タイプ: inst_fmt -> func
        table: Dict[
            InstFmt,
            Callable[[MemSpace.AbstAddrType, MemSpace.AbstDataType], "InstData"],
        ] = {
            InstFmt.R: cls._decode_r,
            InstFmt.I: cls._decode_i,
            InstFmt.S: cls._decode_s,
            InstFmt.B: cls._decode_b,
            InstFmt.U_LUI: cls._decode_u,
            InstFmt.U_AUIPC: cls._decode_u,
            InstFmt.J_JAL: cls._decode_j,
            InstFmt.R_ATOMIC: cls._decode_r_atomic,
            # TODO: Implement the floating point extension
        }
        dst = table.get(inst_fmt, None)
        if dst is not None:
            return dst(inst_addr, inst_data)
        else:
            assert False, f"Unknown instruction format: {inst_fmt}"
            return cls(
                inst_addr=inst_addr,
                inst_data=inst_data,
                inst_fmt=InstFmt.DEBUG_UNDEFINED,
                inst_type=InstType.DEBUG_UNDEFINED,
            )


class Core:
    def __init__(self, config: CoreConfig, slave: BusSlave):
        self.slave = slave
        # 設定参照用にstore
        self.config = config
        # RegisterFile & PC
        self.regs = RegFile()
        self.pc: MemSpace.AbstAddrType = 0

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
        # IF
        inst_addr, inst_data = self._fetch_inst()
        # ID
        inst_data = self._decode_inst(inst_data)
        # EX
        # MEM
        # WB

    def _fetch_inst(self) -> (MemSpace.AbstAddrType, MemSpace.AbstDataType):
        """
        命令データを取得
        """
        inst_addr = self.pc
        inst_data = self.slave.read(inst_addr)
        return inst_addr, inst_data

    def _decode_inst(self, inst_data: MemSpace.AbstDataType) -> MemSpace.AbstDataType:
        """
        命令をデコード
        """
        inst_data = InstData.decode(inst_addr=self.pc, inst_data=inst_data)
        return inst_data
