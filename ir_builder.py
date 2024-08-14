import antlr4

from antlr_generated.MxParser import MxParser
from antlr_generated.MxParserVisitor import MxParserVisitor
from ir_utils import renamer, IRLoad, IRStore, IRAlloca, IRBinOp, BBExit, BlockChain, BuilderStack
from syntax_error import MxSyntaxError, ThrowingErrorListener
from syntax_recorder import SyntaxRecorder, VariableInfo
from type import TypeBase, builtin_types, builtin_functions


class InternalPtrType(TypeBase):
    """Internal type for pointers"""
    pointed_to: TypeBase

    def __init__(self, pointed_to: TypeBase):
        super().__init__("ptr", "ptr")
        self.pointed_to = pointed_to


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


class ExprValue(ExprInfoBase):
    """ir_name is the value itself"""

    def to_operand(self, chain: BlockChain) -> "ExprValue":
        return self


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


class ExprImm(ExprInfoBase):
    """value is the immediate value"""
    value: int | bool

    def __init__(self, typ: TypeBase, value: int | bool):
        super().__init__(typ, "invalid")
        self.value = value

    def llvm(self):
        return str(self.value)

    def to_operand(self, chain: BlockChain) -> "ExprImm":
        return self


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
        new_chain = BlockChain("cond.end")
        new_name = renamer.get_name("cond")
        new_chain.phi(new_name, "i1",
                      [(exit_, "1") for exit_ in self.true_exits]
                      + [(exit_, "0") for exit_ in self.false_exits])
        chain.set_exits(new_chain.exits)
        return ExprValue(builtin_types["bool"], new_name)


class IRBuilder(MxParserVisitor):
    """Demo code (for now)"""
    recorder: SyntaxRecorder
    stack: BuilderStack

    def __init__(self, recorder: SyntaxRecorder):
        super().__init__()
        self.recorder = recorder
        self.stack = BuilderStack()

    def visitFunction_Definition(self, ctx: MxParser.Function_DefinitionContext):
        chain = BlockChain("main")
        # TODO: Add allocation for local variables
        self.stack.push(chain)
        self.visitChildren(ctx)
        self.stack.pop()
        if chain.has_exits():
            chain.ret("i32", "0")
        print(chain.llvm())

    def visitAtom(self, ctx: MxParser.AtomContext):
        variable_info = self.recorder.get_typed_info(ctx, VariableInfo)
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

    def visitBinary(self, ctx: MxParser.BinaryContext):
        lhs: ExprInfoBase = self.visit(ctx.l)
        rhs: ExprInfoBase = self.visit(ctx.r)
        chain = self.stack.top_chain()
        if ctx.op.text == '=':
            assert isinstance(lhs, ExprPtr)
            chain.add_cmd(IRStore(lhs.ir_name, rhs.llvm(), lhs.typ.ir_name))
            return lhs
        int_only_ops = {
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
        if ctx.op.text in int_only_ops:
            op_ir_name = int_only_ops[ctx.op.text]
            lhs_value = lhs.to_operand(chain)
            rhs_value = rhs.to_operand(chain)
            new_name = renamer.get_name_from_ctx(f"%.{op_ir_name}", ctx)
            chain.add_cmd(IRBinOp(new_name, op_ir_name, lhs_value.llvm(), rhs_value.llvm(), lhs.typ.ir_name))
            return ExprValue(lhs.typ, new_name)
        if ctx.op.text == '+':
            if lhs.typ == builtin_types["int"]:
                op_ir_name = "add"
                lhs_value = lhs.to_operand(chain)
                rhs_value = rhs.to_operand(chain)
                new_name = renamer.get_name_from_ctx(f"%.{op_ir_name}", ctx)
                chain.add_cmd(IRBinOp(new_name, op_ir_name, lhs_value.llvm(), rhs_value.llvm(), lhs.typ.ir_name))
                return ExprValue(lhs.typ, new_name)
            elif lhs.typ == builtin_types["string"]:
                raise NotImplementedError("String concatenation is not yet supported")




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


if __name__ == '__main__':
    from antlr_generated.MxLexer import MxLexer
    from syntax_checker import SyntaxChecker
    import sys

    test_file_path = "./testcases/demo/d1.mx"
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
