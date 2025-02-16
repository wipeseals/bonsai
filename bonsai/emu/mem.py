import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import auto
from typing import List, Literal, Optional, Tuple, TypeVar

import numpy as np


class MemSpace:
    """
    アドレス空間表現用
    Endian考慮も必要だが、LittleEndian固定とする
    """

    @staticmethod
    def bit_to_type(bit_width: int) -> TypeVar:
        """
        Convert bit width to type
        """
        if bit_width <= 8:
            return np.uint8
        elif bit_width <= 16:
            return np.uint16
        elif bit_width <= 32:
            return np.uint32
        elif bit_width <= 64:
            return np.uint64
        else:
            raise ValueError(f"Unsupported bit width: {bit_width}")

    @staticmethod
    def unsigned_to_signed(unsigned_type: TypeVar) -> TypeVar:
        """
        Convert unsigned type to signed type
        """
        if unsigned_type == np.uint8:
            return np.int8
        elif unsigned_type == np.uint16:
            return np.int16
        elif unsigned_type == np.uint32:
            return np.int32
        elif unsigned_type == np.uint64:
            return np.int64
        else:
            raise ValueError(f"Unsupported unsigned type: {unsigned_type}")

    def __init__(
        self,
        addr_bits: int = 32,
        data_bits: int = 32,
    ):
        self.num_addr_bits = addr_bits
        self.num_data_bits = data_bits
        self.num_addr_bytes = addr_bits // 8
        self.num_data_bytes = data_bits // 8
        self.AddrType = MemSpace.bit_to_type(addr_bits)
        self.DataType = MemSpace.bit_to_type(data_bits)
        self.DataSignedType = MemSpace.unsigned_to_signed(self.DataType)
        self.ByteEnType = MemSpace.bit_to_type(data_bits // 8)

    # インスタンス化前にアドレス、データの方が欲しい時用
    AbstAddrType = TypeVar("AddrType", np.uint8, np.uint16, np.uint32, np.uint64)
    AbstDataType = TypeVar("DataType", np.uint8, np.uint16, np.uint32, np.uint64)
    AbstDataSignedType = TypeVar(
        "DataSignedType", np.int8, np.int16, np.int32, np.int64
    )
    AbstByteEnType = TypeVar("ByteEnType", np.uint8, np.uint16, np.uint32, np.uint64)


class AccessType(enum.Enum):
    """
    バスアクセスのキャッシュ制御種類
    """

    NORMAL = auto()
    NON_CACHE = auto()
    WRITE_BACK = auto()
    # Emulator内部での実装用
    DEBUG_INTERNAL = auto()


class AccessResult(enum.Enum):
    """
    バスアクセス結果
    """

    OK = auto()
    ERROR_OUT_OF_RANGE = auto()
    ERROR_MISALIGNED = auto()
    ERROR_TIMEOUT = auto()
    ERROR_UNSUPPORTED = auto()
    ERROR_BY_SLAVE = auto()
    ERROR_OTHER = auto()


class BusSlave(ABC):
    """
    Bus Access Slaveを実装したクラス
    """

    def __init__(self, space: MemSpace):
        self.space = space
        super().__init__()

    @abstractmethod
    def name(self) -> str:
        """
        Get the name of the slave
        """
        pass

    @abstractmethod
    def size(self) -> int:
        """
        Get the size of the slave
        """
        pass

    @abstractmethod
    def read(
        self,
        addr: MemSpace.AbstAddrType,
        byteenable: MemSpace.AbstByteEnType | None = None,
        access_type: AccessType = AccessType.NORMAL,
    ) -> (AccessResult, MemSpace.AbstDataType):
        """
        Read data from the slave
        """
        pass

    @abstractmethod
    def write(
        self,
        addr: MemSpace.AbstAddrType,
        data: MemSpace.AbstDataType,
        byteenable: MemSpace.AbstByteEnType | None = None,
        access_type: AccessType = AccessType.NORMAL,
    ) -> AccessResult:
        """
        Write data to the slave
        """
        pass

    def read8(
        self,
        addr: MemSpace.AbstAddrType,
        access_type: AccessType = AccessType.NORMAL,
    ) -> (AccessResult, MemSpace.AbstDataType):
        """
        Read 8bit data from the slave
        """
        return self.read(addr, 0b1, access_type)

    def read16(
        self,
        addr: MemSpace.AbstAddrType,
        access_type: AccessType = AccessType.NORMAL,
    ) -> (AccessResult, MemSpace.AbstDataType):
        """
        Read 16bit data from the slave
        """
        return self.read(addr, 0b11, access_type)

    def read32(
        self,
        addr: MemSpace.AbstAddrType,
        access_type: AccessType = AccessType.NORMAL,
    ) -> (AccessResult, MemSpace.AbstDataType):
        """
        Read 32bit data from the slave
        """
        assert self.space.num_data_bits >= 32
        return self.read(addr, 0b1111, access_type)

    def read64(
        self,
        addr: MemSpace.AbstAddrType,
        access_type: AccessType = AccessType.NORMAL,
    ) -> (AccessResult, MemSpace.AbstDataType):
        """
        Read 64bit data from the slave
        """
        assert self.space.num_data_bits >= 64
        return self.read(addr, 0b1111_1111, access_type)

    def read128(
        self,
        addr: MemSpace.AbstAddrType,
        access_type: AccessType = AccessType.NORMAL,
    ) -> (AccessResult, MemSpace.AbstDataType):
        """
        Read 128bit data from the slave
        """
        assert self.space.num_data_bits >= 128
        return self.read(addr, 0b1111_1111_1111_1111, access_type)

    def write8(
        self,
        addr: MemSpace.AbstAddrType,
        data: MemSpace.AbstDataType,
        access_type: AccessType = AccessType.NORMAL,
    ) -> AccessResult:
        """
        Write 8bit data to the slave
        """
        return self.write(addr, data, 0b1, access_type)

    def write16(
        self,
        addr: MemSpace.AbstAddrType,
        data: MemSpace.AbstDataType,
        access_type: AccessType = AccessType.NORMAL,
    ) -> AccessResult:
        """
        Write 16bit data to the slave
        """
        return self.write(addr, data, 0b11, access_type)

    def write32(
        self,
        addr: MemSpace.AbstAddrType,
        data: MemSpace.AbstDataType,
        access_type: AccessType = AccessType.NORMAL,
    ) -> AccessResult:
        """
        Write 32bit data to the slave
        """
        assert self.space.num_data_bits >= 32
        return self.write(addr, data, 0b1111, access_type)

    def write64(
        self,
        addr: MemSpace.AbstAddrType,
        data: MemSpace.AbstDataType,
        access_type: AccessType = AccessType.NORMAL,
    ) -> AccessResult:
        """
        Write 64bit data to the slave
        """
        assert self.space.num_data_bits >= 64
        return self.write(addr, data, 0b1111_1111, access_type)

    def write128(
        self,
        addr: MemSpace.AbstAddrType,
        data: MemSpace.AbstDataType,
        access_type: AccessType = AccessType.NORMAL,
    ) -> AccessResult:
        """
        Write 128bit data to the slave
        """
        assert self.space.num_data_bits >= 128
        return self.write(addr, data, 0b1111_1111_1111_1111, access_type)

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
        space: MemSpace,
        name: str,
        size: int,
        init_data: List[int] | np.ndarray | bytes | None = None,
    ):
        self.space = space
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

        super().__init__(space)

    def name(self) -> str:
        return self.name

    def size(self) -> int:
        return self.size

    def read(
        self,
        addr: MemSpace.AbstAddrType,
        byteenable: MemSpace.AbstByteEnType | None = None,
        access_type: AccessType = AccessType.NORMAL,
    ) -> (AccessResult, MemSpace.AbstDataType):
        # データ取得
        fetch_data = self.datas[addr : addr + self.space.num_data_bytes]
        data = fetch_data.view(self.space.DataType)
        # byte enable無効部を破棄
        data = data & byteenable
        return AccessResult.OK, data

    def write(
        self,
        addr: MemSpace.AbstAddrType,
        data: MemSpace.AbstDataType,
        byteenable: MemSpace.AbstByteEnType | None = None,
        access_type: AccessType = AccessType.NORMAL,
    ) -> AccessResult:
        # byte enableを考慮して書き込み
        for byte_idx in range(self.space.num_data_bytes):
            if byteenable & (1 << byte_idx):
                self.datas[addr + byte_idx] = (data >> (8 * byte_idx)) & 0xFF
        return AccessResult.OK


