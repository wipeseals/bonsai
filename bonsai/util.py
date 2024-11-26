from amaranth.back import verilog
from amaranth.lib import wiring


def export_verilog_file(component: wiring.Component, name: str):
    """
    Convert a wiring.Component to a Verilog file
    """
    with open(f"{name}.v", "w") as f:
        f.write(verilog.convert(component))
