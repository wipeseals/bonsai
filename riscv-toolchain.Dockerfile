FROM ubuntu:24.04

WORKDIR /app

# riscv-gnu-toolchainのリポジトリを取得
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
    make -j$(nproc) && \
    make

# 環境変数の設定
ENV PATH="/opt/riscv/bin:${PATH}"
