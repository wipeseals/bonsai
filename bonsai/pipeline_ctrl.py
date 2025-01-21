from amaranth import unsigned
from amaranth.lib import data, wiring
from amaranth.lib.wiring import In

from regfile import RegData, RegIndex
import config


class CmdUniqId(data.Struct):
    """
    Command Unique ID for logging
    """

    # Command Unique ID
    uniq_id: config.REG_SHAPE


class Pc(data.Struct):
    """
    Program Counter
    """

    # Program Counter
    pc: config.ADDR_SHAPE

    # Unique ID (for logging)
    uniq_id: In(CmdUniqId)


class RawInst(data.Struct):
    """
    Instruction
    """

    # Instruction
    inst: config.INST_SHAPE

    # PC (for logging)
    pc: Pc

    # Unique ID (for logging)
    uniq_id: In(CmdUniqId)


class StallReq(wiring.Signature):
    """
    次サイクルを止める制御信号
    """

    en: In(unsigned(1))


class FlushReq(wiring.Signature):
    """
    次サイクルでデータを捨てる制御信号
    """

    en: In(unsigned(1))


class BranchReq(wiring.Signature):
    """
    次サイクルで分岐/ジャンプを行う制御信号
    """

    # Branch enable
    en: In(unsigned(1))
    # Branch target address
    next_pc: In(Pc)


class RegWrReq(wiring.Signature):
    """
    次サイクルで指定されたレジスタに書き込む制御信号
    """

    # enable
    en: In(unsigned(1))
    # register index
    index: In(RegIndex)
    # data
    data: In(RegData)


class RegFwdReq(wiring.Signature):
    """
    次サイクルで指定されたレジスタをフォワーディング可能なデータとして設定する制御信号
    """

    # enable
    en: In(unsigned(1))
    # register index
    index: In(RegIndex)
    # data
    data: In(RegData)


class PrevStageReq(wiring.Signature):
    """
    ステージ - ステージ間の制御信号
    """

    # Stall Request from previous stage
    stall: In(StallReq)
    # Flush Request from previous stage
    flush: In(FlushReq)


class InstSelectReq(wiring.Signature):
    """
    ID(Instruction Decode) -> IS(Instruction Select)間の制御信号
    """

    # stall/flush request from pipeline ctrl
    common_req: In(PrevStageReq)

    # Branch request
    branch_req: In(BranchReq)

    # num instruction bytes
    # 1=1byte, 2=2byte, 4=4byte
    num_inst_bytes: In(unsigned(2))


class InstFetchReq(wiring.Signature):
    """
    IS(Instruction Select) -> IF(Instruction Fetch)間の制御信号
    """

    # stall/flush request from IS
    common_req: In(PrevStageReq)

    # Target PC
    pc: In(Pc)


class InstDecodeReq(wiring.Signature):
    """
    IF(Instruction Fetch) -> ID(Instruction Decode)間の制御信号
    """

    # stall/flush request from IF
    common_req: In(PrevStageReq)

    # Instruction
    inst: In(RawInst)
