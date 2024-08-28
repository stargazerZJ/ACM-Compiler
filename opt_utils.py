import dominator
from ir_repr import IRBlock, IRModule


def mark_blocks(blocks: list[IRBlock]):
    for ind, block in enumerate(blocks):
        block.index = ind


def build_graph(blocks: list[IRBlock]) -> dominator.graph_type:
    return [[s.index for s in block.successors] for block in blocks]