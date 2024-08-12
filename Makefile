# Makefile

.PHONY: build run

build:
	zsh scripts/antlr-build.zsh

run:
	python3 syntax_checker.py
