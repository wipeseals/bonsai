import enum
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import auto
from typing import List, Literal, Tuple

import numpy as np


class SysAddr:
    """
    メモリ空間の定義。簡略化のため固定
    """

    # Address Space
    AddrU32 = np.uint32
    # Data (u32)
    DataU32 = np.uint32
    # Data (s32)
    DataS32 = np.int32
    # ワードあたりのバイト数
    WORD_BYTES = 4


class AccessType(enum.Enum):
    """
    バスアクセスのキャッシュ制御種類
    """

    NORMAL = auto()
    NON_CACHE = auto()
    WRITE_BACK = auto()
    # Emulator内部での実装用
    DEBUG_INTERNAL = auto()


class BusError(enum.Enum):
    """
    バスアクセス結果
    """

    ERROR_OUT_OF_RANGE = auto()
    ERROR_TIMEOUT = auto()
    ERROR_UNSUPPORTED = auto()
    ERROR_MISALIGN = auto()
    ERROR_BY_SLAVE = auto()
    ERROR_OTHER = auto()


class BusSlave(ABC):
    """
    Bus Access Slaveを実装したクラス
    """

    @abstractmethod
    def get_name(self) -> str:
        """
        Get the name of the slave
        """
        pass

    @abstractmethod
    def get_size(self) -> int:
        """
        Get the size of the slave
        """
        pass

    @abstractmethod
    def read(
        self,
        addr: SysAddr.AddrU32,
        access_type: AccessType = AccessType.NORMAL,
    ) -> Tuple[SysAddr.DataU32, BusError | None]:
        """
        Read data from the slave
        """
        pass

    @abstractmethod
    def write(
        self,
        addr: SysAddr.AddrU32,
        data: SysAddr.DataU32,
        access_type: AccessType = AccessType.NORMAL,
    ) -> BusError:
        """
        Write data to the slave
        """
        pass

    def dump(
        self,
        dump_file_path: str,
        format: Literal["txt", "csv", "bin"] | None = None,
        offset_addr: int = 0,
    ) -> None:
        """
        現在の内容をファイルに出力
        """
        # formatが指定されていない場合は、拡張子から判断
        if format is None:
            if dump_file_path.endswith(".txt"):
                format = "txt"
            elif dump_file_path.endswith(".csv"):
                format = "csv"
            elif dump_file_path.endswith(".bin"):
                format = "bin"
            else:
                raise ValueError(f"Unsupported file extension: {dump_file_path}")
        # ファイル出力
        if format == "txt":
            with open(dump_file_path, "w") as f:
                f.write("offset in module\taddress\tdata\n")
                for addr_idx, data in enumerate(self.datas):
                    f.write(f"{addr_idx}\t{offset_addr + addr_idx}\t{data}\n")
        elif format == "csv":
            with open(dump_file_path, "w") as f:
                f.write("offset in module,address,data,\n")
                for addr_idx, data in enumerate(self.datas):
                    f.write(f"{addr_idx},{offset_addr + addr_idx},{data},\n")
        elif format == "bin":
            with open(dump_file_path, "wb") as f:
                f.write(self.datas.tobytes())
        else:
            raise ValueError(f"Unsupported format: {format}")


class FixSizeRam(BusSlave):
    """
    固定長のメモリを表すクラス
    """

    def __init__(
        self,
        name: str,
        size: int,
        init_data: List[int] | np.ndarray | bytes | None = None,
    ):
        self.name = name
        self.size = size
        # 生データはu8で保持
        self.datas = np.zeros(size, dtype=np.uint8)
        # 初期値で上書き
        if init_data is not None:
            if isinstance(init_data, list):
                self.datas[: len(init_data)] = init_data
            elif isinstance(init_data, np.ndarray):
                self.datas[: len(init_data)] = init_data
            elif isinstance(init_data, bytes):
                self.datas[: len(init_data)] = np.frombuffer(init_data, dtype=np.uint8)
            else:
                raise ValueError(f"Unsupported init_data type: {type(init_data)}")

    def get_name(self) -> str:
        return self.name

    def get_size(self) -> int:
        return self.size

    def read(
        self,
        addr: SysAddr.AddrU32,
        access_type: AccessType = AccessType.NORMAL,
    ) -> Tuple[SysAddr.DataU32, BusError | None]:
        # アドレス範囲チェック
        if addr < 0 or addr >= self.size:
            return 0, BusError.ERROR_OUT_OF_RANGE
        # ミスアライン例外
        if addr % SysAddr.WORD_BYTES != 0:
            return 0, BusError.ERROR_MISALIGN
        # データ取得
        fetch_data = self.datas[addr : addr + SysAddr.WORD_BYTES]
        data = fetch_data.view(self.space.DataType)
        return data, None

    def write(
        self,
        addr: SysAddr.AddrU32,
        data: SysAddr.DataU32,
        access_type: AccessType = AccessType.NORMAL,
    ) -> BusError:
        # アドレス範囲チェック
        if addr < 0 or addr >= self.size:
            return BusError.ERROR_OUT_OF_RANGE
        # ミスアライン例外
        if addr % SysAddr.WORD_BYTES != 0:
            return BusError.ERROR_MISALIGN
        # データ書き込み
        self.datas[addr : addr + SysAddr.WORD_BYTES] = data.view(np.uint8)
        return None


