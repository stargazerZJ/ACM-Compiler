# Utility types and functions for LLVM 15 IR generation

from ir_renamer import renamer
from syntax_recorder import FunctionInfo, ClassInfo, builtin_function_infos, internal_array_info, VariableInfo
from type import TypeBase, InternalPtrType


class IRCmdBase:
    def llvm(self) -> str:
        raise NotImplementedError()


class IRBinOp(IRCmdBase):
    def __init__(self, dest: str, op: str, lhs: str, rhs: str, typ: str):
        self.op = op
        self.dest = dest
        self.lhs = lhs
        self.rhs = rhs
        self.typ = typ

    def llvm(self):
        return f"{self.dest} = {self.op} {self.typ} {self.lhs}, {self.rhs}"


class IRIcmp(IRCmdBase):
    def __init__(self, dest: str, op: str, typ: str, lhs: str, rhs: str):
        self.op = op
        self.dest = dest
        self.lhs = lhs
        self.rhs = rhs
        self.typ = typ

    def llvm(self):
        return f"{self.dest} = icmp {self.op} {self.typ} {self.lhs}, {self.rhs}"


class IRLoad(IRCmdBase):
    def __init__(self, dest: str, src: str, typ: str):
        self.dest = dest
        self.src = src
        self.typ = typ

    def llvm(self):
        return f"{self.dest} = load {self.typ}, ptr {self.src}"


class IRStore(IRCmdBase):
    def __init__(self, dest: str, src: str, typ: str):
        self.dest = dest
        self.src = src
        self.typ = typ

    def llvm(self):
        return f"store {self.typ} {self.src}, ptr {self.dest}"


class IRAlloca(IRCmdBase):
    def __init__(self, dest: str, typ: str):
        self.dest = dest
        self.typ = typ

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

    def __init__(self, name: str):
        self.name = name
        self.cmds = []
        self.predecessors = []
        self.successors = []

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

    def llvm(self):
        return "unreachable:\n  unreachable\n"


unreachable_block = UnreachableBlock()


class IRJump(IRCmdBase):
    def __init__(self, dest: BBExit):
        self.dest = dest

    def llvm(self):
        return f"br label %{self.dest.llvm()}"


class IRBranch(IRCmdBase):
    def __init__(self, cond: str, true_dest: BBExit, false_dest: BBExit):
        self.cond = cond
        self.true_dest = true_dest
        self.false_dest = false_dest

    def llvm(self):
        return f"br i1 {self.cond}, label %{self.true_dest.llvm()}, label %{self.false_dest.llvm()}"


class IRRet(IRCmdBase):
    def __init__(self, typ: str, value: str = ""):
        self.typ = typ
        self.value = value

    def llvm(self):
        return f"ret {self.typ} {self.value}"


class IRPhi(IRCmdBase):
    def __init__(self, dest: str, typ: str, values: list[tuple[BBExit, str]]):
        self.dest = dest
        self.typ = typ
        self.values = values

    def llvm(self):
        ret = f"{self.dest} = phi {self.typ} "
        for value in self.values:
            ret += f"[{value[1]}, %{value[0].block.name}], "
        ret = ret[:-2]
        return ret


class IRCall(IRCmdBase):
    def __init__(self, dest: str, func: FunctionInfo, args: list[str]):
        self.dest = dest
        self.func = func
        self.typ = func.ret_type.ir_name
        self.args = args

    def llvm(self):
        if self.dest == "":
            return f"call {self.typ} {self.func.ir_name}({', '.join(f'{ty.ir_name} {name}' for ty, name in zip(self.func.param_types, self.args))})"
        return f"{self.dest} = call {self.typ} {self.func.ir_name}({', '.join(f'{ty.ir_name} {name}' for ty, name in zip(self.func.param_types, self.args))})"


class IRMalloc(IRCall):
    """Only structs use malloc. Arrays use __newPtrArray, __newIntArray etc."""

    def __init__(self, dest: str, cls: ClassInfo):
        super().__init__(dest, builtin_function_infos["@malloc"], [str(cls.size)])


