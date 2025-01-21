from enum import IntEnum
from typing import Optional
from amaranth import Format, Print


class Kanata:
    """
    Kanata Log出力用の関数群
    refs. https://www.mtl.t.u-tokyo.ac.jp/~onikiri2/wiki/index.php?%E4%BB%95%E6%A7%98%2F%E3%83%93%E3%82%B8%E3%83%A5%E3%82%A2%E3%83%A9%E3%82%A4%E3%82%B6%2F%E3%83%AD%E3%82%B0%E3%81%AE%E3%83%95%E3%82%A9%E3%83%BC%E3%83%9E%E3%83%83%E3%83%88
    """

    @staticmethod
    def header(version: int = 4) -> Print:
        """
        Kanata Log header
        e.g. Kanata	0004

        Args:
            version: ログファイルのバージョン。省略時は4
        """
        return Print(Format("Kanata\t{:04d}", version))

    @staticmethod
    def start_cyc(cycle: int) -> Print:
        """
        シミュレーション開始サイクル
        e.g. C=	216

        Args:
            cycle: 開始サイクル数
        """
        return Print(Format("C=\t{:d}", cycle))

    @staticmethod
    def elapsed_cyc(cycle: int) -> Print:
        """
        前回ログ出力時からの経過サイクル
        e.g. C	216

        Args:
            cycle: 経過サイクル数
        """
        return (Print(Format("C\t{:d}", cycle)),)

    @staticmethod
    def start_cmd(
        uniq_id: int, inst_id: Optional[int] = None, thread_id: int = 0
    ) -> Print:
        """
        コマンド開始
        e.g. I	0	0	0

        Args:
            uniq_id: ログファイル内の一意なID
            inst_id: シミュレータ内で命令に割り振られたID。省略時はuniq_idと同じになる
            thread_id: スレッドID。省略時は0になる
        """
        return Print(
            Format(
                "I\t{:d}\t{:d}\t{:d}",
                uniq_id,
                inst_id if inst_id is not None else uniq_id,
                thread_id,
            )
        )

    class LabelType(IntEnum):
        """
        ラベルの表示設定
        """

        ALWAYS = 0
        HOVER = 1

    @staticmethod
    def label_cmd_is(uniq_id: int, label_type: LabelType, pc: int) -> Print:
        """
        コマンドラベル
        e.g. L	0	0	12000d918 r4 = iALU(r3, r2)

        Args:
            uniq_id: ログファイル内の一意なID
            label_type: ラベルの表示設定
            pc: プログラムカウンタ
        """
        return Print(
            Format(
                "L\t{:d}\t{:d}\taddr = {:08x}",
                uniq_id,
                label_type.value,
                pc,
            )
        )

    @staticmethod
    def label_cmd_if(uniq_id: int, label_type: LabelType, inst: int) -> Print:
        """
        コマンドラベル
        e.g. L	0	0	12000d918 r4 = iALU(r3, r2)

        Args:
            uniq_id: ログファイル内の一意なID
            label_type: ラベルの表示設定
            inst: 命令データ
        """
        return Print(
            Format(
                "L\t{:d}\t{:d}\tinst = {:08x}",
                uniq_id,
                label_type.value,
                inst,
            )
        )

    @staticmethod
    def label_cmd(uniq_id: int, label_type: LabelType, label_data: str) -> Print:
        """
        コマンドラベル
        e.g. L	0	0	12000d918 r4 = iALU(r3, r2)

        Args:
            uniq_id: ログファイル内の一意なID
            label_type: ラベルの表示設定
            label_data: ラベルのテキスト
        """
        return Print(
            Format(
                "L\t{:d}\t{:d}\t{:s}",
                uniq_id,
                label_type.value,
                label_data,
            )
        )

    @staticmethod
    def start_stage(uniq_id: int, lane_id: int, stage: str) -> Print:
        """
        ステージ開始
        e.g. S	0	0	F

        Args:
            uniq_id: ログファイル内の一意なID
            lane_id: レーンID
            stage_name: ステージ名
        """
        return Print(
            Format(
                "S\t{:d}\t{:d}\t{:s}",
                uniq_id,
                lane_id,
                stage,
            )
        )

    @staticmethod
    def end_stage(uniq_id: int, lane_id: int, stage: str) -> Print:
        """
        ステージ終了
        e.g. E	0	0	F

        Args:
            uniq_id: ログファイル内の一意なID
            lane_id: レーンID
            stage_name: ステージ名
        """
        return Print(
            Format(
                "E\t{:d}\t{:d}\t{:s}",
                uniq_id,
                lane_id,
                stage,
            )
        )

    class CmdEndType(IntEnum):
        """
        コマンド終了のオプション
        """

        RETIRE = 0
        FLUSH = 1

    @staticmethod
    def cmd_end(uniq_id: int, retire_id: int, end_type: CmdEndType) -> Print:
        """
        コマンド終了
        e.g. R	0	0	F

        Args:
            uniq_id: ログファイル内の一意なID
            retire_id: リタイアID
            end_opt: 終了オプション
        """
        return Print(
            Format(
                "R\t{:d}\t{:d}\t{:d}",
                uniq_id,
                retire_id,
                end_type.value,
            )
        )

    class DependType(IntEnum):
        """
        依存関係の種類
        """

        WAKEUP = 0
        RESERVED = 1

    @staticmethod
    def depends(consumer_id: int, producer_id: int, depend_type: DependType) -> Print:
        """
        依存関係
        e.g. D	0	0	0

        Args:
            consumer_id: 依存するID
            producer_id: 依存されるID
            depend_type: 依存関係の種類
        """
        return Print(
            Format(
                "D\t{:d}\t{:d}\t{:d}",
                consumer_id,
                producer_id,
                depend_type.value,
            )
        )
