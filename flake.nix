{
  description = "Nix flake for developing and building KeyboxScavenger";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { nixpkgs, ... }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f system);
    in
    {
      packages = forAllSystems
        (system:
          let
            pkgs = import nixpkgs { inherit system; };
          in
          {
            default = pkgs.stdenvNoCC.mkDerivation {
              pname = "keyboxscavenger";
              version = "dev";
              src = ./.;

              nativeBuildInputs = with pkgs; [
                bash
                binutils
                clang
                coreutils
                file
                findutils
                gawk
                gnugrep
                gnused
                gnutar
                gzip
                zip
              ];

              dontConfigure = true;
              dontFixup = true;

              buildPhase = ''
                runHook preBuild
                export HOME="$TMPDIR"
                chmod -R u+w .
                sh ./build.sh
                runHook postBuild
              '';

              installPhase = ''
                runHook preInstall
                mkdir -p "$out"
                cp -a _builds "$out/"
                cp -a module.prop module.json "$out/"
                runHook postInstall
              '';
            };
          });

      devShells = forAllSystems
        (system:
          let
            pkgs = import nixpkgs { inherit system; };
          in
          {
            default = pkgs.mkShell {
              packages = with pkgs; [
                bash
                binutils
                clang
                coreutils
                file
                findutils
                gawk
                gnugrep
                gnused
                gnutar
                gzip
                zip
              ];

              shellHook = ''
                echo "KeyboxScavenger nix dev shell ready."
                echo "Try: sh check-syntax.sh && sh build.sh"
              '';
            };
          });
    };
}
