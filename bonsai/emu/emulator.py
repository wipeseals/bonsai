import argparse
import enum
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

from elftools.elf.constants import P_FLAGS
from elftools.elf.elffile import ELFFile
from rich import print

from bonsai.emu.core import Core, CoreConfig
from bonsai.emu.mem import (
    BusArbiter,
    BusArbiterEntry,
    FixSizeRam,
    FixSizeRom,
    UartModule,
)


class RegionFlag(enum.Flag):
    EXECUTABLE = enum.auto()
    WRITABLE = enum.auto()
    READABLE = enum.auto()

    @classmethod
    def from_p_flags(cls, flags: int) -> "RegionFlag":
        dst = cls(0)
        if flags & P_FLAGS.PF_X:
            dst |= cls.EXECUTABLE
        if flags & P_FLAGS.PF_W:
            dst |= cls.WRITABLE
        if flags & P_FLAGS.PF_R:
            dst |= cls.READABLE
        return dst


@dataclass
class MemoryMap:
    name: str
    region: RegionFlag
    phys_addr: int
    file_size: int
    mem_size: int
    align: int
    data: bytes = b""

    def __repr__(self) -> str:
        return (
            f"MemoryMap("
            f"name='{self.name}', "
            f"region={self.region}, "
            f"phys_addr={hex(self.phys_addr)}, "
            f"file_size={hex(self.file_size)}, "
            f"mem_size={hex(self.mem_size)}, "
            f"align={hex(self.align)}"
            f")"
        )

    @classmethod
    def from_elffile(cls, elffile: ELFFile) -> List["MemoryMap"]:
        dst = []
        for segment, section in zip(elffile.iter_segments(), elffile.iter_sections()):
            logging.debug(f"type: {segment['p_type']} name: {section.name} {segment}")
            if not segment["p_type"] == "PT_LOAD":
                continue
            dst.append(
                cls(
                    name=section.name,
                    region=RegionFlag.from_p_flags(segment["p_flags"]),
                    phys_addr=segment["p_paddr"],
                    file_size=segment["p_filesz"],
                    mem_size=segment["p_memsz"],
                    align=segment["p_align"],
                    data=segment.data(),
                )
            )
        return dst


@dataclass
class EmulatorBootInfo:
    entry_point_addr: int
    uart_start_addr: int
    segments: List[MemoryMap]

    @classmethod
    def from_elffile(
        cls, elffile: ELFFile, uart_start_addr: int = 0x0100_0000
    ) -> "EmulatorBootInfo":
        return cls(
            entry_point_addr=elffile.header["e_entry"],
            uart_start_addr=uart_start_addr,
            segments=MemoryMap.from_elffile(elffile),
        )

    @classmethod
    def from_file(
        cls, elf_path: str, uart_start_addr: int = 0x0100_0000
    ) -> "EmulatorBootInfo":
        with open(elf_path, "rb") as f:
            elffile = ELFFile(f)
            return cls.from_elffile(elffile)

    def describe(self) -> str:
        dst = "# EmulatorBootInfo\n"
        dst += f" - entry_point_addr : 0x{self.entry_point_addr:016x}\n"
        dst += f" - uart_start_addr  : 0x{self.uart_start_addr:016x}\n"
        dst += f" - {len(self.segments)} segments\n"
        for i, segment in enumerate(self.segments):
            dst += f"  - segment {i}: {segment}\n"
        return dst


class Emulator:
    @classmethod
    def create_dst_path(cls, file_name: str, dist_file_dir: str) -> str:
        """
        Get the path of the generated file
        """
        Path(dist_file_dir).mkdir(parents=True, exist_ok=True)
        return str(Path(dist_file_dir) / file_name)

    @classmethod
    def run(cls, bootinfo: EmulatorBootInfo) -> None:
        logging.info(bootinfo.describe())

        ##################################################################################
        # Create the peripherals
        entries: List[BusArbiterEntry] = []

        # UART
        entries.append(
            BusArbiterEntry(
                slave=UartModule(
                    name="uart0",
                    log_file_path=cls.create_dst_path("uart0.log", "dist_emu"),
                ),
                start_addr=bootinfo.uart_start_addr,
            )
        )
        # RAM or ROM
        for i, segment in enumerate(bootinfo.segments):
            mem = (
                FixSizeRam(
                    name=f"ram{i}_{segment.name}",
                    size=segment.mem_size,
                    init_data=segment.data,
                )
                if segment.region & RegionFlag.WRITABLE
                else FixSizeRom(
                    name=f"rom{i}_{segment.name}",
                    size=segment.mem_size,
                    init_data=segment.data,
                )
            )
            # append to bus entries
            entries.append(
                BusArbiterEntry(
                    slave=mem,
                    start_addr=segment.phys_addr,
                )
            )

        # Main Bus
        bus0 = BusArbiter(
            name="bus0",
            entries=entries,
        )
        logging.info(bus0.describe())

        # RISCV-Core
        core = Core(config=CoreConfig(init_pc=bootinfo.entry_point_addr), slave=bus0)
        core.reset()
        # TODO: Implement the emulator
        for _ in range(100):
            core.step()

    @classmethod
    def main(cls, args: argparse.Namespace) -> None:
        # Read the program binary
        print(f"Loading {args.elf_path}...")
        bootinfo = EmulatorBootInfo.from_file(
            elf_path=args.elf_path, uart_start_addr=args.uart_start_addr
        )
        cls.run(bootinfo)

    @classmethod
    def setup_parser(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """
        Add the build command to the parser
        """
        parser.add_argument(
            "elf_path",
            type=str,
            help="Set the path of the ELF file to be loaded",
        )
        parser.add_argument(
            "--uart_start_addr",
            type=int,
            default=0x0100_0000,
            help="Set the start address of the UART",
        )
        parser.add_argument(
            "--dist-file-dir",
            default="dist_emu",
            help="Set the directory for emulator output files",
        )
        parser.set_defaults(func=cls.main)
        return parser
