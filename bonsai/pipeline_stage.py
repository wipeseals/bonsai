from amaranth import Format, Module, Signal
from amaranth.lib import wiring, memory
from amaranth.lib.wiring import In, Out

from log import Kanata
from pipeline_ctrl import BranchCtrl, FlushCtrl, InstFetchData, StallCtrl
import config
import util


class InstFetchStage(wiring.Component):
    """
    Instruction Fetch Stage

    責務
    - PCを更新し、次の命令を取得する
    - 分岐/ジャンプ命令があれば、次のPCを設定する
    - Flush信号があれば、次の命令を捨てる
    - Stall信号があれば、PCを更新しない
    - PCの値が指しているアドレスの命令を取得する
    - TODO: Instruction Cacheに当該データがない場合、Fetch完了を待ってから次のステージに進む
    """

    # Control in
    stall_in: In(StallCtrl)
    flush_in: In(FlushCtrl)
    branch_in: In(BranchCtrl)

    # result
    data_out: Out(InstFetchData)

    def __init__(self, init_pc: config.ADDR_SHAPE = 0x0, icache_init_data: list = []):
        self._init_pc = init_pc
        self._init_data = icache_init_data
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        # Program Counter: ローカルで保持していた次回PC + 4の値. FF
        next_pc = Signal(config.ADDR_SHAPE, reset=self._init_pc)
        # Program Counter: 今回fetch予定のアドレス. comb
        fetch_pc = Signal(config.ADDR_SHAPE, reset=self._init_pc)
        # Fetch Sequence Counter: 保持するために出力できたときに同期更新
        uniq_id = Signal(config.REG_SHAPE, reset=0)

        # Fetch Sequence Counter: 前回の値
        prev_en = Signal(1, reset=0)
        prev_uniq_id = Signal(config.REG_SHAPE, reset=0)
        prev_inst = Signal(config.INST_SHAPE, reset=0)

        # Instruction Memory TODO: L1 Cacheに変更
        m.submodules.mem = mem = memory.Memory(
            shape=config.INST_SHAPE, depth=config.L1_CACHE_DEPTH, init=self._init_data
        )
        rd_port = mem.read_port(domain="comb")

        # 前回のFetch完了をログ出力
        with m.If(prev_en):
            m.d.sync += Kanata.end_stage(uniq_id=prev_uniq_id, lane_id=0, stage="IF")

        # Flush優先
        with m.If(self.flush_in.en):
            # 出力せず
            self.data_out.clear(m=m, domain="sync", init_pc=self._init_pc)
        with m.Else():
            # Stall中は停滞
            with m.If(self.stall_in.en):
                # stall中はPCを更新せず
                self.data_out.clear(m=m, domain="sync", init_pc=self._init_pc)
                pass
            with m.Else():
                # TODO: 対象の命令がmemにない場合の対応
                # 後段にデータを流せず、Fetch完了を待つ必要がある

                # Fetch結果を出力できるケース

                # Branch/Jumpがあればそのアドレスを設定、なければ前回更新したPCを設定
                with m.If(self.branch_in.en):
                    m.d.sync += fetch_pc.eq(self.branch_in.next_pc)
                with m.Else():
                    m.d.sync += fetch_pc.eq(next_pc)

                # Cmd fetch開始をログ出力
                m.d.sync += [
                    Kanata.start_cmd(uniq_id=uniq_id, inst_id=uniq_id, thread_id=0),
                    Kanata.label_cmd(
                        uniq_id=uniq_id,
                        label_type=Kanata.LabelType.ALWAYS,
                        pc=fetch_pc,
                        inst=prev_inst,
                    ),
                    Kanata.start_stage(uniq_id=uniq_id, lane_id=0, stage="IF"),
                ]

                # read addrにPCの下位2bitを落としたものを設定し、出力をそのまま流す
                m.d.sync += [
                    rd_port.addr.eq(fetch_pc >> config.INST_ADDR_SHIFT),
                ]
                self.data_out.update(
                    m,
                    domain="sync",
                    pc=fetch_pc,
                    inst=rd_port.data,
                    uniq_id=uniq_id,
                )
                # next_pc, uniq_idを同期更新
                m.d.sync += [
                    # TODO: 分岐予測する場合Fetch予定地変更
                    next_pc.eq(fetch_pc + config.INST_BYTES),
                    uniq_id.eq(uniq_id + 1),
                ]

        # logで今回fetchしたコマンドの終了用に値を保持
        m.d.sync += [
            prev_en.eq(self.data_out.ctrl.en),
            prev_inst.eq(rd_port.data),
            prev_uniq_id.eq(uniq_id),
        ]

        return m


if __name__ == "__main__":
    stages = [
        InstFetchStage(),
    ]
    for stage in stages:
        util.export_verilog_file(stage, f"{stage.__class__.__name__}")
