from typing import Union

from ir_repr import IRBlock, IRFunction


class ASMCmdBase:
    comment: str | None

    def __init__(self, comment: str = None):
        self.comment = comment

    def with_comment(self, asm_code: str) -> str:
        if self.comment is not None:
            return asm_code + "\t\t# " + self.comment
        return asm_code

    def riscv(self):
        raise NotImplementedError()

    def __repr__(self):
        return f'ASM("{self.riscv()}")'


class ASMComment(ASMCmdBase):
    def riscv(self):
        return "# " + self.comment


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

    def __init__(self, op: str, dest: str, operands: list, comment: str = None):
        super().__init__(comment)
        self.op = op
        self.dest = dest
        self.operands = [str(operand) for operand in operands]

    def riscv(self):
        return self.with_comment(self.op + " " + self.dest + ", " + ", ".join(self.operands))


class ASMMove(ASMCmd):
    def __init__(self, dest: str, src: str, comment: str = None):
        super().__init__("mv", dest, [src], comment)


class ASMMemOp(ASMCmdBase):
    op: str
    reg: str
    relative: str | None
    addr: str | int  # offset or symbol
    tmp_reg: str | None

    def __init__(self, op: str, reg: str, addr: str | int, relative: str = None, tmp_reg: str = None,
                 comment: str = None):
        super().__init__(comment)
        self.op = op
        self.reg = reg
        self.relative = relative
        self.addr = addr
        self.tmp_reg = tmp_reg

    def riscv(self):
        if self.relative is not None:
            return self.with_comment(self.op + " " + self.reg + ", " + str(self.addr) + f"({self.relative})")
        cmd = self.op + " " + self.reg + ", " + self.addr
        if self.tmp_reg is not None:
            cmd += ", " + self.tmp_reg
        return self.with_comment(cmd)


class ASMFlowControl(ASMCmdBase):
    op: str  # branch type (if exists)
    operands: list[str]
    block: Union["ASMBlock", None]  # destinations are recorded here
    can_fallthrough: bool
    extend_range: bool  # use 3 commands "br, j, j" to enlarge branch range
    function: "ASMFunction"  # used to get the stack size
    tail_function: str
    flipped: bool

    def __init__(self, op: str, operands: list[str], block: Union["ASMBlock", None], comment: str = None):
        super().__init__(comment)
        self.op = op
        self.operands = operands
        self.block = block
        self.can_fallthrough = False
        self.extend_range = False
        self.flipped = False

    @staticmethod
    def jump(block: "ASMBlock", comment: str = None):
        return ASMFlowControl("j", [], block, comment)

    @staticmethod
    def branch(op: str, operands: list[str], block: "ASMBlock", comment: str = None):
        return ASMFlowControl(op, operands, block, comment)

    @staticmethod
    def ret(function: "ASMFunction", comment: str = None):
        ret = ASMFlowControl("ret", [], None, comment)
        ret.__setattr__("function", function)
        return ret

    @staticmethod
    def tail(self, function: str, comment: str = None):
        tail = ASMFlowControl("tail", [], None, comment)
        tail.__setattr__("tail_function", function)
        return tail

    def flip(self):
        self.flipped = not self.flipped
        self.can_fallthrough = False
        self.op = {
            "blt": "bge",
            "bge": "blt",
            "bltu": "bgeu",
            "bgeu": "bltu",
            "beq": "bne",
            "bne": "beq",
            "bnez": "beqz",
            "beqz": "bnez",
            "ble": "bgt",
            "bgt": "ble",
            "blez": "bgtz",
            "bgtz": "blez"
        }[self.op]

    def riscv(self):
        if self.op == "ret":
            if self.function.stack_size != 0:
                cmd = "addi sp, sp, " + str(self.function.stack_size) + "\n\tret"
            else:
                cmd = "ret"
            return self.with_comment(cmd)
        if self.op == "tail":
            return self.with_comment("tail " + self.tail_function)
        if self.op == "j":
            if self.can_fallthrough:
                return self.with_comment("")
            else:
                return self.with_comment("j " + self.block.successors[0].label)
        # branch
        dest = (self.block.successors[0].label, self.block.successors[1].label)
        if self.flipped: dest = (dest[1], dest[0])
        # (false_dest, true_dest)
        if self.extend_range:
            return self.with_comment(self.op + " " + ", ".join(self.operands) + ", .+4" +
                                     "\n\tj " + dest[0] + "\n1:\tj " + dest[1])
        elif self.can_fallthrough:
            return self.with_comment(self.op + " " + ", ".join(self.operands) + ", " + dest[1])
        return self.with_comment(self.op + " " + ", ".join(self.operands) + ", " + dest[1] +
                                 "\n\tj " + dest[0])


class ASMCall(ASMCmdBase):
    function: str

    def __init__(self, function: str, comment: str = None):
        super().__init__(comment)
        self.function = function

    def riscv(self):
        return self.with_comment("call " + self.function)


class ASMBlock:
    label: str
    ir_block: IRBlock | None
    cmds: list[ASMCmdBase]
    flow_control: ASMFlowControl
    predecessors: list["ASMBlock"]
    successors: list["ASMBlock"]

    def __init__(self, label: str, ir_block: IRBlock = None):
        self.label = label
        self.ir_block = ir_block
        self.cmds = []

    def add_cmd(self, *cmds: ASMCmdBase):
        self.cmds.extend(cmds)

    def set_flow_control(self, flow_control: ASMFlowControl):
        self.flow_control = flow_control

    def riscv(self):
        label = ASMLabel(self.label)
        if self.ir_block is not None:
            label.comment = self.ir_block.name
        return "\n\t".join(
            [label.riscv()] +
            [cmd.riscv() for cmd in self.cmds] +
            [self.flow_control.riscv() if hasattr(self, "flow_control") else "# unreachable"]
            # unreachable block has no flow
        )

    def estimated_size(self):
        """Estimated number of instructions when generated to binary"""
        return len(self.cmds) + 2

    def __repr__(self):
        return f'ASMBlock("{self.label}")'


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
        label = f".globl {self.label}\n{self.label}:\t\t# === Function {self.label} ===\n"
        return label + "\n".join(
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
        return self.with_comment(f".globl {self.name}\n{self.name}:\n\t.word {self.value}")


class ASMStr(ASMGlobal):
    value: str

    def __init__(self, name: str, value: str, comment: str = None):
        value = value.rstrip("\0")
        super().__init__(name, value, comment)

    def riscv(self):
        value = (self.value.replace("\\", "\\\\").replace("\n", "\\n")
                 .replace("\"", "\\\""))
        return self.with_comment(f".globl {self.name}\n{self.name}:\n\t.asciz \"{value}\"")


class ASMModule:
    functions: list[ASMFunction]
    globals: list[ASMGlobal]
    strings: list[ASMStr]
    builtin_functions: str

    def __init__(self):
        self.functions = []
        self.globals = []
        self.strings = []

    def set_builtin_functions(self, builtin_functions: str):
        self.builtin_functions = builtin_functions

    def riscv(self):
        asm = "\t.text\n"
        asm += "\n".join(function.riscv() for function in self.functions)
        asm += "\n\t.data\n\t.p2align 2\n"
        asm += "\n".join(global_.riscv() for global_ in self.globals)
        asm += "\n\t.rodata\n\t.p2align 2\n"
        asm += "\n".join(str_.riscv() for str_ in self.strings)
        if hasattr(self, "builtin_functions"):
            asm += "\n\n\t\t# === builtins ===\n"
            asm += self.builtin_functions
        return asm
