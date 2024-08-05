#!/usr/bin/env zsh

cd "${0:h}"/../antlr || exit

mkdir -p ../antlr_generated

antlr4 -visitor -no-listener -o ../antlr_generated/ -Dlanguage=Python3 MxLexer.g4 MxParser.g4

# copy the tokens file to this directory so that the IDE will recognize it
cp ../antlr_generated/MxLexer.tokens .