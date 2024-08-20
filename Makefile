# Makefile

.PHONY: build run

build:
	zsh scripts/antlr-build.zsh
	zsh scripts/clang-build.zsh

run:
	python3 syntax_checker.py
