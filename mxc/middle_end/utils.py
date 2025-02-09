from mxc.common import dominator
from mxc.common.ir_repr import IRBlock, IRCmdBase, IRFunction


def mark_blocks(blocks: list[IRBlock]):
    for ind, block in enumerate(blocks):
        block.index = ind


def build_control_flow_graph(blocks: list[IRBlock]) -> dominator.graph_type:
    return [[s.index for s in block.successors] for block in blocks]


def collect_commands(blocks: list[IRBlock]) -> list:
    command_list = []
    for block in blocks:
        command_list += block.cmds
    return command_list


def collect_var_use(cmds: list[IRCmdBase]) -> set[str]:
    return set(use for cmd in cmds for use in cmd.var_use)

def rearrange_in_rpo(function: IRFunction):
    """Rearrange blocks in reverse post order"""
    blocks = function.blocks
    visited = set()
    new_blocks = []

    def dfs(index: int):
        visited.add(index)
        for succ in blocks[index].successors:
            if succ.index not in visited:
                dfs(succ.index)
        new_blocks.append(blocks[index])

    dfs(0)
    function.blocks = new_blocks[::-1]
    return new_blocks
