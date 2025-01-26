from enum import Flag, auto
from amaranth import Module, Signal, unsigned
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

from log import Kanata
from format import (
    AbortType,
    InstFetchReqSignature,
    InstSelectReqSignature,
    StageCtrlReqSignature,
)
import config
import util


class PrintFlag(Flag):
    """
    Kanata Print Option
    """

    HEADER = auto()
    ELAPLED_CYC = auto()
    STAGE = auto()

    @classmethod
    def none(cls):
        return 0

    @classmethod
    def all(cls):
        return cls.HEADER | cls.ELAPLED_CYC | cls.STAGE


class InstSelectStage(wiring.Component):
    """
    Instruction (Address) Select Stage
    """

    # Stage Control Request
    ctrl_req_in: In(StageCtrlReqSignature())

    # Instruction Select Request
    req_in: In(InstSelectReqSignature())

    # Instruction Fetch Request
    req_out: Out(InstFetchReqSignature())

    ###########################################
    # Debug Signals

    # global cycle counter
    global_cyc: Out(config.CYCLE_COUNTER_SHAPE)
    # branch strobe (for debug)
    branch_strobe: Out(unsigned(1))
    # branch strobe address (for debug)
    branch_strobe_src_addr: Out(config.ADDR_SHAPE)
    branch_strobe_dst_addr: Out(config.ADDR_SHAPE)

    def __init__(
        self,
        initial_pc: int = 0,
        initial_uniq_id: int = 0,
        lane_id: int = 0,
        print_flag: PrintFlag = PrintFlag.all(),
        num_inst_bytes: int = config.NUM_INST_BYTE,
    ):
        self._initial_pc = initial_pc
        self._initial_uniq_id = initial_uniq_id
        self._lane_id = lane_id
        self._print_flag = print_flag
        self._num_inst_bytes = num_inst_bytes
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        # local signals
        pc = Signal(config.ADDR_SHAPE, init=self._initial_pc)
        uniq_id = Signal(config.CMD_UNIQ_ID_SHAPE, init=self._initial_uniq_id)
        cyc = Signal(config.CYCLE_COUNTER_SHAPE, init=0)
        abort_type = Signal(AbortType, init=AbortType.NONE)

        # assign
        m.d.comb += [
            self.global_cyc.eq(cyc),
        ]

        # log (initial header)
        with m.If(cyc == 0):
            if PrintFlag.HEADER in self._print_flag:
                # header + start cycle
                m.d.sync += [
                    Kanata.header(),
                    Kanata.start_cyc(cycle=cyc),
                ]
        with m.Else():
            if PrintFlag.ELAPLED_CYC in self._print_flag:
                # elapsed 1 cycle
                m.d.sync += [Kanata.elapsed_cyc(cycle=1)]

        # log (IS stage end)
        with m.If(self.req_out.en):
            m.d.sync += Kanata.end_stage(
                uniq_id=self.req_out.locate.uniq_id, lane_id=self._lane_id, stage="IS"
            )

        # default next state
        m.d.sync += [
            # disable current cycle destination
            self.req_out.en.eq(0),
            # default abort
            self.req_out.abort_type.eq(abort_type),
            # keep pc
            pc.eq(pc),
            self.req_out.locate.pc.eq(pc),
            # keep uniq_id
            uniq_id.eq(uniq_id),
            self.req_out.locate.uniq_id.eq(uniq_id),
            # always increment cyc
            cyc.eq(cyc + 1),
            # default branch strobe disable
            self.branch_strobe.eq(0),
            self.branch_strobe_src_addr.eq(0),
        ]

        with m.FSM(init="READY", domain="sync"):
            with m.State("ABORT"):
                # Abort Clearが来ていた場合は解除
                with m.If(self.ctrl_req_in.clear):
                    # Abort Clear
                    m.d.sync += [
                        abort_type.eq(AbortType.NONE),
                    ]
                    m.next = "READY"
            with m.State("READY"):
                # main logic
                with m.If(~self.req_in.en):
                    # No Request
                    pass
                with m.Else():
                    with m.If(
                        self.ctrl_req_in.flush
                        | self.ctrl_req_in.stall
                        | self.ctrl_req_in.clear
                    ):
                        # Flush/Stall/Clear Request時は待機
                        pass
                    with m.Else():
                        with m.If(self.req_in.branch_req.en):
                            # Illegal Branch Request
                            # incrementはconfig。NUM_INST_BYTEで行っているので、ミスアライメントが起きる可能性はここ

                            is_misaligned = (
                                self.req_in.branch_req.next_pc.bit_select(
                                    0, config.INST_ADDR_OFFSET_BITS
                                )
                                != 0
                            )
                            with m.If(is_misaligned):
                                # Misaligned Access
                                m.d.sync += [
                                    abort_type.eq(AbortType.MISALIGNED_FETCH),
                                ]
                                m.next = "ABORT"
                            with m.Else():
                                # Valid Branch Request
                                m.d.sync += [
                                    # enable current cycle destination
                                    self.req_out.en.eq(1),
                                    # set branch target pc
                                    pc.eq(
                                        self.req_in.branch_req.next_pc
                                        + self._num_inst_bytes
                                    ),
                                    self.req_out.locate.pc.eq(
                                        self.req_in.branch_req.next_pc
                                    ),
                                    # increment uniq_id
                                    uniq_id.eq(uniq_id + 1),
                                    self.req_out.locate.uniq_id.eq(uniq_id),
                                    # debug branch strobe
                                    self.branch_strobe.eq(1),
                                    self.branch_strobe_src_addr.eq(pc),
                                    self.branch_strobe_dst_addr.eq(
                                        self.req_in.branch_req.next_pc
                                    ),
                                ]
                                if PrintFlag.STAGE in self._print_flag:
                                    # log (cmd start, IS stage start)
                                    m.d.sync += [
                                        Kanata.start_cmd(uniq_id=uniq_id),
                                        Kanata.start_stage(
                                            uniq_id=uniq_id,
                                            lane_id=self._lane_id,
                                            stage="IS",
                                        ),
                                        Kanata.label_cmd_is(
                                            uniq_id=uniq_id,
                                            label_type=Kanata.LabelType.ALWAYS,
                                            pc=self.req_in.branch_req.next_pc,
                                        ),
                                    ]
                        with m.Else():
                            # Increment PC
                            m.d.sync += [
                                # enable current cycle destination
                                self.req_out.en.eq(1),
                                # increment pc
                                pc.eq(pc + self._num_inst_bytes),
                                self.req_out.locate.pc.eq(pc),
                                # increment uniq_id
                                uniq_id.eq(uniq_id + 1),
                                self.req_out.locate.uniq_id.eq(uniq_id),
                            ]
                            if PrintFlag.STAGE in self._print_flag:
                                # log (cmd start, IS stage start)
                                m.d.sync += [
                                    Kanata.start_cmd(uniq_id=uniq_id),
                                    Kanata.start_stage(
                                        uniq_id=uniq_id,
                                        lane_id=self._lane_id,
                                        stage="IS",
                                    ),
                                    Kanata.label_cmd_is(
                                        uniq_id=uniq_id,
                                        label_type=Kanata.LabelType.ALWAYS,
                                        pc=pc,
                                    ),
                                ]
        return m


if __name__ == "__main__":
    stages = [
        InstSelectStage(),
    ]
    for stage in stages:
        util.export_verilog_file(stage, f"{stage.__class__.__name__}")
