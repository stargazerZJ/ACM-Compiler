import dominator
from ir_repr import BasicBlock, IRModule


def mark_blocks(blocks: list[BasicBlock]):
    for ind, block in enumerate(blocks):
        block.index = ind


def build_graph(blocks: list[BasicBlock]) -> dominator.graph_type:
    return [[s.index for s in block.successors] for block in blocks]