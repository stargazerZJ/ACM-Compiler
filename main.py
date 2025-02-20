#!/usr/bin/env python3

import sys
import argparse
import antlr4
from pathlib import Path
from typing import List, Callable, Optional
from dataclasses import dataclass

from mxc.backend.asm_builder import ASMBuilder
from mxc.frontend.parser.MxLexer import MxLexer
from mxc.frontend.parser.MxParser import MxParser
from mxc.frontend.semantic.syntax_checker import SyntaxChecker
from mxc.frontend.semantic.syntax_error import MxSyntaxError, ThrowingErrorListener
from mxc.frontend.ir_generation.ir_builder import IRBuilder
from mxc.common.ir_repr import IRModule
from mxc.middle_end.gvn_pre import gvn_pre
from mxc.middle_end.mem2reg import mem2reg
from mxc.middle_end.mir import mir_builder
from mxc.middle_end.liveness_analysis import liveness_analysis
from mxc.middle_end.dce import naive_dce
from mxc.middle_end.globalvar import inline_global_variables
from mxc.middle_end.remove_unreachable import remove_unreachable, copy_propagation
from mxc.middle_end.sccp import sparse_conditional_constant_propagation
from mxc.middle_end.utils import rearrange_in_rpo

@dataclass
class CompilerOptions:
    input_file: Optional[str]
    output_file: str
    dump_ir: bool
    dump_mir: bool
    dump_asm: bool
    optimization_level: str
    syntax_only: bool
    emit_llvm: bool
    judge_mode: bool


class OptimizationPass:
    def __init__(self, func: Callable, name: str, scope: str = "function"):
        self.func = func
        self.name = name
        self.scope = scope  # "function", "block", or "module"

    def apply(self, ir: IRModule):
        if self.scope == "function":
            ir.for_each_function_definition(self.func)
        elif self.scope == "block":
            ir.for_each_block(self.func)
        else:
            self.func(ir)


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
        OptimizationPass(gvn_pre, "Global Value Numbering - Partial Redundancy Elimination"),
        OptimizationPass(copy_propagation, "Copy Propagation"),
    ]
}


def parse_args():
    parser = argparse.ArgumentParser(description="Mx* Compiler")
    parser.add_argument('input', nargs='?', help='Input file (default: stdin)')
    parser.add_argument('-o', '--output', help='Output file (default: a.s)')
    parser.add_argument('-O', '--optimize', choices=OPTIMIZATION_PRESETS.keys(), default='O1',
                        help='Optimization level (default: O1)')
    parser.add_argument('--dump-ir', action='store_true', help='Dump LLVM IR')
    parser.add_argument('--dump-mir', action='store_true', help='Dump MIR')
    parser.add_argument('--dump-asm', action='store_true', help='Dump assembly')
    parser.add_argument('--syntax-only', action='store_true',
                        help='Stop after syntax checking')
    parser.add_argument('--emit-llvm', action='store_true',
                        help='Emit LLVM IR after optimization passes')
    parser.add_argument('--judge-mode', action='store_true',
                        help='Run in online judge mode')

    args = parser.parse_args()

    return CompilerOptions(
        input_file=args.input,
        output_file=args.output or 'a.s',
        dump_ir=args.dump_ir,
        dump_mir=args.dump_mir,
        dump_asm=args.dump_asm,
        optimization_level=args.optimize,
        syntax_only=args.syntax_only,
        emit_llvm=args.emit_llvm,
        judge_mode=args.judge_mode
    )


def compile(options: CompilerOptions):
    # Setup input stream
    if options.input_file and options.input_file != '-':
        input_stream = antlr4.FileStream(options.input_file, encoding='utf-8')
    else:
        input_stream = antlr4.StdinStream(encoding='utf-8')

    # Lexing and Parsing
    lexer = MxLexer(input_stream)
    parser = MxParser(antlr4.CommonTokenStream(lexer))

    error_listener = ThrowingErrorListener()
    lexer.removeErrorListeners()
    lexer.addErrorListener(error_listener)
    parser.removeErrorListeners()
    parser.addErrorListener(error_listener)

    try:
        tree = parser.file_Input()
        checker = SyntaxChecker()
        recorder = checker.visit(tree)
        if options.syntax_only:
            return 0
    except MxSyntaxError as e:
        print(f"Syntax error: {e}", file=sys.stderr)
        print(e.standardize() if options.judge_mode else e)
        return 1

    # IR Generation
    try:
        ir_builder = IRBuilder(recorder)
        ir: IRModule = ir_builder.visit(tree)
    except Exception as e:
        print(f"IR generation failed: {e}", file=sys.stderr)
        return 1

    # Optimizations
    try:
        for opt_pass in OPTIMIZATION_PRESETS[options.optimization_level]:
            print(f"Running {opt_pass.name}...", file=sys.stderr)
            opt_pass.apply(ir)

            # Dump intermediate results if requested
            if options.dump_ir:
                Path("dumps").mkdir(exist_ok=True)
                with open(f"dumps/ir-after-{opt_pass.name}.ll", "w") as f:
                    print(ir.llvm(), file=f)
        if options.emit_llvm:
            print(ir.llvm())
            return 0
    except Exception as e:
        print(f"Optimization failed: {e}", file=sys.stderr)
        return 1

    # Assembly Generation
    try:
        asm_builder = ASMBuilder(ir)
        asm = asm_builder.build()

        with open("./mxc/runtime/builtin.s", 'r') as file:
            asm.set_builtin_functions(file.read())

        if options.dump_asm:
            Path("dumps").mkdir(exist_ok=True)
            with open(f"dumps/final.s", "w") as f:
                print(asm.riscv(), file=f)

        # Write final output
        if options.judge_mode or options.output_file == '-':
            print(asm.riscv())
        else:
            with open(options.output_file, "w") as f:
                print(asm.riscv(), file=f)

    except Exception as e:
        print(f"Assembly generation failed: {e}", file=sys.stderr)
        return 1

    return 0


def main():
    options = parse_args()
    return compile(options)


if __name__ == '__main__':
    sys.exit(main())