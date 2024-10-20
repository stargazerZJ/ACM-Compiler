import functools

from asm_repr import ASMBlock, ASMMemOp, ASMCmdBase, ASMCmd, ASMMove, ASMFunction
from typing import cast


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


def eliminate_ring_reg(tmp_reg, nodes: list[str]) -> list[ASMMove]:
    n = len(nodes)
    if n == 1:
        # self loop
        return []
    ret = [ASMMove(tmp_reg, nodes[0]), ASMMove(nodes[0], nodes[n - 1])]
    # tmp <- 0, 0 <- (n-1)
    for i in range(n - 1, 1, -1):
        # (n-1) <- (n-2), ..., 2 <- 1
        ret.append(ASMMove(nodes[i], nodes[i - 1]))
    # 1 <- tmp
    ret.append(ASMMove(nodes[1], tmp_reg))
    return ret


def eliminate_tree_reg(graph, u: str) -> list[ASMMove]:
    ret = []
    for v in graph[u]:
        ret.extend(eliminate_tree_reg(graph, v))
    for v in graph[u]:
        ret.append(ASMMove(v, u))  # move v <- u
    return ret


def xor_swap_on_stack(tmp_reg1, tmp_reg2, var1: int, var2: int) -> list[ASMCmd | ASMMemOp]:
    return [
        # var1 <- var1 ^ var2
        ASMMemOp("lw", tmp_reg1, var1, "sp"),
        ASMMemOp("lw", tmp_reg2, var2, "sp"),
        ASMCmd("xor", tmp_reg1, [tmp_reg1, tmp_reg2]),
        ASMMemOp("sw", tmp_reg1, var1, "sp", tmp_reg=tmp_reg2),
        # var2 <- var1 ^ var2
        ASMMemOp("lw", tmp_reg1, var1, "sp"),
        ASMMemOp("lw", tmp_reg2, var2, "sp"),
        ASMCmd("xor", tmp_reg2, [tmp_reg1, tmp_reg2]),
        ASMMemOp("sw", tmp_reg2, var2, "sp", tmp_reg=tmp_reg1),
        # var1 <- var1 ^ var2
        ASMMemOp("lw", tmp_reg1, var1, "sp"),
        ASMMemOp("lw", tmp_reg2, var2, "sp"),
        ASMCmd("xor", tmp_reg1, [tmp_reg1, tmp_reg2]),
        ASMMemOp("sw", tmp_reg1, var1, "sp", tmp_reg=tmp_reg2)
    ]


def eliminate_ring_stack(tmp_reg1, tmp_reg2, nodes: list[int]) -> list[ASMCmdBase]:
    ret = []
    n = len(nodes)
    if n == 1:
        # self loop
        return []
    for i in range(n - 1, 0, -1):
        ret.extend(xor_swap_on_stack(tmp_reg1, tmp_reg2, nodes[i], nodes[(i + 1) % n]))
    return ret


def eliminate_tree_stack(tmp_reg1, tmp_reg2, graph, u: int) -> list[ASMMemOp]:
    ret = []
    for v in graph[u]:
        ret.extend(eliminate_tree_stack(tmp_reg1, tmp_reg2, graph, v))
    ret.append(ASMMemOp("lw", tmp_reg1, u, "sp"))
    for v in graph[u]:
        # lw tmp_reg <- node v, sw tmp_reg -> node u
        ret.append(ASMMemOp("sw", tmp_reg1, v, "sp", tmp_reg=tmp_reg2))
    return ret


def find_ring(graph: dict[str, list[str]]) -> list[str]:
    visited = set()
    path = []

    def dfs(node: str) -> list[str] | None:
        if node in visited:
            if node in path:
                return path[path.index(node):]
            return None
        visited.add(node)
        path.append(node)
        for neighbor in graph[node]:
            result = dfs(neighbor)
            if result:
                return result
        path.pop()
        return None

    for node in graph:
        ring = dfs(node)
        if ring:
            return ring
    return []


