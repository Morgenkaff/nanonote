{
  description = "A flake for Nanonote";

  outputs = { self, nixpkgs }:
    let

      # List of supported systems:
      supportedSystems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      # Helper function to generate an attrset '{ x86_64-linux = f "x86_64-linux"; ... }'.
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
      # Nixpkgs instantiated for supported system types.
      nixpkgsFor = forAllSystems (system: import nixpkgs { inherit system; });
      pkgs = nixpkgs;

    in
    {
      # Create the package output for all system architectures
      packages = forAllSystems (system:
        let
          # Set pkg as nixpkgs for correct system architectures
          pkgs = nixpkgsFor.${system};
        in
        {

          # Declare a default package (there's only one package in this flake..)
          default = self.packages.${system}.nanonote;

          # Write derivation for nanonote.
          # Declaring the src, name, built dependencies etc
          nanonote = with pkgs; pkgs.stdenv.mkDerivation rec {

            # Set the package name with "version" appended
            name = "nanonote";

            # The source is simply the diorectory above. Easy..
            src = ../.;

            # These are the packages needed to build nanonote
            nativeBuildInputs = [
              cmake
              extra-cmake-modules
              libsForQt5.qt5.qtbase
              libsForQt5.qt5.qttools
              libsForQt5.qt5.wrapQtAppsHook
            ];

            # Command to build nanonote (with a core limitation, just to be safe)
            buildPhase = ''
              make -j $NIX_BUILD_CORES
            '';

            # And make install, to get all the pieces tp the wight places.
            # $out is the nix store/derivation output (don't know what it's called)
            installPhase = ''
              make install PREFIX=$out
            '';
          };
        }
      );

      # At last declaring the overlay used in the recieving/consuming flakes
      overlays.default = final: prev: {
        nanonote = self.packages.${prev.system}.nanonote;
      };

    };

}
