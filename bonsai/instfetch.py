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
        m.d.comb += self.rd_data.eq(self.mem[self.rd_addr // self.inst_bytes])
        # simple_inst_memをMemPortに置き換えた場合、リソース競合によるハザードを考慮する用の信号
        m.d.comb += self.rd_valid.eq(1)

        return m


class InstFetchDebug(data.StructLayout):
    """
    Debug information during instruction fetch
    Attributes:
        cyc (Signal): The cycle count at the time of fetch
        seq_no (Signal): The sequence number of the fetch operation
        stall_cyc (Signal): The number of cycles the fetch operation was stalled
    """

    def __init__(self, data_shape: Shape):
        ports = {
            "cyc": data.Signal(data_shape, init=0),
            "seq_no": data.Signal(data_shape, init=0),
            "stall_cyc": data.Signal(data_shape, init=0),
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
            "next_pc": data.Signal(data_shape, init=0),
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
            "inst": data.Signal(data_shape, init=0),
            "pc": data.Signal(data_shape, init=0),
        }
        if is_debug:
            ports["debug"] = data.Signal(InstFetchDebug(data_shape))

        super().__init__()


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

        # signals
        self.pc = Signal(data_shape, init=0)
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

        # next_pc取得
        with m.If(self.input.valid):
            m.d.sync += self.pc.eq(self.input.payload.next_pc)
            m.d.sync += self.input.ready.eq(1)

        with m.If(self.input.valid):
            # メモリアクセス完了時
            with m.If(self.mem.rd_valid):
                # Fetchデータ出力
                m.d.sync += self.output.payload.pc.eq(self.pc)
                m.d.sync += self.output.payload.inst.eq(self.mem.rd_data)
                if self.is_debug:
                    m.d.sync += self.output.payload.debug(self.debug)
                m.d.sync += self.output.valid.eq(1)

                # 次のPCが用意されていれば更新
                if m.If(self.input.valid):
                    m.d.sync += self.pc.eq(self.input.payload.next_pc)  # pc <= next_pc
                    m.d.sync += self.input.ready.eq(1)  # fetch next_pc

                # デバッグ情報更新
                if self.is_debug:
                    # seq_no更新
                    m.d.sync += self.debug.seq_no.eq(self.debug.seq_no + 1)
                    # stall cycle数をリセット
                    m.d.sync += self.debug.stall_cyc.eq(0)

            with m.Else:
                # メモリアクセス中

                if self.is_debug:
                    # stall cycle数をカウントアップ
                    m.d.sync += self.debug.stall_cyc.eq(self.debug.stall_cyc + 1)

        with m.Else:
            # 機能無効時
            # 出力は前回の値を維持

            if self.is_debug:
                # stall cycle数をカウントアップ (mem accessと分ける必要があれば情報分割する)
                m.d.sync += self.debug.stall_cyc.eq(self.debug.stall_cyc + 1)

        # Stream送受信のステータスを更新
        if m.If(self.output.valid & self.output.ready):
            m.d.sync += self.output.valid.eq(0)

        return m


if __name__ == "__main__":
    instfetch = InstFetch(data_shape=unsigned(32), inst_mem_init_data=[0x00000000])
    main(instfetch)
