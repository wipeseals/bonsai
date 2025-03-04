{
    description = "RISCV binary toolchain and RTL tools";

    inputs = {
        nixpkgs.url = "github:NixOS/nixpkgs";
        flake-utils.url = "github:numtide/flake-utils";
    };

    outputs = { self, nixpkgs, flake-utils, }: 
        flake-utils.lib.eachDefaultSystem (system:
        let
            pkgs = import nixpkgs { inherit system; };
            crossPkgs = pkgs.pkgsCross.riscv32-embedded;
        in
        {
            packages.default = crossPkgs.mkShell {
                nativeBuildInputs = with pkgs; [
                    # build tools
                    bazel
                    # riscv
                    crossPkgs.riscv-pk
                    spike
                    # rtl
                    yosys
                    verilator
                    iverilog
                    gtkwave
                ];
            };
        });
}