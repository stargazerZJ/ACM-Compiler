#!/usr/bin/env bash

cd "$(dirname "$0")"/../mxc/common/dominator || exit

mkdir -p ./build

export CC=clang-18
export CXX=clang++-18

# one notable step for this to work is to install `pybind11` headers. On ubuntu, you may run `sudo apt-get install pybind11-dev

cmake -S . -B build
cmake --build build
mv build/*.so .