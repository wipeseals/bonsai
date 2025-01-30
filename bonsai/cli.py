import argparse
import os

import util
from top import Top


def generate_all_verilog_files() -> None:
    """
    Generate all verilog files
    """
    target_components = [
        Top(),
    ]
    for component in target_components:
        util.export_verilog_file(component, f"{component.__class__.__name__}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="Your name")
    parser.add_argument(
        "--generate-all", action="store_true", help="Generate all Verilog files"
    )
    args = parser.parse_args()

    if args.generate_all:
        generate_all_verilog_files()
    else:
        print(f"TODO: implement. args={args}")


if __name__ == "__main__":
    main()
