#!/usr/bin/env python3

from mxc.backend.asm_builder import ASMBuilder
from mxc.frontend.parser.MxLexer import MxLexer
from mxc.frontend.parser.MxParser import MxParser
from mxc.frontend.semantic.syntax_checker import SyntaxChecker
import sys
import antlr4
from mxc.frontend.semantic.syntax_error import MxSyntaxError, ThrowingErrorListener
from mxc.frontend.ir_generation.ir_builder import IRBuilder
from mxc.common.ir_repr import IRModule
from mxc.middle_end.mem2reg import mem2reg
from mxc.middle_end.mir import mir_builder
from mxc.middle_end.liveness_analysis import liveness_analysis
from mxc.middle_end.dce import naive_dce
from mxc.middle_end.globalvar import inline_global_variables
from mxc.middle_end.utils import rearrange_in_rpo

if __name__ == '__main__':

    if len(sys.argv) == 1:
        # test_file_path = "./testcases/demo/d7.mx"
        test_file_path = "./testcases/codegen/t71.mx"
        input_stream = antlr4.FileStream(test_file_path, encoding='utf-8')
    else:
        input_stream = antlr4.StdinStream(encoding='utf-8')
    lexer = MxLexer(input_stream)
    parser = MxParser(antlr4.CommonTokenStream(lexer))

    # Attach error listeners
    error_listener = ThrowingErrorListener()
    lexer.removeErrorListeners()
    lexer.addErrorListener(error_listener)
    parser.removeErrorListeners()
    parser.addErrorListener(error_listener)

    try:
        tree = parser.file_Input()
        checker = SyntaxChecker()
        recorder = checker.visit(tree)
        print("Syntax check passed", file=sys.stderr)
    except MxSyntaxError as e:
        print(f"Syntax check failed: {e}", file=sys.stderr)
        print(e.standardize())
        exit(1)

    try:
        ir_builder = IRBuilder(recorder)
        ir: IRModule = ir_builder.visit(tree)
        print("IR building done", file=sys.stderr)
    except Exception as e:
        print(f"IR building failed: {e}", file=sys.stderr)
        exit(0)

    try:
        ir.for_each_function_definition(naive_dce)
        print("DCE done", file=sys.stderr)

        ir.for_each_function_definition(inline_global_variables)
        print("Global variable inlining done", file=sys.stderr)

        ir.for_each_function_definition(mem2reg)
        print("M2R done", file=sys.stderr)

        ir.for_each_function_definition(naive_dce)
        print("DCE done", file=sys.stderr)

        ir.for_each_function_definition(rearrange_in_rpo)

        with open("./tmp/output.ll", "w") as f:
            print(ir.llvm(), file=f)
            print("IR output to " + "output.ll", file=sys.stderr)

        ir.for_each_function_definition(mir_builder)
        print("MIR done", file=sys.stderr)

        ir.for_each_function_definition(naive_dce)
        print("DCE done", file=sys.stderr)

        with open("./tmp/output-mir.ll", "w") as f:
            print(ir.llvm(), file=f)
            print("MIR output to " + "output-mir.ll", file=sys.stderr)

        ir.for_each_function_definition(liveness_analysis)
        print("Liveness analysis done", file=sys.stderr)
    except Exception as e:
        print(f"Optimization failed: {e}", file=sys.stderr)
        exit(0)

    try:
        asm_builder = ASMBuilder(ir)
        asm = asm_builder.build()
        with open("./mxc/runtime/builtin.s", 'r') as file:
            builtin_asm = file.read()

        asm.set_builtin_functions(builtin_asm)

        print("ASM building done", file=sys.stderr)
        print(asm.riscv())
        with open("./tmp/output-asm.s", "w") as f:
            print(asm.riscv(), file=f)
            print("ASM output to " + "output-asm.s", file=sys.stderr)
    except Exception as e:
        print(f"ASM building failed: {e}", file=sys.stderr)
        exit(0)