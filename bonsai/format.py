from enum import auto
from typing import Optional
from amaranth import unsigned
import amaranth
from amaranth.lib import data, wiring, enum
from amaranth.lib.wiring import In, Out
from amaranth.utils import log2_int

from regfile import RegData, RegIndex
import util
import config


class AbortType(enum.Enum):
    """
    Pipeline Abort Type
    """

    # No Exception
    NONE = 0

    # Misaligned Fetch
    MISALIGNED_FETCH = 1

    # Illegal Memory Operation
    ILLEGAL_MEM_OP = 2

    # Misaligned Memory Access
    MISALIGNED_MEM_ACCESS = 3


class InstLocate(data.Struct):
    """
    Program Counter
    """

    # Program Counter
    pc: config.ADDR_SHAPE

    # Unique ID (for logging)
    uniq_id: config.CMD_UNIQ_ID_SHAPE


class RawInst(data.Struct):
    """
    Instruction
    """

    # Instruction
    inst: config.INST_SHAPE

    # PC (for logging)
    locate: InstLocate

    # Unique ID (for logging)
    uniq_id: config.CMD_UNIQ_ID_SHAPE


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


class MemoryOperationType(enum.Enum):
    """
    キャッシュアクセス時のキャッシュ取り扱い種別
    """

    # NO Operation
    NOP = 0

    # Read Cache
    READ_CACHE = 1
    # Read Non Cache (Memory)
    READ_NON_CACHE = 2

    # Write Back (Cache)
    WRITE_CACHE = 3
    # Write Through (Cache + Memory)
    WRITE_THROUGH = 4
    # Non Cached (Memory)
    WRITE_NON_CACHE = 5

    # Clear Abort Status
    MANAGE_CLEAR_ABORT = 6
    # Cache Line Invalidate
    MANAGE_INVALIDATE = 7
    # Cache Line Clean (Invalidate or Write)
    MANAGE_CLEAN = 8
    # Cache Line Flush (Clean + Invalidate)
    MANAGE_FLUSH = 9
    # Cache Line Zero Fill
    MANAGE_ZERO_FILL = 10
    # Cache Line Prefetch
    MANAGE_PREFETCH = 11


class MemoryAccessReqSignature(wiring.Signature):
    """
    キャッシュアクセス要求の信号
    """

    def __init__(self, addr_shape=config.ADDR_SHAPE, data_shape=config.DATA_SHAPE):
        # misaligned data accessは現状非サポート
        assert util.is_power_of_2(data_shape.width), "Data width must be power of 2"

        super().__init__(
            {
                # Write Back, Write Through, Non Cached
                "op_type": Out(MemoryOperationType),
                # アクセスアドレス
                "addr_in": Out(addr_shape),
                # 書き込みデータ (Read時は無視)
                "data_in": Out(data_shape),
                # 書き込み要求
                "data_out": In(data_shape),
                # 受付不可
                "busy": In(1),
                # 例外発生時のステータス
                "abort_type": In(AbortType),
            }
        )


class StageCtrlReqSignature(wiring.Signature):
    """
    全体から個別Stageへの制御信号
    """

    def __init__(self):
        super().__init__(
            {
                # 本cycの処理停止が必要なときに1
                "stall": Out(unsigned(1)),
                # 次段へのデータを破棄かつ本cycの処理停止が必要なときに1
                "flush": Out(unsigned(1)),
                # Abortして処理停止したStageのAbort状態解除が必要なときに1。clear解除まではstallが継続
                "clear": Out(unsigned(1)),
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
                "en": Out(unsigned(1)),
                # Branch request
                "branch_req": Out(BranchReq),
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
                "en": Out(unsigned(1)),
                # Target PC
                "locate": Out(InstLocate),
                # Abort
                "abort_type": Out(AbortType),
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
                "en": Out(unsigned(1)),
                # Instruction
                "inst": Out(RawInst),
                # Abort
                "abort_type": Out(AbortType),
            }
        )
