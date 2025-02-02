import argparse
import logging
from typing import List

import util
from amaranth import Elaboratable
from amaranth.build.plat import Platform
from amaranth_boards.arty_a7 import ArtyA7_35Platform
from lib.timer import Timer
from top import PlatformTop, Top


def build(args: argparse.Namespace) -> None:
    platform: Platform = None
    if args.platform == "arty":
        platform = ArtyA7_35Platform()
    else:
        logging.warning(f"Unsupported platform: {args.platform}")

    if platform is not None:
        logging.info(
            f"Building for {platform.__class__.__name__}, do_build={not args.skip_build}, do_program={not args.skip_program}"
        )
        platform.build(
            PlatformTop(),
            do_build=not args.skip_build,
            do_program=not args.skip_program,
        )
    else:
        if args.skip_build:
            logging.warning("No platform selected, skipping build")
            return

        logging.info("Generating Verilog files for all components")
        target_components: List[Elaboratable] = [
            Top(clk_freq=100e6, period_sec=1.0),
            Timer(clk_freq=100e6, default_period_seconds=1.0),
        ]
        for component in target_components:
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

    subparsers = parser.add_subparsers(
        dest="action", help="Select the action to perform", required=True
    )
    parser_build = subparsers.add_parser("build", help="build the project")
    parser_build.add_argument(
        "--platform",
        default="",
        choices=["", "arty"],
        help="Set the target platform",
    )
    parser_build.add_argument(
        "--skip-build",
        action="store_true",
        help="Build the project",
    )
    parser_build.add_argument(
        "--skip-program",
        action="store_true",
        help="Program the project",
    )
    parser_build.set_defaults(func=build)

    # parse & run
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level)
    args.func(args)


if __name__ == "__main__":
    main()
