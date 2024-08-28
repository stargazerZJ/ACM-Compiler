from ir_repr import BasicBlock


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
    IRBlock: BasicBlock | None
    cmds: list[ASMCmdBase]
    flow_control: ASMFlowControl
    predecessors: list["ASMBlock"]
    successors: list["ASMBlock"]

    def __init__(self, label: str, IRBlock: BasicBlock = None):
        self.label = label
        self.IRBlock = IRBlock
        self.cmds = []

    def add_cmd(self, cmd: ASMCmdBase):
        self.cmds.append(cmd)

    def set_flow_control(self, flow_control: ASMFlowControl):
        self.flow_control = flow_control

    def riscv(self):
        label = ASMLabel(self.label)
        if self.IRBlock is not None:
            label.comment = self.IRBlock.name
        return "\n\t".join(
            [label.riscv()] +
            [cmd.riscv() for cmd in self.cmds] +
            [self.flow_control.riscv()]
        )
