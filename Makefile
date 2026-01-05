BUILD_CC ?= clang
BUILD_FLAGS ?= -Wall -std=gnu89 -Wno-implicit-int

.PHONY: build clean

build:
	@$(MAKE) -C src clean
	@$(MAKE) -C src circle CC=$(BUILD_CC) MYFLAGS="$(BUILD_FLAGS)"

clean:
	@$(MAKE) -C src clean
