import antlr4

from antlr_generated.MxParser import MxParser
from antlr_generated.MxParserVisitor import MxParserVisitor
from ir_utils import IRLoad, IRStore, IRAlloca, IRBinOp, IRIcmp, BBExit, BlockChain, BuilderStack, IRModule, \
    IRFunction, IRCall, IRClass, IRMalloc, IRGetElementPtr
from ir_renamer import renamer
from syntax_error import MxSyntaxError, ThrowingErrorListener
from syntax_recorder import SyntaxRecorder, VariableInfo, FunctionInfo
from type import TypeBase, builtin_types, InternalPtrType, FunctionType


class ExprInfoBase:
    """Reference types (class, array) are not yet supported"""
    typ: TypeBase
    ir_name: str

    def __init__(self, typ: TypeBase, ir_name: str):
        self.typ = typ
        self.ir_name = ir_name

    def llvm(self):
        return self.ir_name

    def to_operand(self, chain: BlockChain) -> "ExprInfoBase":
        """Convert to value or immediate"""
        raise NotImplementedError()

    def to_bool_flow(self, chain: BlockChain) -> "ExprBoolFlow":
        """Convert to boolean flow"""
        raise NotImplementedError()


class ExprValue(ExprInfoBase):
    """ir_name is the value itself"""

    def to_operand(self, chain: BlockChain) -> "ExprValue":
        return self

    def to_bool_flow(self, chain: BlockChain) -> "ExprBoolFlow":
        true_exits, false_exits = chain.branch(self.llvm())
        return ExprBoolFlow(builtin_types["bool"], true_exits, false_exits)


class ExprPtr(ExprInfoBase):
    """ir_name is the pointer to the value"""
    value_name_hint: str | None

    def __init__(self, typ: TypeBase, ir_name: str, value_name_hint: str = None):
        super().__init__(typ, ir_name)
        self.value_name_hint = value_name_hint

    def load(self, chain: BlockChain) -> ExprValue:
        new_name = renamer.get_name(self.value_name_hint)
        chain.add_cmd(IRLoad(new_name, self.ir_name, self.typ.ir_name))
        return ExprValue(self.typ, new_name)

    def to_operand(self, chain: BlockChain) -> ExprValue:
        return self.load(chain)

    def to_bool_flow(self, chain: BlockChain) -> "ExprBoolFlow":
        return self.load(chain).to_bool_flow(chain)


class ExprImm(ExprInfoBase):
    """value is the immediate value"""
    value: int | bool

    def __init__(self, typ: TypeBase, value: int | bool):
        super().__init__(typ, "invalid")
        self.value = value

    def llvm(self):
        return str(self.value).lower()

    def to_operand(self, chain: BlockChain) -> "ExprImm":
        return self

    def to_bool_flow(self, chain: BlockChain) -> "ExprBoolFlow":
        if self.value:
            return ExprBoolFlow(builtin_types["bool"], chain.jump(), [])
        else:
            return ExprBoolFlow(builtin_types["bool"], [], chain.jump())


class ExprBoolFlow(ExprInfoBase):
    """true_exits are the exits when the condition is true, false_exits are the exits when the condition is false"""
    true_exits: list[BBExit]
    false_exits: list[BBExit]

    def __init__(self, typ: TypeBase, true_exits: list[BBExit], false_exits: list[BBExit]):
        super().__init__(typ, "invalid")
        self.true_exits = true_exits
        self.false_exits = false_exits

    def llvm(self):
        return "invalid"

    def to_operand(self, chain: BlockChain) -> ExprInfoBase:
        if not self.true_exits or not self.false_exits:
            chain.set_exits(self.true_exits + self.false_exits)
            return ExprImm(builtin_types["bool"], not self.false_exits)
        var_name = renamer.get_name("%.cond")
        phi_chain = BlockChain.phi_from_bool_flow(var_name, self.true_exits, self.false_exits)
        chain.set_exits(phi_chain.exits)
        return ExprValue(builtin_types["bool"], var_name)

    def to_bool_flow(self, chain: BlockChain) -> "ExprBoolFlow":
        return self

    def flows(self):
        return self.true_exits, self.false_exits

    def concentrate(self, chain: BlockChain):
        """Continue the flow regardless of the condition"""
        chain.set_exits(self.true_exits)
        chain.merge_exits(self.false_exits)


