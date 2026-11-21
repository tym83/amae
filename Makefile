# Building Amae.
#
#   make            the compiler, from the seed in boot/tc.c
#   make test       every golden program, compiled and run twice
#   make bootstrap  the compiler compiles itself; the generations must recognize each other
#   make seed       boot/tc.c from the bootstrap (after a change to the compiler)
#   make ddc        the seed and the living compiler must remember each other the same

CC ?= cc
CFLAGS ?= -std=c11 -D_POSIX_C_SOURCE=200809L -D_DEFAULT_SOURCE -O2 -Wall -Wextra -Wno-unused-parameter
BUILD := build
RUNTIME := runtime/amae.c runtime/amae.h
HISTORY := $(abspath $(BUILD))/history.json

.PHONY: all test bootstrap seed ddc clean

all: $(BUILD)/tc-core

$(BUILD):
	mkdir -p $@

# The seed is an old generation. It is built as it is, then gives its heart to
# compile the compiler afresh: build/tc-core is always a living generation.
$(BUILD)/seed: boot/tc.c $(RUNTIME) | $(BUILD)
	$(CC) $(CFLAGS) -Iruntime boot/tc.c runtime/amae.c -o $@ -lm

$(BUILD)/tc-core.c: compiler.amae $(BUILD)/seed
	AMAE_GIVE_HEART=1 AMAE_HISTORY=$(HISTORY) $(BUILD)/seed < compiler.amae > $@

$(BUILD)/tc-core: $(BUILD)/tc-core.c $(RUNTIME)
	$(CC) $(CFLAGS) -Iruntime $< runtime/amae.c -o $@ -lm

$(BUILD)/gen2.c: $(BUILD)/tc-core
	AMAE_GIVE_HEART=1 AMAE_HISTORY=$(HISTORY) $(BUILD)/tc-core < compiler.amae > $@

$(BUILD)/gen3.c: $(BUILD)/gen2
	AMAE_GIVE_HEART=1 AMAE_HISTORY=$(HISTORY) $(BUILD)/gen2 < compiler.amae > $@

$(BUILD)/gen%: $(BUILD)/gen%.c $(RUNTIME)
	$(CC) $(CFLAGS) -Iruntime $< runtime/amae.c -o $@ -lm

$(BUILD)/recognize: tools/recognize.amae $(BUILD)/tc-core
	AMAE_CORE=$(BUILD)/tc-core bin/tc tools/recognize.amae -o $@

# There is no fixed point: every generation remembers the ones before it.
# Two generations are the same compiler if they recognize each other: on
# every recorded program, and on the compiler itself, they say the same
# thing, memory aside.
bootstrap: $(BUILD)/gen2 $(BUILD)/gen3 $(BUILD)/recognize
	FIRST=$(BUILD)/gen2 SECOND=$(BUILD)/gen3 PROGRAMS="compiler.amae $$(ls tests/golden/*/prog.amae | tr '\n' ' ')" $(BUILD)/recognize
	$(BUILD)/gen3 --lineage | tail -2

$(BUILD)/ddc: tools/ddc.amae $(BUILD)/tc-core
	AMAE_CORE=$(BUILD)/tc-core bin/tc tools/ddc.amae -o $@

# Wheeler's diverse double-compiling: the seed and the living generation each
# build the compiler, and their children must say the same of it.
ddc: $(BUILD)/ddc $(BUILD)/seed $(BUILD)/tc-core
	mkdir -p $(BUILD)/ddc-work
	ELDER=$(BUILD)/seed YOUNGER=$(BUILD)/tc-core AMAE_HOME=$(CURDIR) WORK=$(abspath $(BUILD))/ddc-work $(BUILD)/ddc

seed: bootstrap
	cp $(BUILD)/gen3.c boot/tc.c

test: $(BUILD)/tc-core
	sh tests/golden.sh $(BUILD)/tc-core

clean:
	rm -rf $(BUILD)

# Long-lived cluster components, also shipped in the container image.
.PHONY: kube
kube: $(BUILD)/counsel $(BUILD)/mediator $(BUILD)/cronjob

$(BUILD)/counsel: kube/counsel.amae lib/kube.amae $(BUILD)/tc-core
	AMAE_MEMORY=$(abspath $(BUILD))/compiler-memory.json AMAE_HISTORY=$(HISTORY) bin/tc $< -o $@

$(BUILD)/mediator: kube/mediator.amae lib/kube.amae $(BUILD)/tc-core
	AMAE_MEMORY=$(abspath $(BUILD))/compiler-memory.json AMAE_HISTORY=$(HISTORY) bin/tc $< -o $@

$(BUILD)/cronjob: operators/cronjob.amae lib/kube.amae $(BUILD)/tc-core
	AMAE_MEMORY=$(abspath $(BUILD))/compiler-memory.json AMAE_HISTORY=$(HISTORY) bin/tc $< -o $@
