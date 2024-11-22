from amaranth import Module, Signal
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.cli import main

from counter import Counter


class Top(wiring.Component):
    def __init__(self):
        self.counter = Counter(16)
        super().__init__()

    def elaborate(self, platform):
        m = Module()
        m.submodules.counter = self.counter

        return m


if __name__ == "__main__":
    top = Top()
    main(top)
