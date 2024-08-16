# Utility types and functions for LLVM 15 IR generation

from ir_renamer import renamer
from syntax_recorder import FunctionInfo
from type import FunctionType


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
    def __init__(self, dest: str, func: str, typ: str, args: list[tuple[str, str]]):
        self.dest = dest
        self.func = func
        self.typ = typ
        self.args = args

    def llvm(self):
        if self.dest == "":
            return f"call {self.typ} {self.func}({', '.join(f'{ty} {name}' for ty, name in self.args)})"
        return f"{self.dest} = call {self.typ} {self.func}({', '.join(f'{ty} {name}' for ty, name in self.args)})"



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
                    block.add_cmd(IRBinOp(invert_cond, "xor", cond, "true", "i1"))
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
        """DEPRECIATED Can only be called when chain is just created"""
        assert self.header is None
        assert len(self.exits) == 0
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


class IRFunction:
    info: FunctionInfo
    blocks: list[BasicBlock] | None

    def __init__(self, info: FunctionInfo, chain: BlockChain = None):
        self.info = info
        self.blocks = chain.collect_blocks() if chain is not None else None

    @staticmethod
    def declare(func: FunctionType):
        # TODO
        # return IRFunction(FunctionInfo(func.ir_name, func.ret_type, func.param_types, func.param_ir_names))
        pass

    def llvm(self):
        param_str = ", ".join(f"{ty.ir_name} {name}.param" for ty, name in zip(self.info.param_types, self.info.param_ir_names))
        if self.blocks is None:
            return f"declare {self.info.ret_type.ir_name} {self.info.ir_name}({param_str})"
        else:
            body = "\n".join(block.llvm() for block in self.blocks)
            return f"define {self.info.ret_type.ir_name} {self.info.ir_name}({param_str}) {{\n{body}}}\n"

class IRModule:
    functions: list[IRFunction]

    def __init__(self):
        self.functions = []

    def llvm(self):
        return "\n".join(func.llvm() for func in self.functions)
