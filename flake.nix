{
  description = "bonsai project development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs";
  };

  outputs = { self, nixpkgs, ... }: let 
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };
  in {
    devShells = {
      x86_64-linux = {
        default = pkgs.mkShell {
          buildInputs = [
            pkgs.pypy310
            pkgs.uv
            pkgs.yosys
            pkgs.sby
            pkgs.verilator
          ];
          shellHook = ''
            echo "Welcome to the bonsai project!"
            uv python install
            uv venv nix-venv
            uv sync --all-extras --dev
          '';
        };
      };
    };
  };
}