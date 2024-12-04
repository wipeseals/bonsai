from typing import Optional, override
from abc import ABC, ABCMeta, abstractmethod
from amaranth import Assert, Cat, Format, Module, Print, Signal, unsigned
from amaranth.lib import data
from amaranth.lib.wiring import In, Out

from regfile import RegData
from inst import InstFormat, Opcode, Operand
import config


class StallCtrl(data.Struct):
    """
    次サイクルを止める制御信号
    """

    en: unsigned(1)

    def update(self, m: Module, domain: str, en: unsigned(1)):
        m.d[domain] += [self.en.eq(en)]

    def enable(self, m: Module, domain: str):
        self.update(m, domain, 1)

    def disable(self, m: Module, domain: str):
        self.update(m, domain, 0)


class FlushCtrl(data.Struct):
    """
    次サイクルでデータを捨てる制御信号
    """

    en: unsigned(1)

    def update(self, m: Module, domain: str, en: unsigned(1)):
        m.d[domain] += [self.en.eq(en)]

    def enable(self, m: Module, domain: str):
        self.update(m, domain, 1)

    def disable(self, m: Module, domain: str):
        self.update(m, domain, 0)


class BranchCtrl(data.Struct):
    """
    次サイクルで分岐/ジャンプを行う制御信号
    """

    # Branch enable
    en: unsigned(1)
    # Branch target address
    next_pc: config.ADDR_SHAPE

    def update(self, m: Module, domain: str, addr: Optional[config.ADDR_SHAPE]):
        if addr is None:
            m.d[domain] += [self.en.eq(0), self.next_pc.eq(0)]
        else:
            m.d[domain] += [self.en.eq(1), self.next_pc.eq(addr)]

    def clear(self, m: Module, domain: str):
        self.update(m, domain, None)


class RegWrCtrl(data.Struct):
    """
    次サイクルで指定されたレジスタに書き込む制御信号
    """

    # write back register data
    reg_data: RegData

    def update(
        self,
        m: Module,
        domain: str,
        rd_index: Optional[config.REGFILE_INDEX_SHAPE],
        data: Optional[config.REG_SHAPE],
    ):
        self.reg_data.update(m=m, domain=domain, index=rd_index, data=data)

    def clear(self, m: Module, domain: str):
        self.reg_data.clear(m, domain)


class RegFwdCtrl(data.Struct):
    """
    次サイクルで指定されたレジスタをフォワーディング可能なデータとして設定する制御信号
    """

    reg_data: RegData

    def update(
        self,
        m: Module,
        domain: str,
        rd_index: Optional[config.REGFILE_INDEX_SHAPE],
        data: Optional[config.REG_SHAPE],
    ):
        self.reg_data.update(m=m, domain=domain, index=rd_index, data=data)

    def clear(self, m: Module, domain: str):
        self.reg_data.clear(m, domain)


class StageCtrl(data.Struct):
    """
    ステージ - ステージ間の制御信号
    """

    en: unsigned(1)
    uniq_id: config.REG_SHAPE

    def update(
        self, m: Module, domain: str, en: unsigned(1), uniq_id: config.REG_SHAPE
    ):
        m.d[domain] += [
            self.en.eq(en),
            self.uniq_id.eq(uniq_id),
        ]

    def enable(self, m: Module, domain: str, uniq_id: config.REG_SHAPE):
        self.update(m, domain, en=1, uniq_id=uniq_id)

    def disable(self, m: Module, domain: str):
        self.update(m, domain, en=0, uniq_id=0)


class InstFetchData(data.Struct):
    """
    IF stageでFetchしたデータとそのアドレスを保持する
    """

    # ctrl
    ctrl: StageCtrl
    # Program Counter
    pc: config.ADDR_SHAPE
    # Instruction data
    inst: config.INST_SHAPE

    def clear(self, m: Module, domain: str, init_pc: config.ADDR_SHAPE):
        self.ctrl.disable(m, domain)

    def update(
        self,
        m: Module,
        domain: str,
        pc: config.ADDR_SHAPE,
        inst: config.INST_SHAPE,
        uniq_id: config.REG_SHAPE,
    ):
        self.ctrl.enable(m, domain, uniq_id=uniq_id)
        m.d[domain] += [self.pc.eq(pc), self.inst.eq(inst)]