class ExprFunc(ExprInfoBase):
    function_info: FunctionInfo
    this: ExprInfoBase | None

    def __init__(self, function_info: FunctionInfo, this: ExprInfoBase = None):
        super().__init__(function_info.ret_type, function_info.ir_name)
        self.function_info = function_info
        self.this = this


class IRBuilder(MxParserVisitor):
    """Demo code (for now)"""
    recorder: SyntaxRecorder
    stack: BuilderStack
    ir_module: IRModule

    def __init__(self, recorder: SyntaxRecorder):
        super().__init__()
        self.recorder = recorder
        self.stack = BuilderStack()

    def visitFile_Input(self, ctx: MxParser.File_InputContext):
        self.ir_module = IRModule()
        self.visitChildren(ctx)
        return self.ir_module

    def visitClass_Definition(self, ctx: MxParser.Class_DefinitionContext):
        class_name = ctx.Identifier().getText()
        class_info = self.recorder.get_class_info(class_name)
        self.ir_module.classes.append(IRClass(class_info))
        self.visitChildren(ctx)

    def visitFunction_Definition(self, ctx: MxParser.Function_DefinitionContext):
        return self.visit_function_definition(ctx)

    def visitClass_Ctor_Function(self, ctx: MxParser.Class_Ctor_FunctionContext):
        return self.visit_function_definition(ctx)

    def visit_function_definition(self, ctx: MxParser.Function_DefinitionContext | MxParser.Class_Ctor_FunctionContext):
        function_info = self.recorder.get_typed_info(ctx, FunctionInfo)
        chain = BlockChain(function_info.name)
        for local_var in function_info.local_vars:
            chain.add_cmd(IRAlloca(local_var.pointer_name(), local_var.type.ir_name))
        for param_name, param_type in zip(function_info.param_ir_names, function_info.param_types):
            chain.add_cmd(IRStore(param_name + ".ptr", param_name + ".param", param_type.ir_name))
        self.stack.push(chain)
        self.visitChildren(ctx)
        self.stack.pop()
        if chain.has_exits():
            if function_info.ir_name == "@main":
                chain.ret("i32", "0")
            else:
                if function_info.ret_type == builtin_types["void"]:
                    chain.ret("void")
                else:
                    # mark the exits of the function as unreachable
                    chain.jump()
        self.ir_module.functions.append(IRFunction(function_info, chain))

    def visitSimple_Stmt(self, ctx: MxParser.Simple_StmtContext):
        if ctx.expression():
            info: ExprInfoBase = self.visit(ctx.expression())
            if isinstance(info, ExprBoolFlow):
                info.concentrate(self.stack.top_chain())

    def visitAtom(self, ctx: MxParser.AtomContext):
        variable_info = self.recorder.get_typed_info(ctx, VariableInfo)
        if isinstance(variable_info.type, FunctionType):
            function_info = self.recorder.get_function_info(variable_info.ir_name)
            return ExprFunc(function_info)
        return ExprPtr(variable_info.type, variable_info.pointer_name(), variable_info.value_name_hint())

    def visitLiteral_Constant(self, ctx: MxParser.Literal_ConstantContext):
        if ctx.Number():
            return ExprImm(builtin_types["int"], int(ctx.Number().getText()))
        elif ctx.True_():
            return ExprImm(builtin_types["bool"], True)
        elif ctx.False_():
            return ExprImm(builtin_types["bool"], False)
        else:
            # Null
            raise NotImplementedError("Null is not yet supported")

    def visitBracket(self, ctx: MxParser.BracketContext):
        return self.visit(ctx.l)

    def visitBinary(self, ctx: MxParser.BinaryContext):
        if ctx.op.text == "&&" or ctx.op.text == "||":
            return self.visit_logic_expr(ctx)
        lhs: ExprInfoBase = self.visit(ctx.l)
        chain = self.stack.top_chain()
        if ctx.op.text == '=':
            assert isinstance(lhs, ExprPtr)
            rhs: ExprInfoBase = self.visit(ctx.r)
            rhs_value = rhs.to_operand(chain)
            chain.add_cmd(IRStore(lhs.ir_name, rhs_value.llvm(), lhs.typ.ir_name))
            return lhs
        arith_ops = {
            "+": "add",
            "-": "sub",
            "*": "mul",
            "/": "sdiv",
            "%": "srem",
            "<<": "shl",
            ">>": "ashr",
            "&": "and",
            "|": "or",
            "^": "xor"
        }
        if ctx.op.text in arith_ops:
            if lhs.typ == builtin_types["int"]:
                op_ir_name = arith_ops[ctx.op.text]
                lhs_value = lhs.to_operand(chain)
                rhs: ExprInfoBase = self.visit(ctx.r)
                rhs_value = rhs.to_operand(chain)
                new_name = renamer.get_name_from_ctx(f"%.{op_ir_name}", ctx)
                chain.add_cmd(IRBinOp(new_name, op_ir_name, lhs_value.llvm(), rhs_value.llvm(), lhs.typ.ir_name))
                return ExprValue(lhs.typ, new_name)
            else:
                # string concatenation
                raise NotImplementedError("String concatenation is not yet supported")
        compare_ops = {
            "==": "eq",
            "!=": "ne",
            "<": "slt",
            ">": "sgt",
            "<=": "sle",
            ">=": "sge"
        }
        if ctx.op.text in compare_ops:
            if lhs.typ == builtin_types["int"] or lhs.typ == builtin_types["bool"] or lhs.typ == InternalPtrType():
                op_ir_name = compare_ops[ctx.op.text]
                lhs_value = lhs.to_operand(chain)
                rhs: ExprInfoBase = self.visit(ctx.r)
                rhs_value = rhs.to_operand(chain)
                new_name = renamer.get_name_from_ctx(f"%.{op_ir_name}", ctx)
                chain.add_cmd(IRIcmp(new_name, op_ir_name, lhs.typ.ir_name, lhs_value.llvm(), rhs_value.llvm()))
                return ExprValue(builtin_types["bool"], new_name)
            elif lhs.typ == builtin_types["string"]:
                raise NotImplementedError("String comparison is not yet supported")

    def visit_logic_expr(self, ctx: MxParser.BinaryContext):
        """&& and ||"""
        lhs: ExprInfoBase = self.visit(ctx.l)
        chain = self.stack.top_chain()
        lhs_true, lhs_false = lhs.to_bool_flow(chain).flows()
        if ctx.op.text == "&&":
            if lhs_true:
                rhs_chain = BlockChain("and_rhs", lhs_true, allow_attach=True)
                self.stack.push(rhs_chain)
                rhs: ExprInfoBase = self.visit(ctx.r)
                self.stack.pop()
                rhs_true, rhs_false = rhs.to_bool_flow(rhs_chain).flows()
                true_exits = rhs_true
                false_exits = BlockChain.merge_exit_lists(lhs_false + rhs_false)
            else:
                true_exits = []
                false_exits = lhs_false
        else:
            # ||
            if lhs_false:
                rhs_chain = BlockChain("or_rhs", lhs_false, allow_attach=True)
                self.stack.push(rhs_chain)
                rhs: ExprInfoBase = self.visit(ctx.r)
                self.stack.pop()
                rhs_true, rhs_false = rhs.to_bool_flow(rhs_chain).flows()
                true_exits = BlockChain.merge_exit_lists(lhs_true + rhs_true)
                false_exits = rhs_false
            else:
                true_exits = lhs_true
                false_exits = []
        return ExprBoolFlow(builtin_types["bool"], true_exits, false_exits)

    def visitFunction(self, ctx: MxParser.FunctionContext):
        chain = self.stack.top_chain()
        func: ExprFunc = self.visit(ctx.l)
        info = func.function_info
        args = []
        if info.is_member:
            this: ExprInfoBase = func.this
            this_value = this.to_operand(chain)
            args.append(this_value.llvm())
        if ctx.expr_List():
            for expr in ctx.expr_List().expression():
                arg: ExprInfoBase = self.visit(expr)
                arg_value = arg.to_operand(chain)
                args.append(arg_value.llvm())
        if info.ret_type == builtin_types["void"]:
            chain.add_cmd(IRCall("", info, args))
            return ExprValue(builtin_types["void"], "")
        else:
            new_name = renamer.get_name_from_ctx("%.call", ctx)
            chain.add_cmd(IRCall(new_name, info, args))
            return ExprValue(info.ret_type, new_name)

    def visitNew_Type(self, ctx: MxParser.New_TypeContext):
        chain = self.stack.top_chain()
        if ctx.BasicTypes():
            element_type = builtin_types[ctx.BasicTypes().getText()]
            if ctx.new_Index():
                # new int[10][]
                raise NotImplementedError("arrays are not yet supported")
            else:
                # new int[][] { {1, 2}, {3, 4} }
                raise NotImplementedError("arrays are not yet supported")
        else:
            if ctx.new_Index():
                # new A[10]
                raise NotImplementedError("arrays are not yet supported")
            else:
                # new A()
                class_name = ctx.Identifier().getText()
                class_info = self.recorder.get_class_info(class_name)
                class_internal_type = self.recorder.get_typed_info(ctx, VariableInfo).type  # internal pointer type
                new_name = renamer.get_name_from_ctx(f"%.new.{class_name}", ctx)
                chain.add_cmd(IRMalloc(new_name, class_info))
                if class_info.ctor:
                    chain.add_cmd(IRCall("", class_info.ctor, [new_name]))
                return ExprValue(class_internal_type, new_name)

    def visitMember(self, ctx: MxParser.MemberContext):
        chain = self.stack.top_chain()
        obj: ExprInfoBase = self.visit(ctx.l)
        assert isinstance(obj.typ, InternalPtrType)
        class_info = self.recorder.get_class_info(obj.typ.pointed_to.name)
        member_info = class_info.get_member(ctx.Identifier().getText())
        if isinstance(member_info, VariableInfo):
            obj_pointer_value = obj.to_operand(chain)
            new_name = renamer.get_name_from_ctx(f"%.member.{member_info.ir_name}", ctx)
            new_ptr_name = new_name + ".ptr"
            new_value_name = new_name + ".val"
            chain.add_cmd(
                IRGetElementPtr(new_ptr_name, class_info, obj_pointer_value.llvm(), member=ctx.Identifier().getText()))
            return ExprPtr(member_info.type, new_ptr_name, new_value_name)
        else:
            # Function
            return ExprFunc(member_info, obj)

    def visitFlow_Stmt(self, ctx: MxParser.Flow_StmtContext):
        chain = self.stack.top_chain()
        if ctx.Break():
            exits = chain.jump()
            self.stack.collect_breaks(exits)
        elif ctx.Continue():
            exits = chain.jump()
            self.stack.collect_continues(exits)
        else:
            # Return
            if not ctx.expression():
                chain.ret("void")
            else:
                expr: ExprInfoBase = self.visit(ctx.expression())
                operand = expr.to_operand(chain)
                chain.ret(operand.typ.ir_name, operand.llvm())

    def visitBranch_Stmt(self, ctx: MxParser.Branch_StmtContext):
        chain = self.stack.top_chain()
        exits_in = chain.jump()
        if_ctx = ctx.if_Stmt()
        else_exits, next_exits = self.visit_if_stmt(exits_in, if_ctx.expression(), if_ctx.suite())
        chain.set_exits(next_exits)
        for elif_ctx in ctx.else_if_Stmt():
            if not else_exits:
                # Skip unreachable code
                return
            else_exits, next_exits = self.visit_if_stmt(else_exits, elif_ctx.expression(), elif_ctx.suite())
            chain.merge_exits(next_exits)
        if else_exits and ctx.else_Stmt():
            else_chain_name = renamer.get_name_from_ctx("else", ctx.else_Stmt())
            else_chain = BlockChain(else_chain_name, else_exits, allow_attach=True)
            self.stack.push(else_chain)
            self.visit(ctx.else_Stmt().suite())
            self.stack.pop()
            chain.merge_exits(else_chain.exits)
        else:
            chain.merge_exits(else_exits)

    def visit_if_stmt(self, exits_in: list[BBExit], expr: MxParser.ExpressionContext, suite: MxParser.SuiteContext) -> \
            tuple[list[BBExit], list[BBExit]]:
        """visit if or elif statements
        :param exits_in: the exits that should be linked to this if statement
        :param expr: the expression to be evaluated
        :param suite: the suite to be executed if the expression is true
        :return: the exits to the **else** suite and the exits to the **next** statements
        """
        chain_name = renamer.get_name_from_ctx("if", expr)
        chain = BlockChain(chain_name, exits_in, allow_attach=True)
        self.stack.push(chain)
        expr_info: ExprInfoBase = self.visit(expr)
        self.stack.pop()
        true_exits, false_exits = expr_info.to_bool_flow(chain).flows()
        if true_exits:
            true_chain = BlockChain(f"{chain_name}.true", true_exits, allow_attach=True)
            self.stack.push(true_chain)
            self.visit(suite)
            self.stack.pop()
            chain.set_exits(true_chain.exits)
        return false_exits, chain.exits

    def visitFor_Stmt(self, ctx: MxParser.For_StmtContext):
        if ctx.initializer:
            self.visit(ctx.initializer)
        name_hint = renamer.get_name_from_ctx("for", ctx)
        self.visit_for_loop(name_hint, ctx.condition, ctx.suite(), ctx.step)

    def visitWhile_Stmt(self, ctx: MxParser.While_StmtContext):
        name_hint = renamer.get_name_from_ctx("while", ctx)
        self.visit_for_loop(name_hint, ctx.expression(), ctx.suite())

    def visit_for_loop(self, name_hint: str,
                       condition: MxParser.ExpressionContext,
                       suite: MxParser.SuiteContext,
                       step: MxParser.ExpressionContext = None):
        if condition:
            condition_info: ExprInfoBase = self.visit(condition)
            true_exits, next_exits = condition_info.to_bool_flow(self.stack.top_chain()).flows()
        else:
            true_exits = self.stack.top_chain().jump()
            next_exits = []
        if true_exits:
            loop_chain = BlockChain(name_hint, true_exits, allow_attach=False)
            if suite:
                self.stack.push(loop_chain, True)
                self.visit(suite)
                breaks, continues = self.stack.pop()
                next_exits += breaks
                loop_chain.merge_exits(continues)
            if loop_chain.has_exits():
                self.stack.push(loop_chain)
                if step:
                    loop_chain.rename(f"{name_hint}.step")
                    self.visit(step)
                if condition:
                    loop_chain.rename(f"{name_hint}.condition")
                    condition_info = self.visit(condition)
                    true_exits2, false_exits2 = condition_info.to_bool_flow(loop_chain).flows()
                    next_exits += false_exits2
                else:
                    # note that the jump destinations are unreachable by default
                    true_exits2 = loop_chain.jump()
                self.stack.pop()
                # if loop_chain.header is not None:
                #     # otherwise, the loop body is empty,
                #     # and we should do nothing to leave the exits unreachable
                loop_chain.add_entrances(true_exits2)
        next_exits = BlockChain.merge_exit_lists(next_exits)
        self.stack.top_chain().set_exits(next_exits)

    def visitBlock_Stmt(self, ctx: MxParser.Block_StmtContext):
        chain = self.stack.top_chain()
        for stmt in ctx.stmt():
            self.visit(stmt)
            if not chain.has_exits():
                return


if __name__ == '__main__':
    from antlr_generated.MxLexer import MxLexer
    from syntax_checker import SyntaxChecker
    import sys

    test_file_path = "./testcases/demo/d7.mx"
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
    ir: IRModule = ir_builder.visit(tree)
    print("IR building passed", file=sys.stderr)
    print(ir.llvm())
