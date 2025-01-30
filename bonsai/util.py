from amaranth.back import verilog
from amaranth.lib.wiring import Component

import config


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


def export_verilog_file(component: Component, name: str):
    """
    Convert a wiring.Component to a Verilog file
    """
    with open(config.dist_file_path(f"{name}.v"), "w") as f:
        f.write(verilog.convert(component))
