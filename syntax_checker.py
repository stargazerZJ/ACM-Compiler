import antlr4
from antlr_generated.MxParserVisitor import MxParserVisitor
from antlr_generated.MxParser import MxParser

class SyntaxChecker(MxParserVisitor):
    def __init__(self):
        super().__init__()

    def visitFile_Input(self, ctx: MxParser.File_InputContext):
        return self.visitChildren(ctx)

    def visitFunction_Definition(self, ctx: MxParser.Function_DefinitionContext):
        line_number = ctx.start.line
        print(f"Visiting function definition at line {line_number}: {ctx.function_Argument().Identifier().getText()}")
        return self.visitChildren(ctx)

    def visitFunction_Param_List(self, ctx: MxParser.Function_Param_ListContext):
        return self.visitChildren(ctx)

    def visitFunction_Argument(self, ctx: MxParser.Function_ArgumentContext):
        return self.visitChildren(ctx)

    def visitClass_Definition(self, ctx: MxParser.Class_DefinitionContext):
        return self.visitChildren(ctx)

    def visitClass_Ctor_Function(self, ctx: MxParser.Class_Ctor_FunctionContext):
        return self.visitChildren(ctx)

    def visitClass_Content(self, ctx: MxParser.Class_ContentContext):
        return self.visitChildren(ctx)

    def visitStmt(self, ctx: MxParser.StmtContext):
        return self.visitChildren(ctx)

    def visitBlock_Stmt(self, ctx: MxParser.Block_StmtContext):
        return self.visitChildren(ctx)

    def visitSimple_Stmt(self, ctx: MxParser.Simple_StmtContext):
        return self.visitChildren(ctx)

    def visitBranch_Stmt(self, ctx: MxParser.Branch_StmtContext):
        return self.visitChildren(ctx)

    def visitIf_Stmt(self, ctx: MxParser.If_StmtContext):
        return self.visitChildren(ctx)


if __name__ == '__main__':
    from antlr_generated.MxLexer import MxLexer
    test_file_path = "./testcases/sema/basic-package/basic-1.mx"
    input_stream = antlr4.FileStream(test_file_path)
    lexer = MxLexer(input_stream)
    token_stream = antlr4.CommonTokenStream(lexer)
    parser = MxParser(token_stream)
    tree = parser.file_Input()
    checker = SyntaxChecker()
    checker.visit(tree)