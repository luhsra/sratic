{
  description = "SRA/OSG Website";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    srapkgs = {
      url = "github:luhsra/srapkgs";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    inputs:
    let
      supportedSystems = [ "aarch64-linux" "x86_64-linux" "aarch64-darwin" "x86_64-darwin"];
      forAllSystems = inputs.nixpkgs.lib.genAttrs supportedSystems;
    in
    {
      devShells = forAllSystems (
        system:
        let
          pkgs = import inputs.nixpkgs { inherit system; };
          srapkgs = inputs.srapkgs.packages.${system};
        in
        {
          default = pkgs.mkShellNoCC {
            buildInputs = with pkgs; [
              (python3.withPackages (py: [
                py.jinja2
                py.markdown
                py.pyyaml
                py.typst
                py.dateutils
              ]))
              pkgs.gnumake
              pkgs.ruff
              srapkgs.bib2json
            ];
          };
        }
      );
    };
}
