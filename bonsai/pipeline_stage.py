from amaranth import Module, Signal
from amaranth.lib import wiring, memory
from amaranth.lib.wiring import In, Out

from log import Kanata
from pipeline_ctrl import BranchReq, FlushReq, InstFetchData, InstSelectReq, StallReq
import config
import util


class InstSelectStage(wiring.Component):
    """
    Instruction Select Stage
    """

    # Instruction Select Request
    req: In(InstSelectReq)

    # Instruction Fetch Request
    if_req: Out(InstFetchData)

    def __init__(self, initial_pc: int = 0):
        self._pc = initial_pc
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        # for Output Signal
        pc = Signal(config.PC_SHAPE, reset=self._pc)
        uniq_id = Signal(config.UNIQ_ID_SHAPE, reset=0)
        stall_req = Signal(StallReq, reset=1)
        flush_req = Signal(FlushReq, reset=1)
        m.d.comb += [
            self.if_req.pc.eq(pc),
            self.if_req.uniq_id.eq(uniq_id),
            self.if_req.stall_req.eq(stall_req),
            self.if_req.flush_req.eq(flush_req),
        ]

        with m.If(self.flush_req.en):
            # Flush Request
            m.d.sync += [
                pc.eq(0),
                uniq_id.eq(0),
                stall_req.eq(1),
                flush_req.eq(1),
            ]
        with m.Else():
            with m.If(self.stall_req.en):
                # Stall Request
                m.d.sync += [
                    pc.eq(0),
                    uniq_id.eq(0),
                    stall_req.eq(1),
                    flush_req.eq(0),
                ]
            with m.Else():
                # 分岐必要なら指定されたPCに移動。そうでなければ現在地をそのまま出力
                with m.If(self.branch_req.en):
                    # Branch Request
                    m.d.sync += [
                        pc.eq(self.branch_req.next_pc),
                        uniq_id.eq(uniq_id + 1),
                        stall_req.eq(0),
                        flush_req.eq(0),
                    ]
                with m.Else():
                    # Increment PC
                    m.d.sync += [
                        pc.eq(pc + 1),
                        uniq_id.eq(uniq_id + 1),
                        stall_req.eq(0),
                        flush_req.eq(0),
                    ]


if __name__ == "__main__":
    stages = [
        InstSelectStage(),
    ]
    for stage in stages:
        util.export_verilog_file(stage, f"{stage.__class__.__name__}")