class IRGetElementPtr(IRCmdBase):
    def __init__(self, dest: str, typ: ClassInfo | TypeBase, ptr: str, arr_index: str = None, member: str = None):
        self.dest = dest
        self.typ = typ
        self.ptr = ptr
        self.arr_index = arr_index or "0"
        self.member = member

    def llvm(self):
        if isinstance(self.typ, ClassInfo):
            member_index = self.typ.get_member_idx(self.member)
            return f"{self.dest} = getelementptr inbounds {self.typ.ir_name}, ptr {self.ptr}, i32 {self.arr_index}, i32 {member_index}"
        elif isinstance(self.typ, TypeBase):
            return f"{self.dest} = getelementptr inbounds {self.typ.ir_name}, ptr {self.ptr}, i32 {self.arr_index}"


class IRGlobal:
    def __init__(self, name: str, typ: str, value: str):
        self.name = name
        self.typ = typ
        self.value = value

    def llvm(self):
        return f"{self.name} = global {self.typ} {self.value}"


class IRStr:
    """String Literal"""
    name: str
    value: str
    length: int

    def __init__(self, name: str, value: str):
        self.name = name
        value = value.replace("\\\\", "\\").replace("\\n", "\n").replace("\\\"", '"')
        self.value = value + "\0"
        self.length = len(value)

    def llvm(self):
        # only 3 characters need to be escaped in the Mx* language: \n, \ and "
        value_ir = (self.value.replace("\\", "\\5C").replace("\n", "\\0A")
                    .replace("\"", "\\22").replace("\0", "\\00"))
        return f"{self.name} = private unnamed_addr constant [{self.length + 1} x i8] c\"{value_ir}\""


