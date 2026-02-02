{
  description = "Python 开发环境";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        devShells.default = pkgs.mkShell {
          packages = [
            pkgs.uv
            pkgs.ruff
            pkgs.pyright

            pkgs.stdenv.cc
            pkgs.pkg-config
          ];

          shellHook = ''
            # 可选：仅在确实遇到运行期缺库时再保留
            export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath [ pkgs.stdenv.cc.cc.lib ]}:$LD_LIBRARY_PATH"

            if [ ! -d .venv ]; then
              echo "Creating Python virtual environment with uv..."
              uv venv
            fi

            if [ -f .venv/bin/activate ]; then
              . .venv/bin/activate
            fi

            if [ -f pyproject.toml ]; then
              uv sync
            fi

            if [ -d "$PWD/src" ]; then
              export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
            fi
          '';
        };
      }
    );
}
