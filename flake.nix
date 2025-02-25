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
            pkgs.python310
          ];
          shellHook = ''
            echo "Welcome to the bonsai project!"
            pip install --user uv --break-system-packages
            uv venv .venv.nix
            source .venv.nix/bin/activate
            uv sync --all-extras --dev
          '';
        };
      };
    };
  };
}