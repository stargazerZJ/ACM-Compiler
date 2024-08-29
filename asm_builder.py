from asm_regalloc import AllocationGlobal, allocate_registers, AllocationStack, AllocationRegister
from asm_repr import ASMGlobal, ASMFunction, ASMStr, ASMModule, ASMBlock, ASMCmd, ASMMemOp, ASMFlowControl, \
    ASMMove, ASMCall
from asm_utils import ASMBuilderUtils, BlockNamer, OperandReg, OperandImm
from ir_repr import IRGlobal, IRModule, IRFunction, IRStr, IRBlock, IRPhi, IRBinOp, IRIcmp, IRLoad, IRStore, \
    IRJump, IRBranch, IRRet, IRCall


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
        param_to = self.prepare_var_to(["ret_addr"] + [
            param + ".param" for param in ir_func.info.param_ir_names])
        header_block.add_cmd(*self.rearrange_variables(param_from, param_to, "t0"))
        header_block.add_cmd(*self.save_registers(self.callee_reg, func.stack_size))

        func.stack_size += self.max_saved_reg * 4
        func.stack_size = (func.stack_size + 15) // 16 * 16

        if func.stack_size > 0:
            # TODO: stack_size >= 2048
            header_block.add_cmd(ASMCmd("addi", "sp", ["sp", str(-func.stack_size)]))

        header_block.predecessors = []
        header_block.successors = [blocks[0]]
        header_block.set_flow_control(ASMFlowControl.jump(header_block))
        blocks[0].predecessors = [header_block]

        blocks.insert(0, header_block)
        blocks = self.rearrange_blocks(blocks)
        # TODO: relax branch offsets
        func.blocks = blocks

        # debug
        self.print_allocation_table()

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
                branch = ir_block.cmds[-1]
                assert isinstance(branch, IRBranch)
                if branch.true_dest.idx == 0:
                    asm_block.successors = [asm_block.successors[1], asm_block.successors[0]]

    def build_block(self, ir_block: IRBlock) -> ASMBlock:
        block = ASMBlock(self.block_namer.get(), ir_block)
        for cmd in ir_block.cmds:
            if isinstance(cmd, IRPhi):
                # Skip phi nodes for now
                continue
            elif isinstance(cmd, IRBinOp):
                dest, store_cmd = self.prepare_dest(cmd.dest)
                if cmd.op == "add" and cmd.lhs == "0":
                    # special case: li
                    block.add_cmd(ASMCmd("li", dest, [self.parse_imm(cmd.rhs)]))
                elif cmd.op == "sub" and cmd.lhs == "0":
                    # special case: neg
                    _, rhs = self.prepare_operands(block, cmd.lhs, cmd.rhs)
                    if isinstance(rhs, OperandImm):
                        # temporary
                        block.add_cmd(ASMCmd("li", dest, [-rhs.imm]))
                    else:
                        block.add_cmd(ASMCmd("neg", dest, [rhs]))
                else:
                    lhs, rhs = self.prepare_operands(block, cmd.lhs, cmd.rhs)
                    assert not isinstance(lhs, OperandImm)
                    assert not isinstance(rhs, OperandImm) or rhs.is_lower()
                    if cmd.op in ["add", "and", "or", "xor"]:
                        op = cmd.op
                        if isinstance(rhs, OperandImm):
                            op += "i"
                        block.add_cmd(ASMCmd(op, dest, [lhs, rhs]))
                    elif cmd.op == "sub":
                        if isinstance(rhs, OperandImm):
                            block.add_cmd(ASMCmd("addi", dest, [lhs, - rhs.imm]))
                        else:
                            block.add_cmd(ASMCmd("sub", dest, [lhs, rhs]))
                    elif cmd.op in ["shl", "ashr"]:
                        # there is no shr in the input IR
                        op = "sll" if cmd.op == "shl" else "sra"
                        if isinstance(rhs, OperandImm):
                            op += "i"
                        block.add_cmd(ASMCmd(op, dest, [lhs, rhs]))
                    elif cmd.op in ["mul", "sdiv", "srem"]:
                        # there are no udiv and urem in the input IR
                        op = {"mul": "mul", "sdiv": "div", "srem": "rem"}[cmd.op]
                        block.add_cmd(ASMCmd(op, dest, [lhs, rhs]))
                    else:
                        raise AssertionError(f"Unknown binary command: {cmd.llvm()}")
                if store_cmd is not None:
                    block.add_cmd(store_cmd)
            elif isinstance(cmd, IRIcmp):
                dest, store_cmd = self.prepare_dest(cmd.dest)
                lhs, rhs = self.prepare_operands(block, cmd.lhs, cmd.rhs)
                assert not isinstance(lhs, OperandImm)
                assert not isinstance(rhs, OperandImm) or rhs.is_lower()
                if cmd.rhs == "0":
                    assert cmd.op in ["slt", "sgt", "ne", "eq"]
                    op = {"slt": "sltz", "sgt": "sgtz", "ne": "snez", "eq": "seqz"}[cmd.op]
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
                if cmd.src in self.allocation_table:
                    addr, _ = self.prepare_operand(block, cmd.src, "t0")
                    assert not isinstance(addr, OperandImm)
                    block.add_cmd(ASMMemOp("lw", dest, 0, str(addr)))
                else:
                    addr = self.global_symbol_table[cmd.src]
                    block.add_cmd(ASMMemOp("lw", dest, addr.label))
                if store_cmd is not None:
                    block.add_cmd(store_cmd)
            elif isinstance(cmd, IRStore):
                if cmd.dest in self.allocation_table:
                    value, pos = self.prepare_operands(block, cmd.src, cmd.dest)
                    assert not isinstance(value, OperandImm)
                    assert not isinstance(pos, OperandImm)
                    block.add_cmd(ASMMemOp("sw", str(value), 0, str(pos)))
                else:
                    value, tmp_used = self.prepare_operand(block, cmd.src, "t0")
                    tmp_reg = "t1" if tmp_used else "t0"
                    assert not isinstance(value, OperandImm)
                    pos = self.global_symbol_table[cmd.dest]
                    block.add_cmd(ASMMemOp("sw", str(value), pos.label, tmp_reg=tmp_reg))
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
                block.add_cmd(*self.restore_registers(self.callee_reg, self.current_function.stack_size))
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
                    ["ra"]
                    + [f"t{i}" for i in range(2, 7)]
                    + [f"a{i}" for i in range(8)]
                )
                caller_regs = list(caller_regs)
                caller_regs.sort()
                block.add_cmd(*self.save_registers(caller_regs, self.current_function.stack_size))

                param_count = len(cmd.func.param_ir_names)

                stack_delta = max(0, param_count - 8) * 4
                stack_delta = (stack_delta + 15) // 16 * 16
                if stack_delta > 0:
                    block.add_cmd(ASMCmd("addi", "sp", ["sp", str(-stack_delta)]))

                param_to = self.prepare_params(param_count)
                param_from = self.prepare_var_from(cmd.var_use)
                block.add_cmd(*self.rearrange_variables(param_from, param_to, "t0"))

                block.add_cmd(ASMCall(func_name))

                if stack_delta > 0:
                    block.add_cmd(ASMCmd("addi", "sp", ["sp", str(stack_delta)]))

                if cmd.dest:
                    result_to = self.prepare_var_to(cmd.var_def)
                    block.add_cmd(*self.rearrange_variables([OperandReg("a0")], result_to, "t0"))

                block.add_cmd(*self.restore_registers(caller_regs, self.current_function.stack_size))
            # There is no alloca nor gep in the input IR
            else:
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
        asm_blocks.extend(new_blocks)


