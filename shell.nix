{ pkgs ? import <nixpkgs> {} }:
pkgs.mkShell {
  packages = with pkgs; [
    gnumake
    gcc
    binutils
    libxcrypt
  ];
  shellHook = ''
    alias dalila-build='make -C src clean ; make -C src circle CC=clang MYFLAGS="-Wall -std=gnu89 -Wno-implicit-int"'
    cat <<'EOF'
Dalila-Mud nix-shell
- Build with clang: dalila-build
EOF
  '';
}
