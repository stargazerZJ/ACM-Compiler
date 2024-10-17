import dominator
from ir_repr import IRBlock, IRModule, IRCmdBase


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
