from enum import IntEnum
from typing import Any, List, Optional
from amaranth import Format, Print

# Kanata 向けログ出力用の関数
# https://www.mtl.t.u-tokyo.ac.jp/~onikiri2/wiki/index.php?%E4%BB%95%E6%A7%98%2F%E3%83%93%E3%82%B8%E3%83%A5%E3%82%A2%E3%83%A9%E3%82%A4%E3%82%B6%2F%E3%83%AD%E3%82%B0%E3%81%AE%E3%83%95%E3%82%A9%E3%83%BC%E3%83%9E%E3%83%83%E3%83%88


def print_header(version: int = 4) -> List[Any]:
    """
    Kanata Log header

    Args:
        version: ログファイルのバージョン。省略時は4
    """
    return [
        Print(Format("Kanata\t%d", version)),
    ]


def print_sim_start_cycle(cycle: int) -> List[Any]:
    """
    シミュレーション開始サイクル

    Args:
        cycle: 開始サイクル数
    """
    return [
        Print(Format("C=\t%d", cycle)),
    ]


def print_elapsed_cycle(cycle: int) -> List[Any]:
    """
    前回ログ出力時からの経過サイクル

    Args:
        cycle: 経過サイクル数
    """
    return [
        Print(Format("C\t%d", cycle)),
    ]


def print_command_start(
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


class LabelVisibility(IntEnum):
    """
    ラベルの表示設定
    """

    ALWAYS = 0
    HOVER = 1


def print_command_label(
    uniq_id: int, visibility: LabelVisibility, label: str
) -> List[Any]:
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
                visibility.value,
                label,
            )
        ),
    ]


# TODO: 残りのログ出力を実装
# TODO: Log上のInstruction Decodeを実装
