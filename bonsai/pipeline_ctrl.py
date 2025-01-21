from amaranth import unsigned
from amaranth.lib import data, wiring
from amaranth.lib.wiring import In

from regfile import RegData, RegIndex
import config


class InstLocate(data.Struct):
    """
    Program Counter
    """

    # Program Counter
    pc: config.ADDR_SHAPE

    # Unique ID (for logging)
    uniq_id: config.ADDR_SHAPE

    # Number of instruction bytes
    num_inst_bytes: config.INST_BYTES_SHAPE


class RawInst(data.Struct):
    """
    Instruction
    """

    # Instruction
    inst: config.INST_SHAPE

    # PC (for logging)
    locate: InstLocate

    # Unique ID (for logging)
    uniq_id: config.ADDR_SHAPE


class BranchReq(data.Struct):
    """
    次サイクルで分岐/ジャンプを行う制御信号
    """

    # Branch enable
    en: unsigned(1)
    # Branch target address
    next_pc: config.ADDR_SHAPE


class RegWrReq(data.Struct):
    """
    次サイクルで指定されたレジスタに書き込む制御信号
    """

    # enable
    en: unsigned(1)
    # register index
    index: RegIndex
    # data
    data: RegData


class RegFwdReq(data.Struct):
    """
    次サイクルで指定されたレジスタをフォワーディング可能なデータとして設定する制御信号
    """

    # enable
    en: unsigned(1)
    # register index
    index: RegIndex
    # data
    data: RegData


class PrevStageReq(data.Struct):
    """
    ステージ - ステージ間の制御信号
    """

    # Stall Request from previous stage
    stall: unsigned(1)
    # Flush Request from previous stage
    flush: unsigned(1)


class InstSelectReqSignature(wiring.Signature):
    """
    ID(Instruction Decode) -> IS(Instruction Select)間の制御信号
    """

    def __init__(self):
        super().__init__(
            {
                # stall/flush request from pipeline ctrl
                "common_req": In(PrevStageReq),
                # Branch request
                "branch_req": In(BranchReq),
                # num instruction bytes
                # 1=1byte, 2=2byte, 4=4byte, 8=8byte
                "num_inst_bytes": In(config.INST_BYTES_SHAPE),
            }
        )


class InstFetchReqSignature(wiring.Signature):
    """
    IS(Instruction Select) -> IF(Instruction Fetch)間の制御信号
    """

    def __init__(self):
        super().__init__(
            {
                # stall/flush request from IS
                "common_req": In(PrevStageReq),
                # Target PC
                "locate": In(InstLocate),
            }
        )


class InstDecodeReqSignature(wiring.Signature):
    """
    IF(Instruction Fetch) -> ID(Instruction Decode)間の制御信号
    """

    def __init__(self):
        super().__init__(
            {
                # stall/flush request from IF
                "common_req": In(PrevStageReq),
                # Instruction
                "inst": In(RawInst),
            }
        )
