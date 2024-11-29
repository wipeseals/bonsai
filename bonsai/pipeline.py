from typing import List
from amaranth import Format, Module, Print, unsigned
from amaranth.lib import data, wiring

from inst import InstFormat, Opcode
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
    Stage間で共通の制御信号
    """

    # Enable the stage (for stall)
    en: unsigned(1)
    # Debug information
    debug: StageCtrlDebug


class SideCtrl(data.Struct):
    """
    Stage間の外からの共通制御信号
    """

    # clear output (for pipeline flush)
    clr: unsigned(1)
    # global cycle counter
    cyc: config.REG_SHAPE


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
        module: Module,
        domain: str,
        addr: config.ADDR_SHAPE,
        debug: StageCtrlDebug,
    ):
        """
        Push the instruction fetch address
        """
        module.d[domain] += [
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

    def stall(self, module: Module, domain: str):
        """
        Stall the instruction fetch
        """
        module.d[domain] += [
            # 次段を止める
            self.ctrl.en.eq(0),
            # データを示すレジスタはすべて Don't care
            Print("[IF] stall"),
        ]

    def flush(self, module: Module, domain: str):
        """
        Flush the instruction fetch
        """
        module.d[domain] += [
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
        module: Module,
        domain: str,
        addr: config.ADDR_SHAPE,
        inst: config.INST_SHAPE,
        debug: StageCtrlDebug,
    ):
        """
        Push the instruction fetch address
        """
        module.d[domain] += [
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

    def stall(self, module: Module, domain: str):
        """
        Stall the instruction fetch
        """
        module.d[domain] += [
            # 次段を止める
            self.ctrl.en.eq(0),
            # データを示すレジスタはすべて Don't care
            Print("[IS] stall"),
        ]

    def flush(self, module: Module, domain: str):
        """
        Flush the instruction fetch
        """
        module.d[domain] += [
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

    # Control signals
    ctrl: StageCtrl
    # Instruction Address
    addr: config.ADDR_SHAPE
    # Instruction Data
    inst: config.INST_SHAPE

    # opcode
    opcode: Opcode
    # Instruction Format
    fmt: InstFormat
    # funct3
    funct3: unsigned(3)
    # funct5 (for atomic)
    funct5: unsigned(5)
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

    # Destination Register Enable
    rd_en: unsigned(1)
    # Destination Register index
    rd_index: config.REGFILE_INDEX_SHAPE

    # Immediate Value
    imm: config.REG_SHAPE
    # Immediate Value (sign extended)
    imm_sext: config.REG_SHAPE

    def push(
        self,
        module: Module,
        domain: str,
        addr: config.ADDR_SHAPE,
        inst: config.INST_SHAPE,
        debug: StageCtrlDebug,
    ):
        """
        Push the instruction decode result
        """
        # 次段にデータを渡す
        module.d[domain] += [
            self.ctrl.en.eq(1),
            self.addr.eq(addr),
            self.inst.eq(inst),
        ]
        # inst分解

        # デバッグ情報
        module.d[domain] += [
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

    def stall(self, module: Module, domain: str):
        """
        Stall the instruction decode
        """
        module.d[domain] += [
            # 次段を止める
            self.ctrl.en.eq(0),
            # データを示すレジスタはすべて Don't care
            Print("[ID] stall"),
        ]

    def flush(self, module: Module, domain: str):
        """
        Flush the instruction decode
        """
        module.d[domain] += [
            # 現状設計は0 dataのfetchはさせない
            self.ctrl.en.eq(0),
            # 明示的にクリア
            self.addr.eq(0),
            self.inst.eq(0),
            self.opcode.eq(0),
            self.fmt.eq(0),
            self.funct3.eq(0),
            self.funct5.eq(0),
            self.funct7.eq(0),
            self.rs1_en.eq(0),
            self.rs1_index.eq(0),
            self.rs1.eq(0),
            self.rs2_en.eq(0),
            self.rs2_index.eq(0),
            self.rs2.eq(0),
            self.rd_en.eq(0),
            self.rd_index.eq(0),
            self.imm.eq(0),
            self.imm_sext.eq(0),
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
