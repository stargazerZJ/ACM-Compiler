import sys
from typing import cast

from asm_regalloc import AllocationRegister, AllocationStack, AllocationGlobal, AllocationBase
from asm_repr import ASMBlock, ASMMemOp, ASMCmdBase, ASMCmd, ASMMove, ASMFunction


class BlockNamer:
    def __init__(self, func_name: str):
        self.counter = 0
        self.func_name = func_name

    def get(self) -> str:
        name = f".L-{self.func_name}-{self.counter}"
        self.counter += 1
        return name


class OperandBase:
    pass


class OperandReg(OperandBase):
    reg: str

    def __init__(self, reg: str):
        self.reg = reg

    def __str__(self):
        return self.reg


class OperandImm(OperandBase):
    imm: int

    def __init__(self, imm: int):
        self.imm = imm

    def is_lower(self):
        return - 2048 <= self.imm < 2048

    def __str__(self):
        return str(self.imm)


class OperandStack(OperandBase):
    offset: int

    def __init__(self, offset: int):
        self.offset = offset


class OperandGlobal(OperandBase):
    label: str

    def __init__(self, label: str):
        self.label = label


class ASMBuilderUtils:
    global_symbol_table: dict[str, AllocationGlobal]
    max_saved_reg: int
    block_namer: BlockNamer
    current_function: ASMFunction
    callee_reg: list[str]
    allocation_table: dict[str, AllocationBase]

    def __init__(self):
        # self.block_namer = BlockNamer(name)
        # self.current_function = func
        self.global_symbol_table = {}
        # self.callee_reg = list(callee_reg.intersection(set(
        #     [f"s{i}" for i in range(12)]
        # )))
        # self.allocation_table = allocation_table
        # self.max_saved_reg = 0

    @staticmethod
    def parse_imm(value: str):
        """does not check 12-bit overflow"""
        if value in ["true", "false", "null"]:
            value = 0 if value != "true" else 1
        return int(value)

    @staticmethod
    def rearrange_blocks(blocks: list[ASMBlock]):
        """Rearrange blocks in reverse post order"""
        header_block = blocks[0]
        visited: set[str] = set()
        result = []

        def dfs(block: ASMBlock):
            visited.add(block.label)
            for succ in block.successors:
                if succ.label not in visited:
                    dfs(succ)
            result.append(block)

        dfs(header_block)
        assert len(result) == len(blocks)
        return result[::-1]

    def save_registers(self, regs: list[str], start_offset: int) -> list[ASMMemOp]:
        self.max_saved_reg = max(self.max_saved_reg, len(regs))
        return [
            ASMMemOp("sw", reg, start_offset + i * 4, "sp")
            for i, reg in enumerate(regs)
        ]

    @staticmethod
    def restore_registers(regs: list[str], start_offset: int) -> list[ASMMemOp]:
        return [
            ASMMemOp("lw", reg, start_offset + i * 4, "sp")
            for i, reg in enumerate(regs)
        ]

    @staticmethod
    def prepare_params(count: int) -> list:
        params = []
        for i in range(min(count, 8)):
            params.append(OperandReg(f"a{i}"))
        for i in range(max(0, count - 8)):
            params.append(OperandStack(i * 4))
        return params

    def prepare_var_from(self, variables: list[str]):
        var_from = []
        for var in variables:
            if var in self.allocation_table:
                alloc = self.allocation_table[var]
                if isinstance(alloc, AllocationRegister):
                    var_from.append(OperandReg(alloc.reg))
                else:
                    alloc = cast(AllocationStack, alloc)
                    var_from.append(OperandStack(alloc.offset))
            elif var in self.global_symbol_table:
                alloc = self.global_symbol_table[var]
                var_from.append(OperandGlobal(alloc.label))
            else:
                var_from.append(OperandImm(self.parse_imm(var)))
        return var_from

    def prepare_var_to(self, variables: list[str]):
        var_to = []
        for var in variables:
            alloc = self.allocation_table[var]
            if isinstance(alloc, AllocationRegister):
                var_to.append(OperandReg(alloc.reg))
            else:
                alloc = cast(AllocationStack, alloc)
                var_to.append(OperandStack(alloc.offset))
        return var_to

    def prepare_dest(self, dest: str) -> tuple[str, ASMMemOp | None]:
        tmp_reg = "t0"
        tmp_reg2 = "t1"
        if dest in self.allocation_table:
            alloc = self.allocation_table[dest]
            if isinstance(alloc, AllocationRegister):
                return alloc.reg, None
            else:
                alloc = cast(AllocationStack, alloc)
                store_cmd = ASMMemOp("sw", tmp_reg, alloc.offset, "sp")
                return tmp_reg, store_cmd
        else:
            alloc = self.global_symbol_table[dest]
            alloc = cast(AllocationGlobal, alloc)
            # `sw rd, symbol, rt` is a pseudo instruction that will be expanded to lui and sw
            store_cmd = (ASMMemOp("sw", tmp_reg, alloc.label, tmp_reg=tmp_reg2))
            return tmp_reg, store_cmd

    def prepare_operand(self, block: ASMBlock, operand: str, tmp_reg: str) -> tuple[OperandBase, bool]:
        if operand in self.allocation_table:
            alloc = self.allocation_table[operand]
            if isinstance(alloc, AllocationRegister):
                return OperandReg(alloc.reg), False
            else:
                alloc = cast(AllocationStack, alloc)
                block.add_cmd(ASMMemOp("lw", tmp_reg, alloc.offset, "sp"))
                return OperandReg(tmp_reg), True
        elif operand in self.global_symbol_table:
            alloc = self.global_symbol_table[operand]
            # `lw rd, symbol` is a pseudo instruction that will be expanded to lui and lw
            block.add_cmd(ASMMemOp("lw", tmp_reg, alloc.label))
            return OperandReg(tmp_reg), True
        else:
            return OperandImm(self.parse_imm(operand)), False

    def prepare_operands(self, block: ASMBlock, lhs: str, rhs: str) -> tuple[OperandBase, OperandBase]:
        lhs_operand, tmp_used = self.prepare_operand(block, lhs, "t0")
        tmp_reg = "t1" if tmp_used else "t0"
        rhs_operand, _ = self.prepare_operand(block, rhs, tmp_reg)
        return lhs_operand, rhs_operand

    @staticmethod
    def rearrange_variables(var_from: list[OperandBase], var_to: list[OperandStack | OperandReg], tmp_reg: str) \
            -> list[ASMCmdBase]:
        assert len(var_from) == len(var_to)
        cmds: list[ASMCmdBase] = []
        for f, t in zip(var_from, var_to):
            if isinstance(t, OperandStack):
                if isinstance(f, OperandStack):
                    if f.offset == t.offset:
                        continue
                    cmds.append(ASMMemOp("lw", tmp_reg, f.offset, "sp"))
                    reg = tmp_reg
                elif isinstance(f, OperandImm):
                    if f.imm == 0:
                        reg = "zero"
                    else:
                        cmds.append(ASMCmd("li", tmp_reg, [str(f)]))
                        reg = tmp_reg
                else:
                    f = cast(OperandReg, f)
                    reg = f.reg
                cmds.append(ASMMemOp("sw", reg, t.offset, "sp"))

        class Node:
            def __init__(self):
                self.out_deg = 0
                self.pred: str | None = None

        graph: dict[str, Node] = {}

        for f, t in zip(var_from, var_to):
            if not isinstance(f, OperandReg) or not isinstance(t, OperandReg):
                continue
            f, t = f.reg, t.reg
            if f == t: continue  # self loops
            if f not in graph: graph[f] = Node()
            if t not in graph: graph[t] = Node()
            graph[f].out_deg += 1
            graph[t].pred = f
        visited: set[str] = set()
        for reg, node in graph.items():
            if node.out_deg == 0:
                # chains
                visited.add(reg)
                while node.pred is not None:
                    cmds.append(ASMMove(reg, node.pred))
                    reg, node = node.pred, graph[node.pred]
                    visited.add(reg)
        for reg, node in graph.items():
            if reg not in visited:
                cmds.append(ASMMove(tmp_reg, reg))
                visited.add(reg)
                while node.pred not in visited:
                    cmds.append(ASMMove(reg, node.pred))
                    reg, node = node.pred, graph[node.pred]
                    visited.add(reg)
                cmds.append(ASMMove(reg, tmp_reg))

        for f, t in zip(var_from, var_to):
            if not isinstance(t, OperandReg): continue
            if isinstance(f, OperandStack):
                cmds.append(ASMMemOp("lw", t.reg, f.offset, "sp"))
            elif isinstance(f, OperandImm):
                cmds.append(ASMCmd("li", t.reg, [str(f)]))
            elif isinstance(f, OperandGlobal):
                cmds.append(ASMMemOp("lw", t.reg, f.label))

        return cmds

    def print_allocation_table(self, file=sys.stderr):
        print(f"=== Allocation Table for {self.current_function.label} ===", file=file)
        for ir_name, alloc in self.allocation_table.items():
            print(f"{ir_name: <20} -> {alloc}", file=file)
        print("\n", file=file)
