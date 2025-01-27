from enum import Flag, auto
from amaranth import Assert, Format, Module, Signal, unsigned
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

from log import Kanata
from bonsai.datatype import (
    AbortType,
    InstDecodeReqSignature,
    InstFetchReqSignature,
    InstSelectReqSignature,
    MemoryAccessReqSignature,
    MemoryOperationType,
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

    # misaligned access address (for debug)
    misaligned_addr: Out(config.ADDR_SHAPE)

    def __init__(
        self,
        initial_pc: int = 0,
        initial_uniq_id: int = 0,
        lane_id: int = 0,
        print_flag: PrintFlag = PrintFlag.all(),
        use_strict_assert: bool = config.USE_STRICT_ASSERT,
    ):
        self._initial_pc = initial_pc
        self._initial_uniq_id = initial_uniq_id
        self._lane_id = lane_id
        self._print_flag = print_flag
        self._use_strict_assert = use_strict_assert
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        # local signals
        pc = Signal(config.ADDR_SHAPE, init=self._initial_pc)
        uniq_id = Signal(config.CMD_UNIQ_ID_SHAPE, init=self._initial_uniq_id)
        cyc = Signal(config.CYCLE_COUNTER_SHAPE, init=0)
        abort_type = Signal(AbortType, init=AbortType.NONE)
        misaligned_addr = Signal(config.ADDR_SHAPE, init=0)

        # 直結
        m.d.comb += [
            self.global_cyc.eq(cyc),
            self.req_out.abort_type.eq(abort_type),
            self.misaligned_addr.eq(misaligned_addr),
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

        # default next state
        m.d.sync += [
            # disable current cycle destination
            self.req_out.en.eq(0),
            # keep pc
            pc.eq(pc),
            self.req_out.locate.pc.eq(pc),
            # keep uniq_id
            uniq_id.eq(uniq_id),
            self.req_out.locate.uniq_id.eq(uniq_id),
            # always increment cyc
            cyc.eq(cyc + 1),
            # default branch strobe disable (for debug)
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
                        misaligned_addr.eq(0),
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
                                    misaligned_addr.eq(self.req_in.branch_req.next_pc),
                                ]
                                m.next = "ABORT"

                                if self._use_strict_assert:
                                    m.d.sync += [
                                        Assert(
                                            0,
                                            Format(
                                                "Misaligned Access: {:016x}",
                                                self.req_in.branch_req.next_pc,
                                            ),
                                        ),
                                    ]
                            with m.Else():
                                # Valid Branch Request
                                m.d.sync += [
                                    # enable current cycle destination
                                    self.req_out.en.eq(1),
                                    # set branch target pc
                                    pc.eq(
                                        self.req_in.branch_req.next_pc
                                        + config.INST_BYTE_WIDTH
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
                                pc.eq(pc + config.INST_BYTE_WIDTH),
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


class InstFetchStage(wiring.Component):
    """
    Instruction Fetch Stage
    """

    # Stage Control Request
    ctrl_req_in: In(StageCtrlReqSignature())

    # Instruction Fetch Request
    req_in: In(InstFetchReqSignature())

    # Instruction Decode Request
    req_out: Out(InstDecodeReqSignature())

    # Memory Access Port
    mem_req_out: Out(MemoryAccessReqSignature())

    def __init__(self, lane_id: int = 0):
        self._lane_id = lane_id
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        # Abort状態
        abort_type = Signal(AbortType, init=AbortType.NONE)
        is_aborted = abort_type != AbortType.NONE

        # Read Access制御。op_typeの変更でRead/Nanageを切り替える
        op_type = Signal(MemoryOperationType, init=MemoryOperationType.READ_CACHE)
        data_in = Signal(config.DATA_SHAPE, init=0)
        m.d.comb += [
            # 読み出しOperation
            self.mem_req_out.op_type.eq(op_type),
            self.mem_req_out.addr_in.eq(self.req_in.locate.pc),
            # Manage用にdata_inを設定
            self.mem_req_out.data_in.eq(data_in),
        ]
        # 有効なデータの条件
        # 要求がValidでstall/flush/clear中ではなくReadを投げていて、MemoryがBusyでない
        req_valid = (
            (~is_aborted)
            & (self.req_in.en)
            & (self.ctrl_req_in.flush == 0)
            & (self.ctrl_req_in.stall == 0)
            & (self.ctrl_req_in.clear == 0)
        )
        read_req_valid = (req_valid) & (op_type == MemoryOperationType.READ_CACHE)
        read_done = (read_req_valid) & (self.mem_req_out.busy == 0)
        read_data = self.mem_req_out.data_out

        # 出力直結
        m.d.comb += [
            # out: Disable/Enable
            self.req_out.en.eq(read_done),
            # out: Read Data & Req引用
            self.req_out.inst.eq(read_data),
            self.req_out.inst.locate.eq(self.req_in.locate),
            # out: Abort Type
            self.req_out.abort_type.eq(abort_type),
        ]

        # TODO: Abort/Manage時の対応
        with m.FSM(init="READY", domain="sync"):
            with m.State("ABORT"):
                # TODO: implement
                pass
            with m.State("MANAGE"):
                # TODO: implement
                pass
            with m.State("READY"):
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
                        # Main Logic
                        # TODO: implement
                        pass
                pass
        return m


if __name__ == "__main__":
    stages = [
        InstSelectStage(),
        InstFetchStage(),
    ]
    for stage in stages:
        util.export_verilog_file(stage, f"{stage.__class__.__name__}")
