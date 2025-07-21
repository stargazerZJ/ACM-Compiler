# Testing Guide

This document provides comprehensive instructions for testing the Mx* compiler across different stages and optimization levels.

## Quick Start

### Prerequisites

Ensure you have completed the setup steps mentioned in the [README](README.md), including:
- Installing `pybind11` dependencies
- Building the dominator module
- Setting up the runtime environment

### Running Semantic Analysis Tests

To test the semantic analyzer with all test cases:

```bash
python3 mxc/test/syntax_checker_test.py
```

## LLVM IR Testing

### Single File Testing

Test LLVM IR generation for a single file:

```bash
scripts/test_llvm_ir.bash './main.py --emit-llvm -O O1 --dump-ir' testcases/codegen/t4.mx mxc/runtime/builtin.ll tmp
```

**Parameters:**
- `O1`: Optimization level (can be changed as needed)
- `testcases/codegen/t4.mx`: Input file to test
- `tmp`: Output directory

### Batch Testing (All Files in Directory)

Test LLVM IR generation for all files in a directory:

```bash
scripts/test_llvm_ir_all.bash './main.py --emit-llvm -O gvn_pre' testcases/optim mxc/runtime/builtin.ll
```

**Parameters:**
- `gvn_pre`: Optimization preset
- `testcases/optim`: Directory containing test files

## Assembly Testing

### Single File Testing

Test assembly generation for a single file:

```bash
scripts/test_asm.bash './main.py -o - -O O1' testcases/codegen/t4.mx mxc/runtime/builtin.s tmp
```

### Batch Testing (All Files in Directory)

Test assembly generation for all files in a directory:

```bash
scripts/test_asm_all.bash './main.py -o - -O O1' testcases/optim
```

## Test Directories

The following subdirectories contain test cases that can be used for both LLVM IR and assembly testing:

- `testcases/codegen` - Basic code generation tests
- `testcases/codegen2` - Additional code generation tests
- `testcases/demo` - Demonstration examples
- `testcases/deprecated` - Legacy test cases
- `testcases/optim` - Optimization test cases
- `testcases/optim-new` - Advanced optimization test cases

## Optimization Levels

The compiler supports several optimization presets:

### Basic Optimization Levels

- **O0**: Minimal optimizations (mandatory for backend compatibility)
  - Dead Code Elimination
  - Memory-to-Register Promotion
  - Block Rearrangement
  - MIR Construction
  - Liveness Analysis

- **O1**: Standard optimizations
  - All O0 optimizations
  - Global Variable Inlining

### Debug/Development Presets

- **ir_only**: No optimizations (IR generation only)
- **mem2reg**: Memory-to-Register Promotion only
- **unreachable**: Memory-to-Register + Remove Unreachable Blocks
- **sccp**: Sparse Conditional Constant Propagation
- **gvn_pre**: Global Value Numbering with Partial Redundancy Elimination

### Example Usage with Different Optimization Levels

```bash
# Test with no optimizations
scripts/test_llvm_ir.bash './main.py --emit-llvm -O ir_only --dump-ir' testcases/demo/d1.mx mxc/runtime/builtin.ll tmp

# Test with SCCP optimization
scripts/test_asm.bash './main.py -o - -O sccp' testcases/optim/pi.mx mxc/runtime/builtin.s tmp

# Test with GVN-PRE optimization
scripts/test_llvm_ir_all.bash './main.py --emit-llvm -O gvn_pre' testcases/optim-new mxc/runtime/builtin.ll
```

## Semantic Analysis Test Suites

The semantic analyzer can be tested against various test packages:

- `testcases/sema/array-package/` - Array-related tests
- `testcases/sema/basic-package/` - Basic language feature tests
- `testcases/sema/class-package/` - Object-oriented programming tests
- `testcases/sema/function-package/` - Function-related tests
- `testcases/sema/loop-package/` - Loop construct tests
- And many more specialized test packages

## Tips for Testing

1. **Start with basic tests**: Begin with `testcases/codegen` before moving to optimization tests
2. **Use appropriate output directories**: Always specify a temporary directory for outputs
3. **Check optimization compatibility**: Some optimization presets are for debugging and may not be backend-compatible
4. **Monitor performance**: Use optimization tests in `testcases/optim` to verify performance improvements
5. **Semantic testing**: Run semantic tests frequently during development to catch early issues

## Troubleshooting

- If tests fail, check that all dependencies (especially `pybind11`) are properly installed
- Ensure the dominator module is built correctly
- Verify that runtime files (`builtin.ll`, `builtin.s`) are accessible
- Check file permissions on test scripts (they may need to be executable)