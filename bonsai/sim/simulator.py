import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from amaranth.lib import wiring
from amaranth.sim import Period, Simulator


class _Tee:
    """
    Duplicate output to multiple files
    """

    def __init__(self, *files):
        self.files = files

    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()  # Ensure the output is written immediately

    def flush(self):
        for f in self.files:
            f.flush()


@dataclass
class RtlSim:
    """
    The result of simulation
    """

    name: str
    log_path: str
    vcd_path: str

    @staticmethod
    def create_dst_path(file_name: str, dist_file_dir: str) -> str:
        """
        Get the path of the generated file
        """
        Path(dist_file_dir).mkdir(parents=True, exist_ok=True)
        return str(Path(dist_file_dir) / file_name)

    @classmethod
    def run(
        cls,
        name: str,
        dut: wiring.Component,
        testbench: Callable,
        clock: float = 100e6,
        setup_f: Optional[Callable[[Simulator], None]] = None,
        dist_file_dir: str = "dist_sim",
    ) -> "RtlSim":
        """
        Run a testbench on a DUT.
        Args:
            name (str): The name of the test.
            dut (wiring.Component): The device under test.
            testbench (Callable): The testbench function.
            clock (float): The main clock frequency.
            setup_f (Optional[Callable[Simulator]]): The setup function.

        Returns:
            str: The path to the log file.
        """
        sim = Simulator(dut)
        sim.add_clock(Period(Hz=clock))
        sim.add_testbench(testbench)
        if setup_f is not None:
            setup_f(sim)

        log_path = cls.create_dst_path(f"{name}.log", dist_file_dir=dist_file_dir)
        vcd_path = cls.create_dst_path(f"{name}.vcd", dist_file_dir=dist_file_dir)
        gtkw_path = cls.create_dst_path(f"{name}.gtkw", dist_file_dir=dist_file_dir)
        try:
            with sim.write_vcd(vcd_path, gtkw_file=gtkw_path):
                # Redirect stdout to a file
                origin_stdout = sys.stdout
                with open(log_path, "w", encoding="utf-8") as f:
                    sys.stdout = _Tee(origin_stdout, f)
                    sim.run()
        finally:
            sys.stdout = origin_stdout

        return cls(name=name, log_path=log_path, vcd_path=vcd_path)

    @staticmethod
    def setup_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """
        Add arguments to the parser
        """
        parser.set_defaults(
            func=lambda args: print(
                "Currently, the simulation is implemented to run as a scenario on pytest. Please run it with `uv run test`."
            )
        )
        return parser
