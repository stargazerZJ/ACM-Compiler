#!/usr/bin/env bash

cd "$(dirname "$0")"/../mxc/frontend/parser || exit

antlr4 -visitor -no-listener -Dlanguage=Python3 MxLexer.g4 MxParser.g4