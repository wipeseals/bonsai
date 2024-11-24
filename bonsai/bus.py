from amaranth import Module, Signal, unsigned
from amaranth.lib import wiring, enum, data
from amaranth.lib.wiring import In, Out
from amaranth.cli import main


class BonsaiSendStat(enum.Enum):
    """
    BonsaiSendStat is an enum for the BonsaiBus request type.
    """

    NOT_VALID = 0
    WR = 1
    RD = 2


class BonsaiRecvStat(enum.Enum):
    """
    BonsaiRecvStat is an enum for the BonsaiBus response type.
    """

    NOT_READY = 0
    READY = 1


class BonsaiStreamSignature(wiring.Signature):
    """
    BonsaiStreamSignature is a signature for the BonsaiStream.
    """

    def __init__(self, width=32):
        self.width = width
        super().__init__(
            {
                "req": Out(BonsaiSendStat),
                "data": Out(unsigned(width)),
                "resp": In(BonsaiRecvStat),
            }
        )

    def __eq__(self, other):
        return self.members == other.members


class BonsaiBusSignature(wiring.Signature):
    """
    BonsaiBusSignature is a signature for the BonsaiBus.
    """

    def __init__(self, width=32):
        self.width = width
        super().__init__(
            {
                "req": Out(BonsaiSendStat),
                "addr": Out(unsigned(width)),
                "wr_data": Out(unsigned(width)),
                "resp": In(BonsaiRecvStat),
                "rd_data": In(unsigned(width)),
            }
        )

    def __eq__(self, other):
        return self.members == other.members


class BonsaiBusMater(wiring.Component):
    """
    BonsaiBusMater is a hardware component that connects the BonsaiBus to the CPU.
    Attributes:
        bus (BonsaiBusSignature): The BonsaiBus signature.
    """

    bus: BonsaiBusSignature

    def __init__(self, width=32):
        self.bus = BonsaiBusSignature(width)
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        return m


class BonsaiBusSlave(wiring.Component):
    """
    BonsaiBusSlave is a hardware component that connects the BonsaiBus to the memory.
    Attributes:
        bus (BonsaiBusSignature): The BonsaiBus signature.
    """

    bus: BonsaiBusSignature

    def __init__(self, width=32):
        self.bus = BonsaiBusSignature(width).flip()
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        return m


if __name__ == "__main__":
    bus_master = BonsaiBusMater(width=32)
    bus_slave = BonsaiBusSlave(width=32)
    main(bus_master, bus_slave)
