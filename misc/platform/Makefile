
BAZEL=$(shell which bazel)

.PHONY: all
all: build

.PHONY: build
build:
	bazel build //main:hello1

.PHONY: clean
clean:
	bazel clean