# Dalila-Mud

CircleMUD-based server with the world data under `lib/`.

## Build (Nix/NixOS)

Use the provided `shell.nix` to get a working toolchain:

```
nix-shell
make -C src circle
```

Inside the Nix shell there is a convenience alias and a short motd:

- `dalila-build` runs:
  `make -C src clean ; make -C src circle CC=clang MYFLAGS="-Wall -std=gnu89 -Wno-implicit-int"`

This repo already ships a generated `src/Makefile` and `src/conf.h`, so you
can build directly without running `./configure`.

If you want to use clang, override the compiler and flags:

```
make -C src circle CC=clang MYFLAGS="-Wall -std=gnu89 -Wno-implicit-int"
```

## Run

```
./run.sh
```

Or run directly on a custom port:

```
bin/circle -q 4000
```

The server uses `lib/` as its data directory by default.

## Clean

```
make -C src clean
```