class FixSizeRom(FixSizeRam):
    """
    固定長のROMを表すクラス
    """

    def write(
        self,
        addr: MemSpace.AbstAddrType,
        data: MemSpace.AbstDataType,
        byteenable: MemSpace.AbstByteEnType | None = None,
        access_type: AccessType = AccessType.NORMAL,
    ) -> AccessResult:
        return AccessResult.ERROR_UNSUPPORTED


class MemMappedRegModule(BusSlave, ABC):
    """
    メモリマップトレジスタを表すクラス
    """

    @classmethod
    def byte_to_reg_idx(cls, byte_idx: int, num_data_bytes: int) -> int:
        """
        Convert byte index to register index
        """
        return byte_idx // num_data_bytes

    @classmethod
    def reg_idx_to_byte(cls, reg_idx: int, num_data_bytes: int) -> int:
        """
        Convert register index to byte index
        """
        return reg_idx * num_data_bytes

    def __init__(self, space: MemSpace, name: str, num_regs: int):
        self.num_regs = num_regs
        self.size = self.reg_idx_to_byte(num_regs, space.num_data_bytes)
        super().__init__(space)

    def read_reg(
        self, reg_idx: int, access_type=AccessType.DEBUG_INTERNAL
    ) -> MemSpace.AbstDataType:
        """
        Get register data
        """
        addr = self.reg_idx_to_byte(reg_idx, self.space.num_data_bytes)
        ret, data = self.read(addr=addr, access_type=access_type)
        assert ret == AccessResult.OK, f"Failed to read register {reg_idx}"
        return data

    def write_reg(
        self,
        reg_idx: int,
        data: MemSpace.AbstDataType,
        access_type=AccessType.DEBUG_INTERNAL,
    ) -> AccessResult:
        """
        Write register data
        """
        addr = self.reg_idx_to_byte(reg_idx, self.space.num_data_bytes)
        return self.write(addr=addr, data=data, access_type=access_type)

    @abstractmethod
    def on_read_reg(
        self, reg_idx: int
    ) -> Optional[Tuple[AccessResult, MemSpace.AbstDataType]]:
        """
        レジスタ値Readが発生したときに呼び出し。以下の用途を想定
        戻り値の想定:
            | usage                                | return |
            | ------------------------------------ | --- |
            | event hookのみ                       | None|
            | event hookしてかつ特定のレジスタ値を返す| (AccessResult.OK, data)|
            | エラー応答させる                      | (AccessResult.ERROR_XXX, None)|
        """
        pass

    @abstractmethod
    def on_write_reg(
        self, reg_idx: int, data: MemSpace.AbstDataType
    ) -> AccessResult | None:
        """
        レジスタ値Writeが発生したときに呼び出し。以下の用途を想定

        戻り値の想定:
            | usage             | return |
            | ----------------- | --- |
            | event hookのみ    | None |
            | エラー応答させる   | AccessResult.ERROR_XXX |

        """
        pass

    def read(
        self,
        addr: MemSpace.AbstAddrType,
        byteenable: MemSpace.AbstByteEnType,
        access_type: AccessType,
    ) -> MemSpace.AbstDataType:
        reg_idx = self.byte_to_reg_idx(addr, self.space.num_data_bytes)
        # register readにフックするが、この際のエラーはそのまま帰す
        hook_ret = self.on_read_reg(reg_idx)
        if hook_ret is not None:
            return hook_ret
        # register readに成功した場合は、そのままreadを実行
        return super().read(addr=addr, byteenable=byteenable, access_type=access_type)

    def write(
        self,
        addr: MemSpace.AbstAddrType,
        data: MemSpace.AbstDataType,
        byteenable: MemSpace.AbstByteEnType,
        access_type: AccessType,
    ) -> AccessResult:
        reg_idx = self.byte_to_reg_idx(addr, self.space.num_data_bytes)
        # register writeにフックする
        hook_ret = self.on_write_reg(reg_idx, data)
        if hook_ret is not None:
            return hook_ret
        # register writeに成功した場合は、そのままwriteを実行
        return super().write(
            addr=addr, data=data, byteenable=byteenable, access_type=access_type
        )


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

    class RegIdx(enum.IntEnum):
        """
        Register Index
        """

        RX_VALID = 0
        RX_DATA = auto()
        TX_FULL = auto()
        TX_DATA = auto()
        NUM_REGS = auto()

    def __init__(
        self,
        space: MemSpace,
        name: str,
        log_file_path: str | None = None,
        pre_stdin: List[str] | None = None,
    ):
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
        super().__init__(space, name, UartModule.RegIdx.NUM_REGS)
        # レジスタ初期値設定必要ならここで設定。全部hookで返すなら不要

    def name(self) -> str:
        return super().name()

    def size(self) -> int:
        return super().size()

    def on_read_reg(
        self, reg_idx: int
    ) -> Optional[Tuple[AccessResult, MemSpace.AbstDataType]]:
        if reg_idx == UartModule.RegIdx.RX_VALID:
            # RX_VALID: always valid
            return AccessResult.OK, 1
        elif reg_idx == UartModule.RegIdx.RX_DATA:
            # RX_DATA: read from stdin
            # 事前設定されたstdinを使う
            if self._pre_stdin_idx is not None:
                if self._pre_stdin_idx < len(self._pre_stdin):
                    ret = ord(self._pre_stdin[self._pre_stdin_idx])
                    self._pre_stdin_idx += 1
                    return AccessResult.OK, ret
            # 事前設定されたstdinがない場合は、入力を待つ
            return AccessResult.OK, input()
        elif reg_idx == UartModule.RegIdx.TX_FULL:
            # TX_FULL: always not full
            return AccessResult.OK, 0
        elif reg_idx == UartModule.RegIdx.TX_DATA:
            # TX_DATA: do nothing
            return None
        else:
            assert False, f"Invalid register index: {reg_idx=}"
            return AccessResult.ERROR_OUT_OF_RANGE, None

    def on_write_reg(
        self, reg_idx: int, data: MemSpace.AbstDataType
    ) -> AccessResult | None:
        if reg_idx == UartModule.RegIdx.RX_VALID:
            # RX_VALID: read only
            assert False, f"RX_VALID is read only. {reg_idx=}, {data=}"
            return AccessResult.ERROR_UNSUPPORTED
        elif reg_idx == UartModule.RegIdx.RX_DATA:
            # RX_DATA: read only
            assert False, f"RX_DATA is read only. {reg_idx=}, {data=}"
            return AccessResult.ERROR_UNSUPPORTED
        elif reg_idx == UartModule.RegIdx.TX_FULL:
            # TX_FULL: read only
            return AccessResult.ERROR_UNSUPPORTED
        elif reg_idx == UartModule.RegIdx.TX_DATA:
            # TX_DATA: write to stdout
            char = chr(data)
            self._stdout.append(char)
            print(char, end="")
            if self._log_file_path is not None:
                with open(self._log_file_path, "a") as f:
                    f.write(char)
            return AccessResult.OK
        else:
            assert False, f"Invalid register index: {reg_idx}"
            return AccessResult.ERROR_OUT_OF_RANGE

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
    start_addr: MemSpace.AbstAddrType

    @property
    def end_addr(self) -> MemSpace.AbstAddrType:
        return self.start_addr + self.slave.size - 1

    @property
    def size(self) -> int:
        return self.slave.size

    def is_in_range(self, addr: MemSpace.AbstAddrType) -> bool:
        return self.start_addr <= addr <= self.end_addr


