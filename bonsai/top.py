from amaranth import Module
from amaranth.lib import wiring
from bonsai.bus import WishboneMaster


class Top(wiring.Component):
    """
    Top Component
    """

    def __init__(self):
        super().__init__({})

    def elaborate(self, platform):
        m = Module()
        m.submodules.core = core = WishboneMaster()
        return m
