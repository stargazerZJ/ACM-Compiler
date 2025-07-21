# Mx* Compiler

This is a compiler for the Mx* language, which is a mixture of C++, Java and Python.

It's the [course lab](https://github.com/ACMClassCourses/Compiler-Design-Implementation) of CS2966@SJTU (Compiler Design, 2024 Summer)

## Incomplete Quickstart Guide

This project depends on `pybind11`, among anything else.

In order for the `dominator` module to work correctly, you need to build it via `pybind11`.

As a result, one notable step to set up is to install `pybind11` headers. On ubuntu, you may run `sudo apt-get install pybind11-dev`. On Windows, install MSVC and then install `pybind11` manually as mentioned in this part of the [official docs](https://pybind11.readthedocs.io/en/stable/compiling.html#find-package-vs-add-subdirectory). Afterward, the build scripts should work.

Alternatively, a `Dockerfile` is provided for you to build the project in a containerized environment. To build the image, run `docker build -t mxstar-compiler .`. To run the container, run `docker run -it mxstar-compiler < /path/to/your/input/file.mx`.

Afterwards, `make build` should be enough.

## Implemented Optimizations

- Dead Code Elimination (Naive DCE)
- Memory-to-Register Promotion (mem2reg)
- Global Variable Inlining
- Remove Unreachable Blocks
- Remove Critical Edges
- Reverse Post-Order Block Rearrangement
- Sparse Conditional Constant Propagation (SCCP)
- Global Value Numbering with Partial Redundancy Elimination (GVN-PRE)
- Copy Propagation
- Liveness Analysis
- MIR Construction
- Lots of small optimizations in ASM generation

### Usage

Specify optimization levels using the `-O` flag:
```bash
python main.py -O O1 input.mx -o output.s    # Standard optimization
python main.py -O O0 input.mx -o output.s    # Minimal optimization
python main.py -O gvn_pre input.mx -o output.s  # GVN-PRE specific optimizations
```

## Testing

For comprehensive testing instructions, including LLVM IR testing, assembly testing, semantic analysis, and optimization level usage, please refer to the [Testing Guide](TESTING.md).