class BusArbiter(BusSlave):
    """
    Bus Slaveを複数持ち、アドレス空間ごとにアクセスを振り分けるクラス
    """

    def __init__(self, space: MemSpace, name: str, entries: List[BusArbiterEntry]):
        self.space = space
        self.name = name
        # 登録されたslaveのRangeからサイズを算出
        self.min_addr = min(slave.start_addr for slave in entries)
        self.max_addr = max(slave.end_addr for slave in entries)
        self.size = self.max_addr - self.min_addr + 1
        assert self.size > 0, "Invalid address range"
        # Overwrapのチェック
        for idx, entry in enumerate(entries):
            for other_entry in entries[idx + 1 :]:
                assert not (
                    entry.start_addr <= other_entry.start_addr
                    and entry.end_addr >= other_entry.start_addr
                ), f"Overwrap detected: {entry=}, {other_entry=}"

        self._entries = list(entries)

        super().__init__(space)

    def name(self) -> str:
        return self.name

    def size(self) -> int:
        return self.size

    def read(
        self,
        addr: MemSpace.AbstAddrType,
        byteenable: MemSpace.AbstByteEnType | None = None,
        access_type: AccessType = AccessType.NORMAL,
    ) -> (AccessResult, MemSpace.AbstDataType):
        for entry in self._entries:
            if entry.is_in_range(addr):
                return entry.slave.read(
                    addr - entry.start_addr, byteenable, access_type
                )
        return AccessResult.ERROR_OUT_OF_RANGE, 0

    def write(
        self,
        addr: MemSpace.AbstAddrType,
        data: MemSpace.AbstDataType,
        byteenable: MemSpace.AbstByteEnType | None = None,
        access_type: AccessType = AccessType.NORMAL,
    ) -> AccessResult:
        for entry in self._entries:
            if entry.is_in_range(addr):
                return entry.slave.write(
                    addr - entry.start_addr, data, byteenable, access_type
                )
        return AccessResult.ERROR_OUT_OF_RANGE

    def add_slave(self, slave: BusArbiterEntry) -> None:
        self._entries.append(slave)

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
            dump_file_path = f"{dump_base_path}_{idx:04d}_{entry.slave.name()}.{format}"
            entry.slave.dump(
                dump_file_path, format, offset_addr=offset_addr + entry.start_addr
            )
