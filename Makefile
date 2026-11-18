# Building Tainted.
#
#   make            the compiler, from the seed in boot/tc.c
#   make test       every golden program, compiled and run twice
#   make bootstrap  the compiler compiles itself; the generations must recognize each other
#   make seed       boot/tc.c from the bootstrap (after a change to the compiler)
#   make ddc        the seed and the living compiler must remember each other the same

CC ?= cc
CFLAGS ?= -std=c11 -D_POSIX_C_SOURCE=200809L -D_DEFAULT_SOURCE -O2 -Wall -Wextra -Wno-unused-parameter
BUILD := build
RUNTIME := runtime/tainted.c runtime/tainted.h
HISTORY := $(abspath $(BUILD))/history.json

.PHONY: all test bootstrap seed ddc clean

all: $(BUILD)/tc-core

$(BUILD):
	mkdir -p $@

# The seed is an old generation. It is built as it is, then gives its heart to
# compile the compiler afresh: build/tc-core is always a living generation.
$(BUILD)/seed: boot/tc.c $(RUNTIME) | $(BUILD)
	$(CC) $(CFLAGS) -Iruntime boot/tc.c runtime/tainted.c -o $@ -lm

$(BUILD)/tc-core.c: compiler.tainted $(BUILD)/seed
	TAINTED_GIVE_HEART=1 TAINTED_HISTORY=$(HISTORY) $(BUILD)/seed < compiler.tainted > $@

$(BUILD)/tc-core: $(BUILD)/tc-core.c $(RUNTIME)
	$(CC) $(CFLAGS) -Iruntime $< runtime/tainted.c -o $@ -lm

$(BUILD)/gen2.c: $(BUILD)/tc-core
	TAINTED_GIVE_HEART=1 TAINTED_HISTORY=$(HISTORY) $(BUILD)/tc-core < compiler.tainted > $@

$(BUILD)/gen3.c: $(BUILD)/gen2
	TAINTED_GIVE_HEART=1 TAINTED_HISTORY=$(HISTORY) $(BUILD)/gen2 < compiler.tainted > $@

$(BUILD)/gen%: $(BUILD)/gen%.c $(RUNTIME)
	$(CC) $(CFLAGS) -Iruntime $< runtime/tainted.c -o $@ -lm

$(BUILD)/recognize: tools/recognize.tainted $(BUILD)/tc-core
	TAINTED_CORE=$(BUILD)/tc-core bin/tc tools/recognize.tainted -o $@

# There is no fixed point: every generation remembers the ones before it.
# Two generations are the same compiler if they recognize each other: on
# every recorded program, and on the compiler itself, they say the same
# thing, memory aside.
bootstrap: $(BUILD)/gen2 $(BUILD)/gen3 $(BUILD)/recognize
	FIRST=$(BUILD)/gen2 SECOND=$(BUILD)/gen3 PROGRAMS="compiler.tainted $$(ls tests/golden/*/prog.tainted | tr '\n' ' ')" $(BUILD)/recognize
	$(BUILD)/gen3 --lineage | tail -2

$(BUILD)/ddc: tools/ddc.tainted $(BUILD)/tc-core
	TAINTED_CORE=$(BUILD)/tc-core bin/tc tools/ddc.tainted -o $@

# Wheeler's diverse double-compiling: the seed and the living generation each
# build the compiler, and their children must say the same of it.
ddc: $(BUILD)/ddc $(BUILD)/seed $(BUILD)/tc-core
	mkdir -p $(BUILD)/ddc-work
	ELDER=$(BUILD)/seed YOUNGER=$(BUILD)/tc-core TAINTED_HOME=$(CURDIR) WORK=$(abspath $(BUILD))/ddc-work $(BUILD)/ddc

seed: bootstrap
	cp $(BUILD)/gen3.c boot/tc.c

test: $(BUILD)/tc-core
	sh tests/golden.sh $(BUILD)/tc-core

clean:
	rm -rf $(BUILD)
