

test llvm ir (single file)
```
scripts/test_llvm_ir.bash './main.py --emit-llvm -O O1 --dump-ir' testcases/codegen/t4.mx mxc/runtime/builtin.ll tmp
```

optimization flag can be changed, default is 1.

test llvm ir (all files in a directory)
```
scripts/test_llvm_ir_all.bash './main.py --emit-llvm -O gvn_pre' testcases/optim mxc/runtime/builtin.ll
```

test asm (single file)
```
scripts/test_asm.bash './main.py -o - -O O1' testcases/codegen/t4.mx mxc/runtime/builtin.s tmp
```

test asm (all files in a directory)
```
scripts/test_asm_all.bash './main.py -o - -O O1' testcases/optim
```

test semantics (all testcases)
```
python3 mxc/test/syntax_checker_test.py
```


Those subdirectories can be tested in llvm and asm.
```
testcases
├── codegen
├── codegen2
├── demo
├── deprecated
├── optim
├── optim-new
```

```
# Predefined optimization sequences
OPTIMIZATION_PRESETS = {
    "O0": [
        OptimizationPass(naive_dce, "Dead Code Elimination (initial)"),
        OptimizationPass(mem2reg, "Memory-to-Register Promotion"),
        OptimizationPass(naive_dce, "Dead Code Elimination (post mem2reg)"),
        OptimizationPass(rearrange_in_rpo, "Reverse Post-Order Block Rearrangement"),
        OptimizationPass(mir_builder, "MIR Construction"),
        OptimizationPass(naive_dce, "Dead Code Elimination (post MIR)"),
        OptimizationPass(liveness_analysis, "Liveness Analysis"),
    ], # These optimizations are mandatory because the backend relies on them
    "O1": [
        OptimizationPass(naive_dce, "Dead Code Elimination (initial)"),
        OptimizationPass(inline_global_variables, "Global Variable Inlining"),
        OptimizationPass(mem2reg, "Memory-to-Register Promotion"),
        OptimizationPass(naive_dce, "Dead Code Elimination (post mem2reg)"),
        OptimizationPass(rearrange_in_rpo, "Reverse Post-Order Block Rearrangement"),
        OptimizationPass(mir_builder, "MIR Construction"),
        OptimizationPass(naive_dce, "Dead Code Elimination (post MIR)"),
        OptimizationPass(liveness_analysis, "Liveness Analysis"),
    ],
    # These presets are for debugging purposes and may not be compatible with the backend
    "ir_only": [],
    "mem2reg": [
        OptimizationPass(mem2reg, "Memory-to-Register Promotion"),
    ],
    "unreachable": [
        OptimizationPass(mem2reg, "Memory-to-Register Promotion"),
        OptimizationPass(remove_unreachable, "Remove Unreachable Blocks"),
    ],
    "sccp": [
        OptimizationPass(mem2reg, "Memory-to-Register Promotion"),
        OptimizationPass(naive_dce, "Dead Code Elimination (post mem2reg)"),
        OptimizationPass(sparse_conditional_constant_propagation, "Sparse Conditional Constant Propagation"),
        OptimizationPass(remove_unreachable, "Remove Unreachable Blocks"),
        OptimizationPass(naive_dce, "Dead Code Elimination (post SCCP)"),
    ],
    "gvn_pre": [
        OptimizationPass(mem2reg, "Memory-to-Register Promotion"),
        OptimizationPass(naive_dce, "Dead Code Elimination (post mem2reg)"),
        OptimizationPass(remove_critical_edge, "Remove Critical Edges"),
        OptimizationPass(gvn_pre, "Global Value Numbering - Partial Redundancy Elimination"),
        OptimizationPass(copy_propagation, "Copy Propagation"),
        OptimizationPass(naive_dce, "Dead Code Elimination (post GVN)"),
    ]
}
```