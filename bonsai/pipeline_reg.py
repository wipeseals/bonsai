from amaranth import Assert, Cat, Format, Module, Print, Signal, unsigned
from amaranth.lib import data, wiring, memory
from amaranth.lib.wiring import In, Out

from bonsai.pipeline_ctrl import BranchCtrl, FlushCtrl, IfData, StallCtrl
from inst import InstFormat, Opcode, Operand
import config


class IfReg(wiring.Component):
    """
    IF stage で使用するレジスタ
    Fetch対象のProgram Counterを保持
    """

    # Control in
    stall_in: In(StallCtrl)
    flush_in: In(FlushCtrl)
    branch_in: In(BranchCtrl)

    # result
    data: Out(IfData)

    def __init__(self, init_pc: config.ADDR_SHAPE = 0x0, icache_init_data: list = []):
        self._init_pc = init_pc
        self._init_data = icache_init_data
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        # L1 Cache Body
        m.submodules.mem = mem = memory.Memory(
            shape=config.INST_SHAPE, depth=config.L1_CACHE_DEPTH, init=self._init_data
        )
        wr_port = mem.write_port(domain="comb")
        rd_port = mem.read_port(domain="comb")

        # Flush優先
        with m.If(self.flush_in.en):
            self.data.clear(m=m, domain="comb", addr=self._init_pc, inst=0)
        with m.Else():
            # Stall中は停滞
            with m.If(self.stall_in.en):
                # stall中はPCを更新しない
                pass
            with m.Else():
                # Branch/Jumpがあれば、そのアドレスを設定
                with m.If(self.branch_in.en):
                    m.d.comb += self.pc.eq(self.branch_in.next_pc)
                with m.Else():
                    # 通常はPCを更新
                    m.d.comb += self.pc.eq(self.pc + config.INST_BYTES)

                # TODO: 対象の命令がmemにない場合の対応
                # 後段にデータを流せず、Fetch完了を待つ必要がある

                # read addrにPCの下位2bitを落としたものを設定し、出力をそのまま流す
                m.d.comb += [
                    rd_port.addr.eq(self.pc >> config.INST_ADDR_SHIFT),
                ]
                self.data.push(m - m, domain="comb", addr=self.pc, inst=rd_port.data)

        return m


class IfIsReg(data.Struct):
    """
    Instruction Fetch Second Half Register
    """

    # Control signals
    ctrl: StallCtrl

    # Instruction Address
    addr: config.INST_SHAPE

    def push(
        self,
        m: Module,
        domain: str,
        addr: config.ADDR_SHAPE,
        debug: FetchInfo,
    ):
        """
        Push the instruction fetch address
        """
        m.d[domain] += [
            # 次段にデータを渡す
            self.ctrl.en.eq(1),
            self.addr.eq(addr),
            self.ctrl.debug.eq(debug),
            Print(
                Format(
                    "[IF] push  cyc:{:016x} seqno:{:016x} addr:{:016x}",
                    debug.cyc,
                    debug.seqno,
                    addr,
                )
            ),
        ]

    def stall(self, m: Module, domain: str):
        """
        Stall the instruction fetch
        """
        m.d[domain] += [
            # 次段を止める
            self.ctrl.en.eq(0),
            # データを示すレジスタはすべて Don't care
            Print("[IF] stall"),
        ]

    def flush(self, m: Module, domain: str):
        """
        Flush the instruction fetch
        """
        m.d[domain] += [
            # 現状設計は0 dataのfetchはさせない
            self.ctrl.en.eq(0),
            # 明示的にクリア
            self.addr.eq(0),
            Print("[IF] flush"),
        ]


class IsIdReg(data.Struct):
    """
    Register Fetch Register
    """

    # Control signals
    ctrl: StallCtrl

    # Instruction Address
    addr: config.ADDR_SHAPE

    # Instruction Data
    inst: config.INST_SHAPE

    def push(
        self,
        m: Module,
        domain: str,
        addr: config.ADDR_SHAPE,
        inst: config.INST_SHAPE,
        debug: FetchInfo,
    ):
        """
        Push the instruction fetch address
        """
        m.d[domain] += [
            # 次段にデータを渡す
            self.ctrl.en.eq(1),
            self.addr.eq(addr),
            self.inst.eq(inst),
            self.ctrl.debug.eq(debug),
            Print(
                Format(
                    "[IS] push  cyc:{:016x} seqno:{:016x} addr:{:016x} inst:{:016x}",
                    debug.cyc,
                    debug.seqno,
                    addr,
                    inst,
                )
            ),
        ]

    def stall(self, m: Module, domain: str):
        """
        Stall the instruction fetch
        """
        m.d[domain] += [
            # 次段を止める
            self.ctrl.en.eq(0),
            # データを示すレジスタはすべて Don't care
            Print("[IS] stall"),
        ]

    def flush(self, m: Module, domain: str):
        """
        Flush the instruction fetch
        """
        m.d[domain] += [
            # 現状設計は0 dataのfetchはさせない
            self.ctrl.en.eq(0),
            # 明示的にクリア
            self.addr.eq(0),
            self.inst.eq(0),
            Print("[IS] flush"),
        ]