class FixSizeRom(FixSizeRam):
    """
    固定長のROMを表すクラス
    """

    def write(
        self,
        addr: SysAddr.AddrU32,
        data: SysAddr.DataU32,
        access_type: AccessType = AccessType.NORMAL,
    ) -> BusError:
        return BusError.ERROR_UNSUPPORTED


class MemMappedRegModule(BusSlave, ABC):
    """
    メモリマップトレジスタを表すクラス
    """

    def byte_to_reg_idx(self, byte_idx: int) -> int:
        """
        Convert byte index to register index
        """
        return byte_idx // SysAddr.WORD_BYTES

    def reg_idx_to_byte(self, reg_idx: int) -> int:
        """
        Convert register index to byte index
        """
        return reg_idx * SysAddr.WORD_BYTES

    @abstractmethod
    def read_reg(
        self,
        reg_idx: int,
        access_type: AccessType,
    ) -> Tuple[SysAddr.DataU32, BusError | None]:
        """
        レジスタ値Readが発生したときに呼び出し
        """
        pass

    @abstractmethod
    def write_reg(
        self,
        reg_idx: int,
        data: SysAddr.DataU32,
        access_type: AccessType,
    ) -> BusError | None:
        """
        レジスタ値Writeが発生したときに呼び出し
        """
        pass

    def read(
        self,
        addr: SysAddr.AddrU32,
        access_type: AccessType,
    ) -> Tuple[SysAddr.DataU32, BusError | None]:
        reg_idx = self.byte_to_reg_idx(addr)
        return self.read_reg(reg_idx, access_type)

    def write(
        self,
        addr: SysAddr.AddrU32,
        data: SysAddr.DataU32,
        access_type: AccessType,
    ) -> BusError | None:
        reg_idx = self.byte_to_reg_idx(addr)
        return self.write_reg(reg_idx, data, access_type)


class UartModule(MemMappedRegModule):
    """
    UARTモジュール

    Register Map(32bit register):
        | addr       | name     | RW | default    | description |
        | ---------- | -------- | -- | ---------- | ----------- |
        | 0x00000000 | RX_VALID | RO | 0x00000000 | bit[0] = RX data valid |
        | 0x00000004 | RX_DATA  | RO | 0x00000000 | RX data |
        | 0x00000008 | TX_FULL  | RO | 0x00000000 | bit[0] = TX full |
        | 0x0000000C | TX_DATA  | RW | 0x00000000 | TX data |
    """

    class RegIdx(enum.Enum):
        """
        Register Index
        """

        RX_VALID = auto()
        RX_DATA = auto()
        TX_FULL = auto()
        TX_DATA = auto()
        NUM_REGS = auto()

    def __init__(
        self,
        name: str,
        log_file_path: str | None = None,
        pre_stdin: List[str] | None = None,
    ):
        self.name = name
        self.size = UartModule.RegIdx.NUM_REGS.value * SysAddr.WORD_BYTES
        # stdin事前入力
        self._pre_stdin = pre_stdin
        self._pre_stdin_idx: int | None = (
            0 if pre_stdin is not None and len(pre_stdin) > 0 else None
        )
        # ログ出力保持
        self._stdout: List[str] = []
        # ログファイルが存在していたら一旦削除
        self._log_file_path = log_file_path
        if self._log_file_path is not None:
            with open(self._log_file_path, "w"):
                pass

    def get_name(self) -> str:
        return self.name

    def get_size(self) -> int:
        return self.size

    def read_reg(
        self,
        reg_idx: int,
        access_type: AccessType,
    ) -> Tuple[SysAddr.DataU32, BusError | None]:
        if reg_idx == UartModule.RegIdx.RX_VALID.value:
            # RX_VALID: always valid
            return 1, None
        elif reg_idx == UartModule.RegIdx.RX_DATA.value:
            # RX_DATA: read from stdin
            # 事前設定されたstdinを使う
            if self._pre_stdin_idx is not None:
                if self._pre_stdin_idx < len(self._pre_stdin):
                    ret = ord(self._pre_stdin[self._pre_stdin_idx]) & 0xFF
                    self._pre_stdin_idx += 1
                    return ret, None
            # 事前設定されたstdinがない場合は、入力を待つ
            return input(), None
        elif reg_idx == UartModule.RegIdx.TX_FULL.value:
            # TX_FULL: always not full
            return 0, None
        elif reg_idx == UartModule.RegIdx.TX_DATA.value:
            # TX_DATA: cleared reg
            return 0, None
        else:
            logging.warning(f"Invalid register index: {reg_idx=}")
            return 0, BusError.ERROR_OUT_OF_RANGE

    def write_reg(
        self,
        reg_idx: int,
        data: SysAddr.DataU32,
        access_type: AccessType,
    ) -> BusError | None:
        if reg_idx == UartModule.RegIdx.RX_VALID.value:
            # RX_VALID: read only
            logging.warning(f"RX_VALID is read only. {reg_idx=}, {data=}")
            return BusError.ERROR_UNSUPPORTED
        elif reg_idx == UartModule.RegIdx.RX_DATA.value:
            # RX_DATA: read only
            logging.warning(f"RX_DATA is read only. {reg_idx=}, {data=}")
            return BusError.ERROR_UNSUPPORTED
        elif reg_idx == UartModule.RegIdx.TX_FULL.value:
            # TX_FULL: read only
            return BusError.ERROR_UNSUPPORTED
        elif reg_idx == UartModule.RegIdx.TX_DATA.value:
            # TX_DATA: write to stdout
            char = chr(data & 0xFF)
            self._stdout.append(char)
            print(char, end="")
            if self._log_file_path is not None:
                with open(self._log_file_path, "a") as f:
                    f.write(char)
            return None
        else:
            logging.warning(f"Invalid register index: {reg_idx}")
            return BusError.ERROR_OUT_OF_RANGE

    @property
    def stdout(self) -> str:
        """
        Get the stdout
        """
        return "".join(self._stdout)