class BlockChain:
    """Chain of basic blocks, helper class for IRGenerator"""
    header: BasicBlock | None
    exits: list[BBExit]  # Exits that should be linked to the next chain
    name_hint: str

    def __init__(self, name_hint: str = "chain_header", from_exits: list[BBExit] = None, allow_attach: bool = False):
        self.header = None
        self.exits = []
        self.name_hint = name_hint
        if from_exits is not None:
            self.exits = from_exits
        if allow_attach and self.exits:
            if self.try_attach():
                self.header = self.exits[0].block
        else:
            self.concentrate()

    def rename(self, name: str):
        self.name_hint = name

    @staticmethod
    def link_exits_to_block(exits: list[BBExit], block: BasicBlock):
        assert not isinstance(block, UnreachableBlock)
        BlockChain.ensure_no_phi(block)
        for exit_ in exits:
            BlockChain.ensure_jump(exit_.block)
            exit_.block.successors[exit_.idx] = block
            block.predecessors.append(exit_)

    @staticmethod
    def ensure_jump(block: BasicBlock):
        if len(block.cmds) == 0 or not isinstance(block.cmds[-1], IRJump):
            if len(block.successors) == 1:
                assert isinstance(block.successors[0], UnreachableBlock)
                block.add_cmd(IRJump(BBExit(block, 0)))

    @staticmethod
    def ensure_no_phi(block: BasicBlock):
        for cmd in block.cmds:
            if isinstance(cmd, IRPhi):
                raise AssertionError("Phi node found in block")

    @staticmethod
    def remove_jump(block: BasicBlock):
        if len(block.successors) != 1:
            return False
        assert isinstance(block.successors[0], UnreachableBlock)
        if len(block.cmds) == 0:
            return True
        last = block.cmds[-1]
        if isinstance(last, IRJump):
            block.cmds.pop()
            return True
        return True

    @staticmethod
    def merge_branches(block: BasicBlock) -> tuple[BBExit, str]:
        assert len(block.cmds) > 0
        last = block.cmds[-1]
        assert isinstance(last, IRBranch)
        block.cmds.pop()
        block.add_cmd(IRJump(last.true_dest))
        block.successors.pop()
        return last.true_dest, last.cond

    def try_attach(self) -> bool:
        block = self.exits[0].block
        if len(self.exits) == 1 and self.remove_jump(block):
            return True
        if len(self.exits) == 2 and block is self.exits[1].block:
            self.merge_branches(block)
            self.remove_jump(block)
            self.exits = [BBExit(block, 0)]
            return True
        return False

    def concentrate(self):
        if self.header is None or len(self.exits) > 2 or not self.try_attach():
            block = BasicBlock(renamer.get_name(self.name_hint))
            self.link_exits_to_block(self.exits, block)
            block.successors = [unreachable_block]
            self.exits = [BBExit(block, 0)]
            if self.header is None:
                self.header = block
        else:
            block = self.exits[0].block
        return block

    def set_exits(self, exits: list[BBExit]):
        assert len(self.exits) == 0
        self.exits = exits

    def merge_exits(self, exits: list[BBExit]):
        """This method will merge the given exits with the existing exits of the chain,
         convert branches to jumps if both branches of a source block are in the merged list,
          and set `self.exits` to the merged list."""
        self.exits = BlockChain.merge_exit_lists(self.exits + exits)

    @staticmethod
    def merge_exit_lists(exits: list[BBExit]) -> list[BBExit]:
        source_blocks = set(exit_.block for exit_ in exits)

        block_exits = {block: [] for block in source_blocks}
        for exit_ in exits:
            block_exits[exit_.block].append(exit_)

        new_exits = []
        for block, block_exits_list in block_exits.items():
            if len(block_exits_list) == 2:
                jump_exit, _ = BlockChain.merge_branches(block)

                new_exits.append(jump_exit)
            elif len(block_exits_list) == 1:
                new_exits.append(block_exits_list[0])
            else:
                raise AssertionError("Block has more than two exits in the merged list")

        return new_exits

    @staticmethod
    def phi_from_bool_flow(dest: str, true_exits: list[BBExit], false_exits: list[BBExit], ) -> "BlockChain":
        """Create a chain with a phi node from boolean flow"""
        chain = BlockChain(name_hint="cond.end")
        block = chain.concentrate()

        all_exits = true_exits + false_exits
        source_blocks = set(exit_.block for exit_ in all_exits)

        block_exits = {b: [] for b in source_blocks}
        for exit_ in all_exits:
            block_exits[exit_.block].append(exit_)

        phi_values = []
        for source_block, exits in block_exits.items():
            if len(exits) == 2:
                assert exits[0] in true_exits and exits[1] in false_exits
                should_invert = exits[0].idx == 1
                jump_exit, cond = BlockChain.merge_branches(source_block)
                BlockChain.link_exits_to_block([jump_exit], block)

                if should_invert:
                    invert_cond = renamer.get_name(cond + ".inv")
                    cmd = IRBinOp(invert_cond, "xor", cond, "true", "i1")
                    predecessor_block = jump_exit.block
                    predecessor_block.cmds.insert(-1, cmd)
                    phi_values.append((jump_exit, invert_cond))
                else:
                    phi_values.append((jump_exit, cond))
            elif len(exits) == 1:
                BlockChain.link_exits_to_block(exits, block)
                phi_values.append((exits[0], "true" if exits[0] in true_exits else "false"))
            else:
                raise AssertionError("Block has more than two exits in the merged list")

        block.add_cmd(IRPhi(dest, "i1", phi_values))
        return chain

    def add_entrances(self, exits: list[BBExit]):
        """Add entrances to the chain from the given exits."""
        BlockChain.link_exits_to_block(exits, self.header)

    def add_cmd(self, cmd: IRCmdBase):
        self.concentrate().add_cmd(cmd)

    def phi(self, dest: str, typ: str, values: list[tuple[BBExit, str]]):
        """Can only be called when chain is just created"""
        assert not self.header.cmds
        self.exits = [exit_ for exit_, _ in values]
        block = self.concentrate()
        block.add_cmd(IRPhi(dest, typ, values))

    def jump(self):
        ret = self.exits
        for exit_ in self.exits:
            BlockChain.ensure_jump(exit_.block)
        ret = BlockChain.merge_exit_lists(ret)
        self.exits = []
        return ret

    def branch(self, cond: str):
        assert len(self.exits) == 1
        block = self.exits[0].block
        block.successors = [unreachable_block, unreachable_block]
        block.add_cmd(IRBranch(cond, BBExit(block, 0), BBExit(block, 1)))
        self.exits = []
        return [BBExit(block, 0)], [BBExit(block, 1)]

    def link_from(self, exits: list[BBExit]):
        assert self.header is not None
        self.link_exits_to_block(exits, self.header)

    def ret(self, typ: str, value: str = ""):
        block = self.concentrate()
        block.add_cmd(IRRet(typ, value))
        block.successors = []
        self.exits = []

    def has_exits(self):
        return len(self.exits) > 0

    def collect_blocks(self) -> list[BasicBlock]:
        visited = set()
        result = []

        def dfs(block: BasicBlock):
            if block in visited:
                return
            visited.add(block)
            result.append(block)
            for succ in block.successors:
                dfs(succ)

        start_block = self.header if self.header else unreachable_block
        dfs(start_block)

        return result

    def llvm(self):
        blocks = self.collect_blocks()
        return "\n".join(block.llvm() for block in blocks)


