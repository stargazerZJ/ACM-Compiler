from asm_regalloc import AllocationBase, AllocationGlobal, allocate_registers, AllocationStack, AllocationRegister
from asm_repr import ASMGlobal, ASMFunction, ASMStr, ASMModule, ASMBlock, ASMCmd, ASMMemOp
from ir_repr import IRGlobal, IRModule, IRFunction, IRStr, IRBlock, IRPhi


class BlockNamer:
    def __init__(self, func_name: str):
        self.counter = 0
        self.func_name = func_name

    def get(self) -> str:
        name = f".L-{self.func_name}-{self.counter}"
        self.counter += 1
        return name


class ASMBuilder:
    ir_module: IRModule
    global_symbol_table: dict[str, AllocationBase]
    max_saved_reg: int
    block_namer: BlockNamer
    current_function: IRFunction
    used_reg: set[str]

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
        if cmd.value in ["true", "false", "null"]:
            value = "0" if cmd.value != "true" else "1"
        else:
            value = cmd.value
        return ASMGlobal(name, value)

    @staticmethod
    def build_str(cmd: IRStr) -> ASMStr:
        name = cmd.name.lstrip("@")
        return ASMStr(name, cmd.value)

    def build_function(self, ir_func: IRFunction) -> ASMFunction:
        name = ir_func.info.ir_name.lstrip("@")
        func = ASMFunction(name, ir_func)
        allocation_table = allocate_registers(ir_func)
        self.max_saved_reg = 0
        self.block_namer = BlockNamer(name)
        self.current_function = ir_func
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

        blocks = [self.build_block(block, allocation_table) for block in ir_func.blocks]
        self.link_blocks(blocks, ir_func)
        self.eliminate_phi(blocks, ir_func)

        func.stack_size += self.max_saved_reg * 4
        func.stack_size = (func.stack_size + 15) // 16 * 16

        header_block = ASMBlock(header_name)
        if func.stack_size > 0:
            # TODO: stack_size > 4096
            header_block.add_cmd(ASMCmd("addi", "sp", ["sp", str(-func.stack_size)]))
        ra_alloc = allocation_table["ret_addr"]
        if isinstance(ra_alloc, AllocationStack):
            header_block.add_cmd(ASMMemOp("sw", "ra", True, ra_alloc.offset))
        # TODO: function params and callee-saved registers

        blocks.insert(0, header_block)
        # TODO: rearrange blocks and relax branch offsets
        func.blocks = blocks
        return func

    def build_block(self, ir_block: IRBlock, allocation_table: dict[str, AllocationBase]) -> ASMBlock:
        block = ASMBlock(self.block_namer.get(), ir_block)
        for cmd in ir_block.cmds:
            if isinstance(cmd, IRPhi):
                # Skip phi nodes for now
                continue
            asm_cmd = self.build_cmd(cmd, allocation_table)
            block.add_cmd(asm_cmd)
        return block
