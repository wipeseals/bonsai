import enum
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import auto
from typing import List, Literal, Tuple


class SysAddr:
    """
    メモリ空間の定義。簡略化のため固定
    """

    # Address Space
    AddrU32 = int
    # Data (u32)
    DataU32 = int
    # Data (s32)
    DataS32 = int
    # ワードあたりのバイト数
    NUM_WORD_BYTES = 4
    # ワードあたりのビット数
    NUM_WORD_BITS = 32


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
        num_en_bytes: SysAddr.AddrU32 = SysAddr.NUM_WORD_BYTES,
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
        num_en_bytes: SysAddr.AddrU32 = SysAddr.NUM_WORD_BYTES,
    ) -> BusError:
        """
        Write data to the slave
        """
        pass

    def mask_unaligned_data(
        self,
        read_data: SysAddr.DataU32,
        offset: SysAddr.AddrU32,
        num_en_bytes: SysAddr.AddrU32,
    ) -> SysAddr.DataU32:
        """
        指定されたデータをoffset+bytemaskして返す
        """
        # データのマスク
        byte_mask = (1 << (num_en_bytes * 8)) - 1
        read_data = (read_data >> (offset * 8)) & byte_mask
        return read_data

    def apply_unaligned_data(
        self,
        current_data: SysAddr.DataU32,
        write_data: SysAddr.DataU32,
        offset: SysAddr.AddrU32,
        num_en_bytes: SysAddr.AddrU32,
    ) -> SysAddr.DataU32:
        """
        指定されたデータをoffset+bytemaskして適用したものを返す
        """
        # 有効部分だけにした書き込みデータを作成
        byte_mask = (1 << (num_en_bytes * 8)) - 1
        write_data = (write_data & byte_mask) << (offset * 8)
        # 現在のデータの書き込み部分を0にMaskしたデータを作成
        current_data = current_data & ~(byte_mask << (offset * 8))
        # 現在のデータに書き込みデータを適用
        dst_data = current_data | write_data
        return dst_data

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
        init_data: List[SysAddr.DataU32] | bytes | None = None,
    ):
        self.name = name
        self.size = size
        self.word_size = size // SysAddr.NUM_WORD_BYTES
        # 生データはword単位で保持
        self.datas = [SysAddr.DataU32(0) for _ in range(self.word_size)]
        # 初期値で上書き
        if init_data is not None:
            if isinstance(init_data, list):
                self.datas[: len(init_data)] = init_data
            elif isinstance(init_data, bytes):
                for idx in range(len(init_data) // SysAddr.NUM_WORD_BYTES):
                    self.datas[idx] = int.from_bytes(
                        init_data[
                            idx * SysAddr.NUM_WORD_BYTES : (idx + 1)
                            * SysAddr.NUM_WORD_BYTES
                        ],
                        "little",
                    )
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
        num_en_bytes: SysAddr.AddrU32 = SysAddr.NUM_WORD_BYTES,
    ) -> Tuple[SysAddr.DataU32, BusError | None]:
        # アドレス範囲チェック
        if addr < 0 or addr >= self.size:
            return 0, BusError.ERROR_OUT_OF_RANGE
        # word_index計算 + ミスアライン例外チェック
        word_addr = addr // SysAddr.NUM_WORD_BYTES
        word_offset = addr % SysAddr.NUM_WORD_BYTES
        if word_offset + num_en_bytes > SysAddr.NUM_WORD_BYTES:
            return 0, BusError.ERROR_MISALIGN
        # データ取得してアライン考慮して返す
        data = self.datas[word_addr]
        data = self.mask_unaligned_data(
            read_data=data, offset=word_offset, num_en_bytes=num_en_bytes
        )
        return data, None

    def write(
        self,
        addr: SysAddr.AddrU32,
        data: SysAddr.DataU32,
        access_type: AccessType = AccessType.NORMAL,
        num_en_bytes: SysAddr.AddrU32 = SysAddr.NUM_WORD_BYTES,
    ) -> BusError:
        # アドレス範囲チェック
        if addr < 0 or addr >= self.size:
            return BusError.ERROR_OUT_OF_RANGE
        # ミスアライン例外
        word_addr = addr // SysAddr.NUM_WORD_BYTES
        word_offset = addr % SysAddr.NUM_WORD_BYTES
        if word_offset + num_en_bytes > SysAddr.NUM_WORD_BYTES:
            return BusError.ERROR_MISALIGN
        # データをアライン考慮して書き込み
        current_data = self.datas[word_addr]
        dst_data = self.apply_unaligned_data(
            current_data=current_data,
            write_data=data,
            offset=word_offset,
            num_en_bytes=num_en_bytes,
        )
        self.datas[word_addr] = dst_data
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
        num_en_bytes: SysAddr.AddrU32 = SysAddr.NUM_WORD_BYTES,
    ) -> BusError:
        return BusError.ERROR_UNSUPPORTED


