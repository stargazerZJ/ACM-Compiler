from ir_repr import IRBlock, IRFunction


class ASMCmdBase:
    comment: str | None

    def __init__(self, comment: str = None):
        self.comment = comment

    def with_comment(self, asm_code: str) -> str:
        if self.comment is not None:
            return asm_code + "\t\t; " + self.comment
        return asm_code

    def riscv(self):
        raise NotImplementedError()


class ASMComment(ASMCmdBase):
    def riscv(self):
        return "; " + self.comment


class ASMLabel(ASMCmdBase):
    label: str

    def __init__(self, label: str, comment: str = None):
        super().__init__(comment)
        self.label = label

    def riscv(self):
        return self.with_comment(self.label + ":")


class ASMCmd(ASMCmdBase):
    op: str
    dest: str
    operands: list[str]

    def __init__(self, op: str, dest: str, operands: list[str], comment: str = None):
        super().__init__(comment)
        self.op = op
        self.dest = dest
        self.operands = operands

    def riscv(self):
        return self.with_comment(self.op + " " + self.dest + ", " + ", ".join(self.operands))


class ASMMemOp(ASMCmdBase):
    op: str
    reg: str
    relative: bool  # relative to sp
    addr: str  # offset or symbol

    def __init__(self, op: str, reg: str, relative: bool, addr: str, comment: str = None):
        super().__init__(comment)
        self.op = op
        self.reg = reg
        self.relative = relative
        self.addr = addr

    def riscv(self):
        if self.relative:
            return self.with_comment(self.op + " " + self.reg + ", " + self.addr + "(sp)")
        return self.with_comment(self.op + " " + self.reg + ", " + self.addr)


class ASMFlowControl(ASMCmdBase):
    op: str  # branch type (if exists)
    operands: list[str]
    dest: list[str]
    can_fallthrough: bool
    extend_range: bool  # use 3 commands "br, j, j" to enlarge branch range

    def __init__(self, op: str, operands: list[str], dest: list[str], comment: str = None):
        super().__init__(comment)
        self.op = op
        self.operands = operands
        self.dest = dest
        self.can_fallthrough = False
        self.extend_range = False

    @staticmethod
    def jump(dest: str, comment: str = None):
        return ASMFlowControl("j", [], [dest], comment)

    @staticmethod
    def branch(op: str, operands: list[str], dest: str, comment: str = None):
        return ASMFlowControl(op, operands, [dest], comment)

    @staticmethod
    def ret(self, comment: str = None):
        return ASMFlowControl("ret", [], [], comment)

    @staticmethod
    def tail(self, function: str, comment: str = None):
        return ASMFlowControl("tail", [], [function], comment)

    def riscv(self):
        if self.op == "ret":
            return self.with_comment("ret")
        if self.op == "tail":
            return self.with_comment("tail " + self.dest[0])
        if self.op == "j":
            if self.can_fallthrough:
                return self.with_comment("j " + self.dest[0])
            else:
                return self.with_comment("")
        # branch
        if self.extend_range:
            return self.with_comment(self.op + " " + ", ".join(self.operands) + ", .+4" +
                                     "\n\tj " + self.dest[0] + "\n1:\tj " + self.dest[1])
        elif self.can_fallthrough:
            return self.with_comment(self.op + " " + ", ".join(self.operands) + ", " + self.dest[1])
        return self.with_comment(self.op + " " + ", ".join(self.operands) + ", " + self.dest[1] +
                                 "\n\tj " + self.dest[1])


class ASMCall(ASMCmdBase):
    function: str

    def __init__(self, function: str, comment: str = None):
        super().__init__(comment)
        self.function = function

    def riscv(self):
        return self.with_comment("call " + self.function)


class ASMBlock:
    label: str
    ir_block: BasicBlock | None
    cmds: list[ASMCmdBase]
    flow_control: ASMFlowControl
    predecessors: list["ASMBlock"]
    successors: list["ASMBlock"]

    def __init__(self, label: str, IRBlock: BasicBlock = None):
        self.label = label
        self.ir_block = IRBlock
        self.cmds = []

    def add_cmd(self, cmd: ASMCmdBase):
        self.cmds.append(cmd)

    def set_flow_control(self, flow_control: ASMFlowControl):
        self.flow_control = flow_control

    def riscv(self):
        label = ASMLabel(self.label)
        if self.ir_block is not None:
            label.comment = self.ir_block.name
        return "\n\t".join(
            [label.riscv()] +
            [cmd.riscv() for cmd in self.cmds] +
            [self.flow_control.riscv()]
        )


class ASMFunction:
    label: str
    ir_function: IRFunction
    blocks: list[ASMBlock]
    stack_size: int  # stack size in bytes

    def __init__(self, label: str, ir_function: IRFunction):
        self.label = label
        self.ir_function = ir_function
        self.blocks = []
        self.stack_size = 0

    def riscv(self):
        label = f".globl {self.label}\n{self.label}:"
        return label + "\n\t".join(
            block.riscv() for block in self.blocks
        ) + "\n"

class ASMGlobal(ASMCmdBase):
    name: str
    value: int

    def __init__(self, name: str, value: int, comment: str = None):
        super().__init__(comment)
        self.name = name
        self.value = value

    def riscv(self):
        return self.with_comment(f".globl {self.name}\n{self.name}: .word {self.value}")

class ASMStr(ASMGlobal):
    def __init__(self, name: str, value: int, comment: str = None):
        super().__init__(name, value, comment)

    def riscv(self):
        return self.with_comment(f".globl {self.name}\n{self.name}: .asciz \"{self.value}\"")


class ASMModule:
    functions: list[ASMFunction]
    globals: list[ASMGlobal]
    strs: list[ASMStr]
    builtin_functions: str

    def __init__(self):
        self.functions = []
        self.globals = []
        self.strs = []

    def set_builtin_functions(self, builtin_functions: str):
        self.builtin_functions = builtin_functions

    def riscv(self):
        asm = "\t.text\n"
        asm += "\n".join(function.riscv() for function in self.functions)
        asm += "\n\t.data\n"
        asm += "\n".join(global_.riscv() for global_ in self.globals)
        asm += "\n\t.rodata\n"
        asm += "\n".join(str_.riscv() for str_ in self.strs)
        if hasattr(self, "builtin_functions"):
            asm += self.builtin_functions
        return asm