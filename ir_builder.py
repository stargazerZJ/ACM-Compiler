import antlr4

from antlr_generated.MxParser import MxParser
from antlr_generated.MxParserVisitor import MxParserVisitor
from ir_renamer import renamer
from ir_utils import IRLoad, IRStore, IRAlloca, IRBinOp, IRIcmp, BBExit, BlockChain, BuilderStack, IRModule, \
    IRFunction, IRCall, IRClass, IRMalloc, IRGetElementPtr, IRGlobal, IRStr
from syntax_error import MxSyntaxError, ThrowingErrorListener
from syntax_recorder import SyntaxRecorder, VariableInfo, FunctionInfo, internal_array_info, builtin_function_infos
from type import TypeBase, builtin_types, InternalPtrType, FunctionType, ArrayType


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
    value: int | bool | None

    def __init__(self, typ: TypeBase, value: int | bool | None):
        super().__init__(typ, "invalid")
        self.value = value

    def llvm(self):
        return str(self.value).lower() if self.value is not None else "null"

    def to_operand(self, chain: BlockChain) -> "ExprImm":
        return self

    def to_bool_flow(self, chain: BlockChain) -> "ExprBoolFlow":
        if self.value:
            return ExprBoolFlow(builtin_types["bool"], chain.jump(), [])
        else:
            return ExprBoolFlow(builtin_types["bool"], [], chain.jump())

    @staticmethod
    def default_value(typ: TypeBase) -> "ExprImm":
        if typ == builtin_types["int"]:
            return ExprImm(typ, 0)
        elif typ == builtin_types["bool"]:
            return ExprImm(typ, False)
        elif typ == builtin_types["string"]:
            return ExprImm(typ, None)
        elif isinstance(typ, InternalPtrType):
            return ExprImm(typ, None)
        else:
            raise NotImplementedError()


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


class ExprArr(ExprInfoBase):
    ptr: ExprInfoBase
    size: ExprInfoBase

    def __init__(self, ptr: ExprInfoBase, size: ExprInfoBase):
        super().__init__(ptr.typ, ptr.ir_name)
        self.ptr = ptr
        self.size = size

    def to_operand(self, chain: BlockChain) -> "ExprInfoBase":
        return self.ptr.to_operand(chain)

    def llvm(self):
        return self.ptr.llvm()


