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

## Project Structure

```
ACM-Compiler/
├── main.py                     # Main compiler entry point
├── mxc/                        # Core compiler package
│   ├── frontend/               # Frontend components
│   │   ├── parser/             # ANTLR grammar files (MxLexer.g4, MxParser.g4)
│   │   ├── semantic/           # Semantic analysis (scope, type checking, syntax validation)
│   │   └── ir_generation/      # IR generation (IR builder, block chain)
│   ├── middle_end/             # Optimization passes
│   │   ├── cfg_transform.py    # Control Flow Graph transformations
│   │   ├── dce.py              # Dead Code Elimination
│   │   ├── mem2reg.py          # Memory-to-Register promotion
│   │   ├── sccp.py             # Sparse Conditional Constant Propagation
│   │   ├── gvn_pre.py          # Global Value Numbering with Partial Redundancy Elimination
│   │   ├── liveness_analysis.py # Liveness analysis for register allocation
│   │   └── mir.py              # Machine IR construction
│   ├── backend/                # Code generation
│   │   ├── asm_builder.py      # Assembly code generation
│   │   ├── asm_repr.py         # Assembly representation
│   │   ├── regalloc.py         # Register allocation
│   │   └── operand.py          # Operand handling
│   ├── common/                 # Shared utilities
│   │   ├── dominator/          # Dominator tree analysis (C++ module with Python bindings)
│   │   ├── ir_repr.py          # IR representation classes
│   │   └── renamer.py          # Variable renaming utilities
│   ├── runtime/                # Runtime support
│   │   └── builtin.c           # Built-in functions implementation
│   └── test/                   # Unit tests and test utilities
├── testcases/                  # Test suite
│   ├── sema/                   # Semantic analysis tests
│   ├── codegen/                # Code generation tests
│   ├── optim/                  # Optimization tests
│   ├── optim2/                 # Additional optimization tests with I/O
│   └── demo/                   # Demo programs
├── scripts/                    # Build and test scripts
│   ├── antlr-build.bash        # ANTLR parser generation
│   ├── pybind11-build.bash     # pybind11 module compilation
│   └── test_*.bash             # Testing scripts
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container setup
├── Makefile                   # Build automation
├── README.md                  # This file
└── TESTING.md                 # Comprehensive testing guide
```

### Key Components

- **Frontend**: Handles lexical analysis, parsing, and semantic analysis of Mx* source code
- **Middle-end**: Implements various optimization passes including DCE, SCCP, GVN-PRE, and more
- **Backend**: Generates assembly code with register allocation and instruction selection
- **Runtime**: Provides built-in function implementations for the Mx* language
- **Dominator Module**: High-performance C++ implementation for dominator tree analysis with Python bindings
- **Test Suite**: Comprehensive tests covering semantic analysis, code generation, and optimizations