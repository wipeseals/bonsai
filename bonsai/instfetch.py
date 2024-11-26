from typing import Any
from amaranth import Const, Format, Module, Mux, Print, Shape, Signal, unsigned
from amaranth.lib import wiring, enum, data, memory, stream
from amaranth.lib.wiring import In, Out
from amaranth.cli import main

import config


class InstFetchDebug(data.Struct):
    """
    Debug information during instruction fetch
    """

    cyc: config.REG_SHAPE
    seq_no: config.REG_SHAPE


class InstFetch(wiring.Component):
    """
    InstFetch is a hardware component that fetches instructions from memory.
    """

    ctrl_in: In(stream.Signature(InstFetchIn))
    ctrl_out: Out(stream.Signature(InstFetchOut))
    read_req: Out(stream.Signature(MemReadReq))
    read_resp: In(stream.Signature(MemReadResp))

    def elaborate(self, platform):
        m = Module()

        #################################################
        # Signals

        # Program Counter
        pc = Signal(config.ADDR_SHAPE, init=0)
        # Ctrl Out Data
        ctrl_out_payload = Signal(InstFetchOut)
        # Debug Information
        debug = Signal(InstFetchDebug)

        #################################################
        # Condition

        # pipeline flush要否
        need_flush = self.ctrl_in.valid & self.ctrl_in.payload.flush
        # fetch先pc. flushの場合は指定された位置に変化
        fetch_addr = Mux(need_flush, self.ctrl_in.payload.jump_pc, pc)
        # read要求投げているけど未完了
        wait_finish_read = self.read_req.valid & ~self.read_resp.valid
        # read完了しているけど次段が受け付けていない
        wait_next_stage = self.read_resp.valid & ~self.ctrl_out.ready

        # fetch完了
        fetch_finished = ~(wait_finish_read | wait_next_stage)

        #################################################
        # Instruction Fetch operation

        m.d.comb += [
            ##################
            # ctrl_in
            # 次段に送信終わったら ctrl_in を受け付ける
            self.ctrl_in.ready.eq(fetch_finished),
            ##################
            # read req
            # fetch先は基本 PC register から。flushの場合は指定された位置から
            self.read_req.payload.addr.eq(fetch_addr),
            # ctrl_in が有効なら read_req を有効にする
            self.read_req.valid.eq(self.ctrl_in.valid),
            ##################
            # read resp
            # fetch完了は次段が受け付けた時
            self.read_resp.ready.eq(self.ctrl_out.ready),
            ##################
            # ctrl_out_payload
            # inst
            ctrl_out_payload.inst.eq(self.read_resp.payload.data),
            # pcはread_reqに投げたアドレス
            ctrl_out_payload.pc.eq(fetch_addr),
            # debug
            ctrl_out_payload.debug.eq(debug),
            ##################
            # ctrl_out
            # read完了ならvalid
            self.ctrl_out.valid.eq(self.read_resp.valid),
            # data
            self.ctrl_out.payload.eq(ctrl_out_payload),
        ]

        #################################################
        # Program Counter (PC) operation

        # 次段が受け付けたタイミングで更新
        with m.If(fetch_finished):
            # 有効ではないときは停止
            with m.If(self.ctrl_in.valid):
                # PCの次の値を設定
                with m.If(self.ctrl_in.payload.flush):
                    # jump先の1つ先の命令から
                    m.d.sync += pc.eq(
                        self.ctrl_in.payload.jump_pc + config.INST_WIDTH // 8
                    )
                with m.Else():
                    # 1命令進める
                    m.d.sync += pc.eq(pc + config.INST_WIDTH // 8)

        #################################################
        # debug information
        m.d.sync += debug.cyc.eq(debug.cyc + 1)
        with m.If(fetch_finished):
            m.d.sync += [
                # fetch seq_no
                debug.seq_no.eq(debug.seq_no + 1),
                # instruction fetch event
                Print(
                    Format(
                        "[IF] cyc:{:016x} seq_no:{:016x} ctrl_out.pc:{:016x} ctrl_out.inst:{:016x}",
                        debug.cyc,
                        debug.seq_no,
                        ctrl_out_payload.pc,
                        ctrl_out_payload.inst,
                    )
                ),
            ]

        return m


if __name__ == "__main__":
    instfetch = InstFetch()
    main(instfetch)
