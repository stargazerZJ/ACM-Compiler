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
        if type_ == builtin_types["void"]:
            raise MxSyntaxError("Variable cannot have type void", ctx)
        for init_stmt in ctx.init_Stmt():
            if init_stmt.expression():
                init_type, _ = self.visit(init_stmt.expression())
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
                literal_type, _ = self.visitLiteral_Constant(literal)
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

    def visitBracket(self, ctx: MxParser.BracketContext):
        return self.visit(ctx.l)

    def visitSubscript(self, ctx: MxParser.SubscriptContext):
        l_type, l_assignable = self.visit(ctx.l)
        r_type, _ = self.visit(ctx.r)
        if r_type != builtin_types["int"]:
            raise MxSyntaxError("Subscript should be int", ctx)
        return l_type.subscript(ctx), l_assignable

    def raise_type_error(self, type_: TypeBase, ctx: antlr4.ParserRuleContext):
        raise MxSyntaxError(f"Type error: Operator '{ctx.op.text}' cannot be applied to {type_.name}", ctx)

    def raise_type_error(self, l_type: TypeBase, r_type: TypeBase, ctx: antlr4.ParserRuleContext):
        raise MxSyntaxError(
            f"Type error: Operator '{ctx.op.text}' cannot be applied to {l_type.name} and {r_type.name}", ctx)

    def raise_value_category_error(self, assignable: bool, ctx: antlr4.ParserRuleContext):
        category = "l-value" if assignable else "r-value"
        raise MxSyntaxError(f"Value category error: Cannot assign to a {category}", ctx)

    def visitFunction(self, ctx: MxParser.FunctionContext):
        func = self.scope.get_variable(ctx.Identifier().getText(), ctx)
        return func.call([self.visit(arg)[0] for arg in ctx.expression()], ctx), False

    def visitMember(self, ctx: MxParser.MemberContext):
        l_type, l_assignable = self.visit(ctx.l)
        return l_type.get_member(ctx.Identifier().getText(), ctx), l_assignable

    def visitUnary(self, ctx: MxParser.UnaryContext):
        if ctx.l:
            # a ++ or a --
            l_type, l_assignable = self.visit(ctx.l)
            if l_type != builtin_types["int"]:
                self.raise_type_error(l_type, ctx)
            if not l_assignable:
                self.raise_value_category_error(l_assignable, ctx)
            return l_type, False
        else:
            # ++ a, -- a, ! a, ~ a, + a, - a
            r_type, r_assignable = self.visit(ctx.r)
            if ctx.op.text in ["++", "--"]:
                if r_type != builtin_types["int"]:
                    self.raise_type_error(r_type, ctx)
                if not r_assignable:
                    self.raise_value_category_error(r_assignable, ctx)
                return r_type, True
            if ctx.op.text in ["!", "~"]:
                if r_type != builtin_types["bool"]:
                    self.raise_type_error(r_type, ctx)
                return r_type, False
            if ctx.op.text in ["+", "-"]:
                if r_type != builtin_types["int"]:
                    self.raise_type_error(r_type, ctx)
                return r_type, False

    def visitNew_Type(self, ctx: MxParser.New_TypeContext):
        if ctx.BasicTypes():
            element_type = builtin_types[ctx.BasicTypes().getText()]
            if element_type == builtin_types["void"]:
                raise MxSyntaxError("Cannot create void type", ctx)
            if ctx.new_Index():
                # new int[10][]
                dimensions = self.visitNew_Index(ctx.new_Index())
                return ArrayType(element_type, dimensions), False
            else:
                # new int[][] { {1, 2}, {3, 4} }
                dimensions = len(ctx.Brack_Left_())
                self.visitArray_Literal(ctx.array_Literal(), element_type.name, dimensions)
                return ArrayType(element_type, dimensions), False
        else:
            class_name = ctx.Identifier().getText()
            class_type = self.scope.get_type(class_name, 0, ctx)
            if ctx.new_Index():
                # new A[10]
                dimensions = self.visitNew_Index(ctx.new_Index())
                return ArrayType(class_type, dimensions), False
            else:
                # new A()
                return class_type, False

    def visitNew_Index(self, ctx: MxParser.New_IndexContext):
        for expression in ctx.expression():
            type_, _ = self.visit(expression)
            if type_ != builtin_types["int"]:
                raise MxSyntaxError("Array index should be int", ctx)
        return len(ctx.Brack_Left_())

    def visitBinary(self, ctx: MxParser.BinaryContext):
        l_type, l_assignable = self.visit(ctx.l)
        r_type, _ = self.visit(ctx.r)
        if l_type == builtin_types["void"] or r_type == builtin_types["void"]:
            self.raise_type_error(l_type, r_type, ctx)
        if ctx.op.text == '=':
            if not l_assignable:
                self.raise_value_category_error(l_assignable, ctx)
            if l_type != r_type:
                if r_type != builtin_types["null"]:
                    self.raise_type_error(l_type, r_type, ctx)
                else:
                    if not l_type.can_be_null(ctx):
                        self.raise_type_error(l_type, r_type, ctx)
            return l_type, True
        if ctx.op.text in ["-", "*", "/", "%", "<<", ">>", "&", "|", "^"]:
            if l_type != builtin_types["int"] or r_type != builtin_types["int"]:
                self.raise_type_error(l_type, r_type, ctx)
            return builtin_types["int"], False
        if ctx.op.text == "+":
            if l_type == builtin_types["int"] and r_type == builtin_types["int"]:
                return builtin_types["int"], False
            if l_type == builtin_types["string"] and r_type == builtin_types["string"]:
                return builtin_types["string"], False
            self.raise_type_error(l_type, r_type, ctx)
        if ctx.op.text in ["&&", "||"]:
            if l_type != builtin_types["bool"] or r_type != builtin_types["bool"]:
                self.raise_type_error(l_type, r_type, ctx)
            return builtin_types["bool"], False
        if ctx.op.text in ["<", ">", "<=", ">="]:
            if l_type != r_type and (l_type != builtin_types["int"] or l_type != builtin_types["string"]):
                self.raise_type_error(l_type, r_type, ctx)
            return builtin_types["bool"], False
        if ctx.op.text in ["==", "!="]:
            if l_type != r_type:
                if l_type == builtin_types["null"]:
                    l_type, r_type = r_type, l_type
                if r_type != builtin_types["null"]:
                    self.raise_type_error(l_type, r_type, ctx)
                else:
                    if not l_type.can_be_null(ctx):
                        self.raise_type_error(l_type, r_type, ctx)
            return builtin_types["bool"], False

    def visitF_string(self, ctx: MxParser.F_stringContext):
        for expression in ctx.expression():
            type_, _ = self.visit(expression)
            if type_ != builtin_types["int"] and type_ != builtin_types["string"] and type_ != builtin_types["bool"]:
                raise MxSyntaxError(f"Type error: f-string cannot contain {type_.name}", ctx)
        return builtin_types["string"], False

    def visitLiteral_Constant(self, ctx: MxParser.Literal_ConstantContext):
        if ctx.Number():
            return builtin_types["int"], False
        if ctx.Cstring():
            return builtin_types["string"], False
        if ctx.True_() or ctx.False_():
            return builtin_types["bool"], False
        if ctx.Null():
            return builtin_types["null"], False

    def visitAtom(self, ctx: MxParser.AtomContext):
        # Note: assigning to a function is undefined behavior
        return self.scope.get_variable(ctx.Identifier().getText(), ctx), True

    def visitThis(self, ctx: MxParser.ThisContext):
        return self.scope.get_this_type(), False

    def visitClass_Definition(self, ctx: MxParser.Class_DefinitionContext):
        self.scope.enter_class_scope(ctx.Identifier().getText())
        if ctx.class_Ctor_Function():
            self.visitClass_Ctor_Function(ctx.class_Ctor_Function())
        for function in ctx.function_Definition():
            self.visitFunction_Definition(function)
        self.scope.exit_class_scope()

    def visitFunction_Definition(self, ctx: MxParser.Function_DefinitionContext):
        ret_type = self.scope.get_type(*self.visitTypename(ctx.function_Argument().typename()), ctx)
        self.scope.set_return_type(ret_type)
        self.scope.push_scope()
        for argument in ctx.function_Param_List().function_Argument():
            arg_type = self.scope.get_type(*self.visitTypename(argument.typename()), argument)
            self.scope.add_variable(argument.Identifier().getText(), arg_type, argument)
        self.visitBlock_Stmt(ctx.block_Stmt())
        self.scope.pop_scope()

    def visitClass_Ctor_Function(self, ctx: MxParser.Class_Ctor_FunctionContext):
        self.scope.set_return_type(builtin_types["void"])  # 'return ;' is allowed in constructor
        self.scope.push_scope()
        self.visitBlock_Stmt(ctx.block_Stmt())
        self.scope.pop_scope()

    def visitIf_Stmt(self, ctx: MxParser.If_StmtContext):
        condition_type, _ = self.visit(ctx.expression())
        if condition_type != builtin_types["bool"]:
            raise MxSyntaxError("Condition should be bool", ctx)
        self.visitSuite(ctx.suite())

    def visitElse_if_Stmt(self, ctx: MxParser.Else_if_StmtContext):
        condition_type, _ = self.visit(ctx.expression())
        if condition_type != builtin_types["bool"]:
            raise MxSyntaxError("Condition should be bool", ctx)
        self.visitSuite(ctx.suite())

    def visitSuite(self, ctx: MxParser.SuiteContext):
        if ctx.block_Stmt():
            self.visitBlock_Stmt(ctx.block_Stmt())
        else:
            self.scope.push_scope()
            self.visitStmt(ctx.stmt())
            self.scope.pop_scope()

    def visitFor_Stmt(self, ctx: MxParser.For_StmtContext):
        self.scope.push_scope(is_loop_scope=True)
        if ctx.initializer:
            self.visit(ctx.initializer)
        if ctx.condition:
            condition_type, _ = self.visit(ctx.condition)
            if condition_type != builtin_types["bool"]:
                raise MxSyntaxError("Condition should be bool", ctx)
        if ctx.step:
            self.visit(ctx.step)
        self.visitSuite(ctx.suite())
        self.scope.pop_scope()

    def visitWhile_Stmt(self, ctx: MxParser.While_StmtContext):
        self.scope.push_scope(is_loop_scope=True)
        condition_type, _ = self.visit(ctx.expression())
        if condition_type != builtin_types["bool"]:
            raise MxSyntaxError("Condition should be bool", ctx)
        self.visitSuite(ctx.suite())
        self.scope.pop_scope()

    def visitFlow_Stmt(self, ctx: MxParser.Flow_StmtContext):
        if ctx.Break():
            if not self.scope.can_break_or_continue():
                raise MxSyntaxError("No loop to break", ctx)
        elif ctx.Continue():
            if not self.scope.can_break_or_continue():
                raise MxSyntaxError("No loop to continue", ctx)
        elif ctx.Return():
            if not ctx.expression():
                ret_type = builtin_types["void"]
            else:
                ret_type, _ = self.visit(ctx.expression())
            if ret_type != self.scope.get_return_type():
                raise MxSyntaxError(
                    f"Return type mismatch: expected {self.scope.get_return_type().name}, got {ret_type.name}", ctx)


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
