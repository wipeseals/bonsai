from tkinter import NORMAL
from amaranth import unsigned
import amaranth
from amaranth.lib import data, wiring, enum
from amaranth.lib.wiring import In, Out

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


class CacheMemoryType(enum.Enum):
    """
    キャッシュメモリのアクセス属性
    """

    # Normal (Storeタイミング任意、順序並び替え許容)
    BUFFERED = 0
    # Device (Storeタイミング任意、順序並び替え禁止)
    BUFFRED_ORDERED = 1
    # Strongly Ordered (Storeタイミング即時、順序並び替え禁止)
    UNBUFFERED_ORDERED = 2


class CacheOperationType(enum.Enum):
    """
    キャッシュアクセス時のキャッシュ取り扱い種別
    """

    # Write Back (Cache)
    WRITE_BACK = 0
    # Write Through (Cache + Memory)
    WRITE_THROUGH = 1
    # Non Cached (Memory)
    NON_CACHED = 2


class CacheRequestSignature(wiring.Signature):
    """
    キャッシュアクセス要求の信号
    """

    def __init__(self, addr_shape=config.ADDR_SHAPE, data_shape=config.DATA_SHAPE):
        super().__init__(
            {
                # Buffer要否、Order要否
                "mem_type": In(CacheMemoryType),
                # Write Back, Write Through, Non Cached
                "op_type": In(CacheOperationType),
                # アクセスアドレス
                "addr_in": In(addr_shape),
                # 書き込みデータ (Read時は無視)
                "data_in": In(data_shape),
                # 書き込み要求
                "data_out": Out(data_shape),
                # 書き込み受付
                "we": In(1),
                # 書き込み受付不可
                "busy": Out(1),
            }
        )


class StageCtrlReqSignature(wiring.Signature):
    """
    全体から個別Stageへの制御信号
    """

    def __init__(self):
        super().__init__(
            {
                # Stall Request from previous stage
                "stall": In(unsigned(1)),
                # Flush Request from previous stage
                "flush": In(unsigned(1)),
            }
        )


class InstSelectReqSignature(wiring.Signature):
    """
    ID(Instruction Decode) -> IS(Instruction Select)間の制御信号
    """

    def __init__(self):
        super().__init__(
            {
                # data enable
                "en": In(unsigned(1)),
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
                # data enable
                "en": In(unsigned(1)),
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
                # data enable
                "en": In(unsigned(1)),
                # Instruction
                "inst": In(RawInst),
            }
        )
