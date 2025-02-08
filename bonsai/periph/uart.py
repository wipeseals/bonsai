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

    @classmethod
    def default(cls, clk_freq: float) -> "UartConfig":
        return cls(clk_freq=clk_freq)

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

    @property
    def baud_rate_error(self) -> float:
        """
        clk_freqで駆動された場合のボーレート誤差率を計算します。
        このメソッドは、クロック周波数とイベントティックカウントに基づいて実際のボーレートを計算し、
        設定されたボーレートに対する誤差率を算出します。
        戻り値:
            float: ボーレート誤差率（パーセンテージ）
        説明:
        actual_baud_rate = self.clk_freq / self.event_tick_count:
            - self.clk_freq: クロック周波数を表します。
            - self.event_tick_count: クロック周波数で駆動された場合に設定されたボーレートでイベントを発火するために必要なティック数を表します。
            - この式は、クロック周波数をイベントティックカウントで割ることで実際のボーレートを計算します。
        error = ((actual_baud_rate - self.baud_rate) / self.baud_rate) * 100:
            - actual_baud_rate: 上記で計算された実際のボーレート。
            - self.baud_rate: 設定されたボーレート。
            - この式は、実際のボーレートと設定されたボーレートの間のパーセンテージ誤差を計算します。
            - (actual_baud_rate - self.baud_rate): 実際のボーレートと設定されたボーレートの差を計算します。
            - self.baud_rateで割ることで相対誤差を求めます。
            - 100を掛けることで相対誤差をパーセンテージに変換します。
        このプロパティは、クロック周波数で駆動された場合の設定されたボーレートからのパーセンテージ偏差を返し、ボーレートの精度を評価することができます。
        """
        actual_baud_rate = self.clk_freq / self.event_tick_count
        error = ((actual_baud_rate - self.baud_rate) / self.baud_rate) * 100
        return error


class UartTx(wiring.Component):
    def __init__(self, config: UartConfig, *, src_loc_at=0):
        self._config = config

        super().__init__(
            {
                "stream": In(stream.Signature(config.num_data_bit)),
                "en": In(1),
                "tx": Out(1),
                "busy": Out(1),
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
        with m.FSM(init="IDLE") as fsm:
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

        m.d.sync += [
            self.busy.eq(~fsm.ongoing("IDLE")),
        ]

        return m


class UartRx(wiring.Component):
    def __init__(self, config: UartConfig, *, src_loc_at=0):
        self._config = config

        super().__init__(
            {
                "rx": In(1),
                "en": In(1),
                "stream": Out(stream.Signature(config.num_data_bit)),
                "busy": Out(1),
                "parity_err": Out(1),
            },
            src_loc_at=src_loc_at,
        )

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        # 受信データ格納
        rx_data = Signal(self._config.num_data_bit, init=0)
        rx_data_valid = Signal(0, init=0)
        # 受信データをstreamに転送
        m.d.comb += [
            self.stream.payload.eq(rx_data),
            self.stream.valid.eq(rx_data_valid),
        ]
        # streamがrdyなら受信データをクリア
        with m.If(self.stream.ready):
            m.d.sync += [
                rx_data_valid.eq(0),
            ]
        div_counter = Signal(self._config.event_tick_counter_width, init=0)
        rx_counter = Signal(self._config.transfer_total_count, init=0)
        with m.FSM(init="IDLE") as fsm:
            with m.State("IDLE"):
                # enable & 受信データをStreamが吸った後 & StartBit検知で受信開始
                with m.If(self.en & ~rx_data_valid & ~self.rx):
                    # data clear
                    m.d.sync += [
                        div_counter.eq(0),
                        rx_data.eq(0),
                        rx_data_valid.eq(0),
                    ]
                    m.next = "START_BIT"
            with m.State("START_BIT"):
                # data capture用に 1/4周期遅らせる
                with m.If(div_counter < self._config.event_tick_count // 4 - 1):
                    # 1/4周期経過までカウント待機
                    m.d.sync += [
                        div_counter.eq(div_counter + 1),
                    ]
                with m.Else():
                    # 現位置はStartBitなので、次のEvent周期からデータキャプチャ
                    m.d.sync += [
                        div_counter.eq(0),
                    ]
                    m.next = "DATA"
            with m.State("DATA"):
                with m.If(div_counter < self._config.event_tick_count - 1):
                    # イベント周期までカウント
                    m.d.sync += [
                        div_counter.eq(div_counter + 1),
                    ]
                with m.Else():
                    # イベント周期でデータキャプチャ
                    m.d.sync += [
                        div_counter.eq(0),  # イベント周期のカウンタはクリア
                        rx_data.bit_select(rx_counter).eq(self.rx),
                    ]
                    with m.If(rx_counter < self._config.num_data_bit - 1):
                        # データビット受信中なので1bit移動
                        m.d.sync += [
                            rx_counter.eq(rx_counter + 1),
                        ]
                    with m.Else():
                        # データビット受信完了
                        with m.If(self._config.parity == UartParity.NONE):
                            m.next = "PUSH_DATA"
                        with m.Else():
                            m.next = "PARITY"
            with m.State("PARITY"):
                with m.If(div_counter < self._config.event_tick_count - 1):
                    # イベント周期までカウント
                    m.d.sync += [
                        div_counter.eq(div_counter + 1),
                    ]
                with m.Else():
                    # イベントカウンタはもう使わない
                    m.d.sync += [
                        div_counter.eq(0),
                    ]
                    # Parity bit受信
                    parity_bit = self.rx
                    # 正解計算
                    event_parity = rx_data.xor()
                    odd_parity = ~event_parity
                    expect_parity = (
                        odd_parity
                        if self._config.parity == UartParity.ODD
                        else event_parity
                    )
                    # 正解ならpush、不正解ならIdleに戻る
                    with m.If(parity_bit == expect_parity):
                        m.d.sync += [
                            self.parity_err.eq(0),
                        ]
                        m.next = "PUSH_DATA"
                    with m.Else():
                        # parity errorの場合はpushしない
                        m.d.sync += [
                            self.parity_err.eq(1),
                        ]
                        m.next = "IDLE"
            with m.State("PUSH_DATA"):
                # StopBitは待つ必要ない（次回のStartBit監視すればよいため）
                m.d.sync += [
                    rx_data_valid.eq(1),
                ]
                m.next = "IDLE"

        m.d.sync += [
            self.busy.eq(~fsm.ongoing("IDLE")),
        ]
