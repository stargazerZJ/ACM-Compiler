import sys
from typing import cast

from .operand import OperandBase, OperandReg, OperandImm, OperandStack, OperandGlobal, rearrange_operands
from .regalloc import AllocationRegister, AllocationStack, AllocationGlobal, AllocationBase
from .asm_repr import ASMBlock, ASMMemOp, ASMCmdBase, ASMFunction
from mxc.common.ir_repr import IRBlock, IRCall
from mxc.middle_end.mem2reg import IRUndefinedValue
from mxc.middle_end.mir import is_zero


class BlockNamer:
    def __init__(self, func_name: str):
        self.counter = 0
        self.func_name = func_name

    def get(self) -> str:
        name = f".L_{self.func_name}_{self.counter}"
        self.counter += 1
        return name


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
        if isinstance(value, IRUndefinedValue):
            return 0
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
            ASMMemOp("sw", reg, start_offset + i * 4, "sp", tmp_reg="t0")
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
                store_cmd = ASMMemOp("sw", tmp_reg, alloc.offset, "sp", tmp_reg=tmp_reg2)
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
            if alloc.label.startswith(".str"):
                block.add_cmd(ASMMemOp("la", tmp_reg, alloc.label))
            else:
                # `lw rd, symbol` is a pseudo instruction that will be expanded to lui and lw
                block.add_cmd(ASMMemOp("lw", tmp_reg, alloc.label))
                raise AssertionError("Unexpected operand type")
            return OperandReg(tmp_reg), True
        elif is_zero(operand):
            return OperandReg("zero"), False
        else:
            return OperandImm(self.parse_imm(operand)), False

    def prepare_operands(self, block: ASMBlock, lhs: str, rhs: str) -> tuple[OperandBase, OperandBase]:
        lhs_operand, tmp_used = self.prepare_operand(block, lhs, "t0")
        tmp_reg = "t1" if tmp_used else "t0"
        rhs_operand, _ = self.prepare_operand(block, rhs, tmp_reg)
        return lhs_operand, rhs_operand

    @staticmethod
    def rearrange_operands(var_from: list[OperandBase], var_to: list[OperandStack | OperandReg], tmp_reg: tuple[str, str]) \
            -> list[ASMCmdBase]:
        return rearrange_operands(var_from, var_to, tmp_reg[0], tmp_reg[1])

    @staticmethod
    def get_max_call_param(blocks: list[IRBlock]):
        """Get the maximum number of parameters in a function call"""
        return max(
            (len(cmd.func.param_types)
            for block in blocks
            for cmd in block.cmds
            if isinstance(cmd, IRCall)
        ), default=0)


    def print_allocation_info(self, file=sys.stderr):
        print(f"=== Allocation Into for {self.current_function.label} ===", file=file)
        print(f"Stack size: {self.current_function.stack_size}", file=file)
        for ir_name, alloc in self.allocation_table.items():
            print(f"{ir_name: <20} -> {alloc}", file=file)
        print("\n", file=file)
