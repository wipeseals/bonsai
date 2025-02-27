import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

from elftools.elf.constants import SH_FLAGS
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


@dataclass
class MemorySegment:
    section_name: str
    type: str
    offset: int
    virt_addr: int
    phys_addr: int
    file_size: int
    mem_size: int
    flags: int
    align: int
    data: bytes = b""

    def __repr__(self) -> str:
        return (
            f"ProgramHeader("
            f"section_name='{self.section_name}', "
            f"type='{self.type}', "
            f"offset={hex(self.offset)}, "
            f"virt_addr={hex(self.virt_addr)}, "
            f"phys_addr={hex(self.phys_addr)}, "
            f"file_size={hex(self.file_size)}, "
            f"mem_size={hex(self.mem_size)}, "
            f"flags={hex(self.flags)}, "
            f"align={hex(self.align)}"
            f")"
        )

    @classmethod
    def from_elffile(cls, elffile: ELFFile) -> List["MemorySegment"]:
        dst = []
        for segment, section in zip(elffile.iter_segments(), elffile.iter_sections()):
            dst.append(
                cls(
                    section_name=section.name,
                    type=segment["p_type"],
                    offset=segment["p_offset"],
                    virt_addr=segment["p_vaddr"],
                    phys_addr=segment["p_paddr"],
                    file_size=segment["p_filesz"],
                    mem_size=segment["p_memsz"],
                    flags=segment["p_flags"],
                    align=segment["p_align"],
                    data=segment.data(),
                )
            )
        return dst


@dataclass
class EmulatorBootInfo:
    entry_point_addr: int
    uart_start_addr: int
    segments: List[MemorySegment]

    @classmethod
    def from_elffile(
        cls, elffile: ELFFile, uart_start_addr: int = 0x0100_0000
    ) -> "EmulatorBootInfo":
        return cls(
            entry_point_addr=elffile.header["e_entry"],
            uart_start_addr=uart_start_addr,
            segments=MemorySegment.from_elffile(elffile),
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
            if segment.type == "PT_LOAD":
                # select write or read only
                is_writable = (segment.flags & SH_FLAGS.SHF_WRITE) != 0
                mem = (
                    FixSizeRam(
                        name=f"ram{i}",
                        size=segment.mem_size,
                        init_data=segment.data,
                    )
                    if is_writable
                    else FixSizeRom(
                        name=f"rom{i}",
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