@dataclass
class BusArbiterEntry:
    """
    バスアービターのエントリ
    """

    slave: BusSlave
    start_addr: SysAddr.AddrU32

    @property
    def end_addr(self) -> SysAddr.AddrU32:
        return self.start_addr + self.slave.get_size() - 1

    @property
    def size(self) -> int:
        return self.slave.get_size()

    def is_in_range(self, addr: SysAddr.AddrU32) -> bool:
        return self.start_addr <= addr <= self.end_addr


class BusArbiter(BusSlave):
    """
    Bus Slaveを複数持ち、アドレス空間ごとにアクセスを振り分けるクラス
    """

    def __init__(self, name: str, entries: List[BusArbiterEntry]):
        self.name = name
        # 登録されたslaveのRangeからサイズを算出
        self.min_addr = min(slave.start_addr for slave in entries)
        self.max_addr = max(slave.end_addr for slave in entries)
        self.size = self.max_addr - self.min_addr + 1
        if self.size < 0:
            raise ValueError(f"Invalid size: {self.size=}")
        # Overwrapのチェック
        for idx, entry in enumerate(entries):
            for other_entry in entries[idx + 1 :]:
                if entry.start_addr <= other_entry.start_addr <= entry.end_addr:
                    raise ValueError(f"Overwrap detected: {entry=}, {other_entry=}")
        self._entries = list(entries)

    def get_name(self) -> str:
        return self.name

    def get_size(self) -> int:
        return self.size

    def read(
        self,
        addr: SysAddr.AddrU32,
        access_type: AccessType = AccessType.NORMAL,
    ) -> Tuple[SysAddr.DataU32, BusError | None]:
        for entry in self._entries:
            if entry.is_in_range(addr):
                return entry.slave.read(addr - entry.start_addr, access_type)
        return 0, BusError.ERROR_OUT_OF_RANGE

    def write(
        self,
        addr: SysAddr.AddrU32,
        data: SysAddr.DataU32,
        access_type: AccessType = AccessType.NORMAL,
    ) -> BusError:
        for entry in self._entries:
            if entry.is_in_range(addr):
                return entry.slave.write(addr - entry.start_addr, data, access_type)
        return BusError.ERROR_OUT_OF_RANGE

    def dump_all_entries(
        self,
        dump_base_path: str,
        format: Literal["txt", "csv", "bin"] | None = None,
        offset_addr: int = 0,
    ) -> None:
        """
        登録された全slaveの内容をファイルに出力
        """
        for idx, entry in enumerate(self._entries):
            dump_file_path = (
                f"{dump_base_path}_{idx:04d}_{entry.slave.get_name()}.{format}"
            )
            entry.slave.dump(
                dump_file_path, format, offset_addr=offset_addr + entry.start_addr
            )
