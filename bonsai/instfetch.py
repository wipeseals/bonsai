from typing import Any
from amaranth import Module, Shape, Signal, unsigned
from amaranth.lib import wiring, enum, data, memory, stream
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
        self.data_shape = data_shape

        # memory実体はdata_shape単位で確保されているが、アドレスはbyte単位
        # 32bit=4byte, 64bit=8byteごとにメモリアクセスする, Compressとの動的切り替えは未対応
        self.inst_bytes = self.data_shape.width // 8
        self.mem = memory.Memory(shape=data_shape, depth=depth, init=init_data)
        super().__init__(
            {
                "rd_addr": In(depth.bit_length()),
                "rd_data": Out(data_shape),
                "rd_valid": Out(1),
            }
        )

    def elaborate(self, platform):
        m = Module()
        m.submodules.mem = self.mem

        # メモリアドレスをbyte単位からdata_shape単位に変換して、メモリからデータを読み出す
        rd_port = self.mem.read_port()
        m.d.comb += rd_port.addr.eq(self.rd_addr // self.inst_bytes)
        m.d.comb += self.rd_data.eq(rd_port.data)
        # simple_inst_memをMemPortに置き換えた場合、リソース競合によるハザードを考慮する用の信号
        m.d.comb += self.rd_valid.eq(1)

        return m


class InstFetchDebug(data.StructLayout):
    """
    Debug information during instruction fetch
    Attributes:
        cyc (Signal): The cycle count at the time of fetch
        seq_no (Signal): The sequence number of the fetch operation
    """

    def __init__(self, data_shape: Shape):
        ports = {
            "cyc": data_shape,
            "seq_no": data_shape,
        }
        super().__init__(ports)


class InstFetchIn(data.StructLayout):
    """
    Data structure of IF input signals
    Attributes:
        next_pc (Signal): The next program counter value
    """

    def __init__(self, data_shape: Shape, is_debug: bool = False):
        ports = {
            "next_pc": data_shape,
        }
        if is_debug:
            # TODO: EX,WB からPC操作時のデバッグ情報があれば追加
            pass

        super().__init__(ports)


class InstFetchOut(data.StructLayout):
    """
    Data structure of the IF/ID pipeline register
    Attributes:
        inst (Signal): The instruction read from memory.
        pc (Signal): The current program counter value.
        debug (InstFetchDebug): Debug information during instruction fetch (optional)
    """

    def __init__(self, data_shape: Shape, is_debug: bool = False):
        ports = {
            "inst": data_shape,
            "pc": data_shape,
        }
        if is_debug:
            ports["debug"] = data.Signal(InstFetchDebug(data_shape))

        super().__init__(ports)


class InstFetch(wiring.Component):
    """
    InstFetch is a hardware component that fetches instructions from memory.
    Attributes:
        en (In): Input signal to enable instruction fetch.
        next_pc (In): Input signal that specifies the next program counter value.
        out (Out): Output signal that contains the instruction read from memory.
    """

    def __init__(
        self,
        data_shape: Shape,
        # TODO: SimpleInstMemをBusMasterに変更する
        inst_mem_depth: int = 256,
        inst_mem_init_data: Any = [0x00000000],
        is_debug: bool = False,
    ):
        # meta data
        self.data_shape = data_shape
        self.is_debug = is_debug

        # TODO: SimpleInstMemをBusMasterに変更する
        self.mem = SimpleInstMem(
            data_shape=data_shape, depth=inst_mem_depth, init_data=inst_mem_init_data
        )

        ports = {
            "input": In(
                stream.Signature(InstFetchIn(data_shape, is_debug=is_debug)).flip()
            ),
            "output": Out(
                stream.Signature(InstFetchOut(data_shape, is_debug=is_debug))
            ),
        }
        if is_debug:
            self.debug = Signal(InstFetchDebug(data_shape))

        super().__init__(ports)

    def elaborate(self, platform):
        m = Module()
        m.submodules.mem = self.mem

        # デバッグ向け情報
        if self.is_debug:
            # cycle数はenable問わずにカウントアップする
            m.d.sync += self.debug.cyc.eq(self.debug.cyc + 1)

        # PC取得はmemアクセス中ではないタイミングで、next_pcが有効な場合に行う
        with m.FSM(init="idle"):
            with m.State("idle"):
                with m.If(self.mem.rd_valid):
                    with m.If(self.input.valid):
                        # next_pcを取得して、メモリアクセスを開始
                        m.d.sync += self.mem.rd_addr.eq(self.input.payload.next_pc)
                        m.d.sync += self.input.ready.eq(1)
                        m.next = "capture next_pc"
                    with m.Else():
                        # next_pcが有効になるまで待ち
                        m.d.sync += self.input.ready.eq(0)
                        m.next = "idle"
                with m.Else():
                    # メモリアクセス中
                    m.d.sync += self.input.ready.eq(0)
                    m.next = "idle"
            with m.State("capture next_pc"):
                with m.If(self.mem.rd_valid):
                    with m.If(self.input.valid):
                        # メモリアクセス完了 & 次のPC有効
                        m.d.sync += self.mem.rd_addr.eq(self.input.payload.next_pc)
                        m.d.sync += self.input.ready.eq(1)
                        m.next = "capture next_pc"
                    with m.Else():
                        # メモリアクセス完了 & 次のPC無効
                        m.d.sync += self.input.ready.eq(0)
                        m.next = "idle"
                with m.Else():
                    # メモリアクセス中
                    m.d.sync += self.input.ready.eq(0)
                    m.next = "idle"

        # inst/pc出力はmemアクセス完了時に行う
        with m.If(self.mem.rd_valid):
            # メモリアクセス完了、Fetchデータ出力
            m.d.sync += self.output.payload.inst.eq(self.mem.rd_data)
            m.d.sync += self.output.payload.pc.eq(self.mem.rd_addr)
            if self.is_debug:
                m.d.sync += self.output.payload.debug.eq(self.debug)
            m.d.sync += self.output.valid.eq(1)
            # デバッグ情報更新
            if self.is_debug:
                m.d.sync += self.debug.seq_no.eq(self.debug.seq_no + 1)
        with m.Else():
            # メモリアクセス中
            m.d.sync += self.output.valid.eq(0)

        return m


if __name__ == "__main__":
    instfetch = InstFetch(data_shape=unsigned(32), inst_mem_init_data=[0x00000000])
    main(instfetch)
