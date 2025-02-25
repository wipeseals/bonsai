#!/bin/bash -eu
set -o pipefail

# This script builds the riscv-tests suite for the RISC-V ISA simulator.
git clone --recursive https://github.com/riscv/riscv-tests
cd riscv-tests && \
    autoconf && \
    ./configure --prefix=$RISCV/target && \
    make