class IRBuilder(MxParserVisitor):
    recorder: SyntaxRecorder
    stack: BuilderStack
    ir_module: IRModule

    def __init__(self, recorder: SyntaxRecorder):
        super().__init__()
        self.recorder = recorder
        self.stack = BuilderStack()

    def visitFile_Input(self, ctx: MxParser.File_InputContext):
        self.ir_module = IRModule()
        for child in ctx.children:
            if not isinstance(child, MxParser.Variable_DefinitionContext):
                # global variable definition will be visited in the main function
                self.visit(child)
        return self.ir_module

    def visitClass_Definition(self, ctx: MxParser.Class_DefinitionContext):
        class_name = ctx.Identifier().getText()
        class_info = self.recorder.get_class_info(class_name)
        self.ir_module.classes.append(IRClass(class_info))
        class_internal_type = self.recorder.get_typed_info(ctx, VariableInfo).type  # internal pointer type
        assert isinstance(class_internal_type, InternalPtrType)
        self.stack.enter_class_scope(class_internal_type)
        if ctx.class_Ctor_Function():
            self.visitClass_Ctor_Function(ctx.class_Ctor_Function()[0])
        for function in ctx.function_Definition():
            self.visitFunction_Definition(function)
        self.stack.exit_class_scope()

    def visitFunction_Definition(self, ctx: MxParser.Function_DefinitionContext):
        return self.visit_function_definition(ctx)

    def visitClass_Ctor_Function(self, ctx: MxParser.Class_Ctor_FunctionContext):
        return self.visit_function_definition(ctx)

    def visit_function_definition(self, ctx: MxParser.Function_DefinitionContext | MxParser.Class_Ctor_FunctionContext):
        function_info = self.recorder.get_typed_info(ctx, FunctionInfo)
        self.stack.enter_function(function_info)
        chain = BlockChain(function_info.name)
        self.stack.push(chain)
        for local_var in function_info.local_vars:
            chain.add_cmd(IRAlloca(local_var.pointer_name(), local_var.type.ir_name))
        if function_info.ir_name == "@main":
            # visit global variable definitions
            global_ctx: MxParser.File_InputContext = ctx.parentCtx
            for definition in global_ctx.variable_Definition():
                self.visitVariable_Definition(definition)
        if function_info.ret_type.is_array():
            self.ir_module.globals.append(IRGlobal(function_info.ir_name + ".size.ptr", "i32", "0"))
        for param_name, param_type in zip(function_info.param_ir_names, function_info.param_types):
            chain.add_cmd(IRStore(param_name + ".ptr", param_name + ".param", param_type.ir_name))
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
        self.stack.exit_function()
        self.ir_module.functions.append(IRFunction(function_info, chain))

    def visitVariable_Definition(self, ctx: MxParser.Variable_DefinitionContext):
        chain = self.stack.top_chain()
        for init_stmt in ctx.init_Stmt():
            variable_info = self.recorder.get_typed_info(init_stmt, VariableInfo)
            if init_stmt.expression():
                expr: ExprInfoBase = self.visit(init_stmt.expression())
                value = expr.to_operand(chain)
            else:
                expr = ExprImm.default_value(variable_info.type)
                value = expr
            is_global = variable_info.ir_name.startswith("@")
            size_value = ExprImm(builtin_types["int"], 0)
            if (is_global and not isinstance(value, ExprImm)) or (not is_global and init_stmt.expression()):
                chain.add_cmd(IRStore(variable_info.pointer_name(), value.llvm(), variable_info.type.ir_name))
                if expr.typ.is_array():
                    size_value = expr.size.to_operand(chain)
                    size_info = variable_info.arr_size_info()
                    if not (is_global and isinstance(size_value, ExprImm)):
                        chain.add_cmd(IRStore(size_info.pointer_name(), size_value.llvm(), size_info.type.ir_name))
            if is_global:
                value = value if isinstance(value, ExprImm) else ExprImm.default_value(variable_info.type)
                self.ir_module.globals.append(
                    IRGlobal(variable_info.pointer_name(), variable_info.type.ir_name, value.llvm()))
                if variable_info.type.is_array():
                    size_info = variable_info.arr_size_info()
                    size_value = size_value if isinstance(size_value, ExprImm) else ExprImm(builtin_types["int"], 0)
                    self.ir_module.globals.append(
                        IRGlobal(size_info.pointer_name(), size_info.type.ir_name, size_value.llvm()))

    def visitAtom(self, ctx: MxParser.AtomContext):
        variable_info = self.recorder.get_typed_info(ctx, VariableInfo)
        is_this_member = variable_info.is_this_member()
        this_value = ExprValue(self.stack.get_this_type(), "%this.param") if is_this_member else None
        if isinstance(variable_info.type, FunctionType):
            function_info = self.recorder.get_function_info(variable_info.type.ir_name)
            return ExprFunc(function_info, this_value)
        if not is_this_member:
            ptr = ExprPtr(variable_info.type, variable_info.pointer_name(), variable_info.value_name_hint())
            if variable_info.type.is_array():
                size_info = variable_info.arr_size_info()
                return ExprArr(ptr, ExprPtr(size_info.type, size_info.pointer_name(), size_info.value_name_hint()))
            return ptr
        else:
            chain = self.stack.top_chain()
            class_info = self.recorder.get_class_info(self.stack.get_this_type().pointed_to.name)
            new_name = renamer.get_name_from_ctx(variable_info.ir_name, ctx)
            new_ptr_name = new_name + ".ptr"
            new_value_name = new_name + ".val"
            chain.add_cmd(IRGetElementPtr(new_ptr_name, class_info, "%this.param", member=ctx.Identifier().getText()))
            ptr = ExprPtr(variable_info.type, new_ptr_name, new_value_name)
            if variable_info.type.is_array():
                size_ptr_name = new_name + ".size.ptr"
                size_value_name = new_name + ".size.val"
                chain.add_cmd(
                    IRGetElementPtr(size_ptr_name, class_info, "%this.param",
                                    member=ctx.Identifier().getText() + ".size"))
                return ExprArr(ptr, ExprPtr(builtin_types["int"], size_ptr_name, size_value_name))
            return ptr

    def visitThis(self, ctx: MxParser.ThisContext):
        return ExprValue(self.stack.get_this_type(), "%this.param")

    def visitLiteral_Constant(self, ctx: MxParser.Literal_ConstantContext):
        if ctx.Number():
            return ExprImm(builtin_types["int"], int(ctx.Number().getText()))
        elif ctx.True_():
            return ExprImm(builtin_types["bool"], True)
        elif ctx.False_():
            return ExprImm(builtin_types["bool"], False)
        elif ctx.Cstring():
            string_info = self.recorder.get_typed_info(ctx, VariableInfo)
            string = ctx.getText()[1:-1]
            self.ir_module.strings.append(IRStr(string_info.ir_name, string))
            return ExprValue(string_info.type, string_info.ir_name)
        else:
            # Null
            return ExprImm(builtin_types["null"], None)

    def visitBracket(self, ctx: MxParser.BracketContext):
        return self.visit(ctx.l)

    def visitBinary(self, ctx: MxParser.BinaryContext):
        if ctx.op.text == "&&" or ctx.op.text == "||":
            return self.visit_logic_expr(ctx)
        lhs: ExprInfoBase = self.visit(ctx.l)
        chain = self.stack.top_chain()
        if ctx.op.text == '=':
            assert isinstance(lhs, ExprPtr) or isinstance(lhs, ExprArr)
            rhs: ExprInfoBase = self.visit(ctx.r)
            rhs_value = rhs.to_operand(chain)
            chain.add_cmd(IRStore(lhs.ir_name, rhs_value.llvm(), lhs.typ.ir_name))
            if rhs.typ.is_array():
                # `array = null` does not need special treatment, and won't go to this branch
                assert isinstance(rhs, ExprArr) and isinstance(lhs, ExprArr)
                size_value = rhs.size.to_operand(chain)
                chain.add_cmd(IRStore(lhs.size.ir_name, size_value.llvm(), lhs.size.typ.ir_name))
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
            lhs_value = lhs.to_operand(chain)
            rhs: ExprInfoBase = self.visit(ctx.r)
            rhs_value = rhs.to_operand(chain)
            if lhs.typ == builtin_types["int"]:
                op_ir_name = arith_ops[ctx.op.text]
                new_name = renamer.get_name_from_ctx(f"%.{op_ir_name}", ctx)
                chain.add_cmd(IRBinOp(new_name, op_ir_name, lhs_value.llvm(), rhs_value.llvm(), lhs.typ.ir_name))
                return ExprValue(lhs.typ, new_name)
            else:
                # string concatenation
                str_add_info = builtin_function_infos["@string_add"]
                new_name = renamer.get_name_from_ctx(f"%.str.add", ctx)
                chain.add_cmd(IRCall(new_name, str_add_info, [lhs_value.llvm(), rhs_value.llvm()]))
                return ExprValue(builtin_types["string"].internal_type(), new_name)

        compare_ops = {
            "==": "eq",
            "!=": "ne",
            "<": "slt",
            ">": "sgt",
            "<=": "sle",
            ">=": "sge"
        }
        if ctx.op.text in compare_ops:
            op_ir_name = compare_ops[ctx.op.text]
            lhs_value = lhs.to_operand(chain)
            rhs: ExprInfoBase = self.visit(ctx.r)
            rhs_value = rhs.to_operand(chain)
            if not lhs.typ.is_string():
                new_name = renamer.get_name_from_ctx(f"%.{op_ir_name}", ctx)
                chain.add_cmd(IRIcmp(new_name, op_ir_name, lhs.typ.ir_name, lhs_value.llvm(), rhs_value.llvm()))
            else:
                new_name = renamer.get_name_from_ctx(f"%.str.{op_ir_name}", ctx)
                call_name = new_name + ".call"
                strcmp_info = builtin_function_infos["@strcmp"]
                chain.add_cmd(IRCall(call_name, strcmp_info, [lhs_value.llvm(), rhs_value.llvm()]))
                chain.add_cmd(IRIcmp(new_name, op_ir_name, strcmp_info.ret_type.ir_name, call_name, "0"))
            return ExprValue(builtin_types["bool"], new_name)

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

    def visitUnary(self, ctx: MxParser.UnaryContext):
        chain = self.stack.top_chain()
        if ctx.l:
            # a ++ or a --
            lhs: ExprPtr = self.visit(ctx.l)
            old_value = lhs.to_operand(chain)
            op = "add" if ctx.op.text == "++" else "sub"
            new_name = renamer.get_name_from_ctx(f"%.post_{op}", ctx)
            chain.add_cmd(IRBinOp(new_name, op, old_value.llvm(), "1", lhs.typ.ir_name))
            chain.add_cmd(IRStore(lhs.ir_name, new_name, lhs.typ.ir_name))
            return old_value  # return the value before the operation
        else:
            # ++ a, -- a, ! a, ~ a, + a, - a
            if ctx.op.text in ("++", "--"):
                ptr: ExprPtr = self.visit(ctx.r)
                old_value = ptr.to_operand(chain)
                op = "add" if ctx.op.text == "++" else "sub"
                new_name = renamer.get_name_from_ctx(f"%.pre_{op}", ctx)
                chain.add_cmd(IRBinOp(new_name, op, old_value.llvm(), "1", old_value.typ.ir_name))
                chain.add_cmd(IRStore(ptr.ir_name, new_name, ptr.typ.ir_name))
                return ptr  # return the pointer
            elif ctx.op.text == "!":
                value: ExprInfoBase = self.visit(ctx.r)
                flow = value.to_bool_flow(chain)
                true_exits, false_exits = flow.flows()
                return ExprBoolFlow(builtin_types["bool"], false_exits, true_exits)  # swap true and false
            elif ctx.op.text == "~":
                value: ExprInfoBase = self.visit(ctx.r)
                value_operand = value.to_operand(chain)
                new_name = renamer.get_name_from_ctx("%.not", ctx)
                bitmask = "-1"  # only i32 is supported by this operation in this language
                chain.add_cmd(IRBinOp(new_name, "xor", value_operand.llvm(), bitmask, value_operand.typ.ir_name))
                return ExprValue(value_operand.typ, new_name)
            elif ctx.op.text == "-":
                value: ExprInfoBase = self.visit(ctx.r)
                value_operand = value.to_operand(chain)
                new_name = renamer.get_name_from_ctx("%.neg", ctx)
                chain.add_cmd(IRBinOp(new_name, "sub", "0", value_operand.llvm(), value_operand.typ.ir_name))
                return ExprValue(value_operand.typ, new_name)
            elif ctx.op.text == "+":
                return self.visit(ctx.r)

    def visitTernary(self, ctx: MxParser.TernaryContext):
        chain = self.stack.top_chain()
        condition: ExprInfoBase = self.visit(ctx.cond)
        true_exits, false_exits = condition.to_bool_flow(chain).flows()
        if not true_exits:
            chain.set_exits(false_exits)
            return self.visit(ctx.false_expr)
        elif not false_exits:
            chain.set_exits(true_exits)
            return self.visit(ctx.true_expr)
        true_chain = BlockChain("ternary_true", true_exits, allow_attach=True)
        self.stack.push(true_chain)
        true_result: ExprInfoBase = self.visit(ctx.l)
        self.stack.pop()
        false_chain = BlockChain("ternary_false", false_exits, allow_attach=True)
        self.stack.push(false_chain)
        false_result: ExprInfoBase = self.visit(ctx.r)
        self.stack.pop()
        if true_result.typ == builtin_types["bool"]:
            true_true, true_false = true_result.to_bool_flow(true_chain).flows()
            false_true, false_false = false_result.to_bool_flow(false_chain).flows()
            true_exits = BlockChain.merge_exit_lists(true_true + false_true)
            false_exits = BlockChain.merge_exit_lists(true_false + false_false)
            return ExprBoolFlow(builtin_types["bool"], true_exits, false_exits)
        elif true_result.typ == builtin_types["void"]:
            true_chain.merge_exits(false_chain.exits)
            chain.merge_exits(true_chain.exits)
            return ExprValue(builtin_types["void"], "")
        else:
            true_value = true_result.to_operand(true_chain)
            # concentrate is called to ensure at least one block is created
            # this is a conservative approach compared to that in logical expressions, if branches, and loops
            # the main consideration is that the ternary operator is added to the language later and is not used frequently
            true_chain.concentrate()
            true_exits = true_chain.jump()
            false_value = false_result.to_operand(false_chain)
            false_chain.concentrate()
            false_exits = false_chain.jump()
            new_name = renamer.get_name_from_ctx("%.ternary", ctx)
            result_chain = BlockChain("ternary_result", allow_attach=True)
            result_chain.phi(new_name, true_value.typ.ir_name,
                             [(bb_exit, true_value.llvm()) for bb_exit in true_exits] +
                             [(bb_exit, false_value.llvm()) for bb_exit in false_exits])
            chain.merge_exits(result_chain.exits)
            return ExprValue(true_value.typ, new_name)

    def visitFunction(self, ctx: MxParser.FunctionContext):
        chain = self.stack.top_chain()
        func: ExprFunc = self.visit(ctx.l)
        info = func.function_info
        args = []
        if info.ir_name == "%.arr.size":
            return func.this.size
        if info.is_member:
            this: ExprInfoBase = func.this
            this_value = this.to_operand(chain)
            args.append(this_value.llvm())
        if ctx.expr_List():
            param_type_iter = iter(info.param_types)
            if info.is_member: next(param_type_iter)
            for expr in ctx.expr_List().expression():
                arg: ExprInfoBase = self.visit(expr)
                arg_value = arg.to_operand(chain)
                args.append(arg_value.llvm())
                param_type = next(param_type_iter)
                if arg.typ.is_array():
                    arg_size_value = arg.size.to_operand(chain)
                    args.append(arg_size_value.llvm())
                    next(param_type_iter)
                elif param_type.is_array():
                    args.append("0")
                    next(param_type_iter)
        if info.ret_type == builtin_types["void"]:
            chain.add_cmd(IRCall("", info, args))
            return ExprValue(builtin_types["void"], "")
        else:
            new_name = renamer.get_name_from_ctx("%.call", ctx)
            chain.add_cmd(IRCall(new_name, info, args))
            value = ExprValue(info.ret_type, new_name)
            if info.ret_type.is_array():
                size_name = new_name + ".size"
                chain.add_cmd(IRLoad(size_name, info.ir_name + ".size.ptr", "i32"))
                return ExprArr(value, ExprValue(builtin_types["int"], size_name))
            return value

    def visitNew_Type(self, ctx: MxParser.New_TypeContext):
        chain = self.stack.top_chain()
        if ctx.BasicTypes():
            if ctx.new_Index():
                # new int[10][]
                return self.visit_new_array_expr(ctx)
            else:
                # new int[][] { {1, 2}, {3, 4} }
                raise NotImplementedError("array literals are not yet supported")
        else:
            if ctx.new_Index():
                # new A[10]
                return self.visit_new_array_expr(ctx)
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

    def visit_new_array_expr(self, ctx: MxParser.New_TypeContext):
        chain = self.stack.top_chain()
        array_internal_type: InternalPtrType = self.recorder.get_typed_info(ctx, VariableInfo).type
        array_type: ArrayType = array_internal_type.pointed_to
        assigned_sizes = self.visitNew_Index(ctx.new_Index())
        assigned_len = len(assigned_sizes)
        if assigned_len == array_type.dimension:
            malloc_type = array_type.element_type.name # one of int, bool and ptr
        else:
            # e.g. int[2][3][]
            malloc_type = "arr_ptr"
        if assigned_len > 2:
            raise NotImplementedError("arrays like int[2][3][4][] are not yet supported")
        function_name = f"@__new_{malloc_type}_{assigned_len}d_array__"
        function_info = self.recorder.get_function_info(function_name)
        arr_ptr_name = renamer.get_name_from_ctx(f"%.new.{array_type.element_type.name}.arr", ctx)
        chain.add_cmd(IRCall(arr_ptr_name, function_info, [size.llvm() for size in assigned_sizes]))
        return ExprArr(ExprValue(array_internal_type, arr_ptr_name), assigned_sizes[0])


    def visitNew_Index(self, ctx: MxParser.New_IndexContext):
        chain = self.stack.top_chain()
        ret = []
        for expression in ctx.good:
            size: ExprInfoBase = self.visit(expression)
            ret.append(size.to_operand(chain))
        return ret

    # noinspection PyUnboundLocalVariable
    def visitSubscript(self, ctx: MxParser.SubscriptContext):
        chain = self.stack.top_chain()
        obj: ExprInfoBase = self.visit(ctx.l)
        dimension = obj.typ.pointed_to.dimension
        for sub_ctx in ctx.sub:
            obj_pointer_value = obj.to_operand(chain)
            sub:ExprInfoBase = self.visit(sub_ctx)
            sub_value = sub.to_operand(chain)
            new_name = renamer.get_name_from_ctx(f"%.subscript", ctx)
            new_ptr_name = new_name + ".ptr"
            new_value_name = new_name + ".val"
            if dimension > 1:
                chain.add_cmd(
                    IRGetElementPtr(new_ptr_name, internal_array_info, obj_pointer_value.llvm(), arr_index=sub_value.llvm(), member=".data"))
                old_obj_pointer_value = obj_pointer_value
                obj = ExprPtr(obj.typ.pointed_to.subscript().internal_type(), new_ptr_name, new_value_name)
                dimension -= 1
            else:
                elem_type = obj_pointer_value.typ.pointed_to.element_type
                chain.add_cmd(
                    IRGetElementPtr(new_ptr_name, elem_type, obj_pointer_value.llvm(), arr_index=sub_value.llvm()))
                return ExprPtr(elem_type, new_ptr_name, new_value_name)
        size_name = new_name + ".size"
        size_ptr_name = size_name + ".ptr"
        size_value_name = size_name + ".val"
        chain.add_cmd(
            IRGetElementPtr(size_ptr_name, internal_array_info, old_obj_pointer_value.llvm(), arr_index=sub_value.llvm(), member=".size"))
        return ExprArr(obj, ExprPtr(builtin_types["int"], size_ptr_name, size_value_name))

    def visitMember(self, ctx: MxParser.MemberContext):
        chain = self.stack.top_chain()
        obj: ExprInfoBase = self.visit(ctx.l)
        assert isinstance(obj.typ, InternalPtrType)
        class_info = self.recorder.get_class_info(obj.typ.pointed_to.name)
        member_name = ctx.Identifier().getText()
        member_info = class_info.get_member(member_name)
        if isinstance(member_info, VariableInfo):
            obj_pointer_value = obj.to_operand(chain)
            new_name = renamer.get_name_from_ctx(f"%.member.{member_info.ir_name}", ctx)
            new_ptr_name = new_name + ".ptr"
            new_value_name = new_name + ".val"
            chain.add_cmd(
                IRGetElementPtr(new_ptr_name, class_info, obj_pointer_value.llvm(), member=member_name))
            ptr = ExprPtr(member_info.type, new_ptr_name, new_value_name)
            if member_info.type.is_array():
                size_member_info = class_info.get_member(member_name + ".size")
                size_name = new_name + ".size"
                size_ptr_name = size_name + ".ptr"
                size_vale_name = size_name + ".val"
                chain.add_cmd(IRGetElementPtr(
                    size_ptr_name, class_info, obj_pointer_value.llvm(), member=member_name + ".size"
                ))
                return ExprArr(ptr, ExprPtr(size_member_info.type, size_ptr_name, size_vale_name))
            return ptr
        else:
            # Function
            return ExprFunc(member_info, obj)

    def visitSimple_Stmt(self, ctx: MxParser.Simple_StmtContext):
        if ctx.expression():
            info: ExprInfoBase = self.visit(ctx.expression())
            if isinstance(info, ExprBoolFlow):
                info.concentrate(self.stack.top_chain())

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
                if expr.typ.is_array():
                    function = self.stack.get_current_function()
                    size_value = expr.size.to_operand(chain)
                    chain.add_cmd(IRStore(function.ir_name + ".size.ptr", size_value.llvm(), size_value.typ.ir_name))
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

    # test_file_path = "./testcases/demo/d11.mx"
    # input_stream = antlr4.FileStream(test_file_path, encoding='utf-8')
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
        print(f"Standardized error message: {e.standardize()}", file=sys.stderr)
        print(e.standardize())
        exit(1)

    ir_builder = IRBuilder(recorder)
    ir: IRModule = ir_builder.visit(tree)
    print("IR building passed", file=sys.stderr)
    print(ir.llvm())
