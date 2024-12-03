from amaranth import Module, Signal, unsigned
from amaranth.lib import data
import config


class RegData(data.Struct):
    """
    Register Data
    """

    # write back enable
    en: unsigned(1)
    # register index
    index: config.REGFILE_INDEX_SHAPE
    # data
    data: config.REG_SHAPE

    def clear(self, m: Module, domain: str):
        """
        Clear RegData
        """
        m.d[domain] += [
            self.en.eq(0),
            self.index.eq(0),
            self.data.eq(0),
        ]

    def update(
        self,
        m: Module,
        domain: str,
        index: config.REGFILE_INDEX_SHAPE,
        data: config.REG_SHAPE,
    ):
        """
        Set RegData
        """
        m.d[domain] += [
            self.en.eq(1),
            self.index.eq(index),
            self.data.eq(data),
        ]


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
