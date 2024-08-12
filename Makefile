# Makefile

.PHONY: build run

build:
	sh scripts/antlr-build.zsh

run:
	python3 syntax_checker.py
