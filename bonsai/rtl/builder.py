import argparse
import copy
import logging
from pathlib import Path
from typing import Dict, List, Optional

from amaranth import Elaboratable
from amaranth.back import cxxrtl, verilog
from amaranth.build.plat import Platform
from amaranth.lib.wiring import Component
from amaranth_boards.tang_nano_9k import TangNano9kPlatform
from rtl.periph.spi import SpiConfig, SpiMaster
from rtl.periph.timer import Timer
from rtl.periph.uart import UartConfig, UartRx, UartTx
from rtl.periph.video import VgaConfig, VgaOut
from rtl.top import Top

SUPPORT_DEVICES: Dict[str, Platform] = {
    "tangnano9k": TangNano9kPlatform(),
}


class RtlBuild:
    @staticmethod
    def create_dst_path(file_name: str, dist_file_dir: str) -> str:
        """
        Generate a file path for the dist directory
        """
        Path(dist_file_dir).mkdir(parents=True, exist_ok=True)
        return str(Path(dist_file_dir) / file_name)

    @classmethod
    def export(
        cls,
        component: Component,
        name: str,
        dist_file_dir: str = "dist_rtl",
        platform: Optional[Platform] = None,
    ) -> None:
        """
        Convert a wiring.Component to a Verilog file
        """
        verilog_path = cls.create_dst_path(f"{name}.v", dist_file_dir=dist_file_dir)
        cxx_path = cls.create_dst_path(f"{name}.cpp", dist_file_dir=dist_file_dir)

        # platform は一度requestしたresouceを再取得できないようにしているのでcloneして実行
        Path(verilog_path).write_text(
            verilog.convert(component, name=name, platform=copy.deepcopy(platform))
        )
        Path(cxx_path).write_text(
            cxxrtl.convert(component, name=name, platform=copy.deepcopy(platform))
        )

    @classmethod
    def main(cls, args: argparse.Namespace) -> None:
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
                SpiMaster(SpiConfig(system_clk_freq=clk_freq, sclk_freq=10e6)),
            ]
            for component in target_components:
                filename = f"{component.__class__.__name__}"
                logging.info(f"Generating {filename}")
                cls.export(
                    component=component,
                    name=filename,
                    platform=target_platform,
                    dist_file_dir=args.dist_file_dir,
                )

    @classmethod
    def setup_parser(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        parser.add_argument(
            "--platform",
            default="",
            choices=[""] + list(SUPPORT_DEVICES.keys()),
            help="Set the target platform",
        )
        parser.add_argument(
            "--skip-build",
            action="store_true",
            help="Build the project",
        )
        parser.add_argument(
            "--skip-program",
            action="store_true",
            help="Program the project",
        )
        parser.add_argument(
            "--dist-file-dir",
            default="dist_rtl",
            help="The directory to store RTL files",
        )
        parser.set_defaults(func=cls.main)
        return parser
