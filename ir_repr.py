# Utility types and functions for LLVM 15 IR generation
from syntax_recorder import FunctionInfo, ClassInfo, builtin_function_infos, internal_array_info, VariableInfo
from type import TypeBase


class IRCmdBase:
    var_def: list[str]
    var_use: list[str]
    live_out: set[str]

    def llvm(self) -> str:
        raise NotImplementedError()


class IRBinOp(IRCmdBase):
    def __init__(self, dest: str, op: str, lhs: str, rhs: str, typ: str):
        self.op = op
        self.var_def = [dest]
        self.var_use = [lhs, rhs]
        self.typ = typ

    @property
    def dest(self): return self.var_def[0]

    @property
    def lhs(self): return self.var_use[0]

    @property
    def rhs(self): return self.var_use[1]

    def llvm(self):
        return f"{self.dest} = {self.op} {self.typ} {self.lhs}, {self.rhs}"


class IRIcmp(IRCmdBase):
    def __init__(self, dest: str, op: str, typ: str, lhs: str, rhs: str):
        self.op = op
        self.var_def = [dest]
        self.var_use = [lhs, rhs]
        self.typ = typ

    @property
    def dest(self): return self.var_def[0]

    @property
    def lhs(self): return self.var_use[0]

    @property
    def rhs(self): return self.var_use[1]

    def llvm(self):
        return f"{self.dest} = icmp {self.op} {self.typ} {self.lhs}, {self.rhs}"


class IRLoad(IRCmdBase):
    def __init__(self, dest: str, src: str, typ: str):
        self.var_def = [dest]
        self.var_use = [src]
        self.typ = typ

    @property
    def dest(self): return self.var_def[0]

    @property
    def src(self): return self.var_use[0]

    def llvm(self):
        return f"{self.dest} = load {self.typ}, ptr {self.src}"


class IRStore(IRCmdBase):
    def __init__(self, dest: str, src: str, typ: str):
        self.var_def = []
        self.var_use = [dest, src]
        self.typ = typ

    @property
    def dest(self): return self.var_use[0]

    @property
    def src(self): return self.var_use[1]

    def llvm(self):
        return f"store {self.typ} {self.src}, ptr {self.dest}"


class IRAlloca(IRCmdBase):
    def __init__(self, dest: str, typ: str):
        self.var_def = [dest]
        self.var_use = []
        self.typ = typ

    @property
    def dest(self): return self.var_def[0]

    def llvm(self):
        return f"{self.dest} = alloca {self.typ}"


class BBExit:
    block: "BasicBlock"
    idx: int

    def __init__(self, block: "BasicBlock", idx: int):
        self.block = block
        self.idx = idx

    def get_dest(self) -> "BasicBlock":
        return self.block.successors[self.idx]

    def llvm(self):
        return self.get_dest().name


class BasicBlock:
    name: str
    cmds: list[IRCmdBase]
    predecessors: list[BBExit]
    successors: list["BasicBlock"]
    index: int
    unreachable_mark: bool
    live_in: set[str]

    def __init__(self, name: str):
        self.name = name
        self.cmds = []
        self.predecessors = []
        self.successors = []
        self.live_in = set()

    def llvm(self):
        ret = f"{self.name}:"
        for cmd in self.cmds:
            ret += f"\n  {cmd.llvm()}"
        ret += "\n"
        return ret

    def add_cmd(self, cmd: IRCmdBase):
        self.cmds.append(cmd)

    def __iter__(self):
        return iter(self.cmds)

    def __hash__(self):
        return hash(self.name)


class UnreachableBlock(BasicBlock):
    def __init__(self):
        super().__init__("unreachable")

    def add_cmd(self, cmd: IRCmdBase):
        pass

    def __iter__(self):
        return iter(())

    def llvm(self):
        return "unreachable:\n  unreachable\n"


unreachable_block = UnreachableBlock()


class IRJump(IRCmdBase):
    def __init__(self, dest: BBExit):
        self.var_def = []
        self.var_use = []
        self.dest = dest

    def llvm(self):
        return f"br label %{self.dest.llvm()}"


class IRBranch(IRCmdBase):
    def __init__(self, cond: str, true_dest: BBExit, false_dest: BBExit):
        self.var_def = []
        self.var_use = [cond]
        self.true_dest = true_dest
        self.false_dest = false_dest

    @property
    def cond(self): return self.var_use[0]

    def llvm(self):
        return f"br i1 {self.cond}, label %{self.true_dest.llvm()}, label %{self.false_dest.llvm()}"


class IRRet(IRCmdBase):
    def __init__(self, typ: str, value: str = ""):
        self.var_def = []
        self.var_use = ["ret_addr", value] if value else ["ret_addr"]
        self.typ = typ

    @property
    def value(self): return self.var_use[1] if len(self.var_use) > 1 else ""

    def llvm(self):
        return f"ret {self.typ} {self.value}".strip()


class IRPhi(IRCmdBase):
    def __init__(self, dest: str, typ: str, values: list[tuple[BasicBlock, str]]):
        self.var_def = [dest]
        self.var_use = [v[1] for v in values]
        self.typ = typ
        self.sources = [v[0] for v in values]

    @property
    def dest(self): return self.var_def[0]

    def llvm(self):
        ret = f"{self.dest} = phi {self.typ} "
        ret += ", ".join(f"[{value}, %{source.name}]" for source, value in zip(self.sources, self.var_use))
        return ret


