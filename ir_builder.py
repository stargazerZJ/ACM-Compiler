import antlr4
from antlr_generated.MxParserVisitor import MxParserVisitor
from antlr_generated.MxParser import MxParser
from type import TypeBase, FunctionType, ArrayType, ClassType, builtin_functions, builtin_types
from scope import Scope, GlobalScope, ScopeBase
from syntax_error import MxSyntaxError, ThrowingErrorListener
from syntax_recorder import SyntaxRecorder, VariableInfo


class IRBuilder(MxParserVisitor):
    """Demo code (for now)"""
    recorder: SyntaxRecorder

    def __init__(self, recorder: SyntaxRecorder):
        super().__init__()
        self.recorder = recorder

    def visitAtom(self, ctx: MxParser.AtomContext):
        try:
            variable_info = self.recorder.get_typed_info(ctx, VariableInfo)
            print(f"Got variable_info \"{variable_info.ir_name}\" in symbol \"{ctx.getText()}\"")
        except AttributeError:
            print(f"No variable_info found in symbol \"{ctx.getText()}\"")


if __name__ == '__main__':
    from antlr_generated.MxLexer import MxLexer
    from syntax_checker import SyntaxChecker
    import sys

    test_file_path = "./testcases/sema/scope-package/scope-1.mx"
    input_stream = antlr4.FileStream(test_file_path, encoding='utf-8')
    # input_stream = antlr4.StdinStream(encoding='utf-8')
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
        print(f"Standardized error message: {e.standardize()}", file=sys.stderr)
        print(e.standardize())
        exit(1)

    ir_builder = IRBuilder(recorder)
    ir_builder.visit(tree)
    print("IR building passed", file=sys.stderr)
