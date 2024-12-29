from enum import IntEnum
from typing import Any, List, Optional
from amaranth import Format, Print


class Kanata:
    """
    Kanata Log出力用の関数群
    refs. https://www.mtl.t.u-tokyo.ac.jp/~onikiri2/wiki/index.php?%E4%BB%95%E6%A7%98%2F%E3%83%93%E3%82%B8%E3%83%A5%E3%82%A2%E3%83%A9%E3%82%A4%E3%82%B6%2F%E3%83%AD%E3%82%B0%E3%81%AE%E3%83%95%E3%82%A9%E3%83%BC%E3%83%9E%E3%83%83%E3%83%88
    """

    @staticmethod
    def header(version: int = 4) -> List[Any]:
        """
        Kanata Log header

        Args:
            version: ログファイルのバージョン。省略時は4
        """
        return [
            Print(Format("Kanata\t%d", version)),
        ]

    @staticmethod
    def start_cyc(cycle: int) -> List[Any]:
        """
        シミュレーション開始サイクル

        Args:
            cycle: 開始サイクル数
        """
        return [
            Print(Format("C=\t%d", cycle)),
        ]

    @staticmethod
    def offset_cyc(cycle: int) -> List[Any]:
        """
        前回ログ出力時からの経過サイクル

        Args:
            cycle: 経過サイクル数
        """
        return [
            Print(Format("C\t%d", cycle)),
        ]

    @staticmethod
    def cmd_start(
        uniq_id: int, inst_id: Optional[int] = None, thread_id: int = 0
    ) -> List[Any]:
        """
        コマンド開始

        Args:
            uniq_id: ログファイル内の一意なID
            inst_id: シミュレータ内で命令に割り振られたID。省略時はuniq_idと同じになる
            thread_id: スレッドID。省略時は0になる
        """
        return [
            Print(
                Format(
                    "I\t%d\t%d\t%d",
                    uniq_id,
                    inst_id if inst_id is not None else uniq_id,
                    thread_id,
                )
            ),
        ]

    class LabelType(IntEnum):
        """
        ラベルの表示設定
        """

        ALWAYS = 0
        HOVER = 1

    @staticmethod
    def cmd_label(uniq_id: int, label_type: LabelType, label: str) -> List[Any]:
        """
        コマンドラベル

        Args:
            uniq_id: ログファイル内の一意なID
            label: ラベル名
            thread_id: スレッドID。省略時は0になる
        """
        return [
            Print(
                Format(
                    "L\t%d\t%d\t%s",
                    uniq_id,
                    label_type.value,
                    label,
                )
            ),
        ]

    @staticmethod
    def stage_start(uniq_id: int, lane_id: int, stage_name: str) -> List[Any]:
        """
        ステージ開始

        Args:
            uniq_id: ログファイル内の一意なID
            lane_id: レーンID
            stage_name: ステージ名
        """
        return [
            Print(
                Format(
                    "S\t%d\t%d\t%s",
                    uniq_id,
                    lane_id,
                    stage_name,
                )
            ),
        ]

    @staticmethod
    def stage_end(uniq_id: int, lane_id: int, stage_name: str) -> List[Any]:
        """
        ステージ終了

        Args:
            uniq_id: ログファイル内の一意なID
            lane_id: レーンID
            stage_name: ステージ名
        """
        return [
            Print(
                Format(
                    "E\t%d\t%d\t%s",
                    uniq_id,
                    lane_id,
                    stage_name,
                )
            ),
        ]

    class CmdEndType(IntEnum):
        """
        コマンド終了のオプション
        """

        RETIRE = 0
        FLUSH = 1

    @staticmethod
    def cmd_end(uniq_id: int, retire_id: int, end_type: CmdEndType) -> List[Any]:
        """
        コマンド終了

        Args:
            uniq_id: ログファイル内の一意なID
            retire_id: リタイアID
            end_opt: 終了オプション
        """
        return [
            Print(
                Format(
                    "R\t%d\t%d\t%d",
                    uniq_id,
                    retire_id,
                    end_type.value,
                )
            ),
        ]

    class DependsType(IntEnum):
        """
        依存関係の種類
        """

        WAKEUP = 0
        RESERVED = 1

    @staticmethod
    def depends(
        consumer_id: int, producer_id: int, depends_type: DependsType
    ) -> List[Any]:
        """
        依存関係

        Args:
            consumer_id: 依存するID
            producer_id: 依存されるID
            depends_type: 依存関係の種類
        """
        return [
            Print(
                Format(
                    "D\t%d\t%d\t%d",
                    consumer_id,
                    producer_id,
                    depends_type.value,
                )
            ),
        ]