class IRCall(IRCmdBase):
    def __init__(self, dest: str, func: FunctionInfo, args: list[str]):
        self.var_def = [dest] if dest else []
        self.var_use = args
        self.func = func
        self.typ = func.ret_type.ir_name

    @property
    def dest(self): return self.var_def[0] if self.var_def else ""

    def llvm(self):
        param_list = ", ".join(f"{ty.ir_name} {name}" for ty, name in zip(self.func.param_types, self.var_use))
        return f"{self.dest} = call {self.typ} {self.func.ir_name}({param_list})" if self.dest else f"call {self.typ} {self.func.ir_name}({param_list})"


class IRMalloc(IRCall):
    """Only structs use malloc. Arrays use __newPtrArray, __newIntArray etc."""

    def __init__(self, dest: str, cls: ClassInfo):
        super().__init__(dest, builtin_function_infos["@malloc"], [str(cls.size)])


class IRGetElementPtr(IRCmdBase):
    def __init__(self, dest: str, typ: ClassInfo | TypeBase, ptr: str, arr_index: str = None, member: str = None):
        self.var_def = [dest]
        self.var_use = [ptr, arr_index] if arr_index else [ptr]
        self.typ = typ
        self.member = member

    @property
    def dest(self):
        return self.var_def[0]

    @property
    def ptr(self):
        return self.var_use[0]

    @property
    def arr_index(self):
        return self.var_use[1] if len(self.var_use) > 1 else "0"

    def llvm(self):
        if isinstance(self.typ, ClassInfo):
            member_index = self.typ.get_member_idx(self.member)
            return f"{self.dest} = getelementptr inbounds {self.typ.ir_name}, ptr {self.ptr}, i32 {self.arr_index}, i32 {member_index}"
        elif isinstance(self.typ, TypeBase):
            return f"{self.dest} = getelementptr inbounds {self.typ.ir_name}, ptr {self.ptr}, i32 {self.arr_index}"


class IRGlobal(IRCmdBase):
    def __init__(self, name: str, typ: str, value: str):
        self.var_def = [name]
        self.typ = typ
        self.var_use = [value]

    @property
    def name(self): return self.var_def[0]

    @property
    def value(self): return self.var_use[0]

    def llvm(self):
        return f"{self.name} = global {self.typ} {self.value}"


class IRStr(IRCmdBase):
    """String Literal"""

    def __init__(self, name: str, value: str):
        self.var_def = [name]
        value = value.replace("\\\\", "\\").replace("\\n", "\n").replace("\\\"", '"')
        self.value = value + "\0"
        self.length = len(value)

    @property
    def name(self): return self.var_def[0]

    def llvm(self):
        # only 3 characters need to be escaped in the Mx* language: \n, \ and "
        value_ir = (self.value.replace("\\", "\\5C").replace("\n", "\\0A")
                    .replace("\"", "\\22").replace("\0", "\\00"))
        return f"{self.name} = private unnamed_addr constant [{self.length + 1} x i8] c\"{value_ir}\""


from ir_utils import BlockChain


class IRFunction:
    info: FunctionInfo
    blocks: list[BasicBlock] | None
    var_defs: set[str]

    def __init__(self, info: FunctionInfo, chain: BlockChain = None):
        self.info = info
        self.blocks = chain.collect_blocks() if chain is not None else None

    def llvm(self):
        if self.is_declare():
            param_str = ", ".join(f"{ty.ir_name}" for ty in self.info.param_types)
            return f"declare {self.info.ret_type.ir_name} {self.info.ir_name}({param_str})"
        else:
            param_str = ", ".join(
                f"{ty.ir_name} {name}.param" for ty, name in zip(self.info.param_types, self.info.param_ir_names))
            body = "\n".join(block.llvm() for block in self.blocks)
            return f"define {self.info.ret_type.ir_name} {self.info.ir_name}({param_str}) {{\n{body}}}\n"

    def is_declare(self):
        return self.blocks is None


class IRClass(ClassInfo):
    def __init__(self, info: ClassInfo):
        super().__init__(info.ir_name)
        self.members = info.members
        self.size = info.size
        self.ctor = info.ctor

    def llvm(self):
        ret = f"{self.ir_name} = type {{"
        ret += ", ".join(member.type.ir_name for member in self.members.values() if isinstance(member, VariableInfo))
        ret += "}"
        return ret


class IRModule:
    functions: list[IRFunction]
    classes: list[IRClass]
    globals: list[IRGlobal]
    strings: list[IRStr]

    def __init__(self):
        self.functions = [IRFunction(func) for func in builtin_function_infos.values()]
        self.classes = [IRClass(internal_array_info)]
        self.globals = []
        self.strings = []

    def llvm(self):
        classes = "\n".join(cls.llvm() for cls in self.classes)
        global_vars = "\n".join(var.llvm() for var in self.globals)
        strings = "\n".join(string.llvm() for string in self.strings)
        functions = "\n".join(func.llvm() for func in self.functions)
        return f"{classes}\n{global_vars}\n{strings}\n{functions}"

    def for_each_function_definition(self, opt):
        for function in self.functions:
            if not function.is_declare():
                opt(function)
