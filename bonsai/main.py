import argparse
import logging
from typing import Dict, List, Optional

import util
from amaranth import Elaboratable
from amaranth.build.plat import Platform
from amaranth_boards.arty_a7 import ArtyA7_35Platform
from amaranth_boards.tang_nano_9k import TangNano9kPlatform
from periph.timer import Timer
from periph.uart import UartConfig, UartRx, UartTx
from periph.video import VgaConfig, VgaOut
from top import Top

SUPPORT_DEVICES: Dict[str, Platform] = {
    "arty": ArtyA7_35Platform(),
    "tangnano9k": TangNano9kPlatform(),
}


def build(args: argparse.Namespace) -> None:
    platform: Optional[Platform] = SUPPORT_DEVICES.get(args.platform, None)

    if platform is not None:
        logging.info(
            f"Building for {platform.__class__.__name__}, do_build={not args.skip_build}, do_program={not args.skip_program}"
        )
        platform.build(
            Top(),
            do_build=not args.skip_build,
            do_program=not args.skip_program,
        )
    else:
        if args.skip_build:
            logging.warning("No platform selected, skipping build")
            return

        logging.info("Generating Verilog files for all components")

        # TODO: tangnano9k 以外
        target_platform = None
        clk_freq = 27e6

        target_components: List[Elaboratable] = [
            Timer(clk_freq=clk_freq, default_period_seconds=1.0),
            UartTx(config=UartConfig.from_freq(clk_freq=clk_freq)),
            UartRx(config=UartConfig.from_freq(clk_freq=clk_freq)),
            VgaOut(VgaConfig.preset_tangnano9k_800x480()),
        ]
        for component in target_components:
            filename = f"{component.__class__.__name__}"
            logging.info(f"Generating {filename}")
            util.export(
                component=component,
                name=filename,
                platform=target_platform,
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
        choices=[""] + list(SUPPORT_DEVICES.keys()),
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

    args = parser.parse_args()
    logging.basicConfig(level=args.log_level)
    args.func(args)


if __name__ == "__main__":
    main()
