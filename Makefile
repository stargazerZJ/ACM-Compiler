# Makefile

.PHONY: build run

build:
	zsh scripts/antlr-build.zsh
	zsh scripts/clang-build.zsh
	zsh scripts/pybind11-build.zsh

run:
	python3 asm_builder.py --stdin
