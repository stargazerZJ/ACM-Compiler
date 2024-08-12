# Makefile

.PHONY: build run

build:
	scripts/antlr-build.zsh

run:
	python3 syntax_checker.py
