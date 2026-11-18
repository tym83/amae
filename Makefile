# Building Tainted.
#
#   make            the compiler, from the seed in boot/tc.c
#   make test       every golden program, compiled and run twice
#   make bootstrap  the compiler compiles itself; generations are compared
#   make seed       boot/tc.c from the bootstrap (after a change to the compiler)

CC ?= cc
CFLAGS ?= -std=c11 -D_POSIX_C_SOURCE=200809L -O2 -Wall -Wextra -Wno-unused-parameter
BUILD := build
RUNTIME := runtime/tainted.c runtime/tainted.h
HISTORY := $(abspath $(BUILD))/history.json

.PHONY: all test bootstrap seed clean

all: $(BUILD)/tc-core

$(BUILD):
	mkdir -p $@

$(BUILD)/tc-core: boot/tc.c $(RUNTIME) | $(BUILD)
	$(CC) $(CFLAGS) -Iruntime boot/tc.c runtime/tainted.c -o $@

# Generation 1 is compiled by the seed, generation 2 by generation 1, and so on.
$(BUILD)/gen1.c: compiler.tainted $(BUILD)/tc-core
	TAINTED_HISTORY=$(HISTORY) $(BUILD)/tc-core < compiler.tainted > $@

$(BUILD)/gen%: $(BUILD)/gen%.c $(RUNTIME)
	$(CC) $(CFLAGS) -Iruntime $< runtime/tainted.c -o $@

$(BUILD)/gen2.c: $(BUILD)/gen1
	TAINTED_HISTORY=$(HISTORY) $(BUILD)/gen1 < compiler.tainted > $@

$(BUILD)/gen3.c: $(BUILD)/gen2
	TAINTED_HISTORY=$(HISTORY) $(BUILD)/gen2 < compiler.tainted > $@

bootstrap: $(BUILD)/gen2.c $(BUILD)/gen3.c
	cmp $(BUILD)/gen2.c $(BUILD)/gen3.c
	@echo "generations 2 and 3 are the same program"

seed: bootstrap
	cp $(BUILD)/gen3.c boot/tc.c

test: $(BUILD)/tc-core
	sh tests/golden.sh $(BUILD)/tc-core

clean:
	rm -rf $(BUILD)
