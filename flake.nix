{
  description = "Keybox Scavenger backend development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
        };

        python = pkgs.python314;

        scavengerCli = pkgs.writeShellApplication {
          name = "keybox-scavenger";
          runtimeInputs = [ python ];
          text = ''
            cd "${self}"
            exec ${python.interpreter} scavenger_main.py "$@"
          '';
          meta = {
            description = "Run Keybox Scavenger userbot";
            mainProgram = "keybox-scavenger";
            license = pkgs.lib.licenses.agpl3Only;
            platforms = pkgs.lib.platforms.unix;
          };
        };
      in
      {
        devShells.default = pkgs.mkShell {
          packages = [
            python
            pkgs.pdm
            pkgs.ruff
            pkgs.git
            pkgs.docker
            pkgs.docker-compose
          ];

          shellHook = ''
            echo "Entering Keybox Scavenger dev shell"
            echo "Next steps: pdm install --prod && pdm run scavenger"
          '';
        };

        packages.default = scavengerCli;
        packages.scavenger = scavengerCli;

        apps.default = {
          type = "app";
          program = "${scavengerCli}/bin/keybox-scavenger";
          meta = {
            description = "Run Keybox Scavenger userbot";
          };
        };

        apps.scavenger = {
          type = "app";
          program = "${scavengerCli}/bin/keybox-scavenger";
          meta = {
            description = "Run Keybox Scavenger userbot";
          };
        };

        formatter = pkgs.nixfmt;
      }
    );
}
