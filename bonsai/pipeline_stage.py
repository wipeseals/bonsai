from amaranth import Module, Signal
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

from log import Kanata
from pipeline_ctrl import (
    InstFetchReqSignature,
    InstSelectReqSignature,
)
import config
import util


class InstSelectStage(wiring.Component):
    """
    Instruction (Address) Select Stage
    """

    # Instruction Select Request
    prev_req: In(InstSelectReqSignature())

    # Instruction Fetch Request
    next_req: Out(InstFetchReqSignature().flip())

    def __init__(self, initial_pc: int = 0, initial_uniq_id: int = 0, lane_id: int = 0):
        self._initial_pc = initial_pc
        self._initial_uniq_id = initial_uniq_id
        self._lane_id = lane_id
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        # local signals
        pc = Signal(config.ADDR_SHAPE, reset=self._initial_pc)
        uniq_id = Signal(config.ADDR_SHAPE, reset=self._initial_uniq_id)
        next_req_sig = InstFetchReqSignature().create()
        valid_prev_cycle = Signal(1, reset=0)

        # log (IS stage end)
        with m.If(valid_prev_cycle):
            m.d.sync += Kanata.end_stage(
                uniq_id=next_req_sig.locate.uniq_id, lane_id=self._lane_id, stage="IS"
            )

        # default next state
        m.d.sync += [
            # keep pc
            pc.eq(pc),
            next_req_sig.locate.pc.eq(pc),
            # keep uniq_id
            uniq_id.eq(uniq_id),
            next_req_sig.locate.uniq_id.eq(uniq_id),
            # pass request
            next_req_sig.common_req.flush.eq(self.prev_req.common_req.flush),
            next_req_sig.common_req.stall.eq(self.prev_req.common_req.stall),
            next_req_sig.locate.num_inst_bytes.eq(self.prev_req.num_inst_bytes),
            # invalid current cycle
            valid_prev_cycle.eq(0),
        ]

        # main logic
        with m.If(self.prev_req.common_req.flush):
            # Flush Request
            m.d.sync += [
                # reset pc
                pc.eq(self._initial_pc),
                next_req_sig.locate.pc.eq(self._initial_pc),
            ]
        with m.Else():
            with m.If(self.prev_req.common_req.stall):
                # Stall Request
                pass
            with m.Else():
                with m.If(self.prev_req.branch_req.en):
                    # Branch Request
                    m.d.sync += [
                        # set branch target pc
                        pc.eq(
                            self.prev_req.branch_req.next_pc
                            + self.prev_req.num_inst_bytes
                        ),
                        next_req_sig.locate.pc.eq(self.prev_req.branch_req.next_pc),
                        # increment uniq_id
                        uniq_id.eq(uniq_id + 1),
                        next_req_sig.locate.uniq_id.eq(uniq_id),
                    ]
                with m.Else():
                    # Increment PC
                    m.d.sync += [
                        # increment pc
                        pc.eq(pc + self.prev_req.num_inst_bytes),
                        next_req_sig.locate.pc.eq(pc),
                        # increment uniq_id
                        uniq_id.eq(uniq_id + 1),
                        next_req_sig.locate.uniq_id.eq(uniq_id),
                    ]
                    # log (cmd start, IS stage start)
                    m.d.sync += [
                        # valid current cycle
                        valid_prev_cycle.eq(1),
                        # log
                        Kanata.start_cmd(uniq_id=uniq_id),
                        Kanata.start_stage(
                            uniq_id=uniq_id, lane_id=self._lane_id, stage="IS"
                        ),
                        Kanata.label_cmd_is(
                            uniq_id=uniq_id, label_type=Kanata.LabelType.ALWAYS, pc=pc
                        ),
                    ]

        return m


if __name__ == "__main__":
    stages = [
        InstSelectStage(),
    ]
    for stage in stages:
        util.export_verilog_file(stage, f"{stage.__class__.__name__}")
