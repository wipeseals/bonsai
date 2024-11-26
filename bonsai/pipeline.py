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
    counter: config.REG_SHAPE
    # fetch sequence number
    seq_no: config.REG_SHAPE


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

    def push(self, addr: config.ADDR_SHAPE):
        """
        Push the instruction fetch address
        """
        return [
            self.ctrl.en.eq(1),
            self.addr.eq(addr),
            Print(Format("[IF] push  addr: {:016x}", addr)),
        ]

    def stall(self):
        """
        Stall the instruction fetch
        """
        return [
            self.ctrl.en.eq(0),
            self.addr.eq(0),
            Print(Format("[IF] stall addr: {:016x}", 0)),
        ]

    def flush(self):
        """
        Flush the instruction fetch
        """
        return [
            self.ctrl.en.eq(0),
            self.addr.eq(1),
            Print(Format("[IF] flush addr: {:016x}", 0)),
        ]


class IsRfReg(data.Struct):
    """
    Register Fetch Register
    """

    # Control signals
    ctrl: StageCtrl

    # Instruction Data
    inst: config.INST_SHAPE

    # Instruction Address
    addr: config.ADDR_SHAPE


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
