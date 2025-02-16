import argparse
from pathlib import Path

from bonsai.emu.mem import BusArbiter, BusArbiterEntry, FixSizeRam, MemSpace, UartModule


class Emulator:
    @classmethod
    def create_dst_path(cls, file_name: str, dist_file_dir: str) -> str:
        """
        Get the path of the generated file
        """
        Path(dist_file_dir).mkdir(parents=True, exist_ok=True)
        return str(Path(dist_file_dir) / file_name)

    @classmethod
    def run(cls, args: argparse.Namespace) -> None:
        """
        Run the emulator
        """

        mem_space = MemSpace(addr_bits=args.addr_width, data_bits=args.data_width)
        uart0 = UartModule(
            space=mem_space,
            name="uart0",
            log_file_path=cls.create_dst_path("uart0.log", args.dist_file_dir),
        )

        # Main Program Memory
        program_data = (
            Path(args.program_binary_path).read_bytes()
            if args.program_binary_path
            else b""
        )
        ram0 = FixSizeRam(
            space=mem_space, name="ram0", size=args.ram_size, init_data=program_data
        )

        # Main Bus
        bus0 = BusArbiter(
            space=mem_space,
            name="bus0",
            entries=[
                # RAM
                BusArbiterEntry(slave=ram0, start_addr=args.ram_start_addr),
                # Peripherals
                BusArbiterEntry(slave=uart0, start_addr=args.uart_start_addr),
            ],
        )
        print(bus0)
        # test print uart
        for c in "Hello, World!\n":
            bus0.write32(
                args.uart_start_addr
                + (UartModule.RegIdx.TX_DATA * mem_space.num_data_bytes),
                ord(c),
            )

        # TODO: Implement the emulator

    @classmethod
    def setup_parser(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """
        Add the build command to the parser
        """
        parser.add_argument(
            "--addr-width",
            type=int,
            default=32,
            help="Set the address width",
        )
        parser.add_argument(
            "--data-width",
            type=int,
            default=32,
            help="Set the data width",
        )
        parser.add_argument(
            "--ram_start_addr",
            type=int,
            default=0x8000_0000,
            help="Set the start address of the RAM",
        )
        parser.add_argument(
            "--ram_size",
            type=int,
            default=64 * 1024,  # 64KB
            help="Set the size of the RAM",
        )
        parser.add_argument(
            "--uart_start_addr",
            type=int,
            default=0x0100_0000,
            help="Set the start address of the UART",
        )
        parser.add_argument(
            "--program-binary-path",
            type=str,
            help="Set the path to the program binary",
        )

        parser.add_argument(
            "--dist-file-dir",
            default="dist_emu",
            help="Set the directory for emulator output files",
        )
        parser.set_defaults(func=cls.run)
        return parser
