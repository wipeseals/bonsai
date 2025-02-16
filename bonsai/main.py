import argparse
import logging

from rtl.builder import RtlBuild
from sim.simulator import RtlSim


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level",
    )

    # subparserのコマンドでsubpackageのparserを追加
    subparsers = parser.add_subparsers(
        dest="action", help="Select the action to perform", required=True
    )
    RtlBuild.setup_parser(subparsers.add_parser("build", help="Build the project"))
    RtlSim.setup_parser(subparsers.add_parser("sim", help="Run the simulator"))

    args = parser.parse_args()
    logging.basicConfig(level=args.log_level)
    args.func(args)


if __name__ == "__main__":
    main()
