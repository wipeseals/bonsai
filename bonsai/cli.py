import argparse
import logging

import util
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
        logging.info(f"Generating {filename}.v")
        util.export_verilog_file(
            component=component,
            name=filename,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level",
    )

    parser.add_argument("--name", help="Your name")
    parser.add_argument(
        "--generate-all", action="store_true", help="Generate all Verilog files"
    )

    # Parse
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))

    if args.generate_all:
        generate_all_verilog_files()
    else:
        print(f"TODO: implement. args={args}")


if __name__ == "__main__":
    main()
