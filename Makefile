# Makefile

.PHONY: build run

build:
	scripts/antlr-build.bash
	scripts/clang-build.bash
	scripts/pybind11-build.bash

run:
	./main.py --stdin
