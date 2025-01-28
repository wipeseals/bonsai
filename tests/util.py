from typing import Callable
from amaranth.sim import Simulator
from amaranth.lib import wiring

from bonsai import config

import sys


class Tee:
    def __init__(self, *files):
        self.files = files

    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()  # Ensure the output is written immediately

    def flush(self):
        for f in self.files:
            f.flush()


def run_sim(name: str, dut: wiring.Component, testbench: Callable) -> str:
    """
    Run a testbench on a DUT.
    Args:
        name (str): The name of the test.
        dut (wiring.Component): The device under test.
        testbench (Callable): The testbench function.

    Returns:
        str: The path to the log file.
    """
    sim = Simulator(dut)
    sim.add_clock(10e-6)  # 10ns=100MHz
    sim.add_testbench(testbench)

    log_path = config.dist_file_path(f"{name}.log")
    try:
        with sim.write_vcd(config.dist_file_path(f"{name}.vcd")):
            # Redirect stdout to a file
            origin_stdout = sys.stdout
            with open(log_path, "w", encoding="utf-8") as f:
                sys.stdout = Tee(origin_stdout, f)
                sim.run()
    finally:
        sys.stdout = origin_stdout

    return log_path
