from dataclasses import dataclass

from amaranth import Module, Signal
from amaranth.build.plat import Platform
from amaranth.lib import enum, stream, wiring
from amaranth.lib.wiring import In, Out
from amaranth.utils import ceil_log2


@enum.unique
class UartParity(enum.IntEnum):
    NONE = 0
    ODD = 1
    EVEN = 2


@dataclass
class UartConfig:
    """
    UARTの設定を保持するクラス
    """

    clk_freq: float
    baud_rate: int = 115200
    num_data_bit: int = 8
    num_stop_bit: int = 1
    parity: UartParity = UartParity(UartParity.NONE)

    @property
    def clk_period(self) -> float:
        """
        クロックの周期を返す
        """
        assert self.clk_freq > 0, "clk_freq must be positive"
        return 1 / self.clk_freq

    @property
    def baud_rate_period(self) -> float:
        """
        baud_rateの周期を返す
        """
        assert self.baud_rate > 0, "baud_rate must be positive"
        return 1 / self.baud_rate

    @property
    def event_tick_count(self) -> int:
        """
        clk_freqで駆動した際、baud_rateの周期でイベントを発火するために必要なカウント数を返す
        """
        count = int(self.baud_rate_period / self.clk_period)
        assert count > 0, "event_tick_count must be positive"
        return count

    @property
    def event_tick_counter_width(self) -> int:
        """
        イベント発火用のカウンタ幅を返す
        """
        count = int(ceil_log2(self.event_tick_count))
        assert count > 0, "event_tick_counter_width must be positive"
        return count

    @property
    def transfer_total_count(self) -> int:
        """
        1回の転送に必要なカウント数を返す
        """
        assert self.num_data_bit > 0, "num_data_bit must be positive"
        assert self.num_stop_bit > 0, "num_stop_bit must be positive"

        return (
            self.num_data_bit
            + self.num_stop_bit
            + (1 if self.parity != UartParity.NONE else 0)
        )

    @property
    def transfer_total_counter_width(self) -> int:
        """
        転送カウンタの幅を返す
        """
        count = int(ceil_log2(self.transfer_total_count))
        assert count > 0, "transfer_counter_width must be positive"
        return count


class UartTx(wiring.Component):
    def __init__(self, config: UartConfig, *, src_loc_at=0):
        self._config = config

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
        div_counter = Signal(self._config.event_tick_counter_width, init=0)
        event_tx = Signal(1, init=0)
        with m.If(div_counter < self._config.event_tick_count - 1):
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
        tx_data = Signal(self._config.num_data_bit, init=0)
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
        tx_counter = Signal(self._config.transfer_total_counter_width, init=0)
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
                    with m.If(tx_counter < self._config.num_data_bit - 1):
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
                        if self._config.parity in [UartParity.ODD, UartParity.EVEN]:
                            m.next = "PARITY"
                        elif self._config.parity == UartParity.NONE:
                            m.next = "STOP_BIT"
                        else:
                            raise ValueError(f"Invalid parity: {self._config.parity}")
            with m.State("PARITY"):
                with m.If(event_tx):
                    # 全bitのxorが奇数なら1、偶数なら0。この結果をそのまま使えるのはeven parity. odd parityはデータ全体が奇数になるように調整するので反転
                    even_parity = tx_data.xor()
                    odd_parity = ~even_parity
                    send_parity = (
                        odd_parity
                        if self._config.parity == UartParity.ODD
                        else even_parity
                    )
                    m.d.sync += [
                        tx_counter.eq(0),  # StopBit送信向けに初期化
                        self.tx.eq(send_parity),
                    ]
                    m.next = "STOP_BIT"
            with m.State("STOP_BIT"):
                with m.If(event_tx):
                    with m.If(tx_counter < self._config.num_stop_bit - 1):
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
