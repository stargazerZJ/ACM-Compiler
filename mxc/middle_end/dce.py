from mxc.common.ir_repr import IRBranch, IRRet, IRStore, IRCall, IRCmdBase, IRJump, IRFunction
from .utils import collect_commands, collect_var_use
from queue import Queue


def build_node(cmds: list[IRCmdBase]):
    for cmd in cmds:
        if cmd.var_def:
            cmd.node = cmd.var_def[0]
        elif isinstance(cmd, IRBranch):
            cmd.node = "branch"
        elif isinstance(cmd, IRJump):
            cmd.node = "jump"
        elif isinstance(cmd, IRRet):
            cmd.node = "ret"
        elif isinstance(cmd, IRStore):
            cmd.node = "store"
        elif isinstance(cmd, IRCall):
            # Only void function call goes here
            cmd.node = "call_no" if cmd.func.no_effect and not cmd.tail_call else "call"
        else:
            raise AssertionError("Invalid node")


def build_graph(cmds: list[IRCmdBase]) -> dict[str, set[str]]:
    build_node(cmds)
    graph = {cmd.node: set() for cmd in cmds}
    graph["effect"] = {"branch", "jump", "ret", "store", "call"}
    graph["call"] = set()
    for cmd in cmds:
        if isinstance(cmd, IRCall) and cmd.var_def and not cmd.func.no_effect:
            graph["call"].add(cmd.node)
        graph[cmd.node].update((use for use in cmd.var_use if use.startswith('%')))
    return graph


def bfs(graph: dict[str, set[str]], start: str):
    queue = Queue()
    queue.put(start)
    visited = {start}
    while queue:
        node = queue.get()
        for next_node in graph[node]:
            if next_node not in visited and next_node in graph:
                visited.add(next_node)
                queue.put(next_node)
    return visited


def naive_dce(function: IRFunction):
    blocks = function.blocks
    cmds = collect_commands(blocks)

    graph = build_graph(cmds)
    live = bfs(graph, "effect")

    for block in blocks:
        block.cmds = [cmd for cmd in block.cmds if cmd.node in live]

    # Remove unused var_def for IRCall
    # and maintain function.is_leaf
    function.is_leaf = True
    cmds = collect_commands(blocks)
    var_use = collect_var_use(cmds)
    for cmd in cmds:
        if isinstance(cmd, IRCall):
            function.is_leaf = False
            if cmd.var_def and cmd.var_def[0] not in var_use:
                cmd.var_def = []