class MemMappedRegModule(BusSlave, ABC):
    """
    メモリマップトレジスタを表すクラス
    """

    def __init__(self, num_reg_bytes: SysAddr.AddrU32 = 4):
        self.num_reg_bytes = num_reg_bytes
        super().__init__()

    def byte_to_reg_idx(self, byte_idx: int) -> int:
        """
        Convert byte index to register index
        """
        return byte_idx // self.num_reg_bytes

    def reg_idx_to_byte(self, reg_idx: int) -> int:
        """
        Convert register index to byte index
        """
        return reg_idx * self.num_reg_bytes

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
        num_en_bytes: SysAddr.AddrU32 = SysAddr.NUM_WORD_BYTES,
    ) -> Tuple[SysAddr.DataU32, BusError | None]:
        reg_idx = self.byte_to_reg_idx(addr)
        data = self.read_reg(reg_idx, access_type)
        # addr offset/en_bytes考慮
        data = self.mask_unaligned_data(
            read_data=data, offset=addr % self.num_reg_bytes, num_en_bytes=num_en_bytes
        )
        return data, None

    def write(
        self,
        addr: SysAddr.AddrU32,
        data: SysAddr.DataU32,
        access_type: AccessType,
        num_en_bytes: SysAddr.AddrU32 = SysAddr.NUM_WORD_BYTES,
    ) -> BusError | None:
        reg_idx = self.byte_to_reg_idx(addr)
        # addr offset/en_bytes考慮
        current_data, err = self.read_reg(reg_idx, AccessType.DEBUG_INTERNAL)
        if err is not None:
            return err

        dst_data = self.apply_unaligned_data(
            current_data=current_data,
            write_data=data,
            offset=addr % self.num_reg_bytes,
            num_en_bytes=num_en_bytes,
        )
        return self.write_reg(reg_idx, dst_data, access_type)


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
        self.size = UartModule.RegIdx.NUM_REGS.value * SysAddr.NUM_WORD_BYTES
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
        super().__init__(num_reg_bytes=4)

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
        num_en_bytes: SysAddr.AddrU32 = SysAddr.NUM_WORD_BYTES,
    ) -> Tuple[SysAddr.DataU32, BusError | None]:
        for entry in self._entries:
            if entry.is_in_range(addr):
                return entry.slave.read(
                    addr - entry.start_addr, access_type, num_en_bytes
                )
        return 0, BusError.ERROR_OUT_OF_RANGE

    def write(
        self,
        addr: SysAddr.AddrU32,
        data: SysAddr.DataU32,
        access_type: AccessType = AccessType.NORMAL,
        num_en_bytes: SysAddr.AddrU32 = SysAddr.NUM_WORD_BYTES,
    ) -> BusError:
        for entry in self._entries:
            if entry.is_in_range(addr):
                return entry.slave.write(
                    addr - entry.start_addr, data, access_type, num_en_bytes
                )
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

    def describe(self) -> str:
        dst = f"# BusArbiter: {self.name}\n"
        dst += f" - min_addr: 0x{self.min_addr:016x}\n"
        dst += f" - max_addr: 0x{self.max_addr:016x}\n"
        dst += f" - size: {self.size} bytes\n"
        dst += f" - {len(self._entries)} entries\n"
        for i, entry in enumerate(self._entries):
            dst += (
                f"  - entry {i}: 0x{entry.start_addr:016x} {entry.slave.get_name()}\n"
            )
        return dst
