from amaranth import unsigned
from amaranth.lib import data, wiring

import config


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
