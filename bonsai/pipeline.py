from typing import List
from amaranth import Assert, Cat, Format, Module, Print, Signal, unsigned
from amaranth.lib import data, wiring

from inst import InstFormat, Opcode, Operand
import config


################################################################
# Control Signals


class StageCtrlDebug(data.Struct):
    """
    Debug information during stage control
    """

    # fetch cycle number
    cyc: config.REG_SHAPE
    # fetch sequence number
    seqno: config.REG_SHAPE


class StageCtrl(data.Struct):
    """
    Common control signals between stages
    """

    # Enable the stage (for stall)
    en: unsigned(1)
    # Debug information
    debug: StageCtrlDebug


class SideCtrl(data.Struct):
    """
    Common control signals from outside the stage
    """

    # clear output (for pipeline flush)
    clr: unsigned(1)
    # global cycle counter
    cyc: config.REG_SHAPE


class BranchCtrl(data.Struct):
    """
    Control signals to pass the PC from the ID or EX stage to the IF stage
    """

    # Branch enable
    en: unsigned(1)
    # Branch target address
    addr: config.ADDR_SHAPE

    def clear(self, m: Module, domain: str):
        """
        Clear the branch control
        """
        m.d[domain] += [self.en.eq(0), self.addr.eq(0)]


class WriteBackCtrl(data.Struct):
    """
    Write Back to Instruction Decode Control
    """

    # write back enable
    en: unsigned(1)
    # write back register index
    rd_index: config.REGFILE_INDEX_SHAPE


################################################################
# Pipeline Register


class IfReg(data.Struct):
    """
    Instruction Fetch First Half Register
    """

    # Control signals
    ctrl: StageCtrl

    # Instruction address
    pc: config.ADDR_SHAPE


class IfIsReg(data.Struct):
    """
    Instruction Fetch Second Half Register
    """

    # Control signals
    ctrl: StageCtrl

    # Instruction Address
    addr: config.INST_SHAPE

    def push(
        self,
        m: Module,
        domain: str,
        addr: config.ADDR_SHAPE,
        debug: StageCtrlDebug,
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
    ctrl: StageCtrl

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
        debug: StageCtrlDebug,
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
    ctrl: StageCtrl

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

        # operand初期値設定 (後から追加した場合、後の内容が優先される)
        self.operand.clear(m=m, domain=push_domain)
        self.br.clear(m=m, domain=push_domain)

        # TODO: formatごとに値を設定

    def push(
        self,
        m: Module,
        domain: str,
        addr: config.ADDR_SHAPE,
        inst: config.INST_SHAPE,
        debug: StageCtrlDebug,
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
    ctrl: StageCtrl

    # TODO:


class DfDsReg(data.Struct):
    """
    Data Fetch Second Half Register
    """

    # Control signals
    ctrl: StageCtrl


class DsWbReg(data.Struct):
    """
    Write Back Register
    """

    # Control signals
    ctrl: StageCtrl

    # Write back control (for ID)
    wb_ctrl: WriteBackCtrl
