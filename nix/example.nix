{
description = "An example flake for Nanonote";

# This example flake does probably not work. But it should make it clear how to add Nanonote
# to your system flake, to be able to install Nanonote on your nix system.

  inputs = {

    # General nixos inputs:
    nixpkgs.url = "github:nixos/nixpkgs/nixos-24.05";

    # Home-mamanger inputs
    home-manager.url = "github:nix-community/home-manager/release-24.05";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";

    # Adding the nanonote flake input
    nanonote.url = "github:Morgenkaff/nanonote/add-flake?dir=nix";

  };

  outputs = { self, nixpkgs, home-manager, nanonote, ... }@inputs:

  let

  system = "x86_64-linux";

  in {
    nixosConfigurations =  {
      hostname = nixpkgs.lib.nixosSystem {
        inherit system;
        specialArgs = { inherit inputs; };
        modules =  [

          # Create an overlay to install Nanonote as was it part of nixpkgs
          ({ nixpkgs.overlays = [ nanonote.overlays.default ]; })
          # And then install it under "environment.systemPackages" in your nix configuration


          # Nix cinfiguration
          ./configuration.nix

          # Home-manager config:
          home-manager.nixosModules.home-manager
          {

            # Alternatively create n overlay for use in Home-manager
            nixpkgs.overlays = [ nanonote.overlays.default ];
            # And then install it under "home.packages" in you Home-manager configuration

            home-manager.useGlobalPkgs = true;
            home-manager.useUserPackages = true;
            home-manager.users.user = import ./home-manager.nix;

          }
      };
    };
  };
}

