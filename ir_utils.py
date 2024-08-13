# Utility types and functions for LLVM 15 IR generation

from antlr4 import ParserRuleContext


class IRCmdBase:
    pass


class IRBinOp(IRCmdBase):
    def __init__(self, op: str, dest: str, lhs: str, rhs: str, typ: str):
        self.op = op
        self.dest = dest
        self.lhs = lhs
        self.rhs = rhs
        self.typ = typ

    def __str__(self):
        return f"{self.dest} = {self.op} {self.typ} {self.lhs}, {self.rhs}"


class IRLoad(IRCmdBase):
    def __init__(self, dest: str, src: str, typ: str):
        self.dest = dest
        self.src = src
        self.typ = typ

    def __str__(self):
        return f"{self.dest} = load {self.typ}, ptr {self.src}"


class IRStore(IRCmdBase):
    def __init__(self, dest: str, src: str, typ: str):
        self.dest = dest
        self.src = src
        self.typ = typ

    def __str__(self):
        return f"store {self.typ} {self.src}, ptr {self.dest}"


class IRAlloca(IRCmdBase):
    def __init__(self, dest: str, typ: str):
        self.dest = dest
        self.typ = typ

    def __str__(self):
        return f"{self.dest} = alloca {self.typ}"


class BBExit:
    block: "BasicBlock"
    idx: int

    def __init__(self, block: "BasicBlock", idx: int):
        self.block = block
        self.idx = idx

    def get_dest(self) -> "BasicBlock":
        return self.block.successors[self.idx]

    def __str__(self):
        return f"{self.get_dest().name}"


class BasicBlock:
    name: str
    cmds: list[IRCmdBase]
    predecessors: list[BBExit]
    successors: list["BasicBlock"]

    def __init__(self, name: str):
        self.name = name
        self.cmds = []

    def __str__(self):
        ret = f"{self.name}:"
        for cmd in self.cmds:
            ret += f"\n  {cmd}"
        ret += "\n"
        return ret

    def add_cmd(self, cmd: IRCmdBase):
        self.cmds.append(cmd)

    def __iter__(self):
        return iter(self.cmds)


class UnreachableBlock(BasicBlock):
    def __init__(self):
        super().__init__("unreachable")

    def add_cmd(self, cmd: IRCmdBase):
        pass

    def __str__(self):
        return "unreachable:\n  unreachable\n"


unreachable_block = UnreachableBlock()


class IRJump(IRCmdBase):
    def __init__(self, dest: BBExit):
        self.dest = dest

    def __str__(self):
        return f"br label %{self.dest}"


class IRBranch(IRCmdBase):
    def __init__(self, cond: str, true_dest: BBExit, false_dest: BBExit):
        self.cond = cond
        self.true_dest = true_dest
        self.false_dest = false_dest

    def __str__(self):
        return f"br i1 {self.cond}, label %{self.true_dest}, label %{self.false_dest}"


class IRRet(IRCmdBase):
    def __init__(self, typ: str, value: str = ""):
        self.typ = typ
        self.value = value

    def __str__(self):
        return f"ret {self.typ} {self.value}"


class IRPhi(IRCmdBase):
    def __init__(self, dest: str, typ: str, values: list[tuple[BBExit, str]]):
        self.dest = dest
        self.typ = typ
        self.values = values

    def __str__(self):
        ret = f"{self.dest} = phi {self.typ} "
        for value in self.values:
            ret += f"[{value[1]}, %{value[0].block.name}], "
        ret = ret[:-2]
        return ret


class Renamer:
    """Rename variables, functions, etc. in IR"""
    name_map: dict[str, int]

    def __init__(self):
        self.name_map = {}

    def get_name(self, name: str) -> str:
        if name not in self.name_map:
            self.name_map[name] = 1
            return name
        self.name_map[name] += 1
        name = f"{name}.{self.name_map[name]}"
        return self.get_name(name)

    def get_name_from_ctx(self, name: str, ctx: ParserRuleContext) -> str:
        if name not in self.name_map:
            self.name_map[name] = 1
            return name
        name += f".line{ctx.start.line}"
        return self.get_name(name)


renamer = Renamer()


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
            if allow_attach and self.remove_jump(self.exits[0].block):
                self.header = self.exits[0].block

    @staticmethod
    def link_exits_to_block(exits: list[BBExit], block: BasicBlock):
        assert not isinstance(block, UnreachableBlock)
        BlockChain.ensure_no_phi(block)
        for exit_ in exits:
            exit_.block.successors[exit_.idx] = block
            BlockChain.ensure_jump(exit_.block)
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
        if len(block.cmds) == 0:
            return True
        last = block.cmds[-1]
        if isinstance(last, IRJump):
            block.cmds.pop()
            return True
        if isinstance(last, IRBranch) or isinstance(last, IRRet):
            return False
        return True

    def concentrate(self):
        if self.header is None or len(self.exits) > 1:
            block = BasicBlock(renamer.get_name(self.name_hint))
            self.link_exits_to_block(self.exits, block)
            block.successors = [unreachable_block]
            self.exits = [BBExit(block, 0)]
            if self.header is None:
                self.header = block
        else:
            block = self.exits[0].block
            if not self.remove_jump(block):
                block = BasicBlock(renamer.get_name(self.name_hint))
                self.link_exits_to_block(self.exits, block)
        return block

    def set_exits(self, exits: list[BBExit]):
        assert len(self.exits) == 0
        self.exits = exits

    def add_cmd(self, cmd: IRCmdBase):
        self.concentrate().add_cmd(cmd)

    def phi(self, dest: str, typ: str, values: list[tuple[BBExit, str]]):
        """Can only be called when chain is just created"""
        assert self.header is not None
        assert len(self.exits) == 0
        self.exits = [exit_ for exit_, _ in values]
        block = self.concentrate()
        block.add_cmd(IRPhi(dest, typ, values))

    def jump(self):
        ret = self.exits
        for exit_ in self.exits:
            BlockChain.ensure_jump(exit_.block)
        self.exits = []
        return ret

    def branch(self, cond: str):
        assert len(self.exits) == 1
        block = self.exits[0].block
        block.successors = [unreachable_block, unreachable_block]
        block.add_cmd(IRBranch(cond, BBExit(block, 0), BBExit(block, 1)))
        self.exits = []
        return [BBExit(block, 0), BBExit(block, 1)]

    def link_from(self, exits: list[BBExit]):
        assert self.header is not None
        self.link_exits_to_block(exits, self.header)

    def ret(self, typ: str, value: str = ""):
        block = self.concentrate()
        block.add_cmd(IRRet(typ, value))
        self.exits = []


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
        return self.layers.pop()

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