class IdExReg(data.Struct):
    """
    Register Fetch Register
    """

    ###################################
    # control signals
    ctrl: StallCtrl

    ###################################
    # previous stage data

    # Instruction Address
    addr: config.ADDR_SHAPE
    # Instruction Data
    inst: config.INST_SHAPE

    ###################################
    # instruction decode result

    # opcode
    opcode: Opcode
    # Undefined opcode error
    undef: unsigned(1)
    # Instruction Format
    fmt: InstFormat
    # operand (funct3, funct5, funct7, rs1, rs2, rd, imm)
    operand: Operand

    ###################################
    # branch/jump target
    br: BranchCtrl

    def _decode_inst(
        self,
        m: Module,
        inst: config.INST_SHAPE,
        push_domain: str,
    ):
        """
        Instruction decode logic.

        When updating values to be set in IdExReg, use the specified push_domain.
        For local calculations, use comb to calculate directly without going through flip-flops.
        It is assumed that it can operate even if comb is specified for push_domain.
        """

        # opcode取得 + Inst Format判定
        # 後のoperand取得で使うが、遅延させたくないのでcombの変数も残す
        opcode = Signal(Opcode)
        fmt = Signal(InstFormat)

        m.d[push_domain] += [
            # combのopcodeを割り付け
            self.opcode.eq(opcode),
            # combのfmtを割り付け
            self.fmt.eq(fmt),
            # undefは0にしておくが、後続の処理で1になる場合がある
            self.undef.eq(0),
        ]

        # Opcode取得 + (Opcode分岐 -> Inst Format判定)
        m.d.comb += opcode.eq(inst[6:0])
        with m.Switch(opcode):
            with m.Case(Opcode.LUI):
                m.d.comb += fmt.eq(InstFormat.U)
            with m.Case(Opcode.AUIPC):
                m.d.comb += fmt.eq(InstFormat.U)
            with m.Case(Opcode.JAL):
                m.d.comb += fmt.eq(InstFormat.J)
            with m.Case(Opcode.JALR):
                m.d.comb += fmt.eq(InstFormat.I)
            with m.Case(Opcode.BRANCH):
                m.d.comb += fmt.eq(InstFormat.B)
            with m.Case(Opcode.LOAD):
                m.d.comb += fmt.eq(InstFormat.I)
            with m.Case(Opcode.STORE):
                m.d.comb += fmt.eq(InstFormat.S)
            with m.Case(Opcode.OP_IMM):
                m.d.comb += fmt.eq(InstFormat.I)
            with m.Case(Opcode.OP):
                m.d.comb += fmt.eq(InstFormat.R)
            with m.Case(Opcode.MISC_MEM):
                m.d.comb += fmt.eq(InstFormat.I)
            with m.Case(Opcode.SYSTEM):
                m.d.comb += fmt.eq(InstFormat.I)
            with m.Default():
                m.d.comb += fmt.eq(InstFormat.R)
                # undefined opcode通知
                m.d[push_domain] += [
                    self.undef.eq(1),
                    Assert(
                        0, Format("[ID] Undefined instruction: {:07b}", self.opcode)
                    ),
                ]

        # inst formatごとにOperand Parse
        with m.Switch(fmt):
            # | 31  25 | 24  20 | 19  15 | 14  12 | 11  7 | 6    0 |
            # | funct7 | rs2    | rs1    | funct3 | rd    | opcode |
            with m.Case(InstFormat.R):
                self.operand.update(
                    m=m,
                    domain=push_domain,
                    funct3=inst[14:12],
                    funct7=inst[31:25],
                    rs1=inst[19:15],
                    rs2=inst[24:20],
                    rd=inst[11:7],
                )
            # | 31     20 | 19  15 | 14  12 | 11  7 | 6    0 |
            # | imm[11:0] | rs1    | funct3 | rd    | opcode |
            with m.Case(InstFormat.I):
                self.operand.update(
                    m=m,
                    domain=push_domain,
                    funct3=inst[14:12],
                    imm=inst[31:20],
                    rs1=inst[19:15],
                    rd=inst[11:7],
                )
            # | 31     25 | 24  20 | 19  15 | 14  12 | 11     7 | 6    0 |
            # | imm[11:5] | rs2    | rs1    | funct3 | imm[4:0] | opcode |
            with m.Case(InstFormat.S):
                self.operand.update(
                    m=m,
                    domain=push_domain,
                    funct3=inst[14:12],
                    imm=Cat(inst[31:25], inst[11:7]),
                    rs1=inst[19:15],
                    rs2=inst[24:20],
                )
            # | 31        25 | 24  20 | 19  15 | 14  12 | 11        7 | 6    0 |
            # | imm[12|10:5] | rs2    | rs1    | funct3 | imm[4:1|11] | opcode |
            with m.Case(InstFormat.B):
                self.operand.update(
                    m=m,
                    domain=push_domain,
                    funct3=inst[14:12],
                    imm=Cat(inst[31], inst[7], inst[30:25], inst[11:8], 0),
                    rs1=inst[19:15],
                    rs2=inst[24:20],
                )
            # | 31     12  | 11  7 | 6    0 |
            # | imm[31:12] | rd    | opcode |
            with m.Case(InstFormat.U):
                self.operand.update(
                    m=m,
                    domain=push_domain,
                    imm=inst[31:12],
                    rd=inst[11:7],
                )
            # | 31                 12 | 11  7 | 6    0 |
            # | imm[20|10:1|11|19:12] | rd    | opcode |
            with m.Case(InstFormat.J):
                self.operand.update(
                    m=m,
                    domain=push_domain,
                    imm=Cat(inst[31], inst[19:12], inst[20], inst[30:21], 0),
                    rd=inst[11:7],
                )

        # EX stage実行時点でjump要否がIR/EX regにあれば、IFのflushで捨てるサイクルを削減できる
        self.br.clear(m=m, domain=push_domain)
        # TODO: branch/jump target addressの計算, branch/jump要否の決定

    def push(
        self,
        m: Module,
        domain: str,
        addr: config.ADDR_SHAPE,
        inst: config.INST_SHAPE,
        debug: FetchInfo,
    ):
        """
        Push the instruction decode result
        """
        # 次段にデータを渡す
        m.d[domain] += [
            self.ctrl.en.eq(1),
            self.addr.eq(addr),
            self.inst.eq(inst),
        ]

        # 命令Decode結果追加
        self._decode_inst(m=m, inst=inst, push_domain=domain)

        # デバッグ情報
        m.d[domain] += [
            self.ctrl.debug.eq(debug),
            Print(
                Format(
                    "[IS] push  cyc:{:016x} seqno:{:016x} addr:{:016x} inst:{:016x}",
                    debug.cyc,
                    debug.seqno,
                    addr,
                    inst,
                )
            ),
        ]

    def stall(self, m: Module, domain: str):
        """
        Stall the instruction decode
        """
        m.d[domain] += [
            # 次段を止める
            self.ctrl.en.eq(0),
            # branch ctrlは念の為明示的に無効化
            self.br.en.eq(0),
            # データを示すレジスタはすべて Don't care
            Print("[ID] stall"),
        ]

    def flush(self, m: Module, domain: str):
        """
        Flush the instruction decode
        """
        m.d[domain] += [
            # 現状設計は0 dataのfetchはさせない
            self.ctrl.en.eq(0),
            # 明示的にクリア
            self.addr.eq(0),
            self.inst.eq(0),
            self.opcode.eq(0),
            self.fmt.eq(0),
            self.undef.eq(0),
        ]

        # operand, branch ctrlもクリア
        self.operand.clear(m, domain)
        self.br.clear(m, domain)

        # debug print
        m.d[domain] += [
            Print("[ID] flush"),
        ]


class ExDfreg(data.Struct):
    """
    Data Fetch First Half Register
    """

    # Control signals
    ctrl: StallCtrl

    # TODO:


class DfDsReg(data.Struct):
    """
    Data Fetch Second Half Register
    """

    # Control signals
    ctrl: StallCtrl


class DsWbReg(data.Struct):
    """
    Write Back Register
    """

    # Control signals
    ctrl: StallCtrl

    # Write back control (for ID)
    wb_ctrl: WriteBackCtrl
