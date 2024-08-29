from asm_regalloc import AllocationBase, AllocationGlobal, allocate_registers, AllocationStack, AllocationRegister
from asm_repr import ASMGlobal, ASMFunction, ASMStr, ASMModule, ASMBlock, ASMCmd, ASMMemOp, ASMCmdBase, ASMFlowControl, \
    ASMMove
from ir_repr import IRGlobal, IRModule, IRFunction, IRStr, IRBlock, IRPhi, IRCmdBase, IRBinOp, IRIcmp, IRLoad, IRStore, \
    IRJump, IRBranch, IRRet


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
        assert self.is_lower()

    def is_lower(self):
        return - 2048 <= self.imm < 2048

    def __str__(self):
        return str(self.imm)


class ASMBuilder:
    ir_module: IRModule
    global_symbol_table: dict[str, AllocationBase]
    max_saved_reg: int
    block_namer: BlockNamer
    current_function: ASMFunction
    used_reg: set[str]
    allocation_table: dict[str, AllocationBase]

    def __init__(self, ir_module: IRModule):
        self.ir_module = ir_module
        self.global_symbol_table = {}

    def build(self) -> ASMModule:
        module = ASMModule()
        ir_module = self.ir_module
        for global_var in ir_module.globals:
            global_asm = self.build_global(global_var)
            self.global_symbol_table[global_var.name] = AllocationGlobal(global_asm.name)
            module.globals.append(global_asm)
        for string_var in ir_module.strings:
            string_asm = self.build_str(string_var)
            self.global_symbol_table[string_var.name] = AllocationGlobal(string_asm.name)
            module.strings.append(string_asm)
        for function in ir_module.functions:
            if function.is_declare(): continue
            function_asm = self.build_function(function)
            module.functions.append(function_asm)
        return module

    @staticmethod
    def build_global(cmd: IRGlobal) -> ASMGlobal:
        name = cmd.name.lstrip("@")
        value = ASMBuilder.parse_imm(cmd.value)
        return ASMGlobal(name, value)

    @staticmethod
    def parse_imm(value: str):
        """does not check 12-bit overflow"""
        if value in ["true", "false", "null"]:
            value = 0 if value != "true" else 1
        return int(value)

    @staticmethod
    def build_str(cmd: IRStr) -> ASMStr:
        name = cmd.name.lstrip("@")
        return ASMStr(name, cmd.value)

    def build_function(self, ir_func: IRFunction) -> ASMFunction:
        name = ir_func.info.ir_name.lstrip("@")
        func = ASMFunction(name, ir_func)
        allocation_table = allocate_registers(ir_func)
        self.allocation_table = allocation_table
        self.max_saved_reg = 0
        self.block_namer = BlockNamer(name)
        self.current_function = func
        self.used_reg = set()
        header_name = self.block_namer.get()
        if hasattr(ir_func, "is_leaf"):
            register_list = (["ra"]
                             + [f"a{i}" for i in range(8)]
                             + [f"t{i}" for i in range(7)]
                             + [f"s{i}" for i in range(12)])
        else:
            register_list = (["ra"]
                             + [f"a{i}" for i in range(8)]
                             + [f"s{i}" for i in range(12)]
                             + [f"t{i}" for i in range(7)])

        for var, alloc in allocation_table.items():
            if isinstance(alloc, AllocationStack):
                alloc.offset = func.stack_size
                func.stack_size += 4
            else:
                alloc: AllocationRegister
                alloc.reg = register_list[alloc.logical_id]
                self.used_reg.add(alloc.reg)

        blocks = [self.build_block(block) for block in ir_func.blocks]
        self.link_blocks(blocks, ir_func)  # and write jump destinations
        self.eliminate_phi(blocks, ir_func)

        func.stack_size += self.max_saved_reg * 4
        func.stack_size = (func.stack_size + 15) // 16 * 16

        header_block = ASMBlock(header_name)
        if func.stack_size > 0:
            # TODO: stack_size >= 2048
            header_block.add_cmd(ASMCmd("addi", "sp", ["sp", str(-func.stack_size)]))
        ra_alloc = allocation_table["ret_addr"]
        if isinstance(ra_alloc, AllocationStack):
            header_block.add_cmd(ASMMemOp("sw", "ra", ra_alloc.offset, "sp"))
        # TODO: function params and callee-saved registers

        blocks.insert(0, header_block)
        # TODO: rearrange blocks and relax branch offsets
        func.blocks = blocks
        return func

    @staticmethod
    def link_blocks(asm_blocks: list[ASMBlock], func: IRFunction):
        ir_blocks = func.blocks
        for ir_block, asm_block in zip(ir_blocks, asm_blocks):
            ir_block: IRBlock
            asm_block: ASMBlock
            asm_block.predecessors = [asm_blocks[pred.block.index] for pred in ir_block.predecessors]
            asm_block.successors = [asm_blocks[succ.index] for succ in ir_block.successors]
            if len(asm_block.successors) == 2:
                branch = ir_block.cmds[:-1]
                assert isinstance(branch, IRBranch)
                if branch.true_dest.idx == 0:
                    asm_block.successors = [asm_block.successors[1], asm_block.successors[0]]

    def prepare_dest(self, dest: str) -> tuple[str, ASMMemOp | None]:
        tmp_reg = "t0"
        if dest in self.allocation_table:
            alloc = self.allocation_table[dest]
            if isinstance(alloc, AllocationRegister):
                return alloc.reg, None
            else:
                store_cmd = ASMMemOp("sw", tmp_reg, alloc.offset, "sp")
                return tmp_reg, store_cmd
        else:
            alloc = self.global_symbol_table[dest]
            # `sw rd, symbol` is a pseudo instruction that will be expanded to lui and sw
            store_cmd = (ASMMemOp("sw", tmp_reg, alloc.label))
            return tmp_reg, store_cmd

    def prepare_operand(self, block: ASMBlock, operand: str, tmp_reg: str) -> tuple[OperandBase, bool]:
        if operand in self.allocation_table:
            alloc = self.allocation_table[operand]
            if isinstance(alloc, AllocationRegister):
                return OperandReg(alloc.reg), False
            else:
                block.add_cmd(ASMMemOp("lw", tmp_reg, alloc.offset, "sp"))
                return OperandReg(tmp_reg), True
        else:
            if operand in self.global_symbol_table:
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

    def build_block(self, ir_block: IRBlock) -> ASMBlock:
        block = ASMBlock(self.block_namer.get(), ir_block)
        for cmd in ir_block.cmds:
            if isinstance(cmd, IRPhi):
                # Skip phi nodes for now
                continue
            if isinstance(cmd, IRBinOp):
                dest, store_cmd = self.prepare_dest(cmd.dest)
                if cmd.op == "add" and cmd.lhs == "0":
                    # special case: li
                    block.add_cmd(ASMCmd("li", dest, [self.parse_imm(cmd.rhs)]))
                lhs, rhs = self.prepare_operands(block, cmd.lhs, cmd.rhs)
                if cmd.op in ["add", "and", "or", "xor"]:
                    op = cmd.op
                    if isinstance(rhs, OperandImm):
                        op += "i"
                    block.add_cmd(ASMCmd(op, dest, [lhs, rhs]))
                if cmd.op == "sub":
                    if cmd.lhs == "0":
                        block.add_cmd(ASMCmd("neg", dest, [rhs]))
                    elif isinstance(rhs, OperandImm):
                        block.add_cmd(ASMCmd("addi", dest, [lhs, - rhs.imm]))
                    else:
                        block.add_cmd(ASMCmd("sub", dest, [lhs, rhs]))
                if cmd.op in ["shl", "ashr"]:
                    # there is no shr in the input IR
                    op = "sll" if cmd.op == "shl" else "sra"
                    if isinstance(rhs, OperandImm):
                        op += "i"
                    block.add_cmd(ASMCmd(op, dest, [lhs, rhs]))
                if cmd.op in ["mul", "sdiv", "srem"]:
                    # there are no udiv and urem in the input IR
                    op = {"mul": "mul", "sdiv": "div", "srem": "rem"}[cmd.op]
                    block.add_cmd(ASMCmd(op, dest, [lhs, rhs]))
                if store_cmd is not None:
                    block.add_cmd(store_cmd)
            elif isinstance(cmd, IRIcmp):
                dest, store_cmd = self.prepare_dest(cmd.dest)
                lhs, rhs = self.prepare_operands(block, cmd.lhs, cmd.rhs)
                if cmd.rhs == "0":
                    assert cmd.op in ["slt", "sgt", "sne", "seq"]
                    op = cmd.op + "z"
                    block.add_cmd(ASMCmd(op, dest, [lhs]))
                else:
                    assert cmd.op == "slt"
                    op = "slt"
                    if isinstance(rhs, OperandImm):
                        op += "i"
                    block.add_cmd(ASMCmd(op, dest, [lhs, rhs]))
                if store_cmd is not None:
                    block.add_cmd(store_cmd)
            elif isinstance(cmd, IRLoad):
                # TODO: load/store with offset
                dest, store_cmd = self.prepare_dest(cmd.dest)
                addr, _ = self.prepare_operand(block, cmd.src, "t0")
                block.add_cmd(ASMMemOp("lw", dest, str(addr)))
                if store_cmd is not None:
                    block.add_cmd(store_cmd)
            elif isinstance(cmd, IRStore):
                value, pos = self.prepare_operands(block, cmd.dest, cmd.src)
                block.add_cmd(ASMMemOp("sw", str(value), str(pos)))
            elif isinstance(cmd, IRJump):
                block.set_flow_control(ASMFlowControl.jump(block))
            elif isinstance(cmd, IRBranch):
                cond, _ = self.prepare_operand(block, cmd.cond, "t0")
                assert isinstance(cond, OperandReg)
                block.set_flow_control(ASMFlowControl.branch("beqz", [str(cond)], block))
            elif isinstance(cmd, IRRet):
                value, _ = self.prepare_operand(block, cmd.value, "a0")
                block.add_cmd(ASMMove("a0", str(value)))
                # TODO: restore callee-saved registers
                block.set_flow_control(ASMFlowControl.ret(self.current_function))  # includes `addi sp`
            # There is no alloca nor gep in the input IR
            # TODO: call
            raise NotImplementedError(f"Unsupported command: {cmd}")
        return block
