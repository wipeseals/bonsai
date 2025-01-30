from amaranth import Module, Signal
from amaranth.lib import data
import config


class RegIndex(data.Struct):
    """
    Register Index
    """

    # Register Index
    index: config.REGFILE_INDEX_SHAPE


class RegData(data.Struct):
    """
    Register Data
    """

    # Register Data
    data: config.REG_SHAPE


class RegFile(data.Struct):
    # TODO: Implement RegFile

    def get_gpr(self, index: config.REGFILE_INDEX_SHAPE) -> Signal:
        raise NotImplementedError("TODO: Implement RegFile.gpr")

    def get_fpr(self, index: config.REGFILE_INDEX_SHAPE) -> Signal:
        raise NotImplementedError("TODO: Implement RegFile.fpr")

    def set_gpr(
        self,
        m: Module,
        domain: str,
        index: config.REGFILE_INDEX_SHAPE,
        value: config.REG_SHAPE,
    ) -> None:
        raise NotImplementedError("TODO: Implement RegFile.set_gpr")

    def set_fpr(
        self,
        m: Module,
        domain: str,
        index: config.REGFILE_INDEX_SHAPE,
        value: config.REG_SHAPE,
    ) -> None:
        raise NotImplementedError("TODO: Implement RegFile.set_fpr")
