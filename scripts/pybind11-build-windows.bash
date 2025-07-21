#!/usr/bin/env bash

cd "$(dirname "$0")"/../mxc/common/dominator || exit

mkdir -p ./build-windows

# one notable step for this to work is to install `pybind11` headers. On Windows, install manually as mentions in this part of the [official docs](https://pybind11.readthedocs.io/en/stable/compiling.html#find-package-vs-add-subdirectory

cmake.exe -S . -B build-windows
cmake.exe --build build-windows --config Release
mv build-windows/release/*.pyd .