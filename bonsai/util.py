from amaranth.back import verilog
from amaranth.lib import wiring

import config


def export_verilog_file(component: wiring.Component, name: str):
    """
    Convert a wiring.Component to a Verilog file
    """
    with open(config.dist_file_path(f"{name}.v"), "w") as f:
        f.write(verilog.convert(component))
