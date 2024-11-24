from typing import Any
from amaranth import Module, Shape, Signal, unsigned
from amaranth.lib import wiring, enum, data, memory
from amaranth.lib.wiring import In, Out
from amaranth.cli import main


class SimpleInstMem(wiring.Component):
    """
    SimpleInstMem is a simple instruction memory component that reads instructions from a memory block.
    Attributes:
        rd_addr (In): Input signal that specifies the address to read from.
        rd_data (Out): Output signal that contains the instruction read from memory.
    """

    def __init__(self, data_shape: Shape, depth: int, init_data: Any = [0x00000000]):
        self.mem = memory.Memory(shape=data_shape, depth=depth, init=init_data)
        super().__init__(
            {
                "rd_addr": In(depth.bit_length()),
                "rd_data": Out(data_shape),
            }
        )

    def elaborate(self, platform):
        m = Module()
        m.submodules.mem = self.mem
        m.d.comb += self.rd_data.eq(self.mem[self.rd_addr])
        return m


class InstFetch(wiring.Component):
    """
    InstFetch is a hardware component that fetches instructions from memory.
    Attributes:
        pc (Signal): The current program counter value.
        simple_inst_mem (SimpleInstMem): The instruction memory component.
        next_pc (In): The next program counter value.
        pc_out (Out): The current program counter value.
        inst_out (Out): The instruction read from memory.
    """

    def __init__(
        self,
        data_shape: Shape,
        # TODO: SimpleInstMemをBusMasterに変更する
        inst_mem_depth: int = 256,
        inst_mem_init_data: Any = [0x00000000],
    ):
        self.pc = Signal(data_shape)

        # TODO: SimpleInstMemをBusMasterに変更する
        self.simple_inst_mem = SimpleInstMem(
            data_shape=data_shape, depth=inst_mem_depth, init_data=inst_mem_init_data
        )

        super().__init__(
            {
                "next_pc": In(data_shape),
                "pc_out": Out(data_shape),
                "inst_out": Out(data_shape),
                "valid": Out(1),
            }
        )

    def elaborate(self, platform):
        m = Module()

        # 組み合わせ回路で現在のPCと対応するメモリアドレスの値をセットで出力
        m.d.comb += self.pc_out.eq(self.pc)
        m.d.comb += self.inst_out.eq(self.simple_inst_mem.rd_data)
        m.d.comb += self.simple_inst_mem.rd_addr.eq(self.pc)
        # simple_inst_memをMemPortに置き換えた場合、リソース競合によるハザードを考慮する
        m.d.comb += self.valid.eq(1)

        with m.If(self.next_pc != self.pc):
            m.d.sync += self.pc.eq(self.next_pc)

        return m


if __name__ == "__main__":
    instfetch = InstFetch(data_shape=unsigned(32), inst_mem_init_data=[0x00000000])
    main(instfetch)
