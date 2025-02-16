import enum
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

from emu.mem import AccessResult, BusSlave, MemSpace


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
        assert 0 <= addr < 32, f"Invalid register address: {addr=}"
        # zero register
        if addr == 0:
            return 0
        return self.regs[addr]

    def write(self, addr: MemSpace.AbstAddrType, data: MemSpace.AbstDataType) -> None:
        """
        Write a register
        """
        assert 0 <= addr < 32, f"Invalid register address: {addr=}"
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
            assert False, f"Unknown opcode: {inst_data=}, {e=}"
            return InstFmt.DEBUG_UNDEFINED

    @classmethod
    def sign_ext(
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
            # Base Integer + Multiply Extension
            0x0: {0x00: InstType.ADD, 0x20: InstType.SUB, 0x01: InstType.MUL},
            0x4: {0x00: InstType.XOR, 0x01: InstType.DIV},
            0x6: {0x00: InstType.OR, 0x01: InstType.REM},
            0x7: {0x00: InstType.AND, 0x01: InstType.REMU},
            0x1: {0x00: InstType.SLL, 0x01: InstType.MULH},
            0x5: {0x00: InstType.SRL, 0x20: InstType.SRA, 0x01: InstType.DIVU},
            0x2: {0x00: InstType.SLT, 0x01: InstType.MULSU},
            0x3: {0x00: InstType.SLTU, 0x01: InstType.MULU},
        }
        inst_type = InstType.DEBUG_UNDEFINED
        if funct3 in table and funct7 in table[funct3]:
            inst_type = table[funct3][funct7]
        else:
            assert False, f"Unknown funct3/funct7: {funct3=}/{funct7=}"

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
        imm_se = cls.sign_ext(imm, 12)  # Sign extend the immediate value to 12 bits
        imm_lower = imm & 0x1F  # Extract bits 4-0 for imm[4:0]
        imm_upper = (imm & 0x7FF) >> 5  # Extract bits 11-5 for imm[11:5]
        # funct3 -> (imm[11:0] -> inst_type)
        table: Dict[int, Callable[InstType]] = {
            0x0: lambda: InstType.ADDI,
            0x4: lambda: InstType.XORI,
            0x6: lambda: InstType.ORI,
            0x7: lambda: InstType.ANDI,
            # SLLI は imm[11] で判定
            0x1: lambda: InstType.SLLI if imm_upper == 0 else InstType.DEBUG_UNDEFINED,
            # SRLI/SRAI は imm[11] で判定
            0x5: lambda: InstType.SRLI if imm_upper == 0 else InstType.SRAI,
            0x2: lambda: InstType.SLTI,
            0x3: lambda: InstType.SLTIU,
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
        imm_se = cls.sign_ext(imm, 12)  # Sign extend the immediate value to 12 bits
        # funct3 -> inst_type
        table: Dict[int, InstType] = {
            0x0: InstType.SB,
            0x1: InstType.SH,
            0x2: InstType.SW,
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
        imm_se = cls.sign_ext(imm, 13)  # Sign extend the immediate value to 13 bits
        # funct3 -> inst_type
        table: Dict[int, InstType] = {
            0x0: InstType.BEQ,
            0x1: InstType.BNE,
            0x4: InstType.BLT,
            0x5: InstType.BGE,
            0x6: InstType.BLTU,
            0x7: InstType.BGEU,
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
        imm_se = cls.sign_ext(imm, 20)  # Sign extend the immediate value to 20 bits
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
        imm_se = cls.sign_ext(imm, 21)  # Sign extend the immediate value to 21 bits
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
    def _decode_i_env(
        cls, inst_addr: MemSpace.AbstAddrType, inst_data: MemSpace.AbstDataType
    ) -> "InstData":
        """
        I-Type (Immediate Type) for Environment Call/Break Decoder
        | I-Type (Immediate Type): | imm[11:0]@31-20                | rs1@19-15 | funct3@14-12 | rd@11-7          | opcode@6-0 |
        """
        _opcode = inst_data & 0x7F  # Extract bits 6-0 for opcode
        rs1 = (inst_data >> 15) & 0x1F  # Extract bits 19-15 for rs1
        rd = (inst_data >> 7) & 0x1F  # Extract bits 11-7 for rd
        funct3 = (inst_data >> 12) & 0x7  # Extract bits 14-12 for funct3
        imm = (inst_data >> 20) & 0xFFF  # Extract bits 31-20 for imm[11:0]
        imm_se = cls.sign_ext(imm, 12)  # Sign extend the immediate value to 12 bits
        # imm -> inst_type
        table: Dict[int, InstType] = {
            0x000: InstType.ECALL,
            0x001: InstType.EBREAK,
        }
        inst_type = table[imm]

        return cls(
            inst_addr=inst_addr,
            inst_data=inst_data,
            inst_fmt=InstFmt.I_ENV,
            inst_type=inst_type,
            rs1=rs1,
            rd=rd,
            funct3=funct3,
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
        id stage: 命令デコードした結果を返す
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
            InstFmt.J_JAL: cls._decode_j,
            InstFmt.J_JALR: cls._decode_i,
            InstFmt.U_LUI: cls._decode_u,
            InstFmt.U_AUIPC: cls._decode_u,
            InstFmt.I_ENV: cls._decode_i_env,
            InstFmt.R_ATOMIC: cls._decode_r_atomic,
            # TODO: Implement the floating point extension
        }
        dst = table.get(inst_fmt, None)
        if dst is not None:
            return dst(inst_addr, inst_data)
        else:
            assert False, f"Unknown instruction format: {inst_fmt=}"
            return cls(
                inst_addr=inst_addr,
                inst_data=inst_data,
                inst_fmt=InstFmt.DEBUG_UNDEFINED,
                inst_type=InstType.DEBUG_UNDEFINED,
            )


@dataclass
class ExecResult:
    """
    EX stageの結果
    """

    # rdへの書き戻しがあれば値をいれる
    write_rd_from_alu: MemSpace.AbstDataType | None = None
    # メモリからデータ取得が必要であればアドレスをいれる
    # addr -> reg_addr
    write_rd_from_mem: Tuple[MemSpace.AbstAddrType, int] | None = None
    # メモリへの書き込みが必要であればアドレスとデータをいれる
    # addr -> data
    write_mem_from_alu: Tuple[MemSpace.AbstAddrType, MemSpace.AbstDataType] | None = (
        None
    )
    # PCの更新が必要であればアドレスをいれる
    write_pc: MemSpace.AbstAddrType | None = None
    # TODO: ecall/ebreakなどの例外が発生した場合の処理を追加

    @classmethod
    def _execute_r(
        cls,
        inst_data: InstData,
        regs: RegFile,
        reg_bit_width: int,
    ) -> MemSpace.AbstDataType:
        """
        Execute R-Type instruction
        """
        # resouce
        rs1_data = regs.read(inst_data.rs1)
        rs2_data = regs.read(inst_data.rs2)
        rs1_data_se = inst_data.sign_ext(rs1_data, reg_bit_width)
        rs2_data_se = inst_data.sign_ext(rs2_data, reg_bit_width)
        rd_data = 0
        # 命令ごと分岐: inst_type -> func[[] -> rd_data]
        table: Dict[
            InstType,
            Callable[MemSpace.AbstDataType],
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
        if inst_data.inst_type not in table:
            raise NotImplementedError(f"Unknown instruction: {inst_data.inst_type=}")

        rd_data = table[inst_data.inst_type]()
        # shiftrやaddで超えるケースがあるのでmask
        rd_data &= (1 << reg_bit_width) - 1
        return rd_data

    def _execute_i(
        cls,
        inst_data: InstData,
        regs: RegFile,
        reg_bit_width: int,
    ) -> MemSpace.AbstDataType:
        """
        Execute I-Type instruction
        """
        # resouce
        rs1_data = regs.read(inst_data.rs1)
        rs1_data_se = inst_data.sign_ext(rs1_data, reg_bit_width)
        rd_data = 0
        # 命令ごと分岐: inst_type -> func[[] -> rd_data]
        table: Dict[
            InstType,
            Callable[MemSpace.AbstDataType],
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
        if inst_data.inst_type not in table:
            raise NotImplementedError(f"Unknown instruction: {inst_data.inst_type=}")

        rd_data = table[inst_data.inst_type]()
        # shiftrやaddで超えるケースがあるのでmask
        rd_data &= (1 << reg_bit_width) - 1
        return rd_data

    @classmethod
    def execute(
        cls, inst_data: InstData, regs: RegFile, reg_bit_width: int
    ) -> "ExecResult":
        """
        execute stage: Decodeした結果とPC(inst_dataに内包)/Reg値から命令を実行
        Reg/Memの書き戻しは現時点ではせず、MEM/WBへの指示として返す
        """
        # 命令タイプ: inst_fmt -> func
        table: Dict[
            InstFmt,
            Callable[[InstData, RegFile, int], "ExecResult"],
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
            # TODO: Implement the floating point extension
        }
        dst = table.get(inst_data.inst_fmt, None)

        if dst is None:
            # Decodeできていればここには来ないはず
            raise NotImplementedError(
                f"Unknown instruction format: {inst_data.inst_fmt=}"
            )

        # reg_bit_width は Compressed Extension がある場合に動的に切り替わるのでMemSpace直参照せず、引数で受ける
        return dst(inst_data, regs, reg_bit_width)


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
        inst_addr, access_ret, inst_data = self._fetch_inst()
        if access_ret != AccessResult.OK:
            # 安定するまでは明らかに不具合だが、最終的にはCoreの例外として処理すべき内容
            assert False, f"Fetch Error: {access_ret}"
            raise RuntimeError(f"TODO: impl Exception Handler: {access_ret=}")
        # ID
        inst_data = self._decode_inst(inst_data)
        if inst_data.inst_type == InstType.DEBUG_UNDEFINED:
            # 安定するまでは不正命令のFetchは止めるべきだが、最終的にはCoreの例外として処理すべき内容
            assert False, "Undefined instruction"
            raise NotImplementedError("TODO: impl Exception Handler")
        # EX: TODO: reg_bit_width は Compressed Extension がある場合に動的に切り替わるので、動的に変更できるようにする
        ex_ret = ExecResult.execute(inst_data, self.regs, self.config.reg_bit_width)
        # MEM
        # WB

    def _fetch_inst(
        self,
    ) -> Tuple[MemSpace.AbstAddrType, AccessResult, MemSpace.AbstDataType]:
        """
        命令データを取得
        """
        inst_addr = self.pc
        accsess_ret, inst_data = self.slave.read(inst_addr)
        return inst_addr, accsess_ret, inst_data

    def _decode_inst(self, inst_data: MemSpace.AbstDataType) -> InstData:
        """
        命令をデコード
        """
        inst_data = InstData.decode(inst_addr=self.pc, inst_data=inst_data)
        return inst_data
