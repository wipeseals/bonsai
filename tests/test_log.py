import sys
from typing import List
from amaranth import Module, Print
from bonsai import config
from bonsai.log import Kanata
import os

from amaranth.sim import Simulator
from amaranth.lib import wiring

from tests.testutil import run_sim


def test_kanata_print_samplelog():
    exp_log = """Kanata	0004 // 0004 バージョンのファイル
C=	216	// 216 サイクル目から開始
I	0	0	0	// 命令0の開始
L	0	0	12000d918 r4 = iALU(r3, r2)	// 命令0にラベル付け
S	0	0	F	// 命令0のFステージを開始
I	1	1	0	// 命令1の開始
L	1	0	12000d91c iBC(r17)	// 命令1にラベル付け
S	1	0	F	// 命令1のFステージを開始
C	1		// 1サイクル経過
E	0	0	F	// 命令0のFステージ終了
S	0	0	Rn	// 命令0のRnステージ開始
E	1	0	F	// 命令1のFステージ終了
S	1	0	Rn	// 命令1のFステージ開始

"""

    # log出力を履くだけのモジュールで出力を作る
    dut = Module()
    dut.d.sync += [
        Kanata.header(version=4),
        Kanata.start_cyc(cycle=216),
        Kanata.start_cmd(uniq_id=0, inst_id=0, thread_id=0),
        Kanata.label_cmd(
            uniq_id=0,
            label_type=Kanata.LabelType.ALWAYS,
            label_data="12000d918 r4 = iALU(r3, r2)",
        ),
        Kanata.start_stage(uniq_id=0, lane_id=0, stage="F"),
        Kanata.start_cmd(uniq_id=1, inst_id=1, thread_id=0),
        Kanata.label_cmd(
            uniq_id=1,
            label_type=Kanata.LabelType.ALWAYS,
            label_data="12000d91c iBC(r17)",
        ),
        Kanata.start_stage(uniq_id=1, lane_id=0, stage="F"),
        Kanata.elapsed_cyc(cycle=1),
        Kanata.end_stage(uniq_id=0, lane_id=0, stage="F"),
        Kanata.start_stage(uniq_id=0, lane_id=0, stage="Rn"),
        Kanata.end_stage(uniq_id=1, lane_id=0, stage="F"),
        Kanata.start_stage(uniq_id=1, lane_id=0, stage="Rn"),
    ]

    # 1cyc進めてログ出力させる
    async def bench(ctx):
        await ctx.tick()

    # 標準出力を奪って確認
    log_path = config.dist_file_path("test_print_example.log")
    sys.stdout = open(log_path, "w", encoding="utf-8")
    run_sim(f"{test_kanata_print_samplelog.__name__}", dut=dut, testbench=bench)
    sys.stdout = sys.__stdout__

    exp_lines = [
        line.split("//")[0].rstrip()
        for line in exp_log.splitlines()
        if len(line.strip()) > 0
    ]

    with open(log_path, "r", encoding="utf-8") as f:
        act_log = f.read()
        act_lines = [
            line.split("//")[0].rstrip()
            for line in act_log.splitlines()
            if len(line.strip()) > 0
        ]

        for exp_line, act_line in zip(exp_lines, act_lines):
            assert exp_line == act_line
