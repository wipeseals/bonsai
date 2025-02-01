import argparse
import logging

import util
from amaranth_boards.arty_a7 import ArtyA7_35Platform
from amaranth_boards.test.blinky import Blinky
from top import Top
from tqdm import tqdm


def generate_all_verilog_files() -> None:
    """
    Generate all verilog files
    """
    target_components = [
        Top(),
    ]
    for component in tqdm(
        target_components, desc="Generating Verilog files", unit="file"
    ):
        filename = f"{component.__class__.__name__}"
        logging.debug(f"Generating {filename}.v")
        util.export_verilog_file(
            component=component,
            name=filename,
        )


def test_arty_a7_35_platform() -> None:
    ArtyA7_35Platform().build(Blinky(), do_build=True, do_program=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log-level",
        default="DEBUG",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level",
    )

    parser.add_argument("--name", help="Your name")
    parser.add_argument(
        "--generate-all", action="store_true", help="Generate all Verilog files"
    )
    parser.add_argument(
        "--test-arty", action="store_true", help="Test Arty A7-35 platform"
    )

    # Parse
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))

    if args.generate_all:
        generate_all_verilog_files()
    elif args.test_arty:
        test_arty_a7_35_platform()
    else:
        print(f"TODO: implement. args={args}")


if __name__ == "__main__":
    main()
