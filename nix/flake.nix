{
  description = "A flake for Nanonote";
  
  inputs = {
        nixpkgs = {
            url = "github:nixos/nixpkgs/nixos-23.11";
        };
        singleapplication.url = "github:itay-grudev/SingleApplication";
        singleapplication.flake = false;

  };
  
  outputs = inputs@{ self, nixpkgs, singleapplication }:
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
        # Provide some binary packages for selected system types.
      packages = forAllSystems (system:
        let 
          pkgs = nixpkgsFor.${system}; 
        in
        {
          
          default = self.packages.${system}.nanonote;
        
          nanonote = with pkgs; pkgs.stdenv.mkDerivation rec {
            name = "nanonote";
            pname = "nanonote";
            src = ../.;
            nativeBuildInputs = [
                cmake
                extra-cmake-modules
                libsForQt5.qt5.qtbase
                libsForQt5.qt5.qttools
                libsForQt5.qt5.wrapQtAppsHook
                git
            ];
            buildPhase = ''
                make -j $NIX_BUILD_CORES;
            '';
            installPhase = ''
                make install PREFIX=$out
            '';
          };
        }
      );
      apps = forAllSystems (system: {
        default = self.apps.${system}.nanonote;

        nanonote = {
          type = "app";
          program = "${self.packages.${system}.nanonote}/bin/nanonote";
        };
      });
    };
}
