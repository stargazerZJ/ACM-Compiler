import antlr4
from antlr_generated.MxParserVisitor import MxParserVisitor
from antlr_generated.MxParser import MxParser
from type import TypeBase, FunctionType, ArrayType, ClassType, builtin_functions, builtin_types
from scope import Scope, GlobalScope, ScopeBase
from syntax_error import MxSyntaxError

class SyntaxChecker(MxParserVisitor):
    scope: Scope

    def __init__(self):
        super().__init__()

    def visitFile_Input(self, ctx: MxParser.File_InputContext):
        global_scope = self.register_class_names_and_functions(ctx)
        self.scope = Scope(global_scope)
        for class_ctx in ctx.class_Definition():
            self.register_class_members(class_ctx)
        return self.visitChildren(ctx)

    def register_class_names_and_functions(self, ctx: MxParser.File_InputContext) -> GlobalScope:
        global_scope = GlobalScope()

        # Register class names
        for class_ctx in ctx.class_Definition():
            class_name = class_ctx.Identifier().getText()
            global_scope.register_class_name(class_name, class_ctx)

        # Register functions
        for func_ctx in ctx.function_Definition():
            func = self.register_function(global_scope, func_ctx)
            global_scope.add_function(func, func_ctx)

        # Check main function
        if "main" not in global_scope.global_functions:
            raise MxSyntaxError("Function 'main' not found", ctx)
        main_func = global_scope.global_functions["main"]
        if main_func.ret_type != builtin_types["int"]:
            raise MxSyntaxError("Function 'main' should return int", ctx)
        if main_func.param_types:
            raise MxSyntaxError("Function 'main' should not have parameters", ctx)

        return global_scope

    def register_function(self, scope: ScopeBase, ctx: MxParser.Function_DefinitionContext) -> FunctionType:
        func_name = ctx.function_Argument().Identifier().getText()
        ret_type = scope.get_type(*self.visitTypename(ctx.function_Argument().typename()), ctx)
        if ctx.function_Param_List():
            param_types = [scope.get_type(*self.visitTypename(ctx.function_Argument().typename()), ctx)
                           for arg in ctx.function_Param_List().function_Argument()]
        else:
            param_types = []
        return FunctionType(func_name, ret_type, param_types)

    def register_class_members(self, ctx: MxParser.Class_DefinitionContext):
        class_name = ctx.Identifier().getText()
        class_type = self.scope.get_type(class_name, 0, ctx)

        # Register member functions
        for func_ctx in ctx.function_Definition():
            func = self.register_function(self.scope, func_ctx)
            class_type.add_member(func.name, func)

        # Register member variables
        for var_ctx in ctx.variable_Definition():
            var_type = self.scope.get_type(*self.visitTypename(var_ctx.typename()), var_ctx)
            for init_stmt in var_ctx.init_Stmt():
                class_type.add_member(init_stmt.Identifier().getText(), var_type)

        # Check constructor if exists
        if ctx.class_Ctor_Function():
            if len(ctx.class_Ctor_Function()) > 1:
                raise MxSyntaxError(f"Class '{class_name}' should have at most one constructor", ctx)
            ctor_ctx = ctx.class_Ctor_Function()[0]
            ctor_name = ctor_ctx.Identifier().getText()
            if ctor_name != class_name:
                raise MxSyntaxError(f"Constructor {ctor_name} should be the same as class name: {class_name}", ctor_ctx)

    def visitVariable_Definition(self, ctx: MxParser.Variable_DefinitionContext):
        typename, dimension = self.visitTypename(ctx.typename())
        type_ = self.scope.get_type(typename, dimension, ctx)
        for init_stmt in ctx.init_Stmt():
            if init_stmt.expression():
                init_type = self.visitExpression(init_stmt.expression())
                if init_type != type_:
                    raise MxSyntaxError(f"Type mismatch: expected {type_.name}, got {init_type.name}", ctx)
            if init_stmt.array_Literal():
                if not isinstance(type_, ArrayType):
                    raise MxSyntaxError(f"Type mismatch: expected {type_.name}, got array", ctx)
                self.visitArray_Literal(init_stmt.array_Literal(), typename, dimension)
            self.scope.add_variable(init_stmt.Identifier().getText(), type_, ctx)

    def visitArray_Literal(self, ctx: MxParser.Array_LiteralContext, typename: str = "", dimension: int = 0):
        if dimension == 0:
            if ctx.array_Literal_List():
                raise MxSyntaxError("Array literal has too many dimensions", ctx)
            for literal in ctx.literal_List().literal():
                literal_type = self.visitLiteral_Constant(literal)
                if literal_type != builtin_types[typename]:
                    raise MxSyntaxError(f"Type mismatch: expected {typename}, got {literal_type.name}", ctx)
        else:
            if not ctx.array_Literal_List():
                raise MxSyntaxError("Array literal has too few dimensions", ctx)
            for literal in ctx.array_Literal_List().array_Literal():
                self.visitArray_Literal(literal, typename, dimension - 1)

    def visitTypename(self, ctx: MxParser.TypenameContext) -> tuple[str, int]:
        typename = ctx.getChild(0).getText()
        dimensions = len(ctx.Brack_Left_())
        return typename, dimensions


if __name__ == '__main__':
    from antlr_generated.MxLexer import MxLexer
    # test_file_path = "./testcases/sema/basic-package/basic-1.mx"
    test_file_path = "./testcases/sema/class-package/class-12.mx"
    input_stream = antlr4.FileStream(test_file_path)
    lexer = MxLexer(input_stream)
    token_stream = antlr4.CommonTokenStream(lexer)
    parser = MxParser(token_stream)
    tree = parser.file_Input()
    checker = SyntaxChecker()
    checker.visit(tree)