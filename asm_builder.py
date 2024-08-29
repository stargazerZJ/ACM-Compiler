from asm_regalloc import AllocationBase, AllocationGlobal, allocate_registers, AllocationStack, AllocationRegister
from asm_repr import ASMGlobal, ASMFunction, ASMStr, ASMModule, ASMBlock, ASMCmd, ASMMemOp, ASMFlowControl, \
    ASMMove, ASMCall
from asm_utils import ASMBuilderUtils
from ir_repr import IRGlobal, IRModule, IRFunction, IRStr, IRBlock, IRPhi, IRBinOp, IRIcmp, IRLoad, IRStore, \
    IRJump, IRBranch, IRRet, IRCall


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


# def function_param_generator() -> OperandReg | OperandStack:
#     yield from (OperandReg("a" + str(i)) for i in range(8))
#     i = 0
#     while True:
#         yield OperandStack(i * 4)



class ASMBuilder(ASMBuilderUtils):
    ir_module: IRModule
    # global_symbol_table: dict[str, AllocationGlobal]
    # max_saved_reg: int
    # block_namer: BlockNamer
    # current_function: ASMFunction
    # callee_reg: list[str]
    # allocation_table: dict[str, AllocationBase]

    def __init__(self, ir_module: IRModule):
        super().__init__()
        self.ir_module = ir_module

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
        callee_reg = set()
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

        func.stack_size += max(0, len(ir_func.info.param_ir_names) - 8) * 4
        for var, alloc in allocation_table.items():
            if isinstance(alloc, AllocationStack):
                alloc.offset = func.stack_size
                func.stack_size += 4
            else:
                alloc: AllocationRegister
                alloc.reg = register_list[alloc.logical_id]
                callee_reg.add(alloc.reg)
        self.callee_reg = list(callee_reg.intersection(set(
            [f"s{i}" for i in range(12)]
        )))
        self.callee_reg.sort()
        del callee_reg

        blocks = [self.build_block(block) for block in ir_func.blocks]
        self.link_blocks(blocks, ir_func)  # and write jump/branch destinations
        self.eliminate_phi(blocks)

        header_block = ASMBlock(header_name)

        param_from = [OperandReg("ra")] + self.prepare_params(len(ir_func.info.param_ir_names))
        param_to = self.prepare_var_to(["ret_addr"] + ir_func.info.param_ir_names)
        header_block.add_cmd(*self.rearrange_variables(param_from, param_to, "t0"))
        header_block.add_cmd(*self.save_registers(self.callee_reg, func.stack_size))

        func.stack_size += self.max_saved_reg * 4
        func.stack_size = (func.stack_size + 15) // 16 * 16

        if func.stack_size > 0:
            # TODO: stack_size >= 2048
            header_block.add_cmd(ASMCmd("addi", "sp", ["sp", str(-func.stack_size)]))

        header_block.successors = blocks[0]

        blocks.insert(0, header_block)
        self.rearrange_blocks(blocks)
        # TODO: relax branch offsets
        func.blocks = blocks
        return func

    @staticmethod
    def link_blocks(asm_blocks: list[ASMBlock], func: IRFunction):
        """link_blocks and write jump/branch destinations"""
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
                assert not isinstance(lhs, OperandImm)
                assert not isinstance(rhs, OperandImm) or rhs.is_lower()
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
                assert not isinstance(lhs, OperandImm)
                assert not isinstance(rhs, OperandImm) or rhs.is_lower()
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
                assert not isinstance(addr, OperandImm)
                block.add_cmd(ASMMemOp("lw", dest, str(addr)))
                if store_cmd is not None:
                    block.add_cmd(store_cmd)
            elif isinstance(cmd, IRStore):
                value, pos = self.prepare_operands(block, cmd.dest, cmd.src)
                assert not isinstance(value, OperandImm)
                assert not isinstance(pos, OperandImm)
                block.add_cmd(ASMMemOp("sw", str(value), str(pos)))
            elif isinstance(cmd, IRJump):
                block.set_flow_control(ASMFlowControl.jump(block))
            elif isinstance(cmd, IRBranch):
                cond, _ = self.prepare_operand(block, cmd.cond, "t0")
                assert isinstance(cond, OperandReg)
                block.set_flow_control(ASMFlowControl.branch("beqz", [str(cond)], block))
            elif isinstance(cmd, IRRet):
                if cmd.value:
                    value, _ = self.prepare_operand(block, cmd.value, "a0")
                    if isinstance(value, OperandImm):
                        block.add_cmd(ASMCmd("li", "a0", [str(value)]))
                        value = OperandReg("a0")
                    if value.reg != "a0":
                        block.add_cmd(ASMMove("a0", str(value)))
                self.restore_registers(self.callee_reg, self.current_function.stack_size)
                ra_alloc = self.allocation_table["ret_addr"]
                if isinstance(ra_alloc, AllocationStack):
                    block.add_cmd(ASMMemOp("lw", "ra", ra_alloc.offset, "sp"))
                block.set_flow_control(ASMFlowControl.ret(self.current_function))  # includes `addi sp`
            elif isinstance(cmd, IRCall):
                func_name = cmd.func.ir_name.lstrip("@")

                caller_regs = set()
                for var in cmd.live_out:
                    if var == cmd.dest: continue
                    alloc = self.allocation_table[var]
                    if isinstance(alloc, AllocationRegister):
                        caller_regs.add(alloc.reg)
                caller_regs.intersection_update(
                    [f"t{i}" for i in range(2, 7)]
                    + [f"a{i}" for i in range(8)]
                )
                caller_regs = list(caller_regs)
                caller_regs.sort()
                self.save_registers(caller_regs, self.current_function.stack_size)

                param_count = len(cmd.func.param_ir_names)

                stack_delta = max(0, param_count - 8) * 4
                stack_delta = (stack_delta + 15) // 16 * 16
                if stack_delta > 0:
                    block.add_cmd(ASMCmd("addi", "sp", ["sp", str(-stack_delta)]))

                param_to = self.prepare_params(param_count)
                param_from = self.prepare_var_from(cmd.func.param_ir_names)
                block.add_cmd(*self.rearrange_variables(param_from, param_to, "t0"))

                block.add_cmd(ASMCall(func_name))

                if stack_delta > 0:
                    block.add_cmd(ASMCmd("addi", "sp", ["sp", str(stack_delta)]))

                result_to = self.prepare_var_to(cmd.var_def)
                block.add_cmd(*self.rearrange_variables([OperandReg("a0")], result_to, "t0"))

                self.restore_registers(caller_regs, self.current_function.stack_size)
            # There is no alloca nor gep in the input IR
            raise NotImplementedError(f"Unsupported command: {cmd}")
        return block

    def eliminate_phi(self, asm_blocks: list[ASMBlock]):
        new_blocks = []
        for block in asm_blocks:
            ir_block = block.ir_block
            if not ir_block.cmds or not isinstance(ir_block.cmds[0], IRPhi):
                continue
            phi_cmds: list[IRPhi] = list(filter(lambda phi: isinstance(phi, IRPhi), ir_block.cmds))
            phi_to = self.prepare_var_to([phi.dest for phi in phi_cmds])

            for pred_id, ir_pred in enumerate(ir_block.predecessors):
                ir_pred = ir_pred.block
                pred = asm_blocks[ir_pred.index]
                phi_from = self.prepare_var_from([phi.lookup(ir_pred) for phi in phi_cmds])
                if len(ir_pred.successors) > 1:
                    new_block = ASMBlock(self.block_namer.get())
                    new_block.add_cmd(*self.rearrange_variables(phi_from, phi_to, "t0"))
                    if pred.successors[0] is block:
                        pred.successors[0] = new_block
                    else:
                        assert pred.successors[1] is block
                        pred.successors[1] = new_block
                    new_block.predecessors = [pred]
                    new_block.successors = [block]
                    new_block.set_flow_control(ASMFlowControl.jump(new_block))
                    assert block.predecessors[pred_id] is pred
                    block.predecessors[pred_id] = new_block
                    new_blocks.append(new_block)
                else:
                    pred.add_cmd(*self.rearrange_variables(phi_from, phi_to, "t0"))