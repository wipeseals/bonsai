from typing import Callable
from amaranth.sim import Simulator
from amaranth.lib import wiring

from bonsai import config


def run_sim(name: str, dut: wiring.Component, testbench: Callable):
    """
    Run a testbench on a DUT.
    Args:
        name (str): The name of the test.
        dut (wiring.Component): The device under test.
        testbench (Callable): The testbench function.
    """
    sim = Simulator(dut)
    sim.add_clock(1)
    sim.add_testbench(testbench)
    with sim.write_vcd(config.dist_file_path(f"{name}.vcd")):
        sim.run()
