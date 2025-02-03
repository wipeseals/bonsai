import os
import sys
from functools import reduce
from typing import Callable, Optional

from amaranth.back import verilog
from amaranth.lib import wiring
from amaranth.lib.wiring import Component
from amaranth.sim import Simulator
from pydantic.dataclasses import dataclass


def byte_width(width: int) -> int:
    """
    Convert bit width to byte width
    e.g.
        1bit -> 1byte
        8bit -> 1byte
        16bit -> 2byte
        32bit -> 4byte
        64bit -> 8byte
        65bit -> 9byte
    """
    return (width + 7) // 8


def is_power_of_2(n: int) -> bool:
    """
    Check if n is a power of 2

    0x400 & 0x3FF == 0 (2^10) のような1つ低い値とのビットANDが1bitだけになることを利用
    """
    return n != 0 and (n & (n - 1)) == 0


def even_parity(data: int, data_width: int) -> int:
    """
    Python上の計算でパリティビットを求める (奇数パリティ)
    """
    return reduce(lambda x, y: x ^ y, [data >> i & 1 for i in range(data_width)])


def odd_parity(data: int, data_width: int) -> int:
    """
    Python上の計算でパリティビットを求める (偶数パリティ)
    """
    return 1 - even_parity(data, data_width)


class Tee:
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


def generate_dist_file_path(file_name: str, dist_file_dir: str = "dist") -> str:
    """
    Get the path of the generated file
    """

    if not os.path.exists(dist_file_dir):
        os.makedirs(dist_file_dir)
    return f"{dist_file_dir}/{file_name}"


def export_verilog_file(
    component: Component, name: str, dist_file_dir: str = "dist"
) -> None:
    """
    Convert a wiring.Component to a Verilog file
    """
    filepath = generate_dist_file_path(f"{name}.v")
    with open(filepath, "w") as f:
        f.write(verilog.convert(component))


@dataclass
class Simulation:
    """
    The result of simulation
    """

    name: str
    log_path: str
    vcd_path: str

    @classmethod
    def run(
        cls,
        name: str,
        dut: wiring.Component,
        testbench: Callable,
        clock: float = 100e6,
        setup_f: Optional[Callable[[Simulator], None]] = None,
    ) -> "Simulation":
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
        sim.add_clock(clock)
        sim.add_testbench(testbench)
        if setup_f is not None:
            setup_f(sim)

        log_path = generate_dist_file_path(f"{name}.log")
        vcd_path = generate_dist_file_path(f"{name}.vcd")
        try:
            with sim.write_vcd(vcd_path):
                # Redirect stdout to a file
                origin_stdout = sys.stdout
                with open(log_path, "w", encoding="utf-8") as f:
                    sys.stdout = Tee(origin_stdout, f)
                    sim.run()
        finally:
            sys.stdout = origin_stdout

        return cls(name=name, log_path=log_path, vcd_path=vcd_path)
