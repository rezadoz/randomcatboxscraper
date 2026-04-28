{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  name = "catbox-scanner";

  buildInputs = with pkgs; [
    (python3.withPackages (ps: with ps; [
      requests
      colorama
    ]))
  ];

  shellHook = ''
    echo "catbox scanner env ready — python $(python --version)"
    echo "run: python catbox_scanner.py --help"
  '';
}
