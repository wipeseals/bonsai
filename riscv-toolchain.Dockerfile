FROM ubuntu:24.04

WORKDIR /app

# riscv-gnu-toolchainのリポジトリを取得
# TODO: Docker関係なく dejagnu の取得でコケる
#    Cloning into '/home/user/riscv-gnu-toolchain/uclibc-ng'...
#    remote: Enumerating objects: 12034, done.
#    remote: Counting objects: 100% (12034/12034), done.
#    remote: Compressing objects: 100% (6732/6732), done.
#    remote: Total 12034 (delta 7641), reused 7644 (delta 5056), pack-reused 0 (from 0)
#    Receiving objects: 100% (12034/12034), 6.05 MiB | 18.62 MiB/s, done.
#    Resolving deltas: 100% (7641/7641), done.
#    Cloning into '/home/user/riscv-gnu-toolchain/dejagnu'...
#    fatal: unable to access 'https://git.savannah.gnu.org/git/dejagnu.git/': Failed to connect to git.savannah.gnu.org port 443 after 130677 ms: Couldn't connect to server
#    fatal: clone of 'https://git.savannah.gnu.org/git/dejagnu.git' into submodule path '/home/user/riscv-gnu-toolchain/dejagnu' failed
#    Failed to clone 'dejagnu' a second time, aborting

RUN apt update && apt install -y git
RUN git clone --recursive https://github.com/riscv/riscv-gnu-toolchain

ENV RISCV=/opt/riscv
ENV ARCH=rv32ima
ENV ABI=ilp32
ENV PATH=$RISCV/bin:$PATH
ENV DEBIAN_FRONTEND=noninteractive

# 必要なパッケージをインストール
RUN apt install -y \
    autoconf \
    automake \
    autotools-dev \
    curl \
    python3 \
    python3-pip \
    python3-tomli \
    libmpc-dev \
    libmpfr-dev \
    libgmp-dev \
    gawk \
    build-essential \
    bison \
    flex \
    texinfo \
    gperf \
    libtool \
    patchutils \
    bc \
    zlib1g-dev \
    libexpat-dev \
    ninja-build \
    git \
    cmake \
    libglib2.0-dev \
    libslirp-dev

# riscv-gnu-toolchainのインストール
RUN cd riscv-gnu-toolchain && \
    ./configure --prefix=$RISCV --with-arch=$ARCH --with-abi=$ABI --enable-multilib --enable-qemu-system && \
    make -j$(nproc) linux


# riscv-isa-simのインストール
RUN apt install -y \
    device-tree-compiler \
    libboost-regex-dev \
    libboost-system-dev
RUN git clone https://github.com/riscv-software-src/riscv-isa-sim.git && \
    mkdir build && \
    cd build && \
    ../riscv-isa-sim/configure --prefix=$RISCV && \
    make -j$(nproc) && \
    make install