def eliminate_forest(graph, eliminate_ring, eliminate_tree) \
        -> tuple[list[ASMMove | ASMMemOp], list[ASMMove | ASMMemOp]]:
    # steps:
    # 1. find all rings
    # 2. for each ring:
    #   ring_nodes = nodes in the ring, in order
    #   ring_cmds += eliminate_ring(ring_nodes)
    #   delete the ring from the graph
    # 3. Now the graph is a forest, for each node whose in degree is 1:
    #   tree_cmds += eliminate_tree(header_node)
    #   cmds += tree_cmds + ring_cmds

    ring_cmds: list[ASMMove | ASMMemOp] = []
    while True:
        ring = find_ring(graph)
        if not ring:
            break
        ring_cmds.extend(eliminate_ring(ring))
        for i in range(len(ring)):
            graph[ring[i]].remove(ring[(i + 1) % len(ring)])

    tree_cmds: list[ASMMove | ASMMemOp] = []
    in_degree = {node: sum(node in graph[v] for v in graph) for node in graph}
    for node in graph:
        if in_degree[node] == 0:
            tree_cmds.extend(eliminate_tree(graph, node))
    return ring_cmds, tree_cmds


def rearrange_operands(var_from: list[OperandBase], var_to: list[OperandStack | OperandReg], tmp_reg: str,
                       tmp_reg2: str) \
        -> list[ASMCmdBase]:
    assert len(var_from) == len(var_to), "The number of operands should be the same"
    cmds: list[ASMCmdBase] = []

    # the registers / stack offsets in var_to must be distinct,
    # so the in degree of each node is <= 1
    # so the graph is an outward base-ring-tree forest
    graph_stack: dict[int, list[int]] = {}

    # build the graph for stack
    for f, t in zip(var_from, var_to):
        if not isinstance(f, OperandStack) or not isinstance(t, OperandStack):
            continue
        f, t = f.offset, t.offset
        if f not in graph_stack: graph_stack[f] = []
        if t not in graph_stack: graph_stack[t] = []
        graph_stack[f].append(t)

    if graph_stack:
        ring_cmds, tree_cmds = eliminate_forest(graph_stack,
                                                functools.partial(eliminate_ring_stack, tmp_reg, tmp_reg2),
                                                functools.partial(eliminate_tree_stack, tmp_reg, tmp_reg2))
        cmds.extend(tree_cmds)
        cmds.extend(ring_cmds)

    for f, t in zip(var_from, var_to):
        if isinstance(t, OperandStack):
            if isinstance(f, OperandStack):
                continue
            elif isinstance(f, OperandImm):
                if f.imm == 0:
                    reg = "zero"
                else:
                    cmds.append(ASMCmd("li", tmp_reg, [str(f)]))
                    reg = tmp_reg
            elif isinstance(f, OperandReg):
                f = cast(OperandReg, f)
                reg = f.reg
            elif isinstance(f, OperandGlobal):
                if f.label.startswith(".str"):
                    cmds.append(ASMMemOp("la", tmp_reg, f.label))
                else:
                    cmds.append(ASMMemOp("lw", tmp_reg, f.label))
                    raise AssertionError("Global variable should not be used as source operand")
                reg = tmp_reg
            else:
                raise AssertionError("Invalid source operand")
            cmds.append(ASMMemOp("sw", reg, t.offset, "sp", tmp_reg=tmp_reg2))

    graph_reg: dict[str, list[str]] = {}

    # build the graph for register
    for f, t in zip(var_from, var_to):
        if not isinstance(f, OperandReg) or not isinstance(t, OperandReg):
            continue
        f, t = f.reg, t.reg
        if f not in graph_reg: graph_reg[f] = []
        if t not in graph_reg: graph_reg[t] = []
        graph_reg[f].append(t)

    if graph_reg:
        ring_cmds, tree_cmds = eliminate_forest(graph_reg,
                                                functools.partial(eliminate_ring_reg, tmp_reg),
                                                eliminate_tree_reg)
        cmds.extend(tree_cmds)
        cmds.extend(ring_cmds)

    for f, t in zip(var_from, var_to):
        if not isinstance(t, OperandReg): continue
        if isinstance(f, OperandStack):
            cmds.append(ASMMemOp("lw", t.reg, f.offset, "sp"))
        elif isinstance(f, OperandImm):
            cmds.append(ASMCmd("li", t.reg, [str(f)]))
        elif isinstance(f, OperandGlobal):
            if f.label.startswith(".str"):
                cmds.append(ASMMemOp("la", t.reg, f.label))
            else:
                cmds.append(ASMMemOp("lw", t.reg, f.label))
                raise AssertionError("Global variable should not be used as source operand")

    return cmds
