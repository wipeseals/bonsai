from curses.ascii import ctrl
from gc import enable
from typing import Any
from amaranth import Const, Format, Module, Mux, Print, Shape, Signal, unsigned
from amaranth.lib import wiring, enum, data, memory, stream
from amaranth.lib.wiring import In, Out
from amaranth.cli import main

import config


class StageCtrl(data.Struct):
    # Enable the stage (for stall)
    en: unsigned(1)
    # Clear the stage (for flush)
    clr: unsigned(1)


class IfReg(data.Struct):
    # Control signals
    ctrl: StageCtrl

    # Program counter
    pc: config.ADDR_SHAPE