class BuilderStack:
    layers: list["Layer"]
    this_type: InternalPtrType | None
    current_function: FunctionInfo | None

    class Layer:
        chain: BlockChain
        is_loop: bool
        breaks: list[BBExit]
        continues: list[BBExit]

        def __init__(self, chain: BlockChain, is_loop: bool):
            self.chain = chain
            self.is_loop = is_loop
            if is_loop:
                self.breaks = []
                self.continues = []

    def __init__(self):
        self.layers = []
        self.this_type = None

    def push(self, chain: BlockChain, is_loop: bool = False):
        self.layers.append(BuilderStack.Layer(chain, is_loop))

    def pop(self):
        layer = self.layers.pop()
        if layer.is_loop:
            return layer.breaks, layer.continues

    def top(self) -> Layer:
        return self.layers[-1]

    def top_chain(self) -> BlockChain:
        return self.top().chain

    def collect_breaks(self, breaks: list[BBExit]):
        for layer in reversed(self.layers):
            if layer.is_loop:
                layer.breaks.extend(breaks)
                return
        raise AssertionError("Break outside loop")

    def collect_continues(self, continues: list[BBExit]):
        for layer in reversed(self.layers):
            if layer.is_loop:
                layer.continues.extend(continues)
                return
        raise AssertionError("Continue outside loop")

    def continue_exits(self):
        return self.top().continues

    def break_exits(self):
        return self.top().breaks

    def enter_class_scope(self, class_type: InternalPtrType):
        self.this_type = class_type

    def exit_class_scope(self):
        self.this_type = None

    def get_this_type(self):
        return self.this_type

    def enter_function(self, function: FunctionInfo):
        self.current_function = function

    def exit_function(self):
        self.current_function = None

    def get_current_function(self):
        return self.current_function


class IRFunction:
    info: FunctionInfo
    blocks: list[BasicBlock] | None

    def __init__(self, info: FunctionInfo, chain: BlockChain = None):
        self.info = info
        self.blocks = chain.collect_blocks() if chain is not None else None

    def llvm(self):
        if self.blocks is None:
            param_str = ", ".join(f"{ty.ir_name}" for ty in self.info.param_types)
            return f"declare {self.info.ret_type.ir_name} {self.info.ir_name}({param_str})"
        else:
            param_str = ", ".join(
                f"{ty.ir_name} {name}.param" for ty, name in zip(self.info.param_types, self.info.param_ir_names))
            body = "\n".join(block.llvm() for block in self.blocks)
            return f"define {self.info.ret_type.ir_name} {self.info.ir_name}({param_str}) {{\n{body}}}\n"


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
