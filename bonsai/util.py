from amaranth.back import verilog
from amaranth.lib import wiring

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


def export_verilog_file(component: wiring.Component, name: str):
    """
    Convert a wiring.Component to a Verilog file
    """
    with open(config.dist_file_path(f"{name}.v"), "w") as f:
        f.write(verilog.convert(component))
