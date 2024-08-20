#!/usr/bin/env zsh

cd "${0:h}"/.. || exit

mkdir -p ../clang_generated

clang -emit-llvm \
  -fno-builtin-printf -fno-builtin-memcpy -fno-builtin-malloc -fno-builtin-strlen\
  -O3 --target=riscv32 \
  builtin.c -S \
  -o clang_generated/builtin.ll

llc --march=riscv32 -O3 -mattr=+m,+a clang_generated/builtin.ll -o clang_generated/builtin.s