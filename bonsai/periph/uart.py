from amaranth import Module, Signal
from amaranth.build.plat import Platform
from amaranth.lib import enum, stream, wiring
from amaranth.lib.wiring import In, Out
from amaranth.utils import ceil_log2
from dataclasses import dataclass


@enum.unique
class UartParity(enum.IntEnum):
    NONE = 0
    ODD = 1
    EVEN = 2


@dataclass
class UartConfig:
    clk_freq: float
    baud_rate: int = 115200
    num_data_bit: int = 8
    num_stop_bit: int = 1
    parity: UartParity = UartParity(UartParity.NONE)


class UartTx(wiring.Component):
    def __init__(self, config: UartConfig, *, src_loc_at=0):
        self._clk_period = 1 / config.clk_freq
        self._period = 1 / config.baud_rate
        self._period_count = int(self._period / self._clk_period)
        self._div_counter_width = ceil_log2(self._period_count)

        assert config.num_data_bit > 0, "num_data_bit must be positive"
        assert config.num_stop_bit > 0, "num_stop_bit must be positive"
        self._num_data_bit = config.num_data_bit
        self._num_stop_bit = config.num_stop_bit
        self._parity = config.parity
        self._transfer_count = (
            self._num_data_bit
            + self._num_stop_bit
            + (1 if self._parity != UartParity.NONE else 0)
        )
        self._transfer_counter_width = ceil_log2(self._transfer_count)

        super().__init__(
            {
                "stream": In(stream.Signature(8)),
                "en": In(1),
                "tx": Out(1),
            },
            src_loc_at=src_loc_at,
        )

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        # 分周カウンタ
        div_counter = Signal(self._div_counter_width, init=0)
        event_tx = Signal(1, init=0)
        with m.If(div_counter < self._period_count):
            m.d.sync += [
                div_counter.eq(div_counter + 1),
                event_tx.eq(0),
            ]
        with m.Else():
            m.d.sync += [
                div_counter.eq(0),
                event_tx.eq(1),
            ]

        # streamからのデータ受付
        # AmaranthのData streamにあるData transfer rulesではSlave側のreadyがvalidを待つことを禁止していないが
        # AXIに習って受付可能状態にreadyを返すようにしておく
        tx_data = Signal(self._num_data_bit)
        tx_data_valid = Signal(1, init=0)
        # tx_dataにデータ格納してなければ取得OK
        m.d.comb += self.stream.ready.eq(~tx_data_valid)
        # ready & validで転送実行
        with m.If(self.stream.valid & self.stream.ready):
            m.d.sync += [
                tx_data.eq(self.stream.payload),
                tx_data_valid.eq(1),
            ]

        # 転送カウンタ+FSMで制御。enはいきなり反応しない
        tx_counter = Signal(self._transfer_counter_width, init=0)
        with m.FSM(init="IDLE"):
            with m.State("IDLE"):
                # 何も起きない場合にtx=1固定
                m.d.sync += [
                    tx_counter.eq(0),
                    self.tx.eq(1),  # Idle
                ]

                # 有効かつイベントタイミングかつデータあれば転送開始 + StartBit
                with m.If(event_tx & self.en & tx_data_valid):
                    m.d.sync += [
                        tx_counter.eq(0),  # 転送ビット位置向けに初期化
                        self.tx.eq(0),  # StartBitは状態遷移中に送信。次からデータ送信
                    ]
                    m.next = "DATA"
            with m.State("DATA"):
                with m.If(event_tx):
                    # Databit送信
                    with m.If(tx_counter < self._num_data_bit - 1):
                        # data bit(0~n-1)
                        m.d.sync += [
                            tx_counter.eq(tx_counter + 1),
                            self.tx.eq(tx_data.bit_select(tx_counter, 1)),
                        ]
                    with m.Else():
                        # last data bit
                        m.d.sync += [
                            tx_counter.eq(0),  # Parity/StopBit送信向けに初期化
                            self.tx.eq(tx_data.bit_select(tx_counter, 1)),
                        ]
                        # parity bit or stop bit
                        if self._parity in [UartParity.ODD, UartParity.EVEN]:
                            m.next = "PARITY"
                        elif self._parity == UartParity.NONE:
                            m.next = "STOP_BIT"
                        else:
                            raise ValueError(f"Invalid parity: {self._parity}")
            with m.State("PARITY"):
                with m.If(event_tx):
                    # 全bitのxorが奇数なら1、偶数なら0。この結果をそのまま使えるのはeven parity. odd parityはデータ全体が奇数になるように調整するので反転
                    even_parity = tx_data.xor()
                    odd_parity = ~even_parity
                    send_parity = (
                        odd_parity if self._parity == UartParity.ODD else even_parity
                    )
                    m.d.sync += [
                        tx_counter.eq(0),  # StopBit送信向けに初期化
                        self.tx.eq(send_parity),
                    ]
                    m.next = "STOP_BIT"
            with m.State("STOP_BIT"):
                with m.If(event_tx):
                    with m.If(tx_counter < self._num_stop_bit - 1):
                        # stop bit (0~n-1)
                        m.d.sync += [
                            tx_counter.eq(tx_counter + 1),
                            self.tx.eq(1),  # StopBit
                        ]
                    with m.Else():
                        # last stop bit
                        m.d.sync += [
                            tx_counter.eq(0),  # 転送終了したので初期化
                            self.tx.eq(1),  # StopBit
                        ]
                        # Fetchしたデータ不要
                        m.d.sync += [
                            tx_data_valid.eq(0),
                        ]
                        m.next = "IDLE"
        return m
