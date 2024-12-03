from amaranth import Module, Signal
from amaranth.lib import data
import config


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
