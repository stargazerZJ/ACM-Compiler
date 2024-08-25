import dominator
from ir_renamer import renamer
from ir_repr import BasicBlock, IRFunction, IRStore, IRAlloca, IRLoad, IRPhi


def mark_blocks(blocks: list[BasicBlock]):
    for ind, block in enumerate(blocks):
        block.index = ind


def build_graph(blocks: list[BasicBlock]) -> dominator.graph_type:
    return [[s.index for s in block.successors] for block in blocks]


def collect_mem_defs(blocks: list[BasicBlock], allocas: set[str]):
    # return [{var for cmd in block for var in cmd.var_def} for block in blocks]
    return [{cmd.dest
             for cmd in block
             if isinstance(cmd, IRStore) and cmd.dest in allocas}
            for block in blocks]


def collect_allocas(blocks: list[BasicBlock]):
    block = blocks[0]
    return {cmd.dest for cmd in block if isinstance(cmd, IRAlloca)}, \
        {cmd.dest: cmd.typ for cmd in block if isinstance(cmd, IRAlloca)}


class IRUndefinedValue:
    typ: str

    def __init__(self, typ: str):
        self.typ = typ

    def llvm(self):
        if self.typ == "i32":
            return "0"
        elif self.typ == "i1":
            return "false"
        return "null"

    def __str__(self):
        return self.llvm()


class PhiMap:
    dest: str
    values: dict[int, str]

    def __init__(self, pointer_name: str):
        self.dest = renamer.get_name(pointer_name.rstrip(".ptr") + ".val")
        self.values = {}


def mem2reg(function: IRFunction):
    blocks: list[BasicBlock] = function.blocks
    n = len(blocks)

    mark_blocks(blocks)
    cfg = build_graph(blocks)
    allocas, type_map = collect_allocas(blocks)
    defs = collect_mem_defs(blocks, allocas)
    dominance_frontier_pred = dominator.get_indirect_predecessor_set_of_dominator_frontier(cfg)
    phi_map = [
        {pointer_name: PhiMap(pointer_name)
         for pointer_name in set.union(*(
            defs[pred] for pred in preds
        ))}
        if preds else {}
        for preds in dominance_frontier_pred
    ]
    stack: dict[str, list[str | IRUndefinedValue]] = {
        pointer_name: [IRUndefinedValue(type_map[pointer_name])]
        for pointer_name in allocas
    }
    rename_map: dict[str, str] = {}
    visited = set()

    def dfs(index: int):
        visited.add(index)
        for pointer_name, info in phi_map[index].items():
            stack[pointer_name].append(info.dest)
        for cmd in blocks[index]:
            cmd.var_use = [
                rename_map.get(var, var) for var in cmd.var_use
            ]
            if isinstance(cmd, IRStore):
                if cmd.dest in allocas:
                    stack[cmd.dest].append(cmd.src)
            elif isinstance(cmd, IRLoad):
                if cmd.src in allocas:
                    rename_map[cmd.dest] = stack[cmd.src][-1]
        for succ in blocks[index].successors:
            for pointer_name, info in phi_map[succ.index].items():
                info.values[index] = stack[pointer_name][-1]
            if succ.index not in visited:
                dfs(succ.index)
            else:
                for cmd in succ:
                    if not isinstance(cmd, IRPhi): break
                    cmd.var_use = [
                        rename_map.get(var, var) for var in cmd.var_use
                    ]
        for pointer_name, info in phi_map[index].items():
            stack[pointer_name].pop()
        for cmd in blocks[index]:
            if isinstance(cmd, IRStore):
                if cmd.dest in allocas:
                    stack[cmd.dest].pop()
        blocks[index].cmds = [cmd for cmd in blocks[index]
                              if (not isinstance(cmd, IRLoad) or cmd.src not in allocas)
                              and (not isinstance(cmd, IRStore) or cmd.dest not in allocas)]

    dfs(0)

    for phi_map_item, block in zip(phi_map, blocks):
        if any( all(isinstance(value, IRUndefinedValue) for value in phi.values.values())
                for phi in phi_map_item.values()):
            block.is_unreachable = True

        phi_cmds = [
            IRPhi(phi.dest, type_map[pointer_name],
                  [(blocks[i], value) for i, value in phi.values.items()])
            for pointer_name, phi in phi_map_item.items()
        ]

        block.cmds = phi_cmds + block.cmds

    blocks[0].cmds = [cmd for cmd in blocks[0].cmds if not isinstance(cmd, IRAlloca)]


if __name__ == '__main__':
    from antlr_generated.MxLexer import MxLexer
    from antlr_generated.MxParser import MxParser
    from syntax_checker import SyntaxChecker
    import sys
    import antlr4
    from syntax_error import MxSyntaxError, ThrowingErrorListener
    from ir_builder import IRBuilder
    from ir_repr import IRModule

    # test_file_path = "./testcases/codegen/t71.mx"
    # input_stream = antlr4.FileStream(test_file_path, encoding='utf-8')
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
        exit(1)

    ir_builder = IRBuilder(recorder)
    ir: IRModule = ir_builder.visit(tree)
    print("IR building done", file=sys.stderr)

    for function in ir.functions:
        if not function.is_declare():
            mem2reg(function)

    print("M2R done", file=sys.stderr)
    print(ir.llvm())
