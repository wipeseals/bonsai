from amaranth import Format, Print, unsigned
from amaranth.lib import data, wiring

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
    Stage間の外からの制御信号
    """

    # clear output (for pipeline flush)
    clr: unsigned(1)
    # global cycle counter
    cyc: config.REG_SHAPE


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

    def push(self, addr: config.ADDR_SHAPE, debug: StageCtrlDebug):
        """
        Push the instruction fetch address
        """
        return [
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

    def stall(self):
        """
        Stall the instruction fetch
        """
        return [
            self.ctrl.en.eq(0),  # 次段を止める
            # self.addr.eq(0), # Don't care
            Print("[IF] stall"),
        ]

    def flush(self):
        """
        Flush the instruction fetch
        """
        return [
            self.ctrl.en.eq(0),  # 現状設計は0 dataのfetchはさせない
            self.addr.eq(0),  # 明示的にクリア
            Print("[IF] flush"),
        ]


class IsRfReg(data.Struct):
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
        self, addr: config.ADDR_SHAPE, inst: config.INST_SHAPE, debug: StageCtrlDebug
    ):
        """
        Push the instruction fetch address
        """
        return [
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

    def stall(self):
        """
        Stall the instruction fetch
        """
        return [
            self.ctrl.en.eq(0),  # 次段を止める
            # self.addr.eq(0), # Don't care
            # self.inst.eq(0), # Don't care
            Print("[IS] stall"),
        ]

    def flush(self):
        """
        Flush the instruction fetch
        """
        return [
            self.ctrl.en.eq(0),  # 現状設計は0 dataのfetchはさせない
            self.addr.eq(0),  # 明示的にクリア
            self.inst.eq(0),  # 明示的にクリア
            Print("[IS] flush"),
        ]


class RfExReg(data.Struct):
    # Control signals
    ctrl: StageCtrl

    # TODO:


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