if __name__ == '__main__':
    from antlr_generated.MxLexer import MxLexer
    from antlr_generated.MxParser import MxParser
    from syntax_checker import SyntaxChecker
    import sys
    import antlr4
    from syntax_error import MxSyntaxError, ThrowingErrorListener
    from ir_builder import IRBuilder
    from ir_repr import IRModule
    from opt_mem2reg import mem2reg
    from opt_mir import mir_builder
    from opt_liveness_analysis import liveness_analysis

    if len(sys.argv) == 1:
        # test_file_path = "./testcases/demo/d7.mx"
        test_file_path = "./testcases/codegen/e10.mx"
        input_stream = antlr4.FileStream(test_file_path, encoding='utf-8')
    else:
        input_stream = antlr4.StdinStream(encoding='utf-8')
    lexer = MxLexer(input_stream)
    parser = MxParser(antlr4.CommonTokenStream(lexer))

    # Attach error listeners
    error_listener = ThrowingErrorListener()
    lexer.removeErrorListeners()
    lexer.addErrorListener(error_listener)
    parser.removeErrorListeners()
    parser.addErrorListener(error_listener)

    try:
        tree = parser.file_Input()
        checker = SyntaxChecker()
        recorder = checker.visit(tree)
        print("Syntax check passed", file=sys.stderr)
    except MxSyntaxError as e:
        print(f"Syntax check failed: {e}", file=sys.stderr)
        print(e.standardize())
        exit(1)

    ir_builder = IRBuilder(recorder)
    ir: IRModule = ir_builder.visit(tree)
    print("IR building done", file=sys.stderr)

    ir.for_each_function_definition(mem2reg)

    print("M2R done", file=sys.stderr)
    with open("output.ll", "w") as f:
        print(ir.llvm(), file=f)
        print("IR output to" + "output.ll", file=sys.stderr)

    ir.for_each_block(mir_builder)
    print("MIR done", file=sys.stderr)
    with open("output-mir.ll", "w") as f:
        print(ir.llvm(), file=f)
        print("MIR output to" + "output.ll", file=sys.stderr)

    ir.for_each_function_definition(liveness_analysis)
    print("Liveness analysis done", file=sys.stderr)

    asm_builder = ASMBuilder(ir)
    asm = asm_builder.build()
    print("ASM building done", file=sys.stderr)
    print(asm.riscv())
    with open("output-asm.s", "w") as f:
        print(asm.riscv(), file=f)
        print("MIR output to" + "output.ll", file=sys.stderr)
